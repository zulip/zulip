import urllib
from typing import List

from zerver.models import Realm, Stream

def hash_util_encode(string: str) -> str:
    # Do the same encoding operation as hash_util.encodeHashComponent on the
    # frontend.
    # `safe` has a default value of "/", but we want those encoded, too.
    return urllib.parse.quote(
        string.encode("utf-8"), safe=b"").replace(".", "%2E").replace("%", ".")

def encode_stream(stream_id: int, stream_name: str) -> str:
    # We encode streams for urls as something like 99-Verona.
    stream_name = stream_name.replace(' ', '-')
    return str(stream_id) + '-' + hash_util_encode(stream_name)

def pm_narrow_url(realm: Realm, participants: List[str]) -> str:
    participants.sort()
    base_url = "%s/#narrow/pm-with/" % (realm.uri,)
    return base_url + hash_util_encode(",".join(participants))

def stream_narrow_url(realm: Realm, stream: Stream) -> str:
    base_url = "%s/#narrow/stream/" % (realm.uri,)
    return base_url + encode_stream(stream.id, stream.name)

def topic_narrow_url(realm: Realm, stream: Stream, topic: str) -> str:
    base_url = "%s/#narrow/stream/" % (realm.uri,)
    return "%s%s/topic/%s" % (base_url,
                              encode_stream(stream.id, stream.name),
                              hash_util_encode(topic))
