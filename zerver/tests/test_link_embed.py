import re
from collections import OrderedDict
from typing import TYPE_CHECKING, Any
from unittest import mock
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import orjson
import responses
from django.test import override_settings
from django.utils.html import escape
from pyoembed.providers import get_provider
from requests.exceptions import ConnectionError
from typing_extensions import override

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.user_groups import check_add_user_group
from zerver.lib.cache import cache_delete, cache_get, preview_url_cache_key
from zerver.lib.camo import get_camo_url
from zerver.lib.queue import queue_json_publish_rollback_unsafe
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish
from zerver.lib.url_preview.oembed import get_oembed_data, strip_cdata
from zerver.lib.url_preview.parsers import GenericParser, OpenGraphParser
from zerver.lib.url_preview.preview import get_link_embed_data
from zerver.lib.url_preview.types import UrlEmbedData, UrlOEmbedData
from zerver.models import Message, NamedUserGroup, Realm, UserMessage, UserProfile
from zerver.models.groups import SystemGroups
from zerver.worker.embed_links import FetchLinksEmbedData

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


def reconstruct_url(url: str, maxwidth: int = 640, maxheight: int = 480) -> str:
    # The following code is taken from
    # https://github.com/rafaelmartins/pyoembed/blob/master/pyoembed/__init__.py.
    # This is a helper function which will be indirectly use to mock the HTTP responses.
    provider = get_provider(str(url))
    oembed_url = provider.oembed_url(url)
    scheme, netloc, path, query_string, fragment = urlsplit(oembed_url)

    query_params = OrderedDict(parse_qsl(query_string))
    query_params["maxwidth"] = str(maxwidth)
    query_params["maxheight"] = str(maxheight)
    final_url = urlunsplit((scheme, netloc, path, urlencode(query_params, True), fragment))
    return final_url


@override_settings(INLINE_URL_EMBED_PREVIEW=True)
class OembedTestCase(ZulipTestCase):
    @responses.activate
    def test_present_provider(self) -> None:
        response_data = {
            "type": "rich",
            "thumbnail_url": "https://scontent.cdninstagram.com/t51.2885-15/n.jpg",
            "thumbnail_width": 640,
            "thumbnail_height": 426,
            "title": "NASA",
            "html": "<p>test</p>",
            "version": "1.0",
            "width": 658,
            "height": 400,
        }
        url = "http://instagram.com/p/BLtI2WdAymy"
        reconstructed_url = reconstruct_url(url)
        responses.add(
            responses.GET,
            reconstructed_url,
            json=response_data,
            status=200,
        )

        data = get_oembed_data(url)
        assert data is not None
        self.assertIsInstance(data, UrlEmbedData)
        self.assertEqual(data.title, response_data["title"])

    @responses.activate
    def test_photo_provider(self) -> None:
        response_data = {
            "type": "photo",
            "thumbnail_url": "https://scontent.cdninstagram.com/t51.2885-15/n.jpg",
            "url": "https://scontent.cdninstagram.com/t51.2885-15/n.jpg",
            "thumbnail_width": 640,
            "thumbnail_height": 426,
            "title": "NASA",
            "html": "<p>test</p>",
            "version": "1.0",
            "width": 658,
            "height": 400,
        }
        # pyoembed.providers.imgur only works with http:// URLs, not https:// (!)
        url = "http://imgur.com/photo/158727223"
        reconstructed_url = reconstruct_url(url)
        responses.add(
            responses.GET,
            reconstructed_url,
            json=response_data,
            status=200,
        )

        data = get_oembed_data(url)
        assert data is not None
        self.assertIsInstance(data, UrlOEmbedData)
        self.assertEqual(data.title, response_data["title"])

    @responses.activate
    def test_video_provider(self) -> None:
        response_data = {
            "type": "video",
            "thumbnail_url": "https://scontent.cdninstagram.com/t51.2885-15/n.jpg",
            "thumbnail_width": 640,
            "thumbnail_height": 426,
            "title": "NASA",
            "html": "<p>test</p>",
            "version": "1.0",
            "width": 658,
            "height": 400,
        }
        url = "http://blip.tv/video/158727223"
        reconstructed_url = reconstruct_url(url)
        responses.add(
            responses.GET,
            reconstructed_url,
            json=response_data,
            status=200,
        )

        data = get_oembed_data(url)
        assert data is not None
        self.assertIsInstance(data, UrlOEmbedData)
        self.assertEqual(data.title, response_data["title"])

    @responses.activate
    def test_connect_error_request(self) -> None:
        url = "http://instagram.com/p/BLtI2WdAymy"
        reconstructed_url = reconstruct_url(url)
        responses.add(responses.GET, reconstructed_url, body=ConnectionError())
        data = get_oembed_data(url)
        self.assertIsNone(data)

    @responses.activate
    def test_400_error_request(self) -> None:
        url = "http://instagram.com/p/BLtI2WdAymy"
        reconstructed_url = reconstruct_url(url)
        responses.add(responses.GET, reconstructed_url, status=400)
        data = get_oembed_data(url)
        self.assertIsNone(data)

    @responses.activate
    def test_500_error_request(self) -> None:
        url = "http://instagram.com/p/BLtI2WdAymy"
        reconstructed_url = reconstruct_url(url)
        responses.add(responses.GET, reconstructed_url, status=500)
        data = get_oembed_data(url)
        self.assertIsNone(data)

    @responses.activate
    def test_invalid_json_in_response(self) -> None:
        url = "http://instagram.com/p/BLtI2WdAymy"
        reconstructed_url = reconstruct_url(url)
        responses.add(
            responses.GET,
            reconstructed_url,
            json="{invalid json}",
            status=200,
        )
        data = get_oembed_data(url)
        self.assertIsNone(data)

    def test_oembed_html(self) -> None:
        html = '<iframe src="//www.instagram.com/embed.js"></iframe>'
        stripped_html = strip_cdata(html)
        self.assertEqual(html, stripped_html)

    def test_autodiscovered_oembed_xml_format_html(self) -> None:
        iframe_content = '<iframe src="https://w.soundcloud.com/player"></iframe>'
        html = f"<![CDATA[{iframe_content}]]>"
        stripped_html = strip_cdata(html)
        self.assertEqual(iframe_content, stripped_html)


