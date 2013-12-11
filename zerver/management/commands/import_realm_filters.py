from __future__ import absolute_import

from django.core.management.base import BaseCommand

from zerver.models import RealmFilter, get_realm

import logging

class Command(BaseCommand):
    help = """Imports realm filters to database"""

    def handle(self, *args, **options):
        realm_filters = {
            "zulip.com": [
                ("#(?P<id>[0-9]{2,8})", "https://trac.zulip.net/ticket/%(id)s"),
                ],
            "mit.edu/zephyr_mirror": [],
        }

        for domain, filters in realm_filters.iteritems():
            realm = get_realm(domain)
            if realm is None:
                logging.error("Failed to get realm for domain %s" % (domain,))
                continue
            for filter in filters:
                RealmFilter(realm=realm, pattern=filter[0], url_format_string=filter[1]).save()
                logging.info("Created realm filter %s for %s" % (filter[0], domain))
