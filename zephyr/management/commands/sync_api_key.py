from __future__ import absolute_import

from django.core.management.base import BaseCommand
from zephyr.models import get_user_profile_by_email
import os
from ConfigParser import SafeConfigParser

class Command(BaseCommand):
    help = """Reset all colors for a person to the default grey"""

    def handle(self, *args, **options):
        config_file = os.path.join(os.environ["HOME"], ".humbugrc")
        if not os.path.exists(config_file):
            raise RuntimeError("No ~/.humbugrc found")
        config = SafeConfigParser()
        with file(config_file, 'r') as f:
            config.readfp(f, config_file)
        api_key = config.get("api", "key")
        email = config.get("api", "email")

        user_profile = get_user_profile_by_email(email)
        user_profile.api_key = api_key
        user_profile.save()
