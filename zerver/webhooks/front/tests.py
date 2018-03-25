from typing import Text
import ujson

from zerver.lib.test_classes import WebhookTestCase

class FrontHookTests(WebhookTestCase):
    STREAM_NAME = 'front'
    URL_TEMPLATE = "/api/v1/external/front?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'front'

    # Scenario 1: Conversation starts from an outbound message.

    # Conversation automatically assigned to a teammate who started it.
    def test_conversation_assigned_outbound(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "**Leela Turanga** assigned themselves."

        self.send_and_test_stream_message('conversation_assigned_outbound',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_outbound_message(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "[Outbound message](https://app.frontapp.com/open/msg_1176ie2) " \
                           "from **support@planet-express.com** " \
                           "to **calculon@momsbot.com**.\n" \
                           "```quote\n*Subject*: Your next delivery is on Epsilon 96Z\n```"

        self.send_and_test_stream_message('outbound_message',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_archived(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "Archived by **Leela Turanga**."

        self.send_and_test_stream_message('conversation_archived',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_reopened(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "Reopened by **Leela Turanga**."

        self.send_and_test_stream_message('conversation_reopened',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_deleted(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "Deleted by **Leela Turanga**."

        self.send_and_test_stream_message('conversation_deleted',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_restored(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "Restored by **Leela Turanga**."

        self.send_and_test_stream_message('conversation_restored',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_unassigned(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "Unassined by **Leela Turanga**."

        self.send_and_test_stream_message('conversation_unassigned',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_mention_all(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "**Leela Turanga** left a comment:\n" \
                           "```quote\n@all Could someone else take this?\n```"

        self.send_and_test_stream_message('mention_all',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    # Scenario 2: Conversation starts from an inbound message.

    def test_inbound_message(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "[Inbound message](https://app.frontapp.com/open/msg_1176r8y) " \
                           "from **calculon@momsbot.com** " \
                           "to **support@planet-express.com**.\n" \
                           "```quote\n*Subject*: Being a robot is great, but...\n```"

        self.send_and_test_stream_message('inbound_message',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_tagged(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Leela Turanga** added tag **Urgent**."

        self.send_and_test_stream_message('conversation_tagged',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    # Conversation automatically assigned to a teammate who replied to it.
    def test_conversation_assigned_reply(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Leela Turanga** assigned themselves."

        self.send_and_test_stream_message('conversation_assigned_reply',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_outbound_reply(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "[Outbound reply](https://app.frontapp.com/open/msg_1176ryy) " \
                           "from **support@planet-express.com** " \
                           "to **calculon@momsbot.com**."

        self.send_and_test_stream_message('outbound_reply',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_untagged(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Leela Turanga** removed tag **Urgent**."

        self.send_and_test_stream_message('conversation_untagged',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_mention(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Leela Turanga** left a comment:\n" \
                           "```quote\n@bender Could you take it from here?\n```"

        self.send_and_test_stream_message('mention',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_comment(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Bender Rodriguez** left a comment:\n" \
                           "```quote\nSure.\n```"

        self.send_and_test_stream_message('comment',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    # Conversation manually assigned to another teammate.
    def test_conversation_assigned(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Leela Turanga** assigned **Bender Rodriguez**."

        self.send_and_test_stream_message('conversation_assigned',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_unknown_webhook_request(self) -> None:
        payload = self.get_body('conversation_assigned')
        payload_json = ujson.loads(payload)
        payload_json['type'] = 'qwerty'
        result = self.client_post(self.url, ujson.dumps(payload_json),
                                  content_type="application/x-www-form-urlencoded")

        self.assert_json_error(result, "Unknown webhook request")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data('front', fixture_name, file_type="json")
