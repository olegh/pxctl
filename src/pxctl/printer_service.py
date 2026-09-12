import select
import socket
import struct
import sys
from dataclasses import dataclass
from typing import List, Tuple

from .utils import NetworkUtils, MagicPicasoConverters
from .enums import NetPrinterState, NetPrinterStatus, PrinterType
from .connection import Connection
from .structs import PrinterState, Printer, Extruder


class PrinterService:
    def __init__(self, connection: Connection):
        self.__connection = connection

    def get_printing_info(self) -> PrinterState | None:
        info_cmd = b"\x01\x00\x01\x00\x00\x00\x08\x00"
        # 8x    header
        # B     state code
        # 3x I  status code (npsPrintDone etc.) after 3 bytes of padding
        # ?     ready-to-print flag
        # 255s  current task file name
        # h 1x  progress marker
        # f     progress percent
        recv_format = "8xB3xI?255sh1xf15xff4xff28x"

        self.__connection.send(info_cmd)

        data = self.__connection.recv()
        if not data:
            return None
        (
            code,
            status_code,
            is_ready_to_print,
            current_task_file_bytes,
            printing_marker,
            progress,
            left_extruder_temperature,
            right_extruder_temperature,
            table_temperature,
            _,
        ) = struct.unpack(recv_format, data)
        task_name = current_task_file_bytes.decode("cp1251", errors="replace").strip("\x00")

        return PrinterState(
            state=NetPrinterState(code),
            status=NetPrinterStatus(status_code),
            left_extruder_temperature=left_extruder_temperature,
            right_extruder_temperature=right_extruder_temperature,
            table_temperature=table_temperature,
            current_task_file=task_name,
            is_printing=printing_marker != 0,
            is_ready=is_ready_to_print,
            progress_percents=progress,
        )

    @staticmethod
    def discover_printers(attempts: int = 3) -> List[Printer]:
        """Broadcasts the discovery probe and describes every printer that answers.

        Discovery rides on UDP broadcast, which WiFi does not acknowledge at the
        link layer, so a probe is lost every so often. Rather than reporting "no
        printers" on a single unlucky round, the sweep is repeated until
        something answers.
        """
        broadcast_addresses = NetworkUtils.get_all_ipv4_broadcast_addresses()
        printers_adresses = set()

        for _ in range(max(attempts, 1)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            try:
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
            finally:
                sock.close()

            if printers_adresses:
                break

        discover_result = []

        for address in printers_adresses:
            with Connection(address) as connection:
                buf = None
                for _ in range(3):
                    connection.send(b"\x01\x00\x0c\x00\x00\x00\x08\x00")
                    buf = connection.recv()
                    if buf:
                        break
                if not buf:
                    print(f"Can't receive info from {address}", file=sys.stderr)
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

                mac_address = PrinterService._parse_mac(buf)
                extruders = PrinterService._parse_extruders(buf)
                discover_result.append(
                    Printer(
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
                            "cp1251", errors="replace"
                        ).strip("\x00"),
                        right_extruder_profile=right_extruder_profile.decode(
                            "cp1251", errors="replace"
                        ).strip("\x00\x1e"),
                        mac_address=mac_address,
                        extruders=extruders,
                    )
                )

        return discover_result

    # Offsets of the two extruder descriptors inside the printer-info response.
    # Each descriptor is: extruder type (CP1251, NUL-padded), then a byte
    # holding the nozzle diameter in hundredths of a millimetre (50 -> 0.5 mm),
    # then the loaded material profile.
    _EXTRUDER_OFFSETS = ((0x59, 0x63, 0x64), (0x8C, 0x96, 0x97))
    _MAC_OFFSET = 0x53

    @staticmethod
    def _parse_mac(buf: bytes) -> str:
        raw = buf[PrinterService._MAC_OFFSET:PrinterService._MAC_OFFSET + 6]
        if len(raw) < 6:
            return ""
        return ":".join(f"{octet:02x}" for octet in raw)

    @staticmethod
    def _parse_extruders(buf: bytes) -> List[Extruder]:
        extruders = []
        for kind_offset, nozzle_offset, material_offset in PrinterService._EXTRUDER_OFFSETS:
            if nozzle_offset >= len(buf):
                continue
            kind = PrinterService._read_string(buf, kind_offset)
            material = PrinterService._read_string(buf, material_offset)
            if not material:
                continue
            extruders.append(
                Extruder(
                    kind=kind,
                    nozzle_diameter_mm=buf[nozzle_offset] / 100.0,
                    material=material,
                )
            )
        return extruders

    @staticmethod
    def _read_string(buf: bytes, offset: int, limit: int = 40) -> str:
        """Reads a NUL-terminated CP1251 string, as the firmware encodes them."""
        raw = buf[offset:offset + limit].split(b"\x00")[0]
        return raw.decode("cp1251", errors="replace").strip()

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
