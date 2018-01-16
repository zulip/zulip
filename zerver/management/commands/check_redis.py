
import logging
import time
from typing import Any, Callable, Optional

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from zerver.lib.rate_limiter import RateLimitedUser, \
    client, max_api_calls, max_api_window
from zerver.models import get_user_profile_by_id

class Command(BaseCommand):
    help = """Checks redis to make sure our rate limiting system hasn't grown a bug
    and left redis with a bunch of data

    Usage: ./manage.py [--trim] check_redis"""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('-t', '--trim',
                            dest='trim',
                            default=False,
                            action='store_true',
                            help="Actually trim excess")

    def _check_within_range(self, key: str, count_func: Callable[[], int],
                            trim_func: Optional[Callable[[str, int], None]]=None) -> None:
        user_id = int(key.split(':')[1])
        try:
            user = get_user_profile_by_id(user_id)
        except Exception:
            user = None
        entity = RateLimitedUser(user)
        max_calls = max_api_calls(entity)

        age = int(client.ttl(key))
        if age < 0:
            logging.error("Found key with age of %s, will never expire: %s" % (age, key,))

        count = count_func()
        if count > max_calls:
            logging.error("Redis health check found key with more elements \
than max_api_calls! (trying to trim) %s %s" % (key, count))
            if trim_func is not None:
                client.expire(key, max_api_window(entity))
                trim_func(key, max_calls)

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.RATE_LIMITING:
            print("This machine is not using redis or rate limiting, aborting")
            exit(1)

        # Find all keys, and make sure they're all within size constraints
        wildcard_list = "ratelimit:*:*:list"
        wildcard_zset = "ratelimit:*:*:zset"

        trim_func = lambda key, max_calls: client.ltrim(key, 0, max_calls - 1)  # type: Optional[Callable[[str, int], None]]
        if not options['trim']:
            trim_func = None

        lists = client.keys(wildcard_list)
        for list_name in lists:
            self._check_within_range(list_name,
                                     lambda: client.llen(list_name),
                                     trim_func)

        zsets = client.keys(wildcard_zset)
        for zset in zsets:
            now = time.time()
            # We can warn on our zset being too large, but we don't know what
            # elements to trim. We'd have to go through every list item and take
            # the intersection. The best we can do is expire it
            self._check_within_range(zset,
                                     lambda: client.zcount(zset, 0, now),
                                     lambda key, max_calls: None)
