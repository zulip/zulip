from zerver.lib.test_classes import WebhookTestCase


class AppveyorHookTests(WebhookTestCase):
    CHANNEL_NAME = "appveyor"
    URL_TEMPLATE = "/api/v1/external/appveyor?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "appveyor"

    def test_appveyor_build_success_message(self) -> None:
        """
        Tests if appveyor build success notification is handled correctly
        """
        expected_topic_name = "Hubot-DSC-Resource"
        expected_message = """
[Build Hubot-DSC-Resource 2.0.59 completed](https://ci.appveyor.com/project/joebloggs/hubot-dsc-resource/build/2.0.59):
* **Commit**: [c06e208b47: Increment version number.](https://github.com/joebloggs/Hubot-DSC-Resource/commit/c06e208b47) by Joe Bloggs
* **Started**: 9/9/2018 7:04 PM
* **Finished**: 9/9/2018 7:06 PM
""".strip()

        self.check_webhook("appveyor_build_success", expected_topic_name, expected_message)

    def test_appveyor_build_failure_message(self) -> None:
        """
        Tests if appveyor build failure notification is handled correctly
        """
        expected_topic_name = "Hubot-DSC-Resource"
        expected_message = """
[Build Hubot-DSC-Resource 2.0.59 failed](https://ci.appveyor.com/project/joebloggs/hubot-dsc-resource/build/2.0.59):
* **Commit**: [c06e208b47: Increment version number.](https://github.com/joebloggs/Hubot-DSC-Resource/commit/c06e208b47) by Joe Bloggs
* **Started**: 9/9/2018 7:04 PM
* **Finished**: 9/9/2018 7:06 PM
""".strip()

        self.check_webhook("appveyor_build_failure", expected_topic_name, expected_message)
