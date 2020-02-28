# -*- coding: utf-8 -*-

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0041_create_attachments_for_old_messages'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='file_name',
            field=models.TextField(db_index=True),
        ),
    ]
