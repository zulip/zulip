from zerver.lib.test_classes import WebhookTestCase

TOPIC = "githubsponsors"


class GithubSponsorsHookTests(WebhookTestCase):
    STREAM_NAME = "githubsponsors"
    URL_TEMPLATE = "/api/v1/external/githubsponsors?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "githubsponsors"

    def test_github_sponsor_cancelled_message(self) -> None:
        expected_topic = TOPIC
        expected_message = ":warning: Uh Oh! Sponsorship Cancelled! :warning:\nSomebody cancelled their sponsorship on 20 December 2019!"

        self.check_webhook(
            "cancelled_sponsorship",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_github_sponsor_created_message(self) -> None:
        expected_topic = TOPIC
        expected_message = ':tada: New Subscription for a Sponsorship! :tada:\nmonalisa subscribed for a "$5 a month" Sponsorship on 20 December 2019!'

        self.check_webhook(
            "created_sponsorship",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_github_sponsor_pending_cancellation_message(self) -> None:
        expected_topic = TOPIC
        expected_message = ":warning: Uh Oh!Upcoming Sponsorship Cancellation! :warning:\nSomebody cancelled their sponsorship! Effective from 05 January 2020."

        self.check_webhook(
            "pending_cancellation_sponsorship",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_github_sponsor_pending_tier_change_message(self) -> None:
        expected_topic = TOPIC
        expected_message = ':money: Upcoming Subscription Change for a Sponsorship! :money:\nmonalisa changed subscription from "$10 a month" to "$5 a month"! Effective from 05 January 2020.'

        self.check_webhook(
            "pending_tier_change_sponsorship",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_github_sponsor_tier_changed_message(self) -> None:
        expected_topic = TOPIC
        expected_message = ':money: Subscription Change for a Sponsorship! :money:\nmonalisa changed subscription from "$10 a month" to "$5 a month" on 30 December 2019!'

        self.check_webhook(
            "tier_changed_sponsorship",
            expected_topic,
            expected_message,
            content_type="application/json",
        )
