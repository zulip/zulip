from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db.models import F

from zerver.models import UserMessage


class Command(BaseCommand):
    help = """Script to mark all messages as unread."""

    def handle(self, *args: Any, **options: Any) -> None:
        assert settings.DEVELOPMENT
        UserMessage.objects.all().update(flags=F('flags').bitand(~UserMessage.flags.read))
        cache._cache.flush_all()
