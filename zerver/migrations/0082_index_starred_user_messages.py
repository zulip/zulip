# -*- coding: utf-8 -*-

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0081_make_emoji_lowercase'),
    ]

    operations = [
        migrations.RunSQL(
            '''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_starred_message_id
                ON zerver_usermessage (user_profile_id, message_id)
                WHERE (flags & 2) != 0;
            ''',
            reverse_sql='DROP INDEX zerver_usermessage_starred_message_id;'
        ),
    ]
