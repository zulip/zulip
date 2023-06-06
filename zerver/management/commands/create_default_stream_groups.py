from argparse import ArgumentParser
from typing import Any

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.streams import ensure_stream
from zerver.models import DefaultStreamGroup


class Command(ZulipBaseCommand):
    help = """
Create default stream groups which the users can choose during sign up.

./manage.py create_default_stream_groups -s gsoc-1,gsoc-2,gsoc-3 -d "Google summer of code"  -r zulip
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True)

        parser.add_argument(
            "-n",
            "--name",
            required=True,
            help="Name of the group you want to create.",
        )

        parser.add_argument(
            "-d",
            "--description",
            required=True,
            help="Description of the group.",
        )

        parser.add_argument(
            "-s", "--streams", required=True, help="A comma-separated list of stream names."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        streams = []
        stream_names = {stream.strip() for stream in options["streams"].split(",")}
        for stream_name in stream_names:
            stream = ensure_stream(realm, stream_name, acting_user=None)
            streams.append(stream)

        try:
            default_stream_group = DefaultStreamGroup.objects.get(
                name=options["name"], realm=realm, description=options["description"]
            )
        except DefaultStreamGroup.DoesNotExist:
            default_stream_group = DefaultStreamGroup.objects.create(
                name=options["name"], realm=realm, description=options["description"]
            )
        default_stream_group.streams.set(streams)

        default_stream_groups = DefaultStreamGroup.objects.all()
        for default_stream_group in default_stream_groups:
            print(default_stream_group.name)
            print(default_stream_group.description)
            for stream in default_stream_group.streams.all():
                print(stream.name)
            print("")
