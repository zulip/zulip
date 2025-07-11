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

        # Channel narrow terms
        terms = [
            NarrowTerm("channel", channel_id, False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        expected_narrow_link = f"/#narrow/channel/{channel_id}-Verona"
        self.assertEqual(narrow_link, expected_narrow_link)

        # Topic narrow terms
        terms = [
            NarrowTerm("channel", channel_id, False),
            NarrowTerm("topic", "Bug Reports", False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        expected_narrow_link = f"/#narrow/channel/{channel_id}-Verona/topic/Bug.20Reports"
        self.assertEqual(narrow_link, expected_narrow_link)

        # Message narrow terms
        terms = [
            NarrowTerm("channel", channel_id, False),
            NarrowTerm("topic", "Bug Reports", False),
            NarrowTerm("near", 98765, False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        expected_narrow_link = (
            f"/#narrow/channel/{channel_id}-Verona/topic/Bug.20Reports/near/98765"
        )
        self.assertEqual(narrow_link, expected_narrow_link)

        # Unsorted narrow terms
        terms = [
            NarrowTerm("topic", "Bug Reports", False),
            NarrowTerm("channel", channel_id, False),
            NarrowTerm("near", 98765, False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        expected_narrow_link = "/#narrow/channel/3-Verona/topic/Bug.20Reports/near/98765"
        self.assertEqual(narrow_link, expected_narrow_link)

        # Unsorted narrow terms
        terms = [
            NarrowTerm("topic", "Bug Reports", False),
            NarrowTerm("channel", channel_id, False),
            NarrowTerm("near", 98765, False),
        ]
        narrow_link = generate_narrow_link_from_narrow_terms(terms, realm)
        expected_narrow_link = "/#narrow/channel/3-Verona/topic/Bug.20Reports/near/98765"
        self.assertEqual(narrow_link, expected_narrow_link)

    def test_decode_encode_narrow(self) -> None:
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
