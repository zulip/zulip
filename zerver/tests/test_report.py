from typing import Callable, ContextManager, List, Tuple
from unittest import mock

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.utils import statsd


class StatsMock:
    def __init__(self, settings: Callable[..., ContextManager[None]]) -> None:
        self.settings = settings
        self.real_impl = statsd
        self.func_calls: List[Tuple[str, Tuple[object, ...]]] = []

    def __getattr__(self, name: str) -> Callable[..., None]:
        def f(*args: object) -> None:
            with self.settings(STATSD_HOST=""):
                getattr(self.real_impl, name)(*args)
            self.func_calls.append((name, args))

        return f


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

        stats_mock = StatsMock(self.settings)
        with mock.patch("zerver.views.report.statsd", wraps=stats_mock):
            result = self.client_post("/json/report/send_times", params)
        self.assert_json_success(result)

        expected_calls = [
            ("timing", ("endtoend.send_time.zulip", 5)),
            ("timing", ("endtoend.receive_time.zulip", 6)),
            ("timing", ("endtoend.displayed_time.zulip", 7)),
            ("incr", ("locally_echoed",)),
            ("incr", ("render_disparity",)),
        ]
        self.assertEqual(stats_mock.func_calls, expected_calls)

    def test_narrow_time(self) -> None:
        self.login("hamlet")

        params = dict(
            initial_core=5,
            initial_free=6,
            network=7,
        )

        stats_mock = StatsMock(self.settings)
        with mock.patch("zerver.views.report.statsd", wraps=stats_mock):
            result = self.client_post("/json/report/narrow_times", params)
        self.assert_json_success(result)

        expected_calls = [
            ("timing", ("narrow.initial_core.zulip", 5)),
            ("timing", ("narrow.initial_free.zulip", 6)),
            ("timing", ("narrow.network.zulip", 7)),
        ]
        self.assertEqual(stats_mock.func_calls, expected_calls)

    def test_anonymous_user_narrow_time(self) -> None:
        params = dict(
            initial_core=5,
            initial_free=6,
            network=7,
        )

        stats_mock = StatsMock(self.settings)
        with mock.patch("zerver.views.report.statsd", wraps=stats_mock):
            result = self.client_post("/json/report/narrow_times", params)
        self.assert_json_success(result)

        expected_calls = [
            ("timing", ("narrow.initial_core.zulip", 5)),
            ("timing", ("narrow.initial_free.zulip", 6)),
            ("timing", ("narrow.network.zulip", 7)),
        ]
        self.assertEqual(stats_mock.func_calls, expected_calls)

    def test_unnarrow_time(self) -> None:
        self.login("hamlet")

        params = dict(
            initial_core=5,
            initial_free=6,
        )

        stats_mock = StatsMock(self.settings)
        with mock.patch("zerver.views.report.statsd", wraps=stats_mock):
            result = self.client_post("/json/report/unnarrow_times", params)
        self.assert_json_success(result)

        expected_calls = [
            ("timing", ("unnarrow.initial_core.zulip", 5)),
            ("timing", ("unnarrow.initial_free.zulip", 6)),
        ]
        self.assertEqual(stats_mock.func_calls, expected_calls)

    def test_anonymous_user_unnarrow_time(self) -> None:
        params = dict(
            initial_core=5,
            initial_free=6,
        )

        stats_mock = StatsMock(self.settings)
        with mock.patch("zerver.views.report.statsd", wraps=stats_mock):
            result = self.client_post("/json/report/unnarrow_times", params)
        self.assert_json_success(result)

        expected_calls = [
            ("timing", ("unnarrow.initial_core.zulip", 5)),
            ("timing", ("unnarrow.initial_free.zulip", 6)),
        ]
        self.assertEqual(stats_mock.func_calls, expected_calls)

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
