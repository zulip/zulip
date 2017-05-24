# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
import ujson
from typing import Any
from requests.exceptions import ConnectionError
from django.test import override_settings

from zerver.models import Recipient, Message
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import MockPythonResponse
from zerver.worker.queue_processors import FetchLinksEmbedData
from zerver.lib.url_preview.preview import get_link_embed_data
from zerver.lib.url_preview.oembed import get_oembed_data
from zerver.lib.url_preview.parsers import (
    OpenGraphParser, GenericParser)


TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'default',
    },
    'database': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'url-preview',
    }
}

@override_settings(INLINE_URL_EMBED_PREVIEW=True)
class OembedTestCase(ZulipTestCase):
    @mock.patch('pyoembed.requests.get')
    def test_present_provider(self, get):
        # type: (Any) -> None
        get.return_value = response = mock.Mock()
        response.headers = {'content-type': 'application/json'}
        response.ok = True
        response_data = {
            'type': 'rich',
            'thumbnail_url': 'https://scontent.cdninstagram.com/t51.2885-15/n.jpg',
            'thumbnail_width': 640,
            'thumbnail_height': 426,
            'title': 'NASA',
            'html': '<p>test</p>',
            'version': '1.0',
            'width': 658,
            'height': None}
        response.text = ujson.dumps(response_data)
        url = 'http://instagram.com/p/BLtI2WdAymy'
        data = get_oembed_data(url)
        self.assertIsInstance(data, dict)
        self.assertIn('title', data)
        self.assertEqual(data['title'], response_data['title'])

    @mock.patch('pyoembed.requests.get')
    def test_error_request(self, get):
        # type: (Any) -> None
        get.return_value = response = mock.Mock()
        response.ok = False
        url = 'http://instagram.com/p/BLtI2WdAymy'
        data = get_oembed_data(url)
        self.assertIsNone(data)


class OpenGraphParserTestCase(ZulipTestCase):
    def test_page_with_og(self):
        # type: () -> None
        html = """<html>
          <head>
          <meta property="og:title" content="The Rock" />
          <meta property="og:type" content="video.movie" />
          <meta property="og:url" content="http://www.imdb.com/title/tt0117500/" />
          <meta property="og:image" content="http://ia.media-imdb.com/images/rock.jpg" />
          <meta property="og:description" content="The Rock film" />
          </head>
        </html>"""

        parser = OpenGraphParser(html)
        result = parser.extract_data()
        self.assertIn('title', result)
        self.assertEqual(result['title'], 'The Rock')
        self.assertEqual(result.get('description'), 'The Rock film')


