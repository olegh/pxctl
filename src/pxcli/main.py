#!/usr/bin/env python

import argparse
import json
import os
import sys
import signal
from time import sleep

from pxctl.notifications import Notifications
from pxctl.printer_service import Connection, PrinterService
from pxctl.tftp import TftpError
from .layout import CardLayout, JsonLayout, TableLayout

cur_dir = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.realpath(cur_dir)

if os.path.isdir(SRC_DIR):
    sys.path.insert(0, SRC_DIR)



def signal_handler(sig, frame):
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def resolve_printer(args):
    """Returns (address, Printer|None) for the printer to talk to.

    The descriptor carries the serial, nozzle sizes and loaded materials, which
    only the discovery response reports -- so it is fetched even when an
    explicit address is given, and simply left out if discovery finds nothing.
    """
    # An explicit address is asked directly, so the command keeps working
    # where discovery broadcasts are dropped.
    if args.address:
        return args.address, PrinterService.describe_printer(args.address)

    printers = PrinterService.discover_printers()

    if not printers:
        print(
            "No printers answered the discovery broadcast.\n"
            "Discovery relies on UDP broadcast, which some access points rate-limit "
            "or drop; a printer that is reachable directly will still work.\n"
            "Try again, or address it explicitly: pxctl show --address 192.0.2.10",
            file=sys.stderr,
        )
        sys.exit(-1)

    return printers[0].ip_address, printers[0]


def get_address(args) -> str:
    return resolve_printer(args)[0]


def get_layout(args):
    if args.json:
        return JsonLayout()
    if getattr(args, "table", False):
        return TableLayout()
    return CardLayout()


def show(args):
    layout_service = get_layout(args)
    address, printer = resolve_printer(args)
    should_repeat = args.continuous
    with_tasks = getattr(args, "tasks", False)

    notifications = Notifications(args.on_success)

    with Connection(address) as connection:
        print_service = PrinterService(connection)

        while True:
            optional_info = print_service.get_printing_info()
            layout_service.print_info(
                address, optional_info, printer, clear=should_repeat
            )
            if with_tasks:
                layout_service.print_tasks(
                    print_service.get_printlists(),
                    optional_info.current_task_file if optional_info else "",
                )
            notifications.update_state(optional_info)

            if not should_repeat:
                break

            sleep(0.6)


def collect_states(printers) -> dict:
    """Queries each discovered printer so the cards show live state."""
    states = {}
    for printer in printers:
        with Connection(printer.ip_address) as connection:
            states[printer.ip_address] = PrinterService(connection).get_printing_info()
    return states


def discover(args):
    layout_service = get_layout(args)
    should_repeat = getattr(args, "continuous", False)

    while True:
        printers = PrinterService.discover_printers()
        states = collect_states(printers) if not args.json else None
        layout_service.print_discover(printers, states, clear=should_repeat)

        if not should_repeat:
            break

        sleep(0.6)


def beep_on(address):
    with Connection(address) as connection:
        printer_service = PrinterService(connection)
        printer_service.beep_on()


def beep_off(address):
    with Connection(address) as connection:
        printer_service = PrinterService(connection)
        printer_service.beep_off()


def beep(args):
    address = get_address(args)
    if args.operation == "enable":
        beep_on(address)

    if args.operation == "disable":
        beep_off(address)


def list_tasks(args):
    """Shows the print lists and the models stored on the printer."""
    layout_service = get_layout(args)
    address = get_address(args)

    with Connection(address) as connection:
        printer_service = PrinterService(connection)
        printlists = printer_service.get_printlists()
        state = printer_service.get_printing_info()

    layout_service.print_tasks(printlists, state.current_task_file if state else "")


def upload_task(args):
    """Sends a .plgx model to the printer."""
    if not args.file:
        print("Specify the file to upload: pxctl task create -f model.plgx", file=sys.stderr)
        sys.exit(-1)

    if not os.path.isfile(args.file):
        print(f"No such file: {args.file}", file=sys.stderr)
        sys.exit(-1)

    address = get_address(args)
    quiet = args.json

    def show_progress(sent: int, total: int):
        if quiet or not sys.stderr.isatty():
            return
        percent = 100.0 * sent / total if total else 100.0
        print(f"\rUploading {percent:5.1f}%  ({sent:,}/{total:,} bytes)",
              end="", file=sys.stderr, flush=True)

    try:
        task_file = PrinterService.upload_task(
            address, args.file, task_id=args.task_id, name=args.name,
            progress=show_progress,
        )
    except (TftpError, RuntimeError) as error:
        if not quiet and sys.stderr.isatty():
            print(file=sys.stderr)
        print(f"Upload failed: {error}", file=sys.stderr)
        sys.exit(-1)

    if not quiet and sys.stderr.isatty():
        print(file=sys.stderr)

    if args.json:
        print(json.dumps({
            "task_id": task_file.task_id,
            "name": args.name or task_file.default_name,
            "uploaded_as": task_file.upload_name,
            "size_bytes": len(task_file.payload),
            "address": address,
        }))
    else:
        name = args.name or task_file.default_name
        print(f"Uploaded {os.path.basename(args.file)} "
              f"({len(task_file.payload):,} bytes) and added it as {name!r}.")


