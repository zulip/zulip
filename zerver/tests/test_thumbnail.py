from io import StringIO
from unittest.mock import patch

import orjson
import pyvips
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import ratelimit_rule, read_test_image_file
from zerver.lib.thumbnail import BadImageError, resize_emoji


class ThumbnailTest(ZulipTestCase):
    def test_thumbnail_redirect(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.jpeg"

        result = self.client_post("/json/user_uploads", {"file": fp})
        self.assert_json_success(result)
        json = orjson.loads(result.content)
        self.assertIn("uri", json)
        url = json["uri"]
        base = "/user_uploads/"
        self.assertEqual(base, url[: len(base)])

        result = self.client_get("/thumbnail", {"url": url[1:], "size": "full"})
        self.assertEqual(result.status_code, 302, result)
        self.assertEqual(url, result["Location"])

        self.login("iago")
        result = self.client_get("/thumbnail", {"url": url[1:], "size": "full"})
        self.assertEqual(result.status_code, 403, result)
        self.assert_in_response("You are not authorized to view this file.", result)

        url = "https://www.google.com/images/srpr/logo4w.png"
        result = self.client_get("/thumbnail", {"url": url, "size": "full"})
        self.assertEqual(result.status_code, 302, result)
        base = "https://external-content.zulipcdn.net/external_content/56c362a24201593891955ff526b3b412c0f9fcd2/68747470733a2f2f7777772e676f6f676c652e636f6d2f696d616765732f737270722f6c6f676f34772e706e67"
        self.assertEqual(base, result["Location"])

        url = "http://www.google.com/images/srpr/logo4w.png"
        result = self.client_get("/thumbnail", {"url": url, "size": "full"})
        self.assertEqual(result.status_code, 302, result)
        base = "https://external-content.zulipcdn.net/external_content/7b6552b60c635e41e8f6daeb36d88afc4eabde79/687474703a2f2f7777772e676f6f676c652e636f6d2f696d616765732f737270722f6c6f676f34772e706e67"
        self.assertEqual(base, result["Location"])

        url = "//www.google.com/images/srpr/logo4w.png"
        result = self.client_get("/thumbnail", {"url": url, "size": "full"})
        self.assertEqual(result.status_code, 302, result)
        base = "https://external-content.zulipcdn.net/external_content/676530cf4b101d56f56cc4a37c6ef4d4fd9b0c03/2f2f7777772e676f6f676c652e636f6d2f696d616765732f737270722f6c6f676f34772e706e67"
        self.assertEqual(base, result["Location"])

    @override_settings(RATE_LIMITING=True)
    def test_thumbnail_redirect_for_spectator(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.jpeg"

        result = self.client_post("/json/user_uploads", {"file": fp})
        self.assert_json_success(result)
        json = orjson.loads(result.content)
        url = json["uri"]

        with ratelimit_rule(86400, 1000, domain="spectator_attachment_access_by_file"):
            # Deny file access for non-web-public stream
            self.subscribe(self.example_user("hamlet"), "Denmark")
            host = self.example_user("hamlet").realm.host
            body = f"First message ...[zulip.txt](http://{host}" + url + ")"
            self.send_stream_message(self.example_user("hamlet"), "Denmark", body, "test")

            self.logout()
            response = self.client_get("/thumbnail", {"url": url[1:], "size": "full"})
            self.assertEqual(response.status_code, 403)

            # Allow file access for web-public stream
            self.login("hamlet")
            self.make_stream("web-public-stream", is_web_public=True)
            self.subscribe(self.example_user("hamlet"), "web-public-stream")
            body = f"First message ...[zulip.txt](http://{host}" + url + ")"
            self.send_stream_message(self.example_user("hamlet"), "web-public-stream", body, "test")

            self.logout()
            response = self.client_get("/thumbnail", {"url": url[1:], "size": "full"})
            self.assertEqual(response.status_code, 302)

        # Deny file access since rate limited
        with ratelimit_rule(86400, 0, domain="spectator_attachment_access_by_file"):
            response = self.client_get("/thumbnail", {"url": url[1:], "size": "full"})
            self.assertEqual(response.status_code, 403)

        # Deny random file access
        response = self.client_get(
            "/thumbnail",
            {
                "url": "user_uploads/2/71/QYB7LA-ULMYEad-QfLMxmI2e/zulip-non-existent.txt",
                "size": "full",
            },
        )
        self.assertEqual(response.status_code, 403)


class EmojiTest(ZulipTestCase):
    def animated_test(self, filename: str) -> None:
        animated_unequal_img_data = read_test_image_file(filename)
        original_image = pyvips.Image.new_from_buffer(animated_unequal_img_data, "n=-1")
        resized_img_data, still_img_data = resize_emoji(
            animated_unequal_img_data, filename, size=50
        )
        assert still_img_data is not None
        emoji_image = pyvips.Image.new_from_buffer(resized_img_data, "n=-1")
        self.assertEqual(emoji_image.get("vips-loader"), "gifload_buffer")
        self.assertEqual(emoji_image.get_n_pages(), original_image.get_n_pages())
        self.assertEqual(emoji_image.get("page-height"), 50)
        self.assertEqual(emoji_image.height, 150)
        self.assertEqual(emoji_image.width, 50)

        still_image = pyvips.Image.new_from_buffer(still_img_data, "")
        self.assertEqual(still_image.get("vips-loader"), "pngload_buffer")
        self.assertEqual(still_image.get_n_pages(), 1)
        self.assertEqual(still_image.height, 50)
        self.assertEqual(still_image.width, 50)

    def test_resize_animated_square(self) -> None:
        """An animated image which is square"""
        self.animated_test("animated_large_img.gif")

    def test_resize_animated_emoji(self) -> None:
        """An animated image which is not square"""
        self.animated_test("animated_unequal_img.gif")

    def test_resize_corrupt_emoji(self) -> None:
        corrupted_img_data = read_test_image_file("corrupt.gif")
        with self.assertRaises(BadImageError):
            resize_emoji(corrupted_img_data, "corrupt.gif")

    def test_resize_too_many_pixels(self) -> None:
        """An image file with too many pixels is not resized"""
        with patch("zerver.lib.thumbnail.IMAGE_BOMB_TOTAL_PIXELS", 100):
            animated_large_img_data = read_test_image_file("animated_large_img.gif")
            with self.assertRaises(BadImageError):
                resize_emoji(animated_large_img_data, "animated_large_img.gif", size=50)

            bomb_img_data = read_test_image_file("bomb.png")
            with self.assertRaises(BadImageError):
                resize_emoji(bomb_img_data, "bomb.png", size=50)

    def test_resize_still_gif(self) -> None:
        """A non-animated square emoji resize"""
        still_large_img_data = read_test_image_file("still_large_img.gif")
        resized_img_data, no_still_data = resize_emoji(
            still_large_img_data, "still_large_img.gif", size=50
        )
        emoji_image = pyvips.Image.new_from_buffer(resized_img_data, "n=-1")
        self.assertEqual(emoji_image.get("vips-loader"), "gifload_buffer")
        self.assertEqual(emoji_image.height, 50)
        self.assertEqual(emoji_image.width, 50)
        self.assertEqual(emoji_image.get_n_pages(), 1)
        assert no_still_data is None

    def test_resize_still_jpg(self) -> None:
        """A non-animatatable format resize"""
        still_large_img_data = read_test_image_file("img.jpg")
        resized_img_data, no_still_data = resize_emoji(still_large_img_data, "img.jpg", size=50)
        emoji_image = pyvips.Image.new_from_buffer(resized_img_data, "")
        self.assertEqual(emoji_image.get("vips-loader"), "jpegload_buffer")
        self.assertEqual(emoji_image.height, 50)
        self.assertEqual(emoji_image.width, 50)
        self.assertEqual(emoji_image.get_n_pages(), 1)
        assert no_still_data is None

    def test_non_image_format_wrong_content_type(self) -> None:
        """A file that is not an image"""
        non_img_data = read_test_image_file("text.txt")
        with self.assertRaises(BadImageError):
            resize_emoji(non_img_data, "text.png", size=50)
