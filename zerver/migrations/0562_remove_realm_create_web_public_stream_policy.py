# Generated by Django 5.0.6 on 2024-07-26 07:18

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0561_alter_realm_can_create_web_public_channel_group"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="realm",
            name="create_web_public_stream_policy",
        ),
    ]
