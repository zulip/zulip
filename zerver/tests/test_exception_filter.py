from django.test import RequestFactory
from django.views.debug import ExceptionReporter

from zerver.filters import ZulipExceptionReporterFilter
from zerver.lib.test_classes import ZulipTestCase


class TestExceptionFilter(ZulipTestCase):
    def test_zulip_filter_masks_sensitive_post_data(self) -> None:
        rf = RequestFactory()
        request = rf.post(
            "/test",
            {
                "password": "sneaky",
                "api_key": "abc123",
                "content": "secret msg",
                "realm_counts": "private",
                "installation_counts": "private",
            },
        )

        filt = ZulipExceptionReporterFilter()
        cleaned = filt.get_post_parameters(request)

        for var in [
            "password",
            "api_key",
            "content",
            "realm_counts",
            "installation_counts",
        ]:
            assert cleaned.get(var) == "**********"

    def test_zulip_filter_removes_settings_from_traceback(self) -> None:
        rf = RequestFactory()
        request = rf.get("/")

        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_type, exc_value, exc_traceback = sys.exc_info()

        filt = ZulipExceptionReporterFilter()
        reporter = ExceptionReporter(request, exc_type, exc_value, exc_traceback, is_email=True)
        reporter.filter = filt
        data = reporter.get_traceback_data()

        for key in ["settings", "filtered_settings", "settings_hidden", "settings_not_a_setting"]:
            value = data.get(key, {})
            assert value == {}, f"Expected {key} to be empty dict, got {value}"
