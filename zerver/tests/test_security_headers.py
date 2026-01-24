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

    def test_csp_report_only_header_present(self):
        """
        Verify that Content-Security-Policy-Report-Only header is set.
        """
        response = self.client_get("/")
        self.assertIn("Content-Security-Policy-Report-Only", response.headers)

    def test_csp_report_only_header_value(self):
        """
        Verify that CSP Report-Only header contains expected directives.
        """
        response = self.client_get("/")
        csp = response["Content-Security-Policy-Report-Only"]
        
        # Should contain default-src directive
        self.assertIn("default-src", csp)
        
        # Should contain report-uri directive
        self.assertIn("report-uri", csp)

    def test_x_frame_options_header(self):
        """
        Verify X-Frame-Options header is set to DENY to prevent clickjacking.
        """
        response = self.client_get("/")
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_x_content_type_options_header(self):
        """
        Verify X-Content-Type-Options header prevents MIME-type sniffing.
        """
        response = self.client_get("/")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_referrer_policy_header(self):
        """
        Verify Referrer-Policy header controls referrer information.
        """
        response = self.client_get("/")
        self.assertIn("Referrer-Policy", response.headers)
        # Check it's set to a reasonable value
        self.assertIn("strict-origin-when-cross-origin", response["Referrer-Policy"])

    def test_permissions_policy_header(self):
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

    def test_headers_on_api_endpoint(self):
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

    def test_headers_on_authenticated_page(self):
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

    def test_csp_violations_endpoint_accepts_post(self):
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
        response = self.client_post(
            "/csp-violations",
            json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204)

    def test_csp_violations_endpoint_rejects_get(self):
        """
        Verify /csp-violations returns 405 for GET.
        """
        response = self.client_get("/csp-violations")
        self.assertEqual(response.status_code, 405)
