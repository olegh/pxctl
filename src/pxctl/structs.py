from dataclasses import dataclass, field
from typing import List

from .enums import NetPrinterState, NetPrinterStatus, PrinterType


@dataclass
class Extruder:
    """One print head, as reported in the printer-info response."""

    kind: str
    """Extruder hardware type, e.g. "Блок400"."""

    nozzle_diameter_mm: float
    """Nozzle size in millimetres, e.g. 0.5."""

    material: str
    """Loaded material profile, e.g. "PETG (BF)(1)"."""


@dataclass
class PrinterState:
    state: NetPrinterState
    status: NetPrinterStatus
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
    mac_address: str = ""
    extruders: List[Extruder] = field(default_factory=list)
