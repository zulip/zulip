import json
import os
from urllib.parse import urlsplit

from django.conf import settings

from zerver.models import Realm

shard_map = {}
if os.path.exists("/etc/zulip/sharding.json"):
    with open("/etc/zulip/sharding.json") as f:
        shard_map = json.loads(f.read())

def get_tornado_port(realm: Realm) -> int:
    if settings.TORNADO_SERVER is None:
        return 9993
    if settings.TORNADO_PROCESSES == 1:
        r = urlsplit(settings.TORNADO_SERVER)
        assert r.port is not None
        return r.port
    return shard_map.get(realm.host, 9800)

def get_tornado_uri(realm: Realm) -> str:
    if settings.TORNADO_PROCESSES == 1:
        return settings.TORNADO_SERVER

    port = get_tornado_port(realm)
    return f"http://127.0.0.1:{port}"

def notify_tornado_queue_name(port: int) -> str:
    if settings.TORNADO_PROCESSES == 1:
        return "notify_tornado"
    return f"notify_tornado_port_{port}"
