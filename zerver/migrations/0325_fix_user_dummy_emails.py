from typing import Any

from django.conf import settings
from django.core.validators import ValidationError, validate_email
from django.db import migrations, transaction
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

# The helper functions below are taken from models.py
# without any functional changes, they're just a workaround
# for the lack of access to Realm methods in migrations.


def host_for_subdomain(subdomain: str) -> str:
    if subdomain == "":
        return settings.EXTERNAL_HOST
    default_host = f"{subdomain}.{settings.EXTERNAL_HOST}"
    return settings.REALM_HOSTS.get(subdomain, default_host)


def get_realm_host(realm: Any) -> str:
    return host_for_subdomain(realm.string_id)


def get_fake_email_domain(realm: Any) -> str:
    try:
        # Check that realm.host can be used to form valid email addresses.
        host = get_realm_host(realm)
        validate_email(f"bot@{host}")
        return host
    except ValidationError:
        pass

    try:
        # Check that the fake email domain can be used to form valid email addresses.
        validate_email("bot@" + settings.FAKE_EMAIL_DOMAIN)
    except ValidationError:
        raise Exception(
            settings.FAKE_EMAIL_DOMAIN + " is not a valid domain. "
            "Consider setting the FAKE_EMAIL_DOMAIN setting."
        )

    return settings.FAKE_EMAIL_DOMAIN


def fix_user_emails(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    EMAIL_ADDRESS_VISIBILITY_EVERYONE = 1
    UserProfile = apps.get_model("zerver", "UserProfile")

    BATCH_SIZE = 200
    last_id = 0
    while True:
        with transaction.atomic():
            user_profiles = list(
                UserProfile.objects.exclude(
                    realm__email_address_visibility=EMAIL_ADDRESS_VISIBILITY_EVERYONE
                )
                .filter(
                    email__iregex=r"^user\d+" + f"@{settings.FAKE_EMAIL_DOMAIN}$", id__gt=last_id
                )
                .select_for_update()
                .order_by("id")[:BATCH_SIZE]
            )
            if not user_profiles:
                # Nothing left to fix.
                break
            last_id = user_profiles[-1].id

            for user_profile in user_profiles:
                user_profile.email = (
                    f"user{user_profile.id}@{get_fake_email_domain(user_profile.realm)}"
                )

            UserProfile.objects.bulk_update(user_profiles, ["email"])


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0324_fix_deletion_cascade_behavior"),
    ]

    operations = [
        migrations.RunPython(fix_user_emails, reverse_code=migrations.RunPython.noop),
    ]
