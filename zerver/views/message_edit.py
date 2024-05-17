from datetime import timedelta
from typing import List, Literal, Optional, Union

import orjson
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import Json, NonNegativeInt

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_edit import check_update_message
from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.exceptions import JsonableError
from zerver.lib.html_diff import highlight_html_differences
from zerver.lib.message import (
    access_message,
    access_message_and_usermessage,
    access_web_public_message,
    messages_for_ids,
)
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.typed_endpoint import OptionalTopic, PathOnly, typed_endpoint
from zerver.lib.types import EditHistoryEvent, FormattedEditHistoryEvent
from zerver.models import Message, UserProfile


def fill_edit_history_entries(
    raw_edit_history: List[EditHistoryEvent], message: Message
) -> List[FormattedEditHistoryEvent]:
    """
    This fills out the message edit history entries from the database
    to have the current topic + content as of that time, plus data on
    whatever changed. This makes it much simpler to do future
    processing.
    """
    prev_content = message.content
    prev_rendered_content = message.rendered_content
    prev_topic_name = message.topic_name()

    # Make sure that the latest entry in the history corresponds to the
    # message's last edit time
    if len(raw_edit_history) > 0:
        assert message.last_edit_time is not None
        assert datetime_to_timestamp(message.last_edit_time) == raw_edit_history[0]["timestamp"]

    formatted_edit_history: List[FormattedEditHistoryEvent] = []
    for edit_history_event in raw_edit_history:
        formatted_entry: FormattedEditHistoryEvent = {
            "content": prev_content,
            "rendered_content": prev_rendered_content,
            "timestamp": edit_history_event["timestamp"],
            "topic": prev_topic_name,
            "user_id": edit_history_event["user_id"],
        }

        if "prev_topic" in edit_history_event:
            prev_topic_name = edit_history_event["prev_topic"]
            formatted_entry["prev_topic"] = prev_topic_name

        # Fill current values for content/rendered_content.
        if "prev_content" in edit_history_event:
            formatted_entry["prev_content"] = edit_history_event["prev_content"]
            prev_content = formatted_entry["prev_content"]
            formatted_entry["prev_rendered_content"] = edit_history_event["prev_rendered_content"]
            prev_rendered_content = formatted_entry["prev_rendered_content"]
            assert prev_rendered_content is not None
            rendered_content = formatted_entry["rendered_content"]
            assert rendered_content is not None
            formatted_entry["content_html_diff"] = highlight_html_differences(
                prev_rendered_content, rendered_content, message.id
            )

        if "prev_stream" in edit_history_event:
            formatted_entry["prev_stream"] = edit_history_event["prev_stream"]
            formatted_entry["stream"] = edit_history_event["stream"]

        formatted_edit_history.append(formatted_entry)

    initial_message_history: FormattedEditHistoryEvent = {
        "content": prev_content,
        "rendered_content": prev_rendered_content,
        "timestamp": datetime_to_timestamp(message.date_sent),
        "topic": prev_topic_name,
        "user_id": message.sender_id,
    }

    formatted_edit_history.append(initial_message_history)

    return formatted_edit_history


@typed_endpoint
def get_message_edit_history(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: PathOnly[NonNegativeInt],
) -> HttpResponse:
    if not user_profile.realm.allow_edit_history:
        raise JsonableError(_("Message edit history is disabled in this organization"))
    message = access_message(user_profile, message_id)

    # Extract the message edit history from the message
    if message.edit_history is not None:
        raw_edit_history = orjson.loads(message.edit_history)
    else:
        raw_edit_history = []

    # Fill in all the extra data that will make it usable
    message_edit_history = fill_edit_history_entries(raw_edit_history, message)
    return json_success(request, data={"message_history": list(reversed(message_edit_history))})


@typed_endpoint
def update_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: PathOnly[NonNegativeInt],
    stream_id: Optional[Json[NonNegativeInt]] = None,
    topic_name: OptionalTopic = None,
    propagate_mode: Literal["change_later", "change_one", "change_all"] = "change_one",
    send_notification_to_old_thread: Json[bool] = False,
    send_notification_to_new_thread: Json[bool] = True,
    content: Optional[str] = None,
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
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = f"[{number_changed}]"

    return json_success(request)


def validate_can_delete_message(user_profile: UserProfile, message: Message) -> None:
    if user_profile.is_realm_admin:
        # Admin can delete any message, any time.
        return
    if message.sender != user_profile and message.sender.bot_owner_id != user_profile.id:
        # Users can only delete messages sent by them or by their bots.
        raise JsonableError(_("You don't have permission to delete this message"))
    if not user_profile.can_delete_own_message():
        # Only user with roles as allowed by delete_own_message_policy can delete message.
        raise JsonableError(_("You don't have permission to delete this message"))

    deadline_seconds: Optional[int] = user_profile.realm.message_content_delete_limit_seconds
    if deadline_seconds is None:
        # None means no time limit to delete message
        return
    if (timezone_now() - message.date_sent) > timedelta(seconds=deadline_seconds):
        # User cannot delete message after deadline time of realm
        raise JsonableError(_("The time limit for deleting this message has passed"))
    return


@transaction.atomic
@typed_endpoint
def delete_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: PathOnly[NonNegativeInt],
) -> HttpResponse:
    # We lock the `Message` object to ensure that any transactions modifying the `Message` object
    # concurrently are serialized properly with deleting the message; this prevents a deadlock
    # that would otherwise happen because of the other transaction holding a lock on the `Message`
    # row.
    message = access_message(user_profile, message_id, lock_message=True)
    validate_can_delete_message(user_profile, message)
    try:
        do_delete_messages(user_profile.realm, [message])
    except (Message.DoesNotExist, IntegrityError):
        raise JsonableError(_("Message already deleted"))
    return json_success(request)


@typed_endpoint
def json_fetch_raw_message(
    request: HttpRequest,
    maybe_user_profile: Union[UserProfile, AnonymousUser],
    *,
    message_id: PathOnly[NonNegativeInt],
    apply_markdown: Json[bool] = True,
) -> HttpResponse:
    if not maybe_user_profile.is_authenticated:
        realm = get_valid_realm_from_request(request)
        message = access_web_public_message(realm, message_id)
        user_profile = None
    else:
        (message, user_message) = access_message_and_usermessage(maybe_user_profile, message_id)
        user_profile = maybe_user_profile

    flags = ["read"]
    if not maybe_user_profile.is_authenticated:
        allow_edit_history = realm.allow_edit_history
    else:
        if user_message:
            flags = user_message.flags_list()
        else:
            flags = ["read", "historical"]
        allow_edit_history = maybe_user_profile.realm.allow_edit_history

    # Security note: It's important that we call this only with a
    # message already fetched via `access_message` type methods,
    # as we do above.
    message_dict_list = messages_for_ids(
        message_ids=[message.id],
        user_message_flags={message_id: flags},
        search_fields={},
        apply_markdown=apply_markdown,
        client_gravatar=True,
        allow_edit_history=allow_edit_history,
        user_profile=user_profile,
        realm=message.realm,
    )
    response = dict(
        message=message_dict_list[0],
        # raw_content is deprecated; we will need to wait until
        # clients have been fully migrated to using the modern API
        # before removing this, probably in 2023.
        raw_content=message.content,
    )
    return json_success(request, response)
