import json
from collections.abc import Callable
from contextlib import nullcontext
from functools import wraps
from typing import Any, Concatenate
from unittest import mock

import orjson
import responses
from django.conf import settings
from django.test import override_settings
from typing_extensions import ParamSpec, override

from zerver.actions.message_send import get_service_bot_events
from zerver.actions.users import do_update_outgoing_webhook_service
from zerver.lib.bot_config import ConfigError, load_bot_config_template, set_bot_config
from zerver.lib.bot_lib import (
    BOT_SERVICE_TRIGGER_EVENT_NAME,
    EmbeddedBotEmptyRecipientsListError,
    EmbeddedBotHandler,
    StateHandler,
)
from zerver.lib.bot_storage import StateError
from zerver.lib.integrations import EMBEDDED_BOTS
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish
from zerver.lib.validator import check_string
from zerver.models import Recipient, UserProfile
from zerver.models.bots import Service, get_bot_services
from zerver.models.messages import UserMessage

BOT_TYPE_TO_QUEUE_NAME = {
    UserProfile.OUTGOING_WEBHOOK_BOT: "outgoing_webhooks",
    UserProfile.EMBEDDED_BOT: "embedded_bots",
}


class TestServiceBotBasics(ZulipTestCase):
    def _get_outgoing_bot(self) -> UserProfile:
        outgoing_bot = self.create_test_bot(
            "bar",
            self.example_user("cordelia"),
            full_name="BarBot",
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
        )

        return outgoing_bot

    def test_service_events_for_pms(self) -> None:
        sender = self.example_user("hamlet")
        assert not sender.is_bot

        outgoing_bot = self._get_outgoing_bot()
        assert outgoing_bot.bot_type is not None

        event_dict = get_service_bot_events(
            sender=sender,
            service_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
            ],
            active_user_ids={outgoing_bot.id},
            mentioned_user_ids=set(),
            recipient_type=Recipient.PERSONAL,
        )

        expected = dict(
            outgoing_webhooks=[
                dict(
                    received_trigger_events=[Service.BOT_TRIGGER_DMS_RECEIVED],
                    user_profile_id=outgoing_bot.id,
                ),
            ],
        )

        self.assertEqual(event_dict, expected)

    def test_spurious_mentions(self) -> None:
        sender = self.example_user("hamlet")
        assert not sender.is_bot

        outgoing_bot = self._get_outgoing_bot()
        assert outgoing_bot.bot_type is not None

        # If outgoing_bot is not in mentioned_user_ids,
        # we will skip over it.  This tests an anomaly
        # of the code that our query for bots can include
        # bots that may not actually be mentioned, and it's
        # easiest to just filter them in get_service_bot_events.
        event_dict = get_service_bot_events(
            sender=sender,
            service_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
            ],
            active_user_ids={outgoing_bot.id},
            mentioned_user_ids=set(),
            recipient_type=Recipient.STREAM,
        )

        self.assert_length(event_dict, 0)

    def test_service_events_for_stream_mentions(self) -> None:
        sender = self.example_user("hamlet")
        assert not sender.is_bot

        outgoing_bot = self._get_outgoing_bot()
        assert outgoing_bot.bot_type is not None

        cordelia = self.example_user("cordelia")

        red_herring_bot = self.create_test_bot(
            short_name="whatever",
            user_profile=cordelia,
        )

        event_dict = get_service_bot_events(
            sender=sender,
            service_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
                (red_herring_bot.id, UserProfile.OUTGOING_WEBHOOK_BOT),
            ],
            active_user_ids=set(),
            mentioned_user_ids={outgoing_bot.id},
            recipient_type=Recipient.STREAM,
        )

        expected = dict(
            outgoing_webhooks=[
                dict(
                    received_trigger_events=[Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS],
                    user_profile_id=outgoing_bot.id,
                ),
            ],
        )

        self.assertEqual(event_dict, expected)

    def test_service_events_for_private_mentions(self) -> None:
        """Service bots should not get access to mentions if they aren't a
        direct recipient."""
        sender = self.example_user("hamlet")
        assert not sender.is_bot

        outgoing_bot = self._get_outgoing_bot()
        assert outgoing_bot.bot_type is not None

        event_dict = get_service_bot_events(
            sender=sender,
            service_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
            ],
            active_user_ids=set(),
            mentioned_user_ids={outgoing_bot.id},
            recipient_type=Recipient.PERSONAL,
        )

        self.assert_length(event_dict, 0)

    def test_service_events_with_unexpected_bot_type(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        bot = self.create_test_bot(
            short_name="whatever",
            user_profile=cordelia,
        )
        wrong_bot_type = UserProfile.INCOMING_WEBHOOK_BOT
        bot.bot_type = wrong_bot_type
        bot.save()

        with self.assertLogs(level="ERROR") as m:
            event_dict = get_service_bot_events(
                sender=hamlet,
                service_bot_tuples=[
                    (bot.id, wrong_bot_type),
                ],
                active_user_ids=set(),
                mentioned_user_ids={bot.id},
                recipient_type=Recipient.PERSONAL,
            )

        self.assert_length(event_dict, 0)
        self.assertEqual(
            m.output[0],
            f"ERROR:root:Unexpected bot_type for Service bot id={bot.id}: {wrong_bot_type}",
        )


class TestServiceBotStateHandler(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("othello")
        self.bot_profile = self.create_test_bot(
            "embedded",
            self.user_profile,
            full_name="EmbeddedBo1",
            bot_type=UserProfile.EMBEDDED_BOT,
            service_name="helloworld",
        )
        self.second_bot_profile = self.create_test_bot(
            "embedded2",
            self.user_profile,
            full_name="EmbeddedBot2",
            bot_type=UserProfile.EMBEDDED_BOT,
            service_name="helloworld",
        )

    def test_basic_storage_and_retrieval(self) -> None:
        storage = StateHandler(self.bot_profile)
        storage.put("some key", "some value")
        storage.put("some other key", "some other value")
        self.assertEqual(storage.get("some key"), "some value")
        self.assertEqual(storage.get("some other key"), "some other value")
        self.assertTrue(storage.contains("some key"))
        self.assertFalse(storage.contains("nonexistent key"))
        self.assertRaisesMessage(
            StateError, "Key does not exist.", lambda: storage.get("nonexistent key")
        )
        storage.put("some key", "a new value")
        self.assertEqual(storage.get("some key"), "a new value")
        second_storage = StateHandler(self.second_bot_profile)
        self.assertRaises(StateError, lambda: second_storage.get("some key"))
        second_storage.put("some key", "yet another value")
        self.assertEqual(storage.get("some key"), "a new value")
        self.assertEqual(second_storage.get("some key"), "yet another value")

    def test_marshaling(self) -> None:
        storage = StateHandler(self.bot_profile)
        serializable_obj = {"foo": "bar", "baz": [42, "cux"]}
        storage.put("some key", serializable_obj)
        self.assertEqual(storage.get("some key"), serializable_obj)

    # Reduce maximal storage size for faster test string construction.
    @override_settings(USER_STATE_SIZE_LIMIT=100)
    def test_storage_limit(self) -> None:
        storage = StateHandler(self.bot_profile)

        # Disable marshaling for storing a string whose size is
        # equivalent to the size of the stored object.
        storage.marshal = lambda obj: check_string("obj", obj)
        storage.demarshal = lambda obj: obj

        key = "capacity-filling entry"
        storage.put(key, "x" * (settings.USER_STATE_SIZE_LIMIT - len(key)))

        with self.assertRaisesMessage(
            StateError,
            "Request exceeds storage limit by 32 characters. The limit is 100 characters.",
        ):
            storage.put("too much data", "a few bits too long")

        second_storage = StateHandler(self.second_bot_profile)
        second_storage.put("another big entry", "x" * (settings.USER_STATE_SIZE_LIMIT - 40))
        second_storage.put("normal entry", "abcd")

    def test_entry_removal(self) -> None:
        storage = StateHandler(self.bot_profile)
        storage.put("some key", "some value")
        storage.put("another key", "some value")
        self.assertTrue(storage.contains("some key"))
        self.assertTrue(storage.contains("another key"))
        storage.remove("some key")
        self.assertFalse(storage.contains("some key"))
        self.assertTrue(storage.contains("another key"))
        self.assertRaises(StateError, lambda: storage.remove("some key"))

    def test_internal_endpoint(self) -> None:
        self.login_user(self.user_profile)

        # Store some data.
        initial_dict = {"key 1": "value 1", "key 2": "value 2", "key 3": "value 3"}
        params = {
            "storage": orjson.dumps(initial_dict).decode(),
        }
        result = self.client_put("/json/bot_storage", params)
        self.assert_json_success(result)

        # Assert the stored data for some keys.
        params = {
            "keys": orjson.dumps(["key 1", "key 3"]).decode(),
        }
        result = self.client_get("/json/bot_storage", params)
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], {"key 3": "value 3", "key 1": "value 1"})

        # Assert the stored data for all keys.
        result = self.client_get("/json/bot_storage")
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], initial_dict)

        # Store some more data; update an entry and store a new entry
        dict_update = {"key 1": "new value", "key 4": "value 4"}
        params = {
            "storage": orjson.dumps(dict_update).decode(),
        }
        result = self.client_put("/json/bot_storage", params)
        self.assert_json_success(result)

        # Assert the data was updated.
        updated_dict = initial_dict.copy()
        updated_dict.update(dict_update)
        result = self.client_get("/json/bot_storage")
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], updated_dict)

        # Assert errors on invalid requests.
        invalid_params = {
            "keys": ["This is a list, but should be a serialized string."],
        }
        result = self.client_get("/json/bot_storage", invalid_params)
        self.assert_json_error(result, "keys is not valid JSON")

        params = {
            "keys": orjson.dumps(["key 1", "nonexistent key"]).decode(),
        }
        result = self.client_get("/json/bot_storage", params)
        self.assert_json_error(result, "Key does not exist.")

        params = {
            "storage": orjson.dumps({"foo": [1, 2, 3]}).decode(),
        }
        result = self.client_put("/json/bot_storage", params)
        self.assert_json_error(result, 'storage["foo"] is not a string')

        # Remove some entries.
        keys_to_remove = ["key 1", "key 2"]
        params = {
            "keys": orjson.dumps(keys_to_remove).decode(),
        }
        result = self.client_delete("/json/bot_storage", params)
        self.assert_json_success(result)

        # Assert the entries were removed.
        for key in keys_to_remove:
            updated_dict.pop(key)
        result = self.client_get("/json/bot_storage")
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], updated_dict)

        # Try to remove an existing and a nonexistent key.
        params = {
            "keys": orjson.dumps(["key 3", "nonexistent key"]).decode(),
        }
        result = self.client_delete("/json/bot_storage", params)
        self.assert_json_error(result, "Key does not exist.")

        # Assert an error has been thrown and no entries were removed.
        result = self.client_get("/json/bot_storage")
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], updated_dict)

        # Remove the entire storage.
        result = self.client_delete("/json/bot_storage")
        self.assert_json_success(result)

        # Assert the entire storage has been removed.
        result = self.client_get("/json/bot_storage")
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], {})


