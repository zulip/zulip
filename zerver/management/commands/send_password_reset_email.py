from __future__ import absolute_import

import logging
from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.core.mail import send_mail, BadHeaderError
from zerver.forms import PasswordResetForm
from zerver.models import UserProfile, get_user_profile_by_email, get_realm
from django.template import loader
from django.core.mail import EmailMultiAlternatives

from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes


from django.contrib.auth.tokens import default_token_generator

class Command(BaseCommand):
    help = """Send email to specified email address."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('--to', metavar='<to>', type=str,
                            help="email of user to send the email")
        parser.add_argument('--realm', metavar='<realm>', type=str,
                            help="realm to send the email to all users in")
        parser.add_argument('--server', metavar='<server>', type=str,
                            help="If you specify 'YES' will send to everyone on server")

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        if options["to"]:
            users = [get_user_profile_by_email(options["to"])]
        elif options["realm"]:
            realm = get_realm(options["realm"])
            users = UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False,
                                               is_mirror_dummy=False)
        elif options["server"] == "YES":
            users = UserProfile.objects.filter(is_active=True, is_bot=False,
                                               is_mirror_dummy=False)
        else:
            raise RuntimeError("Missing arguments")
        self.send(users)

    def send(self, users, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.txt',
             use_https=True, token_generator=default_token_generator,
             from_email=None, request=None, html_email_template_name=None):
        """Sends one-use only links for resetting password to target users

        """
        for user_profile in users:
            context = {
                'email': user_profile.email,
                'domain': user_profile.realm.host,
                'site_name': "zulipo",
                'uid': urlsafe_base64_encode(force_bytes(user_profile.pk)),
                'user': user_profile,
                'token': token_generator.make_token(user_profile),
                'protocol': 'https' if use_https else 'http',
            }

            logging.warning("Sending %s email to %s" % (email_template_name, user_profile.email,))
            self.send_mail(subject_template_name, email_template_name,
                           context, from_email, user_profile.email,
                           html_email_template_name=html_email_template_name)

    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        """
        Sends a django.core.mail.EmailMultiAlternatives to `to_email`.
        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, 'text/html')

        email_message.send()
