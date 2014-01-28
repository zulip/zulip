from __future__ import absolute_import

from django.core.management.base import BaseCommand
from zerver.models import Realm
import sys

class Command(BaseCommand):
    help = """Show the admins in a realm.

Usage: ./manage.py show_admins <realm domain>
"""

    def handle(self, *args, **options):
        try:
            realm = args[0]
        except IndexError:
            print 'Please specify a realm.'
            sys.exit(1)

        try:
            realm = Realm.objects.get(domain=realm)
        except Realm.DoesNotExist:
            print 'There is no realm called %s.' % (realm,)
            sys.exit(1)

        users = realm.get_admin_users()

        if users:
            print 'Admins:\n'
            for user in users:
                print '  %s (%s)' % (user.email, user.full_name)
        else:
            print 'There are no admins for this realm!'

        print '\nYou can use the "knight" management command to knight admins.'
