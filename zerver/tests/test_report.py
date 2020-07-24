from typing import Any, Dict
from unittest import mock

import ujson
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase


def fix_params(raw_params: Dict[str, Any]) -> Dict[str, str]:
    # A few of our few legacy endpoints need their
    # individual parameters serialized as JSON.
    return {k: ujson.dumps(v) for k, v in raw_params.items()}

class TestReport(ZulipTestCase):
    @override_settings(BROWSER_ERROR_REPORTING=True)
    def test_report_error(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)
        self.make_stream('errors', user.realm)

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
            side_effect=KeyError('foo'),
        )
        with publish_mock as m, subprocess_mock:
            result = self.client_post("/json/report/error", params)
        self.assert_json_success(result)

        report = m.call_args[0][1]['report']
        for k in set(params) - {'ui_message', 'more_info'}:
            self.assertEqual(report[k], params[k])

        self.assertEqual(report['more_info'], dict(foo='bar', draft_content="'**xxxxx**'"))
        self.assertEqual(report['user_email'], user.delivery_email)

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
