import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_decoding import NearLinkHandler, is_same_server_message_link
from zerver.lib.url_encoding import near_message_url
from zerver.models.realms import get_realm


class URLDecodeTest(ZulipTestCase):
    def test_is_same_server_message_link(self) -> None:
        tests = orjson.loads(self.fixture_data("message_link_test_cases.json"))
        for test in tests:
            self.assertEqual(
                is_same_server_message_link(test["message_link"]), test["expected_output"]
            )


class NearLinkHandlerTest(ZulipTestCase):
    def build_test_message_near_link(self) -> str:
        realm = get_realm("zulip")
        message = dict(
            type="personal",
            id=555,
            display_recipient=[
                dict(id=77),
                dict(id=80),
            ],
        )
        url = near_message_url(
            realm=realm,
            message=message,
        )
        return url

    def test_initialize_near_link(self) -> None:
        url = self.build_test_message_near_link()

        with self.settings(EXTERNAL_HOST_WITHOUT_PORT="zulip.testserver"):
            handler = NearLinkHandler(url)
        self.assertEqual(handler.get_url(), url)

    def test_initialize_various_near_links(self) -> None:
        tests = orjson.loads(self.fixture_data("test_near_link_variations.json"))
        for test in tests["valid"]:
            url = test["near_link"]
            handler = NearLinkHandler(url)
            self.assertEqual(handler.get_url(), test["expected_output"], msg=test["name"])

    def test_initialize_invalid_near_links(self) -> None:
        tests = orjson.loads(self.fixture_data("test_near_link_variations.json"))
        error_message = "This near link is either invalid or not from this server."
        for test in tests["invalid"]:
            url = test["near_link"]
            with self.assertRaises(AssertionError) as e:
                NearLinkHandler(url)
            self.assertEqual(str(e.exception), error_message, msg=test["name"])

    def test_patch_near_link_fragment(self) -> None:
        old_url = "http://testserver/#narrow/stream/13-Denmark/topic/desktop/near/555"
        handler = NearLinkHandler(old_url)

        fragment_parts: list[str] = handler.get_near_link_fragment_parts()
        new_message_id = "444"
        fragment_parts[-1] = new_message_id
        handler.patch_near_link_fragment_parts(fragment_parts)

        new_url = (
            f"http://testserver/#narrow/channel/13-Denmark/topic/desktop/near/{new_message_id}"
        )
        self.assertEqual(handler.get_url(), new_url)
