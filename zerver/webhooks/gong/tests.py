from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.validator import wrap_wild_value
from zerver.webhooks.gong.view import duration_pretty, format_participant


class GongHookTests(WebhookTestCase):
    def test_gong_normal_call_payload(self) -> None:
        expected_topic = "Gong Call: Ron/Speedman"
        expected_message = """\
:phone: Gong call completed: **[Ron/Speedman](http://local.gong-it.net:8080/call?id=5599332235511222771)**! :phone:

**Call time:** <time:2019-10-18T14:03:37-07:00> to <time:2019-10-18T14:39:36-07:00> (36 minutes)
**Scheduled time**: <time:2019-10-18T14:00:00-07:00>
**Participants**:
* Deshon White: Sales Enablement Manager - Sales Development (deshon.white@acme.com)
* Jennifer Band: Customer Success Manager (jennifer.band@fasttrail.com)"""

        self.check_webhook(
            "gong_payload",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_gong_test_call_payload(self) -> None:
        expected_topic = "Gong call test"
        expected_message = ":phone: Gong webhook test received! :phone:"

        self.check_webhook(
            "gong_test_payload",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_missing_isTest_status(self) -> None:
        webhook_result = self.client_post(
            self.url,
            {},
            content_type="application/json",
        )
        self.assert_json_error(
            webhook_result, "Unable to parse request: Did Gong generate this event?"
        )

    def test_missing_callData_status(self) -> None:
        webhook_result = self.client_post(
            self.url,
            {"isTest": False},
            content_type="application/json",
        )
        self.assert_json_error(
            webhook_result, "Unable to parse request: Did Gong generate this event?"
        )

    def test_format_participant(self) -> None:
        test_name = "Jennifer Band"
        test_title = "Customer Success Manager"
        test_email = "jennifer.band@fasttrail.com"
        test_phone = "5556543210"
        only_name = wrap_wild_value(
            "party",
            {
                "name": test_name,
            },
        )
        title_only = wrap_wild_value(
            "party",
            {
                "name": test_name,
                "title": test_title,
            },
        )
        email_only = wrap_wild_value(
            "party",
            {
                "name": test_name,
                "emailAddress": test_email,
            },
        )
        phone_only = wrap_wild_value(
            "party",
            {
                "name": test_name,
                "phoneNumber": test_phone,
            },
        )
        title_and_email = wrap_wild_value(
            "party",
            {
                "name": test_name,
                "title": test_title,
                "emailAddress": test_email,
            },
        )
        title_and_phone = wrap_wild_value(
            "party",
            {
                "name": test_name,
                "title": test_title,
                "phoneNumber": test_phone,
            },
        )
        email_and_phone = wrap_wild_value(
            "party",
            {
                "name": test_name,
                "emailAddress": test_email,
                "phoneNumber": test_phone,
            },
        )
        all_fields = wrap_wild_value(
            "party",
            {
                "name": test_name,
                "title": test_title,
                "emailAddress": test_email,
                "phoneNumber": test_phone,
            },
        )
        self.assertEqual(format_participant(only_name), f"* {test_name}")
        self.assertEqual(format_participant(title_only), f"* {test_name}: {test_title}")
        self.assertEqual(format_participant(email_only), f"* {test_name} ({test_email})")
        self.assertEqual(format_participant(phone_only), f"* {test_name} ({test_phone})")
        self.assertEqual(
            format_participant(title_and_email), f"* {test_name}: {test_title} ({test_email})"
        )
        self.assertEqual(
            format_participant(title_and_phone), f"* {test_name}: {test_title} ({test_phone})"
        )
        self.assertEqual(
            format_participant(email_and_phone), f"* {test_name} ({test_email}, {test_phone})"
        )
        self.assertEqual(
            format_participant(all_fields),
            f"* {test_name}: {test_title} ({test_email}, {test_phone})",
        )

    def test_duration_pretty(self) -> None:
        self.assertEqual(duration_pretty(0), "0 minutes")
        self.assertEqual(duration_pretty(60), "1 minute")
        self.assertEqual(duration_pretty(3600), "1 hour")
        self.assertEqual(duration_pretty(3661), "1 hour 1 minute")
        self.assertEqual(duration_pretty(7200), "2 hours")
        self.assertEqual(duration_pretty(7320), "2 hours 2 minutes")
        self.assertEqual(duration_pretty(1), "0 minutes")
        self.assertEqual(duration_pretty(3599), "1 hour")
        self.assertEqual(duration_pretty(3645), "1 hour 1 minute")
