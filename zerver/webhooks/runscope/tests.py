from mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase

class RunscopeHookTests(WebhookTestCase):
    STREAM_NAME = 'runscope'
    URL_TEMPLATE = "/api/v1/external/runscope?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'runscope'

    def test_pass_payload(self) -> None:
        expected_subject = u"Wooly Snow: Zulip Integration"
        expected_message = u"""API test for `Wooly Snow: Zulip Integration` completed! [View the results](https://www.runscope.com/radar/pmsim6ddzfaw/2ed4267a-6338-44ff-9d5e-400465080ab5/results/d6e39045-c571-4638-803f-ec196cef9790), [edit the test](https://www.runscope.com/radar/pmsim6ddzfaw/2ed4267a-6338-44ff-9d5e-400465080ab5) or [rerun the tests](https://api.runscope.com/radar/26206a81-360f-476e-9c93-ffa8bc79f7e8/trigger)
 * **Status**: Passed :thumbs_up:
 * **Environment**: Test Settings
 * **Team Name**: Zulip
 * **Location**: US Virginia - None
 * **Total Response Time**: 20 ms
 * **Requests Executed**: 2
 * **Assertions Passed**: 2 of 2
 * **Scripts Passed**: 0 of 0"""
        self.send_and_test_stream_message('test_pass_payload', expected_subject, expected_message)

    def test_failed_payload(self) -> None:
        expected_subject = u"Wooly Snow: Zulip Integration"
        expected_message = u"""API test for `Wooly Snow: Zulip Integration` completed! [View the results](https://www.runscope.com/radar/pmsim6ddzfaw/2ed4267a-6338-44ff-9d5e-400465080ab5/results/20be1051-4f09-4261-8a6e-254d3413e6c0), [edit the test](https://www.runscope.com/radar/pmsim6ddzfaw/2ed4267a-6338-44ff-9d5e-400465080ab5) or [rerun the tests](https://api.runscope.com/radar/26206a81-360f-476e-9c93-ffa8bc79f7e8/trigger)
 * **Status**: Failed
 * **Environment**: Test Settings
 * **Team Name**: Zulip
 * **Location**: US Virginia - None
 * **Total Response Time**: 10 ms
 * **Requests Executed**: 2
 * **Assertions Passed**: 1 of 2
 * **Scripts Passed**: 0 of 0"""
        self.send_and_test_stream_message('test_failed_payload', expected_subject, expected_message)

    def test_specific_topic(self) -> None:
        self.url = self.build_webhook_url(topic="This%20topic%20is%20specific%21")
        expected_subject = u"This topic is specific!"
        expected_message = u"""API test for `Wooly Snow: Zulip Integration` completed! [View the results](https://www.runscope.com/radar/pmsim6ddzfaw/2ed4267a-6338-44ff-9d5e-400465080ab5/results/d6e39045-c571-4638-803f-ec196cef9790), [edit the test](https://www.runscope.com/radar/pmsim6ddzfaw/2ed4267a-6338-44ff-9d5e-400465080ab5) or [rerun the tests](https://api.runscope.com/radar/26206a81-360f-476e-9c93-ffa8bc79f7e8/trigger)
 * **Status**: Passed :thumbs_up:
 * **Environment**: Test Settings
 * **Team Name**: Zulip
 * **Location**: US Virginia - None
 * **Total Response Time**: 20 ms
 * **Requests Executed**: 2
 * **Assertions Passed**: 2 of 2
 * **Scripts Passed**: 0 of 0"""
        self.send_and_test_stream_message('test_pass_payload', expected_subject, expected_message)

    @patch('zerver.webhooks.runscope.view.check_send_stream_message')
    def test_only_on_ignore(self, check_send_stream_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url(only_on="fail")
        payload = self.get_body('test_pass_payload')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_stream_message_mock.called)
        self.assert_json_success(result)

    def test_only_on_message(self) -> None:
        self.url = self.build_webhook_url(topic="This%20topic%20is%20specific%21")
        expected_subject = u"This topic is specific!"
        expected_message = u"""API test for `Wooly Snow: Zulip Integration` completed! [View the results](https://www.runscope.com/radar/pmsim6ddzfaw/2ed4267a-6338-44ff-9d5e-400465080ab5/results/d6e39045-c571-4638-803f-ec196cef9790), [edit the test](https://www.runscope.com/radar/pmsim6ddzfaw/2ed4267a-6338-44ff-9d5e-400465080ab5) or [rerun the tests](https://api.runscope.com/radar/26206a81-360f-476e-9c93-ffa8bc79f7e8/trigger)
 * **Status**: Passed :thumbs_up:
 * **Environment**: Test Settings
 * **Team Name**: Zulip
 * **Location**: US Virginia - None
 * **Total Response Time**: 20 ms
 * **Requests Executed**: 2
 * **Assertions Passed**: 2 of 2
 * **Scripts Passed**: 0 of 0"""
        self.send_and_test_stream_message('test_pass_payload', expected_subject, expected_message)
