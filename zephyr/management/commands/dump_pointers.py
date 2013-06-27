from __future__ import absolute_import

from optparse import make_option
from django.core.management.base import BaseCommand
from zephyr.models import UserProfile, Message, UserMessage, \
    get_user_profile_by_email
from zephyr.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
import ujson

def dump():
    pointers = []
    for u in UserProfile.objects.all():
        pointer = u.pointer
        if pointer != -1:
            pub_date = Message.objects.get(id=pointer).pub_date
            pointers.append((u.email, datetime_to_timestamp(pub_date)))
        else:
            pointers.append((u.email, -1))
    file("dumped-pointers", "w").write(ujson.dumps(pointers) + "\n")

def restore(change):
    for (email, timestamp) in ujson.loads(file("dumped-pointers").read()):
        try:
            u = get_user_profile_by_email(email)
        except UserProfile.DoesNotExist:
            print "Skipping...", email
            continue
        if timestamp == -1:
            pointer = -1
        else:
            try:
                pointer = UserMessage.objects.filter(user_profile=u,
                    message__pub_date__gte=timestamp_to_datetime(timestamp)).order_by("message")[0].message_id
            except IndexError:
                print "Alert...", email, timestamp
                continue
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
