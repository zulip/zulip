# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from zerver.models import UserProfile


def forwards(apps, schema_editor):
    user_profile_model_class = apps.get_model("zerver", "UserProfile")
    db_alias = schema_editor.connection.alias
    user_profile_model_class.objects.using(
        db_alias
    ).filter(
        is_bot=True
    ).update(
        bot_type=UserProfile.DEFAULT_BOT
    )


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0015_attachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='bot_type',
            field=models.PositiveSmallIntegerField(null=True, db_index=True),
        ),
        migrations.RunPython(forwards),
    ]
