# Generated by Django 4.2.6 on 2023-11-09 17:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zilencer", "0034_remoterealmauditlog_remote_realm_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="remoterealmcount",
            name="remote_realm",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE, to="zilencer.remoterealm"
            ),
        ),
        migrations.AlterField(
            model_name="remoterealmcount",
            name="realm_id",
            field=models.IntegerField(null=True),
        ),
    ]
