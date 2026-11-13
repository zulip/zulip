import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from unittest import mock

from tools.triage_bot.gather import (
    ConversationLink,
    CzoThread,
    Item,
    czo_links,
    linked_item_refs,
    parse_conversation_link,
)
from tools.triage_bot.triage_bot import (
    PostedMessages,
    Zulip,
    card_heading,
    post,
    silence_mentions,
    topic_name,
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


class TestTopicName(unittest.TestCase):
    def test_week_in_one_month(self) -> None:
        self.assertEqual(topic_name(date(2026, 10, 8)), "October 5–11, 2026")

    def test_week_across_months(self) -> None:
        self.assertEqual(topic_name(date(2026, 10, 26)), "October 26–November 1, 2026")
        self.assertEqual(topic_name(date(2026, 11, 1)), "October 26–November 1, 2026")

    def test_week_across_years(self) -> None:
        self.assertEqual(topic_name(date(2026, 12, 31)), "December 28, 2026–January 3, 2027")


class TestSilenceMentions(unittest.TestCase):
    def test_mentions(self) -> None:
        self.assertEqual(
            silence_mentions("Bug @**all** in compose; cc @**Tim Abbott** and @*support*"),
            "Bug @_**all** in compose; cc @_**Tim Abbott** and @_*support*",
        )

    def test_silent_mentions_and_github_logins(self) -> None:
        text = "@_**Tim Abbott**, @timabbott, could you review this?"
        self.assertEqual(silence_mentions(text), text)


ITEM = Item(
    number=40000,
    kind="pr",
    url="https://github.com/zulip/zulip/pull/40000",
    title="compose: Fix the thing.",
    author="contributor",
    author_association="CONTRIBUTOR",
    author_is_maintainer=False,
    created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    labels=["bug"],
    assignees=[],
    body="",
)


class TestPostedMessages(unittest.TestCase):
    def test_headings(self) -> None:
        posted = PostedMessages()
        posted.add(card_heading(ITEM) + "\n\nThe card.", "October 5–11, 2026")
        self.assertEqual(posted.card_topics, {40000: "October 5–11, 2026"})

    def test_other_messages(self) -> None:
        posted = PostedMessages()
        # The item's number must match the number its URL ends with.
        posted.add(
            "**[#4000 compose: Fix the thing.](https://github.com/zulip/zulip/pull/40000)**", "t"
        )
        # Only the first line counts.
        posted.add("Hello\n" + card_heading(ITEM), "t")
        self.assertEqual(posted, PostedMessages())

    def test_newest_card_topic(self) -> None:
        posted = PostedMessages()
        posted.add(card_heading(ITEM), "renamed topic")
        posted.add(card_heading(ITEM), "October 5–11, 2026")
        self.assertEqual(posted.card_topics, {40000: "renamed topic"})


def bot_message(message_id: int, content: str, topic: str) -> dict[str, object]:
    return {"id": message_id, "content": content, "subject": topic}


class TestLoadPosted(unittest.TestCase):
    def test_pages(self) -> None:
        zulip = Zulip("triage-bot@chat.zulip.org", "key", "triage")
        pages = [
            {
                "found_oldest": False,
                "messages": [bot_message(20, card_heading(ITEM), "week 2")],
            },
            {
                "found_oldest": True,
                "messages": [bot_message(10, card_heading(ITEM), "week 1")],
            },
        ]
        with mock.patch.object(zulip, "get", side_effect=pages) as get:
            zulip.load_posted()
        self.assertEqual(zulip.posted.card_topics, {40000: "week 2"})
        self.assertEqual([call.args[1]["anchor"] for call in get.call_args_list], ["newest", "20"])
        params = get.call_args.args[1]
        self.assertEqual(params["include_anchor"], "false")
        self.assertEqual(
            json.loads(params["narrow"]),
            [
                {"operator": "channel", "operand": "triage"},
                {"operator": "sender", "operand": "triage-bot@chat.zulip.org"},
            ],
        )

    def test_empty_last_page(self) -> None:
        zulip = Zulip("triage-bot@chat.zulip.org", "key", "triage")
        # A full last page has found_oldest false, and the page after it is empty.
        pages = [
            {"found_oldest": False, "messages": [bot_message(10, card_heading(ITEM), "t")]},
            {"found_oldest": True, "messages": []},
        ]
        with mock.patch.object(zulip, "get", side_effect=pages) as get:
            zulip.load_posted()
        self.assertEqual(zulip.posted.card_topics, {40000: "t"})
        self.assertEqual(get.call_count, 2)


class TestPost(unittest.TestCase):
    def test_post_is_added(self) -> None:
        zulip = Zulip("triage-bot@chat.zulip.org", "key", "triage")
        with redirect_stdout(io.StringIO()):
            post(zulip, card_heading(ITEM), "The card.", dry_run=True)
        self.assertEqual(list(zulip.posted.card_topics), [40000])
