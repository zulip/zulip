from django.db import migrations, models
from django.conf import settings

from zerver.utils import add_index


class Migration(migrations.Migration):
    atomic = settings.ATOMIC_PG_MIGRATIONS

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
