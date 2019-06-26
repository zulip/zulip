from typing import Any

from django.db import connection

from zerver.lib.management import ZulipBaseCommand

def create_indexes() -> None:
    #  Creating concurrent indexes is kind of a pain with current versions
    #  of Django/postgres, because you will get this error with seemingly
    #  reasonable code:
    #
    #    CREATE INDEX CONCURRENTLY cannot be executed from a function or multi-command string
    #
    # For a lot more detail on this process, refer to the commit message
    # that added this file to the repo.

    with connection.cursor() as cursor:
        # copied from 0082
        print("Creating index zerver_usermessage_starred_message_id.")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_starred_message_id
            ON zerver_usermessage (user_profile_id, message_id)
            WHERE (flags & 2) != 0;
        ''')

        # copied from 0083
        print("Creating index zerver_usermessage_mentioned_message_id.")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_mentioned_message_id
            ON zerver_usermessage (user_profile_id, message_id)
            WHERE (flags & 8) != 0;
        ''')

        # copied from 0095
        print("Creating index zerver_usermessage_unread_message_id.")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_unread_message_id
            ON zerver_usermessage (user_profile_id, message_id)
            WHERE (flags & 1) = 0;
        ''')

        # copied from 0098
        print("Creating index zerver_usermessage_has_alert_word_message_id.")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_has_alert_word_message_id
            ON zerver_usermessage (user_profile_id, message_id)
            WHERE (flags & 512) != 0;
        ''')

        # copied from 0099
        print("Creating index zerver_usermessage_wildcard_mentioned_message_id.")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_wildcard_mentioned_message_id
            ON zerver_usermessage (user_profile_id, message_id)
            WHERE (flags & 8) != 0 OR (flags & 16) != 0;
        ''')

        # copied from 0177
        print("Creating index zerver_usermessage_is_private_message_id.")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_is_private_message_id
            ON zerver_usermessage (user_profile_id, message_id)
            WHERE (flags & 2048) != 0;
        ''')

        # copied from 0180
        print("Creating index zerver_usermessage_active_mobile_push_notification_id.")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS zerver_usermessage_active_mobile_push_notification_id
            ON zerver_usermessage (user_profile_id, message_id)
            WHERE (flags & 4096) != 0;
        ''')

        print("Finished.")

class Command(ZulipBaseCommand):
    help = """Create concurrent indexes for large tables."""

    def handle(self, *args: Any, **options: str) -> None:
        create_indexes()
