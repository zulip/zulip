from zerver.lib.test_classes import WebhookTestCase


class PatreonHookTests(WebhookTestCase):
    STREAM_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/patreon?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "patreon"

    def test_patreon_members_create(self) -> None:
        """
        Tests if the event of a new member joining is handled correctly
        """
        expected_topic = "Patreon Notifications"
        expected_message = "Zulip has joined as a member! :tada:\nYou now have 5 patron(s)."

        self.check_webhook(
            "members_create",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_patreon_members_update(self) -> None:
        """
        Tests if the event of an updated membership is handled correctly
        """
        expected_topic = "Patreon Notifications"
        expected_message = "Zulip just updated their membership. :gear:\nYou now have 5 patron(s)."

        self.check_webhook(
            "members_update",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_patreon_members_delete(self) -> None:
        """
        Tests if the event of a deleted membership is handled correctly
        """
        expected_topic = "Patreon Notifications"
        expected_message = (
            "Zulip just deleted their membership. :cross_mark:\nYou now have 5 patron(s)."
        )

        self.check_webhook(
            "members_delete",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_patreon_members_pledge_create(self) -> None:
        """
        Tests if the event of the creation of a new pledge is handled correctly
        """
        expected_topic = "Patreon Notifications"
        expected_message = (
            "Zulip has created a new member pledge of $5.5. :tada:\nYou now have 5 patron(s)."
        )

        self.check_webhook(
            "members_pledge_create",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_patreon_members_pledge_update(self) -> None:
        """
        Tests if the event of an updated pledge is handled correctly
        """
        expected_topic = "Patreon Notifications"
        expected_message = "Zulip just updated their pledge. :gear:\nYou now have 5 patron(s)."

        self.check_webhook(
            "members_pledge_update",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_patreon_members_pledge_delete(self) -> None:
        """
        Tests if the event of a deleted pledge is handled correctly
        """
        expected_topic = "Patreon Notifications"
        expected_message = (
            "Zulip just deleted their pledge. :cross_mark:\nYou now have 5 patron(s)."
        )

        self.check_webhook(
            "members_pledge_delete",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_unsupported_webhook_event(self) -> None:
        """
        Tests if an unsupported webhook event is handled correctly
        """
        self.subscribe(self.test_user, self.STREAM_NAME)
        payload = self.get_body("unsupported_event")

        result = self.client_post(
            self.url,
            payload,
            content_type="application/json",
            HTTP_X_PATREON_EVENT="unsupported:event",
        )

        self.assert_json_error(
            result, "The 'unsupported:event' event isn't currently supported by the Patreon webhook"
        )
