import orjson

from zerver.lib.test_classes import ZulipTestCase


class TestReport(ZulipTestCase):
    def test_report_csp_violations(self) -> None:
        fixture_data = self.fixture_data("csp_report.json")
        with self.assertLogs(level="WARNING") as warn_logs:
            result = self.client_post(
                "/report/csp_violations", fixture_data, content_type="application/json"
            )
        self.assert_json_success(result)
        self.assertEqual(
            warn_logs.output,
            [
                "WARNING:root:CSP violation in document(''). blocked URI(''), original policy(''), violated directive(''), effective directive(''), disposition(''), referrer(''), status code(''), script sample('')"
            ],
        )

    def test_report_csp_violations_sanitizes_control_characters(self) -> None:
        # The report fields are user-controlled, so non-printable
        # characters must be neutralized before logging to prevent
        # forging log lines or injecting terminal escape sequences. This
        # includes non-ASCII line separators (U+2028/U+2029) and format
        # characters (e.g. the U+202E right-to-left override), not just
        # ASCII control characters.
        payload = {
            "document-uri": "https://example.com/\nWARNING:root:forged log line",
            "blocked-uri": "https://evil.example.com/\r\n\x1b\u2028\u2029\u202e[31mred",
        }
        with self.assertLogs(level="WARNING") as warn_logs:
            result = self.client_post(
                "/report/csp_violations",
                orjson.dumps(payload),
                content_type="application/json",
            )
        self.assert_json_success(result)
        self.assertEqual(
            warn_logs.output,
            [
                (
                    "WARNING:root:CSP violation in document('https://example.com/ WARNING:root:forged log line'). "
                    "blocked URI('https://evil.example.com/      [31mred'), original policy(''), "
                    "violated directive(''), effective directive(''), disposition(''), "
                    "referrer(''), status code(''), script sample('')"
                )
            ],
        )

    def test_report_csp_violations_truncates_long_fields(self) -> None:
        payload = {"document-uri": "a" * 500}
        with self.assertLogs(level="WARNING") as warn_logs:
            result = self.client_post(
                "/report/csp_violations",
                orjson.dumps(payload),
                content_type="application/json",
            )
        self.assert_json_success(result)
        self.assertIn(f"document('{'a' * 200}…')", warn_logs.output[0])
