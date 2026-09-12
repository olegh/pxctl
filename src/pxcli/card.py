"""Terminal rendering of the printer status card.

Mirrors the monitoring card of the official PolygonX slicer: serial and
address, a headline state, a progress bar, both extruders with their nozzle
size and loaded material, and the platform temperature.
"""

import os
import sys
from typing import List, Optional

from pxctl.enums import NetPrinterStatus
from pxctl.structs import Extruder, PrintList, Printer, PrinterState, Task

# Box drawing, with an ASCII fallback for terminals that cannot do UTF-8.
_BORDERS_UNICODE = {
    "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│",
    "bar_full": "█", "bar_empty": "░", "sep": "·",
}
_BORDERS_ASCII = {
    "tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|",
    "bar_full": "#", "bar_empty": ".", "sep": "-",
}

# The card is framed in the colour the status maps to, the way the official
# app tints its card border.
_GREEN = "\033[32m"
_BLUE = "\033[34m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_GREY = "\033[90m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"

_STATUS_COLORS = {
    NetPrinterStatus.npsPrintDone: _GREEN,
    NetPrinterStatus.npsWaitNewTask: _GREEN,
    NetPrinterStatus.npsMainPrint: _BLUE,
    NetPrinterStatus.npsUpdateDownload: _BLUE,
    NetPrinterStatus.npsPrintPaused: _YELLOW,
    NetPrinterStatus.npsWaitUser: _YELLOW,
    NetPrinterStatus.npsAdjectiveWarning: _YELLOW,
    NetPrinterStatus.npsService: _YELLOW,
    NetPrinterStatus.npsPrintProblem: _RED,
    NetPrinterStatus.npsCriticalError: _RED,
    NetPrinterStatus.npsConnectionError: _RED,
}

_CARD_WIDTH = 46


def _supports_unicode() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or ""
    return "utf" in encoding.lower()


def _supports_color(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(stream, "isatty") and stream.isatty()


class StatusCard:
    """Renders a printer status card using terminal graphics."""

    def __init__(self, use_color: Optional[bool] = None, use_unicode: Optional[bool] = None):
        self._color = _supports_color(sys.stdout) if use_color is None else use_color
        unicode_ok = _supports_unicode() if use_unicode is None else use_unicode
        self._chars = _BORDERS_UNICODE if unicode_ok else _BORDERS_ASCII

    # -- colour helpers -------------------------------------------------

    def _paint(self, text: str, *styles: str) -> str:
        if not self._color:
            return text
        return f"{''.join(styles)}{text}{_RESET}"

    @staticmethod
    def _visible_width(text: str) -> int:
        """Length of `text` ignoring ANSI escapes, for padding maths."""
        width, in_escape = 0, False
        for char in text:
            if in_escape:
                in_escape = char != "m"
            elif char == "\033":
                in_escape = True
            else:
                width += 1
        return width

    # -- card pieces ----------------------------------------------------

    def _row(self, content: str = "") -> str:
        vertical = self._chars["v"]
        padding = _CARD_WIDTH - self._visible_width(content)
        return f"{vertical} {content}{' ' * max(padding, 0)} {vertical}"

    def _progress_bar(self, percent: float, width: int = 34) -> str:
        percent = max(0.0, min(100.0, percent))
        filled = int(round(width * percent / 100.0))
        bar = self._chars["bar_full"] * filled + self._chars["bar_empty"] * (width - filled)
        return f"{bar} {percent:5.1f}%"

    def _extruder_rows(self, extruders: List[Extruder], left_temp: float, right_temp: float) -> List[str]:
        """Two columns, one per head: temperature above material."""
        temps = (left_temp, right_temp)
        columns = []
        for index in range(2):
            extruder = extruders[index] if index < len(extruders) else None
            label = self._paint(f"{index + 1}", _DIM)
            temp = f"{label} {temps[index]:5.1f} °C"
            if extruder:
                material = f"{extruder.nozzle_diameter_mm:.1f}  {extruder.material}"
            else:
                material = self._paint("not reported", _DIM)
            columns.append((temp, material))

        width = _CARD_WIDTH // 2
        rows = []
        for pair in zip(*columns):
            first = pair[0] + " " * max(width - self._visible_width(pair[0]), 0)
            rows.append(f"{first}{pair[1]}")
        return rows

    # -- public API -----------------------------------------------------

    def render(
        self,
        address: str,
        state: Optional[PrinterState],
        printer: Optional[Printer] = None,
    ) -> str:
        chars = self._chars
        top = chars["tl"] + chars["h"] * (_CARD_WIDTH + 2) + chars["tr"]
        bottom = chars["bl"] + chars["h"] * (_CARD_WIDTH + 2) + chars["br"]

        if state is None:
            lines = [
                self._row(self._paint("NOT CONNECTED", _BOLD, _RED)),
                self._row(self._paint(address, _GREY)),
            ]
            return "\n".join(
                [self._paint(top, _RED)]
                + lines
                + [self._paint(bottom, _RED)]
            )

        color = _STATUS_COLORS.get(state.status, _GREY)
        title = printer.serial if printer and printer.serial else address
        subtitle = address if printer and printer.serial else ""

        lines = [self._row(self._paint(title, _BOLD, color))]
        if subtitle:
            lines.append(self._row(self._paint(subtitle, _GREY)))
        lines.append(self._row())
        lines.append(self._row(self._paint(state.status.description, color)))

        # A task name is only meaningful once something has been queued.
        if state.current_task_file:
            lines.append(self._row(self._paint(state.current_task_file, _DIM)))

        lines.append(self._row(self._progress_bar(state.progress_percents)))
        lines.append(self._row())

        extruders = printer.extruders if printer else []
        lines.extend(
            self._row(row)
            for row in self._extruder_rows(
                extruders,
                state.left_extruder_temperature,
                state.right_extruder_temperature,
            )
        )

        lines.append(self._row())
        lines.append(self._row(f"Platform: {state.table_temperature:5.1f} °C"))

        return "\n".join(
            [self._paint(top, color)] + lines + [self._paint(bottom, color)]
        )

    def render_tasks(
        self,
        printlists: List[PrintList],
        current_task: str = "",
    ) -> str:
        """Draws the print lists and the tasks stored on the printer."""
        chars = self._chars
        top = chars["tl"] + chars["h"] * (_CARD_WIDTH + 2) + chars["tr"]
        bottom = chars["bl"] + chars["h"] * (_CARD_WIDTH + 2) + chars["br"]

        if not printlists:
            return "\n".join(
                [self._paint(top, _GREY),
                 self._row(self._paint("no print lists reported", _DIM)),
                 self._paint(bottom, _GREY)]
            )

        lines = []
        for index, printlist in enumerate(printlists):
            if index:
                lines.append(self._row())
            header = f"{printlist.name}  ({len(printlist.tasks)})"
            lines.append(self._row(self._paint(header, _BOLD)))
            lines.extend(self._task_rows(printlist.tasks, current_task))

        return "\n".join([self._paint(top, _BLUE)] + lines + [self._paint(bottom, _BLUE)])

    def _task_rows(self, tasks: List[Task], current_task: str) -> List[str]:
        if not tasks:
            return [self._row(self._paint("empty", _DIM))]

        # The name the printer reports as current carries a .plgx suffix the
        # task list does not use, so compare without it.
        current = current_task.rsplit(".", 1)[0] if current_task else ""

        rows = []
        for task in tasks:
            size = format_size(task.size_bytes)
            room = _CARD_WIDTH - len(size) - 4
            name = task.name if len(task.name) <= room else task.name[: room - 1] + "…"
            marker = "▸" if self._chars is _BORDERS_UNICODE else ">"
            if task.name == current:
                prefix = self._paint(marker, _GREEN)
                name = self._paint(name, _GREEN)
            else:
                prefix = " "
            padding = _CARD_WIDTH - self._visible_width(name) - len(size) - 2
            rows.append(f"{prefix} {name}{' ' * max(padding, 0)}{size}")
        return [self._row(row) for row in rows]


def format_size(size_bytes: int) -> str:
    """Human-readable size, the way a file manager would show it."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes / 1024 / 1024:.1f} MB"


def clear_screen():
    """Clears the terminal for continuous mode, without spawning a shell."""
    if sys.stdout.isatty():
        # Move home and clear down, so the card redraws without flicker.
        sys.stdout.write("\033[H\033[J")
    else:
        # Piped or redirected: keep every frame, separated by a blank line.
        sys.stdout.write("\n")
