from __future__ import absolute_import

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.core.mail import send_mail, BadHeaderError

class Command(BaseCommand):
    help = """Send email to specified email address."""

    def add_arguments(self, parser):
        parser.add_argument('to', metavar='<to>', type=str,
                            help="email of user to send the email")

    def handle(self, *args, **options):
        subject = "Testing"
        message = "To test email sending in Zulip"
        frm = settings.DEFAULT_FROM_EMAIL
        to = options['to']

        try:
            send_mail(subject, message, frm, [to])
        except BadHeaderError:
            raise CommandError("Invalid email header found")
