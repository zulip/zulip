# -*- coding: utf-8 -*-

from django.db import migrations

from zerver.lib.migrate import create_index_if_not_exist  # nolint

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0082_index_starred_user_messages'),
    ]

    operations = [
        migrations.RunSQL(
            create_index_if_not_exist(
                index_name='zerver_usermessage_mentioned_message_id',
                table_name='zerver_usermessage',
                column_string='user_profile_id, message_id',
                where_clause='WHERE (flags & 8) != 0',
            ),
            reverse_sql='DROP INDEX zerver_usermessage_mentioned_message_id;'
        ),
    ]
