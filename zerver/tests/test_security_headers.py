"""
Tests for SecurityHeadersMiddleware and CSP violations endpoint.

Verifies that security headers are correctly set on HTTP responses
and that /csp-violations accepts and logs CSP reports.
Related to: https://github.com/zulip/zulip/issues/11835
"""

import json

from zerver.lib.test_classes import ZulipTestCase


class SecurityHeadersTest(ZulipTestCase):
    """
    Tests for SecurityHeadersMiddleware.

    Verifies that security headers are correctly set on HTTP responses.
    """

    def test_csp_report_only_header_present(self) -> None:
        """
        Verify that Content-Security-Policy-Report-Only header is set.
        """
        response = self.client_get("/")
        self.assertIn("Content-Security-Policy-Report-Only", response.headers)

    def test_csp_report_only_header_value(self) -> None:
        """
        Verify that CSP Report-Only header contains expected directives.
        """
        response = self.client_get("/")
        csp = response["Content-Security-Policy-Report-Only"]

        # Should contain default-src directive
        self.assertIn("default-src", csp)

        # Should contain report-uri directive
        self.assertIn("report-uri", csp)

    def test_x_frame_options_header(self) -> None:
        """
        Verify X-Frame-Options header is set to DENY to prevent clickjacking.
        """
        response = self.client_get("/")
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_x_content_type_options_header(self) -> None:
        """
        Verify X-Content-Type-Options header prevents MIME-type sniffing.
        """
        response = self.client_get("/")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_referrer_policy_header(self) -> None:
        """
        Verify Referrer-Policy header controls referrer information.
        """
        response = self.client_get("/")
        self.assertIn("Referrer-Policy", response.headers)
        # Check it's set to a reasonable value
        self.assertIn("strict-origin-when-cross-origin", response["Referrer-Policy"])

    def test_permissions_policy_header(self) -> None:
        """
        Verify Permissions-Policy header restricts browser features.
        """
        response = self.client_get("/")
        self.assertIn("Permissions-Policy", response.headers)

        permissions = response["Permissions-Policy"]
        # Should restrict camera, microphone, geolocation, payment
        self.assertIn("camera=()", permissions)
        self.assertIn("microphone=()", permissions)
        self.assertIn("geolocation=()", permissions)
        self.assertIn("payment=()", permissions)

    def test_headers_on_api_endpoint(self) -> None:
        """
        Verify security headers are present on API endpoints.
        """
        # Login first
        user = self.example_user("hamlet")
        self.login_user(user)

        # Make API request
        response = self.client_get("/api/v1/messages")

        # Headers should still be present
        self.assertIn("X-Frame-Options", response.headers)
        self.assertIn("X-Content-Type-Options", response.headers)

    def test_headers_on_authenticated_page(self) -> None:
        """
        Verify security headers are present on authenticated pages.
        """
        user = self.example_user("hamlet")
        self.login_user(user)

        response = self.client_get("/")

        # All security headers should be present
        required_headers = [
            "Content-Security-Policy-Report-Only",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "Referrer-Policy",
            "Permissions-Policy",
        ]

        for header in required_headers:
            self.assertIn(header, response.headers, f"Missing header: {header}")

    def test_csp_violations_endpoint_accepts_post(self) -> None:
        """
        Verify /csp-violations accepts POST with CSP report JSON and returns 204.
        """
        payload = {
            "csp-report": {
                "document-uri": "http://localhost:9991/",
                "violated-directive": "script-src",
                "blocked-uri": "http://example.com/script.js",
            }
        }
        with self.assertLogs("zulip.csp_violations", level="INFO") as logs:
            response = self.client_post(
                "/csp-violations",
                json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 204)
            # Verify the log was captured
            self.assert_length(logs.records, 1)
            self.assertIn("CSP violation", logs.output[0])

    def test_csp_violations_endpoint_rejects_get(self) -> None:
        """
        Verify /csp-violations returns 405 for GET.
        """
        response = self.client_get("/csp-violations")
        self.assertEqual(response.status_code, 405)

    def test_csp_violations_endpoint_invalid_json(self) -> None:
        """
        Verify /csp-violations handles invalid JSON gracefully.
        """
        with self.assertLogs("zulip.csp_violations", level="WARNING") as logs:
            response = self.client_post(
                "/csp-violations",
                "not valid json",
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 204)
            self.assert_length(logs.records, 1)
            self.assertIn("invalid JSON", logs.output[0])

    def test_csp_violations_endpoint_missing_csp_report_key(self) -> None:
        """
        Verify /csp-violations handles missing 'csp-report' key gracefully.
        """
        payload = {"not-csp-report": {"some": "data"}}
        with self.assertLogs("zulip.csp_violations", level="WARNING") as logs:
            response = self.client_post(
                "/csp-violations",
                json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 204)
            self.assert_length(logs.records, 1)
            self.assertIn("missing or invalid 'csp-report' key", logs.output[0])

    def test_csp_violations_endpoint_invalid_csp_report_type(self) -> None:
        """
        Verify /csp-violations handles invalid 'csp-report' type (not dict) gracefully.
        """
        payload = {"csp-report": "not a dict"}
        with self.assertLogs("zulip.csp_violations", level="WARNING") as logs:
            response = self.client_post(
                "/csp-violations",
                json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 204)
            self.assert_length(logs.records, 1)
            self.assertIn("missing or invalid 'csp-report' key", logs.output[0])
