from django.conf import settings
from django.db import migrations, models

from zerver.lib.migrate import add_index


class Migration(migrations.Migration):
    atomic = not settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY

    dependencies = [
        ("confirmation", "0013_alter_realmcreationkey_id"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        add_index(
            model_name="confirmation",
            index=models.Index(
                fields=["content_type", "object_id"], name="confirmatio_content_80155a_idx"
            ),
        ),
    ]
