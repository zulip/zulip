import socket
import time
from http.client import HTTPConnection
from xmlrpc import client

from typing_extensions import override


class UnixStreamHTTPConnection(HTTPConnection):
    @override
    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connected = False
        for i in range(2):
            try:
                self.sock.connect(self.host)
                connected = True
                break
            except FileNotFoundError:
                # Backoff and retry
                time.sleep(2**i)
        if not connected:
            raise Exception(
                "Failed to connect to supervisor -- check that it is running, by running 'service supervisor status'"
            )


class UnixStreamTransport(client.Transport):
    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        super().__init__()

    @override
    def make_connection(self, host: tuple[str, dict[str, str]] | str) -> UnixStreamHTTPConnection:
        return UnixStreamHTTPConnection(self.socket_path)


def rpc() -> client.ServerProxy:
    return client.ServerProxy(
        "http://localhost", transport=UnixStreamTransport("/var/run/supervisor.sock")
    )


def list_supervisor_processes(
    filter_names: list[str] | None = None, *, only_running: bool | None = None
) -> list[str]:
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
                # zulip-tornado:* matches zulip-tornado:9800 and zulip-tornado
                if filter_name.endswith(":*") and (
                    name.startswith(filter_name.removesuffix("*"))
                    or name == filter_name.removesuffix(":*")
                ):
                    match = True
                    break
                if name == filter_name:
                    match = True
                    break
            if not match:
                continue

        if only_running is None:
            results.append(name)
        elif only_running == (process["statename"] in ("RUNNING", "STARTING")):
            results.append(name)

    return results
