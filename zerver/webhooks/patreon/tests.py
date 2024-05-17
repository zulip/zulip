from unittest.mock import patch

import orjson

from zerver.lib.test_classes import WebhookTestCase

EXPECTED_TOPIC = "membership notifications"
IGNORED_EVENTS = [
    "pledges:create",
    "pledges:update",
    "pledges:delete",
]


class PatreonHookTests(WebhookTestCase):
    CHANNEL_NAME = "Patreon"
    URL_TEMPLATE = "/api/v1/external/patreon?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "patreon"

    def test_patreon_members_create(self) -> None:
        expected_message = "Kopi has joined as a member!"
        self.check_webhook(
            "members_create",
            EXPECTED_TOPIC,
            expected_message,
        )

    def test_patreon_members_update(self) -> None:
        expected_message = "Kopi's membership has been updated to active patron."
        self.check_webhook(
            "members_update",
            EXPECTED_TOPIC,
            expected_message,
        )

    def test_patreon_members_delete(self) -> None:
        expected_message = "Kopi's membership has ended."
        self.check_webhook(
            "members_delete",
            EXPECTED_TOPIC,
            expected_message,
        )

    def test_patreon_members_pledge_create(self) -> None:
        expected_message = "Kopi has pledged $5.00 per month. :tada:\nTotal number of patrons: 5"
        self.check_webhook(
            "members_pledge_create",
            EXPECTED_TOPIC,
            expected_message,
        )

    def test_patreon_members_pledge_update(self) -> None:
        expected_message = "Kopi has updated their pledge to $10.00 per month. :gear:"
        self.check_webhook(
            "members_pledge_update",
            EXPECTED_TOPIC,
            expected_message,
        )

    def test_patreon_members_pledge_delete(self) -> None:
        expected_message = (
            "Kopi's pledge has been cancelled. :cross_mark:\nTotal number of patrons: 4"
        )
        self.check_webhook(
            "members_pledge_delete",
            EXPECTED_TOPIC,
            expected_message,
        )

    def test_ignored_events(self) -> None:
        # The payload for these events never gets looked at in the
        # webhook itself; it only needs to be valid JSON.
        payload = "{}"

        for event in IGNORED_EVENTS:
            self.verify_post_is_ignored(payload, event)

    def test_ignored_payloads(self) -> None:
        payload = orjson.loads(self.get_body("members_create"))
        payload["data"]["attributes"]["last_charge_status"] = "Declined"
        payload["data"]["attributes"]["patron_status"] = "declined_patron"

        event_types = [
            "members:create",
            "members:update",
            "members:delete",
            "members:pledge:create",
            "members:pledge:update",
            "members:pledge:delete",
        ]

        for event in event_types:
            self.verify_post_is_ignored(orjson.dumps(payload).decode(), event)

    def verify_post_is_ignored(self, payload: str, http_x_patreon_event: str) -> None:
        with patch("zerver.webhooks.patreon.view.check_send_webhook_message") as m:
            result = self.client_post(
                self.url,
                payload,
                HTTP_X_PATREON_EVENT=http_x_patreon_event,
                content_type="application/json",
            )
        if http_x_patreon_event in IGNORED_EVENTS:
            self.assertFalse(m.called)
        self.assert_json_success(result)
