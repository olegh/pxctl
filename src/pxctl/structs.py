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
class Task:
    """One model uploaded to the printer, as listed in a print list."""

    name: str
    """Task name. The firmware truncates it to 32 bytes, so long names arrive
    clipped -- the official slicer shows them clipped too."""

    guid: str
    """Identifier the firmware assigns to the task."""

    size_bytes: int
    """Size of the stored task data."""


@dataclass
class PrintList:
    """A named collection of tasks held on the printer."""

    name: str
    guid: str
    tasks: List[Task] = field(default_factory=list)


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
