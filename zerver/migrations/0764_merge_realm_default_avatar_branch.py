from django.db import migrations


class Migration(migrations.Migration):
    # Merge migration to resolve parallel branches involving the
    # realm default avatar changes and the follow-up data migration.
    dependencies = [
        ("zerver", "0761_realm_default_new_user_avatar_and_more"),
        ("zerver", "0763_update_existing_realms_default_avatar"),
    ]

    operations = []
