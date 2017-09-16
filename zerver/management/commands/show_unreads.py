from __future__ import absolute_import
from __future__ import print_function

import time
import ujson

from typing import Any, Callable, Dict, List, Set, Text

from argparse import ArgumentParser
from django.core.management.base import CommandError
from django.db import connection

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.topic_mutes import build_topic_mute_checker
from zerver.models import (
    Recipient,
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
        'message__recipient_id',
        'message__recipient__type_id',
    ).order_by("message_id")

    result = [
        dict(
            message_id=row['message_id'],
            topic=row['message__subject'],
            stream_id=row['message__recipient__type_id'],
            recipient_id=row['message__recipient_id'],
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

def show_all_unread(user_profile):
    # type: (UserProfile) -> None
    unreads = get_unread_messages(user_profile)

    stream_ids = {row['stream_id'] for row in unreads}

    muted_stream_ids = get_muted_streams(user_profile, stream_ids)

    is_topic_muted = build_topic_mute_checker(user_profile)

    for row in unreads:
        row['stream_muted'] = row['stream_id'] in muted_stream_ids
        row['topic_muted'] = is_topic_muted(row['recipient_id'], row['topic'])
        row['before'] = row['message_id'] < user_profile.pointer

    for row in unreads:
        print(row)

class Command(ZulipBaseCommand):
    help = """Show unread counts for a particular user."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('email', metavar='<email>', type=str,
                            help='email address to spelunk')
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

        show_all_unread(user_profile)
