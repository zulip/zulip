import re
from collections import OrderedDict
from typing import Any, cast
from unittest import mock
from urllib.parse import urlencode

import responses
from django.test import override_settings
from django.utils.html import escape
from requests.exceptions import ConnectionError
from typing_extensions import override

from zerver.actions.message_delete import do_delete_messages
from zerver.lib.cache import cache_delete, cache_get, preview_url_cache_key
from zerver.lib.camo import get_camo_url
from zerver.lib.queue import queue_json_publish_rollback_unsafe
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish
from zerver.lib.url_preview.oembed import (
    compile_oembed_providers,
    get_oembed_data,
    get_oembed_endpoint,
    scheme_to_regex,
    strip_cdata,
)
from zerver.lib.url_preview.parsers import GenericParser, OpenGraphParser
from zerver.lib.url_preview.preview import get_link_embed_data
from zerver.lib.url_preview.types import UrlEmbedData, UrlOEmbedData
from zerver.models import Message, Realm, UserMessage, UserProfile
from zerver.worker.embed_links import FetchLinksEmbedData


def get_oembed_api_url(endpoint: str, url: str, maxwidth: int = 640, maxheight: int = 480) -> str:
    # Build the oEmbed API URL for a given endpoint and content URL.
    query_params = OrderedDict()
    query_params["url"] = url
    query_params["maxwidth"] = str(maxwidth)
    query_params["maxheight"] = str(maxheight)

    return endpoint + "?" + urlencode(query_params, True)


