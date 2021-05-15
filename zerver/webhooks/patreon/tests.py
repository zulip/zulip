from zerver.lib.test_classes import WebhookTestCase


class PatreonHookTests(WebhookTestCase):
    STREAM_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/patreon?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = "patreon"

    def test_patreon_members_create(self) -> None:
        """
        Tests condition of when a new patron joined
        """
        expected_topic = "patreon"
        expected_message = "New patron joined! :tada:\nPatrons in total: 5"

        self.check_webhook(
            "members_create",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_patreon_members_update(self) -> None:
        """
        Tests condition of when a patron updated membership
        """
        expected_topic = "patreon"
        expected_message = (
            "A patron just updated their membership. :notifications:\nPatrons in total: 5"
        )

        self.check_webhook(
            "members_update",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_patreon_members_delete(self) -> None:
        """
        Tests condition of when a patron deleted membership
        """
        expected_topic = "patreon"
        expected_message = (
            "A patron just deleted their membership. :exclamation:\nPatrons in total: 5"
        )

        self.check_webhook(
            "members_delete",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_patreon_members_pledge_create(self) -> None:
        """
        Tests condition of when a patron created pledge
        """
        expected_topic = "patreon"
        expected_message = "New patron joined through custom pledge! :tada:\nPatrons in total: 5"

        self.check_webhook(
            "members_pledge_create",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_patreon_members_pledge_update(self) -> None:
        """
        Tests condition of when a patron updated pledge
        """
        expected_topic = "patreon"
        expected_message = (
            "A patron just updated their pledge. :notifications:\nPatrons in total: 5"
        )

        self.check_webhook(
            "members_pledge_update",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_patreon_members_pledge_delete(self) -> None:
        """
        Tests condition of when a patron deleted pledge
        """
        expected_topic = "patreon"
        expected_message = "A patron just deleted their pledge. :exclamation:\nPatrons in total: 5"

        self.check_webhook(
            "members_pledge_delete",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_unsupported_webhook_event(self) -> None:
        """
        Tests condition of an unsupported webhook event
        """
        self.subscribe(self.test_user, self.STREAM_NAME)
        payload = self.get_body("unsupported_event")

        post_params = {
            "content_type": "application/json",
            "HTTP_X_PATREON_EVENT": "unsupported:event",
        }
        result = self.client_post(self.url, payload, **post_params)

        self.assert_json_error(
            result, "The 'unsupported:event' event isn't currently supported by the Patreon webhook"
        )
