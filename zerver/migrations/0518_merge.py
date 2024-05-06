from django.db import migrations

# See 0517 for the history of this migration merge commit.


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0516_fix_confirmation_preregistrationusers"),
        ("zerver", "0517_resort_edit_history"),
    ]

    operations = []
