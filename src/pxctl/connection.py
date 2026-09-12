import select
import socket


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

    DEFAULT_TIMEOUT = 0.3

    def recv(self, timeout: float = DEFAULT_TIMEOUT) -> bytes | None:
        read_ready, _, _ = select.select([self.__socket], [], [], timeout)
        if len(read_ready) != 1:
            return None
        buf, _ = self.__socket.recvfrom(1024)
        if len(buf) <= 0:
            return None
        return buf
