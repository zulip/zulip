from django.conf import settings

from zerver.models import Realm

def get_tornado_port(realm: Realm) -> int:
    if settings.TORNADO_SERVER is None:
        return 9993
    if settings.TORNADO_PROCESSES == 1:
        return int(settings.TORNADO_SERVER.split(":")[-1])
    return 9993

def get_tornado_uri(realm: Realm) -> str:
    if settings.TORNADO_PROCESSES == 1:
        return settings.TORNADO_SERVER

    port = get_tornado_port(realm)
    return "http://127.0.0.1:%d" % (port,)

def notify_tornado_queue_name(port: int) -> str:
    if settings.TORNADO_PROCESSES == 1:
        return "notify_tornado"
    return "notify_tornado_port_%d" % (port,)

def tornado_return_queue_name(port: int) -> str:
    if settings.TORNADO_PROCESSES == 1:
        return "tornado_return"
    return "tornado_return_port_%d" % (port,)
