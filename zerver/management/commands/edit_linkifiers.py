import sys
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError

from zerver.actions.realm_linkifiers import do_add_linkifier, do_remove_linkifier
from zerver.lib.management import ZulipBaseCommand
from zerver.models import linkifiers_for_realm


class Command(ZulipBaseCommand):
    help = """Create a link filter rule for the specified realm.

NOTE: Regexes must be simple enough that they can be easily translated to JavaScript
      RegExp syntax. In addition to JS-compatible syntax, the following features are available:

      * Named groups will be converted to numbered groups automatically
      * Inline-regex flags will be stripped, and where possible translated to RegExp-wide flags

Example: ./manage.py edit_linkifiers --realm=zulip --op=add '#(?P<id>[0-9]{2,8})' \
    'https://support.example.com/ticket/{id}'
Example: ./manage.py edit_linkifiers --realm=zulip --op=remove '#(?P<id>[0-9]{2,8})'
Example: ./manage.py edit_linkifiers --realm=zulip --op=show
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--op", default="show", help="What operation to do (add, show, remove)."
        )
        parser.add_argument(
            "pattern", metavar="<pattern>", nargs="?", help="regular expression to match"
        )
        parser.add_argument(
            "url_template",
            metavar="<URL template>",
            nargs="?",
            help="URL template to expand",
        )
        self.add_realm_args(parser, required=True)

    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser
        if options["op"] == "show":
            print(f"{realm.string_id}: {linkifiers_for_realm(realm.id)}")
            sys.exit(0)

        pattern = options["pattern"]
        if not pattern:
            self.print_help("./manage.py", "edit_linkifiers")
            raise CommandError

        if options["op"] == "add":
            url_template = options["url_template"]
            if not url_template:
                self.print_help("./manage.py", "edit_linkifiers")
                raise CommandError
            do_add_linkifier(realm, pattern, url_template, acting_user=None)
            sys.exit(0)
        elif options["op"] == "remove":
            do_remove_linkifier(realm, pattern=pattern, acting_user=None)
            sys.exit(0)
        else:
            self.print_help("./manage.py", "edit_linkifiers")
            raise CommandError
