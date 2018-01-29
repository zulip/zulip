
import sys
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import Any

from django.core.management.base import BaseCommand
from django.db import ProgrammingError

from confirmation.models import generate_realm_creation_url
from zerver.models import Realm

class Command(BaseCommand):
    help = """
    Outputs a randomly generated, 1-time-use link for Organization creation.
    Whoever visits the link can create a new organization on this server, regardless of whether
    settings.OPEN_REALM_CREATION is enabled. The link would expire automatically after
    settings.REALM_CREATION_LINK_VALIDITY_DAYS.

    Usage: ./manage.py generate_realm_creation_link """

    # Fix support for multi-line usage
    def create_parser(self, *args: Any, **kwargs: Any) -> ArgumentParser:
        parser = super().create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            # first check if the db has been initalized
            Realm.objects.first()
        except ProgrammingError:
            print("The Zulip database does not appear to exist. Have you run initialize-database?")
            sys.exit(1)

        url = generate_realm_creation_url(by_admin=True)
        self.stdout.write(self.style.SUCCESS("Please visit the following "
                                             "secure single-use link to register your "))
        self.stdout.write(self.style.SUCCESS("new Zulip organization:\033[0m"))
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("    \033[1;92m%s\033[0m" % (url,)))
        self.stdout.write("")
