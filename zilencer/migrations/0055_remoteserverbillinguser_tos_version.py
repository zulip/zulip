# Generated by Django 4.2.8 on 2023-12-14 17:27

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zilencer", "0054_remoterealmbillinguser_enable_maintenance_release_emails_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="remoteserverbillinguser",
            name="tos_version",
            field=models.TextField(default="-1"),
        ),
    ]
