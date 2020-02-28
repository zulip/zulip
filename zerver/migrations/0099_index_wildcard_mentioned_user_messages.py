# -*- coding: utf-8 -*-

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0098_index_has_alert_word_user_messages'),
    ]

    operations = [
        migrations.RunSQL(
            '''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_wildcard_mentioned_message_id
                ON zerver_usermessage (user_profile_id, message_id)
                WHERE (flags & 8) != 0 OR (flags & 16) != 0;
            ''',
            reverse_sql='DROP INDEX zerver_usermessage_wilcard_mentioned_message_id;'
        ),
    ]
