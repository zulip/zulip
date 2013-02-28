from optparse import make_option
from django.core.management.base import BaseCommand
from zephyr.models import Realm, UserProfile, UserActivity, get_client
import simplejson
from zephyr.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime

def dump():
    pointers = []
    for activity in UserActivity.objects.select_related("user_profile__user__email",
                                                        "client__name").all():
        pointers.append((activity.user_profile.user.email, activity.client.name,
                         activity.query, activity.count,
                         datetime_to_timestamp(activity.last_visit)))
    file("dumped-activity", "w").write(simplejson.dumps(pointers) + "\n")

def restore(change):
    for (email, client_name, query, count, timestamp) in simplejson.loads(file("dumped-activity").read()):
        user_profile = UserProfile.objects.get(user__email__iexact=email)
        client = get_client(client_name)
        last_visit = timestamp_to_datetime(timestamp)
        print "%s: activity for %s,%s" % (email, client_name, query)
        if change:
            activity, created = UserActivity.objects.get_or_create(user_profile=user_profile,
                                                                   query=query, client=client,
                                                                   defaults={"last_visit": last_visit,
                                                                             "count": count})
            if not created:
                activity.count += count
                activity.last_visit = max(last_visit, activity.last_visit)
            activity.save()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--restore', default=False, action='store_true'),
        make_option('--dry-run', '-n', default=False, action='store_true'),)

    def handle(self, *args, **options):
        if options["restore"]:
            restore(change=not options['dry_run'])
        else:
            dump()