class OpenGraphParserTestCase(ZulipTestCase):
    def test_page_with_og(self) -> None:
        html = b"""<html>
          <head>
          <meta property="og:title" content="The Rock" />
          <meta property="og:type" content="video.movie" />
          <meta property="og:url" content="http://www.imdb.com/title/tt0117500/" />
          <meta property="og:image" content="http://ia.media-imdb.com/images/rock.jpg" />
          <meta property="og:description" content="The Rock film" />
          </head>
        </html>"""

        parser = OpenGraphParser(html, "text/html; charset=UTF-8")
        result = parser.extract_data()
        self.assertEqual(result.title, "The Rock")
        self.assertEqual(result.description, "The Rock film")

    def test_charset_in_header(self) -> None:
        html = """<html>
          <head>
            <meta property="og:title" content="中文" />
          </head>
        </html>""".encode("big5")
        parser = OpenGraphParser(html, "text/html; charset=Big5")
        result = parser.extract_data()
        self.assertEqual(result.title, "中文")

    def test_charset_in_meta(self) -> None:
        html = """<html>
          <head>
            <meta content-type="text/html; charset=Big5" />
            <meta property="og:title" content="中文" />
          </head>
        </html>""".encode("big5")
        parser = OpenGraphParser(html, "text/html")
        result = parser.extract_data()
        self.assertEqual(result.title, "中文")


class GenericParserTestCase(ZulipTestCase):
    def test_parser(self) -> None:
        html = b"""
          <html>
            <head><title>Test title</title></head>
            <body>
                <h1>Main header</h1>
                <p>Description text</p>
            </body>
          </html>
        """
        parser = GenericParser(html, "text/html; charset=UTF-8")
        result = parser.extract_data()
        self.assertEqual(result.title, "Test title")
        self.assertEqual(result.description, "Description text")

    def test_extract_image(self) -> None:
        html = b"""
          <html>
            <body>
                <h1>Main header</h1>
                <img data-src="Not an image">
                <img src="http://test.com/test.jpg">
                <div>
                    <p>Description text</p>
                </div>
            </body>
          </html>
        """
        parser = GenericParser(html, "text/html; charset=UTF-8")
        result = parser.extract_data()
        self.assertEqual(result.title, "Main header")
        self.assertEqual(result.description, "Description text")
        self.assertEqual(result.image, "http://test.com/test.jpg")

    def test_extract_bad_image(self) -> None:
        html = b"""
          <html>
            <body>
                <h1>Main header</h1>
                <img data-src="Not an image">
                <img src="http://[bad url/test.jpg">
                <div>
                    <p>Description text</p>
                </div>
            </body>
          </html>
        """
        parser = GenericParser(html, "text/html; charset=UTF-8")
        result = parser.extract_data()
        self.assertEqual(result.title, "Main header")
        self.assertEqual(result.description, "Description text")
        self.assertIsNone(result.image)

    def test_extract_description(self) -> None:
        html = b"""
          <html>
            <body>
                <div>
                    <div>
                        <p>Description text</p>
                    </div>
                </div>
            </body>
          </html>
        """
        parser = GenericParser(html, "text/html; charset=UTF-8")
        result = parser.extract_data()
        self.assertEqual(result.description, "Description text")

        html = b"""
          <html>
            <head><meta name="description" content="description 123"</head>
            <body></body>
          </html>
        """
        parser = GenericParser(html, "text/html; charset=UTF-8")
        result = parser.extract_data()
        self.assertEqual(result.description, "description 123")

        html = b"<html><body></body></html>"
        parser = GenericParser(html, "text/html; charset=UTF-8")
        result = parser.extract_data()
        self.assertIsNone(result.description)


