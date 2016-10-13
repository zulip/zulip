from __future__ import absolute_import

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.core.mail import send_mail, BadHeaderError

class Command(BaseCommand):
    help = """Send email to specified email address."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('to', metavar='<to>', type=str,
                            help="email of user to send the email")

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        subject = "Zulip Test email"
        message = "Success!  If you receive this message, you've successfully " + \
            "configured sending email from your Zulip server."
        sender = settings.DEFAULT_FROM_EMAIL
        to = options['to']

        send_mail(subject, message, sender, [to])
