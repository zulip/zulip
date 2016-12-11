# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
import ujson
from typing import Any
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_preview.oembed import get_oembed_data
from zerver.lib.url_preview.parsers import (
    OpenGraphParser, GenericParser)


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
