from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import orjson
from django.db import connection
from django.db.models import F, Func, JSONField, Q, QuerySet, Subquery, TextField, Value
from django.db.models.functions import Cast

from zerver.lib.request import REQ
from zerver.lib.types import EditHistoryEvent
from zerver.lib.utils import assert_is_not_none
from zerver.models import Message, Reaction, Stream, UserMessage, UserProfile

# Only use these constants for events.
ORIG_TOPIC = "orig_subject"
TOPIC_NAME = "subject"
TOPIC_LINKS = "topic_links"
MATCH_TOPIC = "match_subject"

# Prefix use to mark topic as resolved.
RESOLVED_TOPIC_PREFIX = "✔ "

# This constant is pretty closely coupled to the
# database, but it's the JSON field.
EXPORT_TOPIC_NAME = "subject"

"""
The following functions are for user-facing APIs
where we'll want to support "subject" for a while.
"""


def get_topic_from_message_info(message_info: Dict[str, Any]) -> str:
    """
    Use this where you are getting dicts that are based off of messages
    that may come from the outside world, especially from third party
    APIs and bots.

    We prefer 'topic' to 'subject' here.  We expect at least one field
    to be present (or the caller must know how to handle KeyError).
    """
    if "topic" in message_info:
        return message_info["topic"]

    return message_info["subject"]


def REQ_topic() -> Optional[str]:
    # REQ handlers really return a REQ, but we
    # lie to make the rest of the type matching work.
    return REQ(
        whence="topic",
        aliases=["subject"],
        converter=lambda var_name, x: x.strip(),
        default=None,
    )


"""
TRY TO KEEP THIS DIVIDING LINE.

Below this line we want to make it so that functions are only
using "subject" in the DB sense, and nothing customer facing.

"""

# This is used in low-level message functions in
# zerver/lib/message.py, and it's not user facing.
DB_TOPIC_NAME = "subject"
MESSAGE__TOPIC = "message__subject"


def filter_by_topic_name_via_message(
    query: QuerySet[UserMessage], topic_name: str
) -> QuerySet[UserMessage]:
    return query.filter(message__subject__iexact=topic_name)


def messages_for_topic(
    realm_id: int, stream_recipient_id: int, topic_name: str
) -> QuerySet[Message]:
    return Message.objects.filter(
        # Uses index: zerver_message_realm_recipient_upper_subject
        realm_id=realm_id,
        recipient_id=stream_recipient_id,
        subject__iexact=topic_name,
    )


def save_message_for_edit_use_case(message: Message) -> None:
    message.save(
        update_fields=[
            TOPIC_NAME,
            "content",
            "rendered_content",
            "rendered_content_version",
            "last_edit_time",
            "edit_history",
            "has_attachment",
            "has_image",
            "has_link",
            "recipient_id",
        ]
    )


def user_message_exists_for_topic(
    user_profile: UserProfile, recipient_id: int, topic_name: str
) -> bool:
    return UserMessage.objects.filter(
        user_profile=user_profile,
        message__recipient_id=recipient_id,
        message__subject__iexact=topic_name,
    ).exists()


def update_edit_history(
    message: Message, last_edit_time: datetime, edit_history_event: EditHistoryEvent
) -> None:
    message.last_edit_time = last_edit_time
    if message.edit_history is not None:
        edit_history: List[EditHistoryEvent] = orjson.loads(message.edit_history)
        edit_history.insert(0, edit_history_event)
    else:
        edit_history = [edit_history_event]
    message.edit_history = orjson.dumps(edit_history).decode()


def update_messages_for_topic_edit(
    acting_user: UserProfile,
    edited_message: Message,
    propagate_mode: str,
    orig_topic_name: str,
    topic_name: Optional[str],
    new_stream: Optional[Stream],
    old_stream: Stream,
    edit_history_event: EditHistoryEvent,
    last_edit_time: datetime,
) -> Tuple[QuerySet[Message], Callable[[], QuerySet[Message]]]:
    # Uses index: zerver_message_realm_recipient_upper_subject
    messages = Message.objects.filter(
        realm_id=old_stream.realm_id,
        recipient_id=assert_is_not_none(old_stream.recipient_id),
        subject__iexact=orig_topic_name,
    )
    if propagate_mode == "change_all":
        messages = messages.exclude(id=edited_message.id)
    if propagate_mode == "change_later":
        messages = messages.filter(id__gt=edited_message.id)

    if new_stream is not None:
        # If we're moving the messages between streams, only move
        # messages that the acting user can access, so that one cannot
        # gain access to messages through moving them.
        from zerver.lib.message import bulk_access_stream_messages_query

        messages = bulk_access_stream_messages_query(acting_user, messages, old_stream)
    else:
        # For single-message edits or topic moves within a stream, we
        # allow moving history the user may not have access in order
        # to keep topics together.
        pass

    update_fields: Dict[str, object] = {
        "last_edit_time": last_edit_time,
        # We cast the `edit_history` column to jsonb (defaulting NULL
        # to `[]`), apply the `||` array concatenation operator to it,
        # and cast the result back to text.  See #26496 for making
        # this column itself jsonb, which is a complicated migration.
        #
        # This equates to:
        #    "edit_history" = (
        #      (COALESCE("zerver_message"."edit_history", '[]'))::jsonb
        #      ||
        #      ( '[{ ..json event.. }]' )::jsonb
        #     )::text
        "edit_history": Cast(
            Func(
                Cast(
                    Value(orjson.dumps([edit_history_event]).decode()),
                    JSONField(),
                ),
                Cast(
                    Func(
                        F("edit_history"),
                        Value("[]"),
                        function="COALESCE",
                    ),
                    JSONField(),
                ),
                function="",
                arg_joiner=" || ",
            ),
            TextField(),
        ),
    }
    if new_stream is not None:
        update_fields["recipient"] = new_stream.recipient
    if topic_name is not None:
        update_fields["subject"] = topic_name

    # The update will cause the 'messages' query to no longer match
    # any rows; we capture the set of matching ids first, do the
    # update, and then return a fresh collection -- so we know their
    # metadata has been updated for the UPDATE command, and the caller
    # can update the remote cache with that.
    message_ids = [edited_message.id, *messages.values_list("id", flat=True)]

    def propagate() -> QuerySet[Message]:
        messages.update(**update_fields)
        return Message.objects.filter(id__in=message_ids).select_related(
            *Message.DEFAULT_SELECT_RELATED
        )

    return messages, propagate


