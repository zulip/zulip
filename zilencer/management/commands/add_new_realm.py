from typing import Any

from zerver.lib.actions import do_create_realm, do_create_user
from zerver.lib.management import ZulipBaseCommand
from zerver.models import Realm, UserProfile


class Command(ZulipBaseCommand):
    help = """Add a new realm and initial user for manual testing of the onboarding process."""

    def handle(self, *args: Any, **options: Any) -> None:
        string_id = "realm{:02}".format(Realm.objects.filter(string_id__startswith="realm").count())
        realm = do_create_realm(string_id, string_id)

        name = "{:02}-user".format(UserProfile.objects.filter(email__contains="user@").count())
        do_create_user(
            f"{name}@{string_id}.zulip.com",
            "password",
            realm,
            name,
            role=UserProfile.ROLE_REALM_ADMINISTRATOR,
            realm_creation=True,
            acting_user=None,
        )
