import subprocess
import sys

from printer import PrintingInfo


class Notifications:
    def __init__(self, on_success_hook: str, on_failure_hook: str):
        self.__notified_latch = False
        self.__on_success_hook = on_success_hook
        self.__on_failure_hook = on_failure_hook

    def update_state(self, info_optional: tuple[bool, PrintingInfo]):
        if self.__notified_latch:
            return

        connection_ok, info = info_optional

        if connection_ok:
            if info.state == "SUCCESS":
                self.run_success()
                self.__notified_latch = True
            if info.state == "FAILED":
                self.run_failed()
                self.__notified_latch = True

    def run_success(self):
        if self.__on_success_hook is not None:
            try:
                subprocess.run(self.__on_success_hook, shell=True)
            except Exception as e:
                print(e, file=sys.stderr)

    def run_failed(self):
        if self.__on_failure_hook is not None:
            try:
                subprocess.run(self.__on_failure_hook, shell=True)
            except Exception as e:
                print(e, file=sys.stderr)
