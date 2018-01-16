
import sys
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import Any

from django.core.management.base import CommandParser

from zerver.lib.actions import check_add_realm_emoji, do_remove_realm_emoji
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Manage emoji for the specified realm

Example: ./manage.py realm_emoji --realm=zulip.com --op=add robotheart \\
    https://humbug-user-avatars.s3.amazonaws.com/95ffa70fe0e7aea3c052ba91b38a28d8779f5705
Example: ./manage.py realm_emoji --realm=zulip.com --op=remove robotheart
Example: ./manage.py realm_emoji --realm=zulip.com --op=show
"""

    # Fix support for multi-line usage
    def create_parser(self, *args: Any, **kwargs: Any) -> CommandParser:
        parser = super().create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--op',
                            dest='op',
                            type=str,
                            default="show",
                            help='What operation to do (add, show, remove).')
        parser.add_argument('name', metavar='<name>', type=str, nargs='?', default=None,
                            help="name of the emoji")
        parser.add_argument('img_url', metavar='<image url>', type=str, nargs='?',
                            help="URL of image to display for the emoji")
        self.add_realm_args(parser, True)

    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser
        if options["op"] == "show":
            for name, url in realm.get_emoji().items():
                print(name, url)
            sys.exit(0)

        name = options['name']
        if name is None:
            self.print_help("./manage.py", "realm_emoji")
            sys.exit(1)

        if options["op"] == "add":
            img_url = options['img_url']
            if img_url is None:
                self.print_help("./manage.py", "realm_emoji")
                sys.exit(1)
            check_add_realm_emoji(realm, name, img_url)
            sys.exit(0)
        elif options["op"] == "remove":
            do_remove_realm_emoji(realm, name)
            sys.exit(0)
        else:
            self.print_help("./manage.py", "realm_emoji")
            sys.exit(1)
