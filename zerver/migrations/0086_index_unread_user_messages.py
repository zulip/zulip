# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from zerver.lib.migrate import create_index_if_not_exist  # nolint


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0085_fix_bots_with_none_bot_type'),
    ]

    operations = [
        migrations.RunSQL(
            create_index_if_not_exist(
                index_name='zerver_usermessage_read_message_id',
                table_name='zerver_usermessage',
                column_string='user_profile_id, message_id',
                where_clause='WHERE (flags & 1) != 0',
            ),
            reverse_sql='DROP INDEX zerver_usermessage_read_message_id;'
        ),
    ]
