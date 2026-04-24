from zerver.lib.test_classes import WebhookTestCase


class AppveyorHookTests(WebhookTestCase):
    def test_appveyor_build_success_message(self) -> None:
        """
        Tests if appveyor build success notification is handled correctly
        """
        expected_topic_name = "Hubot-DSC-Resource"
        expected_message = """
[Build Hubot-DSC-Resource 2.0.59 completed](https://ci.appveyor.com/project/joebloggs/hubot-dsc-resource/build/2.0.59):
* **Commit**: [c06e208b47: Increment version number.](https://github.com/joebloggs/Hubot-DSC-Resource/commit/c06e208b47) by Joe Bloggs
* **Started**: <time:2018-09-09T19:04:00+00:00>
* **Finished**: <time:2018-09-09T19:06:00+00:00>
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
* **Started**: <time:2018-09-09T19:04:00+00:00>
* **Finished**: <time:2018-09-09T19:06:00+00:00>
""".strip()

        self.check_webhook("appveyor_build_failure", expected_topic_name, expected_message)
