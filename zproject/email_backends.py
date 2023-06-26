# https://zulip.readthedocs.io/en/latest/subsystems/email.html#testing-in-a-real-email-client
import configparser
import logging
from email.message import Message
from typing import MutableSequence, Sequence, Union

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail.message import EmailMessage
from django.template import loader


def get_forward_address() -> str:
    config = configparser.ConfigParser()
    config.read(settings.FORWARD_ADDRESS_CONFIG_FILE)
    try:
        return config.get("DEV_EMAIL", "forward_address")
    except (configparser.NoSectionError, configparser.NoOptionError):
        return ""


def set_forward_address(forward_address: str) -> None:
    config = configparser.ConfigParser()
    config.read(settings.FORWARD_ADDRESS_CONFIG_FILE)

    if not config.has_section("DEV_EMAIL"):
        config.add_section("DEV_EMAIL")
    config.set("DEV_EMAIL", "forward_address", forward_address)

    with open(settings.FORWARD_ADDRESS_CONFIG_FILE, "w") as cfgfile:
        config.write(cfgfile)


class EmailLogBackEnd(EmailBackend):
    @staticmethod
    def log_email(email: EmailMessage) -> None:
        """Used in development to record sent emails in a nice HTML log"""
        html_message: Union[bytes, EmailMessage, Message, str] = "Missing HTML message"
        assert isinstance(email, EmailMultiAlternatives)
        if len(email.alternatives) > 0:
            html_message = email.alternatives[0][0]

        context = {
            "subject": email.subject,
            "envelope_from": email.from_email,
            "from_email": email.extra_headers.get("From", email.from_email),
            "reply_to": email.reply_to,
            "recipients": email.to,
            "body": email.body,
            "html_message": html_message,
        }

        new_email = loader.render_to_string("zerver/email.html", context)

        # Read in the pre-existing log, so that we can add the new entry
        # at the top.
        try:
            with open(settings.EMAIL_CONTENT_LOG_PATH) as f:
                previous_emails = f.read()
        except FileNotFoundError:
            previous_emails = ""

        with open(settings.EMAIL_CONTENT_LOG_PATH, "w+") as f:
            f.write(new_email + previous_emails)

    @staticmethod
    def prepare_email_messages_for_forwarding(email_messages: Sequence[EmailMessage]) -> None:
        localhost_email_images_base_url = settings.ROOT_DOMAIN_URI + "/static/images/emails"
        czo_email_images_base_url = "https://chat.zulip.org/static/images/emails"

        for email_message in email_messages:
            assert isinstance(email_message, EmailMultiAlternatives)
            assert isinstance(email_message.alternatives[0][0], str)
            # Here, we replace the email addresses used in development
            # with chat.zulip.org, so that web email providers like Gmail
            # will be able to fetch the illustrations used in the emails.
            html_alternative = (
                email_message.alternatives[0][0].replace(
                    localhost_email_images_base_url, czo_email_images_base_url
                ),
                email_message.alternatives[0][1],
            )
            assert isinstance(email_message.alternatives, MutableSequence)
            email_message.alternatives[0] = html_alternative

            email_message.to = [get_forward_address()]

    # This wrapper function exists to allow tests easily to mock the
    # step of trying to send the emails. Previously, we had mocked
    # Django's connection.send_messages(), which caused unexplained
    # test failures when running test-backend at very high
    # concurrency.
    def _do_send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        return super().send_messages(email_messages)  # nocoverage

    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        num_sent = len(email_messages)
        if get_forward_address():
            self.prepare_email_messages_for_forwarding(email_messages)
            num_sent = self._do_send_messages(email_messages)

        if settings.DEVELOPMENT_LOG_EMAILS:
            for email in email_messages:
                self.log_email(email)
                email_log_url = settings.ROOT_DOMAIN_URI + "/emails"
                logging.info("Emails sent in development are available at %s", email_log_url)
        return num_sent
