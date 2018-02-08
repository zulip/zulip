
from django.http import HttpResponse, HttpRequest
from typing import List, Text

import ujson

from django.utils.translation import ugettext as _
from zerver.lib.actions import do_mute_topic, do_unmute_topic, do_mute_user, do_unmute_user
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.topic_mutes import topic_is_muted
from zerver.lib.mute_users import user_is_muted
from zerver.lib.streams import access_stream_by_name, access_stream_for_unmute_topic
from zerver.lib.validator import check_string, check_list
from zerver.models import get_stream, get_user_profile_by_id, Stream, UserProfile

def mute_topic(user_profile: UserProfile, stream_name: str,
               topic_name: str) -> HttpResponse:
    (stream, recipient, sub) = access_stream_by_name(user_profile, stream_name)

    if topic_is_muted(user_profile, stream.id, topic_name):
        return json_error(_("Topic already muted"))

    do_mute_topic(user_profile, stream, recipient, topic_name)
    return json_success()

def unmute_topic(user_profile: UserProfile, stream_name: str,
                 topic_name: str) -> HttpResponse:
    error = _("Topic is not there in the muted_topics list")
    stream = access_stream_for_unmute_topic(user_profile, stream_name, error)

    if not topic_is_muted(user_profile, stream.id, topic_name):
        return json_error(error)

    do_unmute_topic(user_profile, stream, topic_name)
    return json_success()

def mute_user(user_profile: UserProfile,
              muted_user_profile: UserProfile) -> HttpResponse:
    error = _("User already muted")

    if user_is_muted(user_profile, muted_user_profile):
        return json_error(error)

    do_mute_user(user_profile, muted_user_profile)
    return json_success()

def unmute_user(user_profile: UserProfile,
                muted_user_profile: UserProfile) -> HttpResponse:
    error = _("User is not there in muted_users list")

    if not user_is_muted(user_profile, muted_user_profile):
        return json_error(error)

    do_unmute_user(user_profile, muted_user_profile)
    return json_success()

@has_request_variables
def update_muted_topic(request: HttpRequest, user_profile: UserProfile, stream: str=REQ(),
                       topic: str=REQ(), op: str=REQ()) -> HttpResponse:

    if op == 'add':
        return mute_topic(user_profile, stream, topic)
    elif op == 'remove':
        return unmute_topic(user_profile, stream, topic)

@has_request_variables
def add_muted_user(request: HttpRequest, user_profile: UserProfile,
                   muted_user_id: int=REQ()) -> HttpResponse:

    muted_user_profile = get_user_profile_by_id(muted_user_id)
    return mute_user(user_profile, muted_user_profile)

@has_request_variables
def remove_muted_user(request: HttpRequest, user_profile: UserProfile,
                      muted_user_id: int=REQ()) -> HttpResponse:

    muted_user_profile = get_user_profile_by_id(muted_user_id)
    return unmute_user(user_profile, muted_user_profile)
