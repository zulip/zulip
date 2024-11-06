import os
from typing import Any

import orjson
from typing_extensions import override

from zerver.data_import.slack_message_conversion import (
    convert_to_zulip_markdown,
    get_user_full_name,
)
from zerver.lib import mdiff
from zerver.lib.test_classes import ZulipTestCase


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
        text, mentioned_users, has_link = convert_to_zulip_markdown(
            message, users, channel_map, slack_user_map
        )
        full_name = get_user_full_name(users[1])
        self.assertEqual(full_name, "John Doe")
        self.assertEqual(get_user_full_name(users[2]), "Jane")

        self.assertEqual(text, f"Hi @**{full_name}**: How are you? #**general**")
        self.assertEqual(mentioned_users, [540])

        # multiple mentioning
        message = "Hi <@U08RGD1RD|john>: How are you?<@U0CBK5KAT> asked."
        text, mentioned_users, has_link = convert_to_zulip_markdown(
            message, users, channel_map, slack_user_map
        )
        self.assertEqual(text, "Hi @**John Doe**: How are you?@**aaron.anzalone** asked.")
        self.assertEqual(mentioned_users, [540, 554])

        # Check wrong mentioning
        message = "Hi <@U08RGD1RD|jon>: How are you?"
        text, mentioned_users, has_link = convert_to_zulip_markdown(
            message, users, channel_map, slack_user_map
        )
        self.assertEqual(text, message)
        self.assertEqual(mentioned_users, [])

    def test_has_link(self) -> None:
        slack_user_map: dict[str, int] = {}

        message = "<http://journals.plos.org/plosone/article>"
        text, mentioned_users, has_link = convert_to_zulip_markdown(message, [], {}, slack_user_map)
        self.assertEqual(text, "http://journals.plos.org/plosone/article")
        self.assertEqual(has_link, True)

        message = "<http://chat.zulip.org/help/logging-in|Help logging in to CZO>"
        text, mentioned_users, has_link = convert_to_zulip_markdown(message, [], {}, slack_user_map)
        self.assertEqual(text, "[Help logging in to CZO](http://chat.zulip.org/help/logging-in)")
        self.assertEqual(has_link, True)

        message = "<mailto:foo@foo.com>"
        text, mentioned_users, has_link = convert_to_zulip_markdown(message, [], {}, slack_user_map)
        self.assertEqual(text, "mailto:foo@foo.com")
        self.assertEqual(has_link, True)

        message = "random message"
        text, mentioned_users, has_link = convert_to_zulip_markdown(message, [], {}, slack_user_map)
        self.assertEqual(has_link, False)
