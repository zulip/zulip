from zerver.lib.test_classes import WebhookTestCase


class UpdownHookTests(WebhookTestCase):
    def test_updown_check_down_event(self) -> None:
        expected_topic_name = "https://updown.io"
        expected_message = (
            "Service is `down`. It returned a 500 error at <time:2016-02-07T13:11:43+00:00>."
        )
        self.check_webhook("check_down_one_event", expected_topic_name, expected_message)

    def test_updown_check_up_again_event(self) -> None:
        expected_topic_name = "https://updown.io"
        expected_message = "Service is `up` again after 4 minutes 25 seconds."
        self.check_webhook("check_up_again_one_event", expected_topic_name, expected_message)

    def test_updown_check_up_event(self) -> None:
        expected_topic_name = "https://updown.io"
        expected_message = "Service is `up`."
        self.check_webhook("check_up_first_time", expected_topic_name, expected_message)

    def test_updown_check_up_multiple_events(self) -> None:
        topic_name = "https://updown.io"

        down_content = (
            "Service is `down`. It returned a 500 error at <time:2016-02-07T13:11:43+00:00>."
        )
        up_content = "Service is `up` again after 1 second."

        self.subscribe(self.test_user, self.channel_name)
        payload = self.get_body("check_multiple_events")

        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            payload,
            content_type="application/json",
        )

        msg = self.get_second_to_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=topic_name,
            content=down_content,
        )

        msg = self.get_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=topic_name,
            content=up_content,
        )

    def test_unknown_event(self) -> None:
        self.check_webhook("unknown_event", expect_noop=True)
