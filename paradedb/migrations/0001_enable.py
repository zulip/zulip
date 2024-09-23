from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY fts_pg_search_idx
                ON zulip.zerver_message
                USING bm25 (
                    id,
                    rendered_content,
                    subject,
                    realm_id
                )
                WITH (
                    key_field = 'id',
                    text_fields = '{
                        "rendered_content": {
                            "record": "position",
                            "tokenizer": {
                                "lowercase": true,
                                "remove_long": 255,
                                "stemmer": "English",
                                "type": "icu"
                            }
                        },
                        "subject": {
                            "record": "position",
                            "tokenizer": {
                                "lowercase": true,
                                "remove_long": 255,
                                "stemmer": "English",
                                "type": "icu"
                            }
                        }
                    }',
                    numeric_fields='{"realm_id":{"fast":true}}'
                );
                """,
            reverse_sql="DROP INDEX fts_pg_search_idx;",
        ),
    ]
