import json
import os
import re

from django.conf import settings

from zerver.models import Realm

shard_map = {}
shard_regexes = []
if os.path.exists("/etc/zulip/sharding.json"):
    with open("/etc/zulip/sharding.json") as f:
        data = json.loads(f.read())
        shard_map = data.get(
            "shard_map",
            data,  # backwards compatibility
        )
        shard_regexes = [
            (re.compile(regex, re.I), port) for regex, port in data.get("shard_regexes", [])
        ]


def get_tornado_port(realm: Realm) -> int:
    if realm.host in shard_map:
        return shard_map[realm.host]

    for regex, port in shard_regexes:
        if regex.match(realm.host):
            return port

    return settings.TORNADO_PORTS[0]


def get_tornado_uri(realm: Realm) -> str:
    port = get_tornado_port(realm)
    return f"http://127.0.0.1:{port}"


def notify_tornado_queue_name(port: int) -> str:
    if settings.TORNADO_PROCESSES == 1:
        return "notify_tornado"
    return f"notify_tornado_port_{port}"
