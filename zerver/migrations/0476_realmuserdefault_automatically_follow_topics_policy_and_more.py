# Generated by Django 4.2.5 on 2023-09-19 10:52

from django.db import migrations, models

AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER = 4


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0475_realm_jitsi_server_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmuserdefault",
            name="automatically_follow_topics_policy",
            field=models.PositiveSmallIntegerField(
                default=AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER
            ),
        ),
        migrations.AddField(
            model_name="realmuserdefault",
            name="automatically_unmute_topics_in_muted_streams_policy",
            field=models.PositiveSmallIntegerField(
                default=AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="automatically_follow_topics_policy",
            field=models.PositiveSmallIntegerField(
                default=AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="automatically_unmute_topics_in_muted_streams_policy",
            field=models.PositiveSmallIntegerField(
                default=AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER
            ),
        ),
    ]
