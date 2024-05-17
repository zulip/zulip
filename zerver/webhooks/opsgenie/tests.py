from zerver.lib.test_classes import WebhookTestCase


class OpsgenieHookTests(WebhookTestCase):
    CHANNEL_NAME = "opsgenie"
    URL_TEMPLATE = "/api/v1/external/opsgenie?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "opsgenie"

    def test_acknowledge_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: Acknowledge
* **Message**: test alert
* **Tags**: `tag1`, `tag2`
""".strip()

        self.check_webhook(
            "acknowledge",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_addnote_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: AddNote
* **Note**: note to test alert
* **Message**: test alert
* **Tags**: `tag1`, `tag2`
""".strip()

        self.check_webhook(
            "addnote",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_addrecipient_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: AddRecipient
* **Recipient**: team2_escalation
* **Message**: test alert
* **Tags**: `tag1`, `tag2`
""".strip()

        self.check_webhook(
            "addrecipient",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_addtags_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: AddTags
* **Tags added**: tag1,tag2,tag3
* **Message**: test alert
* **Tags**: `tag1`, `tag2`, `tag3`
""".strip()

        self.check_webhook(
            "addtags",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_addteam_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: AddTeam
* **Team added**: team2
* **Message**: test alert
* **Tags**: `tag1`, `tag2`
""".strip()

        self.check_webhook(
            "addteam",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_assignownership_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: AssignOwnership
* **Assigned owner**: user2@ifountain.com
* **Message**: test alert
* **Tags**: `tag1`, `tag2`
""".strip()

        self.check_webhook(
            "assignownership",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_close_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: Close
* **Message**: test alert
""".strip()

        self.check_webhook(
            "close",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_create_alert(self) -> None:
        expected_topic_name = "Webhook"
        expected_message = """
[Opsgenie alert for Webhook](https://app.opsgenie.com/alert/V2#/show/ec03dad6-62c8-4c94-b38b-d88f398e900f):
* **Type**: Create
* **Message**: another alert
* **Tags**: `vip`
""".strip()

        self.check_webhook(
            "create",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_customaction_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: TestAction
* **Message**: test alert
* **Tags**: `tag1`, `tag2`
""".strip()

        self.check_webhook(
            "customaction",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_delete_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: Delete
* **Message**: test alert
""".strip()

        self.check_webhook(
            "delete",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_escalate_alert(self) -> None:
        expected_topic_name = "Webhook_Test"
        expected_message = """
[Opsgenie alert for Webhook_Test](https://app.opsgenie.com/alert/V2#/show/7ba97e3a-d328-4b5e-8f9a-39e945a3869a):
* **Type**: Escalate
* **Escalation**: test_esc
""".strip()

        self.check_webhook(
            "escalate",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_removetags_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: RemoveTags
* **Tags removed**: tag3
* **Message**: test alert
* **Tags**: `tag1`, `tag2`
""".strip()

        self.check_webhook(
            "removetags",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_takeownership_alert(self) -> None:
        expected_topic_name = "Webhook"
        expected_message = """
[Opsgenie alert for Webhook](https://app.opsgenie.com/alert/V2#/show/8a745a79-3ed3-4044-8427-98e067c0623c):
* **Type**: TakeOwnership
* **Message**: message test
* **Tags**: `tag1`, `tag2`
""".strip()

        self.check_webhook(
            "takeownership",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_unacknowledge_alert(self) -> None:
        expected_topic_name = "Integration1"
        expected_message = """
[Opsgenie alert for Integration1](https://app.opsgenie.com/alert/V2#/show/052652ac-5d1c-464a-812a-7dd18bbfba8c):
* **Type**: UnAcknowledge
* **Message**: test alert
* **Tags**: `tag1`, `tag2`
""".strip()

        self.check_webhook(
            "unacknowledge",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
