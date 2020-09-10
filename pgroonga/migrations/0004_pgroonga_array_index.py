from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("pgroonga", "0003_v2_api_upgrade"),
    ]

    database_setting = settings.DATABASES["default"]
    operations = [
        migrations.RunSQL(
            [
                (
                    """
DO $$BEGIN
EXECUTE format('ALTER ROLE %%I SET search_path TO %%L,public', %(USER)s, %(SCHEMA)s);
SET search_path = %(SCHEMA)s,public;
DROP INDEX zerver_message_search_pgroonga;
END$$
""",
                    database_setting,
                ),
                """
CREATE INDEX CONCURRENTLY zerver_message_search_pgroonga ON zerver_message
  USING pgroonga((ARRAY[escape_html(subject), rendered_content]) pgroonga_text_array_full_text_search_ops_v2);
""",
            ],
            [
                (
                    """
DO $$BEGIN
EXECUTE format('ALTER ROLE %%I SET search_path TO %%L,public', %(USER)s, %(SCHEMA)s);
SET search_path = %(SCHEMA)s,public;
DROP INDEX zerver_message_search_pgroonga;
END$$
""",
                    database_setting,
                ),
                """
CREATE INDEX CONCURRENTLY zerver_message_search_pgroonga ON zerver_message
  USING pgroonga(search_pgroonga pgroonga_text_full_text_search_ops_v2);
""",
            ],
        ),
    ]
