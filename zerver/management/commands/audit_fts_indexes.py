from typing import Any

from django.db import connection

from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    def handle(self, *args: Any, **kwargs: str) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE zerver_message
                SET search_tsvector =
                setweight(to_tsvector('zulip.english_us_search', subject), 'A') ||
                setweight(to_tsvector('zulip.english_us_search', rendered_content), 'B')
                WHERE (setweight(to_tsvector('zulip.english_us_search', subject), 'A') ||
                setweight(to_tsvector('zulip.english_us_search', rendered_content), 'B')) != search_tsvector
            """
            )

            fixed_message_count = cursor.rowcount
            print(f"Fixed {fixed_message_count} messages.")
