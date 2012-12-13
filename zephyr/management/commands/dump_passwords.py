from optparse import make_option
from django.core.management.base import BaseCommand
from zephyr.models import User
import simplejson

def dump():
    passwords = []
    for u in User.objects.all():
        passwords.append((u.email, u.password))
    file("dumped-passwords", "w").write(simplejson.dumps(passwords) + "\n")

def restore(change):
    for (email, password) in simplejson.loads(file("dumped-passwords").read()):
        user = User.objects.get(email__iexact=email)
        if change:
            user.password = password
            user.save()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--restore', default=False, action='store_true'),
        make_option('--dry-run', '-n', default=False, action='store_true'),)

    def handle(self, *args, **options):
        if options["restore"]:
            restore(change=not options['dry_run'])
        else:
            dump()
