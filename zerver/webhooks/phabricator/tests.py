import httpretty
from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.bot_config import set_bot_config
from zerver.models import get_user, get_realm

class PhabricatorHookTests(WebhookTestCase):
    STREAM_NAME = "phabricator"
    FIXTURE_DIR_NAME = "phabricator"
    EXPECTED_TOPIC = "Zulip x Phabricator"
    URL_TEMPLATE = "/api/v1/external/phabricator?stream={stream}&api_key={api_key}"

    @httpretty.activate
    def test_commit_successful(self) -> None:
        root_url = "https://phabricator.myinstance.com"
        webhook_bot = get_user('webhook-bot@zulip.com', get_realm('zulip'))
        set_bot_config(webhook_bot, "integration_id", "phabricator")
        set_bot_config(webhook_bot, "phabricator_api_key", "api-f6bd3xtoawh3egc6iazurmrcaqap")
        set_bot_config(webhook_bot, "phabricator_root_url", root_url)
        callbacks = [("/api/diffusion.commit.search", "POST", "commit__diffusion_commit_search"),
                     ("/api/diffusion.repository.search", "POST", "commit__diffusion_repository_search")]
        self.register_callbacks(root_url, callbacks)
        expected_message = "Hemanth V. Alluri authored and committed commit 229bb58fa to Zulip x Phabricator"
        self.send_and_test_stream_message("commit", self.EXPECTED_TOPIC, expected_message)

    def test_commit_with_insufficient_configuration(self) -> None:
        try:
            self.send_and_test_stream_message("commit", self.EXPECTED_TOPIC, "")
        except AssertionError as e:
            self.assertEqual(str(e), "400 != 200 : The \"Zulip Webhook Bot\" bot was \
not setup as a Phabricator integration bot.")
