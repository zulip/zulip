from optparse import make_option
from django.core.management.base import BaseCommand

from zephyr.models import Realm, UserProfile

# Helper to be used with manage.py shell to get rid of bad users on prod.
def banish_busted_users(change=False):
    for u in UserProfile.objects.select_related().all():
        if (u.user.is_active or u.realm.domain != "mit.edu"):
            continue
        (banished_realm, _) = Realm.objects.get_or_create(domain="mit.deleted")
        if "|mit.edu@mit.edu" in u.email.lower():
            print u.email
            if change:
                u.realm = banished_realm
                u.email = u.email.split("@")[0] + "@" + banished_realm.domain
                u.user.save()
                u.save()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--dry-run', '-n', dest='dry_run', default=False, action='store_true'),)

    def handle(self, *args, **options):
        banish_busted_users(change=not options['dry_run'])
