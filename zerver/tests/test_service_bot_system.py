# -*- coding: utf-8 -*-

import json
import mock
from typing import Any, Union, Mapping, Callable

from django.conf import settings
from django.test import override_settings

from zerver.lib.actions import (
    do_create_user,
    get_service_bot_events,
)
from zerver.lib.bot_lib import StateHandler, EmbeddedBotHandler
from zerver.lib.bot_storage import StateError
from zerver.lib.bot_config import set_bot_config, ConfigError, load_bot_config_template
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    get_realm,
    BotStorageData,
    UserProfile,
    Recipient,
)

import ujson

BOT_TYPE_TO_QUEUE_NAME = {
    UserProfile.OUTGOING_WEBHOOK_BOT: 'outgoing_webhooks',
    UserProfile.EMBEDDED_BOT: 'embedded_bots',
}

class TestServiceBotBasics(ZulipTestCase):
    def _get_outgoing_bot(self) -> UserProfile:
        outgoing_bot = do_create_user(
            email="bar-bot@zulip.com",
            password="test",
            realm=get_realm("zulip"),
            full_name="BarBot",
            short_name='bb',
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            bot_owner=self.example_user('cordelia'),
        )

        return outgoing_bot

    def test_service_events_for_pms(self) -> None:
        sender = self.example_user('hamlet')
        assert(not sender.is_bot)

        outgoing_bot = self._get_outgoing_bot()

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
                dict(trigger='private_message', user_profile_id=outgoing_bot.id),
            ],
        )

        self.assertEqual(event_dict, expected)

    def test_service_events_for_stream_mentions(self) -> None:
        sender = self.example_user('hamlet')
        assert(not sender.is_bot)

        outgoing_bot = self._get_outgoing_bot()

        event_dict = get_service_bot_events(
            sender=sender,
            service_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
            ],
            active_user_ids=set(),
            mentioned_user_ids={outgoing_bot.id},
            recipient_type=Recipient.STREAM,
        )

        expected = dict(
            outgoing_webhooks=[
                dict(trigger='mention', user_profile_id=outgoing_bot.id),
            ],
        )

        self.assertEqual(event_dict, expected)

