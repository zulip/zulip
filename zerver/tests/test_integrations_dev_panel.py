import ujson
from mock import MagicMock, patch
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_user, get_realm, Message, Stream

class TestIntegrationsDevPanel(ZulipTestCase):

    zulip_realm = get_realm("zulip")

    def test_check_send_webhook_fixture_message_for_error(self) -> None:
        bot = get_user('webhook-bot@zulip.com', self.zulip_realm)
        url = "/api/v1/external/airbrake?api_key={key}".format(key=bot.api_key)
        target_url = "/devtools/integrations/check_send_webhook_fixture_message"
        body = "{}"  # This empty body should generate a KeyError on the webhook code side.

        data = {
            "url": url,
            "body": body,
            "custom_headers": "",
        }

        response = self.client_post(target_url, data)

        self.assertEqual(response.status_code, 500)  # Since the response would be forwarded.
        expected_response = {"result": "error", "msg": "Internal server error"}
        self.assertEqual(ujson.loads(response.content), expected_response)

    def test_check_send_webhook_fixture_message_for_success_without_headers(self) -> None:
        bot = get_user('webhook-bot@zulip.com', self.zulip_realm)
        url = "/api/v1/external/airbrake?api_key={key}&stream=Denmark&topic=Airbrake Notifications".format(key=bot.api_key)
        target_url = "/devtools/integrations/check_send_webhook_fixture_message"
        with open("zerver/webhooks/airbrake/fixtures/error_message.json", "r") as f:
            body = f.read()

        data = {
            "url": url,
            "body": body,
            "custom_headers": "",
        }

        response = self.client_post(target_url, data)
        self.assertEqual(response.status_code, 200)

        latest_msg = Message.objects.latest('id')
        expected_message = "[ZeroDivisionError](https://zulip.airbrake.io/projects/125209/groups/1705190192091077626): \"Error message from logger\" occurred."
        self.assertEqual(latest_msg.content, expected_message)
        self.assertEqual(Stream.objects.get(id=latest_msg.recipient.type_id).name, "Denmark")
        self.assertEqual(latest_msg.topic_name(), "Airbrake Notifications")

    def test_check_send_webhook_fixture_message_for_success_with_headers(self) -> None:
        bot = get_user('webhook-bot@zulip.com', self.zulip_realm)
        url = "/api/v1/external/github?api_key={key}&stream=Denmark&topic=GitHub Notifications".format(key=bot.api_key)
        target_url = "/devtools/integrations/check_send_webhook_fixture_message"
        with open("zerver/webhooks/github/fixtures/ping_organization.json", "r") as f:
            body = f.read()

        data = {
            "url": url,
            "body": body,
            "custom_headers": ujson.dumps({"X_GITHUB_EVENT": "ping"}),
        }

        response = self.client_post(target_url, data)
        self.assertEqual(response.status_code, 200)

        latest_msg = Message.objects.latest('id')
        expected_message = "GitHub webhook has been successfully configured by eeshangarg."
        self.assertEqual(latest_msg.content, expected_message)
        self.assertEqual(Stream.objects.get(id=latest_msg.recipient.type_id).name, "Denmark")
        self.assertEqual(latest_msg.topic_name(), "GitHub Notifications")

    def test_get_fixtures_for_nonexistant_integration(self) -> None:
        target_url = "/devtools/integrations/somerandomnonexistantintegration/fixtures"
        response = self.client_get(target_url)
        expected_response = {'msg': '"somerandomnonexistantintegration" is not a valid webhook integration.', 'result': 'error'}
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ujson.loads(response.content), expected_response)

    @patch("zerver.views.development.integrations.os.path.exists")
    def test_get_fixtures_for_integration_without_fixtures(self, os_path_exists_mock: MagicMock) -> None:
        os_path_exists_mock.return_value = False
        target_url = "/devtools/integrations/airbrake/fixtures"
        response = self.client_get(target_url)
        expected_response = {'msg': 'The integration "airbrake" does not have fixtures.', 'result': 'error'}
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ujson.loads(response.content), expected_response)

    def test_get_fixtures_for_integration_without_json_fixtures(self) -> None:
        target_url = "/devtools/integrations/deskdotcom/fixtures"
        response = self.client_get(target_url)
        expected_response = {'msg': 'The integration "deskdotcom" has non-JSON fixtures.', 'result': 'error'}
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ujson.loads(response.content), expected_response)

    def test_get_fixtures_for_success(self) -> None:
        target_url = "/devtools/integrations/airbrake/fixtures"
        response = self.client_get(target_url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(ujson.loads(response.content)["fixtures"])

    def test_get_dev_panel_page(self) -> None:
        # Just to satisfy the test suite.
        target_url = "/devtools/integrations/"
        response = self.client_get(target_url)
        self.assertEqual(response.status_code, 200)

    def test_send_all_webhook_fixture_messages_for_success(self) -> None:
        bot = get_user('webhook-bot@zulip.com', self.zulip_realm)
        url = "/api/v1/external/appfollow?api_key={key}&stream=Denmark&topic=Appfollow Bulk Notifications".format(key=bot.api_key)
        target_url = "/devtools/integrations/send_all_webhook_fixture_messages"

        data = {
            "url": url,
            "custom_headers": "",
            "integration_name": "appfollow",
        }

        response = self.client_post(target_url, data)
        expected_responses = [
            {
                "fixture_name": "sample.json",
                "status_code": 200,
                "message": {"msg": "", "result": "success"}
            },
            {
                "fixture_name": "review.json",
                "status_code": 200,
                "message": {"msg": "", "result": "success"}
            }
        ]
        responses = ujson.loads(response.content)["responses"]
        for r in responses:
            r["message"] = ujson.loads(r["message"])
        self.assertEqual(response.status_code, 200)
        for r in responses:
            # We have to use this roundabout manner since the order may vary each time. This is not
            # an issue.
            self.assertTrue(r in expected_responses)
            expected_responses.remove(r)

        new_messages = Message.objects.order_by('-id')[0:2]
        expected_messages = ["Webhook integration was successful.\nTest User / Acme (Google Play)", "Acme - Group chat\nApp Store, Acme Technologies, Inc.\n★★★★★ United States\n**Great for Information Management**\nAcme enables me to manage the flow of information quite well. I only wish I could create and edit my Acme Post files in the iOS app.\n*by* **Mr RESOLUTIONARY** *for v3.9*\n[Permalink](http://appfollow.io/permalink) · [Add tag](http://watch.appfollow.io/add_tag)"]
        for msg in new_messages:
            # new_messages -> expected_messages or expected_messages -> new_messages shouldn't make
            # a difference since equality is commutative.
            self.assertTrue(msg.content in expected_messages)
            expected_messages.remove(msg.content)
            self.assertEqual(Stream.objects.get(id=msg.recipient.type_id).name, "Denmark")
            self.assertEqual(msg.topic_name(), "Appfollow Bulk Notifications")

    @patch("zerver.views.development.integrations.os.path.exists")
    def test_send_all_webhook_fixture_messages_for_missing_fixtures(self, os_path_exists_mock: MagicMock) -> None:
        os_path_exists_mock.return_value = False
        bot = get_user('webhook-bot@zulip.com', self.zulip_realm)
        url = "/api/v1/external/appfollow?api_key={key}&stream=Denmark&topic=Appfollow Bulk Notifications".format(key=bot.api_key)
        data = {
            "url": url,
            "custom_headers": "",
            "integration_name": "appfollow",
        }
        response = self.client_post("/devtools/integrations/send_all_webhook_fixture_messages", data)
        expected_response = {'msg': 'The integration "appfollow" does not have fixtures.', 'result': 'error'}
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ujson.loads(response.content), expected_response)

    def test_send_all_webhook_fixture_messages_for_non_json_fixtures(self) -> None:
        bot = get_user('webhook-bot@zulip.com', self.zulip_realm)
        url = "/api/v1/external/appfollow?api_key={key}&stream=Denmark&topic=Desktdotcom Bulk Notifications".format(key=bot.api_key)
        data = {
            "url": url,
            "custom_headers": "",
            "integration_name": "deskdotcom",
        }
        response = self.client_post("/devtools/integrations/send_all_webhook_fixture_messages", data)
        expected_response = {'msg': 'The integration "deskdotcom" has non-JSON fixtures.', 'result': 'error'}
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ujson.loads(response.content), expected_response)
