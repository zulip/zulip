# Generated by Django 4.2.5 on 2023-09-19 17:02

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0474_realmuserdefault_web_stream_unreads_count_display_policy_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="jitsi_server_url",
            field=models.URLField(default=None, null=True),
        ),
    ]
