# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0231_add_archive_transaction_model'),
    ]

    operations = [
        migrations.RunSQL("DELETE FROM zerver_archivedusermessage"),
        migrations.RunSQL("DELETE FROM zerver_archivedreaction"),
        migrations.RunSQL("DELETE FROM zerver_archivedsubmessage"),
        migrations.RunSQL("DELETE FROM zerver_archivedattachment"),
        migrations.RunSQL("DELETE FROM zerver_archivedattachment_messages"),
        migrations.RunSQL("DELETE FROM zerver_archivedmessage"),
        migrations.RunSQL("DELETE FROM zerver_archivetransaction"),
        migrations.AlterField(
            model_name='archivedmessage',
            name='archive_transaction',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.ArchiveTransaction'),
        ),
    ]
