from typing import Dict
from unittest.mock import patch

import orjson

from zerver.lib.test_classes import WebhookTestCase


class TrelloHookTests(WebhookTestCase):
    CHANNEL_NAME = "trello"
    URL_TEMPLATE = "/api/v1/external/trello?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "trello"

    def test_trello_confirmation_request(self) -> None:
        response = self.client_head(self.build_webhook_url())
        self.assertEqual(response.status_code, 200, response)

    def test_trello_webhook_when_card_was_moved_to_another_list(self) -> None:
        expected_message = "TomaszKolek moved [This is a card.](https://trello.com/c/r33ylX2Z) from Basics to Intermediate."
        self.check_webhook("changing_cards_list", "Welcome Board", expected_message)

    def test_trello_webhook_when_card_was_renamed(self) -> None:
        expected_message = 'TomaszKolek renamed the card from "Old name" to [New name](https://trello.com/c/r33ylX2Z).'
        self.check_webhook("renaming_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_label_was_added_to_card(self) -> None:
        expected_message = 'TomaszKolek added a green label with "text value" to [Card name](https://trello.com/c/r33ylX2Z).'
        self.check_webhook("adding_label_to_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_label_was_removing_from_card(self) -> None:
        expected_message = 'TomaszKolek removed a green label with "text value" from [New Card](https://trello.com/c/r33ylX2Z).'
        self.check_webhook("removing_label_from_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_member_was_added_to_card(self) -> None:
        expected_message = (
            "TomaszKolek added TomaszKolek to [Card name](https://trello.com/c/9BduUcVQ)."
        )
        self.check_webhook("adding_member_to_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_member_was_removed_from_card(self) -> None:
        expected_message = (
            "TomaszKolek removed Trello from [Card name](https://trello.com/c/9BduUcVQ)."
        )
        self.check_webhook("removing_member_from_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_due_date_was_set(self) -> None:
        expected_message = "TomaszKolek set due date for [Card name](https://trello.com/c/9BduUcVQ) to 2016-05-11 10:00:00 UTC."
        self.check_webhook("setting_due_date_to_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_due_date_was_changed(self) -> None:
        expected_message = "TomaszKolek changed due date for [Card name](https://trello.com/c/9BduUcVQ) from 2016-05-11 10:00:00 UTC to 2016-05-24 10:00:00 UTC."
        self.check_webhook("changing_due_date_on_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_due_date_was_removed(self) -> None:
        expected_message = (
            "TomaszKolek removed the due date from [Card name](https://trello.com/c/9BduUcVQ)."
        )
        self.check_webhook("removing_due_date_from_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_card_was_archived(self) -> None:
        expected_message = "TomaszKolek archived [Card name](https://trello.com/c/9BduUcVQ)."
        self.check_webhook("archiving_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_card_was_reopened(self) -> None:
        expected_message = "TomaszKolek reopened [Card name](https://trello.com/c/9BduUcVQ)."
        self.check_webhook("reopening_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_card_was_created(self) -> None:
        expected_message = "TomaszKolek created [New card](https://trello.com/c/5qrgGdD5)."
        self.check_webhook("creating_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_attachment_was_added_to_card(self) -> None:
        expected_message = "TomaszKolek added [attachment_name](http://url.com) to [New card](https://trello.com/c/xPKXoSTQ)."
        self.check_webhook("adding_attachment_to_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_checklist_was_added_to_card(self) -> None:
        expected_message = "TomaszKolek added the Checklist checklist to [New card](https://trello.com/c/xPKXoSTQ)."
        self.check_webhook("adding_checklist_to_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_check_item_is_checked(self) -> None:
        expected_message = "Eeshan Garg checked **Tomatoes** in **Checklist** ([Something something](https://trello.com/c/R2thJK3P))."
        self.check_webhook("check_item_on_card_checklist", "Zulip", expected_message)

    def test_trello_webhook_when_check_item_is_unchecked(self) -> None:
        expected_message = "Eeshan Garg unchecked **Tomatoes** in **Checklist** ([Something something](https://trello.com/c/R2thJK3P))."
        self.check_webhook("uncheck_item_on_card_checklist", "Zulip", expected_message)

    def test_trello_webhook_when_member_was_removed_from_board(self) -> None:
        expected_message = (
            "TomaszKolek removed Trello from [Welcome Board](https://trello.com/b/iqXXzYEj)."
        )
        self.check_webhook("removing_member_from_board", "Welcome Board", expected_message)

    def test_trello_webhook_when_member_was_added_to_board(self) -> None:
        expected_message = (
            "TomaszKolek added Trello to [Welcome Board](https://trello.com/b/iqXXzYEj)."
        )
        self.check_webhook("adding_member_to_board", "Welcome Board", expected_message)

    def test_trello_webhook_when_list_was_added_to_board(self) -> None:
        expected_message = (
            "TomaszKolek added New list list to [Welcome Board](https://trello.com/b/iqXXzYEj)."
        )
        self.check_webhook("adding_new_list_to_board", "Welcome Board", expected_message)

    def test_trello_webhook_when_comment_was_added_to_card(self) -> None:
        expected_message = "TomaszKolek commented on [New card](https://trello.com/c/xPKXoSTQ):\n~~~ quote\nNew comment\n~~~"
        self.check_webhook("adding_comment_to_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_board_was_renamed(self) -> None:
        expected_message = "TomaszKolek renamed the board from Welcome Board to [New name](https://trello.com/b/iqXXzYEj)."
        self.check_webhook("renaming_board", "New name", expected_message)

    def verify_post_is_ignored(self, payload: str) -> None:
        with patch("zerver.webhooks.trello.view.check_send_webhook_message") as m:
            result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(m.called)
        self.assert_json_success(result)

    def test_trello_webhook_when_card_is_moved_within_single_list_ignore(self) -> None:
        payload = self.get_body("moving_card_within_single_list")
        self.verify_post_is_ignored(payload)

    def test_trello_webhook_when_board_background_is_changed_ignore(self) -> None:
        payload = self.get_body("change_board_background_image")
        self.verify_post_is_ignored(payload)

    def test_ignored_card_actions(self) -> None:
        """
        Certain card-related actions are now ignored solely based on the
        action type, and we don't need to do any other parsing to ignore
        them as invalid.
        """
        actions = [
            "copyCard",
            "createCheckItem",
            "updateCheckItem",
            "updateList",
        ]
        for action in actions:
            data = dict(
                model="whatever",
                action=dict(
                    type=action,
                ),
            )
            payload = orjson.dumps(data).decode()
            self.verify_post_is_ignored(payload)

    def test_ignoring_card_updates(self) -> None:
        fields = [
            "cover",
            "dueComplete",
            "idAttachmentCover",
            "pos",
        ]
        for field in fields:
            card: Dict[str, object] = {}
            old = {}
            old[field] = "should-be-ignored"
            data = dict(
                model="whatever",
                action=dict(
                    type="updateCard",
                    data=dict(card=card, old=old),
                ),
            )
            payload = orjson.dumps(data).decode()
            self.verify_post_is_ignored(payload)

    def test_trello_webhook_when_description_was_added_to_card(self) -> None:
        expected_message = "Marco Matarazzo set description for [New Card](https://trello.com/c/P2r0z66z) to:\n~~~ quote\nNew Description\n~~~"
        self.check_webhook("adding_description_to_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_description_was_removed_from_card(self) -> None:
        expected_message = (
            "Marco Matarazzo removed description from [New Card](https://trello.com/c/P2r0z66z)."
        )
        self.check_webhook("removing_description_from_card", "Welcome Board", expected_message)

    def test_trello_webhook_when_description_was_changed_on_card(self) -> None:
        expected_message = "Marco Matarazzo changed description for [New Card](https://trello.com/c/P2r0z66z) from\n~~~ quote\nNew Description\n~~~\nto\n~~~ quote\nChanged Description\n~~~"
        self.check_webhook("changing_description_on_card", "Welcome Board", expected_message)
