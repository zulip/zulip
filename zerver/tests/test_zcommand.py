from typing import Any
from unittest import mock

import orjson

from zerver.lib.actions import get_topic_messages
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile, get_huddle_recipient


class MockResponse:
    def __init__(self, text: str, status_code: int) -> None:
        self.text = text
        self.status_code = status_code

class ZcommandTest(ZulipTestCase):

    def test_invalid_zcommand(self) -> None:
        self.login('hamlet')

        payload = dict(command="/boil-ocean")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "No such command: boil-ocean")

        payload = dict(command="boil-ocean")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "There should be a leading slash in the zcommand.")

    def test_ping_zcommand(self) -> None:
        self.login('hamlet')

        payload = dict(command="/ping")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)

    def test_night_zcommand(self) -> None:
        self.login('hamlet')
        user = self.example_user('hamlet')
        user.color_scheme = UserProfile.COLOR_SCHEME_LIGHT
        user.save()

        payload = dict(command="/night")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('Changed to night', result.json()['msg'])

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('still in night mode', result.json()['msg'])

    def test_day_zcommand(self) -> None:
        self.login('hamlet')
        user = self.example_user('hamlet')
        user.color_scheme = UserProfile.COLOR_SCHEME_NIGHT
        user.save()

        payload = dict(command="/day")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('Changed to day', result.json()['msg'])

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('still in day mode', result.json()['msg'])

    def test_fluid_zcommand(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.fluid_layout_width = False
        user.save()

        payload = dict(command="/fluid-width")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response('Changed to fluid-width mode!', result)

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response('You are still in fluid width mode', result)

    def test_fixed_zcommand(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.fluid_layout_width = True
        user.save()

        payload = dict(command="/fixed-width")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response('Changed to fixed-width mode!', result)

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response('You are still in fixed width mode', result)

    def test_digress_zcommand(self) -> None:
        self.login('hamlet')
        hamlet = self.example_user('hamlet')
        hamlet.save()

        general = self.make_stream('general')
        self.subscribe(hamlet, 'general')
        test = self.make_stream('test')
        self.subscribe(hamlet, 'test')

        payload = dict(
            command="/digress",
            command_data=orjson.dumps(dict(
                old_stream="general",
            )).decode(),
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Invalid data.")

        payload = dict(
            command="/digress",
            command_data=orjson.dumps(dict(
                old_stream="general",
                old_topic="old topic name",
                new_stream="general",
                new_topic="old topic name",
            )).decode(),
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn("Cannot digress to the same thread.", result.json()['msg'])

        payload = dict(
            command="/digress",
            command_data= orjson.dumps(dict(
                old_stream="general",
                old_topic="old topic name",
                new_stream="test",
                new_topic="new topic name",
            )).decode(),
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn("Old topic #**general>old topic name** does not exist.", result.json()['msg'])

        self.client_post("/json/messages", {"type": "stream",
                                            "to": "general",
                                            "client": "test suite",
                                            "content": "Test message",
                                            "topic": "old topic name"})

        payload = dict(
            command="/digress",
            command_data=orjson.dumps(dict(
                old_stream="general",
                old_topic="old topic name",
                new_stream="test",
                new_topic="new topic name",
            )).decode(),
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertEqual('', result.json()['msg'])

        messages = get_topic_messages(hamlet, general, "old topic name")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[1].content, f"@_**King Hamlet|{hamlet.id}** will be talking on the new topic: #**test>new topic name**")

        messages = get_topic_messages(hamlet, test, "new topic name")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, f"@_**King Hamlet|{hamlet.id}** digressed this from old topic: #**general>old topic name**")

    @mock.patch('requests.get', return_value=MockResponse(orjson.dumps(dict(
        data = {'images': {'downsized_large': {'url': 'https://www.example.com'}}}
    )).decode(), 200))
    @mock.patch('zerver.lib.zcommand.get_giphy_api_key', return_value='abcd')
    def test_giphy_zcommand(self, mocked_request: Any, mocked_get_api_key: Any) -> None:
        self.login('hamlet')
        hamlet = self.example_user('hamlet')

        # Test sending giphy zcommand in a stream
        general = self.make_stream('general')
        self.subscribe(hamlet, 'general')

        payload = dict(
            command="/giphy",
            command_data=orjson.dumps(dict(
                text='random',
                stream='general',
                topic='foo',
            )).decode(),
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        messages = get_topic_messages(hamlet, general, "foo")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, '[random](https://www.example.com)')

        # Test sending giphy zcommand in a pm
        aaron = self.example_user('aaron')
        payload = dict(
            command="/giphy",
            command_data=orjson.dumps(dict(
                text='random',
                recipient=aaron.email,
            )).decode(),
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        msg = self.get_last_message()
        self.assertEqual(msg.recipient_id, aaron.id)
        self.assertEqual(msg.content, '[random](https://www.example.com)')

        # Test sending giphy zcommand in a huddle
        iago = self.example_user('iago')
        payload = dict(
            command="/giphy",
            command_data=orjson.dumps(dict(
                text='random',
                recipient=aaron.email + ',' + iago.email,
            )).decode(),
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        msg = self.get_last_message()
        self.assertEqual(msg.recipient_id, get_huddle_recipient({aaron.id, iago.id, hamlet.id}).id)
        self.assertEqual(msg.content, '[random](https://www.example.com)')

        # Test invalid data
        payload = dict(
            command="/giphy",
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Invalid data.")

        # Test invalid API Key
        with mock.patch('zerver.lib.zcommand.get_giphy_api_key', return_value=''):
            payload = dict(
                command="/giphy",
                command_data=orjson.dumps(dict(
                    text='random',
                    stream='general',
                    topic='foo',
                )).decode(),
            )
            result = self.client_post("/json/zcommand", payload)
            self.assert_json_error(result, "Please contact administrator to enable this feature.")

        # Test incomplete data
        payload = dict(
            command="/giphy",
            command_data=orjson.dumps(dict(
                text='random',
                topic='foo',
            )).decode(),
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Invalid data.")
