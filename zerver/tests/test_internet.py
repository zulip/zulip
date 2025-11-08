import requests
import responses

from zerver.lib.test_classes import ZulipTestCase


class ResponsesTest(ZulipTestCase):
    def test_responses(self) -> None:
        # With our test setup, accessing the internet should be blocked.
        with self.assertRaisesRegex(
            Exception,
            r"^Outgoing network requests are not allowed in the Zulip tests\.",
        ):
            result = requests.request("GET", "https://www.google.com")

        # A test can invoke its own responses.RequestsMock context manager
        # and register URLs to mock, accessible from within the context.
        with responses.RequestsMock() as requests_mock:
            requests_mock.add(
                responses.GET,
                "https://www.google.com",
                body="{}",
                status=200,
                content_type="application/json",
            )
            result = requests.request("GET", "https://www.google.com")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.text, "{}")
