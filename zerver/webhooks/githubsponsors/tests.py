from zerver.lib.test_classes import WebhookTestCase


class GithubSponsorsHookTests(WebhookTestCase):
    STREAM_NAME = "GithubSponsors"
    URL_TEMPLATE = "/api/v1/external/githubsponsors?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = "githubsponsors"
    # Note: Include a test function per each distinct message condition your integration supports
    def test_sponsorship_created(self) -> None:
        expected_topic = "Github Sponsors"
        expected_message = "Github Sponsors has a new sponsor : monalisa"
        # use fixture named sponsorship_created
        self.check_webhook("sponsorship_created", expected_topic, expected_message)

    def test_sponsorship_downgraded(self) -> None:
        expected_topic = "Github Sponsors"
        expected_message = "Github Sponsors : sponsorship downgraded by monalisa"
        # use fixture named sponsorship_downgraded
        self.check_webhook("sponsorship_downgraded", expected_topic, expected_message)
