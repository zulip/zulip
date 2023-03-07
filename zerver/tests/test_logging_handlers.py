import logging
import sys
from functools import wraps
from types import TracebackType
from typing import Callable, Dict, Iterator, NoReturn, Optional, Tuple, Type, Union
from unittest import mock
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.utils.log import AdminEmailHandler
from typing_extensions import Concatenate, ParamSpec

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish
from zerver.logging_handlers import AdminNotifyHandler, HasRequest
from zerver.models import UserProfile

ParamT = ParamSpec("ParamT")
captured_request: Optional[HttpRequest] = None
captured_exc_info: Optional[
    Union[Tuple[Type[BaseException], BaseException, TracebackType], Tuple[None, None, None]]
] = None


def capture_and_throw(
    view_func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]
) -> Callable[Concatenate[HttpRequest, ParamT], NoReturn]:
    @wraps(view_func)
    def wrapped_view(
        request: HttpRequest,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> NoReturn:
        global captured_request
        captured_request = request
        try:
            raise Exception("Request error")
        except Exception as e:
            global captured_exc_info
            captured_exc_info = sys.exc_info()
            raise e

    return wrapped_view


class AdminNotifyHandlerTest(ZulipTestCase):
    logger = logging.getLogger("django")

    def setUp(self) -> None:
        super().setUp()
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
        super().tearDown()

    def get_admin_zulip_handler(self) -> AdminNotifyHandler:
        return [h for h in logging.getLogger("").handlers if isinstance(h, AdminNotifyHandler)][0]

    @patch("zerver.logging_handlers.try_git_describe")
    def test_basic(self, mock_function: MagicMock) -> None:
        mock_function.return_value = None
        """A random exception passes happily through AdminNotifyHandler"""
        handler = self.get_admin_zulip_handler()
        try:
            raise Exception("Testing error!")
        except Exception:
            exc_info = sys.exc_info()
        record = self.logger.makeRecord(
            "name", logging.ERROR, "function", 16, "message", {}, exc_info
        )
        handler.emit(record)

    def simulate_error(self) -> logging.LogRecord:
        self.login("hamlet")
        with patch(
            "zerver.lib.rest.authenticated_json_view", side_effect=capture_and_throw
        ) as view_decorator_patch, self.assertLogs(
            "django.request", level="ERROR"
        ) as request_error_log, self.assertLogs(
            "zerver.middleware.json_error_handler", level="ERROR"
        ) as json_error_handler_log, self.settings(
            TEST_SUITE=False
        ):
            result = self.client_get("/json/users")
            self.assert_json_error(result, "Internal server error", status_code=500)
            view_decorator_patch.assert_called_once()
        self.assertEqual(
            request_error_log.output, ["ERROR:django.request:Internal Server Error: /json/users"]
        )
        self.assertTrue(
            "ERROR:zerver.middleware.json_error_handler:Traceback (most recent call last):"
            in json_error_handler_log.output[0]
        )
        self.assertTrue("Exception: Request error" in json_error_handler_log.output[0])

        record = self.logger.makeRecord(
            "name",
            logging.ERROR,
            "function",
            15,
            "message",
            {},
            captured_exc_info,
            extra={"request": captured_request},
        )
        return record

    def run_handler(self, record: logging.LogRecord) -> Dict[str, object]:
        with patch("zerver.lib.error_notify.notify_server_error") as patched_notify:
            self.handler.emit(record)
            patched_notify.assert_called_once()
            return patched_notify.call_args[0][0]

    @patch("zerver.logging_handlers.try_git_describe")
    def test_long_exception_request(self, mock_function: MagicMock) -> None:
        mock_function.return_value = None
        """A request with no stack and multi-line report.getMessage() is handled properly"""
        record = self.simulate_error()
        record.exc_info = None
        record.msg = "message\nmoremessage\nmore"

        report = self.run_handler(record)
        self.assertIn("user", report)
        assert isinstance(report["user"], dict)
        self.assertIn("user_email", report["user"])
        self.assertIn("user_role", report["user"])
        self.assertIn("message", report)
        self.assertIn("stack_trace", report)
        self.assertEqual(report["stack_trace"], "message\nmoremessage\nmore")
        self.assertEqual(report["message"], "message")

    @patch("zerver.logging_handlers.try_git_describe")
    def test_request(self, mock_function: MagicMock) -> None:
        mock_function.return_value = None
        """A normal request is handled properly"""
        record = self.simulate_error()
        assert isinstance(record, HasRequest)

        report = self.run_handler(record)
        self.assertIn("user", report)
        assert isinstance(report["user"], dict)
        self.assertIn("user_email", report["user"])
        self.assertIn("user_role", report["user"])
        self.assertIn("message", report)
        self.assertIn("stack_trace", report)

        # Test that `add_request_metadata` throwing an exception is fine
        with patch("zerver.logging_handlers.traceback.print_exc"):
            with patch(
                "zerver.logging_handlers.add_request_metadata",
                side_effect=Exception("Unexpected exception!"),
            ):
                report = self.run_handler(record)
        self.assertNotIn("user", report)
        self.assertIn("message", report)
        self.assertEqual(report["stack_trace"], "See /var/log/zulip/errors.log")

        # Check anonymous user is handled correctly
        record.request.user = AnonymousUser()
        report = self.run_handler(record)
        self.assertIn("host", report)
        self.assertIn("user", report)
        assert isinstance(report["user"], dict)
        self.assertIn("user_email", report["user"])
        self.assertIn("user_role", report["user"])
        self.assertIn("message", report)
        self.assertIn("stack_trace", report)

        # Put it back so we continue to test the non-anonymous case
        record.request.user = self.example_user("hamlet")

        # Now simulate a DisallowedHost exception
        with mock.patch.object(
            record.request, "get_host", side_effect=Exception("Get host failure!")
        ) as m:
            report = self.run_handler(record)
            self.assertIn("host", report)
            self.assertIn("user", report)
            assert isinstance(report["user"], dict)
            self.assertIn("user_email", report["user"])
            self.assertIn("user_role", report["user"])
            self.assertIn("message", report)
            self.assertIn("stack_trace", report)
            m.assert_called_once()

        # Test an exception_filter exception
        with patch("zerver.logging_handlers.get_exception_reporter_filter", return_value=15):
            record.request.method = "POST"
            report = self.run_handler(record)
            record.request.method = "GET"
        self.assertIn("host", report)
        self.assertIn("user", report)
        assert isinstance(report["user"], dict)
        self.assertIn("user_email", report["user"])
        self.assertIn("user_role", report["user"])
        self.assertIn("message", report)
        self.assertIn("stack_trace", report)

        # Test the catch-all exception handler doesn't throw
        with patch(
            "zerver.lib.error_notify.notify_server_error", side_effect=Exception("queue error")
        ):
            self.handler.emit(record)
        with mock_queue_publish(
            "zerver.logging_handlers.queue_json_publish", side_effect=Exception("queue error")
        ) as m:
            with patch("logging.warning") as log_mock:
                self.handler.emit(record)
                m.assert_called_once()
                log_mock.assert_called_once_with(
                    "Reporting an exception triggered an exception!", exc_info=True
                )
        with mock_queue_publish("zerver.logging_handlers.queue_json_publish") as m:
            with patch("logging.warning") as log_mock:
                self.handler.emit(record)
                m.assert_called_once()
                log_mock.assert_not_called()

        # Test no exc_info
        record.exc_info = None
        report = self.run_handler(record)
        self.assertIn("host", report)
        self.assertIn("user", report)
        assert isinstance(report["user"], dict)
        self.assertIn("user_email", report["user"])
        self.assertIn("user_role", report["user"])
        self.assertIn("message", report)
        self.assertEqual(report["stack_trace"], "No stack trace available")

        # Test arbitrary exceptions from request.user
        del record.request.user
        with patch("zerver.logging_handlers.traceback.print_exc"):
            report = self.run_handler(record)
        self.assertIn("host", report)
        self.assertIn("user", report)
        assert isinstance(report["user"], dict)
        self.assertIn("user_email", report["user"])
        self.assertIn("user_role", report["user"])
        self.assertIn("message", report)
        self.assertIn("stack_trace", report)
        self.assertEqual(report["user"]["user_email"], None)


class LoggingConfigTest(ZulipTestCase):
    @staticmethod
    def all_loggers() -> Iterator[logging.Logger]:
        # There is no documented API for enumerating the loggers; but the
        # internals of `logging` haven't changed in ages, so just use them.
        for logger in logging.Logger.manager.loggerDict.values():
            if not isinstance(logger, logging.Logger):
                continue
            yield logger

    def test_django_emails_disabled(self) -> None:
        for logger in self.all_loggers():
            # The `handlers` attribute is undocumented, but see comment on
            # `all_loggers`.
            for handler in logger.handlers:
                assert not isinstance(handler, AdminEmailHandler)


class ErrorFiltersTest(ZulipTestCase):
    def test_clean_data_from_query_parameters(self) -> None:
        from zerver.filters import clean_data_from_query_parameters

        self.assertEqual(
            clean_data_from_query_parameters("api_key=abcdz&stream=1"),
            "api_key=******&stream=******",
        )
        self.assertEqual(
            clean_data_from_query_parameters("api_key=abcdz&stream=foo&topic=bar"),
            "api_key=******&stream=******&topic=******",
        )


class RateLimitFilterTest(ZulipTestCase):
    # This logger has special settings configured in
    # test_extra_settings.py.
    logger = logging.getLogger("zulip.test_zulip_admins_handler")

    def test_recursive_filter_handling(self) -> None:
        def mocked_cache_get(key: str) -> int:
            self.logger.error(
                "Log an error to trigger recursive filter() calls in _RateLimitFilter."
            )
            raise Exception

        with patch("zerver.lib.logging_util.cache.get", side_effect=mocked_cache_get) as m:
            self.logger.error("Log an error to trigger initial _RateLimitFilter.filter() call.")
            # cache.get should have only been called once, by the original filter() call:
            m.assert_called_once()
