# -*- coding: utf-8 -*-
import sys

from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F

def set_initial_value_of_is_private_flag(
        apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    UserMessage = apps.get_model("zerver", "UserMessage")
    Message = apps.get_model("zerver", "Message")
    if not Message.objects.exists():
        return

    i = 0
    # Total is only used for the progress bar
    total = Message.objects.filter(recipient__type__in=[1, 3]).count()
    processed = 0

    print("\nStart setting initial value for is_private flag...")
    sys.stdout.flush()
    while True:
        range_end = i + 10000
        # Can't use [Recipient.PERSONAL, Recipient.HUDDLE] in migration files
        message_ids = list(Message.objects.filter(recipient__type__in=[1, 3],
                                                  id__gt=i,
                                                  id__lte=range_end).values_list("id", flat=True).order_by("id"))
        count = UserMessage.objects.filter(message_id__in=message_ids).update(flags=F('flags').bitor(UserMessage.flags.is_private))
        if count == 0 and range_end >= Message.objects.last().id:
            break

        i = range_end
        processed += len(message_ids)
        if total != 0:
            percent = round((processed / total) * 100, 2)
        else:
            percent = 100.00
        print("Processed %s/%s %s%%" % (processed, total, percent))
        sys.stdout.flush()

class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('zerver', '0181_userprofile_change_emojiset'),
    ]

    operations = [
        migrations.RunPython(set_initial_value_of_is_private_flag,
                             reverse_code=migrations.RunPython.noop),
    ]
