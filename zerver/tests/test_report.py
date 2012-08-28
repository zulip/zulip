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
