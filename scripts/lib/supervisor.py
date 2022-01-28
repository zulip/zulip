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


def list_supervisor_processes(
    filter_names: Optional[List[str]] = None, *, only_running: Optional[bool] = None
) -> List[str]:
    results = []
    processes = rpc().supervisor.getAllProcessInfo()
    assert isinstance(processes, list)
    for process in processes:
        if process["group"] != process["name"]:
            name = f"{process['group']}:{process['name']}"
        else:
            name = process["name"]

        if filter_names:
            match = False
            for filter_name in filter_names:
                if filter_name.endswith(":*") and name.startswith(filter_name[:-1]):
                    match = True
                    break
                if name == filter_name:
                    match = True
                    break
            if not match:
                continue

        if only_running is None:
            results.append(name)
        elif only_running == (process["statename"] == "RUNNING"):
            results.append(name)
    return results
