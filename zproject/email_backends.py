import logging

from typing import List
import configparser

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail import EmailMultiAlternatives
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

class EmailLogBackEnd(BaseEmailBackend):
    def send_email_smtp(self, email: EmailMultiAlternatives) -> None:
        from_email = email.from_email
        to = get_forward_address()

        msg = MIMEMultipart('alternative')
        msg['Subject'] = email.subject
        msg['From'] = from_email
        msg['To'] = to

        text = email.body
        html = email.alternatives[0][0]

        # Here, we replace the email addresses used in development
        # with chat.zulip.org, so that web email providers like Gmail
        # will be able to fetch the illustrations used in the emails.
        localhost_email_images_base_uri = settings.ROOT_DOMAIN_URI + '/static/images/emails'
        czo_email_images_base_uri = 'https://chat.zulip.org/static/images/emails'
        html = html.replace(localhost_email_images_base_uri, czo_email_images_base_uri)

        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))

        smtp = smtplib.SMTP(settings.EMAIL_HOST)
        smtp.starttls()
        smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        smtp.sendmail(from_email, to, msg.as_string())
        smtp.quit()

    def log_email(self, email: EmailMultiAlternatives) -> None:
        """Used in development to record sent emails in a nice HTML log"""
        html_message = 'Missing HTML message'
        if len(email.alternatives) > 0:
            html_message = email.alternatives[0][0]

        context = {
            'subject': email.subject,
            'from_email': email.from_email,
            'recipients': email.to,
            'body': email.body,
            'html_message': html_message
        }

        new_email = loader.render_to_string('zerver/email.html', context)

        # Read in the pre-existing log, so that we can add the new entry
        # at the top.
        try:
            with open(settings.EMAIL_CONTENT_LOG_PATH, "r") as f:
                previous_emails = f.read()
        except FileNotFoundError:
            previous_emails = ""

        with open(settings.EMAIL_CONTENT_LOG_PATH, "w+") as f:
            f.write(new_email + previous_emails)

    def send_messages(self, email_messages: List[EmailMultiAlternatives]) -> int:
        for email in email_messages:
            if get_forward_address():
                self.send_email_smtp(email)
            if settings.DEVELOPMENT_LOG_EMAILS:
                self.log_email(email)
                email_log_url = settings.ROOT_DOMAIN_URI + "/emails"
                logging.info("Emails sent in development are available at %s" % (email_log_url,))
        return len(email_messages)
