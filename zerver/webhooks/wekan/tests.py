from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase


class WekanHookTests(WebhookTestCase):
    CHANNEL_NAME = "wekan"
    URL_TEMPLATE = "/api/v1/external/wekan?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = "wekan"

    def test_add_attachment_message(self) -> None:
        expected_message = 'JohnFish added attachment "hGfm5ksud8k" to card "Markdown and emoji\'s" at list "Design" at swimlane "Default" at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "add_attachment",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_add_checklist_item_message(self) -> None:
        expected_message = 'JohnFish added checklist item "merge commit 9dfe" to checklist "To do" at card "Markdown and emoji\'s" at list "Design" at swimlane "Default" at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "add_checklist_item",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_add_checklist_message(self) -> None:
        expected_message = 'JohnFish added checklist "To do" to card "Markdown and emoji\'s" at list "Design" at swimlane "Default" at board "bucked-list".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "add_checklist",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_add_label_message(self) -> None:
        expected_message = 'JohnFish Added label Language to card "Markdown & emojis" at list "Design" at swimlane "Default" at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/TMmjFnQGuZPsbjXzS)'
        self.check_webhook(
            "add_label",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_archived_swimlane_message(self) -> None:
        expected_message = 'JohnFish Swimlane "Default" at board "Bucket List" moved to Archive.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)'
        self.check_webhook(
            "archived_swimlane",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_archived_card_message(self) -> None:
        expected_message = 'JohnFish Card "Markdown and emoji\'s" at list "Design" at swimlane "Default" at board "Bucket List" moved to Archive.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "archived_card",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_archived_list_message(self) -> None:
        expected_message = 'JohnFish List "Design" at swimlane "Default" at board "Bucket List" moved to Archive.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)'
        self.check_webhook(
            "archived_list",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_checked_item_message(self) -> None:
        expected_message = 'JohnFish checked To do of checklist "To do" at card "Markdown and emoji\'s" at list "Design" at swimlane "Default" at board "bucket-list".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "checked_item",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_add_comment_message(self) -> None:
        expected_message = 'JohnFish commented on card "Markdown and emoji\'s": "This feature is important" at list "Design" at swimlane "Default" at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "add_comment",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_create_card_message(self) -> None:
        expected_message = 'JohnFish created card "Markdown and emoji\'s" to list "Development & Implementation" at swimlane "Default" at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "create_card",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_create_custom_field_message(self) -> None:
        expected_message = 'JohnFish created custom field Language at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)'
        self.check_webhook(
            "create_custom_field",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_create_list_message(self) -> None:
        expected_message = 'JohnFish added list "Testing & Maintenance" to board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)'
        self.check_webhook(
            "create_list",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_create_swimlane_message(self) -> None:
        expected_message = 'JohnFish created swimlane "Jasper" to board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)'
        self.check_webhook(
            "create_swimlane",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_delete_attachment_message(self) -> None:
        expected_message = 'JohnFish deleted attachment "hGfm5ksud8k.jpg" at card "Markdown and emoji\'s" at list "Design" at swimlane "Default" at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "delete_attachment",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_join_member_message(self) -> None:
        expected_message = 'JohnFish added member kokoboss to card "Markdown & emojis" at list "Design" at swimlane "Default" at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/TMmjFnQGuZPsbjXzS)'
        self.check_webhook(
            "join_member",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_move_card_message(self) -> None:
        expected_message = 'JohnFish moved card "Markdown and emoji\'s" at board "Bucket List" from list "Development & Implementation" at swimlane "Default" to list "Design" at swimlane "Default".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "move_card",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_remove_list_message(self) -> None:
        expected_message = "JohnFish act-removeList.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)"
        self.check_webhook(
            "remove_list",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_remove_swimlane_message(self) -> None:
        expected_message = "JohnFish act-removeSwimlane.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)"
        self.check_webhook(
            "remove_swimlane",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_removed_checklist_item_message(self) -> None:
        expected_message = "JohnFish act-removedChecklistItem.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.check_webhook(
            "removed_checklist_item",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_removed_checklist_message(self) -> None:
        expected_message = 'JohnFish removed checklist "To do" from card "Markdown and emoji\'s" at list "Design" at swimlane "Default" at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "removed_checklist",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_restored_card_message(self) -> None:
        expected_message = 'JohnFish restored card "Markdown and emoji\'s" to list "Design" at swimlane "Default" at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "restored_card",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_set_custom_field_message(self) -> None:
        expected_message = "JohnFish act-setCustomField.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.check_webhook(
            "set_custom_field",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_uncomplete_checklist_message(self) -> None:
        expected_message = 'JohnFish uncompleted checklist To do at card "Markdown and emoji\'s" at list "Design" at swimlane "Default" at board "Bucket List".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)'
        self.check_webhook(
            "uncomplete_checklist",
            "Wekan Notification",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    @override
    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("wekan", fixture_name, file_type="json")
