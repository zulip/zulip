import logging

from typing import List

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail import EmailMultiAlternatives
from django.template import loader

class EmailLogBackEnd(BaseEmailBackend):
    def log_email(self, email):
        # type: (EmailMultiAlternatives) -> None
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

    def send_messages(self, email_messages):
        # type: (List[EmailMultiAlternatives]) -> int
        for email in email_messages:
            self.log_email(email)
            email_log_url = settings.ROOT_DOMAIN_URI + "/emails"
            logging.info("Emails sent in development are available at %s" % (email_log_url,))
        return len(email_messages)
