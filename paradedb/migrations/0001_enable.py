from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""CALL paradedb.create_bm25(
                    index_name => 'fts_pg_search_idx',
                    schema_name => 'zulip',
                    table_name => 'zerver_message',
                    key_field => 'id',
                    text_fields => paradedb.field('rendered_content',
                                                  tokenizer => paradedb.tokenizer('icu', stemmer => 'English'),
                                                  record => 'position')
                                   || paradedb.field('subject', tokenizer => paradedb.tokenizer('icu', stemmer => 'English'), record => 'position')
                );
                """,
            reverse_sql="CALL paradedb.drop_bm25( index_name => 'fts_pg_search_idx', schema_name => 'zulip');",
        ),
    ]
