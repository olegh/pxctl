import select
import socket
import struct
import sys
from dataclasses import dataclass


class Connection:
    def __init__(self, address: str, port: int):
        self.__address = address
        self.__port = port
        self.__socket = None

    def __enter__(self):
        if self.__socket is not None:
            raise FileExistsError("socket already exists")

        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.setblocking(False)
        self.__socket.bind(("0.0.0.0", 0))

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.__socket is not None:
            self.__socket.close()
            self.__socket = None

    def send(self, buf: bytes) -> int:
        return self.__socket.sendto(buf, (self.__address, self.__port))

    def recv(self) -> (bool, bytes):
        read_ready, _, _ = select.select([self.__socket], [], [], 0.3)
        if len(read_ready) == 1:
            buf, _ = self.__socket.recvfrom(1024)
            return len(buf) > 0, buf

        return False, None


def connect(address: str, port: int = 54321) -> Connection:
    return Connection(address, port)


@dataclass
class PrintingInfo:
    state: str
    left_extruder_temperature: float
    right_extruder_temperature: float
    table_temperature: float
    current_task_file: str
    is_printing: bool
    is_armed: bool
    progress_percents: float


@dataclass
class DiscoverInfo:
    serial: str
    ip_address: str
    left_extruder_profile: str
    right_extruder_profile: str


class PrinterService:
    def __init__(self, connection: Connection):
        self.__connection = connection

    @staticmethod
    def from_code_and_task_name(code: int, task_name: str) -> str:
        no_task = "no name"
        if code == 3:
            if task_name == no_task:
                return "IDLE"
            else:
                return "SUCCESS"

        if code in (7, 6, 5, 1):
            return "PRINTING"

        if code == 2:
            return "WAITING"

        return "UNKNOWN"

    def get_printing_info(self) -> (bool, PrintingInfo):
        info_cmd = b'\x01\x00\x01\x00\x00\x00\x08\x00'
        recv_format = "8xB7x?255sh7xB12xff4xff28x"

        self.__connection.send(info_cmd)

        has_data, data = self.__connection.recv()
        if not has_data:
            return False, None

        (code,
         is_ready_to_print,
         current_task_file_bytes,
         printing_marker,
         progress,
         left_extruder_temperature,
         right_extruder_temperature,
         table_temperature,
         _) = struct.unpack(recv_format, data)
        task_name = current_task_file_bytes.decode("utf-8").strip('\x00')

        return (True, PrintingInfo(state=self.from_code_and_task_name(code, task_name),
                                   left_extruder_temperature=left_extruder_temperature,
                                   right_extruder_temperature=right_extruder_temperature,
                                   table_temperature=table_temperature,
                                   current_task_file=task_name,
                                   is_printing=printing_marker != 0,
                                   is_armed=is_ready_to_print,
                                   progress_percents=progress / 2.0))

    @staticmethod
    def discover_printers() -> [DiscoverInfo]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", 0))

        sock.sendto(b'\x50\x49\x43\x41\x53\x4f\x33\x44', ("255.255.255.255", 54321))
        addresses = []

        while True:
            read_ready, _, _ = select.select([sock], [], [], 0.3)
            if read_ready:
                _, (address, _) = sock.recvfrom(1024)
                addresses.append(address)
            else:
                break
        discover_result = []

        for address in addresses:
            with connect(address) as connection:
                connection.send(b'\x01\x00\x0c\x00\x00\x00\x08\x00')
                success, buf = connection.recv()
                if not success:
                    print(f"Can't receive info from ${address}", file=sys.stderr)
                    continue

                (serial, left_extruder_profile, right_extruder_profile) = \
                    struct.unpack("13x20x20s47x40s10x40sx", buf)

                discover_result.append(DiscoverInfo(
                    serial=serial.decode("utf-8").strip('\x00'),
                    ip_address=address,
                    left_extruder_profile=left_extruder_profile.decode("utf-8").strip('\x00'),
                    right_extruder_profile=right_extruder_profile.decode("utf-8").strip('\x00')
                ))

        return discover_result

    def beep_on(self):
        self.__connection.send(b'\x01\x00\x0e\x00\x00\x00\x08\x00')
        ok, _ = self.__connection.recv()
        if not ok:
            print("Printer didn't respond", file=sys.stderr)

    def beep_off(self):
        self.__connection.send(b'\x01\x00\x0f\x00\x00\x00\x08\x00')
        ok, _ = self.__connection.recv()
        if not ok:
            print("Printer didn't respond", file=sys.stderr)
