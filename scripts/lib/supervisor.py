import socket
from http.client import HTTPConnection
from typing import Dict, List, Optional, Tuple, Union
from xmlrpc import client


class UnixStreamHTTPConnection(HTTPConnection):
    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.host)


class UnixStreamTransport(client.Transport, object):
    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        super(UnixStreamTransport, self).__init__()

    def make_connection(
        self, host: Union[Tuple[str, Dict[str, str]], str]
    ) -> UnixStreamHTTPConnection:
        return UnixStreamHTTPConnection(self.socket_path)


def rpc() -> client.ServerProxy:
    return client.ServerProxy(
        "http://localhost", transport=UnixStreamTransport("/var/run/supervisor.sock")
    )
