from __future__ import absolute_import

from typing import Any

from django.core.management.base import BaseCommand
from zerver.lib.retention import archive_messages


class Command(BaseCommand):

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        archive_messages()