class TestServiceBotStateHandler(ZulipTestCase):
    def setUp(self) -> None:
        self.user_profile = self.example_user("othello")
        self.bot_profile = do_create_user(email="embedded-bot-1@zulip.com",
                                          password="test",
                                          realm=get_realm("zulip"),
                                          full_name="EmbeddedBo1",
                                          short_name="embedded-bot-1",
                                          bot_type=UserProfile.EMBEDDED_BOT,
                                          bot_owner=self.user_profile)
        self.second_bot_profile = do_create_user(email="embedded-bot-2@zulip.com",
                                                 password="test",
                                                 realm=get_realm("zulip"),
                                                 full_name="EmbeddedBot2",
                                                 short_name="embedded-bot-2",
                                                 bot_type=UserProfile.EMBEDDED_BOT,
                                                 bot_owner=self.user_profile)

    def test_basic_storage_and_retrieval(self) -> None:
        storage = StateHandler(self.bot_profile)
        storage.put('some key', 'some value')
        storage.put('some other key', 'some other value')
        self.assertEqual(storage.get('some key'), 'some value')
        self.assertEqual(storage.get('some other key'), 'some other value')
        self.assertTrue(storage.contains('some key'))
        self.assertFalse(storage.contains('nonexistent key'))
        self.assertRaisesMessage(StateError,
                                 "Key does not exist.",
                                 lambda: storage.get('nonexistent key'))
        storage.put('some key', 'a new value')
        self.assertEqual(storage.get('some key'), 'a new value')
        second_storage = StateHandler(self.second_bot_profile)
        self.assertRaises(StateError, lambda: second_storage.get('some key'))
        second_storage.put('some key', 'yet another value')
        self.assertEqual(storage.get('some key'), 'a new value')
        self.assertEqual(second_storage.get('some key'), 'yet another value')

    def test_marshaling(self) -> None:
        storage = StateHandler(self.bot_profile)
        serializable_obj = {'foo': 'bar', 'baz': [42, 'cux']}
        storage.put('some key', serializable_obj)  # type: ignore # Ignore for testing.
        self.assertEqual(storage.get('some key'), serializable_obj)

    def test_invalid_calls(self) -> None:
        storage = StateHandler(self.bot_profile)
        storage.marshal = lambda obj: obj
        storage.demarshal = lambda obj: obj
        serializable_obj = {'foo': 'bar', 'baz': [42, 'cux']}
        with self.assertRaisesMessage(StateError, "Value type is <class 'dict'>, but should be str."):
            storage.put('some key', serializable_obj)  # type: ignore # We intend to test an invalid type.
        with self.assertRaisesMessage(StateError, "Key type is <class 'dict'>, but should be str."):
            storage.put(serializable_obj, 'some value')  # type: ignore # We intend to test an invalid type.

    # Reduce maximal storage size for faster test string construction.
    @override_settings(USER_STATE_SIZE_LIMIT=100)
    def test_storage_limit(self) -> None:
        storage = StateHandler(self.bot_profile)

        # Disable marshaling for storing a string whose size is
        # equivalent to the size of the stored object.
        storage.marshal = lambda obj: obj
        storage.demarshal = lambda obj: obj

        key = 'capacity-filling entry'
        storage.put(key, 'x' * (settings.USER_STATE_SIZE_LIMIT - len(key)))

        with self.assertRaisesMessage(StateError, "Request exceeds storage limit by 32 characters. "
                                                  "The limit is 100 characters."):
            storage.put('too much data', 'a few bits too long')

        second_storage = StateHandler(self.second_bot_profile)
        second_storage.put('another big entry', 'x' * (settings.USER_STATE_SIZE_LIMIT - 40))
        second_storage.put('normal entry', 'abcd')

    def test_entry_removal(self) -> None:
        storage = StateHandler(self.bot_profile)
        storage.put('some key', 'some value')
        storage.put('another key', 'some value')
        self.assertTrue(storage.contains('some key'))
        self.assertTrue(storage.contains('another key'))
        storage.remove('some key')
        self.assertFalse(storage.contains('some key'))
        self.assertTrue(storage.contains('another key'))
        self.assertRaises(StateError, lambda: storage.remove('some key'))

    def test_internal_endpoint(self):
        # type: () -> None
        self.login(self.user_profile.email)

        # Store some data.
        initial_dict = {'key 1': 'value 1', 'key 2': 'value 2', 'key 3': 'value 3'}
        params = {
            'storage': ujson.dumps(initial_dict)
        }
        result = self.client_put('/json/bot_storage', params)
        self.assert_json_success(result)

        # Assert the stored data for some keys.
        params = {
            'keys': ujson.dumps(['key 1', 'key 3'])
        }
        result = self.client_get('/json/bot_storage', params)
        self.assert_json_success(result)
        self.assertEqual(result.json()['storage'], {'key 3': 'value 3', 'key 1': 'value 1'})

        # Assert the stored data for all keys.
        result = self.client_get('/json/bot_storage')
        self.assert_json_success(result)
        self.assertEqual(result.json()['storage'], initial_dict)

        # Store some more data; update an entry and store a new entry
        dict_update = {'key 1': 'new value', 'key 4': 'value 4'}
        params = {
            'storage': ujson.dumps(dict_update)
        }
        result = self.client_put('/json/bot_storage', params)
        self.assert_json_success(result)

        # Assert the data was updated.
        updated_dict = initial_dict.copy()
        updated_dict.update(dict_update)
        result = self.client_get('/json/bot_storage')
        self.assert_json_success(result)
        self.assertEqual(result.json()['storage'], updated_dict)

        # Assert errors on invalid requests.
        params = {  # type: ignore # Ignore 'incompatible type "str": "List[str]"; expected "str": "str"' for testing
            'keys': ["This is a list, but should be a serialized string."]
        }
        result = self.client_get('/json/bot_storage', params)
        self.assert_json_error(result, 'Argument "keys" is not valid JSON.')

        params = {
            'keys': ujson.dumps(["key 1", "nonexistent key"])
        }
        result = self.client_get('/json/bot_storage', params)
        self.assert_json_error(result, "Key does not exist.")

        params = {
            'storage': ujson.dumps({'foo': [1, 2, 3]})
        }
        result = self.client_put('/json/bot_storage', params)
        self.assert_json_error(result, "Value type is <class 'list'>, but should be str.")

        # Remove some entries.
        keys_to_remove = ['key 1', 'key 2']
        params = {
            'keys': ujson.dumps(keys_to_remove)
        }
        result = self.client_delete('/json/bot_storage', params)
        self.assert_json_success(result)

        # Assert the entries were removed.
        for key in keys_to_remove:
            updated_dict.pop(key)
        result = self.client_get('/json/bot_storage')
        self.assert_json_success(result)
        self.assertEqual(result.json()['storage'], updated_dict)

        # Try to remove an existing and a nonexistent key.
        params = {
            'keys': ujson.dumps(['key 3', 'nonexistent key'])
        }
        result = self.client_delete('/json/bot_storage', params)
        self.assert_json_error(result, "Key does not exist.")

        # Assert an error has been thrown and no entries were removed.
        result = self.client_get('/json/bot_storage')
        self.assert_json_success(result)
        self.assertEqual(result.json()['storage'], updated_dict)

        # Remove the entire storage.
        result = self.client_delete('/json/bot_storage')
        self.assert_json_success(result)

        # Assert the entire storage has been removed.
        result = self.client_get('/json/bot_storage')
        self.assert_json_success(result)
        self.assertEqual(result.json()['storage'], {})

