Picaso3d Designer X PRO command line tool
========================

Simple command line tool to monitor 3d-printer state.

Installation
------
```bash
 pip install pxctl
```


Examples
------

#### Show the printer status card

```bash
 pxctl show
```

```
╭────────────────────────────────────────────────╮
│ DPX00000000XX00                                │
│ 192.0.2.10                                     │
│                                                │
│ Printing                                       │
│ bracket-v2.plgx                                │
│ ███████████████░░░░░░░░░░░░░░░░░░░  42.7%      │
│                                                │
│ 1 157.0 °C             2  46.0 °C              │
│ 0.5  PETG (BF)(1)      0.3  ABS (BF)           │
│                                                │
│ Platform:  61.0 °C                             │
╰────────────────────────────────────────────────╯
```

The card border is tinted by status: green when the printer is idle or done,
blue while printing, yellow when it is paused or waiting for you, red on an
error. Set `NO_COLOR` to turn colours off; terminals without UTF-8 get an
ASCII frame automatically.

#### Show the status together with the models stored on the printer

```bash
 pxctl show --tasks
```

```
╭────────────────────────────────────────────────╮
│ default-printlist  (4)                         │
│ ▸ bracket-v2                            632 KB │
│   gear-housing                           49 KB │
│   spool-holder                          2.8 MB │
│   table-wheel-1                         5.6 MB │
╰────────────────────────────────────────────────╯
```

The task the printer currently has selected is marked and highlighted.

#### Upload a model to the printer

```bash
 pxctl task create -f model.plgx
 pxctl task create -f model.plgx --name 'bracket v2'
```

Shows upload progress and adds the model to the print list, where the slicer
and the printer's own screen pick it up. The name defaults to the file name.

Re-uploading the same file updates the task it came from rather than creating
a duplicate, because the task is identified by the GUID in its header. Pass
`--task-id` to upload under a different GUID and get a separate task.

#### List the models stored on the printer

```bash
 pxctl task list
 pxctl printlist list
```

#### Discover printer and show it's status continuously

```bash
 pxctl show --continuous
```

#### Show the state as a plain table instead of a card

```bash
 pxctl show --table
```


#### Specify printer ip address and show its status once

```bash
pxctl show --address=192.0.2.10
```


#### Discover every printer on the local network

```bash
  pxctl discover
 ```

Prints a card per printer found, each with its live state -- the same view the
official slicer's monitoring tab shows. Add `--continuous` to keep re-scanning,
or `--table` for a one-line-per-printer summary.

#### Discover printers and get list in json format

```bash
  pxctl discover --json
 ```


#### When discovery finds nothing

Discovery uses a UDP broadcast, which some access points rate-limit or drop
outright. Every command accepts `--address`, which talks to the printer over
unicast only and keeps working in that case:

```bash
 pxctl show --address=192.0.2.10
```

Make printer starts to beep

```bash
  pxctl beep_on --address=192.0.2.10
 ```

Make printer stops to beep

```bash
 pxctl beep_off
 ```

Run hooks when printer success

```bash
 pxctl show --on-success='echo 10'
 ```

Get printer status at json format

```bash 
 pxctl show --json

 ```

## How to build
```bash
make init
make build
```
---------------