class GenericParserTestCase(ZulipTestCase):
    def test_parser(self):
        # type: () -> None
        html = """
          <html>
            <head><title>Test title</title></head>
            <body>
                <h1>Main header</h1>
                <p>Description text</p>
            </body>
          </html>
        """
        parser = GenericParser(html)
        result = parser.extract_data()
        self.assertEqual(result.get('title'), 'Test title')
        self.assertEqual(result.get('description'), 'Description text')

    def test_extract_image(self):
        # type: () -> None
        html = """
          <html>
            <body>
                <h1>Main header</h1>
                <img src="http://test.com/test.jpg">
                <div>
                    <p>Description text</p>
                </div>
            </body>
          </html>
        """
        parser = GenericParser(html)
        result = parser.extract_data()
        self.assertEqual(result.get('title'), 'Main header')
        self.assertEqual(result.get('description'), 'Description text')
        self.assertEqual(result.get('image'), 'http://test.com/test.jpg')

    def test_extract_description(self):
        # type: () -> None
        html = """
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
        parser = GenericParser(html)
        result = parser.extract_data()
        self.assertEqual(result.get('description'), 'Description text')

        html = """
          <html>
            <head><meta name="description" content="description 123"</head>
            <body></body>
          </html>
        """
        parser = GenericParser(html)
        result = parser.extract_data()
        self.assertEqual(result.get('description'), 'description 123')

        html = "<html><body></body></html>"
        parser = GenericParser(html)
        result = parser.extract_data()
        self.assertIsNone(result.get('description'))


class PreviewTestCase(ZulipTestCase):
    open_graph_html = """
          <html>
            <head>
                <title>Test title</title>
                <meta property="og:title" content="The Rock" />
                <meta property="og:type" content="video.movie" />
                <meta property="og:url" content="http://www.imdb.com/title/tt0117500/" />
                <meta property="og:image" content="http://ia.media-imdb.com/images/rock.jpg" />
            </head>
            <body>
                <h1>Main header</h1>
                <p>Description text</p>
            </body>
          </html>
        """

    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def test_edit_message_history(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)
        msg_id = self.send_message(email, "Scotland", Recipient.STREAM,
                                   subject="editing", content="original")

        url = 'http://test.org/'
        response = MockPythonResponse(self.open_graph_html, 200)
        mocked_response = mock.Mock(
            side_effect=lambda k: {url: response}.get(k, MockPythonResponse('', 404)))

        with mock.patch('zerver.views.messages.queue_json_publish') as patched:
            result = self.client_patch("/json/messages/" + str(msg_id), {
                'message_id': msg_id, 'content': url,
            })
            self.assert_json_success(result)
            patched.assert_called_once()
            queue = patched.call_args[0][0]
            self.assertEqual(queue, "embed_links")
            event = patched.call_args[0][1]

        with self.settings(TEST_SUITE=False, CACHES=TEST_CACHES):
            with mock.patch('requests.get', mocked_response):
                FetchLinksEmbedData().consume(event)

        embedded_link = '<a href="{0}" target="_blank" title="The Rock">The Rock</a>'.format(url)
        msg = Message.objects.select_related("sender").get(id=msg_id)
        self.assertIn(embedded_link, msg.rendered_content)

    @override_settings(INLINE_URL_EMBED_PREVIEW=True)
    def _send_message_with_test_org_url(self, sender_email, queue_should_run=True, relative_url=False):
        # type: (str, bool, bool) -> Message
        url = 'http://test.org/'
        with mock.patch('zerver.lib.actions.queue_json_publish') as patched:
            msg_id = self.send_message(
                sender_email, self.example_email('cordelia'),
                Recipient.PERSONAL, subject="url", content=url)
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
        self.assertNotIn(
            '<a href="{0}" target="_blank" title="The Rock">The Rock</a>'.format(url),
            msg.rendered_content)

        # Mock the network request result so the test can be fast without Internet
        response = MockPythonResponse(self.open_graph_html, 200)
        if relative_url is True:
            response = MockPythonResponse(self.open_graph_html.replace('http://ia.media-imdb.com', ''), 200)
        mocked_response = mock.Mock(
            side_effect=lambda k: {url: response}.get(k, MockPythonResponse('', 404)))

        # Run the queue processor to potentially rerender things
        with self.settings(TEST_SUITE=False, CACHES=TEST_CACHES):
            with mock.patch('requests.get', mocked_response):
                FetchLinksEmbedData().consume(event)
        msg = Message.objects.select_related("sender").get(id=msg_id)
        return msg

    def test_get_link_embed_data(self):
        # type: () -> None
        url = 'http://test.org/'
        embedded_link = '<a href="{0}" target="_blank" title="The Rock">The Rock</a>'.format(url)

        # When humans send, we should get embedded content.
        msg = self._send_message_with_test_org_url(sender_email=self.example_email('hamlet'))
        self.assertIn(embedded_link, msg.rendered_content)

        # We don't want embedded content for bots.
        msg = self._send_message_with_test_org_url(sender_email='webhook-bot@zulip.com',
                                                   queue_should_run=False)
        self.assertNotIn(embedded_link, msg.rendered_content)

        # Try another human to make sure bot failure was due to the
        # bot sending the message and not some other reason.
        msg = self._send_message_with_test_org_url(sender_email=self.example_email('prospero'))
        self.assertIn(embedded_link, msg.rendered_content)

    def test_inline_url_embed_preview(self):
        # type: () -> None
        with_preview = '<p><a href="http://test.org/" target="_blank" title="http://test.org/">http://test.org/</a></p>\n<div class="message_embed"><a class="message_embed_image" href="http://test.org/" style="background-image: url(http://ia.media-imdb.com/images/rock.jpg)" target="_blank"></a><div class="data-container"><div class="message_embed_title"><a href="http://test.org/" target="_blank" title="The Rock">The Rock</a></div><div class="message_embed_description">Description text</div></div></div>'
        without_preview = '<p><a href="http://test.org/" target="_blank" title="http://test.org/">http://test.org/</a></p>'
        msg = self._send_message_with_test_org_url(sender_email=self.example_email('hamlet'))
        self.assertEqual(msg.rendered_content, with_preview)

        realm = msg.get_realm()
        setattr(realm, 'inline_url_embed_preview', False)
        realm.save()

        msg = self._send_message_with_test_org_url(sender_email=self.example_email('prospero'), queue_should_run=False)
        self.assertEqual(msg.rendered_content, without_preview)

    def test_inline_url_embed_preview_with_relative_image_url(self):
        # type: () -> None
        with_preview_relative = '<p><a href="http://test.org/" target="_blank" title="http://test.org/">http://test.org/</a></p>\n<div class="message_embed"><a class="message_embed_image" href="http://test.org/" style="background-image: url(http://test.org/images/rock.jpg)" target="_blank"></a><div class="data-container"><div class="message_embed_title"><a href="http://test.org/" target="_blank" title="The Rock">The Rock</a></div><div class="message_embed_description">Description text</div></div></div>'
        # Try case where the opengraph image is a relative url.
        msg = self._send_message_with_test_org_url(sender_email=self.example_email('prospero'), relative_url=True)
        self.assertEqual(msg.rendered_content, with_preview_relative)

    def test_http_error_get_data(self):
        # type: () -> None
        url = 'http://test.org/'
        msg_id = self.send_message(
            self.example_email('hamlet'), self.example_email('cordelia'),
            Recipient.PERSONAL, subject="url", content=url)
        msg = Message.objects.select_related("sender").get(id=msg_id)
        event = {
            'message_id': msg_id,
            'urls': [url],
            'message_realm_id': msg.sender.realm_id,
            'message_content': url}
        with self.settings(INLINE_URL_EMBED_PREVIEW=True, TEST_SUITE=False, CACHES=TEST_CACHES):
            with mock.patch('requests.get', mock.Mock(side_effect=ConnectionError())):
                with mock.patch('logging.error') as error_mock:
                    FetchLinksEmbedData().consume(event)
        self.assertEqual(error_mock.call_count, 1)
        msg = Message.objects.get(id=msg_id)
        self.assertEqual(
            '<p><a href="http://test.org/" target="_blank" title="http://test.org/">http://test.org/</a></p>',
            msg.rendered_content)

    def test_invalid_link(self):
        # type: () -> None
        with self.settings(INLINE_URL_EMBED_PREVIEW=True, TEST_SUITE=False, CACHES=TEST_CACHES):
            self.assertIsNone(get_link_embed_data('com.notvalidlink'))
