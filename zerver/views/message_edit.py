import datetime
from typing import Any, Dict, List, Optional

import orjson
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.decorator import REQ, has_request_variables
from zerver.lib.actions import (
    check_update_message,
    do_delete_messages,
    do_update_message,
    get_user_info_for_message_updates,
    render_incoming_message,
)
from zerver.lib.exceptions import DeactivatedStreamError, JsonableError
from zerver.lib.html_diff import highlight_html_differences
from zerver.lib.message import access_message
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
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
        raise JsonableError(_("Message edit history is disabled in this organization"))
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
    propagate_mode: str = REQ(
        default="change_one", str_validator=check_string_in(PROPAGATE_MODE_VALUES)
    ),
    send_notification_to_old_thread: bool = REQ(default=True, json_validator=check_bool),
    send_notification_to_new_thread: bool = REQ(default=True, json_validator=check_bool),
    content: Optional[str] = REQ(default=None),
) -> HttpResponse:
    if not user_profile.realm.allow_message_editing:
        return json_error(_("Your organization has turned off message editing"))

    if propagate_mode != "change_one" and topic_name is None and stream_id is None:
        return json_error(_("Invalid propagate_mode without topic edit"))

    message, ignored_user_message = access_message(user_profile, message_id)
    is_no_topic_msg = message.topic_name() == "(no topic)"

    # You only have permission to edit a message if:
    # you change this value also change those two parameters in message_edit.js.
    # 1. You sent it, OR:
    # 2. This is a topic-only edit for a (no topic) message, OR:
    # 3. This is a topic-only edit and you are an admin, OR:
    # 4. This is a topic-only edit and your realm allows users to edit topics.
    if message.sender == user_profile:
        pass
    elif (content is None) and (
        is_no_topic_msg
        or user_profile.is_realm_admin
        or user_profile.realm.allow_community_topic_editing
    ):
        pass
    else:
        raise JsonableError(_("You don't have permission to edit this message"))

    # Disallow editing of messages in deactivated streams unless you are an admin.
    if message.is_stream_message() and not user_profile.is_realm_admin:
        message_stream = get_stream_by_id(message.recipient.type_id)
        if message_stream.deactivated:
            raise DeactivatedStreamError()

    # If there is a change to the content, check that it hasn't been too long
    # Allow an extra 20 seconds since we potentially allow editing 15 seconds
    # past the limit, and in case there are network issues, etc. The 15 comes
    # from (min_seconds_to_edit + seconds_left_buffer) in message_edit.js; if
    # you change this value also change those two parameters in message_edit.js.
    edit_limit_buffer = 20
    if content is not None and user_profile.realm.message_content_edit_limit_seconds > 0:
        deadline_seconds = user_profile.realm.message_content_edit_limit_seconds + edit_limit_buffer
        if (timezone_now() - message.date_sent) > datetime.timedelta(seconds=deadline_seconds):
            raise JsonableError(_("The time limit for editing this message has passed"))

    # If there is a change to the topic, check that the user is allowed to
    # edit it and that it has not been too long. If this is not the user who
    # sent the message, they are not the admin, and the time limit for editing
    # topics is passed, raise an error.
    if (
        content is None
        and message.sender != user_profile
        and not user_profile.is_realm_admin
        and not is_no_topic_msg
    ):
        deadline_seconds = Realm.DEFAULT_COMMUNITY_TOPIC_EDITING_LIMIT_SECONDS + edit_limit_buffer
        if (timezone_now() - message.date_sent) > datetime.timedelta(seconds=deadline_seconds):
            raise JsonableError(_("The time limit for editing this message has passed"))

    if topic_name is None and content is None and stream_id is None:
        return json_error(_("Nothing to change"))
    if topic_name is not None:
        topic_name = topic_name.strip()
        if topic_name == "":
            raise JsonableError(_("Topic can't be empty"))
    rendered_content = None
    links_for_embed: Set[str] = set()
    prior_mention_user_ids: Set[int] = set()
    mention_user_ids: Set[int] = set()
    mention_data: Optional[MentionData] = None
    if content is not None:
        if content.rstrip() == "":
            content = "(deleted)"
        content = normalize_body(content)

        mention_data = MentionData(
            realm_id=user_profile.realm.id,
            content=content,
        )
        user_info = get_user_info_for_message_updates(message.id)
        prior_mention_user_ids = user_info["mention_user_ids"]

        # We render the message using the current user's realm; since
        # the cross-realm bots never edit messages, this should be
        # always correct.
        # Note: If rendering fails, the called code will raise a JsonableError.
        rendered_content = render_incoming_message(
            message,
            content,
            user_info["message_user_ids"],
            user_profile.realm,
            mention_data=mention_data,
        )
        links_for_embed |= message.links_for_preview

        mention_user_ids = message.mentions_user_ids

    new_stream = None
    number_changed = 0

    if stream_id is not None:
        if not user_profile.is_realm_admin:
            raise JsonableError(_("You don't have permission to move this message"))
        if content is not None:
            raise JsonableError(_("Cannot change message content while changing stream"))

        new_stream = get_stream_by_id(stream_id)

    number_changed = do_update_message(
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
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = f"[{number_changed}]"

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
    if message.is_stream_message():
        message_stream = get_stream_by_id(message.recipient.type_id)
        if message_stream.deactivated:
            # Users can not delete messages in deactivated streams.
            raise DeactivatedStreamError()

    deadline_seconds = user_profile.realm.message_content_delete_limit_seconds
    if deadline_seconds == 0:
        # 0 for no time limit to delete message
        return
    if (timezone_now() - message.date_sent) > datetime.timedelta(seconds=deadline_seconds):
        # User can not delete message after deadline time of realm
        raise JsonableError(_("The time limit for deleting this message has passed"))
    return


@transaction.atomic
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
