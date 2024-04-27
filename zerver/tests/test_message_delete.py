from datetime import timedelta
from typing import TYPE_CHECKING, Optional, Union
from unittest import mock

import orjson
from django.db import IntegrityError
from django.utils.timezone import now as timezone_now

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.realm_settings import do_set_realm_property
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Realm, UserProfile
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class DeleteMessageTest(ZulipTestCase):
    def test_delete_message_invalid_request_format(self) -> None:
        self.login("iago")
        hamlet = self.example_user("hamlet")
        msg_id = self.send_stream_message(hamlet, "Denmark")
        result = self.client_delete(f"/json/messages/{msg_id + 1}", {"message_id": msg_id})
        self.assert_json_error(result, "Invalid message(s)")
        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_success(result)

    def test_delete_message_by_user(self) -> None:
        def set_message_deleting_params(
            delete_own_message_policy: int, message_content_delete_limit_seconds: Union[int, str]
        ) -> None:
            self.login("iago")
            result = self.client_patch(
                "/json/realm",
                {
                    "delete_own_message_policy": delete_own_message_policy,
                    "message_content_delete_limit_seconds": orjson.dumps(
                        message_content_delete_limit_seconds
                    ).decode(),
                },
            )
            self.assert_json_success(result)

        def test_delete_message_by_admin(msg_id: int) -> "TestHttpResponse":
            self.login("iago")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        def test_delete_message_by_owner(msg_id: int) -> "TestHttpResponse":
            self.login("hamlet")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        def test_delete_message_by_other_user(msg_id: int) -> "TestHttpResponse":
            self.login("cordelia")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        # Test if message deleting is not allowed(default).
        set_message_deleting_params(Realm.POLICY_ADMINS_ONLY, "unlimited")
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        msg_id = self.send_stream_message(hamlet, "Denmark")

        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_other_user(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_admin(msg_id=msg_id)
        self.assert_json_success(result)

        # Test if message deleting is allowed.
        # Test if time limit is None(no limit).
        set_message_deleting_params(Realm.POLICY_EVERYONE, "unlimited")
        msg_id = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id)
        message.date_sent = message.date_sent - timedelta(seconds=600)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_success(result)

        # Test if time limit is non-zero.
        set_message_deleting_params(Realm.POLICY_EVERYONE, 240)
        msg_id_1 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_1)
        message.date_sent = message.date_sent - timedelta(seconds=120)
        message.save()

        msg_id_2 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_2)
        message.date_sent = message.date_sent - timedelta(seconds=360)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_owner(msg_id=msg_id_1)
        self.assert_json_success(result)
        result = test_delete_message_by_owner(msg_id=msg_id_2)
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        # No limit for admin.
        result = test_delete_message_by_admin(msg_id=msg_id_2)
        self.assert_json_success(result)

        # Test multiple delete requests with no latency issues
        msg_id = self.send_stream_message(hamlet, "Denmark")
        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_success(result)
        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_error(result, "Invalid message(s)")

        # Test handling of 500 error caused by multiple delete requests due to latency.
        # see issue #11219.
        with mock.patch("zerver.views.message_edit.do_delete_messages") as m, mock.patch(
            "zerver.views.message_edit.validate_can_delete_message", return_value=None
        ), mock.patch("zerver.views.message_edit.access_message", return_value=(None, None)):
            m.side_effect = IntegrityError()
            result = test_delete_message_by_owner(msg_id=msg_id)
            self.assert_json_error(result, "Message already deleted")
            m.side_effect = Message.DoesNotExist()
            result = test_delete_message_by_owner(msg_id=msg_id)
            self.assert_json_error(result, "Message already deleted")

    def test_delete_message_sent_by_bots(self) -> None:
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        def set_message_deleting_params(
            delete_own_message_policy: int, message_content_delete_limit_seconds: Union[int, str]
        ) -> None:
            result = self.api_patch(
                iago,
                "/api/v1/realm",
                {
                    "delete_own_message_policy": delete_own_message_policy,
                    "message_content_delete_limit_seconds": orjson.dumps(
                        message_content_delete_limit_seconds
                    ).decode(),
                },
            )
            self.assert_json_success(result)

        def test_delete_message_by_admin(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(iago, f"/api/v1/messages/{msg_id}")
            return result

        def test_delete_message_by_bot_owner(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(hamlet, f"/api/v1/messages/{msg_id}")
            return result

        def test_delete_message_by_other_user(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(cordelia, f"/api/v1/messages/{msg_id}")
            return result

        set_message_deleting_params(Realm.POLICY_ADMINS_ONLY, "unlimited")

        hamlet = self.example_user("hamlet")
        test_bot = self.create_test_bot("test-bot", hamlet)
        msg_id = self.send_stream_message(test_bot, "Denmark")

        result = test_delete_message_by_other_user(msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_bot_owner(msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_admin(msg_id)
        self.assert_json_success(result)

        msg_id = self.send_stream_message(test_bot, "Denmark")
        set_message_deleting_params(Realm.POLICY_EVERYONE, "unlimited")

        result = test_delete_message_by_other_user(msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_bot_owner(msg_id)
        self.assert_json_success(result)

        msg_id = self.send_stream_message(test_bot, "Denmark")
        set_message_deleting_params(Realm.POLICY_EVERYONE, 600)

        message = Message.objects.get(id=msg_id)
        message.date_sent = timezone_now() - timedelta(seconds=700)
        message.save()

        result = test_delete_message_by_other_user(msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_bot_owner(msg_id)
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        result = test_delete_message_by_admin(msg_id)
        self.assert_json_success(result)

        # Check that the bot can also delete the messages sent by them
        # depending on the realm permissions for message deletion.
        set_message_deleting_params(Realm.POLICY_ADMINS_ONLY, 600)
        msg_id = self.send_stream_message(test_bot, "Denmark")
        result = self.api_delete(test_bot, f"/api/v1/messages/{msg_id}")
        self.assert_json_error(result, "You don't have permission to delete this message")

        set_message_deleting_params(Realm.POLICY_EVERYONE, 600)
        message = Message.objects.get(id=msg_id)
        message.date_sent = timezone_now() - timedelta(seconds=700)
        message.save()

        result = self.api_delete(test_bot, f"/api/v1/messages/{msg_id}")
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        message.date_sent = timezone_now() - timedelta(seconds=400)
        message.save()
        result = self.api_delete(test_bot, f"/api/v1/messages/{msg_id}")
        self.assert_json_success(result)

    def test_delete_message_according_to_delete_own_message_policy(self) -> None:
        def check_delete_message_by_sender(
            sender_name: str, error_msg: Optional[str] = None
        ) -> None:
            sender = self.example_user(sender_name)
            msg_id = self.send_stream_message(sender, "Verona")
            self.login_user(sender)
            result = self.client_delete(f"/json/messages/{msg_id}")
            if error_msg is None:
                self.assert_json_success(result)
            else:
                self.assert_json_error(result, error_msg)

        realm = get_realm("zulip")

        do_set_realm_property(
            realm, "delete_own_message_policy", Realm.POLICY_ADMINS_ONLY, acting_user=None
        )
        check_delete_message_by_sender("shiva", "You don't have permission to delete this message")
        check_delete_message_by_sender("iago")

        do_set_realm_property(
            realm, "delete_own_message_policy", Realm.POLICY_MODERATORS_ONLY, acting_user=None
        )
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message"
        )
        check_delete_message_by_sender("shiva")

        do_set_realm_property(
            realm, "delete_own_message_policy", Realm.POLICY_MEMBERS_ONLY, acting_user=None
        )
        check_delete_message_by_sender(
            "polonius", "You don't have permission to delete this message"
        )
        check_delete_message_by_sender("cordelia")

        do_set_realm_property(
            realm, "delete_own_message_policy", Realm.POLICY_FULL_MEMBERS_ONLY, acting_user=None
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)
        cordelia = self.example_user("cordelia")
        cordelia.date_joined = timezone_now() - timedelta(days=9)
        cordelia.save()
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message"
        )
        cordelia.date_joined = timezone_now() - timedelta(days=11)
        cordelia.save()
        check_delete_message_by_sender("cordelia")

        do_set_realm_property(
            realm, "delete_own_message_policy", Realm.POLICY_EVERYONE, acting_user=None
        )
        check_delete_message_by_sender("cordelia")
        check_delete_message_by_sender("polonius")

    def test_delete_event_sent_after_transaction_commits(self) -> None:
        """
        Tests that `send_event` is hooked to `transaction.on_commit`. This is important, because
        we don't want to end up holding locks on message rows for too long if the event queue runs
        into a problem.
        """
        hamlet = self.example_user("hamlet")
        self.send_stream_message(hamlet, "Denmark")
        message = self.get_last_message()

        with self.capture_send_event_calls(expected_num_events=1):
            with mock.patch("zerver.tornado.django_api.queue_json_publish") as m:
                m.side_effect = AssertionError(
                    "Events should be sent only after the transaction commits."
                )
                do_delete_messages(hamlet.realm, [message])

    def test_delete_message_in_unsubscribed_private_stream(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        self.assertEqual(iago.role, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login("hamlet")

        self.make_stream("privatestream", invite_only=True, history_public_to_subscribers=False)
        self.subscribe(hamlet, "privatestream")
        self.subscribe(iago, "privatestream")
        msg_id = self.send_stream_message(
            hamlet, "privatestream", topic_name="editing", content="before edit"
        )
        self.unsubscribe(iago, "privatestream")
        self.logout()
        self.login("iago")
        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_error(result, "Invalid message(s)")
        self.assertTrue(Message.objects.filter(id=msg_id).exists())

        # Ensure iago can delete the message after resubscribing, to be certain
        # it's the subscribed/unsubscribed status that's the decisive factor in the
        # permission to do so.
        self.subscribe(iago, "privatestream")
        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_success(result)
        self.assertFalse(Message.objects.filter(id=msg_id).exists())

    def test_update_first_message_id_on_stream_message_deletion(self) -> None:
        realm = get_realm("zulip")
        stream_name = "test"
        cordelia = self.example_user("cordelia")
        self.make_stream(stream_name)
        self.subscribe(cordelia, stream_name)
        message_ids = [self.send_stream_message(cordelia, stream_name) for _ in range(5)]
        first_message_id = message_ids[0]

        message = Message.objects.get(id=message_ids[3])
        do_delete_messages(realm, [message])
        stream = get_stream(stream_name, realm)
        self.assertEqual(stream.first_message_id, first_message_id)

        first_message = Message.objects.get(id=first_message_id)
        do_delete_messages(realm, [first_message])
        stream = get_stream(stream_name, realm)
        self.assertEqual(stream.first_message_id, message_ids[1])

        all_messages = Message.objects.filter(id__in=message_ids)
        with self.assert_database_query_count(23):
            do_delete_messages(realm, all_messages)
        stream = get_stream(stream_name, realm)
        self.assertEqual(stream.first_message_id, None)
