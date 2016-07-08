from __future__ import absolute_import
from __future__ import print_function

from typing import Any
from django.conf import settings
from django.core.management.base import BaseCommand
from confirmation.models import generate_realm_creation_url

class Command(BaseCommand):
    help = """Outputs a randomly generated, 1-time-use link for Organization creation.
    Whoever visits the link can create a new organization on this server, regardless of whether
    settings.OPEN_REALM_CREATION is enabled. The link would expire automatically after
    settings.REALM_CREATION_LINK_VALIDITY_DAYS.

    Usage: python manage.py generate_realm_creation_link """

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        url = generate_realm_creation_url()
        self.stdout.write("\033[1;92mOne time organization creation link generated\033[0m")
        self.stdout.write("\033[1;92m=> Please visit \033[4m%s\033[0m \033[1;92mto "
                          "create the organization\033[0m" % (url))
