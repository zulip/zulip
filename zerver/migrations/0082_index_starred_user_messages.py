# -*- coding: utf-8 -*-

from django.db import migrations

from zerver.lib.migrate import create_index_if_not_exist  # nolint

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0081_make_emoji_lowercase'),
    ]

    operations = [
        migrations.RunSQL(
            create_index_if_not_exist(
                index_name='zerver_usermessage_starred_message_id',
                table_name='zerver_usermessage',
                column_string='user_profile_id, message_id',
                where_clause='WHERE (flags & 2) != 0',
            ),
            reverse_sql='DROP INDEX zerver_usermessage_starred_message_id;'
        ),
    ]
