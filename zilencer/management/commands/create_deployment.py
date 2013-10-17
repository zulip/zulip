from __future__ import absolute_import
from optparse import make_option
import re
import sys

from django.core.management.base import BaseCommand

from zerver.models import get_realm
from zerver.lib.create_user import random_api_key
from zerver.management.commands.create_realm import Command as CreateRealm

from zilencer.models import Deployment

class Command(BaseCommand):
    help = """Create a deployment and accompanying realm."""

    option_list = CreateRealm.option_list + (
        make_option('--no-realm',
                    dest='no_realm',
                    action='store_true',
                    default=False,
                    help='Do not create a new realm; associate with an existing one.' + \
                           ' In this case, only the domain needs to be specified.'),
        )

    def handle(self, *args, **options):
        if options["domain"] is None:
            print >>sys.stderr, "\033[1;31mPlease provide a domain.\033[0m\n"
            self.print_help("python manage.py", "create_realm")
            exit(1)

        if not options["no_realm"]:
            CreateRealm().handle(*args, **options)
            print # Newline

        realm = get_realm(options["domain"])
        if realm is None:
            print >>sys.stderr, "\033[1;31mRealm does not exist!\033[0m\n"
            exit(2)

        dep = Deployment()
        dep.api_key = random_api_key()
        dep.save()
        dep.realms = [realm]
        dep.save()
        print "Deployment created."

