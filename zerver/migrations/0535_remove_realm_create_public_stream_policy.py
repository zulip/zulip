# Generated by Django 5.0.6 on 2024-05-30 08:58

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0534_alter_realm_can_create_public_channel_group"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="realm",
            name="create_public_stream_policy",
        ),
    ]