class TestServiceBotConfigHandler(ZulipTestCase):
    def setUp(self) -> None:
        self.user_profile = self.example_user("othello")
        self.bot_profile = self.create_test_bot('embedded', self.user_profile,
                                                full_name='Embedded bot',
                                                bot_type=UserProfile.EMBEDDED_BOT,
                                                service_name='helloworld')
        self.bot_handler = EmbeddedBotHandler(self.bot_profile)

    def test_basic_storage_and_retrieval(self) -> None:
        with self.assertRaises(ConfigError):
            self.bot_handler.get_config_info('foo')

        self.assertEqual(self.bot_handler.get_config_info('foo', optional=True), dict())

        config_dict = {"entry 1": "value 1", "entry 2": "value 2"}
        for key, value in config_dict.items():
            set_bot_config(self.bot_profile, key, value)
        self.assertEqual(self.bot_handler.get_config_info('foo'), config_dict)

        config_update = {"entry 2": "new value", "entry 3": "value 3"}
        for key, value in config_update.items():
            set_bot_config(self.bot_profile, key, value)
        config_dict.update(config_update)
        self.assertEqual(self.bot_handler.get_config_info('foo'), config_dict)

    @override_settings(BOT_CONFIG_SIZE_LIMIT=100)
    def test_config_entry_limit(self) -> None:
        set_bot_config(self.bot_profile, "some key", 'x' * (settings.BOT_CONFIG_SIZE_LIMIT-8))
        self.assertRaisesMessage(ConfigError,
                                 "Cannot store configuration. Request would require 101 characters. "
                                 "The current configuration size limit is 100 characters.",
                                 lambda: set_bot_config(self.bot_profile, "some key", 'x' * (settings.BOT_CONFIG_SIZE_LIMIT-8+1)))
        set_bot_config(self.bot_profile, "some key", 'x' * (settings.BOT_CONFIG_SIZE_LIMIT-20))
        set_bot_config(self.bot_profile, "another key", 'x')
        self.assertRaisesMessage(ConfigError,
                                 "Cannot store configuration. Request would require 116 characters. "
                                 "The current configuration size limit is 100 characters.",
                                 lambda: set_bot_config(self.bot_profile, "yet another key", 'x'))

    def test_load_bot_config_template(self) -> None:
        bot_config = load_bot_config_template('giphy')
        self.assertTrue(isinstance(bot_config, dict))
        self.assertEqual(len(bot_config), 1)

    def test_load_bot_config_template_for_bot_without_config_data(self) -> None:
        bot_config = load_bot_config_template('converter')
        self.assertTrue(isinstance(bot_config, dict))
        self.assertEqual(len(bot_config), 0)


