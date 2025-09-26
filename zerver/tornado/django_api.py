from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

import orjson
import requests
from django.conf import settings
from django.db import transaction
from requests.adapters import ConnectionError, HTTPAdapter
from requests.models import PreparedRequest, Response
from typing_extensions import override
from urllib3.util import Retry

from zerver.lib.partial import partial
from zerver.lib.queue import queue_json_publish_rollback_unsafe
from zerver.models import Client, Realm, UserProfile
from zerver.models.users import get_user_profile_narrow_by_id
from zerver.tornado.sharding import (
    get_realm_tornado_ports,
    get_tornado_url,
    get_user_id_tornado_port,
    get_user_tornado_port,
    notify_tornado_queue_name,
)


class TornadoAdapter(HTTPAdapter):
    def __init__(self) -> None:
        # All of the POST requests we make to Tornado are safe to
        # retry; allow retries of them, which is not the default.
        retry_methods = Retry.DEFAULT_ALLOWED_METHODS | {"POST"}
        retry = Retry(total=3, backoff_factor=1, allowed_methods=retry_methods)
        super().__init__(max_retries=retry)

    @override
    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: None | float | tuple[float, float] | tuple[float, None] = 0.5,
        verify: bool | str = True,
        cert: None | bytes | str | tuple[bytes | str, bytes | str] = None,
        proxies: Mapping[str, str] | None = None,
    ) -> Response:
        # Don't talk to Tornado through proxies, which only allow
        # requests to external hosts.
        proxies = {}
        try:
            resp = super().send(
                request, stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies
            )
        except ConnectionError:
            parsed_url = urlsplit(request.url)
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


def request_event_queue(
    user_profile: UserProfile,
    user_client: Client,
    apply_markdown: bool,
    client_gravatar: bool,
    slim_presence: bool,
    queue_lifespan_secs: int,
    event_types: Sequence[str] | None = None,
    all_public_streams: bool = False,
    narrow: Iterable[Sequence[str]] = [],
    bulk_message_deletion: bool = False,
    stream_typing_notifications: bool = False,
    user_settings_object: bool = False,
    pronouns_field_type_supported: bool = True,
    linkifier_url_template: bool = False,
    user_list_incomplete: bool = False,
    include_deactivated_groups: bool = False,
    archived_channels: bool = False,
    empty_topic_name: bool = False,
    simplified_presence_events: bool = False,
) -> str | None:
    if not settings.USING_TORNADO:
        return None

    # We make sure to pre-fill the narrow user cache, to save
    # session-based Tornado (/json/events) from having to go to the
    # database.
    get_user_profile_narrow_by_id(user_profile.id)

    if user_client.name == "ZulipFlutter" and queue_lifespan_secs == 0:
        queue_lifespan_secs = 12 * 60 * 60  # Test 12-hour-long GCs for Flutter

    tornado_url = get_tornado_url(get_user_tornado_port(user_profile))
    req = {
        "dont_block": "true",
        "apply_markdown": orjson.dumps(apply_markdown),
        "client_gravatar": orjson.dumps(client_gravatar),
        "slim_presence": orjson.dumps(slim_presence),
        "all_public_streams": orjson.dumps(all_public_streams),
        "client": "internal",
        "user_profile_id": user_profile.id,
        "user_client": user_client.name,
        "narrow": orjson.dumps(narrow),
        "secret": settings.SHARED_SECRET,
        "lifespan_secs": queue_lifespan_secs,
        "bulk_message_deletion": orjson.dumps(bulk_message_deletion),
        "stream_typing_notifications": orjson.dumps(stream_typing_notifications),
        "user_settings_object": orjson.dumps(user_settings_object),
        "pronouns_field_type_supported": orjson.dumps(pronouns_field_type_supported),
        "linkifier_url_template": orjson.dumps(linkifier_url_template),
        "user_list_incomplete": orjson.dumps(user_list_incomplete),
        "include_deactivated_groups": orjson.dumps(include_deactivated_groups),
        "archived_channels": orjson.dumps(archived_channels),
        "empty_topic_name": orjson.dumps(empty_topic_name),
        "simplified_presence_events": orjson.dumps(simplified_presence_events),
    }

    if event_types is not None:
        req["event_types"] = orjson.dumps(event_types)

    resp = requests_client().post(tornado_url + "/api/v1/events/internal", data=req)
    return resp.json()["queue_id"]


