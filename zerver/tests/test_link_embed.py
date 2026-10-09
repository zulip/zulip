import re
from collections import OrderedDict
from collections.abc import Mapping
from typing import Any, TypeAlias
from unittest import mock
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
import responses
from django.test import override_settings
from django.utils.html import escape
from pyoembed.providers import get_provider
from requests.exceptions import ConnectionError
from typing_extensions import override

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_send import render_unsaved_message
from zerver.actions.realm_settings import do_set_realm_property
from zerver.lib.cache import (
    cache_delete,
    cache_get,
    cache_set,
    latest_preview_draft_cache_key,
    pending_preview_draft_cache_key,
    preview_draft_content_hash,
    preview_url_cache_key,
    preview_url_unavailable_cache_key,
)
from zerver.lib.camo import get_camo_url
from zerver.lib.queue import queue_json_publish_rollback_unsafe
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish
from zerver.lib.url_preview.oembed import get_oembed_data, strip_cdata
from zerver.lib.url_preview.parsers import GenericParser, OpenGraphParser
from zerver.lib.url_preview.preview import get_link_embed_data, mark_preview_url_unavailable
from zerver.lib.url_preview.types import UrlEmbedData, UrlOEmbedData
from zerver.models import Message, Realm, UserMessage, UserProfile
from zerver.worker.embed_links import FetchLinksEmbedData


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


