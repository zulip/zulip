from __future__ import absolute_import
from optparse import make_option

from django.core.management.base import BaseCommand
from zerver.lib.actions import send_local_email_template_with_delay, clear_followup_emails_queue
from datetime import timedelta
from django.conf import settings

def dequeue(email):
    return clear_followup_emails_queue(email)

# Changes to this should also be reflected in
# zerver/worker/queue_processors.py:SignupWorker.consume()
def queue(email, name, instant=False):
    delay1 = timedelta(hours=24)
    delay2 = timedelta(hours=48)
    if instant:
        delay1 = delay2 = timedelta(0)

    sender={'email': 'wdaher@zulip.com', 'name': 'Waseem Daher'}
    if settings.ENTERPRISE:
        sender={'email': settings.ZULIP_ADMINISTRATOR, 'name': 'Zulip'}
    #Send day 1 email
    send_local_email_template_with_delay([{'email': email, 'name': name}],
                                         "zerver/emails/followup/day1",
                                         {'name': name},
                                         delay1,
                                         tags=["followup-emails"],
                                         sender=sender)

    #Send day 2 email
    send_local_email_template_with_delay([{'email': email, 'name': name}],
                                         "zerver/emails/followup/day2",
                                         {'name': name},
                                         delay2,
                                         tags=["followup-emails"],
                                         sender=sender)


class Command(BaseCommand):
    help = """Queue (or dequeue) followup emails to point of contact for newly created realm
This currently sends out an email 24 hours and another 48 hours from right now.
For this to work correctly, you should have a correctly set system clock.

Usage: python manage.py enqueue_followup_emails "foobar@example.com" "Foo Bar"
or:
Usage: python manage.py enqueue_followup_emails --remove-queued "foobar@example.com"
"""

    option_list = BaseCommand.option_list + (
        make_option('-r', '--remove-queued',
                    dest='remove_queued',
                    action="store_true",
                    default=False,
                    help='Remove the emails queued for this address'),
        make_option('-i', '--instant',
                    dest='instant',
                    action="store_true",
                    default=False,
                    help="Send immediate, don't queue. Has no effect for removing things from the queue"),
        )

    def handle(self, *args, **options):
        if (options["remove_queued"] and not len(args) == 1) \
                or (not options['remove_queued'] and len(args) != 2):
            self.print_help("python manage.py", "enqueue_followup_emails")
            exit(1)
        if "@" not in args[0]:
            print "It seems that you didn't supply a valid email address--did you swap parameters?"
            exit(1)
        if options["remove_queued"]:
            return dequeue(*args)
        else:
            return queue(*args, instant=options["instant"])

