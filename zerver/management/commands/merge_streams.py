from argparse import ArgumentParser
from typing import Any

from typing_extensions import override

from zerver.actions.streams import merge_streams
from zerver.lib.management import ZulipBaseCommand
from zerver.models.streams import get_stream


class Command(ZulipBaseCommand):
    help = """Merge two streams."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("stream_to_keep", help="name of stream to keep")
        parser.add_argument(
            "stream_to_destroy", help="name of stream to merge into the stream being kept"
        )
        self.add_realm_args(parser, required=True)

    @override
    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser
        stream_to_keep = get_stream(options["stream_to_keep"], realm)
        stream_to_destroy = get_stream(options["stream_to_destroy"], realm)
        stats = merge_streams(realm, stream_to_keep, stream_to_destroy)
        print(f"Added {stats[0]} subscriptions")
        print(f"Moved {stats[1]} messages")
        print(f"Deactivated {stats[2]} subscriptions")
