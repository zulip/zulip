# https://zulip.readthedocs.io/en/latest/subsystems/email.html#testing-in-a-real-email-client
import configparser
import logging
from collections.abc import Sequence
from email.message import Message
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail.message import EmailAlternative, EmailMessage
from django.template import loader
from django.utils.timezone import now as timezone_now
from typing_extensions import override


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
        html_message: bytes | EmailMessage | Message | str = "Missing HTML message"
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
            "date": email.extra_headers.get("Date", "?"),
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
            # Here, we replace the image URLs used in development with
            # chat.zulip.org URLs, so that web email providers like Gmail
            # will be able to fetch the illustrations used in the emails.
            assert isinstance(email_message.alternatives[0], EmailAlternative)
            original_content = email_message.alternatives[0].content
            original_mimetype = email_message.alternatives[0].mimetype
            assert isinstance(original_content, str)
            email_message.alternatives[0] = EmailAlternative(
                content=original_content.replace(
                    localhost_email_images_base_url, czo_email_images_base_url
                ),
                mimetype=original_mimetype,
            )

            email_message.to = [get_forward_address()]

    # This wrapper function exists to allow tests easily to mock the
    # step of trying to send the emails. Previously, we had mocked
    # Django's connection.send_messages(), which caused unexplained
    # test failures when running test-backend at very high
    # concurrency.
    def _do_send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        return super().send_messages(email_messages)  # nocoverage

    @override
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


class PersistentSMTPEmailBackend(EmailBackend):
    def _open(self, **kwargs: Any) -> bool | None:
        is_opened = super().open()
        if is_opened:
            self.opened_at = timezone_now()
            return True

        return is_opened

    @override
    def open(self, **kwargs: Any) -> bool | None:
        is_opened = self._open()
        if is_opened:
            return True

        status = None
        time_elapsed = (timezone_now() - self.opened_at).seconds / 60
        if settings.EMAIL_MAX_CONNECTION_LIFETIME_IN_MINUTES != 0 and (
            settings.EMAIL_MAX_CONNECTION_LIFETIME_IN_MINUTES is None
            or time_elapsed <= settings.EMAIL_MAX_CONNECTION_LIFETIME_IN_MINUTES
        ):
            # No-op to ensure that we don't return a connection that has been
            # closed by the mail server.
            try:
                assert self.connection is not None
                status = self.connection.noop()[0]
            except Exception:
                pass

        # In case of EMAIL_MAX_CONNECTION_LIFETIME_IN_MINUTES = 0, we
        # will always return a newly opened connection. The default
        # smtp.py implementation of send_messages closes the connection
        # after sending the emails if the connection was a new
        # connection i.e. is_opened is True.

        if status is None or status != 250:
            # Close and connect again.
            self.close()
            is_opened = self._open()

        return is_opened
