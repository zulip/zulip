from __future__ import absolute_import

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.apps import flush_cache
from zerver.models import Message
from zerver.lib.message import messages_for_ids

import random
import time


class Command(BaseCommand):

    def handle(self, *args: Any, **options: str) -> None:
        all_ids = Message.objects.values_list('id', flat=True)

        ids_to_fetch = list(set(random.choice(all_ids) for i in range(0, 10000)))
        user_message_flags= {msg_id: ["read"] for msg_id in ids_to_fetch}

        flush_cache(None)

        start_time = time.time()
        print("Fetching messages...")
        messages_for_ids(
            message_ids=ids_to_fetch,
            user_message_flags=user_message_flags,
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )
        print("Done")
        end_time = time.time()
        total_time = end_time - start_time
        print("Total time: {}".format(total_time))
