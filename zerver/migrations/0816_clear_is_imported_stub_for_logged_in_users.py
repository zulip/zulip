from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Exists, OuterRef, Q


def clear_is_imported_stub_for_logged_in_users(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Clears is_imported_stub for imported users who logged in through
    a mobile app or the API, or signed up as a mirror dummy user,
    without seeing the terms of service page.

    UserActivity rows record requests a user made, so a row from a
    client other than the web and desktop apps means the user logged in
    through a mobile app or the API. The web app's event queue
    registrations are recorded as internal activity too, but a stub
    can't load the web app without accepting the terms of service,
    which clears is_imported_stub. Mirror dummy users who signed up
    are identified by their terms of service version, which signing up
    changes from TOS_VERSION_BEFORE_FIRST_LOGIN. On servers without
    terms of service, it changes to NULL, which the negated lookup below
    also matches.
    """

    Realm = apps.get_model("zerver", "Realm")
    UserActivity = apps.get_model("zerver", "UserActivity")
    UserProfile = apps.get_model("zerver", "UserProfile")

    # Copied from zerver/models/users.py
    TOS_VERSION_BEFORE_FIRST_LOGIN = "-1"
    # Copied from zerver/models/clients.py
    WEB_APP_CLIENT_NAMES = ["website", "ZulipElectron"]

    has_api_activity = Exists(
        UserActivity.objects.filter(user_profile_id=OuterRef("id")).exclude(
            client__name__in=WEB_APP_CLIENT_NAMES
        )
    )
    for realm_id in Realm.objects.order_by("id").values_list("id", flat=True).iterator():
        num_updated = (
            UserProfile.objects.filter(realm_id=realm_id, is_imported_stub=True)
            .filter(Q(has_api_activity) | ~Q(tos_version=TOS_VERSION_BEFORE_FIRST_LOGIN))
            .update(is_imported_stub=False)
        )
        if num_updated > 0:
            print(f"Realm {realm_id}: cleared is_imported_stub for {num_updated} users.")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0815_merge"),
    ]

    operations = [
        migrations.RunPython(
            clear_is_imported_stub_for_logged_in_users,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
