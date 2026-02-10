from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("pgroonga", "0002_html_escape_subject"),
    ]

    operations = [
        # This migration does the following things:
        # * Undoes the `search_path` changes from the original migration 0001,
        #   which are no longer necessary with the modern PGroonga API.
        #   (Note that we've deleted those changes from the current version of the
        #    0001 migration).
        # * Drops a legacy-format v1 index if present (will be only if upgrading
        #   an old server).
        # * Does a CREATE INDEX CONCURRENTLY to add a PGroonga v2 search index
        #   on the message.search_pgroonga column (which was populated in
        #   migration 0002).
        migrations.RunSQL(
            sql=[
                "ALTER ROLE CURRENT_USER SET search_path TO zulip,public",
                "SET search_path = zulip,public",
                "DROP INDEX IF EXISTS zerver_message_search_pgroonga",
                (
                    "CREATE INDEX CONCURRENTLY zerver_message_search_pgroonga ON zerver_message "
                    "USING pgroonga(search_pgroonga pgroonga_text_full_text_search_ops_v2)"
                ),
            ],
            reverse_sql=[
                "ALTER ROLE CURRENT_USER SET search_path TO zulip,public,pgroonga,pg_catalog",
                "SET search_path = zulip,public,pgroonga,pg_catalog",
                "DROP INDEX IF EXISTS zerver_message_search_pgroonga",
                (
                    "CREATE INDEX CONCURRENTLY zerver_message_search_pgroonga ON zerver_message "
                    "USING pgroonga(search_pgroonga pgroonga.text_full_text_search_ops)"
                ),
            ],
        ),
    ]
