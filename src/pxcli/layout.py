import json
import os
from typing import List

from tabulate import tabulate

from pxctl.printer_service import PrinterState, Printer


class TableLayout:
    def print_info(self, address: str, info: PrinterState | None = None):
        headers = [
            "Address",
            "State",
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
                    info.current_task_file,
                    round(info.progress_percents, 1),
                    round(info.left_extruder_temperature, 1),
                    round(info.right_extruder_temperature, 1),
                    round(info.table_temperature, 1),
                    info.is_ready,
                ]
            ]
        else:
            table = [[address, "NOT_CONNECTED", "", "", "", "", "", ""]]

        os.system('cls' if os.name == 'nt' else 'clear')
        print(tabulate(table, headers=headers, tablefmt="github"))

    def print_discover(self, printers: List[Printer]):
        headers = ["Printer type", "Address", "Serial", "Left profile", "Right profile"]

        table = []

        for printer in printers:
            table.append(
                [
                    printer.printer_type.name,
                    printer.ip_address,
                    printer.serial,
                    printer.left_extruder_profile,
                    printer.right_extruder_profile,
                ]
            )

        print(tabulate(table, headers=headers, tablefmt="github"))


class JsonLayout:
    def print_info(self, address: str, info: PrinterState | None = None):

        if info:
            dto = {
                "address": address,
                "state": info.state.name,
                "task_name": info.current_task_file,
                "progress_percent": round(info.progress_percents, 1),
                "left_extruder_temperature": round(info.left_extruder_temperature, 1),
                "right_extruder_temperature": round(info.right_extruder_temperature, 1),
                "table_temperature": round(info.right_extruder_temperature, 1),
                "is_ready": info.is_ready,
            }
        else:
            dto = {
                "address": address,
                "state": "NOT_CONNECTED",
            }

        print(json.dumps(dto))

    def print_discover(self, printers: List[Printer]):
        dto = []

        for printer in printers:
            dto.append(
                {
                    "serial": printer.serial,
                    "model": printer.printer_type.name,
                    "ip_address": printer.ip_address,
                    "left_extruder_profile": printer.left_extruder_profile,
                    "right_extruder_profile": printer.right_extruder_profile,
                }
            )

        print(json.dumps(dto))
