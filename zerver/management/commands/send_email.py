from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import send_mail, BadHeaderError

class Command(BaseCommand):
    help = """Send email from specified from_email to to_email."""

    def add_arguments(self, parser):
        parser.add_argument('subject', metavar='<subject>', type=str)
        parser.add_argument('message', metavar='<message>', type=str)
        parser.add_argument('from_email', metavar='<from_email>', type=str)
        parser.add_argument('to_email', metavar='<to_email>', type=str)

    def handle(self, *args, **options):
        subject = options['subject']
        message = options['message']
        from_email = options['from_email']
        to_email = options['to_email']

        try: 
            send_email(subject, message, from_email, [to_email])
        except BadHeaderError:
            raise CommandError("Invalid email header found")
