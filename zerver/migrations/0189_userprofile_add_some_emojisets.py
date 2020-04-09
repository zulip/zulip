# Generated by Django 1.11.14 on 2018-08-28 19:01

from django.db import migrations, models
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def change_emojiset_choice(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model('zerver', 'UserProfile')
    UserProfile.objects.filter(emojiset='google').update(emojiset='google-blob')

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0188_userprofile_enable_login_emails'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='emojiset',
            field=models.CharField(choices=[('google', 'Google modern'), ('google-blob', 'Google classic'), ('twitter', 'Twitter'), ('text', 'Plain text')], default='google-blob', max_length=20),
        ),
        migrations.RunPython(
            change_emojiset_choice,
            reverse_code=migrations.RunPython.noop),
    ]
