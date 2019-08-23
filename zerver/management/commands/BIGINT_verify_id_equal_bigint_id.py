from __future__ import absolute_import

from typing import Any

from django.db.models import F
from django.core.management.base import BaseCommand

from zerver.models import UserMessage

class Command(BaseCommand):

    def handle(self, *args: Any, **options: str) -> None:
        assert UserMessage.objects.exclude(bigint_id=F("id")).count() == 0
