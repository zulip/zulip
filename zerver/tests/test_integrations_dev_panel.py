from unittest.mock import MagicMock, patch

import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Stream, get_realm, get_user


class TestIntegrationsDevPanel(ZulipTestCase):
    zulip_realm = get_realm("zulip")

    def test_check_send_webhook_fixture_message_for_error(self) -> None:
        bot = get_user("webhook-bot@zulip.com", self.zulip_realm)
        url = f"/api/v1/external/airbrake?api_key={bot.api_key}"
        target_url = "/devtools/integrations/check_send_webhook_fixture_message"
        body = "{}"  # This empty body should generate a ValidationError on the webhook code side.

        data = {
            "url": url,
            "body": body,
            "custom_headers": "{}",
            "is_json": "true",
        }
        with self.assertLogs(level="ERROR") as logs, self.settings(TEST_SUITE=False):
            response = self.client_post(target_url, data)

            self.assertEqual(response.status_code, 500)  # Since the response would be forwarded.
            expected_response = {"result": "error", "msg": "Internal server error"}
            self.assertEqual(orjson.loads(response.content), expected_response)

        # Intention of this test looks like to trigger ValidationError
        # so just testing ValidationError is printed along with Traceback in logs
        self.assert_length(logs.output, 1)
        self.assertTrue(
            logs.output[0].startswith(
                "ERROR:django.request:Internal Server Error: /api/v1/external/airbrake\n"
                "Traceback (most recent call last):\n"
            )
        )
        self.assertTrue("ValidationError" in logs.output[0])

    def test_check_send_webhook_fixture_message_for_success_without_headers(self) -> None:
        bot = get_user("webhook-bot@zulip.com", self.zulip_realm)
        url = f"/api/v1/external/airbrake?api_key={bot.api_key}&stream=Denmark&topic=Airbrake notifications"
        target_url = "/devtools/integrations/check_send_webhook_fixture_message"
        with open("zerver/webhooks/airbrake/fixtures/error_message.json") as f:
            body = f.read()

        data = {
            "url": url,
            "body": body,
            "custom_headers": "{}",
            "is_json": "true",
        }

        response = self.client_post(target_url, data)
        expected_response = {
            "responses": [{"status_code": 200, "message": {"result": "success", "msg": ""}}],
            "result": "success",
            "msg": "",
        }
        response_content = orjson.loads(response.content)
        response_content["responses"][0]["message"] = orjson.loads(
            response_content["responses"][0]["message"]
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_content, expected_response)

        latest_msg = Message.objects.latest("id")
        expected_message = '[ZeroDivisionError](https://zulip.airbrake.io/projects/125209/groups/1705190192091077626): "Error message from logger" occurred.'
        self.assertEqual(latest_msg.content, expected_message)
        self.assertEqual(Stream.objects.get(id=latest_msg.recipient.type_id).name, "Denmark")
        self.assertEqual(latest_msg.topic_name(), "Airbrake notifications")

    def test_check_send_webhook_fixture_message_for_success_with_headers(self) -> None:
        bot = get_user("webhook-bot@zulip.com", self.zulip_realm)
        url = f"/api/v1/external/github?api_key={bot.api_key}&stream=Denmark&topic=GitHub notifications"
        target_url = "/devtools/integrations/check_send_webhook_fixture_message"
        with open("zerver/webhooks/github/fixtures/ping__organization.json") as f:
            body = f.read()

        data = {
            "url": url,
            "body": body,
            "custom_headers": orjson.dumps({"X-GitHub-Event": "ping"}).decode(),
            "is_json": "true",
        }

        response = self.client_post(target_url, data)
        self.assertEqual(response.status_code, 200)

        latest_msg = Message.objects.latest("id")
        expected_message = "GitHub webhook has been successfully configured by eeshangarg."
        self.assertEqual(latest_msg.content, expected_message)
        self.assertEqual(Stream.objects.get(id=latest_msg.recipient.type_id).name, "Denmark")
        self.assertEqual(latest_msg.topic_name(), "GitHub notifications")

    def test_check_send_webhook_fixture_message_for_success_with_headers_and_non_json_fixtures(
        self,
    ) -> None:
        bot = get_user("webhook-bot@zulip.com", self.zulip_realm)
        url = f"/api/v1/external/wordpress?api_key={bot.api_key}&stream=Denmark&topic=WordPress notifications"
        target_url = "/devtools/integrations/check_send_webhook_fixture_message"
        with open("zerver/webhooks/wordpress/fixtures/publish_post_no_data_provided.txt") as f:
            body = f.read()

        data = {
            "url": url,
            "body": body,
            "custom_headers": orjson.dumps(
                {"Content-Type": "application/x-www-form-urlencoded"}
            ).decode(),
            "is_json": "false",
        }

        response = self.client_post(target_url, data)
        self.assertEqual(response.status_code, 200)

        latest_msg = Message.objects.latest("id")
        expected_message = "New post published:\n* [New WordPress post](WordPress post URL)"
        self.assertEqual(latest_msg.content, expected_message)
        self.assertEqual(Stream.objects.get(id=latest_msg.recipient.type_id).name, "Denmark")
        self.assertEqual(latest_msg.topic_name(), "WordPress notifications")

    def test_get_fixtures_for_nonexistent_integration(self) -> None:
        target_url = "/devtools/integrations/somerandomnonexistentintegration/fixtures"
        response = self.client_get(target_url)
        expected_response = {
            "code": "BAD_REQUEST",
            "msg": '"somerandomnonexistentintegration" is not a valid webhook integration.',
            "result": "error",
        }
        self.assertEqual(response.status_code, 404)
        self.assertEqual(orjson.loads(response.content), expected_response)

    @patch("zerver.views.development.integrations.os.path.exists")
    def test_get_fixtures_for_integration_without_fixtures(
        self, os_path_exists_mock: MagicMock
    ) -> None:
        os_path_exists_mock.return_value = False
        target_url = "/devtools/integrations/airbrake/fixtures"
        response = self.client_get(target_url)
        expected_response = {
            "code": "BAD_REQUEST",
            "msg": 'The integration "airbrake" does not have fixtures.',
            "result": "error",
        }
        self.assertEqual(response.status_code, 404)
        self.assertEqual(orjson.loads(response.content), expected_response)

    def test_get_fixtures_for_success(self) -> None:
        target_url = "/devtools/integrations/airbrake/fixtures"
        response = self.client_get(target_url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(orjson.loads(response.content)["fixtures"])

    def test_get_dev_panel_page(self) -> None:
        # Just to satisfy the test suite.
        target_url = "/devtools/integrations/"
        response = self.client_get(target_url)
        self.assertEqual(response.status_code, 200)

    def test_send_all_webhook_fixture_messages_for_success(self) -> None:
        bot = get_user("webhook-bot@zulip.com", self.zulip_realm)
        url = f"/api/v1/external/appfollow?api_key={bot.api_key}&stream=Denmark&topic=Appfollow bulk notifications"
        target_url = "/devtools/integrations/send_all_webhook_fixture_messages"

        data = {
            "url": url,
            "custom_headers": "{}",
            "integration_name": "appfollow",
        }

        response = self.client_post(target_url, data)
        expected_responses = [
            {
                "fixture_name": "sample.json",
                "status_code": 200,
                "message": {"msg": "", "result": "success"},
            },
            {
                "fixture_name": "review.json",
                "status_code": 200,
                "message": {"msg": "", "result": "success"},
            },
        ]
        responses = orjson.loads(response.content)["responses"]
        for r in responses:
            r["message"] = orjson.loads(r["message"])
        self.assertEqual(response.status_code, 200)
        for r in responses:
            # We have to use this roundabout manner since the order may vary each time.
            # This is not an issue.
            self.assertTrue(r in expected_responses)
            expected_responses.remove(r)

        new_messages = Message.objects.order_by("-id")[0:2]
        expected_messages = [
            "Webhook integration was successful.\nTest User / Acme (Google Play)",
            "Acme - Group chat\nApp Store, Acme Technologies, Inc.\n★★★★★ United States\n**Great for Information Management**\nAcme enables me to manage the flow of information quite well. I only wish I could create and edit my Acme Post files in the iOS app.\n*by* **Mr RESOLUTIONARY** *for v3.9*\n[Permalink](http://appfollow.io/permalink) · [Add tag](http://watch.appfollow.io/add_tag)",
        ]
        for msg in new_messages:
            # new_messages -> expected_messages or expected_messages -> new_messages shouldn't make
            # a difference since equality is commutative.
            self.assertTrue(msg.content in expected_messages)
            expected_messages.remove(msg.content)
            self.assertEqual(Stream.objects.get(id=msg.recipient.type_id).name, "Denmark")
            self.assertEqual(msg.topic_name(), "Appfollow bulk notifications")

    def test_send_all_webhook_fixture_messages_for_success_with_non_json_fixtures(self) -> None:
        bot = get_user("webhook-bot@zulip.com", self.zulip_realm)
        url = f"/api/v1/external/wordpress?api_key={bot.api_key}&stream=Denmark&topic=WordPress bulk notifications"
        target_url = "/devtools/integrations/send_all_webhook_fixture_messages"

        data = {
            "url": url,
            "custom_headers": "{}",
            "integration_name": "wordpress",
        }

        response = self.client_post(target_url, data)
        expected_responses = [
            {
                "message": {
                    "msg": "Unknown WordPress webhook action: WordPress action",
                    "result": "error",
                    "code": "BAD_REQUEST",
                },
                "fixture_name": "user_register.txt",
                "status_code": 400,
            },
            {
                "message": {
                    "msg": "Unknown WordPress webhook action: WordPress action",
                    "result": "error",
                    "code": "BAD_REQUEST",
                },
                "fixture_name": "publish_post_no_data_provided.txt",
                "status_code": 400,
            },
            {
                "message": {
                    "msg": "Unknown WordPress webhook action: WordPress action",
                    "result": "error",
                    "code": "BAD_REQUEST",
                },
                "fixture_name": "unknown_action_no_data.txt",
                "status_code": 400,
            },
            {
                "message": {
                    "msg": "Unknown WordPress webhook action: WordPress action",
                    "result": "error",
                    "code": "BAD_REQUEST",
                },
                "fixture_name": "publish_page.txt",
                "status_code": 400,
            },
            {
                "message": {
                    "msg": "Unknown WordPress webhook action: WordPress action",
                    "result": "error",
                    "code": "BAD_REQUEST",
                },
                "fixture_name": "unknown_action_no_hook_provided.txt",
                "status_code": 400,
            },
            {
                "message": {
                    "msg": "Unknown WordPress webhook action: WordPress action",
                    "result": "error",
                    "code": "BAD_REQUEST",
                },
                "fixture_name": "publish_post_type_not_provided.txt",
                "status_code": 400,
            },
            {
                "message": {
                    "msg": "Unknown WordPress webhook action: WordPress action",
                    "result": "error",
                    "code": "BAD_REQUEST",
                },
                "fixture_name": "wp_login.txt",
                "status_code": 400,
            },
            {
                "message": {
                    "msg": "Unknown WordPress webhook action: WordPress action",
                    "result": "error",
                    "code": "BAD_REQUEST",
                },
                "fixture_name": "publish_post.txt",
                "status_code": 400,
            },
        ]
        responses = orjson.loads(response.content)["responses"]
        for r in responses:
            r["message"] = orjson.loads(r["message"])
        self.assertEqual(response.status_code, 200)
        for r in responses:
            # We have to use this roundabout manner since the order may vary each time. This is not
            # an issue. Basically, we're trying to compare 2 lists and since we're not resorting to
            # using sets or a sorted order, we're sticking with O(n*m) time complexity for this
            # comparison (where n and m are the lengths of the two lists respectively). But since
            # this is just a unit test and more importantly n = m = some-low-number we don't really
            # care about the time complexity being what it is.
            self.assertTrue(r in expected_responses)
            expected_responses.remove(r)

    @patch("zerver.views.development.integrations.os.path.exists")
    def test_send_all_webhook_fixture_messages_for_missing_fixtures(
        self, os_path_exists_mock: MagicMock
    ) -> None:
        os_path_exists_mock.return_value = False
        bot = get_user("webhook-bot@zulip.com", self.zulip_realm)
        url = f"/api/v1/external/appfollow?api_key={bot.api_key}&stream=Denmark&topic=Appfollow bulk notifications"
        data = {
            "url": url,
            "custom_headers": "{}",
            "integration_name": "appfollow",
        }
        response = self.client_post(
            "/devtools/integrations/send_all_webhook_fixture_messages", data
        )
        expected_response = {
            "code": "BAD_REQUEST",
            "msg": 'The integration "appfollow" does not have fixtures.',
            "result": "error",
        }
        self.assertEqual(response.status_code, 404)
        self.assertEqual(orjson.loads(response.content), expected_response)
