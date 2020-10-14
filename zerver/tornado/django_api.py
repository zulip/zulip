from functools import lru_cache
from typing import Any, Container, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import urlparse

import orjson
import requests
from django.conf import settings
from requests.adapters import ConnectionError, HTTPAdapter
from requests.models import PreparedRequest, Response
from requests.packages.urllib3.util.retry import Retry

from zerver.lib.queue import queue_json_publish
from zerver.models import Client, Realm, UserProfile
from zerver.tornado.event_queue import process_notification
from zerver.tornado.sharding import get_tornado_port, get_tornado_uri, notify_tornado_queue_name


class TornadoAdapter(HTTPAdapter):
    def __init__(self) -> None:
        # All of the POST requests we make to Tornado are safe to
        # retry; allow retries of them, which is not the default.
        retry_methods = Retry.DEFAULT_METHOD_WHITELIST | set(['POST'])
        retry = Retry(total=3, backoff_factor=1, method_whitelist=retry_methods)
        super().__init__(max_retries=retry)

    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: Union[None, float, Tuple[float, float], Tuple[float, None]] = 0.5,
        verify: Union[bool, str] = True,
        cert: Union[None, bytes, str, Container[Union[bytes, str]]] = None,
        proxies: Optional[Mapping[str, str]] = None,
    ) -> Response:
        if not proxies:
            proxies = {}
        merged_proxies = {**proxies, "no_proxy": "localhost,127.0.0.1"}
        try:
            resp = super().send(request, stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=merged_proxies)
        except ConnectionError:
            parsed_url = urlparse(request.url)
            logfile = f"tornado-{parsed_url.port}.log" if settings.TORNADO_PROCESSES > 1 else "tornado.log"
            raise ConnectionError(
                f"Django cannot connect to Tornado server ({request.url}); "
                f"check {settings.ERROR_FILE_LOG_PATH} and {logfile}"
            )
        resp.raise_for_status()
        return resp

@lru_cache(None)
def requests_client() -> requests.Session:
    c = requests.Session()
    adapter = TornadoAdapter()
    for scheme in ("https://", "http://"):
        c.mount(scheme, adapter)
    return c

def request_event_queue(user_profile: UserProfile, user_client: Client, apply_markdown: bool,
                        client_gravatar: bool, slim_presence: bool, queue_lifespan_secs: int,
                        event_types: Optional[Iterable[str]]=None,
                        all_public_streams: bool=False,
                        narrow: Iterable[Sequence[str]]=[],
                        bulk_message_deletion: bool=False) -> Optional[str]:

    if not settings.USING_TORNADO:
        return None

    tornado_uri = get_tornado_uri(user_profile.realm)
    req = {'dont_block': 'true',
           'apply_markdown': orjson.dumps(apply_markdown),
           'client_gravatar': orjson.dumps(client_gravatar),
           'slim_presence': orjson.dumps(slim_presence),
           'all_public_streams': orjson.dumps(all_public_streams),
           'client': 'internal',
           'user_profile_id': user_profile.id,
           'user_client': user_client.name,
           'narrow': orjson.dumps(narrow),
           'secret': settings.SHARED_SECRET,
           'lifespan_secs': queue_lifespan_secs,
           'bulk_message_deletion': orjson.dumps(bulk_message_deletion)}

    if event_types is not None:
        req['event_types'] = orjson.dumps(event_types)

    resp = requests_client().post(
        tornado_uri + '/api/v1/events/internal',
        data=req
    )
    return resp.json()['queue_id']

def get_user_events(user_profile: UserProfile, queue_id: str, last_event_id: int) -> List[Dict[str, Any]]:
    if not settings.USING_TORNADO:
        return []

    tornado_uri = get_tornado_uri(user_profile.realm)
    post_data: Dict[str, Any] = {
        'queue_id': queue_id,
        'last_event_id': last_event_id,
        'dont_block': 'true',
        'user_profile_id': user_profile.id,
        'secret': settings.SHARED_SECRET,
        'client': 'internal',
    }
    resp = requests_client().post(
        tornado_uri + '/api/v1/events/internal',
        data=post_data
    )
    return resp.json()['events']

def send_notification_http(realm: Realm, data: Mapping[str, Any]) -> None:
    if not settings.USING_TORNADO or settings.RUNNING_INSIDE_TORNADO:
        process_notification(data)
    else:
        tornado_uri = get_tornado_uri(realm)
        requests_client().post(
            tornado_uri + "/notify_tornado",
            data=dict(data=orjson.dumps(data), secret=settings.SHARED_SECRET),
        )

# The core function for sending an event from Django to Tornado (which
# will then push it to web and mobile clients for the target users).
# By convention, send_event should only be called from
# zerver/lib/actions.py, which helps make it easy to find event
# generation code.
#
# Every call point should be covered by a test in `test_events.py`,
# with the schema verified in `zerver/lib/event_schema.py`.
#
# See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html
def send_event(realm: Realm, event: Mapping[str, Any],
               users: Union[Iterable[int], Iterable[Mapping[str, Any]]]) -> None:
    """`users` is a list of user IDs, or in the case of `message` type
    events, a list of dicts describing the users and metadata about
    the user/message pair."""
    port = get_tornado_port(realm)
    queue_json_publish(notify_tornado_queue_name(port),
                       dict(event=event, users=list(users)),
                       lambda *args, **kwargs: send_notification_http(realm, *args, **kwargs))
