# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
import sys

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from functools import wraps
from mock import patch
if False:
    from mypy_extensions import NoReturn
from typing import Any, Callable, Dict, Mapping, Optional, Text

from zerver.lib.request import JsonableError
from zerver.lib.test_classes import ZulipTestCase
from zerver.logging_handlers import AdminZulipHandler
from zerver.middleware import JsonErrorHandler
from zerver.views.compatibility import check_compatibility
from zerver.worker.queue_processors import QueueProcessingWorker

captured_request = None  # type: Optional[HttpRequest]
captured_exc_info = None
def capture_and_throw(domain=None):
    # type: (Optional[Text]) -> Callable
    def wrapper(view_func):
        # type: (Callable[..., HttpResponse]) -> Callable[..., HttpResponse]
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # type: (HttpRequest, *Any, **Any) -> NoReturn
            global captured_request
            captured_request = request
            try:
                raise Exception("Request error")
            except Exception as e:
                global captured_exc_info
                captured_exc_info = sys.exc_info()
                raise e
        return wrapped_view
    return wrapper

class AdminZulipHandlerTest(ZulipTestCase):
    logger = logging.getLogger('django')

    def setUp(self):
        # type: () -> None
        self.handler = AdminZulipHandler()
        # Prevent the exceptions we're going to raise from being printed
        # You may want to disable this when debugging tests
        settings.LOGGING_NOT_DISABLED = False

        global captured_exc_info
        global captured_request
        captured_request = None
        captured_exc_info = None

    def tearDown(self):
        # type: () -> None
        settings.LOGGING_NOT_DISABLED = True

    def get_admin_zulip_handler(self, logger):
        # type: (logging.Logger) -> Any

        # Ensure that AdminEmailHandler does not get filtered out
        # even with DEBUG=True.
        admin_email_handler = [
            h for h in logger.handlers
            if h.__class__.__name__ == "AdminZulipHandler"
        ][0]
        return admin_email_handler

    def test_basic(self):
        # type: () -> None
        """A random exception passes happily through AdminZulipHandler"""
        handler = self.get_admin_zulip_handler(self.logger)
        try:
            raise Exception("Testing Error!")
        except Exception:
            exc_info = sys.exc_info()
        record = self.logger.makeRecord('name', logging.ERROR, 'function', 16, 'message', None, exc_info)  # type: ignore # https://github.com/python/typeshed/pull/1100
        handler.emit(record)

    def run_handler(self, record):
        # type: (logging.LogRecord) -> Dict[str, Any]
        with patch('zerver.logging_handlers.queue_json_publish') as patched_publish:
            self.handler.emit(record)
            patched_publish.assert_called_once()
            event = patched_publish.call_args[0][1]
            self.assertIn("report", event)
            return event["report"]

    def test_long_exception_request(self):
        # type: () -> None
        """A request with with no stack where report.getMessage() has newlines
        in it is handled properly"""
        email = self.example_email('hamlet')
        self.login(email)
        with patch("zerver.decorator.rate_limit") as rate_limit_patch:
            rate_limit_patch.side_effect = capture_and_throw
            result = self.client_get("/json/users")
            self.assert_json_error(result, "Internal server error", status_code=500)
            rate_limit_patch.assert_called_once()

            global captured_request
            global captured_exc_info
            record = self.logger.makeRecord('name', logging.ERROR, 'function', 15,  # type: ignore # https://github.com/python/typeshed/pull/1100
                                            'message\nmoremesssage\nmore', None,
                                            None)
            record.request = captured_request # type: ignore # this field is dynamically added

            report = self.run_handler(record)
            self.assertIn("user_email", report)
            self.assertIn("message", report)
            self.assertIn("stack_trace", report)
            self.assertEqual(report['stack_trace'], 'message\nmoremesssage\nmore')
            self.assertEqual(report['message'], 'message')

    def test_request(self):
        # type: () -> None
        """A normal request is handled properly"""
        email = self.example_email('hamlet')
        self.login(email)
        with patch("zerver.decorator.rate_limit") as rate_limit_patch:
            rate_limit_patch.side_effect = capture_and_throw
            result = self.client_get("/json/users")
            self.assert_json_error(result, "Internal server error", status_code=500)
            rate_limit_patch.assert_called_once()

            global captured_request
            global captured_exc_info
            record = self.logger.makeRecord('name', logging.ERROR, 'function', 15, 'message', None, captured_exc_info)  # type: ignore # https://github.com/python/typeshed/pull/1100
            record.request = captured_request # type: ignore # this field is dynamically added

            report = self.run_handler(record)
            self.assertIn("user_email", report)
            self.assertIn("message", report)
            self.assertIn("stack_trace", report)

            # Test that `add_request_metadata` throwing an exception is fine
            with patch("zerver.logging_handlers.traceback.print_exc"):
                with patch("zerver.logging_handlers.add_request_metadata",
                           side_effect=Exception("Unexpected exception!")):
                    report = self.run_handler(record)
            self.assertNotIn("user_email", report)
            self.assertIn("message", report)
            self.assertEqual(report["stack_trace"], "See /var/log/zulip/errors.log")

            # Check anonymous user is handled correctly
            record.request.user = AnonymousUser() # type: ignore # this field is dynamically added
            report = self.run_handler(record)
            self.assertIn("host", report)
            self.assertIn("user_email", report)
            self.assertIn("message", report)
            self.assertIn("stack_trace", report)

            # Now simulate a DisallowedHost exception
            def get_host_error():
                # type: () -> None
                raise Exception("Get Host Failure!")
            orig_get_host = record.request.get_host # type: ignore # this field is dynamically added
            record.request.get_host = get_host_error # type: ignore # this field is dynamically added
            report = self.run_handler(record)
            record.request.get_host = orig_get_host # type: ignore # this field is dynamically added
            self.assertIn("host", report)
            self.assertIn("user_email", report)
            self.assertIn("message", report)
            self.assertIn("stack_trace", report)

            # Test an exception_filter exception
            with patch("zerver.logging_handlers.get_exception_reporter_filter",
                       return_value=15):
                record.request.method = "POST" # type: ignore # this field is dynamically added
                report = self.run_handler(record)
                record.request.method = "GET" # type: ignore # this field is dynamically added
            self.assertIn("host", report)
            self.assertIn("user_email", report)
            self.assertIn("message", report)
            self.assertIn("stack_trace", report)

            # Test the catch-all exception handler doesn't throw
            with patch('zerver.logging_handlers.queue_json_publish',
                       side_effect=Exception("queue error")):
                self.handler.emit(record)

            # Test the STAGING_ERROR_NOTIFICATIONS code path
            with self.settings(STAGING_ERROR_NOTIFICATIONS=True):
                with patch('zerver.lib.error_notify.notify_server_error',
                           side_effect=Exception("queue error")):
                    self.handler.emit(record)

            # Test no exc_info
            record.exc_info = None
            report = self.run_handler(record)
            self.assertIn("host", report)
            self.assertIn("user_email", report)
            self.assertIn("message", report)
            self.assertEqual(report["stack_trace"], None)

            # Test arbitrary exceptions from request.user
            record.request.user = None # type: ignore # this field is dynamically added
            with patch("zerver.logging_handlers.traceback.print_exc"):
                report = self.run_handler(record)
            self.assertIn("host", report)
            self.assertIn("user_email", report)
            self.assertIn("message", report)
            self.assertIn("stack_trace", report)
