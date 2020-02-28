# -*- coding: utf-8 -*-

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0097_reactions_emoji_code'),
    ]

    operations = [
        migrations.RunSQL(
            '''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_has_alert_word_message_id
                ON zerver_usermessage (user_profile_id, message_id)
                WHERE (flags & 512) != 0;
            ''',
            reverse_sql='DROP INDEX zerver_usermessage_has_alert_word_message_id;'
        ),
    ]
