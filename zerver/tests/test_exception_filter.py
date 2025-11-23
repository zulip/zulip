from __future__ import annotations

import sys

from django.test import RequestFactory, override_settings
from django.views.debug import ExceptionReporter

from zerver.filters import ZulipExceptionReporterFilter
from zerver.lib.test_classes import ZulipTestCase


class TestExceptionFilter(ZulipTestCase):
    def test_zulip_filter_masks_sensitive_post_data(self) -> None:
        """
        Verifies that specific sensitive POST parameters are masked.
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

        for var in [
            "password",
            "api_key",
            "content",
            "realm_counts",
            "installation_counts",
        ]:
            self.assertEqual(cleaned.get(var), "**********")

        self.assertEqual(cleaned.get("normal_field"), "safe")

    def test_exception_reporter_returns_settings_in_dev(self) -> None:
        """
        In non-production, settings should be present and non-empty.
        """
        rf = RequestFactory()
        request = rf.get("/")

        try:
            raise ValueError("test error")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()

        reporter = ExceptionReporter(
            request,
            exc_type,
            exc_value,
            tb,
            is_email=True,
        )
        reporter.filter = ZulipExceptionReporterFilter()

        data = reporter.get_traceback_data()

        self.assertIn("settings", data)
        self.assertIsInstance(data["settings"], dict)
        self.assertNotEqual(data["settings"], {})

    @override_settings(
        PRODUCTION=True,
        DEPLOY_ROOT="/home/zulip/deployments/2024-01-01-00-00-00",
    )
    def test_exception_reporter_omits_settings_in_production(self) -> None:
        """
        In production, settings must be omitted (empty dict).
        """
        rf = RequestFactory()
        request = rf.get("/")

        try:
            raise RuntimeError("production error")
        except RuntimeError:
            exc_type, exc_value, tb = sys.exc_info()

        reporter = ExceptionReporter(
            request,
            exc_type,
            exc_value,
            tb,
            is_email=True,
        )
        reporter.filter = ZulipExceptionReporterFilter()

        data = reporter.get_traceback_data()

        self.assertEqual(data.get("settings"), {})

        html = reporter.get_traceback_html()

        self.assertNotIn("LANGUAGE_CODE", html)
        self.assertNotIn("SECRET_KEY", html)
        self.assertNotIn("DATABASES", html)
