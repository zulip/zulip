import unittest

from tools.lib.api_design_links import find_api_design_links, is_api_design_link

API_DESIGN = "https://chat.zulip.org/#narrow/channel/378-api-design"


class TestIsApiDesignLink(unittest.TestCase):
    def test_conversations_in_the_channel(self) -> None:
        for url in [
            f"{API_DESIGN}/topic/some.20topic",
            f"{API_DESIGN}/topic/some.20topic/near/12345",
            f"{API_DESIGN}/topic/some.20topic/with/12345",
            f"{API_DESIGN}/topic/some.20topic/",
            # A link to the channel's "general chat", whose topic is empty.
            f"{API_DESIGN}/topic/",
            # The channel's ID identifies it; the name that follows is decoration.
            "https://chat.zulip.org/#narrow/channel/378/topic/x",
            # Zulip called channels streams until 2024.
            "https://chat.zulip.org/#narrow/stream/378-api-design/topic/x",
        ]:
            with self.subTest(url=url):
                self.assertTrue(is_api_design_link(url))

    def test_other_links(self) -> None:
        for url in [
            # The channel as a whole, naming no conversation in it.
            API_DESIGN,
            f"{API_DESIGN}/",
            "https://chat.zulip.org/#narrow/channel/3-backend/topic/x",
            # A channel whose ID merely starts with the same digits.
            "https://chat.zulip.org/#narrow/channel/3780-other/topic/x",
            # A channel operator with no operand.
            "https://chat.zulip.org/#narrow/channel",
            "https://chat.zulip.org/#narrow",
            "https://chat.zulip.org/",
            "https://chat.zulip.org/api/get-messages",
            # Not the realm's root, so not a narrow link.
            "https://chat.zulip.org/somepage#narrow/channel/378-api-design",
            "https://example.com/#narrow/channel/378-api-design/topic/x",
            "not a URL at all",
            "",
        ]:
            with self.subTest(url=url):
                self.assertFalse(is_api_design_link(url))

    def test_unparseable_urls(self) -> None:
        # urlsplit rejects these outright, rather than returning parts.
        for url in [
            # An IPv6 host with no closing bracket.
            "https://[",
            "http://[::1",
            # A host whose characters change under NFKC normalization.
            "https://chat.zulip.org℀/#narrow/channel/378-api-design/topic/x",
        ]:
            with self.subTest(url=url):
                self.assertFalse(is_api_design_link(url))


class TestFindApiDesignLinks(unittest.TestCase):
    def test_markdown_link(self) -> None:
        text = f"Bug fix as discussed in [#api design > topic]({API_DESIGN}/topic/x/near/1)."
        self.assertEqual(find_api_design_links(text), [f"{API_DESIGN}/topic/x/near/1"])

    def test_trailing_punctuation(self) -> None:
        # None of these characters can appear in a narrow link itself, so
        # each came from the text around one.
        for suffix in [".", ",", ")", "]", ">", "?", "!", "**", "'", '"', ");"]:
            with self.subTest(suffix=suffix):
                text = f"See {API_DESIGN}/topic/x{suffix} Thanks!"
                self.assertEqual(find_api_design_links(text), [f"{API_DESIGN}/topic/x"])

    def test_returns_each_link_once_in_order(self) -> None:
        text = f"""
        First {API_DESIGN}/topic/a/near/1
        then {API_DESIGN}/topic/b/near/2
        and {API_DESIGN}/topic/a/near/1 again.
        """
        self.assertEqual(
            find_api_design_links(text),
            [f"{API_DESIGN}/topic/a/near/1", f"{API_DESIGN}/topic/b/near/2"],
        )

    def test_link_to_the_channel_itself(self) -> None:
        # A link to the channel names no discussion, so it's dropped even
        # alongside a link to a real thread.
        text = f"""
        Discussed in [#api design > some topic]({API_DESIGN}/topic/x/near/1).

        [#api design]: {API_DESIGN}
        """
        self.assertEqual(find_api_design_links(text), [f"{API_DESIGN}/topic/x/near/1"])

    def test_links_to_elsewhere(self) -> None:
        text = """
        Fixes #1234. Discussed with the team in
        https://chat.zulip.org/#narrow/channel/3-backend/topic/x
        and see https://zulip.com/api/send-message .
        """
        self.assertEqual(find_api_design_links(text), [])

    def test_no_text(self) -> None:
        self.assertEqual(find_api_design_links(""), [])
