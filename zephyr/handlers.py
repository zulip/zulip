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
                create_stream_if_needed, get_client, internal_send_message
        from django.conf import settings

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
        subject = self.format_subject(subject)

        if record.exc_info:
            stack_trace = ''.join(traceback.format_exception(*record.exc_info))
        else:
            stack_trace = 'No stack trace available'

        internal_send_message("humbug+errors@humbughq.com",
                Recipient.STREAM, "devel", subject,
                "~~~~ pytb\n%s\n\n%s\n~~~~" % (stack_trace, request_repr))

    def format_subject(self, subject):
        """
        Escape CR and LF characters, and limit length to MAX_SUBJECT_LENGTH.
        """
        from zephyr.models import MAX_SUBJECT_LENGTH
        formatted_subject = subject.replace('\n', '\\n').replace('\r', '\\r')
        return formatted_subject[:MAX_SUBJECT_LENGTH]

