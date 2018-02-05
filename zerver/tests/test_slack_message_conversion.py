# -*- coding: utf-8 -*-
from django.conf import settings

from zerver.lib.slack_message_conversion import (
    convert_to_zulip_markdown,
    get_user_full_name
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_runner import slow
from zerver.lib import mdiff
import ujson

import os
from typing import Any, AnyStr, Dict, List, Optional, Set, Tuple, Text

class SlackMessageConversion(ZulipTestCase):
    def assertEqual(self, first: Any, second: Any, msg: Text = "") -> None:
        if isinstance(first, Text) and isinstance(second, Text):
            if first != second:
                raise AssertionError("Actual and expected outputs do not match; showing diff.\n" +
                                     mdiff.diff_strings(first, second) + msg)
        else:
            super().assertEqual(first, second)

    def load_slack_message_conversion_tests(self) -> Dict[Any, Any]:
        test_fixtures = {}
        data_file = open(os.path.join(os.path.dirname(__file__), '../fixtures/slack_message_conversion.json'), 'r')
        data = ujson.loads('\n'.join(data_file.readlines()))
        for test in data['regular_tests']:
            test_fixtures[test['name']] = test

        return test_fixtures

    @slow("Aggregate of runs of individual slack message conversion tests")
    def test_message_conversion_fixtures(self) -> None:
        format_tests = self.load_slack_message_conversion_tests()
        valid_keys = set(['name', "input", "conversion_output"])

        for name, test in format_tests.items():
            # Check that there aren't any unexpected keys as those are often typos
            self.assertEqual(len(set(test.keys()) - valid_keys), 0)
            slack_user_map = {}  # type: Dict[str, int]
            users = [{}]         # type: List[Dict[str, Any]]
            converted = convert_to_zulip_markdown(test['input'], users, slack_user_map)
            converted_text = converted[0]
            print("Running Slack Message Conversion test: %s" % (name,))
            self.assertEqual(converted_text, test['conversion_output'])

    def test_mentioned_data(self) -> None:
        slack_user_map = {'U08RGD1RD': 540,
                          'U0CBK5KAT': 554,
                          'U09TYF5SK': 571}
        # For this test, only relevant keys are 'id', 'name', 'deleted'
        # and 'real_name'
        users = [{"id": "U0CBK5KAT",
                  "name": "aaron.anzalone",
                  "deleted": False,
                  "real_name": ""},
                 {"id": "U08RGD1RD",
                  "name": "john",
                  "deleted": False,
                  "real_name": "John Doe"},
                 {"id": "U09TYF5Sk",
                  "name": "Jane",
                  "deleted": True}]              # Deleted users don't have 'real_name' key in Slack
        message = 'Hi <@U08RGD1RD|john>: How are you?'
        text, mentioned_users, has_link = convert_to_zulip_markdown(message, users, slack_user_map)
        full_name = get_user_full_name(users[1])
        self.assertEqual(full_name, 'John Doe')
        self.assertEqual(get_user_full_name(users[2]), 'Jane')

        self.assertEqual(text, 'Hi @**%s**: How are you?' % (full_name))
        self.assertEqual(mentioned_users, [540])

        # multiple mentioning
        message = 'Hi <@U08RGD1RD|john>: How are you?<@U0CBK5KAT> asked.'
        text, mentioned_users, has_link = convert_to_zulip_markdown(message, users, slack_user_map)
        self.assertEqual(text, 'Hi @**%s**: How are you?@**%s** asked.' %
                         ('John Doe', 'aaron.anzalone'))
        self.assertEqual(mentioned_users, [540, 554])

        # Check wrong mentioning
        message = 'Hi <@U08RGD1RD|jon>: How are you?'
        text, mentioned_users, has_link = convert_to_zulip_markdown(message, users, slack_user_map)
        self.assertEqual(text, message)
        self.assertEqual(mentioned_users, [])

    def test_has_link(self) -> None:
        slack_user_map = {}  # type: Dict[str, int]

        message = '<http://journals.plos.org/plosone/article>'
        text, mentioned_users, has_link = convert_to_zulip_markdown(message, [], slack_user_map)
        self.assertEqual(text, 'http://journals.plos.org/plosone/article')
        self.assertEqual(has_link, True)

        message = '<mailto:foo@foo.com>'
        text, mentioned_users, has_link = convert_to_zulip_markdown(message, [], slack_user_map)
        self.assertEqual(text, 'mailto:foo@foo.com')
        self.assertEqual(has_link, True)

        message = 'random message'
        text, mentioned_users, has_link = convert_to_zulip_markdown(message, [], slack_user_map)
        self.assertEqual(has_link, False)
