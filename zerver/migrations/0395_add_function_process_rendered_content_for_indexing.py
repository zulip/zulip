from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0394_alter_realm_want_advertise_in_communities_directory"),
    ]

    operations = [
        migrations.RunSQL(
            sql=r"""
            CREATE OR REPLACE FUNCTION extract_anchor_text(message_content text) RETURNS SETOF text IMMUTABLE LANGUAGE 'sql' AS $$
                select anchor_text_match[1] as anchor_text from REGEXP_MATCHES(
                    message_content,'<a [^>]+>([^<]+)<\/a>','g'
                ) as anchor_text_match
            $$ ;

            CREATE OR REPLACE FUNCTION replace_url_delimiters(anchor_text text, replacement text) RETURNS text IMMUTABLE LANGUAGE 'sql' AS $$
                select regexp_replace(anchor_text,'[:\/.?#@]', replacement, 'g');
            $$ ;

            CREATE OR REPLACE FUNCTION replace_anchor_text_url_delimiters(message_content text, replacement text) RETURNS text AS
            $BODY$
                DECLARE
                    anchor_text text;
                    result text;
                BEGIN
                    result := message_content;
                    FOR anchor_text IN select extract_anchor_text(message_content)
                    LOOP
                        result := replace(result,  '>'|| anchor_text ||'<' , '>' || replace_url_delimiters(anchor_text, replacement) || '<');
                    END LOOP;
                RETURN result;
                END;
            $BODY$ LANGUAGE plpgsql;
 
            CREATE OR REPLACE FUNCTION process_text_for_search(text_to_process text) RETURNS text IMMUTABLE LANGUAGE 'sql' AS $$
                select replace_anchor_text_url_delimiters(text_to_process, ' ')
            $$ ;
             """,
        ),
    ]
