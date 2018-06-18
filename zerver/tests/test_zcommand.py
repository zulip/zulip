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

    def test_subscribe_zcommand(self) -> None:
        self.login(self.example_email("hamlet"))
        realm = get_realm('zulip')

        payload = dict(command="/subscribe invalide")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('Usage: /subscribe #<stream_name> @<user>', result.json()['msg'])

        payload = dict(command="/subscribe #**test stream** @**invalid user**")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('Usage: /subscribe #<stream_name> @<user>', result.json()['msg'])

        payload = dict(command="/subscribe #**test stream** @**Cordelia Lear**")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('A valid stream name is required.', result.json()['msg'])

        create_stream_if_needed(realm, "test stream")
        user = self.example_user('cordelia')

        payload = dict(command="/subscribe #**test stream** @**invalid user**")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn('A valid user is required.', result.json()['msg'])

        payload = dict(command="/subscribe #**test stream** @**Cordelia Lear**")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn("test stream", result.json()['stream'])
        self.assertEqual(user.id, result.json()['user_id'])
