# -*- coding: utf-8 -*-

from typing import Any, Callable, Dict, Iterable, List, Tuple

from django.test import override_settings
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.utils import statsd

import mock
import ujson

def fix_params(raw_params: Dict[str, Any]) -> Dict[str, str]:
    # A few of our few legacy endpoints need their
    # individual parameters serialized as JSON.
    return {k: ujson.dumps(v) for k, v in raw_params.items()}

class StatsMock:
    def __init__(self, settings: Callable[..., Any]) -> None:
        self.settings = settings
        self.real_impl = statsd
        self.func_calls = []  # type: List[Tuple[str, Iterable[Any]]]

    def __getattr__(self, name: str) -> Callable[..., Any]:
        def f(*args: Any) -> None:
            with self.settings(STATSD_HOST=''):
                getattr(self.real_impl, name)(*args)
            self.func_calls.append((name, args))

        return f

class TestReport(ZulipTestCase):
    def test_send_time(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)

        params = dict(
            time=5,
            received=6,
            displayed=7,
            locally_echoed='true',
            rendered_content_disparity='true',
        )

        stats_mock = StatsMock(self.settings)
        with mock.patch('zerver.views.report.statsd', wraps=stats_mock):
            result = self.client_post("/json/report/send_times", params)
        self.assert_json_success(result)

        expected_calls = [
            ('timing', ('endtoend.send_time.zulip', 5)),
            ('timing', ('endtoend.receive_time.zulip', 6)),
            ('timing', ('endtoend.displayed_time.zulip', 7)),
            ('incr', ('locally_echoed',)),
            ('incr', ('render_disparity',)),
        ]
        self.assertEqual(stats_mock.func_calls, expected_calls)

    def test_narrow_time(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)

        params = dict(
            initial_core=5,
            initial_free=6,
            network=7,
        )

        stats_mock = StatsMock(self.settings)
        with mock.patch('zerver.views.report.statsd', wraps=stats_mock):
            result = self.client_post("/json/report/narrow_times", params)
        self.assert_json_success(result)

        expected_calls = [
            ('timing', ('narrow.initial_core.zulip', 5)),
            ('timing', ('narrow.initial_free.zulip', 6)),
            ('timing', ('narrow.network.zulip', 7)),
        ]
        self.assertEqual(stats_mock.func_calls, expected_calls)

    def test_unnarrow_time(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)

        params = dict(
            initial_core=5,
            initial_free=6,
        )

        stats_mock = StatsMock(self.settings)
        with mock.patch('zerver.views.report.statsd', wraps=stats_mock):
            result = self.client_post("/json/report/unnarrow_times", params)
        self.assert_json_success(result)

        expected_calls = [
            ('timing', ('unnarrow.initial_core.zulip', 5)),
            ('timing', ('unnarrow.initial_free.zulip', 6)),
        ]
        self.assertEqual(stats_mock.func_calls, expected_calls)

    @override_settings(BROWSER_ERROR_REPORTING=True)
    def test_report_error(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)

        params = fix_params(dict(
            message='hello',
            stacktrace='trace',
            ui_message=True,
            user_agent='agent',
            href='href',
            log='log',
            more_info=dict(foo='bar', draft_content="**draft**"),
        ))

        publish_mock = mock.patch('zerver.views.report.queue_json_publish')
        subprocess_mock = mock.patch(
            'zerver.views.report.subprocess.check_output',
            side_effect=KeyError('foo')
        )
        with publish_mock as m, subprocess_mock:
            result = self.client_post("/json/report/error", params)
        self.assert_json_success(result)

        report = m.call_args[0][1]['report']
        for k in set(params) - set(['ui_message', 'more_info']):
            self.assertEqual(report[k], params[k])

        self.assertEqual(report['more_info'], dict(foo='bar', draft_content="'**xxxxx**'"))
        self.assertEqual(report['user_email'], email)

        # Teset with no more_info
        del params['more_info']
        with publish_mock as m, subprocess_mock:
            result = self.client_post("/json/report/error", params)
        self.assert_json_success(result)

        with self.settings(BROWSER_ERROR_REPORTING=False):
            result = self.client_post("/json/report/error", params)
        self.assert_json_success(result)

        # If js_source_map is present, then the stack trace should be annotated.
        # DEVELOPMENT=False and TEST_SUITE=False are necessary to ensure that
        # js_source_map actually gets instantiated.
        with \
                self.settings(DEVELOPMENT=False, TEST_SUITE=False), \
                mock.patch('zerver.lib.unminify.SourceMap.annotate_stacktrace') as annotate:
            result = self.client_post("/json/report/error", params)
        self.assert_json_success(result)
        # fix_params (see above) adds quotes when JSON encoding.
        annotate.assert_called_once_with('"trace"')

        # Now test without authentication.
        self.logout()
        with \
                self.settings(DEVELOPMENT=False, TEST_SUITE=False), \
                mock.patch('zerver.lib.unminify.SourceMap.annotate_stacktrace') as annotate:
            result = self.client_post("/json/report/error", params)
        self.assert_json_success(result)

    def test_report_csp_violations(self) -> None:
        fixture_data = self.fixture_data('csp_report.json')
        result = self.client_post("/report/csp_violations", fixture_data, content_type="application/json")
        self.assert_json_success(result)
