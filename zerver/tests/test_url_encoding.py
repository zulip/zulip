from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_encoding import encode_full_name_and_id, encode_stream, encode_user_ids


class URLEncodeTest(ZulipTestCase):
    def test_encode_stream(self) -> None:
        # We have more tests for this function in `test_topci_link_utils.py`
        self.assertEqual(encode_stream(9, "Verona"), "9-Verona")
        self.assertEqual(encode_stream(123, "General"), "123-General")
        self.assertEqual(encode_stream(7, "random_stream"), "7-random_stream")
        self.assertEqual(encode_stream(9, "Verona", with_operator=True), "channel/9-Verona")

    def test_encode_user_ids(self) -> None:
        self.assertEqual(encode_user_ids([1, 2, 3]), "1,2,3-group")
        self.assertEqual(encode_user_ids([3, 1, 2]), "1,2,3-group")
        self.assertEqual(encode_user_ids([1, 2, 3], prefix="pm"), "1,2,3-pm")
        self.assertEqual(encode_user_ids([1, 2, 3], with_operator=True), "dm/1,2,3-group")
        self.assertEqual(encode_user_ids([1, 2, 3], with_operator=True, prefix="pm"), "dm/1,2,3-pm")
        self.assertEqual(encode_user_ids([5]), "5-group")
        with self.assertRaises(AssertionError):
            self.assertEqual(encode_user_ids([]), "-group")

    def test_encode_full_name_and_id(self) -> None:
        self.assertEqual(encode_full_name_and_id("King Hamlet", 9), "9-King-Hamlet")
        self.assertEqual(
            encode_full_name_and_id("King Hamlet", 9, with_operator=True), "dm/9-King-Hamlet"
        )
        self.assertEqual(encode_full_name_and_id("ZOE", 1), "1-ZOE")
        self.assertEqual(encode_full_name_and_id("  User Name  ", 100), "100-User-Name")
        self.assertEqual(encode_full_name_and_id("User  Name", 101), "101-User-Name")
        self.assertEqual(encode_full_name_and_id("User/Name", 200), "200-User-Name")
        self.assertEqual(encode_full_name_and_id("User%Name", 201), "201-User-Name")
        self.assertEqual(encode_full_name_and_id("User<Name>", 202), "202-User-Name-")
        self.assertEqual(encode_full_name_and_id('User"Name`', 203), "203-User-Name-")
        self.assertEqual(encode_full_name_and_id('User/ % < > ` " Name', 204), "204-User-Name")
        self.assertEqual(encode_full_name_and_id("User--Name", 205), "205-User--Name")
        self.assertEqual(encode_full_name_and_id("User%%Name", 206), "206-User-Name")
        self.assertEqual(encode_full_name_and_id("User_Name", 5), "5-User_Name")
