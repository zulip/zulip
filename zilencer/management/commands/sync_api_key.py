from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from django.core.management.base import BaseCommand
from zerver.models import get_user_profile_by_email, UserProfile
import os
from six.moves.configparser import ConfigParser

class Command(BaseCommand):
    help = """Sync your API key from ~/.zuliprc into your development instance"""

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        config_file = os.path.join(os.environ["HOME"], ".zuliprc")
        if not os.path.exists(config_file):
            raise RuntimeError("No ~/.zuliprc found")
        config = ConfigParser()
        with open(config_file, 'r') as f:
            # Apparently, six.moves.configparser.ConfigParser is not
            # consistent between Python 2 and 3!
            if hasattr(config, 'read_file'):
                config.read_file(f, config_file)
            else:
                config.readfp(f, config_file)
        api_key = config.get("api", "key")
        email = config.get("api", "email")

        try:
            user_profile = get_user_profile_by_email(email)
            user_profile.api_key = api_key
            user_profile.save(update_fields=["api_key"])
        except UserProfile.DoesNotExist:
            print("User %s does not exist; not syncing API key" % (email,))
