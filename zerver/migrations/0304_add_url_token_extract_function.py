from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0303_realm_wildcard_mention_policy'),
    ]

    # This creates an SQL function that extract url from html rendered content and tokenise it.
    # Tokenise logic is simple:
    # 1. Regex <a\s+(?:[^>]*?\s+)?href="([^"]*)" extract url provided to href attr in anchor tag
    #    of html of message_content.
    # 2. Regex (_|-|\.|\/|:) matches _ - . / : characters from extracted url and then replace them
    #    with space.
    # Eg. <a href="https://chat.zulip.org/">CZO</a> in html content. This function will extract url
    # https://chat.zulip.org/ and replace :, /, . with spaces to make it:
    # "https   chat zulip org ".
    operations = [
        migrations.RunSQL(
            sql=r"""
CREATE FUNCTION extract_url_tokens(message_content text) RETURNS text IMMUTABLE LANGUAGE 'sql' AS $$
  SELECT COALESCE(REGEXP_REPLACE(
    STRING_AGG(
        ARRAY_TO_STRING(links.matched_url, ' '), ' '
    ),'(_|-|\.|\/|:)',' ','g'
  ), '')
  FROM (
    SELECT REGEXP_MATCHES(
        message_content,'<a\s+(?:[^>]*?\s+)?href="([^"]*)"','g'
    ) as matched_url
  ) as links;
$$ ;
            """,
        ),
    ]
