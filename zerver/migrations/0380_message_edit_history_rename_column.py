from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0379_message_edit_history_remove_field"),
    ]

    operations = [
        migrations.RenameField(
            model_name="archivedmessage",
            old_name="edit_history_update_fields",
            new_name="edit_history",
        ),
        migrations.RenameField(
            model_name="message",
            old_name="edit_history_update_fields",
            new_name="edit_history",
        ),
    ]
