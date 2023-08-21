from collections import defaultdict
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import urlparse

import orjson
import requests
from django.conf import settings
from django.db import transaction
from requests.adapters import ConnectionError, HTTPAdapter
from requests.models import PreparedRequest, Response
from urllib3.util import Retry

from zerver.lib.queue import queue_json_publish
from zerver.models import Client, Realm, UserProfile
from .config import get_server_url, notify_queue_name


class TornadoAdapter(HTTPAdapter):
    def __init__(self) -> None:
        # All of the POST requests we make to Tornado are safe to
        # retry; allow retries of them, which is not the default.
        retry_methods = Retry.DEFAULT_ALLOWED_METHODS | {"POST"}
        retry = Retry(total=3, backoff_factor=1, allowed_methods=retry_methods)
        super().__init__(max_retries=retry)

    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: Union[None, float, Tuple[float, float], Tuple[float, None]] = 0.5,
        verify: Union[bool, str] = True,
        cert: Union[None, bytes, str, Tuple[Union[bytes, str], Union[bytes, str]]] = None,
        proxies: Optional[Mapping[str, str]] = None,
    ) -> Response:
        # Don't talk to Tornado through proxies, which only allow
        # requests to external hosts.
        proxies = {}
        try:
            resp = super().send(
                request, stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies
            )
        except ConnectionError:
            parsed_url = urlparse(request.url)
            logfile = (
                f"tornado-{parsed_url.port}.log"
                if settings.TORNADO_PROCESSES > 1
                else "tornado.log"
            )
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


def request_presence_event_queue(
    user_profile: UserProfile,
    user_client: Client,
    queue_lifespan_secs: int,
) -> Optional[str]:
    if not settings.USING_TORNADO:
        return None

    tornado_url = get_server_url()
    req = {
        "dont_block": "true",
        "client": "internal",
        "user_profile_id": user_profile.id,
        "user_client": user_client.name,
        "secret": settings.SHARED_SECRET,
        "lifespan_secs": queue_lifespan_secs,
    }

    resp = requests_client().post(tornado_url + "/api/v1/presence_events/internal", data=req)
    return resp.json()["queue_id"]


def get_user_events(
    user_profile: UserProfile, queue_id: str, last_event_id: int
) -> List[Dict[str, Any]]:
    if not settings.USING_TORNADO:
        return []

    tornado_url = get_server_url()
    post_data: Dict[str, Any] = {
        "queue_id": queue_id,
        "last_event_id": last_event_id,
        "dont_block": "true",
        "user_profile_id": user_profile.id,
        "secret": settings.SHARED_SECRET,
        "client": "internal",
    }
    resp = requests_client().post(tornado_url + "/api/v1/presence_events/internal", data=post_data)
    return resp.json()["events"]


def send_notification_http(port: int, data: Mapping[str, Any]) -> None:
    if not settings.USING_TORNADO or settings.RUNNING_INSIDE_TORNADO:
        # To allow the backend test suite to not require a separate
        # Tornado process, we simply call the process_notification
        # handler directly rather than making the notify_tornado HTTP
        # request.  It would perhaps be better to instead implement
        # this via some sort of `responses` module configuration, but
        # perhaps it's more readable to have the logic live here.
        #
        # We use an import local to this function to prevent this hack
        # from creating import cycles.
        from .event_queue import process_notification

        process_notification(data)
    else:
        print("Post with SHARED_SECRET")
        tornado_url = get_tornado_url(port)
        requests_client().post(
            tornado_url + "/notify_presence",
            data=dict(data=orjson.dumps(data), secret=settings.SHARED_SECRET),
        )

def send_presence_event(event, user_ids):
    port = 8888

    assert event["type"] == "presence"

    print("PRESENCE: about to publish to queue!!")
    queue_json_publish(
        notify_queue_name(),
        dict(event=event, users=user_ids),
        lambda *args, **kwargs: send_notification_http(port, *args, **kwargs),
    )
