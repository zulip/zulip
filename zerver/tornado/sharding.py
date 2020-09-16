import json
import os

from django.conf import settings

from zerver.models import Realm

shard_map = {}
if os.path.exists("/etc/zulip/sharding.json"):
    with open("/etc/zulip/sharding.json") as f:
        shard_map = json.loads(f.read())

def get_tornado_port(realm: Realm) -> int:
    return shard_map.get(realm.host, settings.TORNADO_PORTS[0])

def get_tornado_uri(realm: Realm) -> str:
    port = get_tornado_port(realm)
    return f"http://127.0.0.1:{port}"

def notify_tornado_queue_name(port: int) -> str:
    if settings.TORNADO_PROCESSES == 1:
        return "notify_tornado"
    return f"notify_tornado_port_{port}"
