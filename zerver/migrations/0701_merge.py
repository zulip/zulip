from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0699_scheduledmessage_reminder_target_message_id"),
        ("zerver", "0700_fix_user_role_system_groups"),
    ]

    operations = []
