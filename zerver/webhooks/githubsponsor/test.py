from zerver.lib.test_classes import WebhookTestCase


class GithubSponsorHookTests(WebhookTestCase):
    STREAM_NAME = "githubsponsor"
    URL_TEMPLATE = "/api/v1/external/githubsponsor?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "githubsponsor"

    def test_created_message(self) -> None:
        expected_topic = "githubsponsor"
        expected_message = (
            "New Subscription for a Sponsorship:\nzulip subscribed for a $5 a month "
            "Sponsorship on 2020-04-25 20:42:10."
        )
        # use fixture named helloworld_hello
        self.check_webhook(
            "created",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_pending_tier_change_message(self) -> None:
        expected_topic = "githubsponsor"
        expected_message = (
            "Upcoming Subscription Change for a Sponsorship:\nzulip changed subscription "
            "from $5 to $10. Effective from 2020-05-01 20:42:10."
        )
        self.check_webhook(
            "pending_tier_change",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_tier_changed_message(self) -> None:
        expected_topic = "githubsponsor"
        expected_message = (
            "Subscription Change for a Sponsorship:\nzulip changed subscription from $5 a "
            "month to $10 a month on 2020-04-25 20:42:10."
        )
        self.check_webhook("tier_changed", expected_topic, expected_message)

    def test_pending_cancellation_message(self) -> None:
        expected_topic = "githubsponsor"
        expected_message = (
            "Upcoming Sponsorship Cancellation:\nzulip cancelled their sponsorship. "
            "Effective from 2020-05-01 20:42:10."
        )
        self.check_webhook(
            "pending_cancellation",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_cancelled_message(self) -> None:
        expected_topic = "githubsponsor"
        expected_message = (
            "Sponsorship Cancelled:\nzulip cancelled their sponsorship on 2020-04-25 20:42:10."
        )
        # use fixture named helloworld_hello
        self.check_webhook(
            "cancelled",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
