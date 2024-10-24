import orjson
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic_settings import set_topic_settings_in_database
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream


class TopicSettingsTest(ZulipTestCase):
    INVALID_STREAM_ID = 99999

    def test_update_topic_settings_by_admin_or_moderator(self) -> None:
        realm = get_realm("zulip")
        self.login("iago")

        stream = get_stream("Verona", realm)
        url = "/json/topic_settings"

        result = self.client_post(
            url,
            {"stream_id": stream.id, "topic": "Verona3", "is_locked": orjson.dumps(True).decode()},
        )
        self.assert_json_success(result)

        self.login("shiva")

        result = self.client_post(
            url,
            {"stream_id": stream.id, "topic": "Verona3", "is_locked": orjson.dumps(False).decode()},
        )
        self.assert_json_success(result)

    def test_update_topic_lock_settings_without_access(self) -> None:
        realm = get_realm("zulip")
        stream = get_stream("Verona", realm)
        url = "/json/topic_settings"

        self.login("aaron")
        result = self.client_post(
            url,
            {"stream_id": stream.id, "topic": "Verona3", "is_locked": orjson.dumps(True).decode()},
        )
        self.assert_json_error(result, "Must be an organization moderator.")

    def test_post_message_in_a_lock_topic_by_non_moderator_and_moderator(self) -> None:
        url = "/json/messages"
        realm = get_realm("zulip")
        iago = self.example_user("iago")
        stream = get_stream("Verona", realm)
        set_topic_settings_in_database(
            iago.id, realm.id, stream.id, "Verona3", True, timezone_now()
        )

        recipient_type_name = ["stream", "channel"]
        self.login("hamlet")

        for recipient_type in recipient_type_name:
            result = self.client_post(
                url,
                {
                    "type": recipient_type,
                    "to": orjson.dumps("Verona").decode(),
                    "content": "Test message",
                    "topic": "Verona3",
                },
            )
            self.assert_json_error(result, "This topic has been locked by a moderator.")

        self.login("shiva")

        for recipient_type in recipient_type_name:
            result = self.client_post(
                url,
                {
                    "type": recipient_type,
                    "to": orjson.dumps("Verona").decode(),
                    "content": "Tests message",
                    "topic": "Verona3",
                },
            )
            self.assert_json_success(result)

    def test_move_message_to_lock_topic(self) -> None:
        self.login("hamlet")
        realm = get_realm("zulip")
        stream = get_stream("Denmark", realm)
        iago = self.example_user("iago")
        set_topic_settings_in_database(iago.id, realm.id, stream.id, "edited", True, timezone_now())
        msg_id = self.send_stream_message(
            self.example_user("hamlet"), "Denmark", topic_name="topic1"
        )

        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "topic": "edited",
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_error(result, "This topic has been locked by a moderator.")

        # Authorized users (moderators and admin) can post messages in a lock topic
        self.login("shiva")
        result = self.client_patch(
            f"/json/messages/{msg_id}",
            {
                "topic": "edited",
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)

    def test_invalid_stream(self) -> None:
        self.login("iago")
        url = "/json/topic_settings"

        result = self.client_post(
            url,
            {
                "stream_id": self.INVALID_STREAM_ID,
                "topic": "Verona3",
                "is_locked": orjson.dumps(True).decode(),
            },
        )
        self.assert_json_error(result, "Invalid channel ID")
