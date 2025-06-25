from zerver.lib.narrow import BadNarrowOperatorError
from zerver.lib.narrow_helpers import NarrowTerm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_decoding import Filter, parse_narrow_url
from zerver.lib.url_encoding import (
    encode_channel,
    encode_user_full_name_and_id,
    encode_user_ids,
    generate_narrow_link_from_narrow_terms,
)
from zerver.models.realms import get_realm


class URLEncodeTest(ZulipTestCase):
    def test_encode_channel(self) -> None:
        # We have more tests for this function in `test_topic_link_utils.py`
        self.assertEqual(encode_channel(9, "Verona"), "9-Verona")
        self.assertEqual(encode_channel(123, "General"), "123-General")
        self.assertEqual(encode_channel(7, "random_channel"), "7-random_channel")
        self.assertEqual(encode_channel(9, "Verona", with_operator=True), "channel/9-Verona")

    def test_encode_user_ids(self) -> None:
        # Group narrow URL has 3 or more user IDs
        self.assertEqual(encode_user_ids([1, 2, 3]), "1,2,3-group")
        self.assertEqual(encode_user_ids([3, 1, 2]), "1,2,3-group")

        # One-on-one narrow URL has 2 user IDs
        self.assertEqual(encode_user_ids([1, 2]), "1,2")

        # Narrow URL to ones own direct message conversation
        self.assertEqual(encode_user_ids([1]), "1")

        self.assertEqual(encode_user_ids([1, 2, 3], with_operator=True), "dm/1,2,3-group")
        with self.assertRaises(AssertionError):
            encode_user_ids([])

    def test_encode_user_full_name_and_id(self) -> None:
        self.assertEqual(encode_user_full_name_and_id("King Hamlet", 9), "9-King-Hamlet")
        self.assertEqual(
            encode_user_full_name_and_id("King Hamlet", 9, with_operator=True), "dm/9-King-Hamlet"
        )
        self.assertEqual(encode_user_full_name_and_id("ZOE", 1), "1-ZOE")
        self.assertEqual(encode_user_full_name_and_id("  User Name  ", 100), "100-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User  Name", 101), "101-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User/Name", 200), "200-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User%Name", 201), "201-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User<Name>", 202), "202-User-Name-")
        self.assertEqual(encode_user_full_name_and_id('User"Name`', 203), "203-User-Name-")
        self.assertEqual(encode_user_full_name_and_id('User/ % < > ` " Name', 204), "204-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User--Name", 205), "205-User--Name")
        self.assertEqual(encode_user_full_name_and_id("User%%Name", 206), "206-User-Name")
        self.assertEqual(encode_user_full_name_and_id("User_Name", 5), "5-User_Name")

    def test_generate_narrow_link_from_narrow_terms(self) -> None:
        realm = get_realm("zulip")
        channel_id = self.get_stream_id("Verona", realm)

        terms = [
            NarrowTerm("near", 98765, False),
            NarrowTerm("topic", "Bug Reports", False),
            NarrowTerm("channel", channel_id, False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm, sort_terms=False)
        expected_narrow_link = "/#narrow/near/98765/topic/Bug.20Reports/channel/3-Verona"
        self.assertEqual(narrow_link, expected_narrow_link)

        # Narrow link has operators in correct order.
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm, sort_terms=True)
        expected_narrow_link = "/#narrow/channel/3-Verona/topic/Bug.20Reports/near/98765"
        self.assertEqual(narrow_link, expected_narrow_link)

        # Fallback link to home-view.
        self.assertEqual(generate_narrow_link_from_narrow_terms([], realm), "#")

        # Unsupported operator error.
        terms = [NarrowTerm("unknown", 98765, False)]
        with self.assertRaises(AssertionError) as e:
            generate_narrow_link_from_narrow_terms(terms, realm)
        self.assertEqual(str(e.exception), "This operator is not yet supported: 'unknown'.")

        # Invalid operand type.
        invalid_terms = [
            NarrowTerm("dm", "foo", False),
            NarrowTerm("topic", 1, False),
            NarrowTerm("with", "bar", False),
            NarrowTerm("near", "baz", False),
            NarrowTerm("channel", [1, 2], False),
        ]
        for term in invalid_terms:
            with self.assertRaises(AssertionError):
                generate_narrow_link_from_narrow_terms([term], realm)

    def test_generate_channel_narrow_link_from_terms(self) -> None:
        realm = get_realm("zulip")
        channel_id = self.get_stream_id("Verona", realm)

        # Test encode channel ID and channel name.
        expected_narrow_link = f"/#narrow/channel/{channel_id}-Verona"
        terms = [
            NarrowTerm("channel", channel_id, False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        self.assertEqual(narrow_link, expected_narrow_link)

        terms = [
            NarrowTerm("channel", "Verona", False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        self.assertEqual(narrow_link, expected_narrow_link)

        # Invalid channel operand.
        terms = [
            NarrowTerm("channel", "9999", False),
        ]
        with self.assertRaises(BadNarrowOperatorError) as e:
            narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        self.assertEqual(str(e.exception), "Invalid narrow operator: unknown channel 9999")

    def test_generate_direct_message_narrow_links_from_terms(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        zoe = self.example_user("ZOE")
        othello = self.example_user("othello")

        # Test generate direct message to ones self.
        expected_narrow_link = f"/#narrow/dm/{zoe.id}-Zoe/near/1"
        terms = [
            NarrowTerm("dm", [zoe.id], False),
            NarrowTerm("near", 1, False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        self.assertEqual(narrow_link, expected_narrow_link)

        # Test generate one-on-one direct message.
        user_ids = [hamlet.id, zoe.id]
        dm_recipient_slug = encode_user_ids(user_ids, False)
        expected_narrow_link = f"/#narrow/dm/{dm_recipient_slug}/near/1"
        terms = [
            NarrowTerm("dm", user_ids, False),
            NarrowTerm("near", 1, False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        self.assertEqual(narrow_link, expected_narrow_link)

        # Test generate group direct message.
        user_ids = [hamlet.id, zoe.id, othello.id]
        group_recipient_slug = encode_user_ids(user_ids, False)
        expected_narrow_link = f"/#narrow/dm/{group_recipient_slug}/near/1"
        terms = [
            NarrowTerm("dm", user_ids, False),
            NarrowTerm("near", 1, False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        self.assertEqual(narrow_link, expected_narrow_link)

        # Invalid dm operand.
        terms = [
            NarrowTerm("dm", [], False),
        ]
        with self.assertRaises(BadNarrowOperatorError) as e:
            narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        self.assertEqual(str(e.exception), "Invalid narrow operator: invalid user ID")

        # Unknown user id error.
        terms = [
            NarrowTerm("dm", [9999], False),
            NarrowTerm("near", 1, False),
        ]
        with self.assertRaises(BadNarrowOperatorError) as e:
            narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        self.assertEqual(str(e.exception), "Invalid narrow operator: unknown user in [9999]")

    def test_decode_encode_narrow_link(self) -> None:
        """
        This tests the `parse_narrow_url` -> `Filter` -> `generate_narrow_link_from_narrow_terms`
        flow which covers the whole process of decoding and encoding a narrow link.
        """
        realm = get_realm("zulip")
        channel_id = self.get_stream_id("Verona", realm)

        dm_narrow = f"/#narrow/channel/{channel_id}-Verona"
        raw_terms = parse_narrow_url(dm_narrow)
        assert raw_terms is not None
        dm_narrow_filter = Filter(raw_terms)
        dm_narrow_terms = dm_narrow_filter.terms()
        self.assertEqual(
            dm_narrow,
            generate_narrow_link_from_narrow_terms(
                dm_narrow_terms,
                realm,
                True,
            ),
        )
