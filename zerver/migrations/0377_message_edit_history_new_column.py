from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0376_set_realmemoji_author_and_reupload_realmemoji"),
    ]

    operations = [
        migrations.AddField(
            model_name="archivedmessage",
            name="edit_history_update_fields",
            field=models.JSONField(null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="edit_history_update_fields",
            field=models.JSONField(null=True),
        ),
    ]
