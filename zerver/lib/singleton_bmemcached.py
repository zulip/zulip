import pickle
import socket
from functools import lru_cache
from typing import Any

from bmemcached.protocol import Protocol
from django_bmemcached.memcached import BMemcached

from zerver.lib import zstd_level9


def _enable_tcp_keepalive(sock: socket.socket) -> None:
    # Turn on TCP keepalives, with aggressive timers, on a freshly
    # opened connection to memcached.
    #
    # bmemcached keeps a long-lived connection per thread and exposes no
    # hook to configure the underlying socket, so without this a
    # connection silently reaped while idle -- e.g. by a Kubernetes CNI
    # or a stateful firewall dropping the idle conntrack entry -- is only
    # noticed on its next use.  That surfaces as a spurious "Cannot query
    # memcached" failure (the lost write makes the round-trip read return
    # nothing), most visibly on the every-10s /health check.
    #
    # Keepalives both keep the idle connection fresh (so it is less
    # likely to be reaped) and detect a genuinely dead peer promptly
    # rather than on next use.
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        # Start probing after 60s idle, then every 10s, dropping the
        # connection after 3 failed probes.
        #
        # KEEPIDLE is the constant that matters: a probe every 60s keeps
        # the flow from looking idle, so it is not reaped in the first
        # place.  It must sit comfortably below the shortest idle timeout
        # on the path (conntrack / firewall); 60s clears the common
        # aggressive reapers (~1-5min) with margin.  KEEPINTVL * KEEPCNT
        # (~30s) only governs how fast a genuinely dead peer is noticed,
        # and is kept loose enough not to misfire on a transient blip.
        #
        # These constants are only available on Linux; guard so dev
        # environments on other platforms still work.
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        if hasattr(socket, "TCP_KEEPINTVL"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        if hasattr(socket, "TCP_KEEPCNT"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    except OSError:  # nocoverage
        # Best-effort: never let socket tuning break cache connectivity.
        pass


_original_open_connection = Protocol._open_connection


def _open_connection_with_keepalive(self: Protocol) -> None:
    # Only apply keepalives when we actually open a new TCP connection;
    # _open_connection() is called before every command and short-circuits
    # when a connection already exists.  self.host is falsey for
    # Unix-domain sockets, where the TCP options do not apply.
    was_connected = self.connection is not None
    _original_open_connection(self)
    if not was_connected and self.connection is not None and self.host:
        _enable_tcp_keepalive(self.connection)


Protocol._open_connection = _open_connection_with_keepalive


@lru_cache(None)
def _get_bmemcached(location: str, param_bytes: bytes) -> BMemcached:
    params = pickle.loads(param_bytes)  # noqa: S301
    params["OPTIONS"]["compression"] = zstd_level9
    return BMemcached(location, params)


def SingletonBMemcached(location: str, params: dict[str, Any]) -> BMemcached:
    # Django instantiates the cache backend per-task to guard against
    # thread safety issues, but BMemcached is already thread-safe and
    # does its own per-thread pooling, so make sure we instantiate only
    # one to avoid extra connections.

    return _get_bmemcached(location, pickle.dumps(params))
