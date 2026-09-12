import json
from typing import List

from tabulate import tabulate

from pxctl.printer_service import PrinterState, Printer

from .card import StatusCard, clear_screen


class CardLayout:
    """Default layout: the status card drawn with terminal graphics."""

    def __init__(self):
        self.__card = StatusCard()

    def print_info(
        self,
        address: str,
        info: PrinterState | None = None,
        printer: Printer | None = None,
        clear: bool = False,
    ):
        if clear:
            clear_screen()
        print(self.__card.render(address, info, printer), flush=True)

    def print_discover(
        self,
        printers: List[Printer],
        states: dict | None = None,
        clear: bool = False,
    ):
        if clear:
            clear_screen()
        if not printers:
            print(self.__card.render("no printers found", None))
            return
        states = states or {}
        for printer in printers:
            print(
                self.__card.render(
                    printer.ip_address, states.get(printer.ip_address), printer
                ),
                flush=True,
            )


class TableLayout:
    def print_info(
        self,
        address: str,
        info: PrinterState | None = None,
        printer: Printer | None = None,
        clear: bool = False,
    ):
        headers = [
            "Address",
            "State",
            "Status",
            "Task name",
            "Progress %",
            "Left ℃",
            "Right ℃",
            "Table ℃",
            "Ready",
        ]
        if info:
            table = [
                [
                    address,
                    info.state.name,
                    info.status.description,
                    info.current_task_file,
                    round(info.progress_percents, 1),
                    round(info.left_extruder_temperature, 1),
                    round(info.right_extruder_temperature, 1),
                    round(info.table_temperature, 1),
                    info.is_ready,
                ]
            ]
        else:
            table = [[address, "NOT_CONNECTED", "", "", "", "", "", "", ""]]

        if clear:
            clear_screen()
        print(tabulate(table, headers=headers, tablefmt="github"), flush=True)

    def print_discover(
        self,
        printers: List[Printer],
        states: dict | None = None,
        clear: bool = False,
    ):
        headers = ["Printer type", "Address", "Serial", "Nozzles", "Left profile", "Right profile"]

        table = []

        for printer in printers:
            table.append(
                [
                    printer.printer_type.name,
                    printer.ip_address,
                    printer.serial,
                    " / ".join(
                        f"{extruder.nozzle_diameter_mm:.1f}" for extruder in printer.extruders
                    ),
                    printer.left_extruder_profile,
                    printer.right_extruder_profile,
                ]
            )

        print(tabulate(table, headers=headers, tablefmt="github"))


class JsonLayout:
    def print_info(
        self,
        address: str,
        info: PrinterState | None = None,
        printer: Printer | None = None,
        clear: bool = False,
    ):

        if info:
            dto = {
                "address": address,
                "state": info.state.name,
                "status": info.status.name,
                "status_description": info.status.description,
                "task_name": info.current_task_file,
                "progress_percent": round(info.progress_percents, 1),
                "left_extruder_temperature": round(info.left_extruder_temperature, 1),
                "right_extruder_temperature": round(info.right_extruder_temperature, 1),
                "table_temperature": round(info.table_temperature, 1),
                "is_ready": info.is_ready,
            }
            if printer:
                dto["serial"] = printer.serial
                dto["extruders"] = [
                    {
                        "nozzle_diameter_mm": extruder.nozzle_diameter_mm,
                        "material": extruder.material,
                        "kind": extruder.kind,
                    }
                    for extruder in printer.extruders
                ]
        else:
            dto = {
                "address": address,
                "state": "NOT_CONNECTED",
            }

        print(json.dumps(dto), flush=True)

    def print_discover(
        self,
        printers: List[Printer],
        states: dict | None = None,
        clear: bool = False,
    ):
        dto = []

        for printer in printers:
            dto.append(
                {
                    "serial": printer.serial,
                    "model": printer.printer_type.name,
                    "ip_address": printer.ip_address,
                    "mac_address": printer.mac_address,
                    "left_extruder_profile": printer.left_extruder_profile,
                    "right_extruder_profile": printer.right_extruder_profile,
                    "extruders": [
                        {
                            "nozzle_diameter_mm": extruder.nozzle_diameter_mm,
                            "material": extruder.material,
                            "kind": extruder.kind,
                        }
                        for extruder in printer.extruders
                    ],
                }
            )

        print(json.dumps(dto), flush=True)
