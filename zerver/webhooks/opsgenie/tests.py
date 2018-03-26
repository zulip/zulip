# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class OpsGenieHookTests(WebhookTestCase):
    STREAM_NAME = 'opsgenie'
    URL_TEMPLATE = "/api/v1/external/opsgenie?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'opsgenie'

    def test_acknowledge_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *Acknowledge*\n"
                            u"Message: *test alert*\n"
                            u"`tag1` `tag2`"
                            )
        self.send_and_test_stream_message('acknowledge', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_addnote_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *AddNote*\n"
                            u"Note: *note to test alert*\n"
                            u"Message: *test alert*\n"
                            u"`tag1` `tag2`"
                            )
        self.send_and_test_stream_message('addnote', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_addrecipient_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *AddRecipient*\n"
                            u"Recipient: *team2_escalation*\n"
                            u"Message: *test alert*\n"
                            u"`tag1` `tag2`"
                            )
        # use fixture named helloworld_hello
        self.send_and_test_stream_message('addrecipient', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_addtags_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *AddTags*\n"
                            u"Added tags: *tag1,tag2,tag3*\n"
                            u"Message: *test alert*\n"
                            u"`tag1` `tag2` `tag3`"
                            )
        self.send_and_test_stream_message('addtags', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_addteam_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *AddTeam*\n"
                            u"Added team: *team2*\n"
                            u"Message: *test alert*\n"
                            u"`tag1` `tag2`"
                            )
        self.send_and_test_stream_message('addteam', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_assignownership_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *AssignOwnership*\n"
                            u"Assigned owner: *user2@ifountain.com*\n"
                            u"Message: *test alert*\n"
                            u"`tag1` `tag2`"
                            )
        self.send_and_test_stream_message('assignownership', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_close_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *Close*\n"
                            u"Message: *test alert*"
                            )
        self.send_and_test_stream_message('close', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_create_alert(self) -> None:
        expected_subject = u"Webhook"
        expected_message = (u"**OpsGenie: [Alert for Webhook.](https://app.opsgenie.com/alert/V2#/show/ec03dad6-62c8-4c94-b38b-d88f398e900f)**\n"
                            u"Type: *Create*\n"
                            u"Message: *another alert*\n"
                            u"`vip`"
                            )
        self.send_and_test_stream_message('create', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_customaction_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *TestAction*\n"
                            u"Message: *test alert*\n"
                            u"`tag1` `tag2`"
                            )
        self.send_and_test_stream_message('customaction', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_delete_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *Delete*\n"
                            u"Message: *test alert*"
                            )
        self.send_and_test_stream_message('delete', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_escalate_alert(self) -> None:
        expected_subject = u"Webhook_Test"
        expected_message = (u"**OpsGenie: [Alert for Webhook_Test.](https://app.opsgenie.com/alert/V2#/show/7ba97e3a-d328-4b5e-8f9a-39e945a3869a)**\n"
                            u"Type: *Escalate*\n"
                            u"Escalation: *test_esc*"
                            )
        self.send_and_test_stream_message('escalate', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_removetags_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *RemoveTags*\n"
                            u"Removed tags: *tag3*\n"
                            u"Message: *test alert*\n"
                            u"`tag1` `tag2`"
                            )
        self.send_and_test_stream_message('removetags', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_takeownership_alert(self) -> None:
        expected_subject = u"Webhook"
        expected_message = (u"**OpsGenie: [Alert for Webhook.](https://app.opsgenie.com/alert/V2#/show/8a745a79-3ed3-4044-8427-98e067c0623c)**\n"
                            u"Type: *TakeOwnership*\n"
                            u"Message: *message test*\n"
                            u"`tag1` `tag2`"
                            )
        self.send_and_test_stream_message('takeownership', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_unacknowledge_alert(self) -> None:
        expected_subject = u"Integration1"
        expected_message = (u"**OpsGenie: [Alert for Integration1.](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c)**\n"
                            u"Type: *UnAcknowledge*\n"
                            u"Message: *test alert*\n"
                            u"`tag1` `tag2`"
                            )
        self.send_and_test_stream_message('unacknowledge', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("opsgenie", fixture_name, file_type="json")