def printlist(args):
    if args.operation == "list":
        list_tasks(args)
    else:
        print("Not implemented yet", file=sys.stderr)


def task(args):
    if args.operation == "list":
        list_tasks(args)
    elif args.operation == "create":
        upload_task(args)
    else:
        print("Not implemented yet", file=sys.stderr)


def execute(args):
    print("Not implemented yet", file=sys.stderr)


EPILOG = """\
Typical use:
  pxctl show                       status card for the first printer found
  pxctl show --tasks               status plus the models stored on the printer
  pxctl show --continuous          redraw the card until interrupted
  pxctl task list                  list the stored models
  pxctl discover                   find every printer on the LAN
  pxctl show --json                machine-readable output (every command takes --json)

Addressing:
  Without --address the printer is located with a UDP broadcast. Some access
  points rate-limit or drop broadcasts; if discovery reports nothing, pass
  --address to talk to the printer directly, which only uses unicast:
    pxctl show --address 192.0.2.10

Output formats:
  default   a card drawn with terminal graphics, for a human reader
  --table   one row per printer or task, for grep and awk
  --json    structured output, the format to parse from a script or an agent

Exit codes:
  0  success
  -1 no printer found, or a subcommand was called without an operation

Notes for automated callers:
  Temperatures are degrees Celsius, sizes are bytes, progress is a percentage.
  The status field is a stable enum name (npsPrintDone, npsMainPrint, ...) and
  status_description is its English label; prefer the enum for logic.
  A task name reported as current carries a .plgx suffix that the task list
  omits, so strip the extension before comparing.
"""


