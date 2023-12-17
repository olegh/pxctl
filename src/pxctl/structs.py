from dataclasses import dataclass

from .enums import NetPrinterState, PrinterType


@dataclass
class PrinterState:
    state: NetPrinterState
    left_extruder_temperature: float
    right_extruder_temperature: float
    table_temperature: float
    current_task_file: str
    is_printing: bool
    is_ready: bool
    progress_percents: float


@dataclass
class Printer:
    protocol_version: int
    sub_version: int
    low_hw_version: int
    hi_hw_version: int
    printer_type: PrinterType
    serial: str
    ip_address: str
    left_extruder_profile: str
    right_extruder_profile: str