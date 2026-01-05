import json

from zerver.lib.test_classes import WebhookTestCase


class HerokuHookTests(WebhookTestCase):
    CHANNEL_NAME = "Heroku"
    URL_TEMPLATE = "/api/v1/external/heroku?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "heroku"

    def test_build_pending(self) -> None:
        """Test build create event with pending status"""
        expected_topic = "sample-project / Build"
        expected_message = (
            "Build for **sample-project** triggered by user@example.com is **pending**."
        )
        self.check_webhook("build_create", expected_topic, expected_message)

    def test_build_succeeded(self) -> None:
        """Test build update event with succeeded status"""
        expected_topic = "sample-project / Build"
        # FIX: Changed &amp; to & to match actual output
        expected_message = "Build for **sample-project** triggered by user@example.com **succeeded**. [View Log](https://build-output.heroku.com/streams/43/4335bcdb-5f6f-41f8-a31b-84697ec96475/logs/b6/b6d5ff62-08db-4044-b96c-b8e9e41f1191.log?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAZSXS6CXK3PQ5Y6GY%2F20250517%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250517T113803Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host&X-Amz-Signature=0aa7c17cbf2fb161feec2da740e6956a39c25b8c55fbce6ebec5b6d4e01ade7c)"
        self.check_webhook("build_update", expected_topic, expected_message)

    def test_build_succeeded_no_log_url(self) -> None:
        """Test build success when no log URL is provided (coverage fallback)"""
        expected_topic = "sample-project / Build"
        expected_message = "Build for **sample-project** triggered by user@example.com **succeeded**. [View Log](https://dashboard.heroku.com/apps/sample-project/activity)"

        # Parse JSON and delete key
        payload_text = self.get_body("build_update")
        payload = json.loads(payload_text)
        del payload["data"]["output_stream_url"]

        # Manually verify the message
        self.subscribe(self.test_user, self.CHANNEL_NAME)
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            content=expected_message,
            topic_name=expected_topic,
        )

    def test_fallback_to_user_email_if_no_actor(self) -> None:
        """Test that we fall back to 'user' email if 'actor' is missing (coverage)"""
        expected_topic = "sample-project / Build"
        # The message should still look exactly the same because in our fixtures,
        # the actor email and user email are identical.
        expected_message = "Build for **sample-project** triggered by user@example.com **succeeded**. [View Log](https://dashboard.heroku.com/apps/sample-project/activity)"

        # Parse JSON and delete 'actor' AND 'output_stream_url' (to keep the message simple)
        payload_text = self.get_body("build_update")
        payload = json.loads(payload_text)
        del payload["actor"]
        del payload["data"]["output_stream_url"]

        # Manually verify the message
        self.subscribe(self.test_user, self.CHANNEL_NAME)
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            content=expected_message,
            topic_name=expected_topic,
        )

    def test_build_failed(self) -> None:
        """Test build update event with failed status"""
        expected_topic = "sample-project / Build"
        # Matches the 'build_failed.json' fixture which uses standard &
        expected_message = "Build for **sample-project** triggered by user@example.com **failed**. [View Log](https://build-output.heroku.com/streams/43/4335bcdb-5f6f-41f8-a31b-84697ec96475/logs/b6/b6d5ff62-08db-4044-b96c-b8e9e41f1191.log?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAZSXS6CXK3PQ5Y6GY%2F20250517%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250517T113803Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host&X-Amz-Signature=0aa7c17cbf2fb161feec2da740e6956a39c25b8c55fbce6ebec5b6d4e01ade7c)"
        self.check_webhook("build_failed", expected_topic, expected_message)

    def test_build_failed_no_log_url(self) -> None:
        """Test build failed event when no log URL is provided (coverage fallback)"""
        expected_topic = "sample-project / Build"
        expected_message = "Build for **sample-project** triggered by user@example.com **failed**. [View Log](https://dashboard.heroku.com/apps/sample-project/activity)"

        # Parse JSON and delete key
        payload_text = self.get_body("build_failed")
        payload = json.loads(payload_text)
        del payload["data"]["output_stream_url"]

        # Manually verify the message
        self.subscribe(self.test_user, self.CHANNEL_NAME)
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            content=expected_message,
            topic_name=expected_topic,
        )

    def test_release_succeeded_from_create(self) -> None:
        """Test release create event with succeeded status (no release phases)"""
        expected_topic = "sample-project / Release"
        expected_message = "Release (Deploy 1a5f89db) for **sample-project** triggered by user@example.com **succeeded**."
        self.check_webhook("release_create", expected_topic, expected_message)

    def test_release_succeeded_from_update(self) -> None:
        """Test release update event with succeeded status and current=true"""
        expected_topic = "sample-project / Release"
        expected_message = "Release (Deploy 1a5f89db) for **sample-project** triggered by user@example.com **succeeded**."
        self.check_webhook("release_update", expected_topic, expected_message)

    def test_release_failed(self) -> None:
        """Test release update event with failed status"""
        expected_topic = "sample-project / Release"
        expected_message = "Release (Deploy 1a5f89db) for **sample-project** triggered by user@example.com **failed**."
        self.check_webhook("release_failed", expected_topic, expected_message)

    def test_release_pending(self) -> None:
        """Test release create event with pending status"""
        expected_topic = "sample-project / Release"
        expected_message = "Release (Deploy 1a5f89db) for **sample-project** triggered by user@example.com is **pending**."
        self.check_webhook("release_pending", expected_topic, expected_message)

    def test_release_with_current_false_ignored(self) -> None:
        """Test that release updates with current=false are ignored (duplicate prevention)"""
        self.subscribe(self.test_user, self.CHANNEL_NAME)

        payload = self.get_body("release_update_not_current")

        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_success(result)
