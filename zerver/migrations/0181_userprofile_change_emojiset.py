from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def change_emojiset_choice(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model("zerver", "UserProfile")
    UserProfile.objects.exclude(emojiset__in=["google", "text"]).update(emojiset="google")


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0180_usermessage_add_active_mobile_push_notification"),
    ]

    operations = [
        migrations.RunPython(
            change_emojiset_choice, reverse_code=migrations.RunPython.noop, elidable=True
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="emojiset",
            field=models.CharField(
                choices=[("google", "Google"), ("text", "Plain text")],
                default="google",
                max_length=20,
            ),
        ),
    ]
