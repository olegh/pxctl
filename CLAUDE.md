# pxctl

Command line tool for Picaso3D printers. Talks to a printer over UDP on the
local network: reports its state, lists the models stored on it, and uploads
new ones.

Developed against a **Designer X Pro (1st gen)**. Other models in `PrinterType`
are recognised by hardware version but are untested.

## Layout

```
src/pxctl/     library -- protocol, parsing, no output formatting
  connection.py      UDP socket wrapper for the control port
  printer_service.py commands and response parsing (the core of the protocol)
  structs.py         dataclasses returned to callers
  enums.py           protocol enums, with human-readable status labels
  plgx.py            reads the metadata header of a .plgx task file
  tftp.py            TFTP write client used for uploads
  utils.py           broadcast address discovery, hardware version mapping
  notifications.py   --on-success hook

src/pxcli/     command line front end
  main.py            argparse wiring, one function per subcommand
  card.py            the status card and task list, drawn with box characters
  layout.py          three interchangeable output layouts
```

The split matters: `pxctl` must stay importable as a library with no printing
to stdout, and `pxcli` holds everything user-facing.

### Output layouts

`CardLayout` (default), `TableLayout` (`--table`) and `JsonLayout` (`--json`)
implement the same three methods: `print_info`, `print_discover`, `print_tasks`.
Adding a field means touching all three; leaving one behind is the usual bug.

## The protocol

Reverse-engineered from traffic; there is no vendor documentation. Everything
is UDP -- the printer has **no TCP ports open at all**.

| Port  | Use |
|-------|-----|
| 49149 | discovery: broadcast `PICASO3D` (8 ASCII bytes), printer answers unicast with a 191-byte descriptor |
| 54321 | control and status |
| 69    | TFTP, for uploading a model (write only -- a read request always fails) |

### Control requests

A request is 8 bytes: `<u16 version=1><u16 command><u16 zero><u16 length=8>`,
little-endian. Responses repeat the header and follow it with a payload.

| Command | Meaning |
|---------|---------|
| `0x01` | printing info: state, status, temperatures, current task, progress |
| `0x02` | print lists |
| `0x05` | delete a task (body: task GUID) |
| `0x07` | start printing a task (body: task GUID) |
| `0x09` | pause the running print |
| `0x0b` | resume a paused print |
| `0x0c` | printer descriptor: serial, MAC, extruders (also sent after discovery) |
| `0x0e` / `0x0f` | beep on / off |
| `0x11` | tasks stored on the printer |
| `0x12` | active print list GUID |
| `0x18` | register an uploaded task into a print list (see below) |

Commands not listed here answer with a bare 12-byte header. `0x13` is sent by
the official slicer immediately before an upload and its purpose is unknown;
uploads work without it. `0x19` carries print parameters and is sent before a
start and before a resume, both of which succeed without it. `0x20` returns
the material catalogue, unused so far.

`0x05` and `0x07` share the simplest body there is: the 8-byte header followed
by a 16-byte task GUID, 24 bytes in total. `0x09` and `0x0b` need no body at
all. All four answer with a status word at offset 8, where `1` means accepted.

A refused command is normal operation rather than an error to retry: the
printer declines a start when it is not idle instead of interrupting itself.

Note that accepted is not the same as done. A pause is acknowledged
immediately but the printer keeps moving until it reaches a safe point in the
layer, so `NetPrinterState` stays `npstPrinting` for a moment. A resume goes
through `npstPrepareForPrinting` before printing again. Poll the state rather
than assuming the transition happened.

Unknown command ids are not harmless to probe blindly: these are writes to
firmware. Sweeping the space found the listing commands, but anything that
might mutate state should be confirmed by capturing the official client first.

### Response offsets

Positions matter more than any struct format string, since several fields sit
in what earlier code treated as padding.

`0x01` printing info (344 bytes):
- `0x08` state code (`NetPrinterState`)
- `0x0c` status code (`NetPrinterStatus`) -- this is the headline the official
  app shows ("Print finished"); it was skipped as padding for a long time
- `0x10` ready flag, `0x11` current task file name (255 bytes)
- `0x128`/`0x134` extruder temperatures, `0x12c`/`0x138` a second pair,
  `0x134` platform -- all are live sensor readings, not targets

