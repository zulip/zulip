import os

import orjson

from zerver.lib.split_message import split_message_content
from zerver.lib.test_classes import ZulipTestCase


class SplitMessageTest(ZulipTestCase):
    def test_split_message_test_cases(self) -> None:
        with open(
            os.path.join(os.path.dirname(__file__), "fixtures/split_message_test_cases.json"), "rb"
        ) as f:
            test_cases = orjson.loads(f.read())["split_message_test_cases"]

        for test_case in test_cases:
            with self.subTest(name=test_case["name"]):
                self.assertEqual(
                    split_message_content(test_case["input"]), test_case["expected_parts"]
                )

    def test_split_message_content_max_parts(self) -> None:
        content = "\n\n\n".join(f"part {i}" for i in range(30))
        self.assertEqual(
            split_message_content(content, max_parts=3), ["part 0", "part 1", "part 2"]
        )
        self.assert_length(split_message_content(content), 30)