# Queue jobs, like events, are untyped JSON.
UrlEmbedDataJob: TypeAlias = dict[str, Any]


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

    def render_populating_url_embed_data(self, content: str) -> tuple[str, UrlEmbedDataJob | None]:
        with mock_queue_publish(
            "zerver.actions.message_send.queue_event_on_commit"
        ) as mock_queue_event_on_commit:
            result = self.client_post(
                "/json/messages/render", {"content": content, "populate_url_embed_data": "true"}
            )
        rendered = self.assert_json_success(result)["rendered"]
        if not mock_queue_event_on_commit.called:
            return rendered, None
        mock_queue_event_on_commit.assert_called_once()
        self.assertEqual(mock_queue_event_on_commit.call_args[0][0], "embed_links")
        return rendered, mock_queue_event_on_commit.call_args[0][1]

    def consume_url_embed_data_job(
        self, job: UrlEmbedDataJob, expected_num_events: int
    ) -> list[Mapping[str, Any]]:
        with (
            self.assertLogs(level="INFO") as info_logs,
            self.capture_send_event_calls(expected_num_events=expected_num_events) as events,
        ):
            FetchLinksEmbedData().consume(job)
        for output in info_logs.output:
            self.assertTrue(output.startswith("INFO:root:Time spent on get_link_embed_data for "))
        return events

    def consume_dropped_url_embed_data_job(self, job: UrlEmbedDataJob) -> None:
        with self.capture_send_event_calls(expected_num_events=0):
            FetchLinksEmbedData().consume(job)
        self.assert_length(responses.calls, 0)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_render_without_populate_url_embed_data(self) -> None:
        self.login("hamlet")
        url = "http://test.org/"
        self.create_mock_response(url)
        get_link_embed_data(url)
        result = self.client_post("/json/messages/render", {"content": url})
        rendered = self.assert_json_success(result)["rendered"]
        self.assertNotIn(f'<a href="{url}" title="The Rock">The Rock</a>', rendered)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_with_website_previews_disabled(self) -> None:
        user = self.example_user("hamlet")
        do_set_realm_property(user.realm, "inline_url_embed_preview", False, acting_user=None)
        self.login_user(user)
        url = "http://test.org/"
        self.create_mock_response(url)
        get_link_embed_data(url)
        rendered, job = self.render_populating_url_embed_data(f"{url} http://example.com/")
        self.assertNotIn(f'<a href="{url}" title="The Rock">The Rock</a>', rendered)
        self.assertIsNone(job)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_for_bot(self) -> None:
        url = "http://test.org/"
        self.create_mock_response(url)
        get_link_embed_data(url)
        with mock_queue_publish(
            "zerver.actions.message_send.queue_event_on_commit"
        ) as mock_queue_event_on_commit:
            result = self.api_post(
                self.example_user("default_bot"),
                "/api/v1/messages/render",
                {"content": f"{url} http://example.com/", "populate_url_embed_data": "true"},
            )
        rendered = self.assert_json_success(result)["rendered"]
        self.assertNotIn(f'<a href="{url}" title="The Rock">The Rock</a>', rendered)
        mock_queue_event_on_commit.assert_not_called()

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_bakes_in_cached_embed(self) -> None:
        self.login("hamlet")
        url = "http://test.org/"
        self.create_mock_response(url)
        get_link_embed_data(url)

        rendered, job = self.render_populating_url_embed_data(url)
        self.assertIn(f'<a href="{url}" title="The Rock">The Rock</a>', rendered)
        self.assertIsNone(job)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_skips_second_render_for_link_without_preview(self) -> None:
        self.login("hamlet")
        url = "http://test.org/"
        cache_set(preview_url_cache_key(url), None)

        with mock.patch(
            "zerver.views.message_send.render_unsaved_message", wraps=render_unsaved_message
        ) as mock_render:
            _rendered, job = self.render_populating_url_embed_data(url)
        self.assertIsNone(job)
        mock_render.assert_called_once()

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_mixed_cached_and_uncached_links(self) -> None:
        self.login("hamlet")
        cached_url = "http://test.org/"
        uncached_url = "http://example.com/"
        self.create_mock_response(cached_url)
        get_link_embed_data(cached_url)

        rendered, job = self.render_populating_url_embed_data(f"{cached_url} {uncached_url}")
        self.assertIn(f'<a href="{cached_url}" title="The Rock">The Rock</a>', rendered)
        self.assertNotIn(f'<a href="{uncached_url}" title="The Rock">The Rock</a>', rendered)
        assert job is not None
        self.assertEqual(job["cached_urls"], [cached_url])
        self.assertEqual(job["urls"], [uncached_url])

        self.create_mock_response(uncached_url)
        events = self.consume_url_embed_data_job(job, expected_num_events=1)
        rendered_content = events[0]["event"]["rendered_content"]
        self.assertIn(f'<a href="{cached_url}" title="The Rock">The Rock</a>', rendered_content)
        self.assertIn(f'<a href="{uncached_url}" title="The Rock">The Rock</a>', rendered_content)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_render_without_populate_url_embed_data_queues_nothing(self) -> None:
        self.login("hamlet")
        with mock_queue_publish(
            "zerver.actions.message_send.queue_event_on_commit"
        ) as mock_queue_event_on_commit:
            result = self.client_post("/json/messages/render", {"content": "http://test.org/"})
        self.assert_json_success(result)
        mock_queue_event_on_commit.assert_not_called()

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"
        embedded_link = f'<a href="{url}" title="The Rock">The Rock</a>'

        rendered, job = self.render_populating_url_embed_data(url)
        self.assertNotIn(embedded_link, rendered)
        self.assertEqual(
            job,
            {
                "type": "url_embed_data",
                "user_id": user.id,
                "content": url,
                "cached_urls": [],
                "urls": [url],
            },
        )
        pending_cache_key = pending_preview_draft_cache_key(
            user.id, preview_draft_content_hash(url)
        )
        self.assertIsNotNone(cache_get(pending_cache_key))

        self.create_mock_response(url)
        assert job is not None
        events = self.consume_url_embed_data_job(job, expected_num_events=1)
        self.assertEqual(events[0]["users"], [user.id])
        self.assertEqual(events[0]["event"]["type"], "url_embed_data")
        self.assertEqual(events[0]["event"]["content"], url)
        self.assertIn(embedded_link, events[0]["event"]["rendered_content"])
        self.assertIsNone(cache_get(pending_cache_key))

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_queues_one_job_per_draft(self) -> None:
        self.login("hamlet")
        url = "http://test.org/"
        _rendered, job = self.render_populating_url_embed_data(url)
        self.assertIsNotNone(job)

        _rendered, job = self.render_populating_url_embed_data(url)
        self.assertIsNone(job)

        # The queued job renders the pre-edit draft, which the client
        # discards, so the edited draft needs a job of its own.
        _rendered, job = self.render_populating_url_embed_data(f"{url} edited")
        assert job is not None
        self.assertEqual(job["content"], f"{url} edited")

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_queues_job_for_each_user(self) -> None:
        url = "http://test.org/"
        self.login("hamlet")
        _rendered, job = self.render_populating_url_embed_data(url)
        self.assertIsNotNone(job)

        othello = self.example_user("othello")
        self.login_user(othello)
        _rendered, job = self.render_populating_url_embed_data(url)
        assert job is not None
        self.assertEqual(job["user_id"], othello.id)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_link_without_preview(self) -> None:
        """
        A page that doesn't exist yet has no preview. Previews skip it for a
        while, but that isn't cached for good, so once the page is published,
        the sent message still gets its card.
        """
        self.login("hamlet")
        url = "http://test.org/"
        _rendered, job = self.render_populating_url_embed_data(url)
        assert job is not None

        self.create_mock_response(url, status=404)
        self.consume_url_embed_data_job(job, expected_num_events=0)

        self.assertIsNotNone(cache_get(preview_url_unavailable_cache_key(url)))
        _rendered, job = self.render_populating_url_embed_data(f"{url} edited")
        self.assertIsNone(job)

        self.assertIsNone(cache_get(preview_url_cache_key(url)))
        responses.reset()
        self.create_mock_response(url)
        with mock_queue_publish(
            "zerver.actions.message_send.queue_event_on_commit"
        ) as mock_queue_event_on_commit:
            msg_id = self.send_stream_message(self.example_user("hamlet"), "Denmark", content=url)
        with self.assertLogs(level="INFO"):
            FetchLinksEmbedData().consume(mock_queue_event_on_commit.call_args[0][1])
        msg = Message.objects.get(id=msg_id)
        assert msg.rendered_content is not None
        self.assertIn(f'<a href="{url}" title="The Rock">The Rock</a>', msg.rendered_content)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_link_whose_fetch_fails(self) -> None:
        self.login("hamlet")
        failed_url = "http://test.org/"
        _rendered, job = self.render_populating_url_embed_data(failed_url)
        assert job is not None

        self.create_mock_response(failed_url, body=ConnectionError())
        self.consume_url_embed_data_job(job, expected_num_events=0)
        self.assertIsNone(cache_get(preview_url_cache_key(failed_url)))
        self.assertIsNotNone(cache_get(preview_url_unavailable_cache_key(failed_url)))

        _rendered, job = self.render_populating_url_embed_data(f"{failed_url} edited")
        self.assertIsNone(job)

        fresh_url = "http://example.com/"
        _rendered, job = self.render_populating_url_embed_data(f"{failed_url} {fresh_url}")
        assert job is not None
        self.assertEqual(job["cached_urls"], [])
        self.assertEqual(job["urls"], [fresh_url])

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_link_whose_fetch_raises(self) -> None:
        """
        Unlike a network error, an unexpected error aborts the job. The link
        that raised is then skipped, while the link the job didn't get to is
        queued again on the next preview.
        """
        self.login("hamlet")
        urls = ["http://test.org/", "http://example.com/"]
        content = " ".join(urls)
        _rendered, job = self.render_populating_url_embed_data(content)
        assert job is not None

        for url in urls:
            responses.add(responses.GET, url, body=ValueError("unexpected"))
        with self.assertRaises(ValueError):
            FetchLinksEmbedData().consume(job)
        [raised_url] = {call.request.url for call in responses.calls}
        assert raised_url is not None
        self.assertIsNotNone(cache_get(preview_url_unavailable_cache_key(raised_url)))

        _rendered, job = self.render_populating_url_embed_data(content)
        assert job is not None
        self.assertEqual(job["urls"], [url for url in urls if url != raised_url])

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_skips_link_found_unavailable_while_queued(self) -> None:
        """
        Another job, such as another user's, found nothing for the link while
        this job waited in the queue, so this job doesn't fetch it.
        """
        self.login("hamlet")
        url = "http://test.org/"
        _rendered, job = self.render_populating_url_embed_data(url)
        assert job is not None
        mark_preview_url_unavailable(url)
        self.consume_dropped_url_embed_data_job(job)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_only_cached_links_have_embeds(self) -> None:
        self.login("hamlet")
        cached_url = "http://test.org/"
        uncached_url = "http://test.org/audio.mp3"
        self.create_mock_response(cached_url)
        get_link_embed_data(cached_url)

        _rendered, job = self.render_populating_url_embed_data(f"{cached_url} {uncached_url}")
        assert job is not None
        self.create_mock_response(uncached_url, content_type="application/octet-stream")
        self.consume_url_embed_data_job(job, expected_num_events=0)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_link_without_embed_image(self) -> None:
        """
        A page with preview data but no image renders no card, so there is
        nothing new to send; its data is cached, as for a sent message.
        """
        self.login("hamlet")
        url = "http://test.org/"
        _rendered, job = self.render_populating_url_embed_data(url)
        assert job is not None
        html = "\n".join(
            line for line in self.open_graph_html.splitlines() if "og:image" not in line
        )
        self.create_mock_response(url, body=html)
        self.consume_url_embed_data_job(job, expected_num_events=0)
        self.assertIsNotNone(cache_get(preview_url_cache_key(url)))
        self.assertIsNone(cache_get(preview_url_unavailable_cache_key(url)))

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_refetches_evicted_cached_link(self) -> None:
        """
        A cached link evicted before the job ran is fetched again, so that
        the event doesn't drop the card the preview already shows.
        """
        self.login("hamlet")
        cached_url = "http://test.org/"
        uncached_url = "http://example.com/"
        self.create_mock_response(cached_url)
        get_link_embed_data(cached_url)
        _rendered, job = self.render_populating_url_embed_data(f"{cached_url} {uncached_url}")
        assert job is not None

        cache_delete(preview_url_cache_key(cached_url))
        self.create_mock_response(uncached_url)
        events = self.consume_url_embed_data_job(job, expected_num_events=1)
        rendered_content = events[0]["event"]["rendered_content"]
        self.assertIn(f'<a href="{cached_url}" title="The Rock">The Rock</a>', rendered_content)
        self.assertIn(f'<a href="{uncached_url}" title="The Rock">The Rock</a>', rendered_content)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_for_draft_replaced_by_one_without_links(self) -> None:
        self.login("hamlet")
        _rendered, job = self.render_populating_url_embed_data("http://test.org/")
        assert job is not None
        _rendered, no_job = self.render_populating_url_embed_data("no links")
        self.assertIsNone(no_job)
        self.consume_dropped_url_embed_data_job(job)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_superseded_job_skips_evicted_cached_link(self) -> None:
        """
        A job whose draft has been replaced makes no requests, not even to
        refetch a cached link that was evicted before the job ran.
        """
        self.login("hamlet")
        cached_url = "http://test.org/"
        self.create_mock_response(cached_url)
        get_link_embed_data(cached_url)
        _rendered, job = self.render_populating_url_embed_data(f"{cached_url} http://example.com/")
        assert job is not None

        cache_delete(preview_url_cache_key(cached_url))
        self.render_populating_url_embed_data("edited")
        responses.reset()
        self.consume_dropped_url_embed_data_job(job)

    @responses.activate
    def test_populate_url_embed_data_for_deleted_user(self) -> None:
        url = "http://test.org/"
        job = {
            "type": "url_embed_data",
            "user_id": 1234567890,
            "content": url,
            "cached_urls": [],
            "urls": [url],
        }
        self.consume_dropped_url_embed_data_job(job)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_for_draft_returned_to(self) -> None:
        # Going back to a draft whose job is still queued makes it current
        # again, so that job is the one worth fetching for.
        self.login("hamlet")
        url = "http://test.org/"
        _rendered, original_job = self.render_populating_url_embed_data(url)
        _rendered, edited_job = self.render_populating_url_embed_data(f"{url} edited")
        assert original_job is not None
        assert edited_job is not None

        _rendered, job = self.render_populating_url_embed_data(url)
        self.assertIsNone(job)

        self.consume_dropped_url_embed_data_job(edited_job)

        self.create_mock_response(url)
        events = self.consume_url_embed_data_job(original_job, expected_num_events=1)
        self.assertEqual(events[0]["event"]["content"], url)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_requeues_draft_whose_job_was_dropped(self) -> None:
        # Dropping a job leaves its links uncached, so returning to that draft
        # has to be able to queue another one.
        self.login("hamlet")
        url = "http://test.org/"
        _rendered, superseded_job = self.render_populating_url_embed_data(url)
        self.render_populating_url_embed_data(f"{url} edited")
        assert superseded_job is not None
        self.consume_dropped_url_embed_data_job(superseded_job)

        _rendered, job = self.render_populating_url_embed_data(url)
        self.assertIsNotNone(job)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_drops_job_whose_draft_expired(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        _rendered, job = self.render_populating_url_embed_data("http://test.org/")
        assert job is not None
        cache_delete(latest_preview_draft_cache_key(user.id))
        self.consume_dropped_url_embed_data_job(job)

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_for_draft_replaced_during_fetch(self) -> None:
        """
        The draft is replaced while the job fetches its only link, so no event
        is sent, though the fetched data stays cached for the next preview.
        """
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/"
        _rendered, job = self.render_populating_url_embed_data(url)
        assert job is not None

        def replace_draft_and_respond(
            request: requests.PreparedRequest,
        ) -> tuple[int, dict[str, str], str]:
            cache_set(
                latest_preview_draft_cache_key(user.id),
                preview_draft_content_hash(f"{url} edited"),
            )
            return (200, {"Content-Type": "text/html"}, self.open_graph_html)

        responses.add_callback(responses.GET, url, callback=replace_draft_and_respond)
        self.consume_url_embed_data_job(job, expected_num_events=0)
        self.assertIsNotNone(cache_get(preview_url_cache_key(url)))

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_populate_url_embed_data_stops_fetching_for_replaced_draft(self) -> None:
        """
        The draft is replaced while the job fetches its first link, as if the
        user edited it meanwhile, so the job stops before fetching the second.
        """
        user = self.example_user("hamlet")
        self.login_user(user)
        content = "http://test.org/ http://example.com/"
        _rendered, job = self.render_populating_url_embed_data(content)
        assert job is not None

        def replace_draft_and_respond(
            request: requests.PreparedRequest,
        ) -> tuple[int, dict[str, str], str]:
            cache_set(
                latest_preview_draft_cache_key(user.id),
                preview_draft_content_hash(f"{content} edited"),
            )
            return (200, {"Content-Type": "text/html"}, self.open_graph_html)

        for url in job["urls"]:
            responses.add_callback(responses.GET, url, callback=replace_draft_and_respond)
        self.consume_url_embed_data_job(job, expected_num_events=0)
        self.assertEqual(
            {call.request.url for call in responses.calls},
            {job["urls"][0]},
        )

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
            '<p><a href="http://test.org/foo.html">http://test.org/foo.html</a></p>\n'
            '<div class="message_embed"><div class="data-container">'
            '<div class="message_embed_title">'
            '<a href="http://test.org/foo.html" title="The Rock">The Rock</a></div>'
            '<div class="message_embed_description">Description text</div>'
            "</div></div>",
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
            '<p><a href="http://test.org/foo.html">http://test.org/foo.html</a></p>\n'
            '<div class="message_embed"><div class="data-container">'
            '<div class="message_embed_title">'
            '<a href="http://test.org/foo.html" title="The Rock">The Rock</a></div>'
            '<div class="message_embed_description">Description text</div>'
            "</div></div>",
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
            '<p><a href="http://test.org/foo.html">http://test.org/foo.html</a></p>\n'
            '<div class="message_embed"><div class="data-container">'
            '<div class="message_embed_title">'
            '<a href="http://test.org/foo.html" title="The Rock">The Rock</a></div>'
            '<div class="message_embed_description">Description text</div>'
            "</div></div>",
            msg.rendered_content,
        )

    @responses.activate
    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_link_preview_no_metadata(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        url = "http://test.org/foo.html"
        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            msg_id = self.send_stream_message(user, "Denmark", topic_name="foo", content=url)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        # HTML with no useful metadata at all.
        html = "<html><head></head><body></body></html>"
        self.create_mock_response(url, body=html)
        with self.settings(TEST_SUITE=False):
            with self.assertLogs(level="INFO") as info_logs:
                FetchLinksEmbedData().consume(event)
            self.assertTrue(
                "INFO:root:Time spent on get_link_embed_data for http://test.org/foo.html: "
                in info_logs.output[0]
            )

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
