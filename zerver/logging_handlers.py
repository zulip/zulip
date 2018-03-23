# System documented in https://zulip.readthedocs.io/en/latest/subsystems/logging.html

import logging
import platform
import os
import subprocess
import traceback
from typing import Any, Dict, Optional

from django.conf import settings
from django.core import mail
from django.http import HttpRequest
from django.utils.log import AdminEmailHandler
from django.views.debug import ExceptionReporter, get_exception_reporter_filter

from zerver.lib.logging_util import find_log_caller_module
from zerver.lib.queue import queue_json_publish
from version import ZULIP_VERSION

def try_git_describe() -> Optional[str]:
    try:  # nocoverage
        return subprocess.check_output(
            ['git',
             '--git-dir', os.path.join(os.path.dirname(__file__), '../.git'),
             'describe', '--tags', '--always', '--dirty', '--long'],
            stderr=subprocess.PIPE,
        ).strip().decode('utf-8')
    except Exception:  # nocoverage
        return None

def add_deployment_metadata(report: Dict[str, Any]) -> None:
    report['git_described'] = try_git_describe()
    report['zulip_version_const'] = ZULIP_VERSION

    version_path = os.path.join(os.path.dirname(__file__), '../version')
    if os.path.exists(version_path):
        report['zulip_version_file'] = open(version_path).read().strip()  # nocoverage

def add_request_metadata(report: Dict[str, Any], request: HttpRequest) -> None:
    report['has_request'] = True

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
        report = {}  # type: Dict[str, Any]

        try:
            report['node'] = platform.node()
            report['host'] = platform.node()

            add_deployment_metadata(report)

            if record.exc_info:
                stack_trace = ''.join(traceback.format_exception(*record.exc_info))
                message = str(record.exc_info[1])
            else:
                stack_trace = 'No stack trace available'
                message = record.getMessage()
                if '\n' in message:
                    # Some exception code paths in queue processors
                    # seem to result in super-long messages
                    stack_trace = message
                    message = message.split('\n')[0]
            report['stack_trace'] = stack_trace
            report['message'] = message

            report['logger_name'] = record.name
            report['log_module'] = find_log_caller_module(record)
            report['log_lineno'] = record.lineno

            if hasattr(record, "request"):
                add_request_metadata(report, record.request)  # type: ignore  # record.request is added dynamically

        except Exception:
            report['message'] = "Exception in preparing exception report!"
            logging.warning(report['message'], exc_info=True)
            report['stack_trace'] = "See /var/log/zulip/errors.log"

        if settings.DEBUG_ERROR_REPORTING:  # nocoverage
            logging.warning("Reporting an error to admins...")
            logging.warning("Reporting an error to admins: {} {} {} {} {}" .format(
                record.levelname, report['logger_name'], report['log_module'],
                report['message'], report['stack_trace']))

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
