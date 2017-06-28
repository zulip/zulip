from __future__ import absolute_import

from typing import Any

from django.conf import settings
from django.core.mail import mail_admins, mail_managers, send_mail
from django.core.management.commands import sendtestemail

class Command(sendtestemail.Command):
    def handle(self, *args, **kwargs):
        # type: (*Any, **str) -> None
        subject = "Zulip Test email"
        message = ("Success!  If you receive this message, you've "
                   "successfully configured sending email from your "
                   "Zulip server.")
        sender = settings.ZULIP_ADMINISTRATOR
        send_mail(subject, message, sender, kwargs['email'])

        if kwargs['managers']:
            mail_managers(subject, "This email was sent to the site managers.")

        if kwargs['admins']:
            mail_admins(subject, "This email was sent to the site admins.")
