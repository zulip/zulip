import configparser
import logging
from typing import List

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend
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
    def log_email(email: EmailMultiAlternatives) -> None:
        """Used in development to record sent emails in a nice HTML log"""
        html_message = 'Missing HTML message'
        if len(email.alternatives) > 0:
            html_message = email.alternatives[0][0]

        context = {
            'subject': email.subject,
            'from_email': email.from_email,
            'reply_to': email.reply_to,
            'recipients': email.to,
            'body': email.body,
            'html_message': html_message,
        }

        new_email = loader.render_to_string('zerver/email.html', context)

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
    def prepare_email_messages_for_forwarding(email_messages: List[EmailMultiAlternatives]) -> None:
        localhost_email_images_base_uri = settings.ROOT_DOMAIN_URI + '/static/images/emails'
        czo_email_images_base_uri = 'https://chat.zulip.org/static/images/emails'

        for email_message in email_messages:
            html_alternative = list(email_message.alternatives[0])
            # Here, we replace the email addresses used in development
            # with chat.zulip.org, so that web email providers like Gmail
            # will be able to fetch the illustrations used in the emails.
            html_alternative[0] = html_alternative[0].replace(localhost_email_images_base_uri, czo_email_images_base_uri)
            email_message.alternatives[0] = tuple(html_alternative)

            email_message.to = [get_forward_address()]

    def send_messages(self, email_messages: List[EmailMultiAlternatives]) -> int:
        num_sent = len(email_messages)
        if get_forward_address():
            self.prepare_email_messages_for_forwarding(email_messages)
            num_sent = super().send_messages(email_messages)

        if settings.DEVELOPMENT_LOG_EMAILS:
            for email in email_messages:
                self.log_email(email)
                email_log_url = settings.ROOT_DOMAIN_URI + "/emails"
                logging.info("Emails sent in development are available at %s", email_log_url)
        return num_sent
