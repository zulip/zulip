from optparse import make_option
from django.core.management.base import BaseCommand
from zephyr.models import UserProfile, get_user_profile_by_email
from zephyr.lib.actions import do_change_password
import simplejson

def dump():
    passwords = []
    for user_profile in UserProfile.objects.all():
        passwords.append((user_profile.user.email, user_profile.password))
    file("dumped-passwords", "w").write(simplejson.dumps(passwords) + "\n")

def restore(change):
    for (email, password) in simplejson.loads(file("dumped-passwords").read()):
        try:
            user_profile = get_user_profile_by_email(email)
        except UserProfile.DoesNotExist:
            print "Skipping...", email
            continue
        if change:
            do_change_password(user_profile, password, log=False,
                               hashed_password=True)

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--restore', default=False, action='store_true'),
        make_option('--dry-run', '-n', default=False, action='store_true'),)

    def handle(self, *args, **options):
        if options["restore"]:
            restore(change=not options['dry_run'])
        else:
            dump()
