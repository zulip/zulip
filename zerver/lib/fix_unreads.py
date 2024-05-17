import logging
import time
from typing import Callable, List, TypeVar

from django.db import connection
from django.db.backends.utils import CursorWrapper
from psycopg2.sql import SQL

from zerver.models import UserProfile

T = TypeVar("T")

"""
NOTE!  Be careful modifying this library, as it is used
in a migration, and it needs to be valid for the state
of the database that is in place when the 0104_fix_unreads
migration runs.
"""

logger = logging.getLogger("zulip.fix_unreads")
logger.setLevel(logging.WARNING)


def update_unread_flags(cursor: CursorWrapper, user_message_ids: List[int]) -> None:
    query = SQL(
        """
        UPDATE zerver_usermessage
        SET flags = flags | 1
        WHERE id IN %(user_message_ids)s
    """
    )

    cursor.execute(query, {"user_message_ids": tuple(user_message_ids)})


def get_timing(message: str, f: Callable[[], T]) -> T:
    start = time.time()
    logger.info(message)
    ret = f()
    elapsed = time.time() - start
    logger.info("elapsed time: %.03f\n", elapsed)
    return ret


def fix_unsubscribed(cursor: CursorWrapper, user_profile: UserProfile) -> None:
    def find_recipients() -> List[int]:
        query = SQL(
            """
            SELECT
                zerver_subscription.recipient_id
            FROM
                zerver_subscription
            INNER JOIN zerver_recipient ON (
                zerver_recipient.id = zerver_subscription.recipient_id
            )
            WHERE (
                zerver_subscription.user_profile_id = %(user_profile_id)s AND
                zerver_recipient.type = 2 AND
                (NOT zerver_subscription.active)
            )
        """
        )
        cursor.execute(query, {"user_profile_id": user_profile.id})
        rows = cursor.fetchall()
        recipient_ids = [row[0] for row in rows]
        logger.info("%s", recipient_ids)
        return recipient_ids

    recipient_ids = get_timing(
        "get recipients",
        find_recipients,
    )

    if not recipient_ids:
        return

    def find() -> List[int]:
        query = SQL(
            """
            SELECT
                zerver_usermessage.id
            FROM
                zerver_usermessage
            INNER JOIN zerver_message ON (
                zerver_message.id = zerver_usermessage.message_id
            )
            WHERE (
                zerver_usermessage.user_profile_id = %(user_profile_id)s AND
                (zerver_usermessage.flags & 1) = 0 AND
                zerver_message.recipient_id in %(recipient_ids)s
            )
        """
        )

        cursor.execute(
            query,
            {
                "user_profile_id": user_profile.id,
                "recipient_ids": tuple(recipient_ids),
            },
        )
        rows = cursor.fetchall()
        user_message_ids = [row[0] for row in rows]
        logger.info("rows found: %d", len(user_message_ids))
        return user_message_ids

    user_message_ids = get_timing(
        "finding unread messages for non-active streams",
        find,
    )

    if not user_message_ids:
        return

    def fix() -> None:
        update_unread_flags(cursor, user_message_ids)

    get_timing(
        "fixing unread messages for non-active streams",
        fix,
    )


def fix(user_profile: UserProfile) -> None:
    logger.info("\n---\nFixing %s:", user_profile.id)
    with connection.cursor() as cursor:
        fix_unsubscribed(cursor, user_profile)
