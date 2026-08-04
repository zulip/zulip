from unittest.mock import patch

import orjson
from django.conf import settings
from django.test import override_settings
from typing_extensions import override

from zerver.actions.create_user import do_create_user
from zerver.lib.bot_config import ConfigError, load_bot_config_template, set_bot_config
from zerver.lib.bot_lib import (
    EmbeddedBotEmptyRecipientsListError,
    EmbeddedBotHandler,
    EmbeddedBotQuitError,
    StateHandler,
)
from zerver.lib.bot_storage import StateError
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.validator import check_string
from zerver.models import UserProfile
from zerver.models.bots import get_service_profile
from zerver.models.realms import get_realm
from zerver.models.recipients import get_or_create_direct_message_group
from zerver.models.users import get_user


class TestEmbeddedBotMessaging(ZulipTestCase):
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
            config_data=orjson.dumps({"foo": "bar"}).decode(),
        )

    def test_pm_to_embedded_bot_using_direct_group_message(self) -> None:
        assert self.bot_profile is not None

        direct_group_message = get_or_create_direct_message_group(
            id_list=[self.user_profile.id, self.bot_profile.id]
        )

        self.send_personal_message(self.user_profile, self.bot_profile, content="help")

        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "beep boop")
        self.assertEqual(last_message.sender_id, self.bot_profile.id)
        self.assertEqual(last_message.recipient, direct_group_message.recipient)

        display_recipient = get_display_recipient(last_message.recipient)
        assert isinstance(display_recipient, list)
        self.assert_length(display_recipient, 2)
        self.assertEqual(display_recipient[0]["email"], self.user_profile.email)
        self.assertEqual(display_recipient[1]["email"], self.bot_profile.email)

    def test_stream_message_to_embedded_bot(self) -> None:
        assert self.bot_profile is not None
        self.send_stream_message(
            self.user_profile,
            "Denmark",
            content=f"@**{self.bot_profile.full_name}** foo",
            topic_name="bar",
        )
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "beep boop")
        self.assertEqual(last_message.sender_id, self.bot_profile.id)
        self.assertEqual(last_message.topic_name(), "bar")
        self.assert_message_stream_name(last_message, "Denmark")

    def test_stream_message_not_to_embedded_bot(self) -> None:
        self.send_stream_message(self.user_profile, "Denmark", content="foo", topic_name="bar")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "foo")

    def test_message_to_embedded_bot_with_initialize(self) -> None:
        assert self.bot_profile is not None
        self.subscribe(self.user_profile, "Denmark")
        with patch(
            "zulip_bots.bots.helloworld.helloworld.HelloWorldHandler.initialize", create=True
        ) as mock_initialize:
            self.send_stream_message(
                self.user_profile,
                "Denmark",
                content=f"@**{self.bot_profile.full_name}** foo",
                topic_name="bar",
            )
            mock_initialize.assert_called_once()

    def test_embedded_bot_quit_exception(self) -> None:
        assert self.bot_profile is not None
        with (
            patch(
                "zulip_bots.bots.helloworld.helloworld.HelloWorldHandler.handle_message",
                side_effect=EmbeddedBotQuitError("I'm quitting!"),
            ),
            self.assertLogs(level="WARNING") as m,
        ):
            self.send_stream_message(
                self.user_profile,
                "Denmark",
                content=f"@**{self.bot_profile.full_name}** foo",
                topic_name="bar",
            )
            self.assertEqual(m.output, ["WARNING:root:I'm quitting!"])


class TestEmbeddedBotFailures(ZulipTestCase):
    def test_message_embedded_bot_with_invalid_service(self) -> None:
        user_profile = self.example_user("othello")
        self.create_test_bot(
            short_name="embedded",
            user_profile=user_profile,
            bot_type=UserProfile.EMBEDDED_BOT,
            service_name="helloworld",
        )
        bot_profile = get_user("embedded-bot@zulip.testserver", get_realm("zulip"))
        service_profile = get_service_profile(bot_profile.id, "helloworld")
        service_profile.name = "invalid"
        service_profile.save()
        with self.assertLogs(level="ERROR") as m:
            self.send_stream_message(
                user_profile,
                "Denmark",
                content=f"@**{bot_profile.full_name}** foo",
                topic_name="bar",
            )
            self.assertEqual(
                m.output[0],
                f"ERROR:root:Error: User {bot_profile.id} has bot with invalid embedded bot service invalid",
            )