`0x0c` descriptor (191 bytes):
- `0x0d` serial, `0x53` MAC
- extruders at `(0x59, 0x63, 0x64)` and `(0x8C, 0x96, 0x97)`: type string,
  then a byte holding the nozzle diameter in hundredths of a millimetre
  (`50` -> 0.5 mm), then the material profile

`0x02` / `0x11` listings share a shape: record count at `0x0c`, fixed-size
records from `0x0e`. A task record is 60 bytes (32-byte name, 16-byte GUID,
version word, size at offset 52); a print list record is 48 (name and GUID).

### Text encoding

Strings are **CP1251**, not UTF-8 -- extruder types come through as `Блок400`.
Decoding as UTF-8 leaves stray bytes glued to material names. Always decode
with `errors="replace"` and strip trailing NULs.

### Timeouts

`Connection.recv()` defaults to 0.3 s, which is right for status queries. The
listing commands read from storage and can take well over half a second, so
they pass `_LIST_TIMEOUT`. A listing that silently returns empty is usually
this, not a parsing bug.

## Uploading a model

Two steps, and the second is easy to miss:

1. **TFTP write** the `.plgx` under `<task-guid>.plgx`, where the GUID is the
   `;TID:` line in the file's own header. Reusing that GUID means re-uploading
   a file updates the same task instead of creating a duplicate.
2. **Register it** with command `0x18`. Without this the data is stored but
   nothing appears in the print list.

The `0x18` request is 98 bytes:

| Offset | Field |
|--------|-------|
| `0x08` | GUID of the task to insert after |
| `0x18` | GUID of the new task (matches `;TID:`) |
| `0x28` | task name, 32 bytes |
| `0x48` | format version word, `02 00` |
| `0x4a` | size of the uploaded data |
| `0x52` | GUID of the print list |

The reply carries a status word at offset 8; `1` means accepted.

Uploads negotiate TFTP options (RFC 2347-2349) the way the slicer does. The
64 KB block size is not cosmetic: at the default 512 bytes a 7 MB model needs
over thirteen thousand round trips.

## Discovery is unreliable by nature

Discovery rides on UDP broadcast, which WiFi does not acknowledge at the link
layer. Access points also rate-limit or drop broadcast traffic, sometimes for
hours after a burst. Measured loss on a normal network was roughly one sweep
in six, and **a longer receive timeout does not help** -- the probes are
dropped, not delayed. Hence the retry loop in `discover_printers`.

Consequences to keep in mind:

- `--address` must never depend on discovery. `describe_printer()` fetches the
  descriptor over unicast precisely so every command keeps working when
  broadcast is blocked.
- When debugging "no printers found", first check whether unicast to a known
  address still works. If it does, it is the network, not the code.

## Testing

There is no test suite and no printer simulator, so changes are verified
against real hardware:

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/pxctl show --address <printer-ip>
```

Use `--address` while testing to take broadcast out of the picture. When
changing parsing, check all three layouts and both the connected and
unreachable paths -- `pxctl show --address 192.0.2.1` should report
`NOT CONNECTED` rather than crash.

For protocol work, capture the official slicer talking to the printer and
compare. Filtering the capture down to *requests with a body* is what makes
commands findable: everything else on the control channel is a bare 8-byte
poll repeating a few times a second. `0x18`, `0x05` and `0x07` were all found
this way.

Take care when probing unknown ids by hand: those probes land in your own
captures and look like discoveries. Identify a command by triggering it from
the official client and matching the GUID in its body against a known task.

## Conventions

- Comments explain why, not what; the offset tables above belong in code as
  named constants, not magic numbers scattered through a format string.
- User-facing strings are English. Decoded printer strings may be Russian --
  that comes from the firmware.
- The card renderer tracks visible width itself (`_visible_width`) because ANSI
  escapes would otherwise break the frame alignment. Style text with `_paint`
  and let it handle the escapes; never concatenate escape codes by hand.
- Keep README examples consistent with real output. They are generated by
  running the renderer, and hand-edited widths drift out of alignment.
- Documentation and examples use `192.0.2.x` (RFC 5737) and a placeholder
  serial. Do not commit real addresses, serial numbers or MACs.
