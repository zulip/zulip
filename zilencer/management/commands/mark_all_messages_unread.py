from __future__ import absolute_import

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import F
from django.core.cache import cache
from zerver.models import UserProfile, UserMessage

class Command(BaseCommand):
    help = """Script to mark all messages as unread."""

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        assert settings.DEVELOPMENT
        UserMessage.objects.all().update(flags=F('flags').bitand(~UserMessage.flags.read))
        UserProfile.objects.all().update(pointer=0)
        cache._cache.flush_all()
