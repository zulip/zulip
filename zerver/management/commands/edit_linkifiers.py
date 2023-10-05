import sys
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError

from zerver.actions.realm_linkifiers import do_add_linkifier, do_remove_linkifier
from zerver.lib.management import ZulipBaseCommand
from zerver.models import linkifiers_for_realm


class Command(ZulipBaseCommand):
    """Create a link filter rule for the specified realm.

    NOTE: Regexes must be simple enough that they can be easily translated to JavaScript
    RegExp syntax. In addition to JS-compatible syntax, the following features are
    available:

    * Named groups will be converted to numbered groups automatically
    * Inline-regex flags will be stripped, and where possible translated to RegExp-
    wide flags

    Example: ./manage.py edit_linkifiers --realm=zulip --op=add '#(?P<id>[0-9]{2,8})' \
        'https://support.example.com/ticket/{id}'
    Example: ./manage.py edit_linkifiers --realm=zulip --op=remove '#(?P<id>[0-9]{2,8})'
    Example: ./manage.py edit_linkifiers --realm=zulip --op=show
    """
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
        """
        Add command line arguments.

        Args:
            parser (ArgumentParser): The argument parser for the command.
        """
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
        """
        Handle the command with the given arguments and options.

        This function is responsible for handling the 'handle' command. It takes in
        arguments '*args' and '**options' and has a return type of 'None'. It
        first assigns the value of 'realm' by calling the 'get_realm' function
        with the 'options' argument. Then it checks if the value of
        'options'['op'] is equal to 'show'. If true, it prints the string
        representation of 'realm.string_id' concatenated with the result of the
        'linkifiers_for_realm' function called with the argument 'realm.id'. If
        false, it checks if the value of 'pattern' is empty. If true, it calls the
        'print_help' function with the arguments './manage.py' and
        'edit_linkifiers', and raises a 'CommandError'.
        If false, it checks if the value of 'options'['op'] is equal to 'add'. If true,
        it assigns the value of 'url_template' by getting the value of
        'options'['url_template']. If the value of 'url_template' is empty, it
        calls the 'print_help' function with the arguments './manage.py' and
        'edit_linkifiers', and raises a 'CommandError'. Then it calls the
        'do_add_linkifier' function with the arguments 'realm', 'pattern',
        'url_template', and 'acting_user=None'. If false, it checks if the value
        of 'options'['op'] is equal to 'remove'.
        If true, it calls the 'do_remove_linkifier' function with the arguments 'realm'
        and 'pattern=pattern'.
        If false, it calls the 'print_help' function with the arguments './manage.py'
        and 'edit_linkifiers', and raises a 'CommandError'.
        """
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
