# System documented in https://zulip.readthedocs.io/en/latest/subsystems/logging.html

import logging
import platform
import traceback
from typing import Any, Dict, Optional

from django.conf import settings
from django.core import mail
from django.http import HttpRequest
from django.utils.log import AdminEmailHandler
from django.views.debug import ExceptionReporter, get_exception_reporter_filter

from zerver.lib.queue import queue_json_publish

def add_request_metadata(report: Dict[str, Any], request: HttpRequest) -> None:
    report['path'] = request.path
    report['method'] = request.method
    report['remote_addr'] = request.META.get('REMOTE_ADDR', None),
    report['query_string'] = request.META.get('QUERY_STRING', None),
    report['server_name'] = request.META.get('SERVER_NAME', None),
    try:
        from django.contrib.auth.models import AnonymousUser
        user_profile = request.user
        if isinstance(user_profile, AnonymousUser):
            user_full_name = None
            user_email = None
        else:
            user_full_name = user_profile.full_name
            user_email = user_profile.email
    except Exception:
        # Unexpected exceptions here should be handled gracefully
        traceback.print_exc()
        user_full_name = None
        user_email = None
    report['user_email'] = user_email
    report['user_full_name'] = user_full_name

    exception_filter = get_exception_reporter_filter(request)
    try:
        report['data'] = request.GET if request.method == 'GET' else \
            exception_filter.get_post_parameters(request)
    except Exception:
        # exception_filter.get_post_parameters will throw
        # RequestDataTooBig if there's a really big file uploaded
        report['data'] = {}

    try:
        report['host'] = request.get_host().split(':')[0]
    except Exception:
        # request.get_host() will throw a DisallowedHost
        # exception if the host is invalid
        report['host'] = platform.node()

class AdminNotifyHandler(logging.Handler):
    """An logging handler that sends the log/exception to the queue to be
       turned into an email and/or a Zulip message for the server admins.
    """

    # adapted in part from django/utils/log.py

    def __init__(self) -> None:
        logging.Handler.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:
        report = {}

        try:
            report['node'] = platform.node()
            report['host'] = platform.node()

            stack_trace = None
            if record.exc_info:
                stack_trace = ''.join(traceback.format_exception(*record.exc_info))
                message = str(record.exc_info[1])
            else:
                message = record.getMessage()
                if '\n' in message:
                    # Some exception code paths in queue processors
                    # seem to result in super-long messages
                    stack_trace = message
                    message = message.split('\n')[0]
            report['stack_trace'] = stack_trace
            report['message'] = message

            if hasattr(record, "request"):
                add_request_metadata(report, record.request)  # type: ignore  # record.request is added dynamically

        except Exception:
            report['message'] = "Exception in preparing exception report!"
            logging.warning(report['message'], exc_info=True)
            report['stack_trace'] = "See /var/log/zulip/errors.log"

        try:
            if settings.STAGING_ERROR_NOTIFICATIONS:
                # On staging, process the report directly so it can happen inside this
                # try/except to prevent looping
                from zerver.lib.error_notify import notify_server_error
                notify_server_error(report)
            else:
                queue_json_publish('error_reports', dict(
                    type = "server",
                    report = report,
                ))
        except Exception:
            # If this breaks, complain loudly but don't pass the traceback up the stream
            # However, we *don't* want to use logging.exception since that could trigger a loop.
            logging.warning("Reporting an exception triggered an exception!", exc_info=True)
