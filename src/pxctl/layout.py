import json
import os

from tabulate import tabulate

from printer import PrintingInfo, DiscoverInfo


class TableLayout:

    def print_info(self, address: str, info_optional: tuple[bool, PrintingInfo]):
        headers = ["Address",
                   "State",
                   "Task name",
                   "Progress %",
                   "Left ℃",
                   "Right ℃",
                   "Table ℃",
                   "Armed"]
        connection_ok, info = info_optional

        if connection_ok:
            table = [[address,
                      info.state,
                      info.current_task_file,
                      round(info.progress_percents, 1),
                      round(info.left_extruder_temperature, 1),
                      round(info.right_extruder_temperature, 1),
                      round(info.table_temperature, 1),
                      info.is_armed]
                     ]
        else:
            table = [[address,
                      "NOT_CONNECTED",
                      '',
                      '',
                      '',
                      '',
                      '',
                      '']
                     ]

        os.system('clear')
        print(tabulate(table, headers=headers, tablefmt="github"))

    def print_discover(self, printers: [DiscoverInfo]):
        headers = ["Address",
                   "Serial",
                   "Left profile",
                   "Right profile"]

        table = []

        for printer in printers:
            table.append([
                printer.ip_address,
                printer.serial,
                printer.left_extruder_profile,
                printer.right_extruder_profile
            ])

        print(tabulate(table, headers=headers, tablefmt="github"))


class JsonLayout:
    def print_info(self, address: str, info_optional: tuple[bool, PrintingInfo]):
        connection_ok, info = info_optional

        if connection_ok:
            dto = {"address": address,
                   "state": info.state,
                   "task_name": info.current_task_file,
                   "progress_percent": round(info.progress_percents, 1),
                   "left_extruder_temperature": round(info.left_extruder_temperature, 1),
                   "right_extruder_temperature": round(info.right_extruder_temperature, 1),
                   "table_temperature": round(info.right_extruder_temperature, 1),
                   "is_armed": info.is_armed
                   }
        else:
            dto = {
                "address": address,
                "state": "NOT_CONNECTED",
            }

        print(json.dumps(dto))

    def print_discover(self, printers: [DiscoverInfo]):
        dto = []

        for printer in printers:
            dto.append(
                {
                    "serial": printer.serial,
                    "ip_address": printer.ip_address,
                    "left_extruder_profile": printer.left_extruder_profile,
                    "right_extruder_profile": printer.right_extruder_profile
                }
            )

        print(json.dumps(dto))