def generate_topic_history_from_db_rows(rows: List[Tuple[str, int]]) -> List[Dict[str, Any]]:
    canonical_topic_names: Dict[str, Tuple[int, str]] = {}

    # Sort rows by max_message_id so that if a topic
    # has many different casings, we use the most
    # recent row.
    rows = sorted(rows, key=lambda tup: tup[1])

    for topic_name, max_message_id in rows:
        canonical_name = topic_name.lower()
        canonical_topic_names[canonical_name] = (max_message_id, topic_name)

    history = []
    for max_message_id, topic_name in canonical_topic_names.values():
        history.append(
            dict(name=topic_name, max_id=max_message_id),
        )
    return sorted(history, key=lambda x: -x["max_id"])


def get_topic_history_for_public_stream(realm_id: int, recipient_id: int) -> List[Dict[str, Any]]:
    cursor = connection.cursor()
    # Uses index: zerver_message_realm_recipient_subject
    # Note that this is *case-sensitive*, so that we can display the
    # most recently-used case (in generate_topic_history_from_db_rows)
    query = """
    SELECT
        "zerver_message"."subject" as topic,
        max("zerver_message".id) as max_message_id
    FROM "zerver_message"
    WHERE (
        "zerver_message"."realm_id" = %s AND
        "zerver_message"."recipient_id" = %s
    )
    GROUP BY (
        "zerver_message"."subject"
    )
    ORDER BY max("zerver_message".id) DESC
    """
    cursor.execute(query, [realm_id, recipient_id])
    rows = cursor.fetchall()
    cursor.close()

    return generate_topic_history_from_db_rows(rows)


def get_topic_history_for_stream(
    user_profile: UserProfile, recipient_id: int, public_history: bool
) -> List[Dict[str, Any]]:
    if public_history:
        return get_topic_history_for_public_stream(user_profile.realm_id, recipient_id)

    cursor = connection.cursor()
    # Uses index: zerver_message_realm_recipient_subject
    # Note that this is *case-sensitive*, so that we can display the
    # most recently-used case (in generate_topic_history_from_db_rows)
    query = """
    SELECT
        "zerver_message"."subject" as topic,
        max("zerver_message".id) as max_message_id
    FROM "zerver_message"
    INNER JOIN "zerver_usermessage" ON (
        "zerver_usermessage"."message_id" = "zerver_message"."id"
    )
    WHERE (
        "zerver_usermessage"."user_profile_id" = %s AND
        "zerver_message"."realm_id" = %s AND
        "zerver_message"."recipient_id" = %s
    )
    GROUP BY (
        "zerver_message"."subject"
    )
    ORDER BY max("zerver_message".id) DESC
    """
    cursor.execute(query, [user_profile.id, user_profile.realm_id, recipient_id])
    rows = cursor.fetchall()
    cursor.close()

    return generate_topic_history_from_db_rows(rows)


def get_topic_resolution_and_bare_name(stored_name: str) -> Tuple[bool, str]:
    """
    Resolved topics are denoted only by a title change, not by a boolean toggle in a database column. This
    method inspects the topic name and returns a tuple of:

    - Whether the topic has been resolved
    - The topic name with the resolution prefix, if present in stored_name, removed
    """
    if stored_name.startswith(RESOLVED_TOPIC_PREFIX):
        return (True, stored_name[len(RESOLVED_TOPIC_PREFIX) :])

    return (False, stored_name)


def participants_for_topic(realm_id: int, recipient_id: int, topic_name: str) -> Set[int]:
    """
    Users who either sent or reacted to the messages in the topic.
    The function is expensive for large numbers of messages in the topic.
    """
    messages = Message.objects.filter(
        # Uses index: zerver_message_realm_recipient_upper_subject
        realm_id=realm_id,
        recipient_id=recipient_id,
        subject__iexact=topic_name,
    )
    participants = set(
        UserProfile.objects.filter(
            Q(id__in=Subquery(messages.values("sender_id")))
            | Q(
                id__in=Subquery(
                    Reaction.objects.filter(message__in=messages).values("user_profile_id")
                )
            )
        ).values_list("id", flat=True)
    )
    return participants
