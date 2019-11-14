from zerver.lib.test_classes import WebhookTestCase

class WekanHookTests(WebhookTestCase):
    STREAM_NAME = 'wekan'
    URL_TEMPLATE = '/api/v1/external/wekan?stream={stream}&api_key={api_key}'
    FIXTURE_DIR_NAME = 'wekan'

    def test_add_attachment_message(self) -> None:
        expected_message = u"JohnFish added attachment \"hGfm5ksud8k\" to card \"Markdown and emoji's\" at list \"Design\" at swimlane \"Default\" at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('add_attachment', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_add_checklist_item_message(self) -> None:
        expected_message = u"JohnFish added checklist item \"merge commit 9dfe\" to checklist \"To do\" at card \"Markdown and emoji's\" at list \"Design\" at swimlane \"Default\" at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('add_checklist_item', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_add_checklist_message(self) -> None:
        expected_message = u"JohnFish added checklist \"To do\" to card \"Markdown and emoji's\" at list \"Design\" at swimlane \"Default\" at board \"bucked-list\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('add_checklist', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_add_label_message(self) -> None:
        expected_message = u"JohnFish Added label Language to card \"Markdown & emojis\" at list \"Design\" at swimlane \"Default\" at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/TMmjFnQGuZPsbjXzS)"
        self.send_and_test_stream_message('add_label', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_archived_swimlane_message(self) -> None:
        expected_message = u"JohnFish Swimlane \"Default\" at board \"Bucket List\" moved to Archive.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)"
        self.send_and_test_stream_message('archived_swimlane', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_archived_card_message(self) -> None:
        expected_message = u"JohnFish Card \"Markdown and emoji's\" at list \"Design\" at swimlane \"Default\" at board \"Bucket List\" moved to Archive.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('archived_card', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_archived_list_message(self) -> None:
        expected_message = u"JohnFish List \"Design\" at swimlane \"Default\" at board \"Bucket List\" moved to Archive.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)"
        self.send_and_test_stream_message('archived_list', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_checked_item_message(self) -> None:
        expected_message = u"JohnFish checked To do of checklist \"To do\" at card \"Markdown and emoji's\" at list \"Design\" at swimlane \"Default\" at board \"bucket-list\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('checked_item', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_add_comment_message(self) -> None:
        expected_message = u"JohnFish commented on card \"Markdown and emoji's\": \"This feature is important\" at list \"Design\" at swimlane \"Default\" at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('add_comment', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_create_card_message(self) -> None:
        expected_message = u"JohnFish created card \"Markdown and emoji's\" to list \"Development & Implementation\" at swimlane \"Default\" at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('create_card', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_create_custom_field_message(self) -> None:
        expected_message = u"JohnFish created custom field Language at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)"
        self.send_and_test_stream_message('create_custom_field', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_create_list_message(self) -> None:
        expected_message = u"JohnFish added list \"Testing & Maintenance\" to board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)"
        self.send_and_test_stream_message('create_list', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_create_swimlane_message(self) -> None:
        expected_message = u"JohnFish created swimlane \"Jasper\" to board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)"
        self.send_and_test_stream_message('create_swimlane', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_delete_attachment_message(self) -> None:
        expected_message = u"JohnFish deleted attachment \"hGfm5ksud8k.jpg\" at card \"Markdown and emoji's\" at list \"Design\" at swimlane \"Default\" at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('delete_attachment', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_join_member_message(self) -> None:
        expected_message = u"JohnFish added member kokoboss to card \"Markdown & emojis\" at list \"Design\" at swimlane \"Default\" at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/TMmjFnQGuZPsbjXzS)"
        self.send_and_test_stream_message('join_member', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_move_card_message(self) -> None:
        expected_message = u"JohnFish moved card \"Markdown and emoji's\" at board \"Bucket List\" from list \"Development & Implementation\" at swimlane \"Default\" to list \"Design\" at swimlane \"Default\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('move_card', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_remove_list_message(self) -> None:
        expected_message =  u"JohnFish act-removeList.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)"
        self.send_and_test_stream_message('remove_list', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_remove_swimlane_message(self) -> None:
        expected_message = u"JohnFish act-removeSwimlane.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list)"
        self.send_and_test_stream_message('remove_swimlane', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_removed_checklist_item_message(self) -> None:
        expected_message = u"JohnFish act-removedChecklistItem.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('removed_checklist_item', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_removed_checklist_message(self) -> None:
        expected_message = u"JohnFish removed checklist \"To do\" from card \"Markdown and emoji's\" at list \"Design\" at swimlane \"Default\" at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('removed_checklist', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_restored_card_message(self) -> None:
        expected_message = u"JohnFish restored card \"Markdown and emoji's\" to list \"Design\" at swimlane \"Default\" at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('restored_card', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_set_custom_field_message(self) -> None:
        expected_message = u"JohnFish act-setCustomField.\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('set_custom_field', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def test_uncomplete_checklist_message(self) -> None:
        expected_message = u"JohnFish uncompleted checklist To do at card \"Markdown and emoji's\" at list \"Design\" at swimlane \"Default\" at board \"Bucket List\".\n\n[See in Wekan](http://127.0.0.1/b/Jinj4Xj7qnHLRmrTY/bucket-list/pMtu7kPZvMuhhC4hL)"
        self.send_and_test_stream_message('uncomplete_checklist', u'Wekan Notification' , expected_message,
                                            content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("wekan", fixture_name, file_type="json")
