# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase
from mock import patch, MagicMock

class TrelloHookTests(WebhookTestCase):
    STREAM_NAME = 'trello'
    URL_TEMPLATE = u"/api/v1/external/trello?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'trello'

    def test_trello_confirmation_request(self):
        # type: () -> None
        response = self.client_head(self.build_webhook_url())
        self.assertEqual(response.status_code, 200, response)

    def test_trello_webhook_when_card_was_moved_to_another_list(self):
        # type: () -> None
        expected_message = u"TomaszKolek moved [This is a card.](https://trello.com/c/r33ylX2Z) from Basics to Intermediate."
        self.send_and_test_stream_message('changing_cards_list', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_card_was_renamed(self):
        # type: () -> None
        expected_message = u"TomaszKolek renamed the card from \"Old name\" to [New name](https://trello.com/c/r33ylX2Z)."
        self.send_and_test_stream_message('renaming_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_label_was_added_to_card(self):
        # type: () -> None
        expected_message = u"TomaszKolek added a green label with \"text value\" to [Card name](https://trello.com/c/r33ylX2Z)."
        self.send_and_test_stream_message('adding_label_to_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_label_was_removing_from_card(self):
        # type: () -> None
        expected_message = u"TomaszKolek removed a green label with \"text value\" from [New Card](https://trello.com/c/r33ylX2Z)."
        self.send_and_test_stream_message('removing_label_from_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_member_was_added_to_card(self):
        # type: () -> None
        expected_message = u"TomaszKolek added TomaszKolek to [Card name](https://trello.com/c/9BduUcVQ)."
        self.send_and_test_stream_message('adding_member_to_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_member_was_removed_from_card(self):
        # type: () -> None
        expected_message = u"TomaszKolek removed Trello from [Card name](https://trello.com/c/9BduUcVQ)."
        self.send_and_test_stream_message('removing_member_from_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_due_date_was_set(self):
        # type: () -> None
        expected_message = u"TomaszKolek set due date for [Card name](https://trello.com/c/9BduUcVQ) to 2016-05-11 10:00:00 UTC."
        self.send_and_test_stream_message('setting_due_date_to_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_due_date_was_changed(self):
        # type: () -> None
        expected_message = u"TomaszKolek changed due date for [Card name](https://trello.com/c/9BduUcVQ) from 2016-05-11 10:00:00 UTC to 2016-05-24 10:00:00 UTC."
        self.send_and_test_stream_message('changing_due_date_on_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_due_date_was_removed(self):
        # type: () -> None
        expected_message = u"TomaszKolek removed the due date from [Card name](https://trello.com/c/9BduUcVQ)."
        self.send_and_test_stream_message('removing_due_date_from_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_card_was_archived(self):
        # type: () -> None
        expected_message = u"TomaszKolek archived [Card name](https://trello.com/c/9BduUcVQ)."
        self.send_and_test_stream_message('archiving_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_card_was_reopened(self):
        # type: () -> None
        expected_message = u"TomaszKolek reopened [Card name](https://trello.com/c/9BduUcVQ)."
        self.send_and_test_stream_message('reopening_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_card_was_created(self):
        # type: () -> None
        expected_message = u"TomaszKolek created [New card](https://trello.com/c/5qrgGdD5)."
        self.send_and_test_stream_message('creating_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_attachment_was_added_to_card(self):
        # type: () -> None
        expected_message = u"TomaszKolek added [attachment_name](http://url.com) to [New card](https://trello.com/c/xPKXoSTQ)."
        self.send_and_test_stream_message('adding_attachment_to_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_checklist_was_added_to_card(self):
        # type: () -> None
        expected_message = u"TomaszKolek added the Checklist checklist to [New card](https://trello.com/c/xPKXoSTQ)."
        self.send_and_test_stream_message('adding_checklist_to_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_member_was_removed_from_board(self):
        # type: () -> None
        expected_message = u"TomaszKolek removed Trello from [Welcome Board](https://trello.com/b/iqXXzYEj)."
        self.send_and_test_stream_message('removing_member_from_board', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_member_was_added_to_board(self):
        # type: () -> None
        expected_message = u"TomaszKolek added Trello to [Welcome Board](https://trello.com/b/iqXXzYEj)."
        self.send_and_test_stream_message('adding_member_to_board', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_list_was_added_to_board(self):
        # type: () -> None
        expected_message = u"TomaszKolek added New list list to [Welcome Board](https://trello.com/b/iqXXzYEj)."
        self.send_and_test_stream_message('adding_new_list_to_board', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_comment_was_added_to_card(self):
        # type: () -> None
        expected_message = u"TomaszKolek commented on [New card](https://trello.com/c/xPKXoSTQ)."
        self.send_and_test_stream_message('adding_comment_to_card', u"Welcome Board.", expected_message)

    def test_trello_webhook_when_board_was_renamed(self):
        # type: () -> None
        expected_message = u"TomaszKolek renamed the board from Welcome Board to [New name](https://trello.com/b/iqXXzYEj)."
        self.send_and_test_stream_message('renaming_board', u"New name.", expected_message)

    @patch('zerver.webhooks.trello.view.check_send_message')
    def test_trello_webhook_when_card_is_moved_within_single_list_ignore(
            self, check_send_message_mock):
        # type: (MagicMock) -> None
        payload = self.get_body('moving_card_within_single_list')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.trello.view.check_send_message')
    def test_trello_webhook_when_board_background_is_changed_ignore(
            self, check_send_message_mock):
        # type: (MagicMock) -> None
        payload = self.get_body('change_board_background_image')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_message_mock.called)
        self.assert_json_success(result)
