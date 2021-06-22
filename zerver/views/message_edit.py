import datetime
from typing import Any, Dict, List, Optional

import orjson
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.decorator import REQ, has_request_variables
from zerver.lib.actions import check_update_message, do_delete_messages
from zerver.lib.exceptions import JsonableError
from zerver.lib.html_diff import highlight_html_differences
from zerver.lib.message import access_message
from zerver.lib.response import json_error, json_success
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import LEGACY_PREV_TOPIC, REQ_topic
from zerver.lib.validator import check_bool, check_string_in, to_non_negative_int
from zerver.models import Message, UserProfile


def fill_edit_history_entries(message_history: List[Dict[str, Any]], message: Message) -> None:
    """This fills out the message edit history entries from the database,
    which are designed to have the minimum data possible, to instead
    have the current topic + content as of that time, plus data on
    whatever changed.  This makes it much simpler to do future
    processing.

    Note that this mutates what is passed to it, which is sorta a bad pattern.
    """
    prev_content = message.content
    prev_rendered_content = message.rendered_content
    prev_topic = message.topic_name()

    # Make sure that the latest entry in the history corresponds to the
    # message's last edit time
    if len(message_history) > 0:
        assert message.last_edit_time is not None
        assert datetime_to_timestamp(message.last_edit_time) == message_history[0]["timestamp"]

    for entry in message_history:
        entry["topic"] = prev_topic
        if LEGACY_PREV_TOPIC in entry:
            prev_topic = entry[LEGACY_PREV_TOPIC]
            entry["prev_topic"] = prev_topic
            del entry[LEGACY_PREV_TOPIC]

        entry["content"] = prev_content
        entry["rendered_content"] = prev_rendered_content
        if "prev_content" in entry:
            del entry["prev_rendered_content_version"]
            prev_content = entry["prev_content"]
            prev_rendered_content = entry["prev_rendered_content"]
            assert prev_rendered_content is not None
            entry["content_html_diff"] = highlight_html_differences(
                prev_rendered_content, entry["rendered_content"], message.id
            )

    message_history.append(
        dict(
            topic=prev_topic,
            content=prev_content,
            rendered_content=prev_rendered_content,
            timestamp=datetime_to_timestamp(message.date_sent),
            user_id=message.sender_id,
        )
    )


@has_request_variables
def get_message_edit_history(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int = REQ(converter=to_non_negative_int, path_only=True),
) -> HttpResponse:
    if not user_profile.realm.allow_edit_history:
        return json_error(_("Message edit history is disabled in this organization"))
    message, ignored_user_message = access_message(user_profile, message_id)

    # Extract the message edit history from the message
    if message.edit_history is not None:
        message_edit_history = orjson.loads(message.edit_history)
    else:
        message_edit_history = []

    # Fill in all the extra data that will make it usable
    fill_edit_history_entries(message_edit_history, message)
    return json_success({"message_history": list(reversed(message_edit_history))})


PROPAGATE_MODE_VALUES = ["change_later", "change_one", "change_all"]


@has_request_variables
def update_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int = REQ(converter=to_non_negative_int, path_only=True),
    stream_id: Optional[int] = REQ(converter=to_non_negative_int, default=None),
    topic_name: Optional[str] = REQ_topic(),
    propagate_mode: Optional[str] = REQ(
        default="change_one", str_validator=check_string_in(PROPAGATE_MODE_VALUES)
    ),
    send_notification_to_old_thread: bool = REQ(default=True, json_validator=check_bool),
    send_notification_to_new_thread: bool = REQ(default=True, json_validator=check_bool),
    content: Optional[str] = REQ(default=None),
) -> HttpResponse:
    number_changed = check_update_message(
        user_profile,
        message_id,
        stream_id,
        topic_name,
        propagate_mode,
        send_notification_to_old_thread,
        send_notification_to_new_thread,
        content,
    )

    # Include the number of messages changed in the logs
    request._log_data["extra"] = f"[{number_changed}]"

    return json_success()


def validate_can_delete_message(user_profile: UserProfile, message: Message) -> None:
    if user_profile.is_realm_admin:
        # Admin can delete any message, any time.
        return
    if message.sender != user_profile:
        # Users can only delete messages sent by them.
        raise JsonableError(_("You don't have permission to delete this message"))
    if not user_profile.realm.allow_message_deleting:
        # User can not delete message, if message deleting is not allowed in realm.
        raise JsonableError(_("You don't have permission to delete this message"))

    deadline_seconds = user_profile.realm.message_content_delete_limit_seconds
    if deadline_seconds == 0:
        # 0 for no time limit to delete message
        return
    if (timezone_now() - message.date_sent) > datetime.timedelta(seconds=deadline_seconds):
        # User can not delete message after deadline time of realm
        raise JsonableError(_("The time limit for deleting this message has passed"))
    return


@transaction.atomic(savepoint=False)
@has_request_variables
def delete_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int = REQ(converter=to_non_negative_int, path_only=True),
) -> HttpResponse:
    # We lock the `Message` object to ensure that any transactions modifying the `Message` object
    # concurrently are serialized properly with deleting the message; this prevents a deadlock
    # that would otherwise happen because of the other transaction holding a lock on the `Message`
    # row.
    message, ignored_user_message = access_message(user_profile, message_id, lock_message=True)
    validate_can_delete_message(user_profile, message)
    try:
        do_delete_messages(user_profile.realm, [message])
    except (Message.DoesNotExist, IntegrityError):
        raise JsonableError(_("Message already deleted"))
    return json_success()


@has_request_variables
def json_fetch_raw_message(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int = REQ(converter=to_non_negative_int, path_only=True),
) -> HttpResponse:
    (message, user_message) = access_message(user_profile, message_id)
    return json_success({"raw_content": message.content})