def get_user_events(
    user_profile: UserProfile, queue_id: str, last_event_id: int
) -> list[dict[str, Any]]:
    if not settings.USING_TORNADO:
        return []

    # Pre-fill the narrow user cache, to save session-based Tornado
    # (/json/events) from having to go to the database.  This is
    # almost certainly filled already, from above, but there is little
    # harm in forcing it.
    get_user_profile_narrow_by_id(user_profile.id)

    tornado_url = get_tornado_url(get_user_tornado_port(user_profile))
    post_data: dict[str, Any] = {
        "queue_id": queue_id,
        "last_event_id": last_event_id,
        "dont_block": "true",
        "user_profile_id": user_profile.id,
        "secret": settings.SHARED_SECRET,
        "client": "internal",
    }
    resp = requests_client().post(tornado_url + "/api/v1/events/internal", data=post_data)
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
        from zerver.tornado.event_queue import process_notification

        process_notification(data)
    else:
        # This codepath is only used when running full-stack puppeteer
        # tests, which don't have RabbitMQ but do have a separate
        # Tornado process.
        tornado_url = get_tornado_url(port)
        requests_client().post(
            tornado_url + "/api/internal/notify_tornado",
            data=dict(data=orjson.dumps(data), secret=settings.SHARED_SECRET),
        )


# The core function for sending an event from Django to Tornado (which
# will then push it to web and mobile clients for the target users).
#
# One should generally use `send_event_on_commit` unless there's a strong
# reason to use `send_event_rollback_unsafe` directly, as it doesn't wait
# for the db transaction (within which it gets called, if any) to commit
# and sends event irrespective of commit or rollback.
#
# By convention, `send_event_rollback_unsafe` / `send_event_on_commit`
# should only be called from zerver/actions/*.py, which helps make it
# easy to find event generation code.
#
# Every call point should be covered by a test in `test_events.py`,
# with the schema verified in `zerver/lib/event_schema.py`.
#
# See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html
def send_event_rollback_unsafe(
    realm: Realm, event: Mapping[str, Any], users: Iterable[int] | Iterable[Mapping[str, Any]]
) -> None:
    """`users` is a list of user IDs, or in some special cases like message
    send/update or embeds, dictionaries containing extra data."""
    realm_ports = get_realm_tornado_ports(realm)
    if len(realm_ports) == 1:
        port_user_map = {realm_ports[0]: list(users)}
    else:
        port_user_map = defaultdict(list)
        for user in users:
            user_id = user if isinstance(user, int) else user["id"]
            port_user_map[get_user_id_tornado_port(realm_ports, user_id)].append(user)

    for port, port_users in port_user_map.items():
        queue_json_publish_rollback_unsafe(
            notify_tornado_queue_name(port),
            dict(event=event, users=port_users),
            partial(send_notification_http, port),
        )


def send_event_on_commit(
    realm: Realm, event: Mapping[str, Any], users: Iterable[int] | Iterable[Mapping[str, Any]]
) -> None:
    if not settings.USING_RABBITMQ:
        # In tests, round-trip the event through JSON, as happens with
        # RabbitMQ.  zerver.lib.queue also enforces this, but the
        # on-commit nature of the event sending makes it difficult to
        # trace which event was at fault -- so we also check it
        # immediately, here.
        try:
            event = orjson.loads(orjson.dumps(event))
        except TypeError:
            print(event)
            raise
    transaction.on_commit(lambda: send_event_rollback_unsafe(realm, event, users))
