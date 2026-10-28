import orjson

from zerver.lib.test_classes import WebhookTestCase


class BuildbotHookTests(WebhookTestCase):
    def test_build_started(self) -> None:
        expected_topic_name = "buildbot-hello"
        expected_message = (
            "Build [#33](http://exampleurl.com/#builders/1/builds/33) for **runtests** started."
        )
        self.check_webhook("started", expected_topic_name, expected_message)

    def test_build_success(self) -> None:
        expected_topic_name = "buildbot-hello"
        expected_message = "Build [#33](http://exampleurl.com/#builders/1/builds/33) (result: success) for **runtests** finished."
        self.check_webhook("finished_success", expected_topic_name, expected_message)

    def test_build_failure(self) -> None:
        expected_topic_name = "general"  # project key is empty
        expected_message = "Build [#34](http://exampleurl.com/#builders/1/builds/34) (result: failure) for **runtests** finished."
        self.check_webhook("finished_failure", expected_topic_name, expected_message)

    def test_build_cancelled(self) -> None:
        expected_topic_name = "zulip/zulip-zapier"
        expected_message = "Build [#10434](https://ci.example.org/#builders/79/builds/307) (result: cancelled) for **AMD64 Ubuntu 18.04 Python 3** finished."
        self.check_webhook("finished_cancelled", expected_topic_name, expected_message)

    def test_build_unknown_result(self) -> None:
        expected_topic_name = "buildbot-hello"
        expected_message = "Build [#33](http://exampleurl.com/#builders/1/builds/33) (result: unknown) for **runtests** finished."
        for result in [7, -1]:
            payload = self.get_body("finished_success").replace(
                '"results": 0', f'"results": {result}'
            )
            self.check_webhook(
                "finished_success",
                expected_topic_name,
                expected_message,
                custom_payload=payload,
            )

    def test_unsupported_event(self) -> None:
        payload = orjson.dumps(
            {
                "event": "unsupported",
                "buildid": 33,
                "buildername": "runtests",
                "url": "http://exampleurl.com/#builders/1/builds/33",
                "project": "buildbot-hello",
            }
        ).decode()
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_success(result)
        self.assert_in_response(
            "The 'unsupported' event isn't currently supported by the Buildbot webhook; ignoring",
            result,
        )
