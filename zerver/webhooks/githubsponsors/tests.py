from zerver.lib.test_classes import WebhookTestCase

class GitHubSponsorsHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/githubsponsors?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = 'githubsponsors'

    def test_created_message(self) -> None:
        expected_topic = "GitHub Sponsors"
        expected_message = "Hello from GitHub Sponsorships!\n**[monalisa](https://github.com/monalisa)** has decided to sponsor you in the **$5 a month** tier!"
        # use fixture named githubsponsors_created
        self.check_webhook('created', expected_topic, expected_message,
                           content_type="application/x-www-form-urlencoded")

    def test_pending_tier_change_message(self) -> None:
        expected_topic = "GitHub Sponsors"
        expected_message = "Hello from GitHub Sponsorships!\n**[monalisa](https://github.com/monalisa)** has changed their sponsorship tier from **$10 a month** to **$5 a month**.\nThese changes will be effective from 2019-12-30T00:00:00+00:00."
        # use fixture named githubsponsors_pending_tier_change
        self.check_webhook('pending_tier_change', expected_topic, expected_message,
                           content_type="application/x-www-form-urlencoded")
    
    def test_pending_cancellation_message(self) -> None:
        expected_topic = "GitHub Sponsors"
        expected_message = "Hello from GitHub Sponsorships!\n**[monalisa](https://github.com/monalisa)** has decided to stop sponsoring you.\nThese changes will be effective from 2019-12-30T00:00:00+00:00."
        # use fixture named githubsponsors_pending_cancellation
        self.check_webhook('pending_cancellation', expected_topic, expected_message,
                           content_type="application/x-www-form-urlencoded")

