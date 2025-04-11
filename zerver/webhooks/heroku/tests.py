from zerver.lib.test_classes import WebhookTestCase


class HerokuHookTests(WebhookTestCase):
    WEBHOOK_DIR_NAME = "heroku"
    CHANNEL_NAME = "Heroku"
    URL_TEMPLATE = "/api/v1/external/heroku?stream={stream}&api_key={api_key}"

    def test_build_create(self) -> None:
        expected_topic = "vedant-test"
        expected_message = "vedant.messi101@gmail.com created a new [build](https://build-output.heroku.com/streams/43/4335bcdb-5f6f-41f8-a31b-84697ec96475/logs/b6/b6d5ff62-08db-4044-b96c-b8e9e41f1191.log?X-Amz-Algorithm=AWS4-HMAC-SHA256&amp;X-Amz-Credential=AKIAZSXS6CXK3PQ5Y6GY%2F20250517%2Fus-east-1%2Fs3%2Faws4_request&amp;X-Amz-Date=20250517T113737Z&amp;X-Amz-Expires=86400&amp;X-Amz-SignedHeaders=host&amp;X-Amz-Signature=b2f0cac0426f4898d9bdcd214401027af128935b9e9618eeb6f83a3546b142d2)."
        self.check_webhook(
            "build_create",
            expected_topic,
            expected_message,
        )

    def test_build_update(self) -> None:
        expected_topic = "vedant-test"
        expected_message = "The [build](https://build-output.heroku.com/streams/43/4335bcdb-5f6f-41f8-a31b-84697ec96475/logs/b6/b6d5ff62-08db-4044-b96c-b8e9e41f1191.log?X-Amz-Algorithm=AWS4-HMAC-SHA256&amp;X-Amz-Credential=AKIAZSXS6CXK3PQ5Y6GY%2F20250517%2Fus-east-1%2Fs3%2Faws4_request&amp;X-Amz-Date=20250517T113803Z&amp;X-Amz-Expires=86400&amp;X-Amz-SignedHeaders=host&amp;X-Amz-Signature=0aa7c17cbf2fb161feec2da740e6956a39c25b8c55fbce6ebec5b6d4e01ade7c) succeeded."
        self.check_webhook(
            "build_update",
            expected_topic,
            expected_message,
        )

    def test_release_create(self) -> None:
        expected_topic = "vedant-test"
        expected_message = "vedant.messi101@gmail.com created a new release(v3): Deploy 1a5f89db."
        self.check_webhook(
            "release_create",
            expected_topic,
            expected_message,
        )

    def test_release_update(self) -> None:
        expected_topic = "vedant-test"
        expected_message = "The release(v3) succeeded."
        self.check_webhook(
            "release_update",
            expected_topic,
            expected_message,
        )
