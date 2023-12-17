import select
import socket
import struct
import sys
from dataclasses import dataclass
from typing import List, Tuple

from .utils import NetworkUtils, MagicPicasoConverters
from .enums import NetPrinterState, PrinterType


class Connection:
    def __init__(self, address: str, port: int = 54321):
        self.__address = address
        self.__port = port
        self.__socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def __enter__(self):
        self.__socket.setblocking(False)
        self.__socket.bind(("0.0.0.0", 0))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.__socket is not None:
            self.__socket.close()

    def send(self, buf: bytes) -> int:
        return self.__socket.sendto(buf, (self.__address, self.__port))

    def recv(self) -> bytes | None:
        read_ready, _, _ = select.select([self.__socket], [], [], 0.3)
        if len(read_ready) != 1:
            return None
        buf, _ = self.__socket.recvfrom(1024)
        if len(buf) <= 0:
            return None
        return buf


@dataclass
class PrintingInfo:
    state: NetPrinterState
    left_extruder_temperature: float
    right_extruder_temperature: float
    table_temperature: float
    current_task_file: str
    is_printing: bool
    is_ready: bool
    progress_percents: float


@dataclass
class DiscoverInfo:
    protocol_version: int
    sub_version: int
    low_hw_version: int
    hi_hw_version: int
    printer_type: PrinterType
    serial: str
    ip_address: str
    left_extruder_profile: str
    right_extruder_profile: str


class PrinterService:
    def __init__(self, connection: Connection):
        self.__connection = connection

    def get_printing_info(self) -> PrintingInfo | None:
        info_cmd = b"\x01\x00\x01\x00\x00\x00\x08\x00"
        recv_format = "8xB7x?255sh7xB12xff4xff28x"

        self.__connection.send(info_cmd)

        data = self.__connection.recv()
        if not data:
            return None

        (
            code,
            is_ready_to_print,
            current_task_file_bytes,
            printing_marker,
            progress,
            left_extruder_temperature,
            right_extruder_temperature,
            table_temperature,
            _,
        ) = struct.unpack(recv_format, data)
        task_name = current_task_file_bytes.decode("utf-8").strip("\x00")

        return PrintingInfo(
            state=NetPrinterState(code),
            left_extruder_temperature=left_extruder_temperature,
            right_extruder_temperature=right_extruder_temperature,
            table_temperature=table_temperature,
            current_task_file=task_name,
            is_printing=printing_marker != 0,
            is_ready=is_ready_to_print,
            progress_percents=progress / 2.0,
        )

    @staticmethod
    def discover_printers() -> List[DiscoverInfo]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        broadcast_addresses = NetworkUtils.get_all_ipv4_broadcast_addresses()
        printers_adresses = set()
        for b_addr in broadcast_addresses:
            for _ in range(3):
                sock.sendto("PICASO3D".encode("ascii"), (b_addr, 49149))
                while True:
                    read_ready, _, _ = select.select([sock], [], [], 0.3)
                    if read_ready:
                        _, (address, _) = sock.recvfrom(1024)
                        printers_adresses.add(address)
                    else:
                        break
        discover_result = []

        for address in printers_adresses:
            with Connection(address) as connection:
                connection.send(b"\x01\x00\x0c\x00\x00\x00\x08\x00")
                buf = connection.recv()
                if not buf:
                    print(f"Can't receive info from ${address}", file=sys.stderr)
                    continue
                (
                    protocol_version,
                    sub_version,
                    low_hw_version,
                    hi_hw_version,
                    serial,
                    left_extruder_profile,
                    right_extruder_profile,
                ) = struct.unpack("1c1c6x1c1c3x20x20s47x40s10x40sx", buf)
                discover_result.append(
                    DiscoverInfo(
                        protocol_version=int.from_bytes(protocol_version),
                        sub_version=int.from_bytes(sub_version),
                        low_hw_version=int.from_bytes(low_hw_version),
                        hi_hw_version=int.from_bytes(hi_hw_version),
                        printer_type=PrinterType(
                            MagicPicasoConverters.convert_hi_hw_ver_to_printer_model(
                                int.from_bytes(hi_hw_version)
                            )
                        ),
                        serial=serial.decode("utf-8").strip("\x00"),
                        ip_address=address,
                        left_extruder_profile=left_extruder_profile.decode(
                            "utf-8"
                        ).strip("\x00"),
                        right_extruder_profile=right_extruder_profile.decode(
                            "utf-8"
                        ).strip("\x00"),
                    )
                )

        return discover_result

    def beep_on(self):
        self.__connection.send(b"\x01\x00\x0e\x00\x00\x00\x08\x00")
        resp = self.__connection.recv()
        if not resp:
            print("Printer didn't respond", file=sys.stderr)

    def beep_off(self):
        self.__connection.send(b"\x01\x00\x0f\x00\x00\x00\x08\x00")
        resp = self.__connection.recv()
        if not resp:
            print("Printer didn't respond", file=sys.stderr)
