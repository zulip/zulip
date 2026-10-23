import json
import os
import unittest

from tools.triage_bot.gather import (
    conversation_operands,
    czo_links,
    linked_item_refs,
    parse_narrow_url,
    zulip_ci_checks,
)

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(
    os.path.dirname(TOOLS_DIR), "zerver/tests/fixtures/narrow_url_to_narrow_terms.json"
)


class TestParseNarrowUrl(unittest.TestCase):
    def test_matches_the_server(self) -> None:
        # The same cases as zerver/tests/test_url_decoding.py, so the copy
        # can't drift from the server's parse_narrow_url.
        with open(FIXTURE) as f:
            test_cases = json.load(f)
        for test_case in test_cases:
            with self.subTest(name=test_case["name"]):
                self.assertEqual(
                    parse_narrow_url(test_case["near_link"]), test_case.get("expected_output")
                )


class TestCzoLinks(unittest.TestCase):
    def test_trailing_punctuation(self) -> None:
        link = "https://chat.zulip.org/#narrow/channel/9-issues/topic/foo/near/123"
        for text in [f"See {link}.", f"({link})", f"[here]({link}),", f"<{link}>"]:
            with self.subTest(text=text):
                self.assertEqual(czo_links(text), [link])

    def test_encoded_punctuation_is_kept(self) -> None:
        link = "https://chat.zulip.org/#narrow/channel/9-issues/topic/why.3F"
        self.assertEqual(czo_links(f"{link}?"), [link])

    def test_other_links(self) -> None:
        self.assertEqual(
            czo_links("https://chat.zulip.org/help/ and https://github.com/zulip/zulip"), []
        )


class TestConversationOperands(unittest.TestCase):
    def test_conversation_links(self) -> None:
        czo = "https://chat.zulip.org/#narrow"
        self.assertEqual(
            conversation_operands(f"{czo}/channel/9-issues/topic/foo/with/123"),
            {"channel": 9, "topic": "foo", "with": "123"},
        )
        self.assertEqual(
            conversation_operands(f"{czo}/stream/9-issues/subject/foo"),
            {"channel": 9, "topic": "foo"},
        )
        self.assertEqual(conversation_operands(f"{czo}/dm/15-John/near/19"), {"dm": 15, "near": 19})

    def test_other_links(self) -> None:
        czo = "https://chat.zulip.org/#narrow"
        for link in [
            f"{czo}/channel/101-design",
            f"{czo}/channels/public/search/foo",
            f"{czo}/near/x",
        ]:
            with self.subTest(link=link):
                self.assertIsNone(conversation_operands(link))


class TestLinkedItemRefs(unittest.TestCase):
    def test_refs_in_order(self) -> None:
        text = (
            "Fixes #39001. See zulip/zulip-flutter#1234, zulip/zulip#777,"
            " https://github.com/zulip/zulip-flutter/issues/56 and"
            " https://github.com/zulip/zulip/pull/888."
        )
        self.assertEqual(
            linked_item_refs(text),
            [
                ("zulip/zulip", 39001),
                ("zulip/zulip-flutter", 1234),
                ("zulip/zulip", 777),
                ("zulip/zulip-flutter", 56),
                ("zulip/zulip", 888),
            ],
        )

    def test_short_numbers(self) -> None:
        # "#12" alone is usually a list position, not an issue.
        self.assertEqual(linked_item_refs("Step #2 of 3"), [])
        self.assertEqual(linked_item_refs("zulip/zulip-flutter#12"), [("zulip/zulip-flutter", 12)])


class TestZulipCiChecks(unittest.TestCase):
    def test_other_workflows_are_left_out(self) -> None:
        def check(name: str, conclusion: str, suite_id: int) -> dict[str, object]:
            return {"name": name, "conclusion": conclusion, "check_suite": {"id": suite_id}}

        # A failing Copilot code review job on the same commit as a passing Zulip CI run.
        checks = [
            check("Cleanup artifacts", "failure", 7),
            check("Agent", "success", 7),
            check("Ubuntu 22.04 (Python 3.10, backend + frontend)", "success", 3),
        ]
        self.assertEqual(
            zulip_ci_checks(checks, [{"check_suite_id": 3}]),
            [check("Ubuntu 22.04 (Python 3.10, backend + frontend)", "success", 3)],
        )
        # With no Zulip CI run, nothing counts.
        self.assertEqual(zulip_ci_checks(checks, []), [])
