from django.conf import settings

from zerver.models import Realm

def get_tornado_port(realm: Realm) -> int:
    if settings.TORNADO_PROCESSES == 1:
        return int(settings.TORNADO_SERVER.split(":")[-1])
    return 9993

def get_tornado_uri(realm: Realm) -> str:
    if settings.TORNADO_PROCESSES == 1:
        return settings.TORNADO_SERVER

    port = get_tornado_port(realm)
    return "http://127.0.0.1:%d" % (port,)
