import hashlib
from typing import Any, List

from django.conf import settings
from django.db import migrations, transaction
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

CROSS_REALM_BOT_EMAILS = {
    "notification-bot@zulip.com",
    "welcome-bot@zulip.com",
    "emailgateway@zulip.com",
}


def get_huddle_hash(id_list: List[int]) -> str:
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    return hashlib.sha1(hash_key.encode("utf-8")).hexdigest()


def migrate_cross_realm_messages(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    Message = apps.get_model("zerver", "Message")
    UserProfile = apps.get_model("zerver", "UserProfile")
    UserMessage = apps.get_model("zerver", "UserMessage")
    Huddle = apps.get_model("zerver", "Huddle")
    Realm = apps.get_model("zerver", "Realm")
    Subscription = apps.get_model("zerver", "Subscription")
    Stream = apps.get_model("zerver", "Stream")
    RECIPIENT_HUDDLE = 3

    cross_realm_bots = list(
        UserProfile.objects.filter(
            email__in=settings.CROSS_REALM_BOT_EMAILS, realm__string_id=settings.SYSTEM_BOT_REALM
        ).select_related("recipient")
    )
    cross_realm_bot_ids = [bot.id for bot in cross_realm_bots]
    cross_realm_bot_recipients = [bot.recipient for bot in cross_realm_bots]

    all_cross_realm_huddle_ids = set(
        Subscription.objects.filter(
            user_profile__in=cross_realm_bots,
            recipient__type=RECIPIENT_HUDDLE,
        ).values_list("recipient__type_id", flat=True)
    )

    def migrate_cross_realm_messages_for_realm(realm: Any) -> None:
        realm_bots_dict = {
            bot.id: UserProfile.objects.get(email__iexact=bot.email, realm=realm)
            for bot in cross_realm_bots
        }
        cross_realm_bot_recipient_id_to_realm_bot_recipient = {
            bot.recipient_id: realm_bots_dict[bot.id].recipient for bot in cross_realm_bots
        }

        """
        Personal messages block
        """

        realm_users_query = UserProfile.objects.filter(realm=realm)
        personal_recipient_ids = realm_users_query.values_list("recipient_id", flat=True)

        personal_messages_from_cross_realm_bots = Message.objects.filter(
            sender__in=cross_realm_bots, recipient_id__in=personal_recipient_ids
        )
        usermessages = UserMessage.objects.filter(
            message__in=personal_messages_from_cross_realm_bots, user_profile__in=cross_realm_bots
        )
        message_id_to_usermessage = {
            usermessage.message_id: usermessage for usermessage in usermessages
        }
        usermessages_to_add = []
        for message in personal_messages_from_cross_realm_bots:
            new_sender = realm_bots_dict[message.sender_id]
            message.sender = new_sender
            try:
                message_id_to_usermessage[message.id].user_profile = new_sender
            except KeyError:
                # flags = 2048 means setting the is_private flag.
                usermessages_to_add.append(
                    UserMessage(user_profile=new_sender, message=message, flags=2048)
                )

        with transaction.atomic():
            Message.objects.bulk_update(personal_messages_from_cross_realm_bots, fields=["sender"])
            UserMessage.objects.bulk_update(
                message_id_to_usermessage.values(), fields=["user_profile"]
            )
            UserMessage.objects.bulk_create(usermessages_to_add)
        # Message lists can be relatively large, so we don't want to keep them in memory longer than needed.
        del personal_messages_from_cross_realm_bots

        personal_messages_to_cross_realm_bots = Message.objects.filter(
            sender__realm=realm, recipient__in=cross_realm_bot_recipients
        )
        usermessages = UserMessage.objects.filter(
            message__in=personal_messages_to_cross_realm_bots, user_profile__in=cross_realm_bots
        )
        message_id_to_usermessage = {
            usermessage.message_id: usermessage for usermessage in usermessages
        }
        usermessages_to_add = []
        for message in personal_messages_to_cross_realm_bots:
            new_recipient = cross_realm_bot_recipient_id_to_realm_bot_recipient[
                message.recipient_id
            ]
            message.recipient = new_recipient
            try:
                message_id_to_usermessage[message.id].user_profile_id = new_recipient.type_id
            except KeyError:
                usermessages_to_add.append(
                    UserMessage(user_profile_id=new_recipient.type_id, message=message, flags=2048)
                )

        with transaction.atomic():
            Message.objects.bulk_update(personal_messages_to_cross_realm_bots, fields=["recipient"])
            UserMessage.objects.bulk_update(
                message_id_to_usermessage.values(), fields=["user_profile_id"]
            )
            UserMessage.objects.bulk_create(usermessages_to_add)
        del personal_messages_to_cross_realm_bots

        """
        Stream messages block.
        This block doesn't involve UserMessages, as cross-realm bots
        don't get UserMessages for the cross-realm messages they send.
        """
        stream_recipient_ids = Stream.objects.filter(realm=realm).values_list(
            "recipient_id", flat=True
        )
        stream_messages_from_cross_realm_bots = Message.objects.filter(
            sender__in=cross_realm_bots, recipient_id__in=stream_recipient_ids
        )
        for message in stream_messages_from_cross_realm_bots:
            new_sender = realm_bots_dict[message.sender_id]
            message.sender = new_sender

        with transaction.atomic():
            Message.objects.bulk_update(stream_messages_from_cross_realm_bots, fields=["sender"])
        del stream_messages_from_cross_realm_bots

        """
        Huddle messages block
        The queries and loops are not well-optimized but cross-realm huddles
        should be extremely rare (if they exist at all), so it shouldn't pose a problem.
        """
        recipient_ids_of_huddles_with_cross_realm_bots = set(
            Subscription.objects.filter(
                user_profile__realm=realm,
                recipient__type=RECIPIENT_HUDDLE,
                recipient__type_id__in=all_cross_realm_huddle_ids,
            ).values_list("recipient_id", flat=True)
        )
        subscriptions_to_huddles_with_cross_realm_bots = Subscription.objects.filter(
            recipient_id__in=recipient_ids_of_huddles_with_cross_realm_bots,
        ).select_related("recipient")

        huddles_with_cross_realm_bots = Huddle.objects.filter(
            id__in=set(
                sub.recipient.type_id for sub in subscriptions_to_huddles_with_cross_realm_bots
            )
        )

        if Message.objects.filter(
            recipient_id__in=recipient_ids_of_huddles_with_cross_realm_bots,
            sender__in=cross_realm_bots,
        ).exists():
            raise AssertionError(
                "Cross-realm huddle messages where the sender is a cross-realm bot should't exist"
            )

        # Now we need to fix Huddle objects and their Subscriptions so that they stop being cross-realm.
        # That's done by swapping the bots' Subscriptions to belong to the corresponding in-realm bots,
        # and adjusting the huddle_hash of the Huddle.
        subs_to_update = []
        for huddle in huddles_with_cross_realm_bots:
            subs = [
                sub
                for sub in subscriptions_to_huddles_with_cross_realm_bots
                if sub.recipient.type_id == huddle.id
            ]
            if huddle.huddle_hash != get_huddle_hash([sub.user_profile_id for sub in subs]):
                raise AssertionError(
                    f"Cross-realm huddle {huddle.id} hash mismatching its subscribers"
                )

            bots_subs = [sub for sub in subs if sub.user_profile_id in cross_realm_bot_ids]
            for sub in bots_subs:
                corresponding_realm_bot = realm_bots_dict[sub.user_profile_id]
                sub.user_profile_id = corresponding_realm_bot.id
                subs_to_update.append(sub)
            huddle.huddle_hash = get_huddle_hash([sub.user_profile_id for sub in subs])

        with transaction.atomic():
            Subscription.objects.bulk_update(subs_to_update, fields=["user_profile_id"])
            Huddle.objects.bulk_update(huddles_with_cross_realm_bots, fields=["huddle_hash"])
            for cross_realm_bot_id in cross_realm_bot_ids:
                UserMessage.objects.filter(
                    user_profile_id=cross_realm_bot_id,
                    message__recipient_id__in=recipient_ids_of_huddles_with_cross_realm_bots,
                ).update(user_profile_id=realm_bots_dict[cross_realm_bot_id].id)

    for realm in Realm.objects.exclude(string_id=settings.SYSTEM_BOT_REALM):
        migrate_cross_realm_messages_for_realm(realm)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0341_put_system_bots_in_all_realms"),
    ]

    operations = [
        migrations.RunPython(
            migrate_cross_realm_messages,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
