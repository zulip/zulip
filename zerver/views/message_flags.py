from typing import List, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import REQ, has_request_variables
from zerver.lib.actions import (
    do_mark_all_as_read,
    do_mark_stream_messages_as_read,
    do_update_message_flags,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id
from zerver.lib.topic import user_message_exists_for_topic
from zerver.lib.validator import check_int, check_list
from zerver.models import UserActivity, UserProfile


def get_latest_update_message_flag_activity(user_profile: UserProfile) -> Optional[UserActivity]:
    return UserActivity.objects.filter(user_profile=user_profile,
                                       query='update_message_flags').order_by("last_visit").last()

# NOTE: If this function name is changed, add the new name to the
# query in get_latest_update_message_flag_activity
@has_request_variables
def update_message_flags(request: HttpRequest, user_profile: UserProfile,
                         messages: List[int]=REQ(validator=check_list(check_int)),
                         operation: str=REQ('op'), flag: str=REQ()) -> HttpResponse:

    count = do_update_message_flags(user_profile, request.client, operation, flag, messages)

    target_count_str = str(len(messages))
    log_data_str = f"[{operation} {flag}/{target_count_str}] actually {count}"
    request._log_data["extra"] = log_data_str

    return json_success({'result': 'success',
                         'messages': messages,
                         'msg': ''})

@has_request_variables
def mark_all_as_read(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    count = do_mark_all_as_read(user_profile, request.client)

    log_data_str = f"[{count} updated]"
    request._log_data["extra"] = log_data_str

    return json_success({'result': 'success',
                         'msg': ''})

@has_request_variables
def mark_stream_as_read(request: HttpRequest,
                        user_profile: UserProfile,
                        stream_id: int=REQ(validator=check_int)) -> HttpResponse:
    stream, sub = access_stream_by_id(user_profile, stream_id)
    count = do_mark_stream_messages_as_read(user_profile, stream.recipient_id)

    log_data_str = f"[{count} updated]"
    request._log_data["extra"] = log_data_str

    return json_success({'result': 'success',
                         'msg': ''})

@has_request_variables
def mark_topic_as_read(request: HttpRequest,
                       user_profile: UserProfile,
                       stream_id: int=REQ(validator=check_int),
                       topic_name: str=REQ()) -> HttpResponse:
    stream, sub = access_stream_by_id(user_profile, stream_id)

    if topic_name:
        topic_exists = user_message_exists_for_topic(
            user_profile=user_profile,
            recipient_id=stream.recipient_id,
            topic_name=topic_name,
        )

        if not topic_exists:
            raise JsonableError(_('No such topic \'{}\'').format(topic_name))

    count = do_mark_stream_messages_as_read(user_profile, stream.recipient_id, topic_name)

    log_data_str = f"[{count} updated]"
    request._log_data["extra"] = log_data_str

    return json_success({'result': 'success',
                         'msg': ''})
