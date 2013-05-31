from __future__ import absolute_import
from optparse import make_option

from django.core.management.base import BaseCommand
from zephyr.lib.actions import do_create_realm

class Command(BaseCommand):
    help = """Create a realm for the specified domain.

Usage: python manage.py create_realm foo.com"""

    option_list = BaseCommand.option_list + (
        make_option('-o', '--open-realm',
                    dest='open_realm',
                    action="store_true",
                    default=False,
                    help='Make this an open realm.'),
        )

    def handle(self, *args, **options):
        if not args:
            self.print_help("python manage.py", "create_realm")
            exit(1)

        domain = args[0]
        realm, created = do_create_realm(
            domain, restricted_to_domain=not options["open_realm"])
        if created:
            print domain, "created."
        else:
            print domain, "already exists."
