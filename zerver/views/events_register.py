from typing import Dict, Iterable, Optional, Sequence

from django.http import HttpRequest, HttpResponse

from zerver.lib.events import do_events_register
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_bool, check_dict, check_list, check_string
from zerver.models import Stream, UserProfile


def _default_all_public_streams(user_profile: UserProfile,
                                all_public_streams: Optional[bool]) -> bool:
    if all_public_streams is not None:
        return all_public_streams
    else:
        return user_profile.default_all_public_streams

def _default_narrow(user_profile: UserProfile,
                    narrow: Iterable[Sequence[str]]) -> Iterable[Sequence[str]]:
    default_stream: Optional[Stream] = user_profile.default_events_register_stream
    if not narrow and default_stream is not None:
        narrow = [['stream', default_stream.name]]
    return narrow

NarrowT = Iterable[Sequence[str]]
@has_request_variables
def events_register_backend(
        request: HttpRequest, user_profile: UserProfile,
        apply_markdown: bool=REQ(default=False, validator=check_bool),
        client_gravatar: bool=REQ(default=False, validator=check_bool),
        slim_presence: bool=REQ(default=False, validator=check_bool),
        all_public_streams: Optional[bool]=REQ(default=None, validator=check_bool),
        include_subscribers: bool=REQ(default=False, validator=check_bool),
        client_capabilities: Optional[Dict[str, bool]]=REQ(validator=check_dict([
            # This field was accidentally made required when it was added in v2.0.0-781;
            # this was not realized until after the release of Zulip 2.1.2. (It remains
            # required to help ensure backwards compatibility of client code.)
            ("notification_settings_null", check_bool),
        ], [
            # Any new fields of `client_capabilities` should be optional. Add them here.
            ("bulk_message_deletion", check_bool),
            ('user_avatar_url_field_optional', check_bool),
        ], value_validator=check_bool), default=None),
        event_types: Optional[Iterable[str]]=REQ(validator=check_list(check_string), default=None),
        fetch_event_types: Optional[Iterable[str]]=REQ(validator=check_list(check_string), default=None),
        narrow: NarrowT=REQ(validator=check_list(check_list(check_string, length=2)), default=[]),
        queue_lifespan_secs: int=REQ(converter=int, default=0, documentation_pending=True),
) -> HttpResponse:
    all_public_streams = _default_all_public_streams(user_profile, all_public_streams)
    narrow = _default_narrow(user_profile, narrow)

    if client_capabilities is None:
        client_capabilities = {}

    ret = do_events_register(user_profile, request.client,
                             apply_markdown, client_gravatar, slim_presence,
                             event_types, queue_lifespan_secs, all_public_streams,
                             narrow=narrow, include_subscribers=include_subscribers,
                             client_capabilities=client_capabilities,
                             fetch_event_types=fetch_event_types)
    return json_success(ret)
