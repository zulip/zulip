# Generated by Django 4.2.6 on 2023-11-16 14:03

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0489_alter_realm_can_access_all_users_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmuserdefault",
            name="enable_dm_reactions_notifications",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="realmuserdefault",
            name="enable_followed_topics_reactions_notifications",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="realmuserdefault",
            name="enable_unmuted_topic_reactions_notifications",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="enable_dm_reactions_notifications",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="enable_followed_topics_reactions_notifications",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="enable_unmuted_topic_reactions_notifications",
            field=models.BooleanField(default=True),
        ),
    ]
