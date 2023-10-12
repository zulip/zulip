import urllib

from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase


class TravisHookTests(WebhookTestCase):
    STREAM_NAME = "travis"
    URL_TEMPLATE = "/api/v1/external/travis?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "travis"
    TOPIC = "builds"
    EXPECTED_MESSAGE = """
Author: josh_mandel
Build status: Passed :thumbs_up:
Details: [changes](https://github.com/hl7-fhir/fhir-svn/compare/6dccb98bcfd9...6c457d366a31), [build log](https://travis-ci.org/hl7-fhir/fhir-svn/builds/92495257)
""".strip()

    def test_travis_message(self) -> None:
        """
        Build notifications are generated by Travis after build completes.

        The subject describes the repo and Stash "project". The
        content describes the commits pushed.
        """

        self.check_webhook(
            "build",
            self.TOPIC,
            self.EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_ignore_travis_pull_request_by_default(self) -> None:
        self.check_webhook(
            "pull_request", content_type="application/x-www-form-urlencoded", expect_noop=True
        )

    def test_travis_pull_requests_are_not_ignored_when_applicable(self) -> None:
        self.url = f"{self.build_webhook_url()}&ignore_pull_requests=false"

        self.check_webhook(
            "pull_request",
            self.TOPIC,
            self.EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_travis_only_push_event(self) -> None:
        self.url = f'{self.build_webhook_url()}&only_events=["push"]'

        self.check_webhook(
            "build",
            self.TOPIC,
            self.EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_travis_only_push_event_not_sent(self) -> None:
        self.url = f'{self.build_webhook_url()}&only_events=["push"]&ignore_pull_requests=false'

        self.check_webhook(
            "pull_request",
            content_type="application/x-www-form-urlencoded",
            expect_noop=True,
        )

    def test_travis_exclude_push_event(self) -> None:
        self.url = f'{self.build_webhook_url()}&exclude_events=["push"]'

        self.check_webhook(
            "build",
            content_type="application/x-www-form-urlencoded",
            expect_noop=True,
        )

    def test_travis_exclude_push_event_sent(self) -> None:
        self.url = f'{self.build_webhook_url()}&exclude_events=["push"]&ignore_pull_requests=false'

        self.check_webhook(
            "pull_request",
            self.TOPIC,
            self.EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_travis_include_glob_events(self) -> None:
        self.url = f'{self.build_webhook_url()}&include_events=["*"]&ignore_pull_requests=false'

        self.check_webhook(
            "pull_request",
            self.TOPIC,
            self.EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

        self.check_webhook(
            "build",
            self.TOPIC,
            self.EXPECTED_MESSAGE,
            content_type="application/x-www-form-urlencoded",
        )

    def test_travis_exclude_glob_events(self) -> None:
        self.url = f'{self.build_webhook_url()}&exclude_events=["*"]&ignore_pull_requests=false'

        self.check_webhook(
            "pull_request",
            content_type="application/x-www-form-urlencoded",
            expect_noop=True,
        )

        self.check_webhook(
            "build",
            content_type="application/x-www-form-urlencoded",
            expect_noop=True,
        )

    def test_travis_noop(self) -> None:
        expected_error_message = """
While no message is expected given expect_noop=True,
your test code triggered an endpoint that did write
one or more new messages.
        """.strip()

        with self.assertRaises(Exception) as exc:
            self.check_webhook(
                "build", content_type="application/x-www-form-urlencoded", expect_noop=True
            )
        self.assertEqual(str(exc.exception), expected_error_message)

    @override
    def get_body(self, fixture_name: str) -> str:
        return urllib.parse.urlencode(
            {"payload": self.webhook_fixture_data("travis", fixture_name, file_type="json")}
        )