class TestServiceBotStateHandler(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("othello")
        self.bot_profile = do_create_user(
            email="embedded-bot-1@zulip.com",
            password="test",
            realm=get_realm("zulip"),
            full_name="EmbeddedBo1",
            bot_type=UserProfile.EMBEDDED_BOT,
            bot_owner=self.user_profile,
            acting_user=None,
        )
        self.second_bot_profile = do_create_user(
            email="embedded-bot-2@zulip.com",
            password="test",
            realm=get_realm("zulip"),
            full_name="EmbeddedBot2",
            bot_type=UserProfile.EMBEDDED_BOT,
            bot_owner=self.user_profile,
            acting_user=None,
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

    def test_bot_storage_restrictions(self) -> None:
        bot_storage_url = "/api/v1/bot_storage"
        result = self.api_put(self.user_profile, bot_storage_url, {"storage": "{}"})
        self.assert_json_error(result, "Must be a bot user")
        result = self.api_get(self.user_profile, bot_storage_url)
        self.assert_json_error(result, "Must be a bot user")
        result = self.api_delete(self.user_profile, bot_storage_url)
        self.assert_json_error(result, "Must be a bot user")

    def test_bot_storage_endpoint(self) -> None:
        bot_storage_url = "/api/v1/bot_storage"

        # Store some data.
        initial_dict = {"key 1": "value 1", "key 2": "value 2", "key 3": "value 3"}
        params = {
            "storage": orjson.dumps(initial_dict).decode(),
        }
        result = self.api_put(self.bot_profile, bot_storage_url, params)
        self.assert_json_success(result)

        # Assert the stored data for some keys.
        params = {
            "keys": orjson.dumps(["key 1", "key 3"]).decode(),
        }
        result = self.api_get(self.bot_profile, bot_storage_url, params)
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], {"key 3": "value 3", "key 1": "value 1"})

        # Assert the stored data for all keys.
        result = self.api_get(self.bot_profile, bot_storage_url)
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], initial_dict)

        # Store some more data; update an entry and store a new entry
        dict_update = {"key 1": "new value", "key 4": "value 4"}
        params = {
            "storage": orjson.dumps(dict_update).decode(),
        }
        result = self.api_put(self.bot_profile, bot_storage_url, params)
        self.assert_json_success(result)

        # Assert the data was updated.
        updated_dict = initial_dict.copy()
        updated_dict.update(dict_update)
        result = self.api_get(self.bot_profile, bot_storage_url)
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], updated_dict)

        # Assert errors on invalid requests.
        invalid_params = {
            "keys": ["This is a list, but should be a serialized string."],
        }
        result = self.api_get(self.bot_profile, bot_storage_url, invalid_params)
        self.assert_json_error(result, "keys is not valid JSON")

        params = {
            "keys": orjson.dumps(["key 1", "nonexistent key"]).decode(),
        }
        result = self.api_get(self.bot_profile, bot_storage_url, params)
        self.assert_json_error(result, "Key does not exist.")

        params = {
            "storage": orjson.dumps({"foo": [1, 2, 3]}).decode(),
        }
        result = self.api_put(self.bot_profile, bot_storage_url, params)
        self.assert_json_error(result, 'storage["foo"] is not a string')

        # Remove some entries.
        keys_to_remove = ["key 1", "key 2"]
        params = {
            "keys": orjson.dumps(keys_to_remove).decode(),
        }
        result = self.api_delete(self.bot_profile, bot_storage_url, params)
        self.assert_json_success(result)

        # Assert the entries were removed.
        for key in keys_to_remove:
            updated_dict.pop(key)
        result = self.api_get(self.bot_profile, bot_storage_url)
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], updated_dict)

        # Try to remove an existing and a nonexistent key.
        params = {
            "keys": orjson.dumps(["key 3", "nonexistent key"]).decode(),
        }
        result = self.api_delete(self.bot_profile, bot_storage_url, params)
        self.assert_json_error(result, "Key does not exist.")

        # Assert an error has been thrown and no entries were removed.
        result = self.api_get(self.bot_profile, bot_storage_url)
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["storage"], updated_dict)

        # Remove the entire storage.
        result = self.api_delete(self.bot_profile, bot_storage_url)
        self.assert_json_success(result)

        # Assert the entire storage has been removed.
        result = self.api_get(self.bot_profile, bot_storage_url)
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
