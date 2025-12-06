from __future__ import annotations

import sys

from django.conf import settings
from django.test import RequestFactory
from django.views.debug import ExceptionReporter

from zerver.filters import ZulipExceptionReporterFilter
from zerver.lib.test_classes import ZulipTestCase


class TestExceptionFilter(ZulipTestCase):
    def test_zulip_filter_masks_sensitive_post_data(self) -> None:
        """
        Verifies that specific sensitive POST parameters are masked with **********.
        """
        rf = RequestFactory()
        request = rf.post(
            "/test",
            {
                "password": "sneaky",
                "api_key": "abc123",
                "content": "secret msg",
                "realm_counts": "private",
                "installation_counts": "private",
                "normal_field": "safe",
            },
        )

        filt = ZulipExceptionReporterFilter()
        cleaned = filt.get_post_parameters(request)

        # Check sensitive fields are masked
        for var in [
            "password",
            "api_key",
            "content",
            "realm_counts",
            "installation_counts",
        ]:
            self.assertEqual(
                cleaned.get(var),
                "**********",
                f"Field '{var}' was not masked correctly",
            )

        self.assertEqual(cleaned.get("normal_field"), "safe")

    def test_zulip_filter_removes_settings_from_context(self) -> None:
        """
        Verifies that the filter returns an empty dict for settings.
        """
        rf = RequestFactory()
        request = rf.get("/")

        try:
            raise ValueError("test error")
        except ValueError:
            exc_type, exc_value, exc_traceback = sys.exc_info()

        reporter = ExceptionReporter(
            request,
            exc_type,
            exc_value,
            exc_traceback,
            is_email=True,
        )
        reporter.filter = ZulipExceptionReporterFilter()

        data = reporter.get_traceback_data()

        # Update Expectation: Expect empty dict {}
        self.assertEqual(data.get("settings"), {}, "Settings should be an empty dict")

    def test_integration_exception_reporter_hides_sensitive_data(self) -> None:
        """
        Integration test: Verifies configuration and ensures no sensitive
        settings leak into the HTML.
        """
        # 1. Verify Configuration
        self.assertEqual(
            settings.DEFAULT_EXCEPTION_REPORTER_FILTER,
            "zerver.filters.ZulipExceptionReporterFilter",
            "Django is not configured to use the Zulip exception filter",
        )

        # 2. Setup Request
        rf = RequestFactory()
        request = rf.get("/trigger/500")

        try:
            _ = 1 / 0
        except ZeroDivisionError:
            exc_type, exc_value, tb = sys.exc_info()

        # 3. Instantiate Reporter
        reporter = ExceptionReporter(request, exc_type, exc_value, tb, is_email=True)
        self.assertIsInstance(reporter.filter, ZulipExceptionReporterFilter)

        # 4. Generate HTML
        html = reporter.get_traceback_html()

        # 5. Security Check: Ensure sensitive variables are NOT in the HTML.
        # We assume 'settings_not_a_setting' would exist if the global settings
        # were fully dumped.
        self.assertNotIn("settings_not_a_setting", html)
