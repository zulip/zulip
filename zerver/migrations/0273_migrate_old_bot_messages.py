from typing import Any

from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def fix_messages(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Conceptually, this migration cleans up the old NEW_USER_BOT and FEEDBACK_BOT
    UserProfile objects (their implementations were removed long ago).

    We do this by:
    * Changing their sent messages to have been sent by NOTIFICATION_BOT.
    * Changing their 1:1 PMs to be PMs with NOTIFICATION_BOT and deleting their
      PM recipient object.
    * Deleting any Huddles that involve them (zulip.com data suggests there are none,
      so this is mainly out of caution) and Recipient objects (which will cascade to
      associated Subscription, Message, and UserMessage objects if they exist).
    * Deleting their UserProfile objects.

    The end result if these users are completely removed, with any
    messages that might have been associated with them transferred
    to NOTIFICATION_BOT to preserve history.
    """
    UserProfile = apps.get_model("zerver", "UserProfile")
    Huddle = apps.get_model("zerver", "Huddle")
    Subscription = apps.get_model("zerver", "Subscription")
    Recipient = apps.get_model("zerver", "Recipient")
    RECIPIENT_HUDDLE = 3
    Message = apps.get_model("zerver", "Message")
    Realm = apps.get_model("zerver", "Realm")

    try:
        internal_realm = Realm.objects.get(string_id=settings.SYSTEM_BOT_REALM)
    except Realm.DoesNotExist:
        # Server not initialized, or no system bot realm. Either way, we shouldn't do anything.
        return

    def get_bot_by_delivery_email(email: str) -> Any:
        return UserProfile.objects.select_related().get(
            delivery_email__iexact=email.strip(), realm=internal_realm
        )

    notification_bot = get_bot_by_delivery_email(settings.NOTIFICATION_BOT)

    def fix_messages_by_bot(bot_profile: Any) -> None:
        Message.objects.filter(sender=bot_profile).update(sender=notification_bot)
        Message.objects.filter(recipient=bot_profile.recipient).update(
            recipient=notification_bot.recipient
        )

    def clean_up_bot(bot_profile: Any) -> None:
        huddle_recipient_ids = Subscription.objects.filter(
            user_profile_id=bot_profile.id, recipient__type=RECIPIENT_HUDDLE
        ).values_list("recipient_id", flat=True)
        Huddle.objects.filter(recipient_id__in=huddle_recipient_ids).delete()
        Recipient.objects.filter(id__in=huddle_recipient_ids).delete()

        personal_recipient_id = bot_profile.recipient_id
        bot_profile.delete()
        Recipient.objects.filter(id=personal_recipient_id).delete()

    new_user_bot_email = getattr(settings, "NEW_USER_BOT", "new-user-bot@zulip.com")
    try:
        new_user_bot = get_bot_by_delivery_email(new_user_bot_email)
        fix_messages_by_bot(new_user_bot)
        clean_up_bot(new_user_bot)
    except UserProfile.DoesNotExist:
        pass

    feedback_bot_email = getattr(settings, "FEEDBACK_BOT", "feedback@zulip.com")
    try:
        feedback_bot = get_bot_by_delivery_email(feedback_bot_email)
        fix_messages_by_bot(feedback_bot)
        clean_up_bot(feedback_bot)
    except UserProfile.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0272_realm_default_code_block_language"),
    ]

    operations = [
        migrations.RunPython(fix_messages, reverse_code=migrations.RunPython.noop, elidable=True),
    ]
