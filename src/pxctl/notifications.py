import subprocess
import sys

from .printer_service import PrinterState


class Notifications:
    def __init__(self, on_success_hook: str):
        self.__notified_latch = False
        self.__on_success_hook = on_success_hook

    def update_state(self, info: PrinterState | None = None):
        if self.__notified_latch:
            return

        if info:
            if info.state == "SUCCESS":
                self.run_success()
                self.__notified_latch = True

    def run_success(self):
        if self.__on_success_hook is not None:
            try:
                subprocess.run(self.__on_success_hook, shell=True)
            except Exception as e:
                print(e, file=sys.stderr)

