from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.db.models import get_app, get_models
from django.contrib.auth.management import create_permissions

class Command(BaseCommand):
    help = "Sync newly created object permissions to the database"

    def handle(self, *args, **options):
        # From http://stackoverflow.com/a/11914435/90777
        create_permissions(get_app("zerver"), get_models(), 2)
