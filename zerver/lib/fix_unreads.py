from __future__ import absolute_import
from __future__ import print_function

import time
import logging

from typing import Callable, List, TypeVar, Text
from psycopg2.extensions import cursor
CursorObj = TypeVar('CursorObj', bound=cursor)

from django.db import connection

from zerver.models import UserProfile

'''
NOTE!  Be careful modifying this library, as it is used
in a migration, and it needs to be valid for the state
of the database that is in place when the 0104_fix_unreads
migration runs.
'''

logger = logging.getLogger('zulip.fix_unreads')
logger.setLevel(logging.WARNING)

def build_topic_mute_checker(cursor, user_profile):
    # type: (CursorObj, UserProfile) -> Callable[[int, Text], bool]
    '''
    This function is similar to the function of the same name
    in zerver/lib/topic_mutes.py, but it works without the ORM,
    so that we can use it in migrations.
    '''
    query = '''
        SELECT
            recipient_id,
            topic_name
        FROM
            zerver_mutedtopic
        WHERE
            user_profile_id = %s
    '''
    cursor.execute(query, [user_profile.id])
    rows = cursor.fetchall()

    tups = {
        (recipient_id, topic_name.lower())
        for (recipient_id, topic_name) in rows
    }

    def is_muted(recipient_id, topic):
        # type: (int, Text) -> bool
        return (recipient_id, topic.lower()) in tups

    return is_muted

def update_unread_flags(cursor, user_message_ids):
    # type: (CursorObj, List[int]) -> None
    um_id_list = ', '.join(str(id) for id in user_message_ids)
    query = '''
        UPDATE zerver_usermessage
        SET flags = flags | 1
        WHERE id IN (%s)
    ''' % (um_id_list,)

    cursor.execute(query)


def get_timing(message, f):
    # type: (str, Callable) -> None
    start = time.time()
    logger.info(message)
    f()
    elapsed = time.time() - start
    logger.info('elapsed time: %.03f\n' % (elapsed,))


def fix_unsubscribed(cursor, user_profile):
    # type: (CursorObj, UserProfile) -> None

    recipient_ids = []

    def find_recipients():
        # type: () -> None
        query = '''
            SELECT
                zerver_subscription.recipient_id
            FROM
                zerver_subscription
            INNER JOIN zerver_recipient ON (
                zerver_recipient.id = zerver_subscription.recipient_id
            )
            WHERE (
                zerver_subscription.user_profile_id = '%s' AND
                zerver_recipient.type = 2 AND
                (NOT zerver_subscription.active)
            )
        '''
        cursor.execute(query, [user_profile.id])
        rows = cursor.fetchall()
        for row in rows:
            recipient_ids.append(row[0])
        logger.info(str(recipient_ids))

    get_timing(
        'get recipients',
        find_recipients
    )

    if not recipient_ids:
        return

    user_message_ids = []

    def find():
        # type: () -> None
        recips = ', '.join(str(id) for id in recipient_ids)

        query = '''
            SELECT
                zerver_usermessage.id
            FROM
                zerver_usermessage
            INNER JOIN zerver_message ON (
                zerver_message.id = zerver_usermessage.message_id
            )
            WHERE (
                zerver_usermessage.user_profile_id = %s AND
                (zerver_usermessage.flags & 1) = 0 AND
                zerver_message.recipient_id in (%s)
            )
        ''' % (user_profile.id, recips)

        logger.info('''
            EXPLAIN analyze''' + query.rstrip() + ';')

        cursor.execute(query)
        rows = cursor.fetchall()
        for row in rows:
            user_message_ids.append(row[0])
        logger.info('rows found: %d' % (len(user_message_ids),))

    get_timing(
        'finding unread messages for non-active streams',
        find
    )

    if not user_message_ids:
        return

    def fix():
        # type: () -> None
        update_unread_flags(cursor, user_message_ids)

    get_timing(
        'fixing unread messages for non-active streams',
        fix
    )

def fix_pre_pointer(cursor, user_profile):
    # type: (CursorObj, UserProfile) -> None

    pointer = user_profile.pointer

    if not pointer:
        return

    recipient_ids = []

    def find_non_muted_recipients():
        # type: () -> None
        query = '''
            SELECT
                zerver_subscription.recipient_id
            FROM
                zerver_subscription
            INNER JOIN zerver_recipient ON (
                zerver_recipient.id = zerver_subscription.recipient_id
            )
            WHERE (
                zerver_subscription.user_profile_id = '%s' AND
                zerver_recipient.type = 2 AND
                zerver_subscription.in_home_view AND
                zerver_subscription.active
            )
        '''
        cursor.execute(query, [user_profile.id])
        rows = cursor.fetchall()
        for row in rows:
            recipient_ids.append(row[0])
        logger.info(str(recipient_ids))

    get_timing(
        'find_non_muted_recipients',
        find_non_muted_recipients
    )

    if not recipient_ids:
        return

    user_message_ids = []

    def find_old_ids():
        # type: () -> None
        recips = ', '.join(str(id) for id in recipient_ids)

        is_topic_muted = build_topic_mute_checker(cursor, user_profile)

        query = '''
            SELECT
                zerver_usermessage.id,
                zerver_message.recipient_id,
                zerver_message.subject
            FROM
                zerver_usermessage
            INNER JOIN zerver_message ON (
                zerver_message.id = zerver_usermessage.message_id
            )
            WHERE (
                zerver_usermessage.user_profile_id = %s AND
                zerver_usermessage.message_id <= %s AND
                (zerver_usermessage.flags & 1) = 0 AND
                zerver_message.recipient_id in (%s)
            )
        ''' % (user_profile.id, pointer, recips)

        logger.info('''
            EXPLAIN analyze''' + query.rstrip() + ';')

        cursor.execute(query)
        rows = cursor.fetchall()
        for (um_id, recipient_id, topic) in rows:
            if not is_topic_muted(recipient_id, topic):
                user_message_ids.append(um_id)
        logger.info('rows found: %d' % (len(user_message_ids),))

    get_timing(
        'finding pre-pointer messages that are not muted',
        find_old_ids
    )

    if not user_message_ids:
        return

    def fix():
        # type: () -> None
        update_unread_flags(cursor, user_message_ids)

    get_timing(
        'fixing unread messages for pre-pointer non-muted messages',
        fix
    )

def fix(user_profile):
    # type: (UserProfile) -> None
    logger.info('\n---\nFixing %s:' % (user_profile.email,))
    with connection.cursor() as cursor:
        fix_unsubscribed(cursor, user_profile)
        fix_pre_pointer(cursor, user_profile)
