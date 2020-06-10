from zerver.lib.test_classes import ZulipTestCase
from zerver.views.auth import get_safe_redirect_to

import responses
import requests

class ResponsesTest(ZulipTestCase):
    def test_responses(self) -> None:
        # With our test setup, accessing the internet should be blocked.
        with self.assertRaises(Exception):
            result = requests.request('GET', 'https://www.google.com')

        # A test can invoke its own responses.RequestsMock context manager
        # and register URLs to mock, accessible from within the context.
        with responses.RequestsMock() as requests_mock:
            requests_mock.add(responses.GET, 'https://www.google.com',
                              body='{}', status=200,
                              content_type='application/json')
            result = requests.request('GET', 'https://www.google.com')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.text, '{}')

class GetSafeRedirectUrlTest(ZulipTestCase):
    def test_get_safe_redirect_to(self) -> None:
        self.assertEqual(
            get_safe_redirect_to('/test/endpoint?query', 'example.com'),
            '/test/endpoint?query'
        )
        self.assertEqual(
            get_safe_redirect_to('/test/endpoint?query', 'https://example.com'),
            '/test/endpoint?query'
        )
        self.assertEqual(
            get_safe_redirect_to('https://example.com/test/endpoint?query', 'example.com'),
            'https://example.com/test/endpoint?query'
        )
        self.assertEqual(
            get_safe_redirect_to('https://example.com/test/endpoint?query', 'https://example.com'),
            'https://example.com/test/endpoint?query'
        )
        # Don't allow redirect to an unintended host. Convert to a redirect to the safe host.
        self.assertEqual(
            get_safe_redirect_to('https://evilexample.com/test/endpoint?query', 'example.com'),
            'https://example.com'
        )
        self.assertEqual(
            get_safe_redirect_to('https://evilexample.com/test/endpoint?query', 'https://example.com'),
            'https://example.com'
        )
