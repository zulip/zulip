import sys
import logging
import traceback

from django.utils.timezone import now
from django.views.debug import get_exception_reporter_filter


class AdminHumbugHandler(logging.Handler):
    """An exception log handler that Humbugs log entries to the Humbug realm.

    If the request is passed as the first argument to the log record,
    request data will be provided in the email report.
    """

    # adapted in part from django/utils/log.py

    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        # We have to defer imports to avoid circular imports in settings.py.
        from zephyr.models import Message, UserProfile, Recipient, \
                create_stream_if_needed, get_client, do_send_message
        from django.conf import settings
        message = Message()
        message.sender = UserProfile.objects.get(user__email="humbug+errors@humbughq.com")
        message.recipient = Recipient.objects.get(type_id=create_stream_if_needed(
            message.sender.realm, "devel").id, type=Recipient.STREAM)
        message.pub_date = now()
        message.sending_client = get_client("Internal")

        try:
            request = record.request
            subject = '%s (%s IP): %s' % (
                record.levelname,
                (request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS
                 and 'internal' or 'EXTERNAL'),
                record.getMessage()
            )
            filter = get_exception_reporter_filter(request)
            request_repr = filter.get_request_repr(request)
        except Exception:
            subject = '%s: %s' % (
                record.levelname,
                record.getMessage()
            )
            request = None
            request_repr = "Request repr() unavailable."
        message.subject = self.format_subject(subject)

        if record.exc_info:
            stack_trace = '\n'.join(traceback.format_exception(*record.exc_info))
        else:
            stack_trace = 'No stack trace available'

        message.content = "~~~~ pytb\n%s\n\n%s\n~~~~" % (stack_trace, request_repr)
        do_send_message(message)

    def format_subject(self, subject):
        """
        Escape CR and LF characters, and limit length to 60 characters.
        """
        formatted_subject = subject.replace('\n', '\\n').replace('\r', '\\r')
        return formatted_subject[:60]