class PreviewTestCase(ZulipTestCase):
    open_graph_html = """
          <html>
            <head>
                <title>Test title</title>
                <meta property="og:title" content="The Rock" />
                <meta property="og:type" content="video.movie" />
                <meta property="og:url" content="http://www.imdb.com/title/tt0117500/" />
                <meta property="og:image" content="http://ia.media-imdb.com/images/rock.jpg" />
                <meta http-equiv="refresh" content="30" />
                <meta property="notog:extra-text" content="Extra!" />
            </head>
            <body>
                <h1>Main header</h1>
                <p>Description text</p>
            </body>
          </html>
        """

    @override
    def setUp(self) -> None:
        super().setUp()
        Realm.objects.all().update(inline_url_embed_preview=True)

    @classmethod
    def create_mock_response(
        cls,
        url: str,
        status: int = 200,
        relative_url: bool = False,
        content_type: str = "text/html",
        body: str | ConnectionError | None = None,
    ) -> None:
        if body is None:
            body = cls.open_graph_html
        if relative_url is True and isinstance(body, str):
            body = body.replace("http://ia.media-imdb.com", "")
        responses.add(responses.GET, url, body=body, status=status, content_type=content_type)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_edit_message_history(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        msg_id = self.send_stream_message(user, "Denmark", topic_name="editing", content="original")

        url = "http://test.org/"
        self.create_mock_response(url)

        with mock_queue_publish("zerver.actions.message_edit.queue_event_on_commit") as patched:
            result = self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "content": url,
                },
            )
            self.assert_json_success(result)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        with self.settings(TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
                in info_logs.output[0]
            )

        embedded_link = f'<a href="{url}" title="The Rock">The Rock</a>'
        msg = Message.objects.select_related("sender").get(id=msg_id)
        assert msg.rendered_content is not None
        self.assertIn(embedded_link, msg.rendered_content)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def _send_message_with_test_org_url(
        self,
        sender: UserProfile,
        queue_should_run: bool = True,
        relative_url: bool = False,
        other_content: str = "",
    ) -> Message:
        url = "http://test.org/"
        # Ensure the cache for this is empty
        cache_delete(preview_url_cache_key(url))
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_personal_message(
                sender,
                self.example_user("cordelia"),
                content=url + other_content,
            )
            if queue_should_run:
                patched.assert_called_once()
                queue = patched.call_args[0][0]
                self.assertEqual(queue, "embed_links")
                event = patched.call_args[0][1]
            else:
                patched.assert_not_called()
                # If we nothing was put in the queue, we don't need to
                # run the queue processor or any of the following code
                return Message.objects.select_related("sender").get(id=msg_id)

        # Verify the initial message doesn't have the embedded links rendered
        msg = Message.objects.select_related("sender").get(id=msg_id)
        assert msg.rendered_content is not None
        self.assertNotIn(f'<a href="{url}" title="The Rock">The Rock</a>', msg.rendered_content)

        self.create_mock_response(url, relative_url=relative_url)

        # Run the queue processor to potentially rerender things
        with self.settings(TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
                in info_logs.output[0]
            )

        msg = Message.objects.select_related("sender").get(id=msg_id)
        return msg

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_message_update_race_condition(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        original_url = "http://test.org/"
        edited_url = "http://edited.org/"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(
                user, "Denmark", topic_name="foo", content=original_url
            )
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        def wrapped_queue_event_on_commit(*args: Any, **kwargs: Any) -> None:
            self.create_mock_response(original_url)
            self.create_mock_response(edited_url)

            with self.settings(TEST_SUITE=False), self.assertLogs(level="INFO") as info_logs:
                # Run the queue processor. This will simulate the event for original_url being
                # processed after the message has been edited.
                FetchLinksEmbedData().consume(event)
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
                in info_logs.output[0]
            )
            msg = Message.objects.select_related("sender").get(id=msg_id)
            assert msg.rendered_content is not None
            # The content of the message has changed since the event for original_url has been created,
            # it should not be rendered. Another, up-to-date event will have been sent (edited_url).
            self.assertNotIn(
                f'<a href="{original_url}" title="The Rock">The Rock</a>', msg.rendered_content
            )

            self.assertTrue(responses.assert_call_count(edited_url, 0))

            with self.settings(TEST_SUITE=False), self.assertLogs(level="INFO") as info_logs:
                # Now proceed with the original queue_json_publish_rollback_unsafe
                # and call the up-to-date event for edited_url.
                queue_json_publish_rollback_unsafe(*args, **kwargs)
                msg = Message.objects.select_related("sender").get(id=msg_id)
                assert msg.rendered_content is not None
                self.assertIn(
                    f'<a href="{edited_url}" title="The Rock">The Rock</a>',
                    msg.rendered_content,
                )
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://edited.org/: "
                in info_logs.output[0]
            )

        with mock_queue_publish(
            "zerver.actions.message_edit.queue_event_on_commit", wraps=wrapped_queue_event_on_commit
        ):
            result = self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "content": edited_url,
                },
            )
            self.assert_json_success(result)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_message_deleted(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(user, "Denmark", topic_name="foo", content=url)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        msg = Message.objects.select_related("sender").get(id=msg_id)
        do_delete_messages(msg.realm, [msg], acting_user=None)

        # We do still fetch the URL, as we don't want to incur the
        # cost of locking the row while we do the HTTP fetches.
        self.create_mock_response(url)
        with self.settings(TEST_SUITE=False), self.assertLogs(level="INFO") as info_logs:
            # Run the queue processor. This will simulate the event for original_url being
            # processed after the message has been deleted.
            FetchLinksEmbedData().consume(event)
        self.assertTrue(
            "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
            in info_logs.output[0]
        )

    def test_mentions_preserved(self) -> None:
        # Updating the message with the preview content should be sure
        # to preserve the mention data.
        msg = self._send_message_with_test_org_url(
            sender=self.example_user("hamlet"),
            other_content=" @**Cordelia, Lear's daughter** mention",
        )
        self.assertEqual(
            int(
                UserMessage.objects.get(message=msg, user_profile=self.example_user("hamlet")).flags
            ),
            int(UserMessage.flags.read | UserMessage.flags.is_private),
        )
        self.assertEqual(
            int(
                UserMessage.objects.get(
                    message=msg, user_profile=self.example_user("cordelia")
                ).flags
            ),
            int(UserMessage.flags.mentioned | UserMessage.flags.is_private),
        )

        msg = self._send_message_with_test_org_url(
            sender=self.example_user("hamlet"), other_content=" @*hamletcharacters* mention"
        )
        self.assertEqual(
            int(
                UserMessage.objects.get(message=msg, user_profile=self.example_user("hamlet")).flags
            ),
            int(
                UserMessage.flags.mentioned | UserMessage.flags.read | UserMessage.flags.is_private
            ),
        )
        self.assertEqual(
            int(
                UserMessage.objects.get(
                    message=msg, user_profile=self.example_user("cordelia")
                ).flags
            ),
            int(UserMessage.flags.mentioned | UserMessage.flags.is_private),
        )

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_topic_wildcard_mention_preserved(self) -> None:
        url = "http://test.org/"
        cache_delete(preview_url_cache_key(url))
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Denmark")
        self.subscribe(cordelia, "Denmark")
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(
                hamlet,
                "Denmark",
                topic_name="test",
                content=url + " @**topic**",
            )
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        # Hamlet sent the message, so he is a topic participant.
        self.assertEqual(
            int(UserMessage.objects.get(message_id=msg_id, user_profile=hamlet).flags),
            int(UserMessage.flags.topic_wildcard_mentioned | UserMessage.flags.read),
        )
        # Cordelia is not a participant in the topic
        self.assertEqual(
            int(UserMessage.objects.get(message_id=msg_id, user_profile=cordelia).flags),
            0,
        )

        self.create_mock_response(url)
        with self.settings(TEST_SUITE=False), self.assertLogs(level="INFO") as info_logs:
            FetchLinksEmbedData().consume(event)
        self.assertTrue(
            "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
            in info_logs.output[0]
        )

        # The topic wildcard mention flag must be preserved.
        self.assertEqual(
            int(UserMessage.objects.get(message_id=msg_id, user_profile=hamlet).flags),
            int(UserMessage.flags.topic_wildcard_mentioned | UserMessage.flags.read),
        )
        self.assertEqual(
            int(UserMessage.objects.get(message_id=msg_id, user_profile=cordelia).flags),
            0,
        )

        # Test the topic wildcard mention flag is preserved when editing a message as well.
        msg_id = self.send_stream_message(
            cordelia, "Denmark", topic_name="test", content=" @**topic**"
        )
        # Both Hamlet and Cordelia are topic participants.
        self.assertEqual(
            int(UserMessage.objects.get(message_id=msg_id, user_profile=hamlet).flags),
            int(UserMessage.flags.topic_wildcard_mentioned),
        )
        self.assertEqual(
            int(UserMessage.objects.get(message_id=msg_id, user_profile=cordelia).flags),
            int(UserMessage.flags.topic_wildcard_mentioned | UserMessage.flags.read),
        )

        self.login("cordelia")
        with mock_queue_publish("zerver.actions.message_edit.queue_event_on_commit") as patched:
            result = self.client_patch(
                "/json/messages/" + str(msg_id),
                {
                    "content": url + " @**topic**",
                },
            )
            self.assert_json_success(result)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        self.create_mock_response(url)
        with self.settings(TEST_SUITE=False), self.assertLogs(level="INFO") as info_logs:
            FetchLinksEmbedData().consume(event)
        self.assertTrue(
            "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
            in info_logs.output[0]
        )

        # The topic wildcard mention flag must be preserved.
        self.assertEqual(
            int(UserMessage.objects.get(message_id=msg_id, user_profile=hamlet).flags),
            int(UserMessage.flags.topic_wildcard_mentioned),
        )
        self.assertEqual(
            int(UserMessage.objects.get(message_id=msg_id, user_profile=cordelia).flags),
            int(UserMessage.flags.topic_wildcard_mentioned | UserMessage.flags.read),
        )

    def test_get_link_embed_data(self) -> None:
        url = "http://test.org/"
        embedded_link = f'<a href="{url}" title="The Rock">The Rock</a>'

        # When humans send, we should get embedded content.
        msg = self._send_message_with_test_org_url(sender=self.example_user("hamlet"))
        self.assertIn(embedded_link, msg.rendered_content)

        # We don't want embedded content for bots.
        msg = self._send_message_with_test_org_url(
            sender=self.example_user("webhook_bot"), queue_should_run=False
        )
        self.assertNotIn(embedded_link, msg.rendered_content)

        # Try another human to make sure bot failure was due to the
        # bot sending the message and not some other reason.
        msg = self._send_message_with_test_org_url(sender=self.example_user("prospero"))
        self.assertIn(embedded_link, msg.rendered_content)

    @override_settings(CAMO_URI="")
    def test_inline_url_embed_preview(self) -> None:
        with_preview = '<p><a href="http://test.org/">http://test.org/</a></p>\n<div class="message_embed"><a class="message_embed_image" href="http://test.org/" style="background-image: url(&quot;http://ia.media-imdb.com/images/rock.jpg&quot;)"></a><div class="data-container"><div class="message_embed_title"><a href="http://test.org/" title="The Rock">The Rock</a></div><div class="message_embed_description">Description text</div></div></div>'
        without_preview = '<p><a href="http://test.org/">http://test.org/</a></p>'
        msg = self._send_message_with_test_org_url(sender=self.example_user("hamlet"))
        self.assertEqual(msg.rendered_content, with_preview)

        realm = msg.get_realm()
        realm.inline_url_embed_preview = False
        realm.save()

        msg = self._send_message_with_test_org_url(
            sender=self.example_user("prospero"), queue_should_run=False
        )
        self.assertEqual(msg.rendered_content, without_preview)

    def test_inline_url_embed_preview_with_camo(self) -> None:
        camo_url = get_camo_url("http://ia.media-imdb.com/images/rock.jpg")
        with_preview = (
            '<p><a href="http://test.org/">http://test.org/</a></p>\n<div class="message_embed"><a class="message_embed_image" href="http://test.org/" style="background-image: url(&quot;'
            + camo_url
            + '&quot;)"></a><div class="data-container"><div class="message_embed_title"><a href="http://test.org/" title="The Rock">The Rock</a></div><div class="message_embed_description">Description text</div></div></div>'
        )
        msg = self._send_message_with_test_org_url(sender=self.example_user("hamlet"))
        self.assertEqual(msg.rendered_content, with_preview)

    @responses.activate
    @override_settings(CAMO_URI="")
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_link_preview_css_escaping_image(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(user, "Denmark", topic_name="foo", content=url)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        # Swap the URL out for one with characters that need CSS escaping
        html = re.sub(r"rock\.jpg", r"rock.jpg\\", self.open_graph_html)
        self.create_mock_response(url, body=html)
        with self.settings(TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
                in info_logs.output[0]
            )

        msg = Message.objects.select_related("sender").get(id=msg_id)
        with_preview = (
            '<p><a href="http://test.org/">http://test.org/</a></p>\n'
            '<div class="message_embed"><a class="message_embed_image" href="http://test.org/"'
            ' style="background-image:'
            ' url(&quot;http://ia.media-imdb.com/images/rock.jpg\\\\&quot;)"></a><div'
            ' class="data-container"><div class="message_embed_title"><a href="http://test.org/"'
            ' title="The Rock">The Rock</a></div><div class="message_embed_description">Description'
            " text</div></div></div>"
        )
        self.assertEqual(
            with_preview,
            msg.rendered_content,
        )

    @override_settings(CAMO_URI="")
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_inline_relative_url_embed_preview(self) -> None:
        # Relative URLs should not be sent for URL preview.
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            self.send_personal_message(
                self.example_user("prospero"),
                self.example_user("cordelia"),
                content="http://zulip.testserver/api/",
            )
            patched.assert_not_called()

    @override_settings(CAMO_URI="")
    def test_inline_url_embed_preview_with_relative_image_url(self) -> None:
        with_preview_relative = '<p><a href="http://test.org/">http://test.org/</a></p>\n<div class="message_embed"><a class="message_embed_image" href="http://test.org/" style="background-image: url(&quot;http://test.org/images/rock.jpg&quot;)"></a><div class="data-container"><div class="message_embed_title"><a href="http://test.org/" title="The Rock">The Rock</a></div><div class="message_embed_description">Description text</div></div></div>'
        # Try case where the Open Graph image is a relative URL.
        msg = self._send_message_with_test_org_url(
            sender=self.example_user("prospero"), relative_url=True
        )
        self.assertEqual(msg.rendered_content, with_preview_relative)

    @responses.activate
    def test_http_error_get_data(self) -> None:
        url = "http://test.org/"
        msg_id = self.send_personal_message(
            self.example_user("hamlet"),
            self.example_user("cordelia"),
            content=url,
        )
        msg = Message.objects.select_related("sender").get(id=msg_id)
        event = {
            "message_id": msg_id,
            "urls": [url],
            "message_realm_id": msg.sender.realm_id,
            "message_content": url,
        }

        self.create_mock_response(url, body=ConnectionError())

        with self.settings(INLINE_URL_EMBED_PREVIEW=True, TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
                in info_logs.output[0]
            )

        msg = Message.objects.get(id=msg_id)
        self.assertEqual(
            '<p><a href="http://test.org/">http://test.org/</a></p>', msg.rendered_content
        )

    def test_invalid_link(self) -> None:
        with self.settings(INLINE_URL_EMBED_PREVIEW=True, TEST_SUITE=False):
            self.assertIsNone(get_link_embed_data("com.notvalidlink"))
            self.assertIsNone(get_link_embed_data("μένει.com.notvalidlink"))

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_link_preview_non_html_data(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/audio.mp3"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(user, "Denmark", topic_name="foo", content=url)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        content_type = "application/octet-stream"
        self.create_mock_response(url, content_type=content_type)

        with self.settings(TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
                cached_data = cache_get(preview_url_cache_key(url))[0]
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/audio.mp3: "
                in info_logs.output[0]
            )

        self.assertIsNone(cached_data)
        msg = Message.objects.select_related("sender").get(id=msg_id)
        self.assertEqual(
            '<p><a href="http://test.org/audio.mp3">http://test.org/audio.mp3</a></p>',
            msg.rendered_content,
        )

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_link_preview_no_open_graph_image(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/foo.html"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(user, "Denmark", topic_name="foo", content=url)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        # HTML without the og:image metadata
        html = "\n".join(
            line for line in self.open_graph_html.splitlines() if "og:image" not in line
        )
        self.create_mock_response(url, body=html)
        with self.settings(TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
                cached_data = cache_get(preview_url_cache_key(url))[0]
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/foo.html: "
                in info_logs.output[0]
            )

        assert cached_data is not None
        self.assertIsNotNone(cached_data.title)
        self.assertIsNone(cached_data.image)
        msg = Message.objects.select_related("sender").get(id=msg_id)
        self.assertEqual(
            '<p><a href="http://test.org/foo.html">http://test.org/foo.html</a></p>',
            msg.rendered_content,
        )

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_link_preview_open_graph_image_bad_url(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/foo.html"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(user, "Denmark", topic_name="foo", content=url)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        # HTML with a bad og:image metadata
        html = "\n".join(
            (
                line
                if "og:image" not in line
                else '<meta property="og:image" content="http://[bad url/" />'
            )
            for line in self.open_graph_html.splitlines()
        )
        self.create_mock_response(url, body=html)
        with self.settings(TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
                cached_data = cache_get(preview_url_cache_key(url))[0]
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/foo.html: "
                in info_logs.output[0]
            )

        assert cached_data is not None
        self.assertIsNotNone(cached_data.title)
        self.assertIsNone(cached_data.image)
        msg = Message.objects.select_related("sender").get(id=msg_id)
        self.assertEqual(
            '<p><a href="http://test.org/foo.html">http://test.org/foo.html</a></p>',
            msg.rendered_content,
        )

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_link_preview_open_graph_image_missing_content(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/foo.html"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(user, "Denmark", topic_name="foo", content=url)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        # HTML without the og:image metadata
        html = "\n".join(
            line if "og:image" not in line else '<meta property="og:image"/>'
            for line in self.open_graph_html.splitlines()
        )
        self.create_mock_response(url, body=html)
        with self.settings(TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
                cached_data = cache_get(preview_url_cache_key(url))[0]
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/foo.html: "
                in info_logs.output[0]
            )

        assert cached_data is not None
        self.assertIsNotNone(cached_data.title)
        self.assertIsNone(cached_data.image)
        msg = Message.objects.select_related("sender").get(id=msg_id)
        self.assertEqual(
            '<p><a href="http://test.org/foo.html">http://test.org/foo.html</a></p>',
            msg.rendered_content,
        )

    @responses.activate
    @override_settings(CAMO_URI="")
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_link_preview_no_content_type_header(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(user, "Denmark", topic_name="foo", content=url)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        self.create_mock_response(url)
        with self.settings(TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
                cached_data = cache_get(preview_url_cache_key(url))[0]
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
                in info_logs.output[0]
            )

        assert cached_data is not None
        msg = Message.objects.select_related("sender").get(id=msg_id)
        assert msg.rendered_content is not None
        self.assertIn(cached_data.title, msg.rendered_content)
        assert cached_data.image is not None
        self.assertIn(cached_data.image, msg.rendered_content)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_valid_content_type_error_get_data(self) -> None:
        url = "http://test.org/"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit"):
            msg_id = self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("cordelia"),
                content=url,
            )
        msg = Message.objects.select_related("sender").get(id=msg_id)
        event = {
            "message_id": msg_id,
            "urls": [url],
            "message_realm_id": msg.sender.realm_id,
            "message_content": url,
        }

        self.create_mock_response(url, body=ConnectionError())

        with (
            mock.patch(
                "zerver.lib.url_preview.preview.get_oembed_data",
                side_effect=lambda *args, **kwargs: None,
            ),
            mock.patch(
                "zerver.lib.url_preview.preview.valid_content_type", side_effect=lambda k: True
            ),
            self.settings(TEST_SUITE=False),
        ):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
                in info_logs.output[0]
            )

            # This did not get cached -- hence the lack of [0] on the cache_get
            cached_data = cache_get(preview_url_cache_key(url))
            self.assertIsNone(cached_data)

        msg.refresh_from_db()
        self.assertEqual(
            '<p><a href="http://test.org/">http://test.org/</a></p>', msg.rendered_content
        )

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_invalid_url(self) -> None:
        url = "http://test.org/"
        error_url = "http://test.org/x"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit"):
            msg_id = self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("cordelia"),
                content=error_url,
            )
        msg = Message.objects.select_related("sender").get(id=msg_id)
        event = {
            "message_id": msg_id,
            "urls": [error_url],
            "message_realm_id": msg.sender.realm_id,
            "message_content": error_url,
        }

        self.create_mock_response(error_url, status=404)
        with self.settings(TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/x: "
                in info_logs.output[0]
            )

            # FIXME: Should we really cache this, especially without cache invalidation?
            cached_data = cache_get(preview_url_cache_key(error_url))[0]

        self.assertIsNone(cached_data)
        msg.refresh_from_db()
        self.assertEqual(
            '<p><a href="http://test.org/x">http://test.org/x</a></p>', msg.rendered_content
        )
        self.assertTrue(responses.assert_call_count(url, 0))

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_safe_oembed_html_url(self) -> None:
        url = "http://test.org/"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit"):
            msg_id = self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("cordelia"),
                content=url,
            )
        msg = Message.objects.select_related("sender").get(id=msg_id)
        event = {
            "message_id": msg_id,
            "urls": [url],
            "message_realm_id": msg.sender.realm_id,
            "message_content": url,
        }

        mocked_data = UrlOEmbedData(
            html=f'<iframe src="{url}"></iframe>',
            type="video",
            image=f"{url}/image.png",
        )
        self.create_mock_response(url)
        with self.settings(TEST_SUITE=False):
            with (
                self.assertLogs(level="INFO") as info_logs,
                mock.patch(
                    "zerver.lib.url_preview.preview.get_oembed_data",
                    lambda *args, **kwargs: mocked_data,
                ),
            ):
                FetchLinksEmbedData().consume(event)
                cached_data = cache_get(preview_url_cache_key(url))[0]
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/: "
                in info_logs.output[0]
            )

        self.assertEqual(cached_data, mocked_data)
        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertIn(f'a data-id="{escape(mocked_data.html)}"', msg.rendered_content)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_youtube_url_title_replaces_url(self) -> None:
        url = "https://www.youtube.com/watch?v=eSJTXC7Ixgg"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit"):
            msg_id = self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("cordelia"),
                content=url,
            )
        msg = Message.objects.select_related("sender").get(id=msg_id)
        event = {
            "message_id": msg_id,
            "urls": [url],
            "message_realm_id": msg.sender.realm_id,
            "message_content": url,
        }

        mocked_data = UrlEmbedData(
            title="Clearer Code at Scale - Static Types at Zulip and Dropbox"
        )
        self.create_mock_response(url)
        with self.settings(TEST_SUITE=False):
            with (
                self.assertLogs(level="INFO") as info_logs,
                mock.patch(
                    "zerver.worker.embed_links.url_preview.get_link_embed_data",
                    lambda *args, **kwargs: mocked_data,
                ),
            ):
                FetchLinksEmbedData().consume(event)
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for https://www.youtube.com/watch?v=eSJTXC7Ixgg:"
                in info_logs.output[0]
            )

        msg.refresh_from_db()
        expected_content = f"""<p><a href="https://www.youtube.com/watch?v=eSJTXC7Ixgg">YouTube - Clearer Code at Scale - Static Types at Zulip and Dropbox</a></p>\n<div class="youtube-video message_inline_image"><a data-id="eSJTXC7Ixgg" href="https://www.youtube.com/watch?v=eSJTXC7Ixgg"><img src="{get_camo_url("https://i.ytimg.com/vi/eSJTXC7Ixgg/mqdefault.jpg")}"></a></div>"""
        self.assertEqual(expected_content, msg.rendered_content)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_custom_title_replaces_youtube_url_title(self) -> None:
        url = "[YouTube link](https://www.youtube.com/watch?v=eSJTXC7Ixgg)"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit"):
            msg_id = self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("cordelia"),
                content=url,
            )
        msg = Message.objects.select_related("sender").get(id=msg_id)
        event = {
            "message_id": msg_id,
            "urls": [url],
            "message_realm_id": msg.sender.realm_id,
            "message_content": url,
        }

        mocked_data = UrlEmbedData(
            title="Clearer Code at Scale - Static Types at Zulip and Dropbox"
        )
        self.create_mock_response(url)
        with self.settings(TEST_SUITE=False):
            with (
                self.assertLogs(level="INFO") as info_logs,
                mock.patch(
                    "zerver.worker.embed_links.url_preview.get_link_embed_data",
                    lambda *args, **kwargs: mocked_data,
                ),
            ):
                FetchLinksEmbedData().consume(event)
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for [YouTube link](https://www.youtube.com/watch?v=eSJTXC7Ixgg):"
                in info_logs.output[0]
            )

        msg.refresh_from_db()
        expected_content = f"""<p><a href="https://www.youtube.com/watch?v=eSJTXC7Ixgg">YouTube link</a></p>\n<div class="youtube-video message_inline_image"><a data-id="eSJTXC7Ixgg" href="https://www.youtube.com/watch?v=eSJTXC7Ixgg"><img src="{get_camo_url("https://i.ytimg.com/vi/eSJTXC7Ixgg/mqdefault.jpg")}"></a></div>"""
        self.assertEqual(expected_content, msg.rendered_content)


