import orjson

from zerver.lib.test_classes import WebhookTestCase


class HerokuHookTests(WebhookTestCase):
    TOPIC_NAME = "zulip-test"

    def test_build_create(self) -> None:
        expected_message = "sampleuser@gmail.com triggered a [build](https://build-output.heroku.com/streams/43/4335bcdb-5f6f-41f8-a31b-84697ec96475/logs/b6/b6d5ff62-08db-4044-b96c-b8e9e41f1191.log?X-Amz-Algorithm=AWS4-HMAC-SHA256&amp;X-Amz-Credential=AKIAZSXS6CXK3PQ5Y6GY%2F20250517%2Fus-east-1%2Fs3%2Faws4_request&amp;X-Amz-Date=20250517T113737Z&amp;X-Amz-Expires=86400&amp;X-Amz-SignedHeaders=host&amp;X-Amz-Signature=b2f0cac0426f4898d9bdcd214401027af128935b9e9618eeb6f83a3546b142d2)."
        self.check_webhook("build_create", self.TOPIC_NAME, expected_message)

    def test_build_update(self) -> None:
        expected_message = "The [build](https://build-output.heroku.com/streams/43/4335bcdb-5f6f-41f8-a31b-84697ec96475/logs/b6/b6d5ff62-08db-4044-b96c-b8e9e41f1191.log?X-Amz-Algorithm=AWS4-HMAC-SHA256&amp;X-Amz-Credential=AKIAZSXS6CXK3PQ5Y6GY%2F20250517%2Fus-east-1%2Fs3%2Faws4_request&amp;X-Amz-Date=20250517T113803Z&amp;X-Amz-Expires=86400&amp;X-Amz-SignedHeaders=host&amp;X-Amz-Signature=0aa7c17cbf2fb161feec2da740e6956a39c25b8c55fbce6ebec5b6d4e01ade7c) triggered by sampleuser@gmail.com **succeeded**."
        self.check_webhook("build_update", self.TOPIC_NAME, expected_message)

    def test_release_create(self) -> None:
        expected_message = "sampleuser@gmail.com triggered a release(v3): Deploy 1a5f89db."
        self.check_webhook("release_create", self.TOPIC_NAME, expected_message)

    def test_release_update(self) -> None:
        expected_message = (
            "The release(v3): Deploy 1a5f89db triggered by sampleuser@gmail.com **succeeded**."
        )
        self.check_webhook("release_update", self.TOPIC_NAME, expected_message)

    def test_release_phase_update(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = self.webhook_fixture_data(self.webhook_dir_name, "release_update")
        data = orjson.loads(payload)
        data["data"]["current"] = False
        result = self.client_post(self.url, orjson.dumps(data), content_type="application/json")
        self.assert_json_success(result)
