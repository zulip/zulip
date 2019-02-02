# -*- coding: utf-8 -*-

import logging
import sys

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.test import TestCase
from django.utils.log import AdminEmailHandler
from functools import wraps
from mock import MagicMock, patch
from mypy_extensions import NoReturn
from typing import Any, Callable, Dict, Iterator, Optional, Tuple, Type
from types import TracebackType

from zerver.lib.types import ViewFuncT
from zerver.lib.test_classes import ZulipTestCase
from zerver.logging_handlers import AdminNotifyHandler

captured_request = None  # type: Optional[HttpRequest]
captured_exc_info = None  # type: Tuple[Optional[Type[BaseException]], Optional[BaseException], Optional[TracebackType]]
def capture_and_throw(domain: Optional[str]=None) -> Callable[[ViewFuncT], ViewFuncT]:
    def wrapper(view_func: ViewFuncT) -> ViewFuncT:
        @wraps(view_func)
        def wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> NoReturn:
            global captured_request
            captured_request = request
            try:
                raise Exception("Request error")
            except Exception as e:
                global captured_exc_info
                captured_exc_info = sys.exc_info()
                raise e
        return wrapped_view  # type: ignore # https://github.com/python/mypy/issues/1927
    return wrapper

class AdminNotifyHandlerTest(ZulipTestCase):
    logger = logging.getLogger('django')

    def setUp(self) -> None:
        self.handler = AdminNotifyHandler()
        # Prevent the exceptions we're going to raise from being printed
        # You may want to disable this when debugging tests
        settings.LOGGING_ENABLED = False

        global captured_exc_info
        global captured_request
        captured_request = None
        captured_exc_info = None

    def tearDown(self) -> None:
        settings.LOGGING_ENABLED = True

    def get_admin_zulip_handler(self) -> AdminNotifyHandler:
        return [
            h for h in logging.getLogger('').handlers
            if isinstance(h, AdminNotifyHandler)
        ][0]

    @patch('zerver.logging_handlers.try_git_describe')
    def test_basic(self, mock_function: MagicMock) -> None:
        mock_function.return_value = None
        """A random exception passes happily through AdminNotifyHandler"""
        handler = self.get_admin_zulip_handler()
        try:
            raise Exception("Testing Error!")
        except Exception:
            exc_info = sys.exc_info()
        record = self.logger.makeRecord('name', logging.ERROR, 'function', 16,
                                        'message', {}, exc_info)
        handler.emit(record)

    def simulate_error(self) -> logging.LogRecord:
        email = self.example_email('hamlet')
        self.login(email)
        with patch("zerver.decorator.rate_limit") as rate_limit_patch:
            rate_limit_patch.side_effect = capture_and_throw
            result = self.client_get("/json/users")
            self.assert_json_error(result, "Internal server error", status_code=500)
            rate_limit_patch.assert_called_once()

        record = self.logger.makeRecord('name', logging.ERROR, 'function', 15,
                                        'message', {}, captured_exc_info)
        record.request = captured_request  # type: ignore # this field is dynamically added
        return record

    def run_handler(self, record: logging.LogRecord) -> Dict[str, Any]:
        with patch('zerver.lib.error_notify.notify_server_error') as patched_notify:
            self.handler.emit(record)
            patched_notify.assert_called_once()
            return patched_notify.call_args[0][0]

    @patch('zerver.logging_handlers.try_git_describe')
    def test_long_exception_request(self, mock_function: MagicMock) -> None:
        mock_function.return_value = None
        """A request with no stack and multi-line report.getMessage() is handled properly"""
        record = self.simulate_error()
        record.exc_info = None
        record.msg = 'message\nmoremesssage\nmore'

        report = self.run_handler(record)
        self.assertIn("user_email", report)
        self.assertIn("message", report)
        self.assertIn("stack_trace", report)
        self.assertEqual(report['stack_trace'], 'message\nmoremesssage\nmore')
        self.assertEqual(report['message'], 'message')

    @patch('zerver.logging_handlers.try_git_describe')
    def test_request(self, mock_function: MagicMock) -> None:
        mock_function.return_value = None
        """A normal request is handled properly"""
        record = self.simulate_error()

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
        record.request.user = AnonymousUser()  # type: ignore # this field is dynamically added
        report = self.run_handler(record)
        self.assertIn("host", report)
        self.assertIn("user_email", report)
        self.assertIn("message", report)
        self.assertIn("stack_trace", report)

        # Now simulate a DisallowedHost exception
        def get_host_error() -> None:
            raise Exception("Get Host Failure!")
        orig_get_host = record.request.get_host  # type: ignore # this field is dynamically added
        record.request.get_host = get_host_error  # type: ignore # this field is dynamically added
        report = self.run_handler(record)
        record.request.get_host = orig_get_host  # type: ignore # this field is dynamically added
        self.assertIn("host", report)
        self.assertIn("user_email", report)
        self.assertIn("message", report)
        self.assertIn("stack_trace", report)

        # Test an exception_filter exception
        with patch("zerver.logging_handlers.get_exception_reporter_filter",
                   return_value=15):
            record.request.method = "POST"  # type: ignore # this field is dynamically added
            report = self.run_handler(record)
            record.request.method = "GET"  # type: ignore # this field is dynamically added
        self.assertIn("host", report)
        self.assertIn("user_email", report)
        self.assertIn("message", report)
        self.assertIn("stack_trace", report)

        # Test the catch-all exception handler doesn't throw
        with patch('zerver.lib.error_notify.notify_server_error',
                   side_effect=Exception("queue error")):
            self.handler.emit(record)
        with self.settings(STAGING_ERROR_NOTIFICATIONS=False):
            with patch('zerver.logging_handlers.queue_json_publish',
                       side_effect=Exception("queue error")):
                self.handler.emit(record)

        # Test no exc_info
        record.exc_info = None
        report = self.run_handler(record)
        self.assertIn("host", report)
        self.assertIn("user_email", report)
        self.assertIn("message", report)
        self.assertEqual(report["stack_trace"], 'No stack trace available')

        # Test arbitrary exceptions from request.user
        record.request.user = None  # type: ignore # this field is dynamically added
        with patch("zerver.logging_handlers.traceback.print_exc"):
            report = self.run_handler(record)
        self.assertIn("host", report)
        self.assertIn("user_email", report)
        self.assertIn("message", report)
        self.assertIn("stack_trace", report)

class LoggingConfigTest(TestCase):
    @staticmethod
    def all_loggers() -> Iterator[logging.Logger]:
        # There is no documented API for enumerating the loggers; but the
        # internals of `logging` haven't changed in ages, so just use them.
        loggerDict = logging.Logger.manager.loggerDict  # type: ignore
        for logger in loggerDict.values():
            if not isinstance(logger, logging.Logger):
                continue
            yield logger

    def test_django_emails_disabled(self) -> None:
        for logger in self.all_loggers():
            # The `handlers` attribute is undocumented, but see comment on
            # `all_loggers`.
            for handler in logger.handlers:
                assert not isinstance(handler, AdminEmailHandler)

class ErrorFiltersTest(TestCase):
    def test_clean_data_from_query_parameters(self) -> None:
        from zerver.filters import clean_data_from_query_parameters
        self.assertEqual(clean_data_from_query_parameters("api_key=abcdz&stream=1"),
                         "api_key=******&stream=******")
        self.assertEqual(clean_data_from_query_parameters("api_key=abcdz&stream=foo&topic=bar"),
                         "api_key=******&stream=******&topic=******")
