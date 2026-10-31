import orjson

from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.famulor.view import format_duration

CALL_ID = "c1b2c3d4-0000-4000-8000-000000000010"
CALL_TOPIC = f"Call {CALL_ID}"
CALL_SUMMARY = """
**Duration**: 2 minutes 12 seconds
**Summary**: Customer confirmed interest and booked a demo.
**Outcome**: Appointment booked
**Sentiment**: positive
**Success**: yes
""".strip()
CALL_VARIABLES = """
**Collected**:
* appointment_time: 2026-09-02T10:00:00Z

**Variables**:
* lead_quality: high

**Input variables**:
* customer_name: Max Mustermann
""".strip()
BOOKING_INVITEE = "**Invitee**: Anna Schmidt (anna@example.com, +4915123456789)"
BOOKING_WHEN = "**When**: <time:2026-08-14T09:00:00+00:00> to <time:2026-08-14T09:30:00+00:00>"
BOOKING_DETAILS = f"""
{BOOKING_INVITEE}
**Invitee timezone**: Europe/Berlin
{BOOKING_WHEN}
**Status**: confirmed
**Source**: call
**Call**: {CALL_ID}
**Notes**: Booked during the call.
""".strip()


class FamulorHookTests(WebhookTestCase):
    def test_call_completed(self) -> None:
        expected_message = f"**Outbound** call **completed**.\n\n{CALL_SUMMARY}\n\n{CALL_VARIABLES}"
        self.check_webhook(
            "call_completed",
            CALL_TOPIC,
            expected_message,
            content_type="application/json",
        )

    def test_call_completed_with_failure(self) -> None:
        payload = orjson.loads(self.get_body("call_completed"))
        payload["data"]["status"] = "no_answer"
        payload["data"]["failure"] = {
            "operation": "outbound_call",
            "code": "no_answer",
            "message": "The destination did not answer before the call timed out.",
            "retryable": True,
            "action": "retry_later",
        }
        expected_message = f"""
**Outbound** call **no answer**.

**Duration**: 2 minutes 12 seconds
**Summary**: Customer confirmed interest and booked a demo.
**Outcome**: Appointment booked
**Sentiment**: positive
**Success**: yes
**Failure (outbound_call)**: The destination did not answer before the call timed out. (no_answer)
**Retryable**: yes
**Suggested action**: retry later

{CALL_VARIABLES}
""".strip()
        self.check_webhook(
            "call_completed",
            CALL_TOPIC,
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_call_completed_unsuccessful(self) -> None:
        payload = orjson.loads(self.get_body("call_completed"))
        payload["data"]["analysis"]["success"] = False
        payload["data"]["failure"] = {
            "code": "no_answer",
            "retryable": False,
        }
        expected_message = f"""
**Outbound** call **completed**.

**Duration**: 2 minutes 12 seconds
**Summary**: Customer confirmed interest and booked a demo.
**Outcome**: Appointment booked
**Sentiment**: positive
**Success**: no
**Failure**: no_answer
**Retryable**: no

{CALL_VARIABLES}
""".strip()
        self.check_webhook(
            "call_completed",
            CALL_TOPIC,
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_call_completed_failure_message_only(self) -> None:
        payload = orjson.loads(self.get_body("call_completed"))
        del payload["data"]["analysis"]["success"]
        payload["data"]["failure"] = {
            "operation": "warm_transfer",
            "message": "The transfer target did not answer.",
            "action": "retry_later",
        }
        expected_message = f"""
**Outbound** call **completed**.

**Duration**: 2 minutes 12 seconds
**Summary**: Customer confirmed interest and booked a demo.
**Outcome**: Appointment booked
**Sentiment**: positive
**Failure (warm_transfer)**: The transfer target did not answer.
**Suggested action**: retry later

{CALL_VARIABLES}
""".strip()
        self.check_webhook(
            "call_completed",
            CALL_TOPIC,
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_call_completed_failure_without_detail(self) -> None:
        payload = orjson.loads(self.get_body("call_completed"))
        payload["data"]["failure"] = {
            "operation": "outbound_call",
            "code": "",
            "message": "   ",
            "retryable": True,
            "action": "retry_later",
        }
        expected_message = f"**Outbound** call **completed**.\n\n{CALL_SUMMARY}\n\n{CALL_VARIABLES}"
        self.check_webhook(
            "call_completed",
            CALL_TOPIC,
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_call_completed_with_phone_numbers_and_recording(self) -> None:
        payload = orjson.loads(self.get_body("call_completed"))
        payload["data"]["from_number"] = "+4912345678"
        payload["data"]["to_number"] = "+4915123456789"
        payload["data"]["recording_url"] = "https://recordings.famulor.de/call-480336.mp3"
        expected_message = f"""
**Outbound** call **completed**.

**Duration**: 2 minutes 12 seconds
**From**: +4912345678
**To**: +4915123456789
**Recording**: [Recording](https://recordings.famulor.de/call-480336.mp3)
**Summary**: Customer confirmed interest and booked a demo.
**Outcome**: Appointment booked
**Sentiment**: positive
**Success**: yes

{CALL_VARIABLES}
""".strip()
        self.check_webhook(
            "call_completed",
            "+4915123456789",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_inbound_call(self) -> None:
        payload = orjson.loads(self.get_body("call_completed"))
        payload["data"]["direction"] = "inbound"
        payload["data"]["from_number"] = "+493012345678"
        payload["data"]["to_number"] = "+498998765432"
        expected_message = f"""
**Inbound** call **completed**.

**Duration**: 2 minutes 12 seconds
**From**: +493012345678
**To**: +498998765432
**Summary**: Customer confirmed interest and booked a demo.
**Outcome**: Appointment booked
**Sentiment**: positive
**Success**: yes

{CALL_VARIABLES}
""".strip()
        self.check_webhook(
            "call_completed",
            "+493012345678",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_call_completed_without_optional_details(self) -> None:
        payload = orjson.loads(self.get_body("call_completed"))
        for key in ("direction", "analysis", "collected", "variables", "input_variables"):
            del payload["data"][key]
        self.check_webhook(
            "call_completed",
            CALL_TOPIC,
            "Call **completed**.\n\n**Duration**: 2 minutes 12 seconds",
            content_type="application/json",
            custom_payload=payload,
        )

    def test_call_completed_without_call_id(self) -> None:
        payload = orjson.loads(self.get_body("call_completed"))
        del payload["data"]["call_id"]
        payload["data"]["collected"]["notes"] = None
        payload["data"]["collected"]["transcript"] = {"items": []}
        payload["data"]["variables"]["tags"] = ["vip"]
        expected_message = f"**Outbound** call **completed**.\n\n{CALL_SUMMARY}\n\n{CALL_VARIABLES}"
        self.check_webhook(
            "call_completed",
            "Famulor call",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_legacy_post_call(self) -> None:
        expected_message = """
Call **completed**.

**Duration**: 3 minutes
**Customer phone**: +4915123456789
**Assistant phone**: +4912345678
**Recording**: [Recording](https://recordings.famulor.de/call-480336.mp3)
**Campaign**: New Customer Acquisition Q1 2024
**Lead**: +4915123456789 (contacted)

**Input variables**:
* customer_name: Max Mustermann
* company: Beispiel GmbH

**Extracted variables**:
* customer_interested: yes
* appointment_scheduled: no
* contact_reason: product_inquiry
* follow_up_needed: yes
* customer_budget: 10000-50000
* decision_maker: yes
* next_contact_date: 2024-02-15
""".strip()
        self.check_webhook(
            "legacy_post_call",
            "+4915123456789",
            expected_message,
            content_type="application/json",
        )

    def test_legacy_post_call_without_lead(self) -> None:
        expected_message = """
Call **completed**.

**Duration**: 2 minutes
**Customer phone**: +4917123456789
**Assistant phone**: +4912345678

**Extracted variables**:
* issue_resolved: yes
* customer_satisfaction: 9
* support_category: technical
""".strip()
        self.check_webhook(
            "legacy_post_call_without_lead",
            "+4917123456789",
            expected_message,
            content_type="application/json",
        )

    def test_legacy_post_call_lead_without_status(self) -> None:
        payload = orjson.loads(self.get_body("legacy_post_call"))
        del payload["lead"]["status"]
        expected_message = """
Call **completed**.

**Duration**: 3 minutes
**Customer phone**: +4915123456789
**Assistant phone**: +4912345678
**Recording**: [Recording](https://recordings.famulor.de/call-480336.mp3)
**Campaign**: New Customer Acquisition Q1 2024
**Lead**: +4915123456789

**Input variables**:
* customer_name: Max Mustermann
* company: Beispiel GmbH

**Extracted variables**:
* customer_interested: yes
* appointment_scheduled: no
* contact_reason: product_inquiry
* follow_up_needed: yes
* customer_budget: 10000-50000
* decision_maker: yes
* next_contact_date: 2024-02-15
""".strip()
        self.check_webhook(
            "legacy_post_call",
            "+4915123456789",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_legacy_post_call_busy_without_phone(self) -> None:
        payload = orjson.loads(self.get_body("legacy_post_call_without_lead"))
        payload["status"] = "busy"
        payload["customer_phone"] = None
        expected_message = """
Call **busy**.

**Duration**: 2 minutes
**Assistant phone**: +4912345678

**Extracted variables**:
* issue_resolved: yes
* customer_satisfaction: 9
* support_category: technical
""".strip()
        self.check_webhook(
            "legacy_post_call_without_lead",
            "Call 480337",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_legacy_extracted_variables_are_capped(self) -> None:
        payload = orjson.loads(self.get_body("legacy_post_call"))
        payload["extracted_variables"]["score"] = 1.5
        payload["extracted_variables"]["extra_note"] = "later"
        expected_message = """
Call **completed**.

**Duration**: 3 minutes
**Customer phone**: +4915123456789
**Assistant phone**: +4912345678
**Recording**: [Recording](https://recordings.famulor.de/call-480336.mp3)
**Campaign**: New Customer Acquisition Q1 2024
**Lead**: +4915123456789 (contacted)

**Input variables**:
* customer_name: Max Mustermann
* company: Beispiel GmbH

**Extracted variables**:
* customer_interested: yes
* appointment_scheduled: no
* contact_reason: product_inquiry
* follow_up_needed: yes
* customer_budget: 10000-50000
* decision_maker: yes
* next_contact_date: 2024-02-15
* score: 1.5
* and 1 field
""".strip()
        self.check_webhook(
            "legacy_post_call",
            "+4915123456789",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_conversation_ended_widget(self) -> None:
        expected_message = """
**Widget** conversation **ended** (8 messages).

**Customer**: John Doe
**Summary**: Customer asked about pricing plans and was interested in the Pro plan
**Objective**: achieved

**Input variables**:
* name: John Doe
* email: john@example.com
""".strip()
        self.check_webhook(
            "conversation_ended_widget",
            "John Doe",
            expected_message,
            content_type="application/json",
        )

    def test_conversation_ended_not_achieved(self) -> None:
        payload = orjson.loads(self.get_body("conversation_ended_widget"))
        payload["extracted_variables"]["status"] = False
        payload["customer_name"] = None
        payload["message_count"] = 1
        expected_message = """
**Widget** conversation **ended** (1 message).

**Summary**: Customer asked about pricing plans and was interested in the Pro plan
**Objective**: not achieved

**Input variables**:
* name: John Doe
* email: john@example.com
""".strip()
        self.check_webhook(
            "conversation_ended_widget",
            "Conversation a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_conversation_ended_whatsapp(self) -> None:
        expected_message = """
**WhatsApp** conversation **ended** (12 messages).

**Phone**: +1234567890
**Sender**: My Business (+19876543210)
**Summary**: Customer scheduled an appointment for next week
**Objective**: achieved

**Attachments**:
* [appointment-form.jpg](https://storage.famulor.de/conversations/attachments/abc123.jpg)
""".strip()
        self.check_webhook(
            "conversation_ended_whatsapp",
            "+1234567890",
            expected_message,
            content_type="application/json",
        )

    def test_conversation_ended_with_numeric_id(self) -> None:
        payload = orjson.loads(self.get_body("conversation_ended_widget"))
        payload["conversation_id"] = None
        payload["customer_name"] = None
        expected_message = """
**Widget** conversation **ended** (8 messages).

**Summary**: Customer asked about pricing plans and was interested in the Pro plan
**Objective**: achieved

**Input variables**:
* name: John Doe
* email: john@example.com
""".strip()
        self.check_webhook(
            "conversation_ended_widget",
            "Conversation 1042",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_conversation_sender_name_only(self) -> None:
        payload = orjson.loads(self.get_body("conversation_ended_whatsapp"))
        payload["sender"] = {"display_name": "My Business"}
        expected_message = """
**WhatsApp** conversation **ended** (12 messages).

**Phone**: +1234567890
**Sender**: My Business
**Summary**: Customer scheduled an appointment for next week
**Objective**: achieved

**Attachments**:
* [appointment-form.jpg](https://storage.famulor.de/conversations/attachments/abc123.jpg)
""".strip()
        self.check_webhook(
            "conversation_ended_whatsapp",
            "+1234567890",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_conversation_extracted_variables(self) -> None:
        payload = orjson.loads(self.get_body("conversation_ended_widget"))
        payload["extracted_variables"]["plan"] = "Pro"
        payload["extracted_variables"]["budget"] = None
        payload["extracted_variables"]["metadata"] = {"tier": "pro"}
        payload["extracted_variables"]["tags"] = ["vip"]
        payload["extracted_variables"]["blank"] = "   "
        expected_message = """
**Widget** conversation **ended** (8 messages).

**Customer**: John Doe
**Summary**: Customer asked about pricing plans and was interested in the Pro plan
**Objective**: achieved

**Extracted variables**:
* plan: Pro

**Input variables**:
* name: John Doe
* email: john@example.com
""".strip()
        self.check_webhook(
            "conversation_ended_widget",
            "John Doe",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_conversation_attachments_without_url(self) -> None:
        payload = orjson.loads(self.get_body("conversation_ended_whatsapp"))
        payload["attachments"] = [
            None,
            {"filename": "invoice.pdf", "type": "document"},
            {"type": "audio"},
        ]
        expected_message = """
**WhatsApp** conversation **ended** (12 messages).

**Phone**: +1234567890
**Sender**: My Business (+19876543210)
**Summary**: Customer scheduled an appointment for next week
**Objective**: achieved

**Attachments**:
* invoice.pdf
* audio
""".strip()
        self.check_webhook(
            "conversation_ended_whatsapp",
            "+1234567890",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_conversation_ended_event(self) -> None:
        self.check_webhook(
            "conversation_ended",
            "Conversation c1b2c3d4-0000-4000-8000-000000000010",
            "**conversation** conversation **closed** (6 messages).",
            content_type="application/json",
        )

    def test_booking_created(self) -> None:
        expected_message = f"**Intro call** booked.\n\n{BOOKING_DETAILS}"
        self.check_webhook(
            "booking_created",
            "Anna Schmidt",
            expected_message,
            content_type="application/json",
        )

    def test_booking_created_with_answers(self) -> None:
        payload = orjson.loads(self.get_body("booking_created"))
        payload["data"]["answers"] = {"company": "Beispiel GmbH"}
        expected_message = f"""
**Intro call** booked.

{BOOKING_DETAILS}

**Answers**:
* company: Beispiel GmbH
""".strip()
        self.check_webhook(
            "booking_created",
            "Anna Schmidt",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_booking_cancelled(self) -> None:
        payload = orjson.loads(self.get_body("booking_created"))
        payload["event"] = "booking.cancelled"
        payload["data"]["status"] = "cancelled"
        del payload["data"]["event_type_name"]
        expected_message = f"""
**intro-call** cancelled.

{BOOKING_INVITEE}
**Invitee timezone**: Europe/Berlin
{BOOKING_WHEN}
**Status**: cancelled
**Source**: call
**Call**: {CALL_ID}
**Notes**: Booked during the call.
""".strip()
        self.check_webhook(
            "booking_created",
            "Anna Schmidt",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_booking_rescheduled(self) -> None:
        payload = orjson.loads(self.get_body("booking_created"))
        payload["event"] = "booking.rescheduled"
        payload["data"]["previous_start_time"] = "2026-08-13T09:00:00Z"
        expected_message = f"""
**Intro call** rescheduled.

{BOOKING_INVITEE}
**Invitee timezone**: Europe/Berlin
**Previous start**: <time:2026-08-13T09:00:00+00:00>
{BOOKING_WHEN}
**Status**: confirmed
**Source**: call
**Call**: {CALL_ID}
**Notes**: Booked during the call.
""".strip()
        self.check_webhook(
            "booking_created",
            "Anna Schmidt",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_booking_without_event_type_or_invitee(self) -> None:
        payload = orjson.loads(self.get_body("booking_created"))
        for key in ("event_type_name", "event_type_slug", "invitee", "notes", "call_id"):
            del payload["data"][key]
        payload["data"]["end_time"] = None
        expected_message = """
Booking booked.

**When**: <time:2026-08-14T09:00:00+00:00>
**Status**: confirmed
**Source**: call
""".strip()
        self.check_webhook(
            "booking_created",
            "Booking 5c9f6e2a-4b1d-4b7a-9c1e-8f2a1b3c4d5e",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_booking_with_unparsed_times(self) -> None:
        payload = orjson.loads(self.get_body("booking_created"))
        payload["data"]["previous_start_time"] = "yesterday"
        payload["data"]["start_time"] = "2026-08-14T09:00:00"
        payload["data"]["end_time"] = "later today"
        expected_message = f"""
**Intro call** booked.

{BOOKING_INVITEE}
**Invitee timezone**: Europe/Berlin
**Previous start**: yesterday
**When**: 2026-08-14T09:00:00 to later today
**Status**: confirmed
**Source**: call
**Call**: {CALL_ID}
**Notes**: Booked during the call.
""".strip()
        self.check_webhook(
            "booking_created",
            "Anna Schmidt",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_booking_invitee_without_name(self) -> None:
        payload = orjson.loads(self.get_body("booking_created"))
        del payload["data"]["invitee"]["name"]
        del payload["data"]["invitee"]["phone"]
        expected_message = f"""
**Intro call** booked.

**Invitee**: anna@example.com
**Invitee timezone**: Europe/Berlin
{BOOKING_WHEN}
**Status**: confirmed
**Source**: call
**Call**: {CALL_ID}
**Notes**: Booked during the call.
""".strip()
        self.check_webhook(
            "booking_created",
            "Intro call",
            expected_message,
            content_type="application/json",
            custom_payload=payload,
        )

    def test_exclude_call_completed(self) -> None:
        self.url = self.build_webhook_url() + '&exclude_events=["call.completed"]'
        self.check_webhook("call_completed", expect_noop=True, content_type="application/json")

    def test_call_variables_unsupported(self) -> None:
        result = self.client_post(
            self.url,
            self.get_body("call_variables"),
            content_type="application/json",
        )
        self.assert_json_success(result)
        self.assert_in_response(
            "The 'call.variables' event isn't currently supported by the Famulor webhook; ignoring",
            result,
        )

    def test_conversation_ended_without_documented_body(self) -> None:
        result = self.client_post(
            self.url,
            {"event": "conversation.ended", "data": {}},
            content_type="application/json",
        )
        self.assert_json_success(result)
        self.assert_in_response(
            "The 'conversation.ended' event isn't currently supported by the Famulor webhook; "
            "ignoring",
            result,
        )

    def test_anomalous_payload(self) -> None:
        result = self.client_post(self.url, {}, content_type="application/json")
        self.assert_json_error(result, "Unable to parse request: Did Famulor generate this event?")

    def test_format_duration(self) -> None:
        test_cases = [
            (0, "0 seconds"),
            (1, "1 second"),
            (45, "45 seconds"),
            (60, "1 minute"),
            (132, "2 minutes 12 seconds"),
            (180, "3 minutes"),
            (3600, "1 hour"),
            (3661, "1 hour 1 minute 1 second"),
            (7320, "2 hours 2 minutes"),
        ]
        for seconds, expected in test_cases:
            with self.subTest(seconds=seconds):
                self.assertEqual(format_duration(seconds), expected)
