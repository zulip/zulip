from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase


class SlackIncomingHookTests(WebhookTestCase):
    CHANNEL_NAME = "slack_incoming"
    URL_TEMPLATE = "/api/v1/external/slack_incoming?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "slack_incoming"

    def test_message(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
Hello, world.
""".strip()

        self.check_webhook(
            "text",
            expected_topic_name,
            expected_message,
        )

    def test_message_formatting(self) -> None:
        tests = [
            ("some *foo* word", "some **foo** word"),
            ("*foo*", "**foo**"),
            ("*foo* *bar*", "**foo** **bar**"),
            ("*foo*a*bar*", "*foo*a*bar*"),
            ("some _foo_ word", "some *foo* word"),
        ]
        self.subscribe(self.test_user, self.CHANNEL_NAME)
        for input_value, output_value in tests:
            payload = {"text": input_value}
            msg = self.send_webhook_payload(
                self.test_user,
                self.url,
                payload,
                content_type="application/json",
            )
            self.assert_channel_message(
                message=msg,
                channel_name=self.CHANNEL_NAME,
                topic_name="(no topic)",
                content=output_value,
            )

    def test_null_message(self) -> None:
        self.check_webhook(
            "null_text",
            expect_noop=True,
        )

    def test_message_as_www_urlencoded(self) -> None:
        expected_topic_name = "devops"
        expected_message = """
:zap: chris has started deploying project tag v0.0.2rc10 to staging
""".strip()

        self.check_webhook(
            "urlencoded_text",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_message_without_payload(self) -> None:
        self.url = self.build_webhook_url()
        result = self.client_post(self.url)
        self.assert_json_error(result, "Missing 'payload' argument")

    def test_message_with_actions(self) -> None:
        expected_topic_name = "C1H9RESGL"
        expected_message = """
Danny Torrence left the following *review* for your property:

[Overlook Hotel](https://google.com) \n :star: \n Doors had too many axe holes, guest in room 237 was far too rowdy, whole place felt stuck in the 1920s.

[Haunted hotel image](https://is5-ssl.mzstatic.com/image/thumb/Purple3/v4/d3/72/5c/d3725c8f-c642-5d69-1904-aa36e4297885/source/256x256bb.jpg)

**Average Rating**
1.0
""".strip()

        self.check_webhook(
            "actions",
            expected_topic_name,
            expected_message,
        )

    def test_message_with_blocks(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
Danny Torrence left the following review for your property:

[Overlook Hotel](https://example.com) \n :star: \n Doors had too many axe holes, guest in room 237 was far too rowdy, whole place felt stuck in the 1920s.

[Haunted hotel image](https://is5-ssl.mzstatic.com/image/thumb/Purple3/v4/d3/72/5c/d3725c8f-c642-5d69-1904-aa36e4297885/source/256x256bb.jpg)

**Average Rating**
1.0
""".strip()

        self.check_webhook(
            "blocks",
            expected_topic_name,
            expected_message,
        )

    def test_message_with_attachment(self) -> None:
        expected_topic_name = "prometheus-alerts"
        expected_message = """
## [[FIRING:2] InstanceDown for api-server (env="prod", severity="critical")](https://alertmanager.local//#/alerts?receiver=default)

:chart_with_upwards_trend: **[Graph](http://generator.local/1)**   :notebook: **[Runbook](https://runbook.local/1)**

**Alert details**:
**Alert:** api-server down - `critical`
**Description:** api-server at 1.2.3.4:8080 couldn't be scraped **Details:**
   • **alertname:** `InstanceDown`
   • **env:** `prod`
   • **instance:** `1.2.3.4:8080`
   • **job:** `api-server`
   • **severity:** `critical`

**Alert:** api-server down - `critical`
**Description:** api-server at 1.2.3.4:8081 couldn't be scraped **Details:**
   • **alertname:** `InstanceDown`
   • **env:** `prod`
   • **instance:** `1.2.3.4:8081`
   • **job:** `api-server`
   • **severity:** `critical`
""".strip()

        self.check_webhook(
            "attachment",
            expected_topic_name,
            expected_message,
        )

    def test_complicated(self) -> None:
        # Paste the JSON into
        # https://api.slack.com/tools/block-kit-builder to see how it
        # is rendered in Slack
        expected_topic_name = "(no topic)"
        expected_message = """
## Hello from TaskBot

Hey there 👋 I'm TaskBot. I'm here to help you create and manage tasks in Slack.
There are two ways to quickly create tasks:

**1️⃣ Use the `/task` command**. Type `/task` followed by a short description of your tasks and I'll ask for a due date (if applicable). Try it out by using the `/task` command in this channel.

**2️⃣ Use the *Create a Task* action.** If you want to create a task from a message, select `Create a Task` in a message's context menu. Try it out by selecting the *Create a Task* action for this message (shown below).

[image1](https://api.slack.com/img/blocks/bkb_template_images/onboardingComplex.jpg)

➕ To start tracking your team's tasks, **add me to a channel** and I'll introduce myself. I'm usually added to a team or project channel. Type `/invite @TaskBot` from the channel or pick a channel on the right.

----

[cute cat](https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg)

👀 View all tasks with `/task list`

❓Get help at any time with:
- `/task help`, or
- type **help** in a DM with me
        """.strip()

        self.check_webhook(
            "complicated",
            expected_topic_name,
            expected_message,
        )

    def test_attachment_blocks(self) -> None:
        # On https://api.slack.com/tools/block-kit-builder choose
        # "Attachment preview" and paste the JSON in.
        expected_topic_name = "(no topic)"
        expected_message = """
This is a section block with an accessory image.

[cute cat](https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg)

This is a section block with a button.

| | |
|-|-|
| one | two |
| three | four |
| five |  |
        """.strip()

        self.check_webhook(
            "attachment_blocks",
            expected_topic_name,
            expected_message,
        )

    def test_attachment_fields(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
Build bla bla succeeded

**Requested by**: Some user
**Duration**: 00:02:03
**Build pipeline**: ConsumerAddressModule
**Title with null value**
**Title without value**
Value with null title
Value without title
        """.strip()

        self.check_webhook(
            "attachment_fields",
            expected_topic_name,
            expected_message,
        )

    def test_attachment_pieces(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
## Test

[](https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg)

<time:1655945306>
        """.strip()

        self.check_webhook(
            "attachment_pieces",
            expected_topic_name,
            expected_message,
        )

    @override
    def get_body(self, fixture_name: str) -> str:
        if "urlencoded" in fixture_name:
            file_type = "txt"
        else:
            file_type = "json"
        return self.webhook_fixture_data("slack_incoming", fixture_name, file_type=file_type)

    def test_attachment_pieces_title_null(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
Sample pretext.

Sample text.

[](https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg)

Sample footer.

<time:1655945306>
        """.strip()

        self.check_webhook(
            "attachment_pieces_title_null",
            expected_topic_name,
            expected_message,
        )

    def test_attachment_pieces_image_url_null(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
## [Sample title.](https://www.google.com)

Sample pretext.

Sample text.

Sample footer.

<time:1655945306>
        """.strip()

        self.check_webhook(
            "attachment_pieces_image_url_null",
            expected_topic_name,
            expected_message,
        )

    def test_attachment_pieces_ts_null(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
## [Sample title.](https://www.google.com)

Sample pretext.

Sample text.

[](https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg)

Sample footer.
        """.strip()

        self.check_webhook(
            "attachment_pieces_ts_null",
            expected_topic_name,
            expected_message,
        )

    def test_attachment_pieces_text_null(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
## [Sample title.](https://www.google.com)

Sample pretext.

[](https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg)

Sample footer.

<time:1655945306>
        """.strip()

        self.check_webhook(
            "attachment_pieces_text_null",
            expected_topic_name,
            expected_message,
        )

    def test_attachment_pieces_pretext_null(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
## [Sample title.](https://www.google.com)

Sample text.

[](https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg)

Sample footer.

<time:1655945306>
        """.strip()

        self.check_webhook(
            "attachment_pieces_pretext_null",
            expected_topic_name,
            expected_message,
        )

    def test_attachment_pieces_footer_null(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
## [Sample title.](https://www.google.com)

Sample pretext.

Sample text.

[](https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg)

<time:1655945306>
        """.strip()

        self.check_webhook(
            "attachment_pieces_footer_null",
            expected_topic_name,
            expected_message,
        )

    def test_attachment_pieces_title_link_null(self) -> None:
        expected_topic_name = "(no topic)"
        expected_message = """
## Sample title.

Sample pretext.

Sample text.

[](https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg)

Sample footer.

<time:1655945306>
        """.strip()

        self.check_webhook(
            "attachment_pieces_title_link_null",
            expected_topic_name,
            expected_message,
        )

    def test_attachment_pieces_all_null(self) -> None:
        self.check_webhook("attachment_pieces_all_null", expect_noop=True)
