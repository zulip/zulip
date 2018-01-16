from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Q

from zerver.models import Message, Realm, \
    Recipient, Stream, Subscription, get_realm

class Command(BaseCommand):
    help = "Generate statistics on the streams for a realm."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('realms', metavar='<realm>', type=str, nargs='*',
                            help="realm to generate statistics for")

    def handle(self, *args: Any, **options: str) -> None:
        if options['realms']:
            try:
                realms = [get_realm(string_id) for string_id in options['realms']]
            except Realm.DoesNotExist as e:
                print(e)
                exit(1)
        else:
            realms = Realm.objects.all()

        for realm in realms:
            print(realm.string_id)
            print("------------")
            print("%25s %15s %10s" % ("stream", "subscribers", "messages"))
            streams = Stream.objects.filter(realm=realm).exclude(Q(name__istartswith="tutorial-"))
            invite_only_count = 0
            for stream in streams:
                if stream.invite_only:
                    invite_only_count += 1
                    continue
                print("%25s" % (stream.name,), end=' ')
                recipient = Recipient.objects.filter(type=Recipient.STREAM, type_id=stream.id)
                print("%10d" % (len(Subscription.objects.filter(recipient=recipient,
                                                                active=True)),), end=' ')
                num_messages = len(Message.objects.filter(recipient=recipient))
                print("%12d" % (num_messages,))
            print("%d invite-only streams" % (invite_only_count,))
            print("")
