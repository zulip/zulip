from __future__ import absolute_import

from typing import Any

from django.core.management.base import BaseCommand
from zerver.lib.retention import delete_expired_archived_data


class Command(BaseCommand):

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        delete_expired_archived_data()