class TestServiceBotConfigHandler(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("othello")
        self.bot_profile = self.create_test_bot(
            "embedded",
            self.user_profile,
            full_name="Embedded bot",
            bot_type=UserProfile.EMBEDDED_BOT,
            service_name="helloworld",
        )
        self.bot_handler = EmbeddedBotHandler(self.bot_profile)

    def test_basic_storage_and_retrieval(self) -> None:
        with self.assertRaises(ConfigError):
            self.bot_handler.get_config_info("foo")

        self.assertEqual(self.bot_handler.get_config_info("foo", optional=True), {})

        config_dict = {"entry 1": "value 1", "entry 2": "value 2"}
        for key, value in config_dict.items():
            set_bot_config(self.bot_profile, key, value)
        self.assertEqual(self.bot_handler.get_config_info("foo"), config_dict)

        config_update = {"entry 2": "new value", "entry 3": "value 3"}
        for key, value in config_update.items():
            set_bot_config(self.bot_profile, key, value)
        config_dict.update(config_update)
        self.assertEqual(self.bot_handler.get_config_info("foo"), config_dict)

    @override_settings(BOT_CONFIG_SIZE_LIMIT=100)
    def test_config_entry_limit(self) -> None:
        set_bot_config(self.bot_profile, "some key", "x" * (settings.BOT_CONFIG_SIZE_LIMIT - 8))
        self.assertRaisesMessage(
            ConfigError,
            "Cannot store configuration. Request would require 101 characters. "
            "The current configuration size limit is 100 characters.",
            lambda: set_bot_config(
                self.bot_profile, "some key", "x" * (settings.BOT_CONFIG_SIZE_LIMIT - 8 + 1)
            ),
        )
        set_bot_config(self.bot_profile, "some key", "x" * (settings.BOT_CONFIG_SIZE_LIMIT - 20))
        set_bot_config(self.bot_profile, "another key", "x")
        self.assertRaisesMessage(
            ConfigError,
            "Cannot store configuration. Request would require 116 characters. "
            "The current configuration size limit is 100 characters.",
            lambda: set_bot_config(self.bot_profile, "yet another key", "x"),
        )

    def test_load_bot_config_template(self) -> None:
        bot_config = load_bot_config_template("giphy")
        self.assertTrue(isinstance(bot_config, dict))
        self.assert_length(bot_config, 1)

    def test_load_bot_config_template_for_bot_without_config_data(self) -> None:
        bot_config = load_bot_config_template("converter")
        self.assertTrue(isinstance(bot_config, dict))
        self.assert_length(bot_config, 0)

    def test_bot_send_pm_with_empty_recipients_list(self) -> None:
        with self.assertRaisesRegex(
            EmbeddedBotEmptyRecipientsListError, "Message must have recipients!"
        ):
            self.bot_handler.send_message(message={"type": "private", "to": []})


ParamT = ParamSpec("ParamT")


def for_all_bot_types(
    test_func: Callable[Concatenate["TestServiceBotEventTriggers", ParamT], None],
) -> Callable[Concatenate["TestServiceBotEventTriggers", ParamT], None]:
    @wraps(test_func)
    def _wrapped(
        self: "TestServiceBotEventTriggers", /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> None:
        for bot_type in BOT_TYPE_TO_QUEUE_NAME:
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()
            if bot_type == UserProfile.EMBEDDED_BOT:
                service = get_bot_services(self.bot_profile.id)[0]
                service.name = EMBEDDED_BOTS[0].name
                service.save()

            test_func(self, *args, **kwargs)

    return _wrapped


def patch_queue_publish(
    method_to_patch: str,
) -> Callable[
    [Callable[["TestServiceBotEventTriggers", mock.Mock], None]],
    Callable[["TestServiceBotEventTriggers"], None],
]:
    def inner(
        func: Callable[["TestServiceBotEventTriggers", mock.Mock], None],
    ) -> Callable[["TestServiceBotEventTriggers"], None]:
        @wraps(func)
        def _wrapped(self: "TestServiceBotEventTriggers") -> None:
            with mock_queue_publish(method_to_patch) as m:
                func(self, m)

        return _wrapped

    return inner


class TestServiceBotEventTriggers(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("othello")
        self.bot_profile = self.create_test_bot(
            "foo",
            self.user_profile,
            full_name="FooBot",
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            payload_url='"https://bot.example.com/"',
        )
        self.second_bot_profile = self.create_test_bot(
            "bar",
            self.user_profile,
            full_name="BarBot",
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            payload_url='"https://bot.example.com/"',
        )

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_trigger_on_stream_mention_from_user(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        content = "@**FooBot** foo bar!!!"
        recipient = "Denmark"
        recipient_type = "stream"

        def check_values_passed(
            queue_name: Any,
            trigger_event: dict[str, Any],
            processor: Callable[[Any], None] | None = None,
        ) -> None:
            assert self.bot_profile.bot_type
            self.assertEqual(queue_name, BOT_TYPE_TO_QUEUE_NAME[self.bot_profile.bot_type])
            self.assertEqual(trigger_event["message"]["content"], content)
            self.assertEqual(trigger_event["message"]["display_recipient"], recipient)
            self.assertEqual(trigger_event["message"]["sender_email"], self.user_profile.email)
            self.assertEqual(trigger_event["message"]["type"], recipient_type)
            self.assertEqual(
                trigger_event["received_trigger_events"], [Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS]
            )
            self.assertEqual(trigger_event["user_profile_id"], self.bot_profile.id)

        mock_queue_event_on_commit.side_effect = check_values_passed

        self.send_stream_message(self.user_profile, "Denmark", content)
        self.assertTrue(mock_queue_event_on_commit.called)

    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_no_trigger_on_stream_message_without_mention(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        sender = self.user_profile
        self.send_stream_message(sender, "Denmark")
        self.assertFalse(mock_queue_event_on_commit.called)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_no_trigger_on_stream_mention_from_bot(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        self.send_stream_message(self.second_bot_profile, "Denmark", "@**FooBot** foo bar!!!")
        self.assertFalse(mock_queue_event_on_commit.called)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_no_trigger_on_mention_from_bot_with_no_trigger(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        foo_bot = self.bot_profile
        # No trigger if the bot doesn't have the "all_direct_mentions" trigger.
        # Set the bots' trigger to only "dms_received".
        do_update_outgoing_webhook_service(
            foo_bot,
            interface=1,
            base_url="https://bot.example.com/",
            triggers=[Service.BOT_TRIGGER_DMS_RECEIVED],
            acting_user=None,
        )
        self.send_stream_message(self.second_bot_profile, "Denmark", "@**FooBot** foo bar!!!")
        self.assertFalse(mock_queue_event_on_commit.called)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_trigger_on_personal_message_from_user(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        sender = self.user_profile
        recipient = self.bot_profile

        def check_values_passed(
            queue_name: Any,
            trigger_event: dict[str, Any],
            processor: Callable[[Any], None] | None = None,
        ) -> None:
            assert self.bot_profile.bot_type
            self.assertEqual(queue_name, BOT_TYPE_TO_QUEUE_NAME[self.bot_profile.bot_type])
            self.assertEqual(trigger_event["user_profile_id"], self.bot_profile.id)
            self.assertEqual(
                trigger_event["received_trigger_events"], [Service.BOT_TRIGGER_DMS_RECEIVED]
            )
            self.assertEqual(trigger_event["message"]["sender_email"], sender.email)
            display_recipients = [
                trigger_event["message"]["display_recipient"][0]["email"],
                trigger_event["message"]["display_recipient"][1]["email"],
            ]
            self.assertTrue(sender.email in display_recipients)
            self.assertTrue(recipient.email in display_recipients)

        mock_queue_event_on_commit.side_effect = check_values_passed

        self.send_personal_message(sender, recipient, "test")
        self.assertTrue(mock_queue_event_on_commit.called)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_no_trigger_on_personal_message_from_bot(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        sender = self.second_bot_profile
        recipient = self.bot_profile
        self.send_personal_message(sender, recipient)
        self.assertFalse(mock_queue_event_on_commit.called)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_trigger_on_group_direct_message_from_user(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        self.second_bot_profile.bot_type = self.bot_profile.bot_type
        self.second_bot_profile.save()

        sender = self.user_profile
        recipients = [self.bot_profile, self.second_bot_profile]
        profile_ids = [self.bot_profile.id, self.second_bot_profile.id]

        def check_values_passed(
            queue_name: Any,
            trigger_event: dict[str, Any],
            processor: Callable[[Any], None] | None = None,
        ) -> None:
            assert self.bot_profile.bot_type
            self.assertEqual(queue_name, BOT_TYPE_TO_QUEUE_NAME[self.bot_profile.bot_type])
            self.assertIn(trigger_event["user_profile_id"], profile_ids)
            profile_ids.remove(trigger_event["user_profile_id"])
            self.assertEqual(
                trigger_event["received_trigger_events"], [Service.BOT_TRIGGER_DMS_RECEIVED]
            )
            self.assertEqual(trigger_event["message"]["sender_email"], sender.email)
            self.assertEqual(trigger_event["message"]["type"], "private")

        mock_queue_event_on_commit.side_effect = check_values_passed

        self.send_group_direct_message(sender, recipients, "test")
        self.assertEqual(mock_queue_event_on_commit.call_count, 2)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_no_trigger_on_group_direct_message_from_bot(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        sender = self.second_bot_profile
        recipients = [self.user_profile, self.bot_profile]
        self.send_group_direct_message(sender, recipients)
        self.assertFalse(mock_queue_event_on_commit.called)

    @responses.activate
    @for_all_bot_types
    def test_no_trigger_when_bot_lacks_relevant_triggers(self) -> None:
        sender = self.user_profile
        recipient = self.bot_profile
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        # No response when direct messaged if the bot doesn't have
        # the appropriate trigger.
        do_update_outgoing_webhook_service(
            recipient,
            interface=1,
            base_url="https://bot.example.com/",
            triggers=[Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS],
            acting_user=None,
        )
        service = get_bot_services(recipient.id)[0]
        assert service.triggers == [Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS]

        message_id = self.send_personal_message(sender, recipient)
        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertNotIn("read", bot_user_message.flags_list())

        # No response when mentioned if the bot doesn't have the
        # appropriate trigger.
        do_update_outgoing_webhook_service(
            recipient,
            interface=1,
            base_url="https://bot.example.com/",
            triggers=[Service.BOT_TRIGGER_DMS_RECEIVED],
            acting_user=None,
        )
        service = get_bot_services(recipient.id)[0]
        assert service.triggers == [Service.BOT_TRIGGER_DMS_RECEIVED]

        channel = "Denmark"
        self.subscribe(self.bot_profile, channel)
        self.subscribe(sender, channel)
        message_id = self.send_stream_message(sender, channel, "@**FooBot** foo bar!!!")
        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertNotIn("read", bot_user_message.flags_list())

    @responses.activate
    @for_all_bot_types
    def test_flag_messages_service_bots_has_processed(self) -> None:
        """
        Verifies that once an event has been processed by the service bot's
        queue processor, the message is marked as processed (flagged with `read`).
        """
        sender = self.user_profile
        recipients = [self.user_profile, self.bot_profile, self.second_bot_profile]
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        with self.assertLogs(level="INFO"):
            message_id = self.send_group_direct_message(
                sender, recipients, content=f"@**{self.bot_profile.full_name}** foo"
            )

        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertIn("read", bot_user_message.flags_list())

    @responses.activate
    @for_all_bot_types
    def test_no_bot_message_read_flag_when_no_service_triggered(self) -> None:
        """
        Verifies that when a send message event doesn't trigger a bot's service,
        the message isn't flagged as read."
        """
        sender = self.user_profile

        service = get_bot_services(self.bot_profile.id)[0]
        service.triggers = [Service.BOT_TRIGGER_DMS_RECEIVED]
        service.save()

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        channel = "Denmark"
        self.subscribe(sender, channel)
        self.subscribe(self.bot_profile, channel)
        with self.assertNoLogs(level="INFO"):
            message_id = self.send_stream_message(
                sender, channel, content=f"@**{self.bot_profile.full_name}** foo"
            )

        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertNotIn("read", bot_user_message.flags_list())

    @responses.activate
    @for_all_bot_types
    def test_direct_mention_to_bot_with_multiple_triggers(self) -> None:
        sender = self.user_profile
        service = get_bot_services(self.bot_profile.id)[0]
        self.assertListEqual(
            sorted(service.triggers),
            sorted([Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS, Service.BOT_TRIGGER_DMS_RECEIVED]),
        )

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        ctx = (
            self.assertLogs(level="INFO")
            if self.bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT
            else nullcontext()
        )

        channel = "Denmark"
        channel_mention = f"@**{self.bot_profile.full_name}** foo"

        with ctx:
            self.send_stream_message(sender, channel, content=channel_mention)

        request = responses.calls[0].request
        assert request.body is not None
        payload = json.loads(request.body)

        self.assertEqual(
            payload["trigger"],
            BOT_SERVICE_TRIGGER_EVENT_NAME[Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS],
        )
        self.assertEqual(payload["message"]["content"], channel_mention)
        self.assertEqual(payload["bot_email"], self.bot_profile.email)

    @responses.activate
    @for_all_bot_types
    def test_dm_to_bot_with_multiple_triggers(self) -> None:
        sender = self.user_profile
        service = get_bot_services(self.bot_profile.id)[0]
        self.assertListEqual(
            sorted(service.triggers),
            sorted([Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS, Service.BOT_TRIGGER_DMS_RECEIVED]),
        )

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        ctx = (
            self.assertLogs(level="INFO")
            if self.bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT
            else nullcontext()
        )
        recipients = [self.user_profile, self.bot_profile]
        dm_content = "hello, this is a direct message"
        with ctx:
            self.send_group_direct_message(sender, recipients, content=dm_content)

        request = responses.calls[0].request
        assert request.body is not None
        payload = json.loads(request.body)

        self.assertEqual(
            payload["trigger"],
            BOT_SERVICE_TRIGGER_EVENT_NAME[Service.BOT_TRIGGER_DMS_RECEIVED],
        )
        self.assertEqual(payload["message"]["content"], dm_content)
        self.assertEqual(payload["bot_email"], self.bot_profile.email)

    @responses.activate
    @for_all_bot_types
    def test_old_service_bot_with_no_configured_triggers(self) -> None:
        """
        Verifies that service bots created before the multiple-triggers system
        was implemented are treated like they have the default triggers
        (`get_default_service_bot_triggers`)
        """
        sender = self.user_profile
        recipients = [self.user_profile, self.bot_profile]
        service = get_bot_services(self.bot_profile.id)[0]
        service.triggers = []
        service.save()
        self.assertListEqual(
            sorted(service.triggers),
            sorted([]),
        )

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        ctx = (
            self.assertLogs(level="INFO")
            if self.bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT
            else nullcontext()
        )

        with ctx:
            message_id = self.send_group_direct_message(
                sender,
                recipients,
                content="hello, this is a direct message",
            )
        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertIn("read", bot_user_message.flags_list())

        channel = "Denmark"
        self.subscribe(self.bot_profile, channel)
        self.subscribe(self.user_profile, channel)

        with ctx:
            message_id = self.send_stream_message(
                self.user_profile,
                channel,
                content=f"@**{self.bot_profile.full_name}** foo",
            )
        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertIn("read", bot_user_message.flags_list())