def main():
    parser = argparse.ArgumentParser(
        prog="pxctl",
        description="Monitor and control a Picaso3D Designer X Pro over the network.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(metavar="COMMAND")

    ADDRESS_HELP = "Please provide the IPv4 address of the printer. By default, the printer is discovered automatically on the local network."
    PRINTLIST_HELP = "Please provide the name of the print list. If there is only one print list, it will be used by default."

    show_parser = subparsers.add_parser(
        "show",
        help="Show the printer state: status, temperatures, materials, progress.",
        description="Shows a status card: serial, status, progress, both extruders "
                    "with nozzle size and material, and the platform temperature.",
        epilog="Examples:\n"
               "  pxctl show\n"
               "  pxctl show --tasks\n"
               "  pxctl show --address 192.0.2.10 --json\n"
               "  pxctl show --continuous --on-success='notify-send done'",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    show_parser.add_argument("-j", "--json", help="Output the information of printer state in JSON format.",
                             action="store_true")
    show_parser.add_argument("-a", "--address", type=str, help=ADDRESS_HELP)
    show_parser.add_argument("-l", "--tasks", help="Also list the models stored on the printer.",
                             action="store_true")
    show_parser.add_argument("-t", "--table", help="Output the printer state as a plain table instead of a card.",
                             action="store_true")
    show_parser.add_argument("-c", "--continuous",
                             help="Continuously output the current state of the 3D printer to the standard output.",
                             action="store_true")
    show_parser.add_argument("-s", "--on-success", type=str,
                             help="Once the printing is complete, execute the bash script hook. example: %(prog)s --on-success='touch /tmp/done' ",
                             metavar="BASH_SCRIPT")
    show_parser.set_defaults(mode="show")

    beep_parser = subparsers.add_parser(
        "beep",
        help="Make the printer beep, to tell it apart from others.",
        description="Starts or stops the printer's identification beep.",
        epilog="Examples:\n"
               "  pxctl beep enable\n"
               "  pxctl beep disable",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    beep_parser.add_argument("operation",
                             help="Enable or disable the printer's beeping function for identification. Example: '%(prog)s enable'",
                             nargs="?",
                             choices=("enable", "disable"))
    beep_parser.add_argument("-a", "--address", type=str, help=ADDRESS_HELP)
    beep_parser.set_defaults(mode="beep")

    discover_parser = subparsers.add_parser(
        "discover",
        help="Find every printer on the local network.",
        description="Broadcasts a discovery probe and reports every printer that answers, "
                    "with its serial, address, nozzle sizes and loaded materials.",
        epilog="Examples:\n"
               "  pxctl discover\n"
               "  pxctl discover --json\n"
               "Discovery needs UDP broadcast; if it finds nothing, the printer may still "
               "be reachable via 'pxctl show --address IP'.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    discover_parser.add_argument("-j", "--json", help="Output the results of the printer discovery in JSON format.",
                                 action="store_true")
    discover_parser.add_argument("-t", "--table", help="Output the discovered printers as a plain table instead of cards.",
                                 action="store_true")
    discover_parser.add_argument("-c", "--continuous",
                                 help="Continuously re-scan the network and redraw the discovered printers.",
                                 action="store_true")
    discover_parser.set_defaults(mode="discover")

    printlist_parser = subparsers.add_parser(
        "printlist", aliases=["pl"],
        help="List the print lists on the printer (create/delete not implemented).",
        description="Lists the print lists held on the printer and the models in them.",
        epilog="Examples:\n"
               "  pxctl printlist list\n"
               "  pxctl pl list --json\n"
               "Only 'list' is implemented; create and delete are not yet supported.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    printlist_parser.add_argument("operation",
                                  help="'list' shows the print lists and their models. 'create' and 'delete' are not implemented yet.",
                                  nargs="?",
                                  choices=("create", "delete", "list")
                                  )
    printlist_parser.add_argument("-n", "--name", help="Please provide a name for the print-list")
    printlist_parser.add_argument("-a", "--address", type=str, help=ADDRESS_HELP)
    printlist_parser.add_argument("-j", "--json", help="Output the print lists in JSON format.",
                                  action="store_true")
    printlist_parser.add_argument("-t", "--table", help="Output the print lists as a plain table.",
                                  action="store_true")
    printlist_parser.set_defaults(mode="printlist")

    task_parser = subparsers.add_parser(
        "task",
        help="Upload a model to the printer, or list the models already stored.",
        description="Uploads a .plgx model to the printer, or lists the models it holds. "
                    "An upload needs no separate registration: the printer reads the task "
                    "id from the file header and adds it to the print list itself.",
        epilog="Examples:\n"
               "  pxctl task list\n"
               "  pxctl task create -f model.plgx\n"
               "  pxctl task create -f model.plgx --json\n"
               "'delete' is not implemented yet.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    task_parser.add_argument("operation",
                             help="'create' uploads a .plgx file (-f), 'list' shows the stored models. 'delete' is not implemented yet.",
                             nargs="?",
                             choices=("create", "delete", "list")
                             )
    task_parser.add_argument("-n", "--name", type=str,
                             help="Name to show in the print list. Defaults to the file name.")
    task_parser.add_argument("--task-id", type=str,
                             help="Task GUID to upload under. Defaults to the ;TID: value in the file, "
                                  "so re-uploading replaces that task instead of adding a duplicate.")
    task_parser.add_argument("-f", "--file", type=str,
                             help="Path to the .plgx file to upload. Required by 'create'.")
    task_parser.add_argument("-p", "--printlist", type=str, help=PRINTLIST_HELP)
    task_parser.add_argument("-a", "--address", type=str, help=ADDRESS_HELP)
    task_parser.add_argument("-j", "--json", help="Output the tasks in JSON format.",
                             action="store_true")
    task_parser.add_argument("-t", "--table", help="Output the tasks as a plain table.",
                             action="store_true")
    task_parser.set_defaults(mode="task")

    execute_parser = subparsers.add_parser(
        "execute", aliases=["ex"],
        help="Start, pause or resume a print (not implemented yet).",
        description="Starts, pauses or resumes a print job. Not implemented yet.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    execute_parser.add_argument("operation",
                                help="Initiate printing using the NAME from the PRINTLIST or add a new one from FILE to PRINTLIST.\
                           Otherwise pause or resume the current task. Example: 'pxctl ex start -f model.plgx",
                                nargs="?",
                                choices=("start", "pause", "resume"))
    execute_parser.add_argument("-n", "--name", type=str, help="Use the task's name exclusively for start purposes.")
    execute_parser.add_argument("-f", "--file", type=str,
                                help="Transfer the task from FILE to PRINTLIST. Exclusively for start purposes.")
    execute_parser.add_argument("-p", "--printlist", type=str, help=PRINTLIST_HELP)
    execute_parser.add_argument("-a", "--address", type=str, help=ADDRESS_HELP)
    execute_parser.set_defaults(mode="execute")
    args = parser.parse_args()

    if "mode" not in args:
        parser.print_help()
        sys.exit(-1)

    if args.mode == "show":
        show(args)

    elif args.mode == "discover":
        discover(args)

    elif args.mode == "beep":
        if args.operation is None:
            beep_parser.print_help()
            sys.exit(-1)
        else:
            beep(args)

    elif args.mode == "printlist":
        if args.operation is None:
            printlist_parser.print_help()
            sys.exit(-1)
        else:
            printlist(args)

    elif args.mode == "task":
        if args.operation is None:
            task_parser.print_help()
            sys.exit(-1)
        else:
            task(args)

    elif args.mode == "execute":
        if args.operation is None:
            execute_parser.print_help()
            sys.exit(-1)
        else:
            execute(args)

    sys.exit(0)


if __name__ == '__main__':
    main()
