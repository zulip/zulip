from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("confirmation", "0013_alter_realmcreationkey_id"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="confirmation",
            index=models.Index(
                fields=["content_type", "object_id"], name="confirmatio_content_80155a_idx"
            ),
        ),
    ]
