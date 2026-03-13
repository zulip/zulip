import json
import os
from typing import Any

import orjson
from typing_extensions import override

from zerver.data_import.slack_message_conversion import (
    ChannelMentionProcessorT,
    LossyConversionError,
    RenderResult,
    UserMentionProcessorT,
    convert_to_zulip_markdown,
    get_user_full_name,
    get_zulip_mention_for_slack_user,
    process_slack_block_and_attachment,
)
from zerver.lib import mdiff
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.validator import to_wild_value


class SlackMessageConversion(ZulipTestCase):
    @override
    def assertEqual(self, first: Any, second: Any, msg: str = "") -> None:
        if isinstance(first, str) and isinstance(second, str):
            if first != second:
                raise AssertionError(
                    "Actual and expected outputs do not match; showing diff.\n"
                    + mdiff.diff_strings(first, second)
                    + msg
                )
        else:
            super().assertEqual(first, second)

    def load_slack_message_conversion_tests(self) -> dict[Any, Any]:
        test_fixtures = {}
        with open(
            os.path.join(os.path.dirname(__file__), "fixtures/slack_message_conversion.json"), "rb"
        ) as f:
            data = orjson.loads(f.read())
        for test in data["regular_tests"]:
            test_fixtures[test["name"]] = test

        return test_fixtures

    def test_message_conversion_fixtures(self) -> None:
        format_tests = self.load_slack_message_conversion_tests()
        valid_keys = {"name", "input", "conversion_output"}

        for name, test in format_tests.items():
            # Check that there aren't any unexpected keys as those are often typos
            self.assert_length(set(test.keys()) - valid_keys, 0)
            slack_user_map: dict[str, int] = {}
            users: list[dict[str, Any]] = [{}]
            channel_map: dict[str, tuple[str, int]] = {}
            converted = convert_to_zulip_markdown(test["input"], users, channel_map, slack_user_map)
            converted_text = converted[0]
            with self.subTest(slack_message_conversion=name):
                self.assertEqual(converted_text, test["conversion_output"])

    def test_mentioned_data(self) -> None:
        slack_user_map = {"U08RGD1RD": 540, "U0CBK5KAT": 554, "U09TYF5SK": 571}
        # For this test, only relevant keys are 'id', 'name', 'deleted'
        # and 'real_name'
        users = [
            {
                "id": "U0CBK5KAT",
                "name": "aaron.anzalone",
                "deleted": False,
                "is_mirror_dummy": False,
                "real_name": "",
            },
            {
                "id": "U08RGD1RD",
                "name": "john",
                "deleted": False,
                "is_mirror_dummy": False,
                "real_name": "John Doe",
            },
            {
                "id": "U09TYF5Sk",
                "name": "Jane",
                "is_mirror_dummy": False,
                "deleted": True,  # Deleted users don't have 'real_name' key in Slack
            },
        ]
        channel_map = {"general": ("C5Z73A7RA", 137)}
        message = "Hi <@U08RGD1RD|john>: How are you? <#C5Z73A7RA|general>"
        text, mentioned_users, _has_link = convert_to_zulip_markdown(
            message, users, channel_map, slack_user_map
        )
        full_name = get_user_full_name(users[1])
        self.assertEqual(full_name, "John Doe")
        self.assertEqual(get_user_full_name(users[2]), "Jane")

        self.assertEqual(text, f"Hi @**{full_name}**: How are you? #**general**")
        self.assertEqual(mentioned_users, [540])

        # multiple mentioning
        message = "Hi <@U08RGD1RD|john>: How are you?<@U0CBK5KAT> asked."
        text, mentioned_users, _has_link = convert_to_zulip_markdown(
            message, users, channel_map, slack_user_map
        )
        self.assertEqual(text, "Hi @**John Doe**: How are you?@**aaron.anzalone** asked.")
        self.assertEqual(mentioned_users, [540, 554])

        # Check wrong mentioning
        message = "Hi <@U08RGD1RD|jon>: How are you?"
        text, mentioned_users, _has_link = convert_to_zulip_markdown(
            message, users, channel_map, slack_user_map
        )
        self.assertEqual(text, message)
        self.assertEqual(mentioned_users, [])

    def test_has_link(self) -> None:
        slack_user_map: dict[str, int] = {}

        message = "<http://journals.plos.org/plosone/article>"
        text, _mentioned_users, has_link = convert_to_zulip_markdown(
            message, [], {}, slack_user_map
        )
        self.assertEqual(text, "http://journals.plos.org/plosone/article")
        self.assertEqual(has_link, True)

        message = "<http://chat.zulip.org/help/logging-in|Help logging in to CZO>"
        text, _mentioned_users, has_link = convert_to_zulip_markdown(
            message, [], {}, slack_user_map
        )
        self.assertEqual(text, "[Help logging in to CZO](http://chat.zulip.org/help/logging-in)")
        self.assertEqual(has_link, True)

        message = "<mailto:foo@foo.com>"
        text, _mentioned_users, has_link = convert_to_zulip_markdown(
            message, [], {}, slack_user_map
        )
        self.assertEqual(text, "mailto:foo@foo.com")
        self.assertEqual(has_link, True)

        message = "random message"
        text, _mentioned_users, has_link = convert_to_zulip_markdown(
            message, [], {}, slack_user_map
        )
        self.assertEqual(has_link, False)


