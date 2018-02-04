# -*- coding: utf-8 -*-

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0111_botuserstatedata'),
    ]

    operations = [
        migrations.RunSQL(
            '''
            CREATE INDEX zerver_mutedtopic_stream_topic
            ON zerver_mutedtopic
            (stream_id, upper(topic_name))
            ''',
            reverse_sql='DROP INDEX zerver_mutedtopic_stream_topic;'
        ),
    ]
