from zerver.lib.test_classes import ZulipTestCase


class TestReport(ZulipTestCase):
    def test_send_time(self) -> None:
        self.login("hamlet")

        params = dict(
            time=5,
            received=6,
            displayed=7,
            locally_echoed="true",
            rendered_content_disparity="true",
        )

        result = self.client_post("/json/report/send_times", params)
        self.assert_json_success(result)

    def test_narrow_time(self) -> None:
        self.login("hamlet")

        params = dict(
            initial_core=5,
            initial_free=6,
            network=7,
        )

        result = self.client_post("/json/report/narrow_times", params)
        self.assert_json_success(result)

    def test_anonymous_user_narrow_time(self) -> None:
        params = dict(
            initial_core=5,
            initial_free=6,
            network=7,
        )

        result = self.client_post("/json/report/narrow_times", params)
        self.assert_json_success(result)

    def test_unnarrow_time(self) -> None:
        self.login("hamlet")

        params = dict(
            initial_core=5,
            initial_free=6,
        )

        result = self.client_post("/json/report/unnarrow_times", params)
        self.assert_json_success(result)

    def test_anonymous_user_unnarrow_time(self) -> None:
        params = dict(
            initial_core=5,
            initial_free=6,
        )

        result = self.client_post("/json/report/unnarrow_times", params)
        self.assert_json_success(result)

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
