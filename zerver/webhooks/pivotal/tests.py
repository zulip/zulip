from unittest import mock

import orjson
from typing_extensions import override

from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.pivotal.view import api_pivotal_webhook_v5


class PivotalV3HookTests(WebhookTestCase):
    CHANNEL_NAME = "pivotal"
    URL_TEMPLATE = "/api/v1/external/pivotal?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "pivotal"

    def test_accepted(self) -> None:
        expected_topic_name = "My new Feature story"
        expected_message = 'Leo Franchi accepted "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573).'
        self.check_webhook(
            "accepted", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_bad_subject(self) -> None:
        expected_topic_name = "Story changed"
        expected_message = "Leo Franchi accepted My new Feature story \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)."
        self.check_webhook(
            "bad_accepted", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_commented(self) -> None:
        expected_topic_name = "Comment added"
        expected_message = 'Leo Franchi added comment: "FIX THIS NOW" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573).'
        self.check_webhook(
            "commented", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_created(self) -> None:
        expected_topic_name = "My new Feature story"
        expected_message = 'Leo Franchi added "My new Feature story" \
(unscheduled feature):\n\n~~~ quote\nThis is my long description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573).'
        self.check_webhook(
            "created", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_delivered(self) -> None:
        expected_topic_name = "Another new story"
        expected_message = 'Leo Franchi delivered "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289).'
        self.check_webhook(
            "delivered", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_finished(self) -> None:
        expected_topic_name = "Another new story"
        expected_message = 'Leo Franchi finished "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289).'
        self.check_webhook(
            "finished", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_moved(self) -> None:
        expected_topic_name = "My new Feature story"
        expected_message = 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573).'
        self.check_webhook(
            "moved", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_rejected(self) -> None:
        expected_topic_name = "Another new story"
        expected_message = 'Leo Franchi rejected "Another new story" with comments: \
"Not good enough, sorry" [(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289).'
        self.check_webhook(
            "rejected", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_started(self) -> None:
        expected_topic_name = "Another new story"
        expected_message = 'Leo Franchi started "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289).'
        self.check_webhook(
            "started", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_created_estimate(self) -> None:
        expected_topic_name = "Another new story"
        expected_message = 'Leo Franchi added "Another new story" \
(unscheduled feature worth 2 story points):\n\n~~~ quote\nSome loong description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289).'
        self.check_webhook(
            "created_estimate",
            expected_topic_name,
            expected_message,
            content_type="application/xml",
        )

    def test_type_changed(self) -> None:
        expected_topic_name = "My new Feature story"
        expected_message = 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573).'
        self.check_webhook(
            "type_changed", expected_topic_name, expected_message, content_type="application/xml"
        )

    @override
    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("pivotal", fixture_name, file_type="xml")


class PivotalV5HookTests(WebhookTestCase):
    CHANNEL_NAME = "pivotal"
    URL_TEMPLATE = "/api/v1/external/pivotal?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "pivotal"

    def test_accepted(self) -> None:
        expected_topic_name = "#63486316: Story of the Year"
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **unstarted** to **accepted**"""
        self.check_webhook(
            "accepted", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_commented(self) -> None:
        expected_topic_name = "#63486316: Story of the Year"
        expected_message = """Leo Franchi added a comment to [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
~~~quote
A comment on the story
~~~"""
        self.check_webhook(
            "commented", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_created(self) -> None:
        expected_topic_name = "#63495662: Story that I created"
        expected_message = """Leo Franchi created bug: [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story that I created](http://www.pivotaltracker.com/story/show/63495662)
* State is **unscheduled**
* Description is

> What a description"""
        self.check_webhook(
            "created", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_delivered(self) -> None:
        expected_topic_name = "#63486316: Story of the Year"
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **accepted** to **delivered**"""
        self.check_webhook(
            "delivered", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_finished(self) -> None:
        expected_topic_name = "#63486316: Story of the Year"
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **delivered** to **accepted**"""
        self.check_webhook(
            "finished", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_moved(self) -> None:
        expected_topic_name = "#63496066: Pivotal Test"
        expected_message = """Leo Franchi moved [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066) from **unstarted** to **unscheduled**."""
        self.check_webhook(
            "moved", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_rejected(self) -> None:
        expected_topic_name = "#63486316: Story of the Year"
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* Comment added:
~~~quote
Try again next time
~~~
* state changed from **delivered** to **rejected**"""
        self.check_webhook(
            "rejected", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_started(self) -> None:
        expected_topic_name = "#63495972: Fresh Story"
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Fresh Story](http://www.pivotaltracker.com/story/show/63495972):
* state changed from **unstarted** to **started**"""
        self.check_webhook(
            "started", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_created_estimate(self) -> None:
        expected_topic_name = "#63496066: Pivotal Test"
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066):
* estimate is now **3 points**"""
        self.check_webhook(
            "created_estimate",
            expected_topic_name,
            expected_message,
            content_type="application/xml",
        )

    def test_type_changed(self) -> None:
        expected_topic_name = "#63496066: Pivotal Test"
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066):
* estimate changed from 3 to **0 points**
* type changed from **feature** to **bug**"""
        self.check_webhook(
            "type_changed", expected_topic_name, expected_message, content_type="application/xml"
        )

    def test_bad_payload(self) -> None:
        bad = ("foo", None, "bar")
        with self.assertRaisesRegex(AssertionError, "Unable to handle Pivotal payload"):
            with mock.patch(
                "zerver.webhooks.pivotal.view.api_pivotal_webhook_v3", return_value=bad
            ):
                self.check_webhook("accepted", expect_topic="foo")

    def test_bad_request(self) -> None:
        request = mock.MagicMock()
        hamlet = self.example_user("hamlet")
        bad = orjson.loads(self.get_body("bad_request"))

        with mock.patch("zerver.webhooks.pivotal.view.orjson.loads", return_value=bad):
            result = api_pivotal_webhook_v5(request, hamlet)
            self.assertEqual(result[0], "#0: ")

        bad = orjson.loads(self.get_body("bad_kind"))
        with self.assertRaisesRegex(UnsupportedWebhookEventTypeError, "'unknown_kind'.* supported"):
            with mock.patch("zerver.webhooks.pivotal.view.orjson.loads", return_value=bad):
                api_pivotal_webhook_v5(request, hamlet)

    @override
    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("pivotal", f"v5_{fixture_name}", file_type="json")
