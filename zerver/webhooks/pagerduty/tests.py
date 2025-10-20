import hashlib
import hmac
from zerver.lib.test_classes import WebhookTestCase


class PagerDutyHookTests(WebhookTestCase):
    CHANNEL_NAME = "pagerduty"
    URL_TEMPLATE = "/api/v1/external/pagerduty?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "pagerduty"

    def test_trigger(self) -> None:
        expected_message = "Incident [3](https://zulip-test.pagerduty.com/incidents/P140S4Y) triggered by [Test service](https://zulip-test.pagerduty.com/services/PIL5CUQ) (assigned to [armooo](https://zulip-test.pagerduty.com/users/POBCFRJ)).\n\n``` quote\nfoo\n```"
        self.check_webhook("trigger", "Incident 3", expected_message)

    def test_trigger_v2(self) -> None:
        expected_message = "Incident [33](https://webdemo.pagerduty.com/incidents/PRORDTY) triggered by [Production XDB Cluster](https://webdemo.pagerduty.com/services/PN49J75) (assigned to [Laura Haley](https://webdemo.pagerduty.com/users/P553OPV)).\n\n``` quote\nMy new incident\n```"
        self.check_webhook("trigger_v2", "Incident 33", expected_message)

    def test_triggerer_v3(self) -> None:
        expected_message = "Incident [Test Incident 3 (#9)](https://pig208.pagerduty.com/incidents/PFQZPSY) triggered by [pig208](https://pig208.pagerduty.com/services/PA2P440) (assigned to [PIG 208](https://pig208.pagerduty.com/users/PJ0LVEB))."
        self.check_webhook("triggered_v3", "Incident Test Incident 3 (#9)", expected_message)

    def test_trigger_without_assignee_v2(self) -> None:
        expected_message = "Incident [33](https://webdemo.pagerduty.com/incidents/PRORDTY) triggered by [Production XDB Cluster](https://webdemo.pagerduty.com/services/PN49J75) (assigned to nobody).\n\n``` quote\nMy new incident\n```"
        self.check_webhook("trigger_without_assignee_v2", "Incident 33", expected_message)

    def test_unacknowledge(self) -> None:
        expected_message = "Incident [3](https://zulip-test.pagerduty.com/incidents/P140S4Y) unacknowledged by [Test service](https://zulip-test.pagerduty.com/services/PIL5CUQ) (assigned to [armooo](https://zulip-test.pagerduty.com/users/POBCFRJ)).\n\n``` quote\nfoo\n```"
        self.check_webhook("unacknowledge", "Incident 3", expected_message)

    def test_unacknowledged_v3(self) -> None:
        expected_message = "Incident [Test Incident (#10)](https://pig208.pagerduty.com/incidents/PQ1K5C8) unacknowledged by [pig208](https://pig208.pagerduty.com/services/PA2P440) (assigned to [PIG 208](https://pig208.pagerduty.com/users/PJ0LVEB))."
        self.check_webhook("unacknowledged_v3", "Incident Test Incident (#10)", expected_message)

    def test_resolved(self) -> None:
        expected_message = "Incident [1](https://zulip-test.pagerduty.com/incidents/PO1XIJ5) resolved by [armooo](https://zulip-test.pagerduty.com/users/POBCFRJ).\n\n``` quote\nIt is on fire\n```"
        self.check_webhook("resolved", "Incident 1", expected_message)

    def test_resolved_v2(self) -> None:
        expected_message = "Incident [33](https://webdemo.pagerduty.com/incidents/PRORDTY) resolved by [Laura Haley](https://webdemo.pagerduty.com/users/P553OPV).\n\n``` quote\nMy new incident\n```"
        self.check_webhook("resolve_v2", "Incident 33", expected_message)

    def test_resolved_v3(self) -> None:
        expected_message = "Incident [Test Incident (#6)](https://pig208.pagerduty.com/incidents/PCPZE64) resolved by [PIG 208](https://pig208.pagerduty.com/users/PJ0LVEB)."
        self.check_webhook("resolved_v3", "Incident Test Incident (#6)", expected_message)

    def test_auto_resolved(self) -> None:
        expected_message = "Incident [2](https://zulip-test.pagerduty.com/incidents/PX7K9J2) resolved.\n\n``` quote\nnew\n```"
        self.check_webhook("auto_resolved", "Incident 2", expected_message)

    def test_acknowledge(self) -> None:
        expected_message = "Incident [1](https://zulip-test.pagerduty.com/incidents/PO1XIJ5) acknowledged by [armooo](https://zulip-test.pagerduty.com/users/POBCFRJ).\n\n``` quote\nIt is on fire\n```"
        self.check_webhook("acknowledge", "Incident 1", expected_message)

    def test_acknowledge_without_trigger_summary_data(self) -> None:
        expected_message = "Incident [1](https://zulip-test.pagerduty.com/incidents/PO1XIJ5) acknowledged by [armooo](https://zulip-test.pagerduty.com/users/POBCFRJ).\n\n``` quote\n\n```"
        self.check_webhook(
            "acknowledge_without_trigger_summary_data", "Incident 1", expected_message
        )

    def test_acknowledged_v3(self) -> None:
        expected_message = "Incident [Test Incident (#10)](https://pig208.pagerduty.com/incidents/PQ1K5C8) acknowledged by [PIG 208](https://pig208.pagerduty.com/users/PJ0LVEB)."
        self.check_webhook("acknowledged_v3", "Incident Test Incident (#10)", expected_message)

    def test_acknowledge_v2(self) -> None:
        expected_message = "Incident [33](https://webdemo.pagerduty.com/incidents/PRORDTY) acknowledged by [Laura Haley](https://webdemo.pagerduty.com/users/P553OPV).\n\n``` quote\nMy new incident\n```"
        self.check_webhook("acknowledge_v2", "Incident 33", expected_message)

    def test_incident_assigned_v2(self) -> None:
        expected_message = "Incident [33](https://webdemo.pagerduty.com/incidents/PRORDTY) assigned to [Wiley Jacobson](https://webdemo.pagerduty.com/users/PFBSJ2Z).\n\n``` quote\nMy new incident\n```"
        self.check_webhook("assign_v2", "Incident 33", expected_message)

    def test_reassigned_v3(self) -> None:
        expected_message = "Incident [Test Incident (#3)](https://pig208.pagerduty.com/incidents/PIQUG8X) reassigned to [Test User](https://pig208.pagerduty.com/users/PI9DT01)."
        self.check_webhook("reassigned_v3", "Incident Test Incident (#3)", expected_message)

    def test_no_subject(self) -> None:
        expected_message = "Incident [48219](https://dropbox.pagerduty.com/incidents/PJKGZF9) resolved.\n\n``` quote\nmp_error_block_down_critical\u2119\u01b4\n```"
        self.check_webhook("mp_fail", "Incident 48219", expected_message)

    def test_unsupported_webhook_event(self) -> None:
        for version in range(1, 4):
            payload = self.get_body(f"unsupported_v{version}")
            result = self.client_post(self.url, payload, content_type="application/json")
            self.assert_json_success(result)
            self.assert_in_response(
                "The 'incident.unsupported' event isn't currently supported by the PagerDuty webhook; ignoring",
                result,
            )
    # TEST FOR SIGNATURE VERIFICATION
    def test_valid_signature(self) -> None:
        """Test that webhooks with valid PagerDuty signature are accepted"""
        payload = self.get_body("trigger_v2")
        # Use a test webhook secret
        webhook_secret = "test_webhook_secret_123"
        # Generate valid signature using the webhook secret
        signature = hmac.new(
            webhook_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        # Build URL with webhook_secret parameter
        url = self.build_webhook_url(webhook_secret=webhook_secret)
        # Enable signature verification for this test
        with self.settings(VERIFY_WEBHOOK_SIGNATURES=True):
            # Send webhook with valid signature
            result = self.client_post(url,payload,content_type="application/json",HTTP_X_PAGERDUTY_SIGNATURE=f"v1={signature}",)
            self.assert_json_success(result)

    def test_invalid_signature(self) -> None:
        """Test that webhooks with invalid PagerDuty signature are rejected"""
        payload = self.get_body("trigger_v2")
        webhook_secret = "test_webhook_secret_123"
        invalid_signature = "0" * 64
        url = self.build_webhook_url(webhook_secret=webhook_secret)t
        with self.settings(VERIFY_WEBHOOK_SIGNATURES=True):
            result = self.client_post(url,payload,content_type="application/json",HTTP_X_PAGERDUTY_SIGNATURE=f"v1={invalid_signature}",)
            self.assert_json_error(result, "Webhook signature verification failed.")
            
    def test_multiple_signatures_one_valid(self) -> None:
        """Test that webhook accepts if at least one signature in comma-separated list is valid"""
        payload = self.get_body("trigger_v2")
        webhook_secret = "test_webhook_secret_123"
        valid_signature = hmac.new(
            webhook_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        invalid_signature = "0" * 64
        mixed_signatures = f"v1={invalid_signature},v1={valid_signature}"
        url = self.build_webhook_url(webhook_secret=webhook_secret)
        with self.settings(VERIFY_WEBHOOK_SIGNATURES=True):
            result = self.client_post(url,payload,content_type="application/json",HTTP_X_PAGERDUTY_SIGNATURE=mixed_signatures,)
            self.assert_json_success(result)

    def test_service_created_v3(self) -> None:
        """Test service.created event from PagerDuty V3"""
        expected_message = (
            "Service [Test Service](https://pig208.pagerduty.com/services/PSERVICE1) created."
        )
        self.check_webhook("service_created_v3", "Service Test Service", expected_message)

    def test_service_updated_v3(self) -> None:
        """Test service.updated event from PagerDuty V3"""
        expected_message = (
            "Service [Test Service](https://pig208.pagerduty.com/services/PSERVICE1) updated."
        )
        self.check_webhook("service_updated_v3", "Service Test Service", expected_message)

    def test_service_deleted_v3(self) -> None:
        """Test service.deleted event from PagerDuty V3"""
        expected_message = (
            "Service [Test Service](https://pig208.pagerduty.com/services/PSERVICE1) deleted."
        )
        self.check_webhook("service_deleted_v3", "Service Test Service", expected_message)
