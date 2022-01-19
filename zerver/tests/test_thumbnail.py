from io import StringIO

import orjson

from zerver.lib.test_classes import ZulipTestCase


class ThumbnailTest(ZulipTestCase):
    def test_thumbnail_redirect(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.jpeg"

        result = self.client_post("/json/user_uploads", {"file": fp})
        self.assert_json_success(result)
        json = orjson.loads(result.content)
        self.assertIn("uri", json)
        uri = json["uri"]
        base = "/user_uploads/"
        self.assertEqual(base, uri[: len(base)])

        result = self.client_get("/thumbnail", {"url": uri[1:], "size": "full"})
        self.assertEqual(result.status_code, 302, result)
        self.assertEqual(uri, result.url)

        self.login("iago")
        result = self.client_get("/thumbnail", {"url": uri[1:], "size": "full"})
        self.assertEqual(result.status_code, 403, result)
        self.assert_in_response("You are not authorized to view this file.", result)

        uri = "https://www.google.com/images/srpr/logo4w.png"
        result = self.client_get("/thumbnail", {"url": uri, "size": "full"})
        self.assertEqual(result.status_code, 302, result)
        base = "https://external-content.zulipcdn.net/external_content/56c362a24201593891955ff526b3b412c0f9fcd2/68747470733a2f2f7777772e676f6f676c652e636f6d2f696d616765732f737270722f6c6f676f34772e706e67"
        self.assertEqual(base, result.url)

        uri = "http://www.google.com/images/srpr/logo4w.png"
        result = self.client_get("/thumbnail", {"url": uri, "size": "full"})
        self.assertEqual(result.status_code, 302, result)
        base = "https://external-content.zulipcdn.net/external_content/7b6552b60c635e41e8f6daeb36d88afc4eabde79/687474703a2f2f7777772e676f6f676c652e636f6d2f696d616765732f737270722f6c6f676f34772e706e67"
        self.assertEqual(base, result.url)

        uri = "//www.google.com/images/srpr/logo4w.png"
        result = self.client_get("/thumbnail", {"url": uri, "size": "full"})
        self.assertEqual(result.status_code, 302, result)
        base = "https://external-content.zulipcdn.net/external_content/676530cf4b101d56f56cc4a37c6ef4d4fd9b0c03/2f2f7777772e676f6f676c652e636f6d2f696d616765732f737270722f6c6f676f34772e706e67"
        self.assertEqual(base, result.url)
