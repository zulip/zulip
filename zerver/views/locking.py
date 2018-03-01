
from django.http import HttpResponse, HttpRequest
from typing import List, Text

from zerver.decorator import require_realm_admin
from django.utils.translation import ugettext as _
from zerver.lib.actions import do_lock_topic, do_unlock_topic
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.locked_topics import topic_is_locked
from zerver.lib.streams import access_stream_by_name
from zerver.models import Stream, UserProfile

def lock_topic(user_profile: UserProfile, stream_name: str,
               topic_name: str) -> HttpResponse:
    (stream, recipient, sub) = access_stream_by_name(user_profile, stream_name)

    if topic_is_locked(stream.id, topic_name):
        return json_error(_("Topic already locked"))

    do_lock_topic(user_profile, stream, topic_name)
    return json_success()

def unlock_topic(user_profile: UserProfile, stream_name: str,
                 topic_name: str) -> HttpResponse:
    error = _("Topic is not there in the locked_topics list")
    (stream, recipient, sub) = access_stream_by_name(user_profile, stream_name)

    if not topic_is_locked(stream.id, topic_name):
        return json_error(error)

    do_unlock_topic(user_profile, stream, topic_name)
    return json_success()

@require_realm_admin
@has_request_variables
def update_locked_topic(request: HttpRequest, user_profile: UserProfile, stream: str=REQ(),
                        topic: str=REQ(), op: str=REQ()) -> HttpResponse:

    if op == 'add':
        return lock_topic(user_profile, stream, topic)
    elif op == 'remove':
        return unlock_topic(user_profile, stream, topic)
