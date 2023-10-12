# Generated by Django 4.2.5 on 2023-10-02 05:53

from django.db import migrations, models

AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER = 4


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0476_realmuserdefault_automatically_follow_topics_policy_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="realmuserdefault",
            name="automatically_follow_topics_policy",
            field=models.PositiveSmallIntegerField(
                default=AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER
            ),
        ),
        migrations.AlterField(
            model_name="realmuserdefault",
            name="automatically_unmute_topics_in_muted_streams_policy",
            field=models.PositiveSmallIntegerField(
                default=AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="automatically_follow_topics_policy",
            field=models.PositiveSmallIntegerField(
                default=AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="automatically_unmute_topics_in_muted_streams_policy",
            field=models.PositiveSmallIntegerField(
                default=AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER
            ),
        ),
    ]
