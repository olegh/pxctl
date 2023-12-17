#!/usr/bin/env python

import argparse
import os
import sys
from time import sleep

from pxctl.notifications import Notifications
from pxctl.printer_service import Connection, PrinterService
from layout import JsonLayout, TableLayout

cur_dir = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.realpath(cur_dir)

if os.path.isdir(SRC_DIR):
    sys.path.insert(0, SRC_DIR)


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


def show(layout_service, args):
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


def discover(layout_service, args):
    printers = PrinterService.discover_printers()
    layout_service.print_discover(printers)


def beep_on(args):
    address = get_address(args)
    with Connection(address) as connection:
        printer_service = PrinterService(connection)
        printer_service.beep_on()


def beep_off(args):
    address = get_address(args)
    with Connection(address) as connection:
        printer_service = PrinterService(connection)
        printer_service.beep_off()


def main():
    parser = argparse.ArgumentParser(prog="pxctl")
    parser.add_argument("mode",
                        help="show printing info or discover printers",
                        nargs='?',
                        choices=("show", "discover", "beep_on", "beep_off"))
    parser.add_argument("-j", "--json", help="print info at json format", action="store_true")
    parser.add_argument("-a", "--address", type=str, help="specify printer IPv4 address")
    parser.add_argument("-c", "--continuous", help="keep printing with period example", action="store_true")
    parser.add_argument("-s", "--on-success", type=str, help="run hook when done printing")
    args = parser.parse_args()

    if args.json:
        layout_service = JsonLayout()
    else:
        layout_service = TableLayout()

    if args.mode == "show":
        show(layout_service, args)
        sys.exit(0)

    if args.mode == "discover":
        discover(layout_service, args)
        sys.exit(0)

    if args.mode == "beep_on":
        beep_on(args)
        sys.exit(0)

    if args.mode == "beep_off":
        beep_off(args)
        sys.exit(0)

    print("examples: ")
    print('''
    pxctl show --continuous
    pxctl show --address=192.168.1.35
    pxctl discover --json
    pxctl beep_on --address=192.168.1.35
    pxctl beep_off
    pxctl show --on-success='echo 10'
    pxctl show --json"
''')

    parser.print_help()


if __name__ == '__main__':
    main()
