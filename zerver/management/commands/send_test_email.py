
from typing import Any

from django.conf import settings
from django.core.mail import mail_admins, mail_managers, send_mail
from django.core.management import CommandError
from django.core.management.commands import sendtestemail

from zerver.lib.send_email import FromAddress

class Command(sendtestemail.Command):
    def handle(self, *args: Any, **kwargs: str) -> None:
        if settings.WARN_NO_EMAIL:
            raise CommandError("Outgoing email not yet configured, see\n  "
                               "https://zulip.readthedocs.io/en/latest/production/email.html")
        message = ("Success!  If you receive this message, you've "
                   "successfully configured sending email from your "
                   "Zulip server.  Remember that you need to restart "
                   "the Zulip server with /home/zulip/deployments/current/scripts/restart-server "
                   "after changing the settings in /etc/zulip before your changes will take effect.")
        send_mail("Zulip email test", message, FromAddress.SUPPORT, kwargs['email'])
        send_mail("Zulip noreply email test", message, FromAddress.tokenized_no_reply_address(), kwargs['email'])

        if kwargs['managers']:
            mail_managers("Zulip manager email test", "This email was sent to the site managers.")

        if kwargs['admins']:
            mail_admins("Zulip admins email test", "This email was sent to the site admins.")
