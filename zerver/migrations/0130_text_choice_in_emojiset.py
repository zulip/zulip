from django.db import migrations, models
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

# change emojiset to text if emoji_alt_code is true.
def change_emojiset(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model("zerver", "UserProfile")
    for user in UserProfile.objects.filter(emoji_alt_code=True):
        user.emojiset = "text"
        user.save(update_fields=["emojiset"])

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0129_remove_userprofile_autoscroll_forever'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='emojiset',
            field=models.CharField(choices=[('google', 'Google'), ('apple', 'Apple'), ('twitter', 'Twitter'), ('emojione', 'EmojiOne'), ('text', 'Plain text')], default='google', max_length=20),
        ),
        migrations.RunPython(change_emojiset),
        migrations.RemoveField(
            model_name='userprofile',
            name='emoji_alt_code',
        ),
    ]
