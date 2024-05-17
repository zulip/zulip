from zerver.lib.test_classes import WebhookTestCase


class NetlifyHookTests(WebhookTestCase):
    CHANNEL_NAME = "netlify"
    URL_TEMPLATE = "/api/v1/external/netlify?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "netlify"

    def test_building_message(self) -> None:
        expected_topic_name = "master"
        expected_message = "The build [objective-jepsen-35fbb2](http://objective-jepsen-35fbb2.netlify.com) on branch master is now building."

        self.check_webhook(
            "deploy_building",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_created_message(self) -> None:
        expected_topic_name = "master"
        expected_message = "The build [objective-jepsen-35fbb2](http://objective-jepsen-35fbb2.netlify.com) on branch master is now ready."

        self.check_webhook(
            "deploy_created", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_failed_message(self) -> None:
        expected_topic_name = "master"
        expected_message = (
            "The build [objective-jepsen-35fbb2](http://objective-jepsen-35fbb2.netlify.com) "
            "on branch master failed during stage 'building site': Build script returned non-zero exit code: 127"
        )

        self.check_webhook(
            "deploy_failed", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_locked_message(self) -> None:
        expected_topic_name = "master"
        expected_message = (
            "The build [objective-jepsen-35fbb2](http://objective-jepsen-35fbb2.netlify.com) "
            "on branch master is now locked."
        )

        self.check_webhook(
            "deploy_locked", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_unlocked_message(self) -> None:
        expected_topic_name = "master"
        expected_message = (
            "The build [objective-jepsen-35fbb2](http://objective-jepsen-35fbb2.netlify.com) "
            "on branch master is now unlocked."
        )

        self.check_webhook(
            "deploy_unlocked",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )
