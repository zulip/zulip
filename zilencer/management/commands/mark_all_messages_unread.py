from typing import Any

import bmemcached
from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserMessage


class Command(ZulipBaseCommand):
    help = """Script to mark all messages as unread."""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        assert settings.DEVELOPMENT
        UserMessage.objects.all().update(flags=F("flags").bitand(~UserMessage.flags.read))
        _cache = cache._cache  # type: ignore[attr-defined] # not in stubs
        assert isinstance(_cache, bmemcached.Client)
        _cache.flush_all()
