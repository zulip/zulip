from typing import Annotated, TypeAlias

from annotated_types import Len
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.compatibility import is_pronouns_field_type_supported
from zerver.lib.events import DEFAULT_CLIENT_CAPABILITIES, ClientCapabilities, do_events_register
from zerver.lib.exceptions import JsonableError, MissingAuthenticationError
from zerver.lib.narrow_helpers import narrow_dataclasses_from_tuples
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import ApiParamConfig, DocumentationStatus, typed_endpoint
from zerver.models import Stream, UserProfile


def _default_all_public_streams(user_profile: UserProfile, all_public_streams: bool | None) -> bool:
    if all_public_streams is not None:
        return all_public_streams
    else:
        return user_profile.default_all_public_streams


def _default_narrow(user_profile: UserProfile, narrow: list[list[str]]) -> list[list[str]]:
    default_stream: Stream | None = user_profile.default_events_register_stream
    if not narrow and default_stream is not None:
        narrow = [["stream", default_stream.name]]
    return narrow


NarrowT: TypeAlias = list[Annotated[list[str], Len(min_length=2, max_length=2)]]


@typed_endpoint
def events_register_backend(
    request: HttpRequest,
    maybe_user_profile: UserProfile | AnonymousUser,
    *,
    all_public_streams: Json[bool] | None = None,
    apply_markdown: Json[bool] = False,
    client_capabilities: Json[ClientCapabilities] = DEFAULT_CLIENT_CAPABILITIES,
    client_gravatar_raw: Annotated[Json[bool | None], ApiParamConfig("client_gravatar")] = None,
    event_types: Json[list[str]] | None = None,
    fetch_event_types: Json[list[str]] | None = None,
    include_subscribers: Json[bool] = False,
    narrow: Json[NarrowT] | None = None,
    presence_history_limit_days: Json[int] | None = None,
    queue_lifespan_secs: Annotated[
        Json[int], ApiParamConfig(documentation_status=DocumentationStatus.DOCUMENTATION_PENDING)
    ] = 0,
    slim_presence: Json[bool] = False,
) -> HttpResponse:
    if narrow is None:
        narrow = []
    if client_gravatar_raw is None:
        client_gravatar = maybe_user_profile.is_authenticated
    else:
        client_gravatar = client_gravatar_raw

    if maybe_user_profile.is_authenticated:
        user_profile = maybe_user_profile
        spectator_requested_language = None
        assert isinstance(user_profile, UserProfile)
        realm = user_profile.realm
        include_streams = True

        if all_public_streams and not user_profile.can_access_public_streams():
            raise JsonableError(_("User not authorized for this query"))

        all_public_streams = _default_all_public_streams(user_profile, all_public_streams)
        narrow = _default_narrow(user_profile, narrow)
    else:
        user_profile = None
        realm = get_valid_realm_from_request(request)
        if not realm.allow_web_public_streams_access():
            raise MissingAuthenticationError

        # These parameters must be false for anonymous requests.
        if client_gravatar:
            raise JsonableError(
                _("Invalid '{key}' parameter for anonymous request").format(key="client_gravatar")
            )
        if include_subscribers:
            raise JsonableError(
                _("Invalid '{key}' parameter for anonymous request").format(
                    key="include_subscribers"
                )
            )

        # Language set by spectator to be passed down to clients as user_settings.
        spectator_requested_language = request.COOKIES.get(
            settings.LANGUAGE_COOKIE_NAME, realm.default_language
        )

        all_public_streams = False
        include_streams = False

    client = RequestNotes.get_notes(request).client
    assert client is not None

    pronouns_field_type_supported = is_pronouns_field_type_supported(
        request.headers.get("User-Agent")
    )

    # TODO: We eventually want to let callers pass in dictionaries over the wire,
    #       but we will still need to support tuples for a long time.
    modern_narrow = narrow_dataclasses_from_tuples(narrow)

    ret = do_events_register(
        user_profile,
        realm,
        client,
        apply_markdown,
        client_gravatar,
        slim_presence,
        None,
        presence_history_limit_days,
        event_types,
        queue_lifespan_secs,
        all_public_streams,
        narrow=modern_narrow,
        include_subscribers=include_subscribers,
        include_streams=include_streams,
        client_capabilities=client_capabilities,
        fetch_event_types=fetch_event_types,
        spectator_requested_language=spectator_requested_language,
        pronouns_field_type_supported=pronouns_field_type_supported,
    )
    return json_success(request, data=ret)
