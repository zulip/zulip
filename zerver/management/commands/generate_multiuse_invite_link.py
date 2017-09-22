from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from confirmation.models import Confirmation, create_confirmation_link
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.actions import create_stream_if_needed
from zerver.models import MultiuseInvite

class Command(ZulipBaseCommand):
    help = "Generates invite link that can be used for inviting multiple users"

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        self.add_realm_args(parser, True)

        parser.add_argument(
            '-s', '--streams',
            dest='streams',
            type=str,
            help='A comma-separated list of stream names.')

        parser.add_argument(
            '--referred-by',
            dest='referred_by',
            type=str,
            help='Email of referrer',
            required=True,
        )

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        realm = self.get_realm(options)

        streams = []
        if options["streams"]:
            stream_names = set([stream.strip() for stream in options["streams"].split(",")])

            for stream_name in set(stream_names):
                stream, _ = create_stream_if_needed(realm, stream_name)
                streams.append(stream)

        referred_by = self.get_user(options['referred_by'], realm)
        invite = MultiuseInvite.objects.create(realm=realm, referred_by=referred_by)

        if streams:
            invite.streams = streams
            invite.save()

        invite_link = create_confirmation_link(invite, realm.host, Confirmation.MULTIUSE_INVITE)
        print("You can use %s to invite as many number of people to the organization." % (invite_link,))