@override_settings(INLINE_URL_EMBED_PREVIEW=True)
class RemoveLinkPreviewTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        Realm.objects.all().update(inline_url_embed_preview=True)

    def _send_and_embed_urls(self, user: UserProfile, urls: list[str]) -> Message:
        """Send a message linking each URL, and process the embed worker."""
        for url in urls:
            # Clear any cached data so the mock responses are actually fetched.
            cache_delete(preview_url_cache_key(url))
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(
                user, "Denmark", topic_name="test", content="\n".join(urls)
            )
            patched.assert_called_once()
            event = patched.call_args[0][1]

        for url in urls:
            PreviewTestCase.create_mock_response(url)
        with self.settings(TEST_SUITE=False), self.assertLogs(level="INFO"):
            FetchLinksEmbedData().consume(event)

        return Message.objects.select_related("sender").get(id=msg_id)

    def _send_and_embed_url(self, user: UserProfile, url: str) -> Message:
        return self._send_and_embed_urls(user, [url])

    def _remove_previews(
        self, message_id: int, urls: list[str], op: str = "remove"
    ) -> "TestHttpResponse":
        return self.client_patch(
            f"/json/messages/{message_id}/link_previews",
            {"op": op, "urls": orjson.dumps(urls).decode()},
        )

    @responses.activate
    def test_remove_preview_suppresses_embed(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"

        msg = self._send_and_embed_url(user, url)
        assert msg.rendered_content is not None
        self.assertIn("message_embed", msg.rendered_content)
        self.assertEqual(msg.removed_preview_urls, [])

        # Removing a preview is a rendering update rather than a content
        # edit, so clients are notified with rendering_only set.
        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self._remove_previews(msg.id, [url])
            self.assert_json_success(result)
        self.assertEqual(events[0]["event"]["type"], "update_message")
        self.assertTrue(events[0]["event"]["rendering_only"])
        self.assertIsNone(events[0]["event"]["user_id"])

        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertNotIn("message_embed", msg.rendered_content)
        self.assertIn(url, msg.rendered_content)
        self.assertEqual(msg.removed_preview_urls, [url])

        # The message's content and edit history are untouched.
        self.assertEqual(msg.content, url)
        self.assertIsNone(msg.edit_history)

    @responses.activate
    def test_remove_preview_is_idempotent(self) -> None:
        """Removing the same URL twice should not create duplicates."""
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"

        msg = self._send_and_embed_url(user, url)
        self.assert_json_success(self._remove_previews(msg.id, [url]))

        # Removing an already-removed preview is a no-op: it changes nothing
        # and emits no message-update event.
        with self.capture_send_event_calls(expected_num_events=0):
            self.assert_json_success(self._remove_previews(msg.id, [url]))

        msg.refresh_from_db()
        self.assertEqual(msg.removed_preview_urls, [url])

    @responses.activate
    def test_remove_multiple_previews_in_one_request(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url1 = "http://test.org/"
        url2 = "http://other.org/"

        msg = self._send_and_embed_urls(user, [url1, url2])
        assert msg.rendered_content is not None
        self.assertEqual(msg.rendered_content.count('class="message_embed"'), 2)

        # A URL repeated in one request is stored once.
        with self.capture_send_event_calls(expected_num_events=1):
            self.assert_json_success(self._remove_previews(msg.id, [url1, url2, url1]))

        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertNotIn("message_embed", msg.rendered_content)
        self.assertEqual(msg.removed_preview_urls, [url1, url2])

    @responses.activate
    def test_remove_preview_skips_validating_already_removed_urls(self) -> None:
        """A URL whose preview is already removed is not re-validated, so a
        client removing several previews at once does not fail on one it
        removed earlier -- even if that URL can no longer be previewed."""
        user = self.example_user("hamlet")
        self.login_user(user)
        url1 = "http://test.org/"
        url2 = "http://other.org/"

        msg = self._send_and_embed_urls(user, [url1, url2])
        self.assert_json_success(self._remove_previews(msg.id, [url1]))

        # Edit the message so url1 is no longer a link at all.
        result = self.client_patch(f"/json/messages/{msg.id}", {"content": f"`{url1}` {url2}"})
        self.assert_json_success(result)

        self.assert_json_success(self._remove_previews(msg.id, [url1, url2]))
        msg.refresh_from_db()
        self.assertEqual(msg.removed_preview_urls, [url1, url2])

    @responses.activate
    def test_remove_preview_rejects_request_atomically(self) -> None:
        """If any requested URL has no preview, the whole request fails and
        no preview is removed."""
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"

        msg = self._send_and_embed_url(user, url)
        result = self._remove_previews(msg.id, [url, "http://not-in-message.org/"])
        self.assert_json_error(
            result, "URL does not have a link preview: http://not-in-message.org/"
        )

        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertEqual(msg.removed_preview_urls, [])
        self.assertIn("message_embed", msg.rendered_content)

    @responses.activate
    def test_remove_preview_permission_non_sender(self) -> None:
        """A user who cannot edit the message cannot remove its previews."""
        sender = self.example_user("hamlet")
        other_user = self.example_user("cordelia")
        self.login_user(sender)
        url = "http://test.org/"

        msg = self._send_and_embed_url(sender, url)

        self.login_user(other_user)
        result = self._remove_previews(msg.id, [url])
        self.assert_json_error(result, "You don't have permission to edit this message")

    @responses.activate
    def test_remove_preview_with_message_editing_disabled(self) -> None:
        """Removing a preview requires the permission to edit the message's
        content, so it is refused when editing is turned off."""
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"

        msg = self._send_and_embed_url(user, url)
        do_set_realm_property(user.realm, "allow_message_editing", False, acting_user=None)

        result = self._remove_previews(msg.id, [url])
        self.assert_json_error(result, "Your organization has turned off message editing")

        msg.refresh_from_db()
        self.assertEqual(msg.removed_preview_urls, [])

    @responses.activate
    def test_embed_worker_respects_removed_urls(self) -> None:
        """The embed worker must not restore a removed preview, even when
        handed a (possibly stale) event that still lists the removed URL."""
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"

        msg = self._send_and_embed_url(user, url)
        assert msg.rendered_content is not None
        self.assertIn("message_embed", msg.rendered_content)

        self.assert_json_success(self._remove_previews(msg.id, [url]))
        msg.refresh_from_db()
        self.assertNotIn("message_embed", msg.rendered_content)

        # The renderer consults removed_preview_urls directly, so even an
        # embed event that still lists the removed URL does not restore it.
        event = {
            "message_id": msg.id,
            "message_content": msg.content,
            "message_realm_id": msg.realm_id,
            "urls": [url],
        }
        PreviewTestCase.create_mock_response(url)
        with self.settings(TEST_SUITE=False), self.assertLogs(level="INFO"):
            FetchLinksEmbedData().consume(event)

        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertNotIn("message_embed", msg.rendered_content)

    @responses.activate
    def test_content_edit_preserves_removed_inline_image(self) -> None:
        """A removed inline image must stay removed after a content edit.

        Inline image/video previews never pass through the embed worker, so
        the renderer must skip removed URLs itself -- otherwise they reappear
        on edit.
        """
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "https://example.com/photo.jpg"

        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit"):
            msg_id = self.send_stream_message(user, "Denmark", topic_name="test", content=url)

        msg = Message.objects.select_related("sender").get(id=msg_id)
        assert msg.rendered_content is not None
        self.assertIn("message_inline_image", msg.rendered_content)

        self.assert_json_success(self._remove_previews(msg.id, [url]))
        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertNotIn("message_inline_image", msg.rendered_content)

        # Editing the message content must not restore the removed image.
        result = self.client_patch(
            f"/json/messages/{msg.id}",
            {"content": f"{url} updated text"},
        )
        self.assert_json_success(result)

        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertNotIn("message_inline_image", msg.rendered_content)
        self.assertIn(url, msg.rendered_content)

    @responses.activate
    def test_remove_preview_reuses_cached_sibling_embeds(self) -> None:
        """Removing one preview reuses the cached embed data of the others, so
        they stay inline and are not re-fetched by the embed worker."""
        user = self.example_user("hamlet")
        self.login_user(user)
        url1 = "http://test.org/"
        url2 = "http://other.org/"

        msg = self._send_and_embed_urls(user, [url1, url2])
        assert msg.rendered_content is not None
        self.assertEqual(msg.rendered_content.count('class="message_embed"'), 2)

        # Both URLs' embed data is warm in the cache. Removing url1's preview
        # should keep url2's embed inline and NOT re-queue it.
        with mock_queue_publish("zerver.actions.message_edit.queue_event_on_commit") as patched:
            self.assert_json_success(self._remove_previews(msg.id, [url1]))
            patched.assert_not_called()

        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertEqual(msg.rendered_content.count('class="message_embed"'), 1)
        self.assertIn(url2, msg.rendered_content)

    @responses.activate
    def test_remove_preview_requeue_keeps_cached_previews(self) -> None:
        """The embed worker re-renders the message with only the URLs it was
        given, so the re-queue has to list every preview the message still
        has -- not just the ones that missed the cache."""
        user = self.example_user("hamlet")
        self.login_user(user)
        url1 = "http://test.org/"
        url2 = "http://other.org/"
        url3 = "http://third.org/"

        msg = self._send_and_embed_urls(user, [url1, url2, url3])
        assert msg.rendered_content is not None
        self.assertEqual(msg.rendered_content.count('class="message_embed"'), 3)

        # url3 has no cached embed data, so removing url1 leaves url2's
        # preview inline from the cache and re-queues url3.
        cache_delete(preview_url_cache_key(url3))
        with mock_queue_publish("zerver.actions.message_edit.queue_event_on_commit") as patched:
            self.assert_json_success(self._remove_previews(msg.id, [url1]))
            patched.assert_called_once()
            requeue_event = patched.call_args[0][1]
        self.assertNotIn(url1, requeue_event["urls"])

        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertEqual(msg.rendered_content.count('class="message_embed"'), 1)

        PreviewTestCase.create_mock_response(url3)
        with self.settings(TEST_SUITE=False), self.assertLogs(level="INFO"):
            FetchLinksEmbedData().consume(requeue_event)

        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertEqual(msg.rendered_content.count('class="message_embed"'), 2)
        self.assertIn(url2, msg.rendered_content)
        self.assertIn(url3, msg.rendered_content)

    def test_remove_preview_requires_previews_enabled(self) -> None:
        """A link has no preview to remove when the organization does not
        generate one for it."""
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"

        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit"):
            msg_id = self.send_stream_message(user, "Denmark", topic_name="test", content=url)

        do_set_realm_property(user.realm, "inline_url_embed_preview", False, acting_user=None)
        with self.capture_send_event_calls(expected_num_events=0):
            result = self._remove_previews(msg_id, [url])
        self.assert_json_error(result, f"URL does not have a link preview: {url}")

        # With image previews off too, nothing is previewed at all, and the
        # request is rejected without rendering the message.
        do_set_realm_property(user.realm, "inline_image_preview", False, acting_user=None)
        result = self._remove_previews(msg_id, [url])
        self.assert_json_error(result, f"URL does not have a link preview: {url}")

        msg = Message.objects.get(id=msg_id)
        self.assertEqual(msg.removed_preview_urls, [])

    def test_remove_preview_rejects_uploaded_file(self) -> None:
        """An uploaded file's preview is message content rather than a
        generated link preview, so it cannot be removed."""
        user = self.example_user("hamlet")
        self.login_user(user)
        path_id = self.upload_and_thumbnail_image("img.png")
        # An upload linked with the realm's own URL renders as a relative
        # path; over https on an http realm it stays absolute, which is the
        # form a client can name.
        upload_url = f"https://zulip.testserver/user_uploads/{path_id}"

        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit"):
            msg_id = self.send_stream_message(
                user, "Denmark", topic_name="test", content=upload_url
            )

        msg = Message.objects.get(id=msg_id)
        assert msg.rendered_content is not None
        self.assertIn("message_inline_image", msg.rendered_content)
        self.assertIn(upload_url, msg.rendered_content)

        result = self._remove_previews(msg_id, [upload_url])
        self.assert_json_error(result, f"URL does not have a link preview: {upload_url}")

        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertEqual(msg.removed_preview_urls, [])
        self.assertIn("message_inline_image", msg.rendered_content)

    def test_remove_preview_requires_a_url(self) -> None:
        """A preview is named by its URL, so anything that is not one -- such
        as the relative path an upload is rendered with -- is rejected."""
        user = self.example_user("hamlet")
        self.login_user(user)
        msg_id = self.send_stream_message(user, "Denmark", topic_name="test", content="hello")

        result = self._remove_previews(msg_id, ["user_uploads/2/ab/cd/img.png"])
        self.assert_json_error(result, "Invalid urls[0]: Value error, Not a URL")

    def test_remove_preview_url_must_be_a_previewable_link(self) -> None:
        """A URL that is only a substring of a real link, or appears only in
        a code block, has no preview and must be rejected rather than stored."""
        user = self.example_user("hamlet")
        self.login_user(user)
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit"):
            # The real link is the full URL; `http://example.com/` is just a
            # substring of it, and the code-span URL is not a link at all.
            msg_id = self.send_stream_message(
                user,
                "Denmark",
                topic_name="test",
                content="http://example.com/article and `http://test.org/`",
            )

        for url in ["http://example.com/", "http://test.org/"]:
            result = self._remove_previews(msg_id, [url])
            self.assert_json_error(result, f"URL does not have a link preview: {url}")

        msg = Message.objects.get(id=msg_id)
        self.assertEqual(msg.removed_preview_urls, [])

        # The whole link is previewable, even though its website preview is
        # fetched asynchronously and has not arrived yet.
        self.assert_json_success(self._remove_previews(msg_id, ["http://example.com/article"]))
        msg.refresh_from_db()
        self.assertEqual(msg.removed_preview_urls, ["http://example.com/article"])

    def test_remove_preview_url_with_rewritten_source(self) -> None:
        """Previews whose rendered link is a rewritten form of the message
        URL (Wikipedia File: correction, Dropbox media) can still be removed,
        even though the client sends the rewritten URL, not the original."""
        user = self.example_user("hamlet")
        self.login_user(user)
        cases = [
            (
                "https://en.wikipedia.org/wiki/File:Example.jpg",
                "https://en.wikipedia.org/wiki/Special:FilePath/File:Example.jpg",
            ),
            (
                "https://www.dropbox.com/scl/fi/abc123/photo.jpg",
                "https://www.dropbox.com/scl/fi/abc123/photo.jpg?raw=1",
            ),
        ]
        for original, rendered_url in cases:
            with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit"):
                msg_id = self.send_stream_message(
                    user, "Denmark", topic_name="test", content=original
                )
            msg = Message.objects.get(id=msg_id)
            assert msg.rendered_content is not None
            self.assertIn("message_inline_image", msg.rendered_content)
            # The preview links to the rewritten URL, which is what the
            # client sends back to remove it.
            self.assertIn(rendered_url, msg.rendered_content)

            self.assert_json_success(self._remove_previews(msg.id, [rendered_url]))
            msg.refresh_from_db()
            assert msg.rendered_content is not None
            self.assertNotIn("message_inline_image", msg.rendered_content)

    def test_remove_preview_on_dm_skips_content_edit_checks(self) -> None:
        """Removing a preview is not a content edit, so it must not re-run
        content-edit validation. In a direct message that mentions a group
        the sender can no longer mention, removing an unrelated preview must
        still succeed rather than failing the group-mention check."""
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        self.login_user(cordelia)

        leadership = check_add_user_group(
            cordelia.realm, "leadership", [cordelia], acting_user=cordelia
        )
        url = "https://example.com/photo.jpg"
        msg_id = self.send_personal_message(cordelia, hamlet, f"@*leadership* {url}")

        msg = Message.objects.select_related("sender").get(id=msg_id)
        assert msg.rendered_content is not None
        self.assertIn("message_inline_image", msg.rendered_content)

        # Restrict the group so cordelia may no longer mention it. A real
        # content edit would now be rejected, but removing a preview must not.
        moderators = NamedUserGroup.objects.get(
            realm_for_sharding=cordelia.realm,
            name=SystemGroups.MODERATORS,
            is_system_group=True,
        )
        leadership.can_mention_group = moderators
        leadership.save()

        self.assert_json_success(self._remove_previews(msg.id, [url]))

        msg.refresh_from_db()
        assert msg.rendered_content is not None
        self.assertNotIn("message_inline_image", msg.rendered_content)
        self.assertEqual(msg.removed_preview_urls, [url])
