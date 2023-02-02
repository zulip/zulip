# Generated by Django 4.0.7 on 2022-09-26 21:02

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0417_alter_customprofilefield_field_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="archivedmessage",
            name="realm",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="realm",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
            ),
        ),
    ]
