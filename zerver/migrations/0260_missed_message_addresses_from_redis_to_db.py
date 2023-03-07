import secrets

from django.core.exceptions import ObjectDoesNotExist
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

# Imported to avoid needing to duplicate Redis-related code.
from zerver.lib.redis_utils import get_redis_client


def generate_missed_message_token() -> str:
    return "mm" + secrets.token_hex(16)


def move_missed_message_addresses_to_database(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    redis_client = get_redis_client()
    MissedMessageEmailAddress = apps.get_model("zerver", "MissedMessageEmailAddress")
    UserProfile = apps.get_model("zerver", "UserProfile")
    Message = apps.get_model("zerver", "Message")
    Recipient = apps.get_model("zerver", "Recipient")
    RECIPIENT_PERSONAL = 1
    RECIPIENT_STREAM = 2

    all_mm_keys = redis_client.keys("missed_message:*")
    for key in all_mm_keys:
        # Don't migrate mm addresses that have already been used.
        if redis_client.hincrby(key, "uses_left", -1) < 0:
            redis_client.delete(key)
            continue

        user_profile_id, recipient_id, subject_b = redis_client.hmget(
            key, "user_profile_id", "recipient_id", "subject"
        )
        if user_profile_id is None or recipient_id is None or subject_b is None:
            # Missing data, skip this key; this should never happen
            redis_client.delete(key)
            continue

        topic_name = subject_b.decode()

        # The data model for missed-message emails has changed in two
        # key ways: We're moving it from Redis to the database for
        # better persistence, and also replacing the stream + topic
        # (as the reply location) with a message to reply to.  Because
        # the Redis data structure only had stream/topic pairs, we use
        # the following migration logic to find the latest message in
        # the thread indicated by the Redis data (if it exists).
        try:
            user_profile = UserProfile.objects.get(id=user_profile_id)
            recipient = Recipient.objects.get(id=recipient_id)

            if recipient.type == RECIPIENT_STREAM:
                message = Message.objects.filter(
                    subject__iexact=topic_name, recipient_id=recipient.id
                ).latest("id")
            elif recipient.type == RECIPIENT_PERSONAL:
                # Tie to the latest PM from the sender to this user;
                # we expect at least one existed because it generated
                # this missed-message email, so we can skip the
                # normally required additional check for messages we
                # ourselves sent to the target user.
                message = Message.objects.filter(
                    recipient_id=user_profile.recipient_id, sender_id=recipient.type_id
                ).latest("id")
            else:
                message = Message.objects.filter(recipient_id=recipient.id).latest("id")
        except ObjectDoesNotExist:
            # If all messages in the original thread were deleted or
            # had their topics edited, we can't find an appropriate
            # message to tag; we just skip migrating this message.
            # The consequence (replies to this particular
            # missed-message email bouncing) is acceptable.
            redis_client.delete(key)
            continue

        # The timestamp will be set to the default (now) which means
        # the address will take longer to expire than it would have in
        # Redis, but this small issue is probably worth the simplicity
        # of not having to figure out the precise timestamp.
        MissedMessageEmailAddress.objects.create(
            message=message, user_profile=user_profile, email_token=generate_missed_message_token()
        )
        # We successfully transferred this missed-message email's data
        # to the database, so this message can be deleted from Redis.
        redis_client.delete(key)


class Migration(migrations.Migration):
    # Atomicity is not feasible here, since we're doing operations on Redis too.
    # It's better to be non-atomic on both Redis and database, than atomic
    # on the database and not on Redis.
    atomic = False

    dependencies = [
        ("zerver", "0259_missedmessageemailaddress"),
    ]

    operations = [
        migrations.RunPython(
            move_missed_message_addresses_to_database,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