class TestServiceBotEventTriggers(ZulipTestCase):

    def setUp(self) -> None:
        self.user_profile = self.example_user("othello")
        self.bot_profile = do_create_user(email="foo-bot@zulip.com",
                                          password="test",
                                          realm=get_realm("zulip"),
                                          full_name="FooBot",
                                          short_name="foo-bot",
                                          bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                          bot_owner=self.user_profile)
        self.second_bot_profile = do_create_user(email="bar-bot@zulip.com",
                                                 password="test",
                                                 realm=get_realm("zulip"),
                                                 full_name="BarBot",
                                                 short_name="bar-bot",
                                                 bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                                 bot_owner=self.user_profile)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_trigger_on_stream_mention_from_user(self, mock_queue_json_publish: mock.Mock) -> None:
        for bot_type, expected_queue_name in BOT_TYPE_TO_QUEUE_NAME.items():
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            content = u'@**FooBot** foo bar!!!'
            recipient = 'Denmark'
            trigger = 'mention'
            message_type = Recipient._type_names[Recipient.STREAM]

            def check_values_passed(queue_name: Any,
                                    trigger_event: Union[Mapping[Any, Any], Any],
                                    x: Callable[[Any], None]=None) -> None:
                self.assertEqual(queue_name, expected_queue_name)
                self.assertEqual(trigger_event["message"]["content"], content)
                self.assertEqual(trigger_event["message"]["display_recipient"], recipient)
                self.assertEqual(trigger_event["message"]["sender_email"], self.user_profile.email)
                self.assertEqual(trigger_event["message"]["type"], message_type)
                self.assertEqual(trigger_event['trigger'], trigger)
                self.assertEqual(trigger_event['user_profile_id'], self.bot_profile.id)
            mock_queue_json_publish.side_effect = check_values_passed

            self.send_stream_message(
                self.user_profile.email,
                'Denmark',
                content)
            self.assertTrue(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_no_trigger_on_stream_message_without_mention(self, mock_queue_json_publish: mock.Mock) -> None:
        sender_email = self.user_profile.email
        self.send_stream_message(sender_email, "Denmark")
        self.assertFalse(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_no_trigger_on_stream_mention_from_bot(self, mock_queue_json_publish: mock.Mock) -> None:
        for bot_type in BOT_TYPE_TO_QUEUE_NAME:
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            self.send_stream_message(
                self.second_bot_profile.email,
                'Denmark',
                u'@**FooBot** foo bar!!!')
            self.assertFalse(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_trigger_on_personal_message_from_user(self, mock_queue_json_publish: mock.Mock) -> None:
        for bot_type, expected_queue_name in BOT_TYPE_TO_QUEUE_NAME.items():
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            sender_email = self.user_profile.email
            recipient_email = self.bot_profile.email

            def check_values_passed(queue_name: Any,
                                    trigger_event: Union[Mapping[Any, Any], Any],
                                    x: Callable[[Any], None]=None) -> None:
                self.assertEqual(queue_name, expected_queue_name)
                self.assertEqual(trigger_event["user_profile_id"], self.bot_profile.id)
                self.assertEqual(trigger_event["trigger"], "private_message")
                self.assertEqual(trigger_event["message"]["sender_email"], sender_email)
                display_recipients = [
                    trigger_event["message"]["display_recipient"][0]["email"],
                    trigger_event["message"]["display_recipient"][1]["email"],
                ]
                self.assertTrue(sender_email in display_recipients)
                self.assertTrue(recipient_email in display_recipients)
            mock_queue_json_publish.side_effect = check_values_passed

            self.send_personal_message(sender_email, recipient_email, 'test')
            self.assertTrue(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_no_trigger_on_personal_message_from_bot(self, mock_queue_json_publish: mock.Mock) -> None:
        for bot_type in BOT_TYPE_TO_QUEUE_NAME:
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            sender_email = self.second_bot_profile.email
            recipient_email = self.bot_profile.email
            self.send_personal_message(sender_email, recipient_email)
            self.assertFalse(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_trigger_on_huddle_message_from_user(self, mock_queue_json_publish: mock.Mock) -> None:
        for bot_type, expected_queue_name in BOT_TYPE_TO_QUEUE_NAME.items():
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            self.second_bot_profile.bot_type = bot_type
            self.second_bot_profile.save()

            sender_email = self.user_profile.email
            recipient_emails = [self.bot_profile.email, self.second_bot_profile.email]
            profile_ids = [self.bot_profile.id, self.second_bot_profile.id]

            def check_values_passed(queue_name: Any,
                                    trigger_event: Union[Mapping[Any, Any], Any],
                                    x: Callable[[Any], None]=None) -> None:
                self.assertEqual(queue_name, expected_queue_name)
                self.assertIn(trigger_event["user_profile_id"], profile_ids)
                profile_ids.remove(trigger_event["user_profile_id"])
                self.assertEqual(trigger_event["trigger"], "private_message")
                self.assertEqual(trigger_event["message"]["sender_email"], sender_email)
                self.assertEqual(trigger_event["message"]["type"], u'private')
            mock_queue_json_publish.side_effect = check_values_passed

            self.send_huddle_message(sender_email, recipient_emails, 'test')
            self.assertEqual(mock_queue_json_publish.call_count, 2)
            mock_queue_json_publish.reset_mock()

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_no_trigger_on_huddle_message_from_bot(self, mock_queue_json_publish: mock.Mock) -> None:
        for bot_type in BOT_TYPE_TO_QUEUE_NAME:
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            sender_email = self.second_bot_profile.email
            recipient_emails = [self.user_profile.email, self.bot_profile.email]
            self.send_huddle_message(sender_email, recipient_emails)
            self.assertFalse(mock_queue_json_publish.called)
