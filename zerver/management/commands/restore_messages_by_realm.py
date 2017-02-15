from __future__ import absolute_import

from typing import Any
from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from zerver.lib.retention import restore_realm_archived_data
from zerver.models import get_realm


class Command(BaseCommand):

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('domain', metavar='<domain>', type=str,
                            help='The domain of the realm to restore messages data to.')

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = get_realm(options["domain"])
        restore_realm_archived_data(realm_id=realm.id)
