from optparse import make_option
from django.core.management.base import BaseCommand

from zephyr.models import UserProfile
from zephyr.lib.actions import compute_mit_user_fullname

# Helper to be used with manage.py shell to fix bad names on prod.
def update_mit_fullnames(change=False):
    for u in UserProfile.objects.select_related().all():
        if (u.user.is_active or u.realm.domain != "mit.edu"):
            # Don't change fullnames for non-MIT users or users who
            # actually have an account (is_active) and thus have
            # presumably set their fullname how they like it.
            continue
        computed_name = compute_mit_user_fullname(u.user.email)
        if u.full_name != computed_name:
            print "%s: %s => %s" % (u.user.email, u.full_name, computed_name)
            if change:
                u.full_name = computed_name
                u.save()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--dry-run', '-n', dest='dry_run', default=False, action='store_true'),)

    def handle(self, *args, **options):
        update_mit_fullnames(change=not options['dry_run'])
