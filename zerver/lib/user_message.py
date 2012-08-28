from django.db import connection
from psycopg2.extras import execute_values
from psycopg2.sql import SQL, Composable, Literal

from zerver.models import UserMessage


class UserMessageLite:
    """
    The Django ORM is too slow for bulk operations.  This class
    is optimized for the simple use case of inserting a bunch of
    rows into zerver_usermessage.
    """

    def __init__(self, user_profile_id: int, message_id: int, flags: int) -> None:
        self.user_profile_id = user_profile_id
        self.message_id = message_id
        self.flags = flags

    def flags_list(self) -> list[str]:
        return UserMessage.flags_list_for_flags(self.flags)


DEFAULT_HISTORICAL_FLAGS = UserMessage.flags.historical | UserMessage.flags.read


def create_historical_user_messages(
    *,
    user_id: int,
    message_ids: list[int],
    flagattr: int | None = None,
    flag_target: int | None = None,
) -> None:
    # Users can see and interact with messages sent to streams with
    # public history for which they do not have a UserMessage because
    # they were not a subscriber at the time the message was sent.
    # In order to add emoji reactions or mutate message flags for
    # those messages, we create UserMessage objects for those messages;
    # these have the special historical flag which keeps track of the
    # fact that the user did not receive the message at the time it was sent.
    if flagattr is not None and flag_target is not None:
        conflict = SQL(
            "(user_profile_id, message_id) DO UPDATE SET flags = excluded.flags & ~ {mask} | {attr}"
        ).format(mask=Literal(flagattr), attr=Literal(flag_target))
        flags = (DEFAULT_HISTORICAL_FLAGS & ~flagattr) | flag_target
    else:
        conflict = None
        flags = DEFAULT_HISTORICAL_FLAGS
    bulk_insert_all_ums([user_id], message_ids, flags, conflict)


def bulk_insert_ums(ums: list[UserMessageLite]) -> None:
    """
    Doing bulk inserts this way is much faster than using Django,
    since we don't have any ORM overhead.  Profiling with 1000
    users shows a speedup of 0.436 -> 0.027 seconds, so we're
    talking about a 15x speedup.
    """
    if not ums:
        return

    vals = [(um.user_profile_id, um.message_id, um.flags) for um in ums]
    query = SQL(
        """
        INSERT into
            zerver_usermessage (user_profile_id, message_id, flags)
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    )

    with connection.cursor() as cursor:
        execute_values(cursor.cursor, query, vals)


def bulk_insert_all_ums(
    user_ids: list[int], message_ids: list[int], flags: int, conflict: Composable | None = None
) -> None:
    if not user_ids or not message_ids:
        return

    query = SQL(
        """
        INSERT INTO zerver_usermessage (user_profile_id, message_id, flags)
        SELECT user_profile_id, message_id, %s AS flags
          FROM UNNEST(%s) user_profile_id
          CROSS JOIN UNNEST(%s) message_id
        ON CONFLICT {conflict}
        """
    ).format(conflict=conflict if conflict is not None else SQL("DO NOTHING"))

    with connection.cursor() as cursor:
        cursor.execute(query, [flags, user_ids, message_ids])
