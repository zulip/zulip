# Generated by Django 1.11.2 on 2017-06-20 10:31
from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def fix_bot_type(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model("zerver", "UserProfile")
    bots = UserProfile.objects.filter(is_bot=True, bot_type=None)
    for bot in bots:
        bot.bot_type = 1
        bot.save()

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0084_realmemoji_deactivated'),
    ]

    operations = [
        migrations.RunPython(fix_bot_type),
    ]
