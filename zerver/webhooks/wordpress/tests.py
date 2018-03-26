# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase
from zerver.models import get_realm, get_user

class WordPressHookTests(WebhookTestCase):
    STREAM_NAME = 'wordpress'
    URL_TEMPLATE = "/api/v1/external/wordpress?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'wordpress'

    def test_publish_post(self) -> None:

        expected_topic = u"WordPress Post"
        expected_message = u"New post published.\n[New Blog Post](http://example.com\n)"

        self.send_and_test_stream_message('publish_post', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_publish_post_type_not_provided(self) -> None:

        expected_topic = u"WordPress Post"
        expected_message = u"New post published.\n[New Blog Post](http://example.com\n)"

        self.send_and_test_stream_message('publish_post_type_not_provided',
                                          expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_publish_post_no_data_provided(self) -> None:

        # Note: the fixture includes 'hook=publish_post' because it's always added by HookPress
        expected_topic = u"WordPress Notification"
        expected_message = u"New post published.\n" + "[New WordPress Post](WordPress Post URL)"

        self.send_and_test_stream_message('publish_post_no_data_provided',
                                          expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_publish_page(self) -> None:

        expected_topic = u"WordPress Page"
        expected_message = u"New page published.\n" + "[New Blog Page](http://example.com\n)"

        self.send_and_test_stream_message('publish_page', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_user_register(self) -> None:

        expected_topic = u"New Blog Users"
        expected_message = u"New blog user registered.\nName: test_user\nemail: test_user@example.com"

        self.send_and_test_stream_message('user_register', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_wp_login(self) -> None:

        expected_topic = u"New Login"
        expected_message = u"User testuser logged in."

        self.send_and_test_stream_message('wp_login', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_unknown_action_no_data(self) -> None:

        # Mimic send_and_test_stream_message() to manually execute a negative test.
        # Otherwise its call to send_json_payload() would assert on the non-success
        # we are testing. The value of result is the error message the webhook should
        # return if no params are sent. The fixture for this test is an empty file.

        # subscribe to the target stream
        self.subscribe(self.test_user, self.STREAM_NAME)

        # post to the webhook url
        post_params = {'stream_name': self.STREAM_NAME,
                       'content_type': 'application/x-www-form-urlencoded'}
        result = self.client_post(self.url, 'unknown_action', **post_params)

        # check that we got the expected error message
        self.assert_json_error(result, "Unknown WordPress webhook action: WordPress Action")

    def test_unknown_action_no_hook_provided(self) -> None:

        # Similar to unknown_action_no_data, except the fixture contains valid blog post
        # params but without the hook parameter. This should also return an error.

        self.subscribe(self.test_user, self.STREAM_NAME)
        post_params = {'stream_name': self.STREAM_NAME,
                       'content_type': 'application/x-www-form-urlencoded'}
        result = self.client_post(self.url, 'unknown_action', **post_params)

        self.assert_json_error(result, "Unknown WordPress webhook action: WordPress Action")

    def get_body(self, fixture_name: str) -> str:
        return self.fixture_data("wordpress", fixture_name, file_type="txt")
