from typing import Any

from django.db import connection

from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    """
    Django management command to update the search_tsvector field of the
    zerver_message table.
    """
    def handle(self, *args: Any, **kwargs: str) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE zerver_message
                SET search_tsvector =
                to_tsvector('zulip.english_us_search', subject || rendered_content)
                WHERE to_tsvector('zulip.english_us_search', subject || rendered_content) != search_tsvector
            """
            )

            fixed_message_count = cursor.rowcount
            print(f"Fixed {fixed_message_count} messages.")
