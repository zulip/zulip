from typing import Text
import ujson

from zerver.lib.test_classes import WebhookTestCase

class FrontHookTests(WebhookTestCase):
    STREAM_NAME = 'front'
    URL_TEMPLATE = "/api/v1/external/front?&api_key={api_key}"
    FIXTURE_DIR_NAME = 'front'

    def _test_no_message_data(self, fixture_name: Text) -> None:
        payload = self.get_body(fixture_name)
        payload_json = ujson.loads(payload)
        del payload_json['conversation']['subject']
        result = self.client_post(self.url, ujson.dumps(payload_json),
                                  content_type="application/x-www-form-urlencoded")

        self.assert_json_error(result, "Missing required data")

    def _test_no_source_name(self, fixture_name: Text) -> None:
        payload = self.get_body(fixture_name)
        payload_json = ujson.loads(payload)
        del payload_json['source']['data']['first_name']
        result = self.client_post(self.url, ujson.dumps(payload_json),
                                  content_type="application/x-www-form-urlencoded")

        self.assert_json_error(result, "Missing required data")

    def _test_no_target_name(self, fixture_name: Text) -> None:
        payload = self.get_body(fixture_name)
        payload_json = ujson.loads(payload)
        del payload_json['target']['data']['first_name']
        result = self.client_post(self.url, ujson.dumps(payload_json),
                                  content_type="application/x-www-form-urlencoded")

        self.assert_json_error(result, "Missing required data")

    def _test_no_comment(self, fixture_name: Text) -> None:
        payload = self.get_body(fixture_name)
        payload_json = ujson.loads(payload)
        del payload_json['target']['data']['body']
        result = self.client_post(self.url, ujson.dumps(payload_json),
                                  content_type="application/x-www-form-urlencoded")

        self.assert_json_error(result, "Missing required data")

    def _test_no_tag(self, fixture_name: Text) -> None:
        payload = self.get_body(fixture_name)
        payload_json = ujson.loads(payload)
        del payload_json['target']['data']['name']
        result = self.client_post(self.url, ujson.dumps(payload_json),
                                  content_type="application/x-www-form-urlencoded")

        self.assert_json_error(result, "Missing required data")

    def test_no_event_type(self) -> None:
        payload = self.get_body('1_conversation_assigned_outbound')
        payload_json = ujson.loads(payload)
        del payload_json['type']
        result = self.client_post(self.url, ujson.dumps(payload_json),
                                  content_type="application/x-www-form-urlencoded")

        self.assert_json_error(result, "Missing required data")

    def test_no_conversation_id(self) -> None:
        payload = self.get_body('1_conversation_assigned_outbound')
        payload_json = ujson.loads(payload)
        del payload_json['conversation']['id']
        result = self.client_post(self.url, ujson.dumps(payload_json),
                                  content_type="application/x-www-form-urlencoded")

        self.assert_json_error(result, "Missing required data")

    # Scenario 1: Conversation starts from an outbound message.

    # Conversation automatically assigned to a teammate who started it.
    def test_conversation_assigned_outbound(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "**Leela Turanga** assigned themselves."

        self.send_and_test_stream_message('1_conversation_assigned_outbound',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_outbound_message(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "[Outbound message](https://app.frontapp.com/open/msg_1176ie2) " \
                           "from **support@planet-express.com** " \
                           "to **calculon@momsbot.com**.\n" \
                           "```quote\n*Subject*: Your next delivery is on Epsilon 96Z\n```"

        self.send_and_test_stream_message('2_outbound_message',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_outbound_message_error(self) -> None:
        self._test_no_message_data('2_outbound_message')

    def test_conversation_archived(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "Archived by **Leela Turanga**."

        self.send_and_test_stream_message('3_conversation_archived',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_archived_error(self) -> None:
        self._test_no_source_name('3_conversation_archived')

    def test_conversation_reopened(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "Reopened by **Leela Turanga**."

        self.send_and_test_stream_message('4_conversation_reopened',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_reopened_error(self) -> None:
        self._test_no_source_name('4_conversation_reopened')

    def test_conversation_deleted(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "Deleted by **Leela Turanga**."

        self.send_and_test_stream_message('5_conversation_deleted',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_deleted_error(self) -> None:
        self._test_no_source_name('5_conversation_deleted')

    def test_conversation_restored(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "Restored by **Leela Turanga**."

        self.send_and_test_stream_message('6_conversation_restored',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_restored_error(self) -> None:
        self._test_no_source_name('6_conversation_restored')

    def test_conversation_unassigned(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "Unassined by **Leela Turanga**."

        self.send_and_test_stream_message('7_conversation_unassigned',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_unassigned_error(self) -> None:
        self._test_no_source_name('7_conversation_unassigned')

    def test_mention_all(self) -> None:
        expected_subject = 'cnv_keo696'
        expected_message = "**Leela Turanga** left a comment:\n" \
                           "```quote\n@all Could someone else take this?\n```"

        self.send_and_test_stream_message('8_mention_all',
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

        self.send_and_test_stream_message('9_inbound_message',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_inbound_message_error(self) -> None:
        self._test_no_message_data('9_inbound_message')

    def test_conversation_tagged(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Leela Turanga** added tag **Urgent**."

        self.send_and_test_stream_message('10_conversation_tagged',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_tagged_error(self) -> None:
        self._test_no_tag('10_conversation_tagged')

    # Conversation automatically assigned to a teammate who replied to it.
    def test_conversation_assigned_reply(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Leela Turanga** assigned themselves."

        self.send_and_test_stream_message('11_conversation_assigned_reply',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_outbound_reply(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "[Outbound reply](https://app.frontapp.com/open/msg_1176ryy) " \
                           "from **support@planet-express.com** " \
                           "to **calculon@momsbot.com**."

        self.send_and_test_stream_message('12_outbound_reply',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_outbound_reply_error(self) -> None:
        self._test_no_message_data('12_outbound_reply')

    def test_conversation_untagged(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Leela Turanga** removed tag **Urgent**."

        self.send_and_test_stream_message('13_conversation_untagged',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_untagged_error(self) -> None:
        self._test_no_tag('13_conversation_untagged')

    def test_mention(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Leela Turanga** left a comment:\n" \
                           "```quote\n@bender Could you take it from here?\n```"

        self.send_and_test_stream_message('14_mention',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_comment(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Bender Rodriguez** left a comment:\n" \
                           "```quote\nSure.\n```"

        self.send_and_test_stream_message('15_comment',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_comment_error(self) -> None:
        self._test_no_comment('15_comment')

    # Conversation manually assigned to another teammate.
    def test_conversation_assigned(self) -> None:
        expected_subject = 'cnv_keocka'
        expected_message = "**Leela Turanga** assigned **Bender Rodriguez**."

        self.send_and_test_stream_message('16_conversation_assigned',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_conversation_assigned_error(self) -> None:
        self._test_no_target_name('16_conversation_assigned')

    def test_unknown_webhook_request(self) -> None:
        payload = self.get_body('16_conversation_assigned')
        payload_json = ujson.loads(payload)
        payload_json['type'] = 'qwerty'
        result = self.client_post(self.url, ujson.dumps(payload_json),
                                  content_type="application/x-www-form-urlencoded")

        self.assert_json_error(result, "Unknown webhook request")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data('front', fixture_name, file_type="json")
