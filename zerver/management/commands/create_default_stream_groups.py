
from argparse import ArgumentParser
from typing import Any

from zerver.lib.actions import create_stream_if_needed
from zerver.lib.management import ZulipBaseCommand
from zerver.models import DefaultStreamGroup

class Command(ZulipBaseCommand):
    help = """
Create default stream groups which the users can choose during sign up.

./manage.py create_default_stream_groups -s gsoc-1,gsoc-2,gsoc-3 -d "Google summer of code"  -r zulip
"""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        self.add_realm_args(parser, True)

        parser.add_argument(
            '-s', '--streams',
            dest='streams',
            type=str,
            required=True,
            help='A comma-separated list of stream names.')

        parser.add_argument(
            '-d', '--default-stream-group',
            dest='default_stream_group',
            type=str,
            required=True,
            help='Name of the group you want to create.'
        )

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        streams = []
        stream_names = set([stream.strip() for stream in options["streams"].split(",")])
        for stream_name in set(stream_names):
            stream, _ = create_stream_if_needed(realm, stream_name)
            streams.append(stream)

        try:
            default_stream_group = DefaultStreamGroup.objects.get(
                name=options["default_stream_group"], realm=realm)
        except DefaultStreamGroup.DoesNotExist:
            default_stream_group = DefaultStreamGroup.objects.create(
                name=options["default_stream_group"], realm=realm)
        default_stream_group.streams = streams
        default_stream_group.save()

        default_stream_groups = DefaultStreamGroup.objects.all()
        for default_stream_group in default_stream_groups:
            print(default_stream_group.name)
            for stream in default_stream_group.streams.all():
                print(stream.name)
