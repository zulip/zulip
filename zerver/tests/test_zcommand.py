# -*- coding: utf-8 -*-

from zerver.lib.test_classes import (
    ZulipTestCase,
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
