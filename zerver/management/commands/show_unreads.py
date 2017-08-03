from __future__ import absolute_import
from __future__ import print_function

import time
import ujson

from typing import Any, Callable, Dict, List, Set, Text

from argparse import ArgumentParser
from django.core.management.base import CommandError

from zerver.lib.management import ZulipBaseCommand
from zerver.models import (
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile
)

def get_unread_messages(user_profile):
    # type: (UserProfile) -> List[Dict[str, Any]]
    user_msgs = UserMessage.objects.filter(
        user_profile=user_profile,
        message__recipient__type=Recipient.STREAM
    ).extra(
        where=[UserMessage.where_unread()]
    ).values(
        'message_id',
        'message__subject',
        'message__recipient__type_id',
    ).order_by("message_id")

    result = [
        dict(
            message_id=row['message_id'],
            topic=row['message__subject'],
            stream_id=row['message__recipient__type_id'],
        )
        for row in list(user_msgs)]

    return result

def get_muted_streams(user_profile, stream_ids):
    # type: (UserProfile, Set[int]) -> Set[int]
    rows = Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type_id__in=stream_ids,
        in_home_view=False,
    ).values(
        'recipient__type_id'
    )
    muted_stream_ids = {
        row['recipient__type_id']
        for row in rows}

    return muted_stream_ids

def build_topic_mute_checker(user_profile):
    # type: (UserProfile) -> Callable[[int, Text], bool]
    rows = ujson.loads(user_profile.muted_topics)
    stream_names = {row[0] for row in rows}
    stream_dict = dict()
    for name in stream_names:
        stream_id = Stream.objects.get(
            name__iexact=name.strip(),
            realm_id=user_profile.realm_id,
        ).id
        stream_dict[name] = stream_id
    tups = set()
    for row in rows:
        stream_name = row[0]
        topic = row[1]
        stream_id = stream_dict[stream_name]
        tups.add((stream_id, topic))

    def is_muted(stream_id, topic):
        # type: (int, Text) -> bool
        return (stream_id, topic) in tups

    return is_muted

def show_all_unread(user_profile):
    # type: (UserProfile) -> None
    unreads = get_unread_messages(user_profile)

    stream_ids = {row['stream_id'] for row in unreads}

    muted_stream_ids = get_muted_streams(user_profile, stream_ids)

    is_topic_muted = build_topic_mute_checker(user_profile)

    for row in unreads:
        row['stream_muted'] = row['stream_id'] in muted_stream_ids
        row['topic_muted'] = is_topic_muted(row['stream_id'], row['topic'])
        row['before'] = row['message_id'] < user_profile.pointer

    for row in unreads:
        print(row)

def get_timing(message, f):
    # type: (str, Callable) -> None
    start = time.time()
    print(message)
    f()
    elapsed = time.time() - start
    print('elapsed time: %.03f\n' % (elapsed,))


def fix_unsubscribed(user_profile):
    # type: (UserProfile) -> None
    where_clause = '''
        INNER JOIN zerver_message ON (
            zerver_message.id = zerver_usermessage.message_id
        )
        INNER JOIN zerver_recipient ON (
            zerver_recipient.id = zerver_message.recipient_id
        )
        INNER JOIN zerver_subscription ON (
            zerver_subscription.user_profile_id = '%s' AND
            zerver_subscription.recipient_id = zerver_recipient.id
        )
        WHERE (
            zerver_usermessage.user_profile_id = %s AND
            zerver_recipient.type = 2 AND
            (zerver_usermessage.flags & 1) = 0 AND
            (NOT zerver_subscription.active)
        )
        ORDER BY zerver_message.id
    '''

    from django.db import connection

    cursor = connection.cursor()

    def execute(query):
        # type: (str) -> None
        cursor.execute(query, [user_profile.id, user_profile.id])

    def find():
        # type: () -> None
        query = '''
            SELECT
                zerver_usermessage.id
            FROM zerver_usermessage
        ''' + where_clause
        execute(query)
        rows = cursor.fetchall()
        print('rows found: %d' % (len(rows),))

    get_timing(
        'finding unread messages for non-active streams',
        find
    )

    fix_query = '''
        UPDATE zerver_usermessage
        SET flags = flags | 1
        WHERE id IN (
            SELECT zerver_usermessage.id
            FROM zerver_usermessage
    ''' + where_clause + ')'
    print(fix_query)

    def fix():
        # type: () -> None
        execute(fix_query)

    get_timing(
        'fixing unread messages for non-active streams',
        fix
    )

    cursor.close()

class Command(ZulipBaseCommand):
    help = """Troubleshoot/fix problems related to unread counts."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('email', metavar='<email>', type=str,
                            help='email address to spelunk')
        parser.add_argument('--fix',
                            action="store_true",
                            dest='fix',
                            default=False,
                            help='fix unread messsages for inactive streams')
        self.add_realm_args(parser)

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = self.get_realm(options)
        email = options['email']
        try:
            user_profile = self.get_user(email, realm)
        except CommandError:
            print("e-mail %s doesn't exist in the realm %s, skipping" % (email, realm))
            return

        if options['fix']:
            fix_unsubscribed(user_profile)
        else:
            show_all_unread(user_profile)
