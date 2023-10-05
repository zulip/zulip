import io
import smtplib
from contextlib import redirect_stderr
from typing import Any

from django.conf import settings
from django.core.mail import mail_admins, mail_managers, send_mail
from django.core.management import CommandError
from django.core.management.commands import sendtestemail

from zerver.lib.send_email import FromAddress, log_email_config_errors


class Command(sendtestemail.Command):

    def handle(self, *args: Any, **kwargs: str) -> None:
        """
        Send test emails.

        This method sends test emails to the specified email addresses. It checks if
        outgoing email is configured and raises an error if not. It then logs
        any email configuration errors. Next, it checks if an email address is
        provided as an argument and raises an error if not. It prints a
        message with instructions for troubleshooting if there are any issues.
        It sends two test emails, one from the support email address and
        another from the tokenized no-reply address. If there is any exception
        while sending emails, it prints the error message and the full
        SMTP log. Finally, it sends emails to the managers and admins if the
        corresponding flags are set in the command arguments.

        Args:
            *args: Any number of positional arguments.
            **kwargs: A dictionary of keyword arguments.
                email (List[str]): The email addresses to send the test emails to.
                managers (bool): Flag indicating whether to send the test email to managers.
                admins (bool): Flag indicating whether to send the test email to admins.
        """
        if settings.WARN_NO_EMAIL:
            raise CommandError(
                "Outgoing email not yet configured, see\n  "
                "https://zulip.readthedocs.io/en/latest/production/email.html"
            )

        log_email_config_errors()

        if len(kwargs["email"]) == 0:
            raise CommandError(
                "Usage: /home/zulip/deployments/current/manage.py "
                "send_test_email username@example.com"
            )

        print("If you run into any trouble, read:")
        print()
        print("  https://zulip.readthedocs.io/en/latest/production/email.html#troubleshooting")
        print()
        print("The most common error is not setting `ADD_TOKENS_TO_NOREPLY_ADDRESS=False` when")
        print("using an email provider that doesn't support that feature.")
        print()
        print("Sending 2 test emails from:")

        message = (
            "Success!  If you receive this message (and a second with a different subject), "
            "you've successfully configured sending emails from your Zulip server.  "
            "Remember that you need to restart "
            "the Zulip server with /home/zulip/deployments/current/scripts/restart-server "
            "after changing the settings in /etc/zulip before your changes will take effect."
        )
        with redirect_stderr(io.StringIO()) as f:
            smtplib.SMTP.debuglevel = 1
            try:
                sender = FromAddress.SUPPORT
                print(f"  * {sender}")
                send_mail("Zulip email test", message, sender, kwargs["email"])

                noreply_sender = FromAddress.tokenized_no_reply_address()
                print(f"  * {noreply_sender}")
                send_mail("Zulip noreply email test", message, noreply_sender, kwargs["email"])
            except smtplib.SMTPException as e:
                print(f"Failed to send mails: {e}")
                print()
                print("Full SMTP log follows:")
                print(f.getvalue())
                raise CommandError("Email sending failed!")
        print()
        print("Successfully sent 2 emails to {}!".format(", ".join(kwargs["email"])))

        if kwargs["managers"]:
            mail_managers("Zulip manager email test", "This email was sent to the site managers.")

        if kwargs["admins"]:
            mail_admins("Zulip admins email test", "This email was sent to the site admins.")
