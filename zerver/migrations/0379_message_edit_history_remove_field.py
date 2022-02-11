from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0378_message_edit_history_update_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="archivedmessage",
            name="edit_history",
        ),
        migrations.RemoveField(
            model_name="message",
            name="edit_history",
        ),
    ]
