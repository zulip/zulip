from zerver.lib.test_classes import WebhookTestCase


class RaygunHookTests(WebhookTestCase):
    def test_status_changed_message(self) -> None:
        expected_topic_name = "test"
        expected_message = """
[Error](https://app.raygun.com/error-url) status changed to **Ignored** by Emma Cat:
* **Timestamp**: <time:1970-01-28T01:49:36+00:00>
* **Application details**: [Best App](http://app.raygun.io/application-url)
""".strip()

        self.check_webhook(
            "error_status_changed",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_comment_added_to_error_message(self) -> None:
        expected_topic_name = "test"
        expected_message = """
Anita Peacock commented on [Error](https://app.raygun.com/error-url):

``` quote
Ignoring these errors
```
* **Timestamp**: <time:1970-01-28T01:49:36+00:00>
* **Application details**: [application name](http://app.raygun.io/application-url)
""".strip()

        self.check_webhook(
            "comment_added_to_error",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_error_assigned_to_user_message(self) -> None:
        expected_topic_name = "test"
        expected_message = """
Amy Loondon assigned [Error](https://app.raygun.com/error-url) to Kyle Kenny:
* **Timestamp**: <time:1970-01-28T01:49:36+00:00>
* **Application details**: [application name](http://app.raygun.io/application-url)
""".strip()

        self.check_webhook(
            "error_assigned_to_user",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_one_minute_followup_error_message(self) -> None:
        expected_topic_name = "test"
        expected_message = """
One minute [follow-up error](http://app.raygun.io/error-url):
* **First occurred**: <time:1970-01-28T01:49:36+00:00>
* **Last occurred**: <time:1970-01-28T01:49:36+00:00>
* 1 users affected with 1 total occurrences
* **Application details**: [application name](http://app.raygun.io/application-url)
""".strip()

        self.check_webhook(
            "one_minute_followup_error",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_hourly_followup_error_message(self) -> None:
        expected_topic_name = "test"
        expected_message = """
Hourly [follow-up error](http://app.raygun.io/error-url):
* **First occurred**: <time:1970-01-28T01:49:36+00:00>
* **Last occurred**: <time:1970-01-28T01:49:36+00:00>
* 1 users affected with 1 total occurrences
* **Application details**: [application name](http://app.raygun.io/application-url)
""".strip()

        self.check_webhook(
            "hourly_followup_error",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_new_error_message(self) -> None:
        expected_topic_name = "test"
        expected_message = """
New [Error](http://app.raygun.io/error-url) occurred:
* **First occurred**: <time:1970-01-28T01:49:36+00:00>
* **Last occurred**: <time:1970-01-28T01:49:36+00:00>
* 1 users affected with 1 total occurrences
* **Tags**: test, error-page, v1.0.1, env:staging
* **Affected user**: a9b7d8...33846
* **pageName**: Error Page
* **userLoggedIn**: True
* **Application details**: [application name](http://app.raygun.io/application-url)
""".strip()

        self.check_webhook(
            "new_error",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_reoccurred_error_message(self) -> None:
        expected_topic_name = "test"
        expected_message = """
[Error](http://app.raygun.io/error-url) reoccurred:
* **First occurred**: <time:1970-01-28T01:49:36+00:00>
* **Last occurred**: <time:1970-01-28T01:49:36+00:00>
* 1 users affected with 1 total occurrences
* **Tags**: test, error-page, v1.0.1, env:staging
* **Affected user**: a9b7d8...33846
* **pageName**: Error Page
* **userLoggedIn**: True
* **Application details**: [application name](http://app.raygun.io/application-url)
""".strip()

        self.check_webhook(
            "reoccurred_error",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
