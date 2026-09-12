"""Minimal TFTP write client, used to upload a model to the printer.

The printer accepts task data over TFTP (RFC 1350) on the standard port. Only
writing is implemented, because the firmware refuses read requests -- it answers
a RRQ with "Unable to open requested file" whatever name is asked for.

A TFTP server replies from a freshly chosen port and the rest of the transfer
runs against that port, so the first reply decides where the remaining blocks
go.
"""

import socket
import struct
from typing import Callable, Optional

_OPCODE_WRQ = 2
_OPCODE_DATA = 3
_OPCODE_ACK = 4
_OPCODE_ERROR = 5
_OPCODE_OACK = 6

# The slicer negotiates this block size; the firmware accepts it and it keeps
# a multi-megabyte upload down to a manageable number of round trips.
_BLOCK_SIZE = 65464
_MIN_BLOCK_SIZE = 512
_DEFAULT_PORT = 69
_DEFAULT_TIMEOUT = 5.0
_MAX_RETRIES = 5


class TftpError(RuntimeError):
    """Raised when the server rejects a transfer or stops responding."""


def _encode_request(filename: str, size: int, block_size: int, mode: str = "octet") -> bytes:
    """Builds a write request, negotiating options the way the slicer does.

    The official client asks for a large block size, a 5 second timeout and
    announces the transfer size (RFC 2347/2348/2349). Without a bigger block a
    multi-megabyte model would need tens of thousands of round trips.
    """
    parts = [
        # Names are CP1251 on this firmware, matching how it reports them back.
        filename.encode("cp1251"),
        mode.encode("ascii"),
        b"blksize", str(block_size).encode("ascii"),
        b"timeout", b"5",
        b"tsize", str(size).encode("ascii"),
    ]
    return struct.pack("!H", _OPCODE_WRQ) + b"\x00".join(parts) + b"\x00"


def _parse_error(packet: bytes) -> str:
    message = packet[4:].split(b"\x00")[0]
    return message.decode("cp1251", errors="replace")


def upload(
    address: str,
    filename: str,
    payload: bytes,
    port: int = _DEFAULT_PORT,
    timeout: float = _DEFAULT_TIMEOUT,
    progress: Optional[Callable[[int, int], None]] = None,
    block_size: int = _BLOCK_SIZE,
) -> None:
    """Writes `payload` to `filename` on the printer.

    `progress` is called with the number of bytes sent and the total, so a
    caller can draw a progress indicator.

    Raises TftpError if the server rejects the transfer or goes silent.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        peer, block_size = _handshake(
            sock, address, port, filename, len(payload), block_size
        )
        _send_blocks(sock, peer, payload, block_size, progress)
    finally:
        sock.close()


def _handshake(
    sock: socket.socket,
    address: str,
    port: int,
    filename: str,
    size: int,
    block_size: int,
) -> tuple:
    """Sends the write request and settles on a peer port and block size.

    Returns the address the server answered from -- TFTP moves the transfer to
    a fresh port -- along with the block size it agreed to.
    """
    request = _encode_request(filename, size, block_size)
    for _ in range(_MAX_RETRIES):
        sock.sendto(request, (address, port))
        try:
            reply, peer = sock.recvfrom(4096)
        except socket.timeout:
            continue

        opcode = struct.unpack("!H", reply[:2])[0]
        if opcode == _OPCODE_ERROR:
            raise TftpError(f"printer rejected the upload: {_parse_error(reply)}")
        # An OACK accepts the request along with the options; a plain ACK for
        # block 0 accepts the request but declines them.
        if opcode == _OPCODE_OACK:
            return peer, _negotiated_block_size(reply, block_size)
        if opcode == _OPCODE_ACK:
            # Options declined: fall back to the size every server supports.
            return peer, _MIN_BLOCK_SIZE
        raise TftpError(f"unexpected TFTP opcode {opcode} in response to the write request")

    raise TftpError(f"no response from {address}:{port} -- is the printer reachable?")


def _negotiated_block_size(reply: bytes, requested: int) -> int:
    """Reads the block size out of an option acknowledgement."""
    fields = reply[2:].split(b"\x00")
    for name, value in zip(fields[::2], fields[1::2]):
        if name.lower() == b"blksize":
            try:
                return max(int(value), _MIN_BLOCK_SIZE)
            except ValueError:
                break
    return requested


def _send_blocks(
    sock: socket.socket,
    peer: tuple,
    payload: bytes,
    block_size: int,
    progress: Optional[Callable[[int, int], None]],
) -> None:
    total = len(payload)
    blocks = [payload[i:i + block_size] for i in range(0, total, block_size)]
    # A transfer ends with a short block, so a payload that divides evenly
    # needs an empty one to terminate it.
    if not blocks or len(blocks[-1]) == block_size:
        blocks.append(b"")

    sent = 0
    for index, chunk in enumerate(blocks, start=1):
        # Block numbers are 16-bit and wrap around on large files.
        block_number = index & 0xFFFF
        packet = struct.pack("!HH", _OPCODE_DATA, block_number) + chunk

        for _ in range(_MAX_RETRIES):
            sock.sendto(packet, peer)
            try:
                reply, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue

            opcode = struct.unpack("!H", reply[:2])[0]
            if opcode == _OPCODE_ERROR:
                raise TftpError(f"printer aborted the upload: {_parse_error(reply)}")
            if opcode != _OPCODE_ACK:
                continue
            if struct.unpack("!H", reply[2:4])[0] == block_number:
                break
            # An ACK for an earlier block is a duplicate; keep waiting.
        else:
            raise TftpError(f"no acknowledgement for block {block_number}")

        sent += len(chunk)
        if progress:
            progress(min(sent, total), total)
