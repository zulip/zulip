from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase


class HerokuHookTests(WebhookTestCase):
    CHANNEL_NAME = "heroku"
    URL_TEMPLATE = "/api/v1/external/heroku?stream={stream}&api_key={api_key}"

    def test_deployment(self) -> None:
        expected_topic_name = "sample-project"
        expected_message = """
user@example.com deployed version 3eb5f44 of [sample-project](http://sample-project.herokuapp.com):

``` quote
  * Example User: Test commit for Deploy Hook 2
```
""".strip()
        self.check_webhook(
            "deploy",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_deployment_multiple_commits(self) -> None:
        expected_topic_name = "sample-project"
        expected_message = """user@example.com deployed version 3eb5f44 of \
[sample-project](http://sample-project.herokuapp.com)
``` quote
  * Example User: Test commit for Deploy Hook
  * Example User: Second test commit for Deploy Hook 2
```"""

        expected_message = """
user@example.com deployed version 3eb5f44 of [sample-project](http://sample-project.herokuapp.com):

``` quote
  * Example User: Test commit for Deploy Hook
  * Example User: Second test commit for Deploy Hook 2
```
""".strip()
        self.check_webhook(
            "deploy_multiple_commits",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    @override
    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("heroku", fixture_name, file_type="txt")
