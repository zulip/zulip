import unittest
from unittest import mock

from github.PullRequestComment import PullRequestComment
from github.PullRequestReview import PullRequestReview

from tools.triage_bot.gather import (
    ConversationLink,
    CzoThread,
    czo_links,
    fetch_comments,
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


def review_event(state: str, body: str, day: int) -> dict[str, object]:
    return {
        "event": "reviewed",
        "user": {"login": "timabbott"},
        "author_association": "MEMBER",
        "state": state,
        "body": body,
        "submitted_at": f"2026-10-{day:02}T00:00:00Z",
    }


class TestFetchComments(unittest.TestCase):
    def test_reviews_and_inline_comments(self) -> None:
        events: list[dict[str, object]] = [
            {
                "event": "commented",
                "actor": {"login": "contributor"},
                "author_association": "CONTRIBUTOR",
                "body": "Ready for review.",
                "created_at": "2026-10-01T00:00:00Z",
            },
            review_event("changes_requested", "", 3),
            review_event("approved", "Looks good!", 4),
            review_event("dismissed", "", 4),
            # Holds only the inline comment below.
            review_event("commented", "", 5),
        ]
        requester = mock.Mock()
        # As PyGithub builds it from a page of the list response.
        inline_comment = PullRequestComment(
            requester,
            {},
            {
                "url": "https://api.github.com/repos/zulip/zulip/pulls/comments/1",
                "user": {"login": "timabbott", "type": "User"},
                "author_association": "MEMBER",
                "body": "Typo here.",
                "path": "web/src/compose.ts",
                "pull_request_review_id": 7,
                # Drafted before the reviews above, but sent after them.
                "created_at": "2026-10-02T00:00:00Z",
                "html_url": "https://github.com/zulip/zulip/pull/40000#discussion_r1",
            },
            completed=False,
        )
        with mock.patch("tools.triage_bot.gather.repository") as repository:
            repository().get_pull().get_review_comments.return_value = [inline_comment]
            repository().get_pull().get_reviews.return_value = [
                PullRequestReview(requester, {}, {"id": 7, "submitted_at": "2026-10-05T00:00:00Z"})
            ]
            comments = fetch_comments(40000, "pr", events)
        requester.requestJsonAndCheck.assert_not_called()
        self.assertEqual(
            [(comment.kind, comment.review_state, comment.path) for comment in comments],
            [
                ("comment", None, None),
                ("review", "changes_requested", None),
                ("review", "approved", None),
                ("inline_comment", None, "web/src/compose.ts"),
            ],
        )

    def test_issue_has_no_inline_comments(self) -> None:
        with mock.patch("tools.triage_bot.gather.repository") as repository:
            self.assertEqual(fetch_comments(40000, "issue", []), [])
        repository.assert_not_called()
