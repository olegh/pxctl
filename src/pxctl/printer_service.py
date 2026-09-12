import select
import socket
import time
import struct
import sys
from dataclasses import dataclass
from typing import List, Tuple

from .utils import NetworkUtils, MagicPicasoConverters
from .enums import NetPrinterState, NetPrinterStatus, PrinterType
from .connection import Connection
from . import tftp
from .plgx import TaskFile, read_task_file
from .structs import PrinterState, Printer, Extruder, Task, PrintList


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
                        # Wait out each probe separately: replies are unicast
                        # and can be dropped on a busy WiFi link, so draining
                        # only after the last send loses the earlier answers.
                        deadline = time.monotonic() + 0.3
                        while True:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                break
                            read_ready, _, _ = select.select([sock], [], [], remaining)
                            if not read_ready:
                                break
                            _, (address, _) = sock.recvfrom(1024)
                            printers_adresses.add(address)
            finally:
                sock.close()

            if printers_adresses:
                break

        discover_result = []

        for address in printers_adresses:
            printer = PrinterService.describe_printer(address)
            if printer:
                discover_result.append(printer)

        return discover_result

    @staticmethod
    def describe_printer(address: str) -> Printer | None:
        """Queries one printer directly for its descriptor.

        Unicast only, so it works even where discovery broadcasts are dropped.
        """
        with Connection(address) as connection:
            buf = None
            for _ in range(3):
                connection.send(b"\x01\x00\x0c\x00\x00\x00\x08\x00")
                buf = connection.recv()
                if buf:
                    break
            if not buf:
                print(f"Can't receive info from {address}", file=sys.stderr)
                return None
            (
                protocol_version,
                sub_version,
                low_hw_version,
                hi_hw_version,
                serial,
                left_extruder_profile,
                right_extruder_profile,
            ) = struct.unpack("1c1c6x1c1c3x20x20s47x40s10x40sx", buf)

            return Printer(
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
                mac_address=PrinterService._parse_mac(buf),
                extruders=PrinterService._parse_extruders(buf),
            )

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

    # Layout shared by the list responses: an 8-byte header, 4 bytes of
    # padding, then a record count and the fixed-size records themselves.
    # Reading the stored lists is slower than a status query.
    _LIST_TIMEOUT = 2.0

    _LIST_COUNT_OFFSET = 0x0C
    _LIST_DATA_OFFSET = 0x0E

    # Task record: name, GUID, a constant version word, then the stored size.
    _TASK_RECORD_SIZE = 60
    _TASK_NAME_SIZE = 32
    # Print list record: just a name and a GUID.
    _PRINTLIST_RECORD_SIZE = 48
    _PRINTLIST_NAME_SIZE = 32

    def get_tasks(self) -> List[Task]:
        """Lists the models uploaded to the printer."""
        self.__connection.send(b"\x01\x00\x11\x00\x00\x00\x08\x00")
        data = self.__connection.recv(self._LIST_TIMEOUT)
        if not data:
            return []

        tasks = []
        for record in PrinterService._iter_records(data, PrinterService._TASK_RECORD_SIZE):
            name = PrinterService._read_string(record, 0, PrinterService._TASK_NAME_SIZE)
            if not name:
                continue
            tasks.append(
                Task(
                    name=name,
                    guid=record[32:48].hex(),
                    size_bytes=struct.unpack("<I", record[52:56])[0],
                )
            )
        return tasks

    def get_printlists(self) -> List[PrintList]:
        """Lists the print lists defined on the printer, with their tasks.

        The firmware reports a single flat task list, so the tasks are attached
        to the print list that holds them -- which is the only one the Designer
        X Pro exposes.
        """
        self.__connection.send(b"\x01\x00\x02\x00\x00\x00\x08\x00")
        data = self.__connection.recv(self._LIST_TIMEOUT)
        if not data:
            return []
        # Read the records out before issuing the task query, which reuses the
        # same socket and would otherwise clobber this response.
        records = list(
            PrinterService._iter_records(data, PrinterService._PRINTLIST_RECORD_SIZE)
        )

        tasks = self.get_tasks()
        printlists = []
        for record in records:
            name = PrinterService._read_string(record, 0, PrinterService._PRINTLIST_NAME_SIZE)
            if not name:
                continue
            printlists.append(
                PrintList(name=name, guid=record[32:48].hex(), tasks=tasks)
            )
            # Only the first list owns the reported tasks.
            tasks = []
        return printlists

    @staticmethod
    def _iter_records(data: bytes, record_size: int):
        """Yields the fixed-size records carried by a list response."""
        header_end = PrinterService._LIST_DATA_OFFSET
        if len(data) < header_end:
            return
        count = struct.unpack(
            "<H", data[PrinterService._LIST_COUNT_OFFSET:header_end]
        )[0]
        payload = data[header_end:]
        for index in range(count):
            record = payload[index * record_size:(index + 1) * record_size]
            if len(record) < record_size:
                return
            yield record

    # Registration request (0x18) laid out as the slicer sends it:
    #   0x08  GUID of the task to insert after
    #   0x18  GUID of the new task, matching the ;TID: in the file
    #   0x28  task name, 32 bytes
    #   0x48  format version word, always 02 00
    #   0x4a  size of the uploaded data
    #   0x52  GUID of the print list to add it to
    _REGISTER_REQUEST_SIZE = 98
    _REGISTER_NAME_SIZE = 32
    _TASK_FORMAT_VERSION = 2

    def register_task(
        self,
        task_id: str,
        name: str,
        size_bytes: int,
        printlist_guid: str,
        after_task_guid: str = "",
    ) -> bool:
        """Adds an uploaded task to a print list.

        An upload alone does not make a task appear: the file is stored under
        its GUID, and this call is what puts it in the list under a readable
        name. Returns whether the printer accepted it.
        """
        anchor = bytes.fromhex(after_task_guid) if after_task_guid else b"\x00" * 16

        request = bytearray(PrinterService._REGISTER_REQUEST_SIZE)
        struct.pack_into(
            "<HHHH", request, 0, 1, 0x18, 0, PrinterService._REGISTER_REQUEST_SIZE
        )
        request[0x08:0x18] = anchor.ljust(16, b"\x00")[:16]
        request[0x18:0x28] = PrinterService._guid_to_bytes(task_id)
        request[0x28:0x48] = name.encode("cp1251", errors="replace")[
            : PrinterService._REGISTER_NAME_SIZE
        ].ljust(PrinterService._REGISTER_NAME_SIZE, b"\x00")
        struct.pack_into("<H", request, 0x48, PrinterService._TASK_FORMAT_VERSION)
        struct.pack_into("<I", request, 0x4A, size_bytes)
        request[0x52:0x62] = bytes.fromhex(printlist_guid).ljust(16, b"\x00")[:16]

        self.__connection.send(bytes(request))
        reply = self.__connection.recv(PrinterService._LIST_TIMEOUT)
        if not reply or len(reply) < 12:
            return False
        # The reply carries a status word: 1 on success.
        return struct.unpack("<I", reply[8:12])[0] == 1

    @staticmethod
    def _guid_to_bytes(task_id: str) -> bytes:
        """Packs a GUID the way the firmware stores it, dashed or not."""
        return bytes.fromhex(task_id.replace("-", "")).ljust(16, b"\x00")[:16]

    @staticmethod
    def upload_task(
        address: str,
        path: str,
        task_id: str | None = None,
        name: str | None = None,
        progress=None,
    ) -> TaskFile:
        """Uploads a .plgx model and adds it to the printer's print list.

        Two steps: the file goes up over TFTP named after its task GUID, then a
        registration request puts it in the print list under a readable name.
        Uploading alone stores the data but leaves nothing visible on the
        printer.

        Returns the task file that was sent, so a caller can report its id.
        """
        task_file = read_task_file(path, task_id)
        tftp.upload(
            address,
            task_file.upload_name,
            task_file.payload,
            progress=progress,
        )

        with Connection(address) as connection:
            service = PrinterService(connection)
            printlists = service.get_printlists()
            if not printlists:
                raise RuntimeError(
                    "uploaded, but the printer reported no print list to add the task to"
                )
            printlist = printlists[0]
            # New tasks go after the last one, matching where the slicer puts them.
            anchor = printlist.tasks[-1].guid if printlist.tasks else ""
            accepted = service.register_task(
                task_id=task_file.task_id,
                name=name or task_file.default_name,
                size_bytes=len(task_file.payload),
                printlist_guid=printlist.guid,
                after_task_guid=anchor,
            )

        if not accepted:
            raise RuntimeError("the printer refused to add the task to its print list")

        return task_file

    # Delete is a bare GUID: an 8-byte header followed by the task identifier.
    _DELETE_REQUEST_SIZE = 24

    def delete_task(self, task_guid: str) -> bool:
        """Removes a task from the printer. Returns whether it was accepted."""
        request = bytearray(PrinterService._DELETE_REQUEST_SIZE)
        struct.pack_into(
            "<HHHH", request, 0, 1, 0x05, 0, PrinterService._DELETE_REQUEST_SIZE
        )
        request[0x08:0x18] = PrinterService._guid_to_bytes(task_guid)

        self.__connection.send(bytes(request))
        reply = self.__connection.recv(PrinterService._LIST_TIMEOUT)
        if not reply or len(reply) < 12:
            return False
        return struct.unpack("<I", reply[8:12])[0] == 1

    def find_task(self, name: str) -> Task | None:
        """Looks up a stored task by the name shown in the print list."""
        for task in self.get_tasks():
            if task.name == name:
                return task
        return None

    # Start, like delete, is an 8-byte header followed by the task GUID.
    _START_REQUEST_SIZE = 24

    def start_task(self, task_guid: str) -> bool:
        """Starts printing a task already stored on the printer.

        Returns whether the printer accepted the request. It will refuse when
        it is not ready -- already printing, or waiting on the user.
        """
        request = bytearray(PrinterService._START_REQUEST_SIZE)
        struct.pack_into(
            "<HHHH", request, 0, 1, 0x07, 0, PrinterService._START_REQUEST_SIZE
        )
        request[0x08:0x18] = PrinterService._guid_to_bytes(task_guid)

        self.__connection.send(bytes(request))
        reply = self.__connection.recv(PrinterService._LIST_TIMEOUT)
        if not reply or len(reply) < 12:
            return False
        return struct.unpack("<I", reply[8:12])[0] == 1

    def pause_print(self) -> bool:
        """Pauses the running print.

        The printer takes a moment to reach a safe spot in the layer before it
        actually stops, so the state does not change the instant this returns.
        """
        return self.__simple_command(0x09)

    def resume_print(self) -> bool:
        """Resumes a paused print."""
        return self.__simple_command(0x0B)

    def __simple_command(self, command_id: int) -> bool:
        """Sends a request that carries no body and reads its status word."""
        self.__connection.send(struct.pack("<HHHH", 1, command_id, 0, 8))
        reply = self.__connection.recv(PrinterService._LIST_TIMEOUT)
        if not reply or len(reply) < 12:
            return False
        return struct.unpack("<I", reply[8:12])[0] == 1

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
