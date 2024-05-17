from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase


class WordPressHookTests(WebhookTestCase):
    CHANNEL_NAME = "wordpress"
    URL_TEMPLATE = "/api/v1/external/wordpress?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "wordpress"

    def test_publish_post(self) -> None:
        expected_topic_name = "WordPress Post"
        expected_message = "New post published:\n* [New Blog Post](http://example.com\n)"

        self.check_webhook(
            "publish_post",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_publish_post_type_not_provided(self) -> None:
        expected_topic_name = "WordPress Post"
        expected_message = "New post published:\n* [New Blog Post](http://example.com\n)"

        self.check_webhook(
            "publish_post_type_not_provided",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_publish_post_no_data_provided(self) -> None:
        # Note: the fixture includes 'hook=publish_post' because it's always added by HookPress
        expected_topic_name = "WordPress notification"
        expected_message = "New post published:\n* [New WordPress post](WordPress post URL)"

        self.check_webhook(
            "publish_post_no_data_provided",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_publish_page(self) -> None:
        expected_topic_name = "WordPress Page"
        expected_message = "New page published:\n* [New Blog Page](http://example.com\n)"

        self.check_webhook(
            "publish_page",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_user_register(self) -> None:
        expected_topic_name = "New Blog Users"
        expected_message = (
            "New blog user registered:\n* **Name**: test_user\n* **Email**: test_user@example.com"
        )

        self.check_webhook(
            "user_register",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_wp_login(self) -> None:
        expected_topic_name = "New Login"
        expected_message = "User testuser logged in."

        self.check_webhook(
            "wp_login",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_unknown_action_no_data(self) -> None:
        # Mimic check_webhook() to manually execute a negative test.
        # Otherwise its call to send_webhook_payload() would assert on the non-success
        # we are testing. The value of result is the error message the webhook should
        # return if no params are sent. The fixture for this test is an empty file.

        # subscribe to the target channel
        self.subscribe(self.test_user, self.CHANNEL_NAME)

        # post to the webhook url
        result = self.client_post(
            self.url,
            self.get_body("unknown_action_no_data"),
            content_type="application/x-www-form-urlencoded",
        )

        # check that we got the expected error message
        self.assert_json_error(result, "Unknown WordPress webhook action: WordPress action")

    def test_unknown_action_no_hook_provided(self) -> None:
        # Similar to unknown_action_no_data, except the fixture contains valid blog post
        # params but without the hook parameter. This should also return an error.

        self.subscribe(self.test_user, self.CHANNEL_NAME)
        result = self.client_post(
            self.url,
            self.get_body("unknown_action_no_hook_provided"),
            content_type="application/x-www-form-urlencoded",
        )

        self.assert_json_error(result, "Unknown WordPress webhook action: WordPress action")

    @override
    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("wordpress", fixture_name, file_type="txt")
