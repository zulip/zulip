from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0001_initial"),
    ]

    database_setting = settings.DATABASES["default"]

    operations = [
        migrations.RunSQL(
            sql="""CALL paradedb.create_bm25(
                    index_name => 'fts_pg_search_idx',
                    schema_name => 'zulip',
                    table_name => 'zerver_message',
                    key_field => 'id',
                    text_fields => paradedb.field('rendered_content',
                                                  tokenizer => paradedb.tokenizer('en_stem'))
                                   || paradedb.field('subject', tokenizer => paradedb.tokenizer('en_stem'))
                );
                """,
            reverse_sql="CALL paradedb.drop_bm25( index_name => 'fts_pg_search_idx', schema_name => 'zulip');",
        ),
    ]
