from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from zerver.models import Message, Realm, Recipient, Stream, Subscription, get_realm


class Command(BaseCommand):
    help = "Generate statistics on the streams for a realm."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('realms', metavar='<realm>', nargs='*',
                            help="realm to generate statistics for")

    def handle(self, *args: Any, **options: str) -> None:
        if options['realms']:
            try:
                realms = [get_realm(string_id) for string_id in options['realms']]
            except Realm.DoesNotExist as e:
                raise CommandError(e)
        else:
            realms = Realm.objects.all()

        for realm in realms:
            streams = Stream.objects.filter(realm=realm).exclude(Q(name__istartswith="tutorial-"))
            # private stream count
            private_count = 0
            # public stream count
            public_count = 0
            for stream in streams:
                if stream.invite_only:
                    private_count += 1
                else:
                    public_count += 1
            print("------------")
            print(realm.string_id, end=' ')
            print("{:>10} {} public streams and".format("(", public_count), end=' ')
            print(f"{private_count} private streams )")
            print("------------")
            print("{:>25} {:>15} {:>10} {:>12}".format("stream", "subscribers", "messages", "type"))

            for stream in streams:
                if stream.invite_only:
                    stream_type = 'private'
                else:
                    stream_type = 'public'
                print(f"{stream.name:>25}", end=' ')
                recipient = Recipient.objects.filter(type=Recipient.STREAM, type_id=stream.id)
                print("{:10}".format(len(Subscription.objects.filter(recipient=recipient,
                                                                     active=True))), end=' ')
                num_messages = len(Message.objects.filter(recipient=recipient))
                print(f"{num_messages:12}", end=' ')
                print(f"{stream_type:>15}")
            print("")
