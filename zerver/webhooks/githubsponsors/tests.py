from zerver.lib.test_classes import WebhookTestCase

from .view import DatetimeParser



class GithubSponsorHookTests(WebhookTestCase):
    '''Webhook Integration for Github Sponsors'''
    STREAM_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/githubsponsors?&api_key={api_key}&stream={stream}"
    PM_URL_TEMPLATE = "/api/v1/external/githubsponsors?&api_key={api_key}"
    WEBHOOK_DIR_NAME = "githubsponsors"

    # NEW SPONSOR CREATED TEST
    def test_github_sponsor_created_message(self) -> None:
        expected_topic = "New Sponsorship Subscription"
        expected_message = ':confetti: New Subscription for a Sponsorship! :confetti:\nmonalisa subscribed for a "$5 a month" Sponsorship on 20 December 2019, Friday'

        # use fixture named github_sponsor_created
        self.check_webhook(
            "github_sponsor_created",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    # SPONSOR TIER CHANGE TEST
    def test_github_sponsor_pending_tier_change_message(self) -> None:
        expected_topic = "Subscription Change"
        expected_message = ':bullhorn: Subscription Tier Change :bullhorn:\nmonalisa changed their Sponsor subscription from "$10 a month" to "$5 a month" effective from 30 December 2019, Monday'

        # using fixture named gihub_sponsor_downgrade
        self.check_webhook(
            "github_sponsor_downgrade",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_github_sponsor_cancelled_message(self) -> None:
        expected_topic = "Cancelled Subscription"
        expected_message = ":warning: Sponsorship Cancelled! :warning:\nSomebody cancelled their sponsorship subscription"

        # using fixture github_sponsor_cancelled
        self.check_webhook(
            "github_sponsor_cancelled",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    # NOT RELATED TO THE SPONSORSHIP WEBHOOK
    # TESTING DATE PARSER HELPER CLASS IN THE VIEW
    def test_github_sponsor_date_time_parser(self) -> None:
        expected_date = "30 December 2019, Monday"
        date_from_payload = "2019-12-30T00:00:00+00:00"

        parser = DatetimeParser()
        parsed_date = parser.parse(date_from_payload)

        self.assertEqual(expected_date, parsed_date)
