# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class AppveyorHookTests(WebhookTestCase):
    STREAM_NAME = 'appveyor'
    URL_TEMPLATE = "/api/v1/external/appveyor?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'appveyor'

    def test_appveyor_build_success_message(self) -> None:
        """
        Tests if appveyor build success notification is handled correctly
        """
        expected_topic = "Hubot-DSC-Resource"
        expected_message = ("[Build Hubot-DSC-Resource 2.0.59 completed](https://ci.appveyor.com/project"
                            "/joebloggs/hubot-dsc-resource/build/2.0.59)\n"
                            "Commit [c06e208b47](https://github.com/joebloggs/Hubot-DSC-Resource"
                            "/commit/c06e208b47) by Joe Bloggs on 6/12/2018"
                            " 6:22 PM: Increment version number.\n"
                            "Build Started: 9/9/2018 7:04 PM\n"
                            "Build Finished: 9/9/2018 7:06 PM")

        self.send_and_test_stream_message('appveyor_build_success', expected_topic, expected_message)

    def test_appveyor_build_failure_message(self) -> None:
        """
        Tests if appveyor build failure notification is handled correctly
        """
        expected_topic = "Hubot-DSC-Resource"
        expected_message = ("[Build Hubot-DSC-Resource 2.0.59 failed](https://ci.appveyor.com/project"
                            "/joebloggs/hubot-dsc-resource/build/2.0.59)\n"
                            "Commit [c06e208b47](https://github.com/joebloggs/Hubot-DSC-Resource"
                            "/commit/c06e208b47) by Joe Bloggs on 6/12/2018"
                            " 6:22 PM: Increment version number.\n"
                            "Build Started: 9/9/2018 7:04 PM\n"
                            "Build Finished: 9/9/2018 7:06 PM")

        self.send_and_test_stream_message('appveyor_build_failure', expected_topic, expected_message)

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("appveyor", fixture_name, file_type="json")
