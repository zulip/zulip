from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse
from typing import Text
from typing import Iterable, Optional, Sequence

from zerver.lib.events import do_events_register
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_string, check_list, check_bool
from zerver.models import Stream, UserProfile

def _default_all_public_streams(user_profile, all_public_streams):
    # type: (UserProfile, Optional[bool]) -> bool
    if all_public_streams is not None:
        return all_public_streams
    else:
        return user_profile.default_all_public_streams

def _default_narrow(user_profile, narrow):
    # type: (UserProfile, Iterable[Sequence[Text]]) -> Iterable[Sequence[Text]]
    default_stream = user_profile.default_events_register_stream  # type: Optional[Stream]
    if not narrow and user_profile.default_events_register_stream is not None:
        narrow = [['stream', default_stream.name]]
    return narrow

@has_request_variables
def events_register_backend(request, user_profile,
                            apply_markdown=REQ(default=False, validator=check_bool),
                            all_public_streams=REQ(default=None, validator=check_bool),
                            include_subscribers=REQ(default=False, validator=check_bool),
                            event_types=REQ(validator=check_list(check_string), default=None),
                            fetch_event_types=REQ(validator=check_list(check_string), default=None),
                            narrow=REQ(validator=check_list(check_list(check_string, length=2)), default=[]),
                            queue_lifespan_secs=REQ(converter=int, default=0)):
    # type: (HttpRequest, UserProfile, bool, Optional[bool], bool, Optional[Iterable[str]], Optional[Iterable[str]], Iterable[Sequence[Text]], int) -> HttpResponse
    all_public_streams = _default_all_public_streams(user_profile, all_public_streams)
    narrow = _default_narrow(user_profile, narrow)

    ret = do_events_register(user_profile, request.client, apply_markdown,
                             event_types, queue_lifespan_secs, all_public_streams,
                             narrow=narrow, include_subscribers=include_subscribers,
                             fetch_event_types=fetch_event_types)
    return json_success(ret)
