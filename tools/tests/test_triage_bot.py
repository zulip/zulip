import unittest

from tools.triage_bot.gather import (
    ConversationLink,
    CzoThread,
    czo_links,
    linked_item_refs,
    parse_conversation_link,
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


class TestParseConversationLink(unittest.TestCase):
    def test_conversation_links(self) -> None:
        self.assertEqual(
            parse_conversation_link(
                "https://chat.zulip.org/#narrow/channel/9-issues/topic/foo/with/123"
            ),
            ConversationLink(message_id=123, channel_id=9, topic="foo"),
        )
        # Old links use "stream" and "subject" for "channel" and "topic".
        self.assertEqual(
            parse_conversation_link(
                "https://chat.zulip.org/#narrow/stream/9-issues/subject/foo.2Fbar"
            ),
            ConversationLink(message_id=None, channel_id=9, topic="foo/bar"),
        )
        # A message ID is enough to find the conversation, even in a DM link.
        self.assertEqual(
            parse_conversation_link("https://chat.zulip.org/#narrow/dm/15-John/near/19"),
            ConversationLink(message_id=19, channel_id=None, topic=None),
        )

    def test_other_links(self) -> None:
        for link in [
            "https://chat.zulip.org/#narrow/channel/101-design",
            "https://chat.zulip.org/#narrow/channels/public/search/foo",
            "https://chat.zulip.org/#narrow/near/x",
        ]:
            with self.subTest(link=link):
                self.assertIsNone(parse_conversation_link(link))


class TestCzoThreadUrl(unittest.TestCase):
    def test_url_leads_back_to_the_topic(self) -> None:
        thread = CzoThread(
            channel_id=101,
            channel="api design",
            topic="Why (not) 50%? v1.2",
            messages=[],
            found_oldest=True,
        )
        self.assertEqual(
            thread.url,
            "https://chat.zulip.org/#narrow/channel/101-api-design/topic/Why.20.28not.29.2050.25.3F.20v1.2E2",
        )
        self.assertEqual(
            parse_conversation_link(thread.url),
            ConversationLink(message_id=None, channel_id=101, topic="Why (not) 50%? v1.2"),
        )


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
