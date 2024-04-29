import logging
import time
from typing import Any, Callable, Optional

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from typing_extensions import override

from zerver.lib.partial import partial
from zerver.lib.rate_limiter import RateLimitedUser, client
from zerver.models.users import get_user_profile_by_id


class Command(BaseCommand):
    help = """Checks Redis to make sure our rate limiting system hasn't grown a bug
    and left Redis with a bunch of data

    Usage: ./manage.py [--trim] check_redis"""

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("-t", "--trim", action="store_true", help="Actually trim excess")

    def _check_within_range(
        self,
        key: bytes,
        count_func: Callable[[], int],
        trim_func: Optional[Callable[[bytes, int], object]] = None,
    ) -> None:
        user_id = int(key.split(b":")[2])
        user = get_user_profile_by_id(user_id)
        entity = RateLimitedUser(user)
        max_calls = entity.max_api_calls()

        age = int(client.ttl(key))
        if age < 0:
            logging.error("Found key with age of %s, will never expire: %s", age, key)

        count = count_func()
        if count > max_calls:
            logging.error(
                "Redis health check found key with more elements \
than max_api_calls! (trying to trim) %s %s",
                key,
                count,
            )
            if trim_func is not None:
                client.expire(key, entity.max_api_window())
                trim_func(key, max_calls)

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.RATE_LIMITING:
            raise CommandError("This machine is not using Redis or rate limiting, aborting")

        # Find all keys, and make sure they're all within size constraints
        wildcard_list = "ratelimit:*:*:*:list"
        wildcard_zset = "ratelimit:*:*:*:zset"

        trim_func: Optional[Callable[[bytes, int], object]] = lambda key, max_calls: client.ltrim(
            key, 0, max_calls - 1
        )
        if not options["trim"]:
            trim_func = None

        lists = client.keys(wildcard_list)
        for list_name in lists:
            self._check_within_range(list_name, partial(client.llen, list_name), trim_func)

        zsets = client.keys(wildcard_zset)
        for zset in zsets:
            now = time.time()
            # We can warn on our zset being too large, but we don't know what
            # elements to trim. We'd have to go through every list item and take
            # the intersection. The best we can do is expire it
            self._check_within_range(
                zset,
                partial(client.zcount, zset, 0, now),
                lambda key, max_calls: None,
            )
