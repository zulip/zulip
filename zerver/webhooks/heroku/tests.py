# -*- coding: utf-8 -*-

from zerver.lib.test_classes import WebhookTestCase

class HerokuHookTests(WebhookTestCase):
    STREAM_NAME = 'heroku'
    URL_TEMPLATE = u"/api/v1/external/heroku?stream={stream}&api_key={api_key}"

    def test_deployment(self) -> None:
        expected_topic = "sample-project"
        expected_message = u"""user@example.com deployed version 3eb5f44 of \
[sample-project](http://sample-project.herokuapp.com)
``` quote
  * Example User: Test commit for Deploy Hook 2
```"""
        self.send_and_test_stream_message('deploy', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_deployment_multiple_commits(self) -> None:
        expected_topic = "sample-project"
        expected_message = u"""user@example.com deployed version 3eb5f44 of \
[sample-project](http://sample-project.herokuapp.com)
``` quote
  * Example User: Test commit for Deploy Hook
  * Example User: Second test commit for Deploy Hook 2
```"""
        self.send_and_test_stream_message('deploy_multiple_commits', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("heroku", fixture_name, file_type="txt")
