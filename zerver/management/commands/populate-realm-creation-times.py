#!/usr/bin/python

from django.core.management.base import BaseCommand

from zerver.models import Realm

import datetime

# Pulled from event logs on staging.

times = """"""

# Pulled from event logs on prod.

times = times + """"""

times = times + """"""

times_dict = {}
for row in times.split("\n"):
    domain, timestr = row.split(" ")
    timestamp = datetime.datetime.fromtimestamp(int(timestr))
    times_dict[domain] = timestamp

class Command(BaseCommand):
    help = """Set the realm creation time for all existing realms."""

    def handle(self, **options):
        for realm in Realm.objects.all():
            timestamp = times_dict.get(realm.domain)
            if timestamp:
                print "Saving", realm.domain, timestamp
                realm.date_created = timestamp
                realm.save()
            else:
                print "Couldn't find data for", realm.domain
