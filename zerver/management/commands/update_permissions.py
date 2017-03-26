from __future__ import absolute_import

from typing import Any

from django.core.management.base import BaseCommand
from django.apps import apps
from django.contrib.auth.management import create_permissions

class Command(BaseCommand):
    help = "Sync newly created object permissions to the database"

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        # From http://stackoverflow.com/a/11914435/90777
        create_permissions(apps.get_app_config("zerver"), apps.get_models(), 2)
