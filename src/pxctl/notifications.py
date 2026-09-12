import subprocess
import sys

from .enums import NetPrinterStatus
from .printer_service import PrinterState


class Notifications:
    def __init__(self, on_success_hook: str):
        self.__notified_latch = False
        self.__on_success_hook = on_success_hook

    def update_state(self, info: PrinterState | None = None):
        if self.__notified_latch:
            return

        if info:
            # The hook fires once the printer reports a finished print. This
            # used to compare the state enum against the string "SUCCESS",
            # which never matched, so the hook never ran.
            if info.status == NetPrinterStatus.npsPrintDone:
                self.run_success()
                self.__notified_latch = True

    def run_success(self):
        if self.__on_success_hook is not None:
            try:
                subprocess.run(self.__on_success_hook, shell=True)
            except Exception as e:
                print(e, file=sys.stderr)

