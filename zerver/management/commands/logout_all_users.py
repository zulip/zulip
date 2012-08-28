from argparse import ArgumentParser
from typing import Any

from django.db.models import Q
from typing_extensions import override

from zerver.actions.user_settings import bulk_regenerate_api_keys
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.sessions import (
    delete_all_deactivated_user_sessions,
    delete_all_user_sessions,
    delete_realm_user_sessions,
)
from zerver.models import UserProfile


class Command(ZulipBaseCommand):
    help = """\
Log out all users from active browser sessions.

Does not disable API keys, and thus will not log users out of the
mobile apps.
"""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--deactivated-only",
            action="store_true",
            help="Only log out all users who are deactivated",
        )
        parser.add_argument(
            "--rotate-api-keys",
            action="store_true",
            help="Also rotate API keys of the affected users",
        )
        self.add_realm_args(parser, help="Only log out all users in a particular realm")

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        rotate_api_keys = options["rotate_api_keys"]
        if realm:
            delete_realm_user_sessions(realm)
            regenerate_api_key_queryset = UserProfile.objects.filter(realm=realm).values_list(
                "id", flat=True
            )
        elif options["deactivated_only"]:
            delete_all_deactivated_user_sessions()
            regenerate_api_key_queryset = UserProfile.objects.filter(
                Q(is_active=False) | Q(realm__deactivated=True)
            ).values_list("id", flat=True)
        else:
            delete_all_user_sessions()
            regenerate_api_key_queryset = UserProfile.objects.values_list("id", flat=True)

        if rotate_api_keys:
            bulk_regenerate_api_keys(regenerate_api_key_queryset)
