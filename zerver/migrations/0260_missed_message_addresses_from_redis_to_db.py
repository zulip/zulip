# -*- coding: utf-8 -*-
from django.core.exceptions import ObjectDoesNotExist
from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

from zerver.lib.redis_utils import get_redis_client
from zerver.lib.utils import generate_random_token

def generate_missed_message_token() -> str:
    return 'mm' + generate_random_token(32)

def move_missed_message_addresses_to_database(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    redis_client = get_redis_client()
    MissedMessageEmailAddress = apps.get_model('zerver', 'MissedMessageEmailAddress')
    UserProfile = apps.get_model('zerver', 'UserProfile')
    Message = apps.get_model('zerver', 'Message')
    Recipient = apps.get_model('zerver', 'Recipient')
    RECIPIENT_PERSONAL = 1
    RECIPIENT_STREAM = 2

    all_mm_keys = redis_client.keys('missed_message:*')
    for key in all_mm_keys:
        # Don't migrate mm addresses that have already been used.
        if redis_client.hincrby(key, 'uses_left', -1) < 0:
            redis_client.delete(key)
            continue

        result = redis_client.hmget(key, 'user_profile_id', 'recipient_id', 'subject')
        if not all(val is not None for val in result):
            # Missing data, skip this key
            redis_client.delete(key)
            continue

        user_profile_id, recipient_id, subject_b = result  # type: (bytes, bytes, bytes)
        topic_name = subject_b.decode('utf-8')

        # Now we have to figure out the appropriate objects to which ForeignKey fields
        # of MissedMessageEmailAddress should point. UserProfile and Recipient are straightforward,
        # the main complication is with Message, since the redis data doesn't hold information
        # about which Message exactly the "missed message" actually was. We take a "best effort"
        # approach here and select the "latest most viable" Message. For personals and huddles that's simple,
        # for streams we try "latest message with the topic name".
        # If the necessary objects can't be found in the database, we will catch ObjectDoesNotExist and skip this address.
        try:
            user_profile = UserProfile.objects.get(id=user_profile_id)
            recipient = Recipient.objects.get(id=recipient_id)

            if recipient.type == RECIPIENT_STREAM:
                message = Message.objects.filter(subject__iexact=topic_name,
                                                 recipient_id=recipient.id).latest('id')
            elif recipient.type == RECIPIENT_PERSONAL:
                # Tie to the latest PM from the sender to this user.
                message = Message.objects.filter(recipient_id=user_profile.recipient_id,
                                                 sender_id=recipient.type_id).latest('id')
            else:
                # Huddle case is the simplest - tie the mm address to the latest message
                # in the conversation.
                message = Message.objects.filter(recipient_id=recipient.id).latest('id')
        except ObjectDoesNotExist:
            redis_client.delete(key)
            continue

        # The timestamp will be set to the default (now) which means the address will take
        # longer to expire than it would have in redis, but this small issue is probably worth
        # the simplicity of not having to figure out the precise "fully correct" timestamp.
        MissedMessageEmailAddress.objects.create(message=message,
                                                 user_profile=user_profile,
                                                 email_token=generate_missed_message_token())
        # We successfully transferred the data to the database, so it can be deleted from redis.
        redis_client.delete(key)

class Migration(migrations.Migration):
    # Atomicity is not feasible here, since we're doing operations on redis too.
    # It's better to be non-atomic on both redis and database, than atomic
    # on the database and not on redis.
    atomic = False

    dependencies = [
        ('zerver', '0259_missedmessageemailaddress'),
    ]

    operations = [
        migrations.RunPython(move_missed_message_addresses_to_database, reverse_code=migrations.RunPython.noop),
    ]