@override_settings(INLINE_URL_EMBED_PREVIEW=True)
class OembedTestCase(ZulipTestCase):
    @responses.activate
    def test_unsupported_resource_type(self) -> None:
        response_data = {
            "type": "rich",
            "title": "NASA",
            "html": "<p>test</p>",
            "version": "1.0",
            "width": 658,
            "height": 400,
        }
        url = "https://www.youtube.com/watch?v=BLtI2WdAymy"
        api_url = get_oembed_api_url("https://www.youtube.com/oembed", url)
        responses.add(responses.GET, api_url, json=response_data, status=200)

        data = get_oembed_data(url)
        assert data is not None
        self.assertIsInstance(data, UrlEmbedData)
        self.assertEqual(data.title, "NASA")

    @responses.activate
    def test_supported_photo_and_video_resource_types(self) -> None:
        test_cases: list[dict[str, Any]] = [
            {
                "name": "photo",
                "url": "https://www.flickr.com/photos/bees/2341623661/",
                "response_data": {
                    "type": "photo",
                    "url": "https://live.staticflickr.com/3123/2341623661_7c99f48bbf_b.jpg",
                    "thumbnail_width": 640,
                    "thumbnail_height": 426,
                    "title": "Flickr Test Image",
                    "version": "1.0",
                    "width": 658,
                    "height": 400,
                },
                "expected_title": "Flickr Test Image",
                "expected_type": "photo",
                "expected_image": "https://live.staticflickr.com/3123/2341623661_7c99f48bbf_b.jpg",
                "expected_html": None,
            },
            {
                "name": "video",
                "url": "https://vimeo.com/158727223",
                "response_data": {
                    "type": "video",
                    "thumbnail_url": "https://i.vimeocdn.com/video/590587169-640x360.jpg",
                    "thumbnail_width": 480,
                    "thumbnail_height": 360,
                    "title": "Vimeo Test Video",
                    "html": '<![CDATA[<iframe src="https://player.vimeo.com/video/158727223" width="480" height="270" frameborder="0"></iframe>]]>',
                    "version": "1.0",
                    "width": 480,
                    "height": 270,
                },
                "expected_title": "Vimeo Test Video",
                "expected_type": "video",
                "expected_image": "https://i.vimeocdn.com/video/590587169-640x360.jpg",
                "expected_html": '<iframe src="https://player.vimeo.com/video/158727223" width="480" height="270" frameborder="0"></iframe>',
            },
        ]

        for case in test_cases:
            with self.subTest(case_name=case["name"]):
                responses.reset()
                url = cast(str, case["url"])
                response_data = cast(dict[str, Any], case["response_data"])
                expected_type = cast(str, case["expected_type"])
                expected_title = cast(str, case["expected_title"])
                expected_image = cast(str, case["expected_image"])
                expected_html = cast(str | None, case["expected_html"])

                endpoint = get_oembed_endpoint(url)
                assert endpoint is not None
                api_url = get_oembed_api_url(endpoint, url)
                responses.add(responses.GET, api_url, json=response_data, status=200)

                data = get_oembed_data(url)
                assert data is not None
                self.assertIsInstance(data, UrlOEmbedData)
                self.assertEqual(data.type, expected_type)
                self.assertEqual(data.title, expected_title)
                self.assertEqual(data.image, expected_image)
                self.assertEqual(data.html, expected_html)

    @responses.activate
    def test_request_error_responses(self) -> None:
        url = "https://www.youtube.com/watch?v=BLtI2WdAymy"
        api_url = get_oembed_api_url("https://www.youtube.com/oembed", url)

        error_cases: list[tuple[str, dict[str, Any]]] = [
            ("connection_error", {"body": ConnectionError()}),
            ("status_400", {"status": 400}),
            ("status_500", {"status": 500}),
            (
                "invalid_json",
                {
                    "body": "{invalid json}",
                    "content_type": "application/json",
                    "status": 200,
                },
            ),
        ]

        for case_name, response_kwargs in error_cases:
            with self.subTest(case_name=case_name):
                responses.reset()
                responses.add(responses.GET, api_url, **response_kwargs)
                data = get_oembed_data(url)
                self.assertIsNone(data)

    @responses.activate
    def test_oembed_html(self) -> None:
        html = '<iframe src="//www.instagram.com/embed.js"></iframe>'
        stripped_html = strip_cdata(html)
        self.assertEqual(html, stripped_html)

    def test_autodiscovered_oembed_xml_format_html(self) -> None:
        iframe_content = '<iframe src="https://w.soundcloud.com/player"></iframe>'
        html = f"<![CDATA[{iframe_content}]]>"
        stripped_html = strip_cdata(html)
        self.assertEqual(iframe_content, stripped_html)

    def test_scheme_to_regex(self) -> None:
        test_cases: list[dict[str, Any]] = [
            {
                "name": "wildcard_subdomain",
                "scheme": "https://*.youtube.com/watch*",
                "match_urls": [
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
                    "https://youtube.com/watch?v=dQw4w9WgXcQ",
                    "http://youtube.com/watch?v=dQw4w9WgXcQ",
                ],
                "non_match_urls": ["https://youtube.com/v/dQw4w9WgXcQ"],
            },
            {
                "name": "literal_plus_in_query",
                "scheme": "https://example.com/watch?v=*&list=+",
                "match_urls": ["https://example.com/watch?v=abc&list=+"],
                "non_match_urls": ["https://example.com/watch?v=abc&list=something"],
            },
            {
                "name": "anchors_non_wildcard_path",
                "scheme": "https://example.com/watch",
                "match_urls": ["https://example.com/watch", "http://example.com/watch"],
                "non_match_urls": ["https://example.com/watch/extra"],
            },
        ]

        for case in test_cases:
            with self.subTest(case_name=case["name"]):
                regex = scheme_to_regex(cast(str, case["scheme"]))
                for url in cast(list[str], case["match_urls"]):
                    self.assertIsNotNone(re.match(regex, url))
                for url in cast(list[str], case["non_match_urls"]):
                    self.assertIsNone(re.match(regex, url))

        wildcard_regex = scheme_to_regex("https://*.youtube.com/watch*")
        self.assertIsNotNone(
            re.match(wildcard_regex, "HTTPS://M.YOUTUBE.COM/WATCH?v=dQw4w9WgXcQ", re.IGNORECASE)
        )

    def test_oembed_endpoint_with_existing_query_param(self) -> None:
        # hearthis.at's endpoint already contains ?format=json.
        # Verify that session.get(endpoint, params=params) appends additional
        # parameters with & instead of ?, producing a valid URL.
        endpoint = get_oembed_endpoint("https://hearthis.at/some-artist/some-track/")
        assert endpoint is not None
        self.assertIn("?", endpoint)

        url = "https://hearthis.at/some-artist/some-track/"
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "https://hearthis.at/oembed/",
                json={"type": "rich", "title": "Test Track", "version": "1.0"},
                status=200,
            )
            get_oembed_data(url)
            self.assert_length(rsps.calls, 1)
            called_url = rsps.calls[0].request.url
            assert called_url is not None
            self.assertEqual(called_url.count("?"), 1)
            self.assertIn("url=", called_url)
            self.assertIn("maxwidth=", called_url)

    def test_unknown_provider_returns_none(self) -> None:
        url = "https://unknown-site.example.com/page"
        data = get_oembed_data(url)
        self.assertIsNone(data)

    def test_compile_oembed_providers_missing_endpoint(self) -> None:
        mock_providers: list[dict[str, Any]] = [
            {
                "provider_name": "TestProvider",
                "endpoints": [
                    {
                        "schemes": [
                            "https://*.example.com/watch*",
                            "https://example.com/watch?v=*&list=+",
                        ],
                        "url": "https://example.com/oembed",
                    }
                ],
            },
            {"provider_name": "MissingEndpoints"},
            {
                "provider_name": "MissingSchemes",
                "endpoints": [{"url": "https://invalid.example.com/oembed"}],
            },
            {
                "provider_name": "MissingEndpointUrl",
                "endpoints": [{"schemes": ["https://missing-url.example.com/*"]}],
            },
        ]

        endpoint_map = compile_oembed_providers(mock_providers)
        self.assert_length(endpoint_map, 1)
        [(compiled_regex, endpoint_url)] = endpoint_map.items()
        self.assertEqual(endpoint_url, "https://example.com/oembed")

        regex_match_cases = [
            ("https://www.example.com/watch?v=123", True),
            ("https://example.com/watch?v=123&list=+", True),
            ("https://example.com/v/123", False),
        ]
        for url, should_match in regex_match_cases:
            with self.subTest(url=url):
                self.assertEqual(compiled_regex.match(url) is not None, should_match)

    def test_compile_oembed_providers_format_and_http_normalization(self) -> None:
        mock_providers: list[dict[str, Any]] = [
            {
                "provider_name": "FormatAndSchemeVariants",
                "endpoints": [
                    {
                        "schemes": ["https://example.com/watch/*"],
                        "url": "https://example.com/oembed.{format}",
                    }
                ],
            }
        ]

        mock_map = compile_oembed_providers(mock_providers)

        with mock.patch("zerver.lib.url_preview.oembed.OEMBED_ENDPOINT_MAP", mock_map):
            test_cases = [
                ("https://example.com/watch/123", "https://example.com/oembed.json"),
                ("http://example.com/watch/123", "https://example.com/oembed.json"),
            ]
            for url, expected_endpoint in test_cases:
                with self.subTest(url=url):
                    self.assertEqual(get_oembed_endpoint(url), expected_endpoint)

    def test_compile_oembed_providers_wildcard_matches_bare_domain(self) -> None:
        mock_providers: list[dict[str, Any]] = [
            {
                "provider_name": "WildcardSubdomain",
                "endpoints": [
                    {
                        "schemes": ["https://*.example.com/watch/*"],
                        "url": "https://example.com/oembed",
                    }
                ],
            }
        ]

        mock_map = compile_oembed_providers(mock_providers)

        with mock.patch("zerver.lib.url_preview.oembed.OEMBED_ENDPOINT_MAP", mock_map):
            self.assertEqual(
                get_oembed_endpoint("https://media.example.com/watch/123"),
                "https://example.com/oembed",
            )
            self.assertEqual(
                get_oembed_endpoint("https://example.com/watch/123"),
                "https://example.com/oembed",
            )

    def test_get_oembed_endpoint_provider_matches(self) -> None:
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/oembed"),
            ("http://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/oembed"),
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/oembed"),
            ("https://youtu.be/dQw4w9WgXcQ", "https://www.youtube.com/oembed"),
            ("https://www.youtube.com/v/dQw4w9WgXcQ", "https://www.youtube.com/oembed"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "https://www.youtube.com/oembed"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "https://www.youtube.com/oembed"),
            ("https://vimeo.com/123456789", "https://vimeo.com/api/oembed.json"),
            ("http://vimeo.com/123456789", "https://vimeo.com/api/oembed.json"),
            ("https://open.spotify.com/track/abc123", "https://open.spotify.com/oembed"),
            ("http://open.spotify.com/track/abc123", "https://open.spotify.com/oembed"),
            ("https://soundcloud.com/artist/track", "https://soundcloud.com/oembed"),
            ("http://soundcloud.com/artist/track", "https://soundcloud.com/oembed"),
        ]
        for url, expected_endpoint in test_cases:
            with self.subTest(url=url):
                self.assertEqual(get_oembed_endpoint(url), expected_endpoint)

    def test_get_oembed_endpoint_matches_first_provider(self) -> None:
        # When two providers match the same URL, the first one registered is preferred.
        mock_providers: list[dict[str, Any]] = [
            {
                "provider_name": "GenericProvider",
                "endpoints": [
                    {
                        "schemes": ["https://example.com/*"],
                        "url": "https://generic.example.com/oembed",
                    }
                ],
            },
            {
                "provider_name": "SpecificProvider",
                "endpoints": [
                    {
                        "schemes": ["https://example.com/video/*"],
                        "url": "https://specific.example.com/oembed",
                    }
                ],
            },
        ]

        mock_map = compile_oembed_providers(mock_providers)

        with mock.patch("zerver.lib.url_preview.oembed.OEMBED_ENDPOINT_MAP", mock_map):
            self.assertEqual(
                get_oembed_endpoint("https://example.com/video/123"),
                "https://generic.example.com/oembed",
            )

    def test_get_oembed_endpoint_skips_malformed_provider(self) -> None:
        mock_providers: list[dict[str, Any]] = [
            {"provider_name": "MissingEndpoints"},
            {
                "provider_name": "MissingSchemes",
                "endpoints": [{"url": "https://invalid.example.com/oembed"}],
            },
            {
                "provider_name": "EmptySchemes",
                "endpoints": [{"schemes": [], "url": "https://invalid.example.com/oembed"}],
            },
            {
                "provider_name": "Valid",
                "endpoints": [
                    {
                        "schemes": ["https://example.com/video/*"],
                        "url": "https://specific.example.com/oembed",
                    }
                ],
            },
        ]

        mock_map = compile_oembed_providers(mock_providers)

        with mock.patch("zerver.lib.url_preview.oembed.OEMBED_ENDPOINT_MAP", mock_map):
            self.assertEqual(
                get_oembed_endpoint("https://example.com/video/123"),
                "https://specific.example.com/oembed",
            )


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
