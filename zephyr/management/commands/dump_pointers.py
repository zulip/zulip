from optparse import make_option
from django.core.management.base import BaseCommand
from zephyr.models import Realm, UserProfile
import simplejson

def dump():
    pointers = []
    for u in UserProfile.objects.select_related("user__email").all():
        pointers.append((u.user.email, u.pointer))
    file("dumped-pointers", "w").write(simplejson.dumps(pointers) + "\n")

def restore(change):
    for (email, pointer) in simplejson.loads(file("dumped-pointers").read()):
        u = UserProfile.objects.get(user__email__iexact=email)
        print "%s: pointer %s => %s" % (email, u.pointer, pointer)
        if change:
            u.pointer = pointer
            u.save()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--restore', default=False, action='store_true'),
        make_option('--dry-run', '-n', default=False, action='store_true'),)

    def handle(self, *args, **options):
        if options["restore"]:
            restore(change=not options['dry_run'])
        else:
            dump()
