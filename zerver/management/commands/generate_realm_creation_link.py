from typing import Any

from django.core.management.base import CommandError
from django.db import ProgrammingError
from typing_extensions import override

from confirmation.models import generate_realm_creation_url
from zerver.lib.management import ZulipBaseCommand
from zerver.models import Realm


class Command(ZulipBaseCommand):
    help = """
    Outputs a randomly generated, 1-time-use link for Organization creation.
    Whoever visits the link can create a new organization on this server, regardless of whether
    settings.OPEN_REALM_CREATION is enabled. The link would expire automatically after
    settings.REALM_CREATION_LINK_VALIDITY_DAYS.

    Usage: ./manage.py generate_realm_creation_link """

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        try:
            # first check if the db has been initialized
            Realm.objects.first()
        except ProgrammingError:
            raise CommandError(
                "The Zulip database does not appear to exist. Have you run initialize-database?"
            )

        url = generate_realm_creation_url(by_admin=True)
        self.stdout.write(
            self.style.SUCCESS(
                "Please visit the following secure single-use link to register your "
            )
        )
        self.stdout.write(self.style.SUCCESS("new Zulip organization:\033[0m"))
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"    \033[1;92m{url}\033[0m"))
        self.stdout.write("")
