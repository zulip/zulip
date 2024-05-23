import orjson

from zerver.lib.send_email import FromAddress
from zerver.lib.test_classes import WebhookTestCase
from zerver.models import Recipient
from zerver.models.realms import get_realm
from zerver.models.users import get_user_by_delivery_email
from zerver.webhooks.teamcity.view import MISCONFIGURED_PAYLOAD_TYPE_ERROR_MESSAGE


class TeamCityHookTests(WebhookTestCase):
    CHANNEL_NAME = "teamcity"
    URL_TEMPLATE = "/api/v1/external/teamcity?stream={stream}&api_key={api_key}"
    TOPIC_NAME = "Project :: Compile"
    WEBHOOK_DIR_NAME = "teamcity"

    def test_teamcity_success(self) -> None:
        expected_message = "Project :: Compile build 5535 - CL 123456 was successful! :thumbs_up: See [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv) and [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)."
        self.check_webhook("success", self.TOPIC_NAME, expected_message)

    def test_teamcity_success_branch(self) -> None:
        expected_message = "Project :: Compile build 5535 - CL 123456 was successful! :thumbs_up: See [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv) and [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)."
        expected_topic_name = "Project :: Compile (MyBranch)"
        self.check_webhook("success_branch", expected_topic_name, expected_message)

    def test_teamcity_broken(self) -> None:
        expected_message = "Project :: Compile build 5535 - CL 123456 is broken with status Exit code 1 (new)! :thumbs_down: See [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv) and [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)."
        self.check_webhook("broken", self.TOPIC_NAME, expected_message)

    def test_teamcity_failure(self) -> None:
        expected_message = "Project :: Compile build 5535 - CL 123456 is still broken with status Exit code 1! :thumbs_down: See [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv) and [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)."
        self.check_webhook("failure", self.TOPIC_NAME, expected_message)

    def test_teamcity_fixed(self) -> None:
        expected_message = "Project :: Compile build 5535 - CL 123456 has been fixed! :thumbs_up: See [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv) and [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)."
        self.check_webhook("fixed", self.TOPIC_NAME, expected_message)

    def test_teamcity_personal(self) -> None:
        expected_message = "Your personal build for Project :: Compile build 5535 - CL 123456 is broken with status Exit code 1 (new)! :thumbs_down: See [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv) and [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)."
        payload = orjson.dumps(
            orjson.loads(self.webhook_fixture_data(self.WEBHOOK_DIR_NAME, "personal"))
        )
        self.client_post(self.url, payload, content_type="application/json")
        msg = self.get_last_message()

        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.recipient.type, Recipient.PERSONAL)

    def test_non_generic_payload_ignore_pm_notification(self) -> None:
        expected_message = MISCONFIGURED_PAYLOAD_TYPE_ERROR_MESSAGE.format(
            bot_name=get_user_by_delivery_email(
                "webhook-bot@zulip.com", get_realm("zulip")
            ).full_name,
            support_email=FromAddress.SUPPORT,
        ).strip()
        payload = self.get_body("slack_non_generic_payload")
        self.client_post(self.url, payload, content_type="application/json")
        msg = self.get_last_message()

        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.recipient.type, Recipient.PERSONAL)