class SlackBlockAndAttachmentConversionTest(ZulipTestCase):
    def check_converted_content(
        self,
        fixture_name: str,
        channel_mention_processor: ChannelMentionProcessorT,
        user_mention_processor: UserMentionProcessorT,
        expected_result: RenderResult,
    ) -> None:
        raw_message = orjson.loads(
            self.fixture_data(fixture_name, "slack_fixtures/exported_messages_fixtures")
        )
        result = process_slack_block_and_attachment(
            (to_wild_value("message", json.dumps(raw_message))),
            channel_mention_processor,
            user_mention_processor,
        )
        self.assertEqual(expected_result.content, result.content)
        self.assertEqual(expected_result.has_link, result.has_link)
        self.assertEqual(expected_result.mentioned_user_ids, result.mentioned_user_ids)

    def test_bold_italic_strike(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_basic_formatting.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content=(
                    "Hello there, I am a basic rich text block!\n"
                    "Hello there, **I am a bold rich text block!**\n"
                    "Hello there, *I am an italic rich text block!*\n"
                    "Hello there, ~~I am a strikethrough rich text block!~~"
                ),
                has_link=False,
                mentioned_user_ids=[],
            ),
        )

    def test_emojis(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_emojis.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content="Hello there! Here are some emojis :basketball: :snowboarder: :checkered_flag:",
                has_link=False,
                mentioned_user_ids=[],
            ),
        )

    def test_links(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_links.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content="""
[Text with a link](https://chat.zulip.org/)
**[Text with a link](https://chat.zulip.org/)**
*[Text with a link](https://chat.zulip.org/)*
[Text with a link](https://chat.zulip.org/)
~~[Text with a link](https://chat.zulip.org/)~~
## [Public view of Zulip Community | Zulip team chat](https://chat.zulip.org/)

Browse the publicly accessible channels in Zulip Community without logging in.
""".strip(),
                has_link=True,
                mentioned_user_ids=[],
            ),
        )

    def test_bullet_list(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_bullet_list.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content=(
                    "Basic bullet list with rich elements\n\n"
                    "- item 1: :basketball:\n"
                    "- item 2: **this** is *a list* item\n"
                    "- item 3: **[with a link](https://example.com/)**\n"
                    "- item 4: we are near ~~the end~~\n"
                    "- item 5: ~~***[this is the end](https://chat.zulip.org/)***~~"
                ),
                has_link=True,
                mentioned_user_ids=[],
            ),
        )

    def test_nested_unordered_list(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_nested_unordered_list.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content=(
                    "unordered list with subitems:\n\n"
                    "- main item 1\n"
                    "   1. nested item 1\n"
                    "   1. nested item 2\n"
                    "   1. nested item 3\n"
                    "- main item 2\n"
                    "   1. nested item 1"
                ),
                has_link=False,
                mentioned_user_ids=[],
            ),
        )

    def test_nested_ordered_list(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_nested_ordered_list.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content=(
                    "ordered list with subitems:\n\n"
                    "1. main item 1\n"
                    "   - nested item 1\n"
                    "   - nested item 2\n"
                    "   - nested item 3\n"
                    "1. main item 2\n"
                    "   1. nested item 1"
                ),
                has_link=False,
                mentioned_user_ids=[],
            ),
        )

    def test_inline_code(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_inline_code.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content="""
Hello there, I am an `inline code`
**Hello there, I am an** **`inline code`**
 ~~***[Hello there, I am an ](https://chat.zulip.org)***~~~~***`inline code`***~~
## [Public view of Zulip Community | Zulip team chat](https://chat.zulip.org/)

Browse the publicly accessible channels in Zulip Community without logging in.
""".strip(),
                has_link=True,
                mentioned_user_ids=[],
            ),
        )

    def test_code_block(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_code_block.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content="""
```text
# I'm a code block!

def convert_slack_formatting(text: str) -> str:
    return text
```
""".strip(),
                has_link=False,
                mentioned_user_ids=[],
            ),
        )

    def test_quote_block(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_quote_block.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content="""
```quote
Hello there, I am a rich text section block!
**Hello there, I am a rich text section block!**
~~***`Hello there, I am a rich text section block!`***~~
```
""".strip(),
                has_link=False,
                mentioned_user_ids=[],
            ),
        )

    def test_user_mentions(self) -> None:

        slack_user_id_to_zulip_user_id = {"U06NU4E26M9": 1}
        users = [
            {
                "id": "U06NU4E26M9",
                "name": "john",
                "is_mirror_dummy": False,
                "real_name": "John Doe",
                "profile": {
                    "image_32": "",
                    "email": "jon@gmail.com",
                    "avatar_hash": "hash",
                    "phone": "+1-123-456-77-868",
                    "fields": {},
                },
            }
        ]

        def user_mention_processor(slack_user_id: str) -> tuple[str, int] | None:
            if mention := get_zulip_mention_for_slack_user(slack_user_id, None, users):
                return (mention, slack_user_id_to_zulip_user_id[slack_user_id])
            else:
                return None

        self.check_converted_content(
            fixture_name="message_with_user_mentions.json",
            user_mention_processor=user_mention_processor,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content="@**john** test user mention **#Unknown Slack user U074VRHQ11T**",
                has_link=False,
                mentioned_user_ids=[1],
            ),
        )

    def test_channel_mentions(self) -> None:
        slack_channel_id_to_name = {"C079A3FA12P": "general", "C0AHX20ADQQ": "issues"}

        def channel_mention_processor(slack_channel_id: str) -> str | None:
            if slack_channel_id in slack_channel_id_to_name:
                return f"#**{slack_channel_id_to_name[slack_channel_id]}**"
            else:
                return None

        self.check_converted_content(
            fixture_name="message_with_channel_mentions.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=channel_mention_processor,
            expected_result=RenderResult(
                content="#**general** #**issues** **#Unknown Slack channel C06P6T3QGD7**",
                has_link=False,
                mentioned_user_ids=[],
            ),
        )

    def test_workspace_mentions(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_workspace_mentions.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content="@**all** @**all** test mention",
                has_link=False,
                mentioned_user_ids=[],
            ),
        )

    def test_variety_files_and_rich_text(self) -> None:
        self.check_converted_content(
            fixture_name="message_with_variety_files_and_rich_text.json",
            user_mention_processor=lambda id: None,
            channel_mention_processor=lambda id: None,
            expected_result=RenderResult(
                content="message with **files**  **#Unknown Slack user U074VRHQ11T**",
                has_link=False,
                mentioned_user_ids=[],
            ),
        )

    def test_unknown_rich_text_block(self) -> None:
        with self.assertRaises(LossyConversionError) as e:
            self.check_converted_content(
                fixture_name="message_with_unknown_rich_text_block.json",
                user_mention_processor=lambda id: None,
                channel_mention_processor=lambda id: None,
                expected_result=RenderResult(
                    content="",
                    has_link=False,
                    mentioned_user_ids=[],
                ),
            )
        self.assertEqual(
            str(e.exception),
            "Unknown rich_text block: unknown_block.\n{'type': 'unknown_block'}",
        )
