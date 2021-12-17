from django.conf import settings

from zerver.lib.test_classes import WebhookTestCase
from zerver.models import get_realm, get_system_bot


class RhodeCodeHookTests(WebhookTestCase):
    STREAM_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/rhodecode?&api_key={api_key}&stream={stream}"
    PM_URL_TEMPLATE = "/api/v1/external/rhodecode?&api_key={api_key}"
    WEBHOOK_DIR_NAME = "rhodecode"

    def test_push_1_commit(self) -> None:
        expected_topic = "u/<user>/webhook / master"
        expected_message = "<user> [pushed](https://code.rhodecode.com/_1880) 1 commit to branch master. Commits by <author> <<email>> (1).\n\n* yow ([9dae8ab](https://code.rhodecode.com/u/<user>/webhook/changeset/9dae8abbc728c8f0243bce4705a2654fdbe06c2e))"

        self.check_webhook("push_1_commit", expected_topic, expected_message)
