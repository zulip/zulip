# -*- coding: utf-8 -*-

from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.actions import (
    create_stream_if_needed, get_realm,
)

class ZcommandTest(ZulipTestCase):

    def test_invalid_zcommand(self) -> None:
        self.login(self.example_email("hamlet"))

        payload = dict(command="/boil-ocean")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "No such command: boil-ocean")

        payload = dict(command="boil-ocean")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "There should be a leading slash in the zcommand.")

    def test_ping_zcommand(self) -> None:
        self.login(self.example_email("hamlet"))

        payload = dict(command="/ping")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)

    def test_night_zcommand(self) -> None:
        self.login(self.example_email("hamlet"))
        user = self.example_user('hamlet')
        user.night_mode = False
        user.save()

        payload = dict(command="/night")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('Changed to night', result.json()['msg'])

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('still in night mode', result.json()['msg'])

    def test_day_zcommand(self) -> None:
        self.login(self.example_email("hamlet"))
        user = self.example_user('hamlet')
        user.night_mode = True
        user.save()

        payload = dict(command="/day")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('Changed to day', result.json()['msg'])

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('still in day mode', result.json()['msg'])

    def test_mute_topic_zcommand(self) -> None:
        self.login(self.example_email("hamlet"))
        realm = get_realm("zulip")

        # Test invalid usage of mute_topic command
        payload = dict(command="/mute_topic invalid")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('Usage: /mute_topic #<stream_name> <topic_name>', result.json()['msg'])

        # Test invalid stream and topic
        payload = dict(command="/mute_topic #**test stream with spaces** topic")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('A valid stream name is required.', result.json()['msg'])

        # Test invalid topic
        payload = dict(command="/mute_topic #**Denmark** invalid_topic")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('A valid topic is required.', result.json()['msg'])

        create_stream_if_needed(realm, "test stream with spaces")

        # Test stream with spaces in the name
        payload = dict(command="/mute_topic #**test stream with spaces** invalid_topic")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('A valid topic is required.', result.json()['msg'])

        self.send_stream_message(self.example_email('hamlet'), "test stream with spaces",
                                 content="test", topic_name="my topic")

        # Test muting of a topic
        payload = dict(command="/mute_topic  #**Verona** Verona1")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn("Verona1", result.json()['subject'])
        self.assertIn("Verona", result.json()['stream'])
        self.assertIn("stream", result.json()['type'])

        payload = dict(command="/mute_topic #**test stream with spaces** My topic")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn("My topic", result.json()['subject'])
        self.assertIn("test stream with spaces", result.json()['stream'])
        self.assertIn("stream", result.json()['type'])

        # Test muting an already muted topic
        payload = dict(command="/mute_topic #**Verona**  Verona1")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn("Verona1", result.json()['subject'])
        self.assertIn("Verona", result.json()['stream'])
        self.assertIn("stream", result.json()['type'])
