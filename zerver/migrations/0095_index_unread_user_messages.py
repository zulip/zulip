# -*- coding: utf-8 -*-

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0094_realm_filter_url_validator'),
    ]

    operations = [
        migrations.RunSQL(
            '''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_unread_message_id
                ON zerver_usermessage (user_profile_id, message_id)
                WHERE (flags & 1) = 0;
            ''',
            reverse_sql='DROP INDEX zerver_usermessage_unread_message_id;'
        ),
    ]
