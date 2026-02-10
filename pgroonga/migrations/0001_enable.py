from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0001_initial"),
    ]

    database_setting = settings.DATABASES["default"]

    operations = [
        # This previously had additional operations, but they are all
        # undone in migration 0003 because we switched to using the
        # PGroonga v2 API.
        migrations.RunSQL(
            sql="ALTER TABLE zerver_message ADD COLUMN search_pgroonga text;",
            reverse_sql="ALTER TABLE zerver_message DROP COLUMN search_pgroonga;",
        ),
    ]
