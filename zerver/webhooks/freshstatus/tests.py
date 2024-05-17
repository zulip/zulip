from zerver.lib.send_email import FromAddress
from zerver.lib.test_classes import WebhookTestCase
from zerver.models import Recipient
from zerver.webhooks.freshstatus.view import MISCONFIGURED_PAYLOAD_ERROR_MESSAGE


class FreshstatusHookTests(WebhookTestCase):
    CHANNEL_NAME = "freshstatus"
    URL_TEMPLATE = "/api/v1/external/freshstatus?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "freshstatus"

    def test_freshstatus_incident_open_multiple_services(self) -> None:
        """
        Tests if freshstatus incident open multiple services is handled correctly
        """
        expected_topic_name = "Degradation of Multiple Servers"
        expected_message = """
The following incident has been opened: **Degradation of Multiple Servers**
**Description:** This issue is being investigated.
**Start Time:** 2021-04-12 16:29 UTC
**Affected Services:**
* Database Server
* Web Server
* Web Server 2
        """.strip()
        self.check_webhook(
            "freshstatus_incident_open_multiple_services", expected_topic_name, expected_message
        )

    def test_freshstatus_incident_open_multiple_services_over_limit(self) -> None:
        """
        Tests if freshstatus incident open multiple services over limit is handled correctly
        """
        expected_topic_name = "Degradation of Multiple Servers"
        expected_message = """
The following incident has been opened: **Degradation of Multiple Servers**
**Description:** This issue is being investigated.
**Start Time:** 2021-04-12 16:29 UTC
**Affected Services:**
* Database Server
* Web Server
* Web Server 2
* Database Server 2
* Active Directory Server
[and 2 more service(s)]
        """.strip()
        self.check_webhook(
            "freshstatus_incident_open_multiple_services_over_limit",
            expected_topic_name,
            expected_message,
        )

    def test_freshstatus_incident_open(self) -> None:
        """
        Tests if freshstatus incident open is handled correctly
        """
        expected_topic_name = "Degradation of Database Server"
        expected_message = """
The following incident has been opened: **Degradation of Database Server**
**Description:** This issue is being investigated.
**Start Time:** 2021-04-12 16:29 UTC
**Affected Services:**
* Database Server
        """.strip()
        self.check_webhook("freshstatus_incident_open", expected_topic_name, expected_message)

    def test_freshstatus_incident_note_created(self) -> None:
        """
        Tests if freshstatus incident note created is handled correctly
        """
        expected_topic_name = "Degradation of Database Server"
        expected_message = """
The following note has been added to the incident: **Degradation of Database Server**
**Note:** The incident is being worked on.
        """.strip()
        self.check_webhook(
            "freshstatus_incident_note_created", expected_topic_name, expected_message
        )

    def test_freshstatus_incident_closed(self) -> None:
        """
        Tests if freshstatus incident closed is handled correctly
        """
        expected_topic_name = "Degradation of Database Server"
        expected_message = """
The following incident has been closed: **Degradation of Database Server**
**Note:** The incident has been resolved.
        """.strip()
        self.check_webhook("freshstatus_incident_closed", expected_topic_name, expected_message)

    def test_freshstatus_scheduled_maintenance_planned(self) -> None:
        """
        Tests if freshstatus scheduled maintenance planned is handled correctly
        """
        expected_topic_name = "Expect some services downtime due to server maintenance"
        expected_message = """
The following scheduled maintenance has been opened: **Expect some services downtime due to server maintenance**
**Description:** As part of the upgrade routine, we will be carrying out server maintenance work for this Service. This work will affect the Service to be unavailable during the maintenance window. We apologize for any inconvenience this may cause. Please do not hesitate to contact our support team at support@example.com if you have any questions regarding this server upgrading exercise.
**Scheduled Start Time:** 2021-04-12 17:08 UTC
**Scheduled End Time:** 2021-04-12 18:08 UTC
**Affected Services:**
* Sample Service
        """.strip()
        self.check_webhook(
            "freshstatus_scheduled_maintenance_planned", expected_topic_name, expected_message
        )

    def test_freshstatus_scheduled_maintenance_planned_multiple_services(self) -> None:
        """
        Tests if freshstatus scheduled maintenance planned multiple services is handled correctly
        """
        expected_topic_name = "Expect some services downtime due to server maintenance"
        expected_message = """
The following scheduled maintenance has been opened: **Expect some services downtime due to server maintenance**
**Description:** As part of the upgrade routine, we will be carrying out server maintenance work for this Service. This work will affect the Service to be unavailable during the maintenance window. We apologize for any inconvenience this may cause. Please do not hesitate to contact our support team at support@example.com if you have any questions regarding this server upgrading exercise.
**Scheduled Start Time:** 2021-04-12 17:08 UTC
**Scheduled End Time:** 2021-04-12 18:08 UTC
**Affected Services:**
* Sample Service
* Sample Service 2
        """.strip()
        self.check_webhook(
            "freshstatus_scheduled_maintenance_planned_multiple_services",
            expected_topic_name,
            expected_message,
        )

    def test_freshstatus_scheduled_maintenance_planned_multiple_services_over_limit(self) -> None:
        """
        Tests if freshstatus scheduled maintenance planned multiple services over limit is handled correctly
        """
        expected_topic_name = "Expect some services downtime due to server maintenance"
        expected_message = """
The following scheduled maintenance has been opened: **Expect some services downtime due to server maintenance**
**Description:** As part of the upgrade routine, we will be carrying out server maintenance work for this Service. This work will affect the Service to be unavailable during the maintenance window. We apologize for any inconvenience this may cause. Please do not hesitate to contact our support team at support@example.com if you have any questions regarding this server upgrading exercise.
**Scheduled Start Time:** 2021-04-12 17:08 UTC
**Scheduled End Time:** 2021-04-12 18:08 UTC
**Affected Services:**
* Sample Service
* Sample Service 2
* Sample Service 3
* Sample Service 4
* Sample Service 5
[and 2 more service(s)]
        """.strip()
        self.check_webhook(
            "freshstatus_scheduled_maintenance_planned_multiple_services_over_limit",
            expected_topic_name,
            expected_message,
        )

    def test_freshstatus_scheduled_maintenance_note_created(self) -> None:
        """
        Tests if freshstatus scheduled maintenance note created is handled correctly
        """
        expected_topic_name = "Scheduled Maintenance Test"
        expected_message = """
The following note has been added to the scheduled maintenance: **Scheduled Maintenance Test**
**Note:** We are about to start the maintenance.
        """.strip()
        self.check_webhook(
            "freshstatus_scheduled_maintenance_note_created", expected_topic_name, expected_message
        )

    def test_freshstatus_scheduled_maintenance_closed(self) -> None:
        """
        Tests if freshstatus scheduled maintenance closed is handled correctly
        """
        expected_topic_name = "Scheduled Maintenance Test"
        expected_message = """
The following scheduled maintenance has been closed: **Scheduled Maintenance Test**
**Note:** The maintenance is now complete.
        """.strip()
        self.check_webhook(
            "freshstatus_scheduled_maintenance_closed", expected_topic_name, expected_message
        )

    def test_freshstatus_test(self) -> None:
        """
        Tests if freshstatus test is handled correctly
        """
        expected_topic_name = "Freshstatus"
        expected_message = "Freshstatus webhook has been successfully configured."
        self.check_webhook("freshstatus_test", expected_topic_name, expected_message)

    def test_freshstatus_event_not_supported(self) -> None:
        """
        Tests if freshstatus event not supported is handled correctly
        """
        expected_topic_name = "Sample title"
        expected_message = "The event (INCIDENT_REOPEN) is not supported yet."
        self.check_webhook("freshstatus_event_not_supported", expected_topic_name, expected_message)

    def test_freshstatus_invalid_payload_with_missing_data(self) -> None:
        """
        Tests if invalid Freshstatus payloads are handled correctly
        """
        self.url = self.build_webhook_url()
        payload = self.get_body("freshstatus_invalid_payload_with_missing_data")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_error(result, "Invalid payload")

        expected_message = MISCONFIGURED_PAYLOAD_ERROR_MESSAGE.format(
            bot_name=self.test_user.full_name,
            support_email=FromAddress.SUPPORT,
        ).strip()

        msg = self.get_last_message()
        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.recipient.type, Recipient.PERSONAL)
