import datetime

from django.db import connection
from django.db.models.query import QuerySet, Q
from django.utils.timezone import now as timezone_now

from sqlalchemy.sql import (
    column,
    literal,
    func,
)

from zerver.lib.request import REQ
from zerver.models import (
    Message,
    Recipient,
    UserMessage,
    UserProfile,
)

from typing import Any, Dict, List, Optional, Tuple

# Only use these constants for events.
ORIG_TOPIC = "orig_subject"
TOPIC_NAME = "subject"
TOPIC_LINKS = "subject_links"
MATCH_TOPIC = "match_subject"

# This constant is actually embedded into
# the JSON data for message edit history,
# so we'll always need to handle legacy data
# unless we do a pretty tricky migration.
LEGACY_PREV_TOPIC = "prev_subject"

# This constant is pretty closely coupled to the
# database, but it's the JSON field.
EXPORT_TOPIC_NAME = "subject"

'''
The following functions are for user-facing APIs
where we'll want to support "subject" for a while.
'''

def get_topic_from_message_info(message_info: Dict[str, Any]) -> str:
    '''
    Use this where you are getting dicts that are based off of messages
    that may come from the outside world, especially from third party
    APIs and bots.

    We prefer 'topic' to 'subject' here.  We expect at least one field
    to be present (or the caller must know how to handle KeyError).
    '''
    if 'topic' in message_info:
        return message_info['topic']

    return message_info['subject']

def REQ_topic() -> Optional[str]:
    # REQ handlers really return a REQ, but we
    # lie to make the rest of the type matching work.
    return REQ(
        whence='topic',
        aliases=['subject'],
        converter=lambda x: x.strip(),
        default=None,
    )  # type: ignore # see comment above

'''
TRY TO KEEP THIS DIVIDING LINE.

Below this line we want to make it so that functions are only
using "subject" in the DB sense, and nothing customer facing.

'''

# This is used in low-level message functions in
# zerver/lib/message.py, and it's not user facing.
DB_TOPIC_NAME = "subject"
MESSAGE__TOPIC = 'message__subject'

def topic_match_sa(topic_name: str) -> Any:
    # _sa is short for Sql Alchemy, which we use mostly for
    # queries that search messages
    topic_cond = func.upper(column("subject")) == func.upper(literal(topic_name))
    return topic_cond

def topic_column_sa() -> Any:
    return column("subject")

def filter_by_exact_message_topic(query: QuerySet, message: Message) -> QuerySet:
    topic_name = message.topic_name()
    return query.filter(subject=topic_name)

def filter_by_topic_name_via_message(query: QuerySet, topic_name: str) -> QuerySet:
    return query.filter(message__subject__iexact=topic_name)

def messages_for_topic(stream_id: int, topic_name: str) -> QuerySet:
    return Message.objects.filter(
        recipient__type_id=stream_id,
        subject__iexact=topic_name,
    )

def save_message_for_edit_use_case(message: Message) -> None:
    message.save(update_fields=["subject", "content", "rendered_content",
                                "rendered_content_version", "last_edit_time",
                                "edit_history"])

def user_message_exists_for_topic(user_profile: UserProfile,
                                  recipient: Recipient,
                                  topic_name: str) -> bool:
    return UserMessage.objects.filter(
        user_profile=user_profile,
        message__recipient=recipient,
        message__subject__iexact=topic_name,
    ).exists()

def update_messages_for_topic_edit(message: Message,
                                   propagate_mode: str,
                                   orig_topic_name: str,
                                   topic_name: str) -> List[Message]:
    propagate_query = Q(recipient = message.recipient, subject = orig_topic_name)
    # We only change messages up to 2 days in the past, to avoid hammering our
    # DB by changing an unbounded amount of messages
    if propagate_mode == 'change_all':
        before_bound = timezone_now() - datetime.timedelta(days=2)

        propagate_query = (propagate_query & ~Q(id = message.id) &
                           Q(pub_date__range=(before_bound, timezone_now())))
    if propagate_mode == 'change_later':
        propagate_query = propagate_query & Q(id__gt = message.id)

    messages = Message.objects.filter(propagate_query).select_related()

    # Evaluate the query before running the update
    messages_list = list(messages)
    messages.update(subject=topic_name)

    for m in messages_list:
        # The cached ORM object is not changed by messages.update()
        # and the remote cache update requires the new value
        m.set_topic_name(topic_name)

    return messages_list

def generate_topic_history_from_db_rows(rows: List[Tuple[str, int]]) -> List[Dict[str, Any]]:
    canonical_topic_names = {}  # type: Dict[str, Tuple[int, str]]

    # Sort rows by max_message_id so that if a topic
    # has many different casings, we use the most
    # recent row.
    rows = sorted(rows, key=lambda tup: tup[1])

    for (topic_name, max_message_id) in rows:
        canonical_name = topic_name.lower()
        canonical_topic_names[canonical_name] = (max_message_id, topic_name)

    history = []
    for canonical_topic, (max_message_id, topic_name) in canonical_topic_names.items():
        history.append(dict(
            name=topic_name,
            max_id=max_message_id)
        )
    return sorted(history, key=lambda x: -x['max_id'])

def get_topic_history_for_stream(user_profile: UserProfile,
                                 recipient: Recipient,
                                 public_history: bool) -> List[Dict[str, Any]]:
    cursor = connection.cursor()
    if public_history:
        query = '''
        SELECT
            "zerver_message"."subject" as topic,
            max("zerver_message".id) as max_message_id
        FROM "zerver_message"
        WHERE (
            "zerver_message"."recipient_id" = %s
        )
        GROUP BY (
            "zerver_message"."subject"
        )
        ORDER BY max("zerver_message".id) DESC
        '''
        cursor.execute(query, [recipient.id])
    else:
        query = '''
        SELECT
            "zerver_message"."subject" as topic,
            max("zerver_message".id) as max_message_id
        FROM "zerver_message"
        INNER JOIN "zerver_usermessage" ON (
            "zerver_usermessage"."message_id" = "zerver_message"."id"
        )
        WHERE (
            "zerver_usermessage"."user_profile_id" = %s AND
            "zerver_message"."recipient_id" = %s
        )
        GROUP BY (
            "zerver_message"."subject"
        )
        ORDER BY max("zerver_message".id) DESC
        '''
        cursor.execute(query, [user_profile.id, recipient.id])
    rows = cursor.fetchall()
    cursor.close()

    return generate_topic_history_from_db_rows(rows)

def get_topic_history_for_web_public_stream(recipient: Recipient) -> List[Dict[str, Any]]:
    cursor = connection.cursor()
    query = '''
    SELECT
        "zerver_message"."subject" as topic,
        max("zerver_message".id) as max_message_id
    FROM "zerver_message"
    WHERE (
        "zerver_message"."recipient_id" = %s
    )
    GROUP BY (
        "zerver_message"."subject"
    )
    ORDER BY max("zerver_message".id) DESC
    '''
    cursor.execute(query, [recipient.id])
    rows = cursor.fetchall()
    cursor.close()

    return generate_topic_history_from_db_rows(rows)

def get_turtle_message(message_ids: List[int]) -> Message:
    # This is used for onboarding, and it's only extracted
    # here to make subject -> topic sweeping easier.
    turtle_message = Message.objects.get(  # nolint
        id__in=message_ids,
        subject='topic demonstration',
        content__icontains='cute/turtle.png')
    return turtle_message
