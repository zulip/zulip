import json
import os
import re
from re import Pattern

from django.conf import settings

from zerver.models import Realm, UserProfile

shard_map: dict[str, int | list[int]] = {}
shard_regexes: list[tuple[Pattern[str], int | list[int]]] = []
if os.path.exists("/etc/zulip/sharding.json"):
    with open("/etc/zulip/sharding.json") as f:
        data = json.loads(f.read())
        shard_map = data.get(
            "shard_map",
            data,  # backwards compatibility
        )
        shard_regexes = [
            (re.compile(regex, re.IGNORECASE), port)
            for regex, port in data.get("shard_regexes", [])
        ]


def get_realm_tornado_ports(realm: Realm) -> list[int]:
    if realm.host in shard_map:
        ports = shard_map[realm.host]
        return [ports] if isinstance(ports, int) else ports

    for regex, ports in shard_regexes:
        if regex.match(realm.host):
            return [ports] if isinstance(ports, int) else ports

    return [settings.TORNADO_PORTS[0]]


def get_user_id_tornado_port(realm_ports: list[int], user_id: int) -> int:
    return realm_ports[user_id % len(realm_ports)]


def get_user_tornado_port(user: UserProfile) -> int:
    return get_user_id_tornado_port(get_realm_tornado_ports(user.realm), user.id)


def get_tornado_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def notify_tornado_queue_name(port: int) -> str:
    if settings.TORNADO_PROCESSES == 1:
        return "notify_tornado"
    return f"notify_tornado_port_{port}"
