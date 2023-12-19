#!/usr/bin/env python

import argparse
import os
import sys
import signal
from time import sleep

from pxctl.notifications import Notifications
from pxctl.printer_service import Connection, PrinterService
from .layout import JsonLayout, TableLayout

cur_dir = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.realpath(cur_dir)

if os.path.isdir(SRC_DIR):
    sys.path.insert(0, SRC_DIR)



def signal_handler(sig, frame):
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def get_address(args) -> str:
    if args.address:
        address = args.address
    else:
        printers = PrinterService.discover_printers()
        if len(printers) == 0:
            print("Printers not found, try set ip address manually", file=sys.stderr)
            sys.exit(-1)
        else:
            address = printers[0].ip_address

    return address


def get_layout(args):
    if args.json:
        return JsonLayout()
    else:
        return TableLayout()


def show(args):
    layout_service = get_layout(args)
    address = get_address(args)
    should_repeat = args.continuous

    notifications = Notifications(args.on_success)

    with Connection(address) as connection:
        print_service = PrinterService(connection)

        while True:
            optional_info = print_service.get_printing_info()
            layout_service.print_info(address, optional_info)
            notifications.update_state(optional_info)

            if not should_repeat:
                break

            sleep(0.6)


def discover(args):
    layout_service = get_layout(args)
    printers = PrinterService.discover_printers()
    layout_service.print_discover(printers)


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


def printlist(args):
    print("Not implemented yet", file=sys.stderr)


def task(args):
    print("Not implemented yet", file=sys.stderr)


def execute(args):
    print("Not implemented yet", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(prog="pxctl")
    subparsers = parser.add_subparsers()

    ADDRESS_HELP = "Please provide the IPv4 address of the printer. By default, the printer is discovered automatically on the local network."
    PRINTLIST_HELP = "Please provide the name of the print list. If there is only one print list, it will be used by default."

    show_parser = subparsers.add_parser("show",
                                        help="Print the details of the 3D printer state to the standard output. '%(prog)s show -h' for more details")
    show_parser.add_argument("-j", "--json", help="Output the information of printer state in JSON format.",
                             action="store_true")
    show_parser.add_argument("-a", "--address", type=str, help=ADDRESS_HELP)
    show_parser.add_argument("-c", "--continuous",
                             help="Continuously output the current state of the 3D printer to the standard output.",
                             action="store_true")
    show_parser.add_argument("-s", "--on-success", type=str,
                             help="Once the printing is complete, execute the bash script hook. example: %(prog)s --on-success='touch /tmp/done' ",
                             metavar="BASH_SCRIPT")
    show_parser.set_defaults(mode="show")

    beep_parser = subparsers.add_parser("beep",
                                        help="Triggers the 3D printer to emit a series of beeps for identification purposes. '%(prog)s beep -h' for more details")
    beep_parser.add_argument("operation",
                             help="Enable or disable the printer's beeping function for identification. Example: '%(prog)s enable'",
                             nargs="?",
                             choices=("enable", "disable"))
    beep_parser.add_argument("-a", "--address", type=str, help=ADDRESS_HELP)
    beep_parser.set_defaults(mode="beep")

    discover_parser = subparsers.add_parser("discover",
                                            help="Search for printers connected to the local network. '%(prog)s discover -h' for more details")
    discover_parser.add_argument("-j", "--json", help="Output the results of the printer discovery in JSON format.",
                                 action="store_true")
    discover_parser.set_defaults(mode="discover")

    printlist_parser = subparsers.add_parser("printlist", aliases=["pl"],
                                             help="create/delete/list print-lists, '%(prog)s printlist -h' for more details")
    printlist_parser.add_argument("operation",
                                  help="You can either create with a specific NAME, delete by specifying the NAME, or list the existing print lists. Example: pxctl pl create my-print-list",
                                  nargs="?",
                                  choices=("create", "delete", "list")
                                  )
    printlist_parser.add_argument("-n", "--name", help="Please provide a name for the print-list")
    printlist_parser.add_argument("-a", "--address", type=str, help=ADDRESS_HELP)
    printlist_parser.set_defaults(mode="printlist")

    task_parser = subparsers.add_parser("task", help="create/delete/list tasks. '%(prog)s task -h' for more details")
    task_parser.add_argument("operation",
                             help="Create task from FILE, remove task by NAME, or display all current tasks. Example: pxctl task create -f model.plgx",
                             nargs="?",
                             choices=("create", "delete", "list")
                             )
    task_parser.add_argument("-n", "--name", type=str, help="Use the task's name exclusively for deletion purposes.")
    task_parser.add_argument("-f", "--file", type=str,
                             help="The file path to the .plgx file, which will be uploaded to the 3D printer, should only be used for creating.")
    task_parser.add_argument("-p", "--printlist", type=str, help=PRINTLIST_HELP)
    task_parser.add_argument("-a", "--address", type=str, help=ADDRESS_HELP)
    task_parser.set_defaults(mode="task")

    execute_parser = subparsers.add_parser("execute", aliases=['ex'],
                                           help="Execute the start, pause, or resume operation with task '%(prog)s ex -h' for more details")
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
