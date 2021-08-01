import secrets
from typing import Any, Optional

import orjson
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.utils.timezone import now as timezone_now

USERPROFILE_DEFAULT_BOT = 1
USERPROFILE_AVATAR_FROM_GRAVATAR = "G"
USERPROFILE_TUTORIAL_WAITING = "W"
RECIPIENT_PERSONAL = 1


def generate_api_key() -> str:
    api_key = ""
    while len(api_key) < 32:
        # One iteration suffices 99.4992% of the time.
        api_key += secrets.token_urlsafe(3 * 9).replace("_", "").replace("-", "")
    return api_key[:32]


def create_bots(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model("zerver", "UserProfile")
    Realm = apps.get_model("zerver", "Realm")
    Recipient = apps.get_model("zerver", "Recipient")
    Subscription = apps.get_model("zerver", "Subscription")

    """
    Helper functions, copy-pasted from production code and adjusted
    to work in a migration, for system bot-creating purposes.
    """

    def create_user(
        realm: Any,
        email: str,
        full_name: str,
        bot_type: Optional[int] = None,
    ) -> Any:
        active = True
        bot_owner = None
        tos_version = None
        timezone = ""
        avatar_source = USERPROFILE_AVATAR_FROM_GRAVATAR
        is_mirror_dummy = False
        default_sending_stream = None
        default_events_register_stream = None

        now = timezone_now()

        user_profile = UserProfile(
            password=make_password(None),  # This sets an unusable password.
            is_staff=False,
            is_active=active,
            full_name=full_name,
            last_login=now,
            date_joined=now,
            realm=realm,
            is_bot=bool(bot_type),
            bot_type=bot_type,
            bot_owner=bot_owner,
            is_mirror_dummy=is_mirror_dummy,
            tos_version=tos_version,
            timezone=timezone,
            tutorial_status=USERPROFILE_TUTORIAL_WAITING,
            enter_sends=False,
            onboarding_steps=orjson.dumps([]).decode(),
            default_language=realm.default_language,
            twenty_four_hour_time=realm.default_twenty_four_hour_time,
            delivery_email=email,
        )

        user_profile.email = email
        user_profile.api_key = generate_api_key()
        user_profile.avatar_source = avatar_source
        user_profile.timezone = timezone
        user_profile.default_sending_stream = default_sending_stream
        user_profile.default_events_register_stream = default_events_register_stream

        user_profile.save()

        recipient = Recipient.objects.create(type_id=user_profile.id, type=RECIPIENT_PERSONAL)
        user_profile.recipient = recipient
        user_profile.save(update_fields=["recipient"])

        Subscription.objects.create(user_profile=user_profile, recipient=recipient)
        return user_profile

    def create_system_bots_in_realm(realm: Any) -> None:
        internal_bots = [
            (bot["name"], bot["email_template"] % (settings.INTERNAL_BOT_DOMAIN,))
            for bot in settings.REALM_INTERNAL_BOTS
        ]
        for full_name, email in internal_bots:
            create_user(realm, email, full_name, bot_type=USERPROFILE_DEFAULT_BOT)
        # Set the owners for these bots to the bots themselves
        bots = UserProfile.objects.filter(email__in=[bot_info[1] for bot_info in internal_bots])
        for bot in bots:
            bot.bot_owner = bot
            bot.save()

        # Initialize the email gateway bot as able to forge senders.
        email_gateway_bot = UserProfile.objects.get(email=settings.EMAIL_GATEWAY_BOT, realm=realm)
        email_gateway_bot.can_forge_sender = True
        email_gateway_bot.save(update_fields=["can_forge_sender"])

    for realm in Realm.objects.exclude(string_id=settings.SYSTEM_BOT_REALM):
        create_system_bots_in_realm(realm)


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0340_rename_mutedtopic_to_usertopic"),
    ]

    operations = [
        migrations.RunPython(create_bots),
    ]
