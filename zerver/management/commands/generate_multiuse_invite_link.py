from argparse import ArgumentParser
from typing import Any, List

from zerver.lib.actions import do_create_multiuse_invite_link, ensure_stream
from zerver.lib.management import ZulipBaseCommand
from zerver.models import PreregistrationUser, Stream


class Command(ZulipBaseCommand):
    help = "Generates invite link that can be used for inviting multiple users"

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, True)

        parser.add_argument(
            '-s', '--streams',
            help='A comma-separated list of stream names.')

        parser.add_argument(
            '--referred-by',
            help='Email of referrer',
            required=True,
        )

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        streams: List[Stream] = []
        if options["streams"]:
            stream_names = {stream.strip() for stream in options["streams"].split(",")}
            for stream_name in set(stream_names):
                stream = ensure_stream(realm, stream_name, acting_user=None)
                streams.append(stream)

        referred_by = self.get_user(options['referred_by'], realm)
        invite_as = PreregistrationUser.INVITE_AS['MEMBER']
        invite_link = do_create_multiuse_invite_link(referred_by, invite_as, streams)
        print(f"You can use {invite_link} to invite as many number of people to the organization.")
