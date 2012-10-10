from django.core.management.base import BaseCommand
from zephyr.lib.initial_password import initial_password

class Command(BaseCommand):
    help = "Print the initial password for accounts as created by populate_db"

    def handle(self, *args, **options):
        print
        for email in args:
            if '@' not in email:
                print 'ERROR: %s does not look like an email address' % (email,)
                continue
            print '%-30s %-16s' % (email, initial_password(email))
