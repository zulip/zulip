from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0813_alter_preregistrationuser_external_auth_id_and_more"),
        ("zerver", "0814_backfill_userprofile_is_deleted"),
    ]

    operations = []
