from __future__ import absolute_import

from django.core.management.base import BaseCommand
from zerver.lib.initial_password import initial_password
from zerver.models import get_user_profile_by_email

class Command(BaseCommand):
    help = "Print the initial password and API key for accounts as created by populate_db"

    fmt = '%-30s %-16s  %-32s'

    def handle(self, *args, **options):
        print self.fmt % ('email', 'password', 'API key')
        for email in args:
            if '@' not in email:
                print 'ERROR: %s does not look like an email address' % (email,)
                continue
            print self.fmt % (email, initial_password(email), get_user_profile_by_email(email).api_key)
