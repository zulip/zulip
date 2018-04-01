from argparse import ArgumentParser
from typing import Any

from zerver.lib.export import do_export_user_tarball
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Exports message data from a Zulip user

    This command exports the message history for a single Zulip user.

    Note that this only exports the user's message history and
    realm-public metadata needed to understand it; it does nothing
    with (for example) any bots owned by the user."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('email', metavar='<email>', type=str,
                            help="email of user to export")
        parser.add_argument('--output',
                            dest='output_dir',
                            action="store",
                            default=None,
                            help='Directory to write exported data to.')
        self.add_realm_args(parser)

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        user_profile = self.get_user(options["email"], realm)
        do_export_user_tarball(user_profile)
