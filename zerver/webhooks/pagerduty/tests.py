from zerver.lib.test_classes import WebhookTestCase


class PagerDutyHookTests(WebhookTestCase):
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

    def test_escalated_v3(self) -> None:
        expected_message = "Incident [Critical: Checkout API High Latency (#5)](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD) escalated to [Harsh Santwani](https://harsh0303.pagerduty.com/users/PXRUEF2)."
        self.check_webhook(
            "escalate_v3", "Incident Critical: Checkout API High Latency (#5)", expected_message
        )

    def test_delegated_v3(self) -> None:
        expected_message = "Incident [Critical: Checkout API High Latency (#5)](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD) delegated; current escalation policy is [APIs-ep](https://harsh0303.pagerduty.com/escalation_policies/P3RAX8S) and current assignee is [Harsh Santwani](https://harsh0303.pagerduty.com/users/PXRUEF2)."
        self.check_webhook(
            "delegated_v3", "Incident Critical: Checkout API High Latency (#5)", expected_message
        )

    def test_reopened_v3(self) -> None:
        expected_message = "Incident [Test Incident 2 (#4)](https://harsh0303.pagerduty.com/incidents/Q05XJA8GDXGOB3) reopened."
        self.check_webhook("reopened_v3", "Incident Test Incident 2 (#4)", expected_message)

    def test_priority_updated_v3(self) -> None:
        expected_message = "Incident [Critical: Checkout API High Latency (#5)](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD) priority updated to P2"
        self.check_webhook(
            "priority_updated_v3",
            "Incident Critical: Checkout API High Latency (#5)",
            expected_message,
        )

    def test_status_updated_v3(self) -> None:
        expected_message = "Incident [Critical: Checkout API High Latency](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD) status update published: Investigating a P1 incident with the Checkout API in us-east-1. Customers may see 504 errors or delays during purchase. We've identified a database lock and are working on a fix. Expected remediation within 30 minutes; next update at 08:15 UTC."
        self.check_webhook(
            "status_updated_v3", "Incident Critical: Checkout API High Latency", expected_message
        )

    def test_annotated_v3(self) -> None:
        expected_message = "Incident [Critical: Checkout API High Latency](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD) annotated with: Running KILL on long-running queries from the reporting-service."
        self.check_webhook(
            "annotated_v3", "Incident Critical: Checkout API High Latency", expected_message
        )

    def test_responder_added_v3(self) -> None:
        expected_message = 'Responder [Harsh Santwani](https://harsh0303.pagerduty.com/users/PXRUEF2) added to incident [Critical: Checkout API High Latency](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD).\n\n``` quote\nPlease help with "Critical: Checkout API High Latency"\n```'
        self.check_webhook(
            "responder_added", "Incident Critical: Checkout API High Latency", expected_message
        )

    def test_responder_replied_v3(self) -> None:
        expected_message = "Responder [Harsh Santwani](https://harsh0303.pagerduty.com/users/PXRUEF2) replied to incident [Critical: Checkout API High Latency](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD).\n\n``` quote\nChecking now. Investigating DB locks on cluster-01 and reviewing latency metrics in Datadog. Will update in 5 mins.\n\n```"
        self.check_webhook(
            "responder_replied_v3",
            "Incident Critical: Checkout API High Latency",
            expected_message,
        )

    def test_conference_bridge_updated_v3(self) -> None:
        expected_message = "Incident [Critical: Checkout API High Latency](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD) conference bridge updated: https://example.com/123-456-789"
        self.check_webhook(
            "conference_bridge_updated_v3",
            "Incident Critical: Checkout API High Latency",
            expected_message,
        )

    def test_service_updated_v3(self) -> None:
        expected_message = "Incident [Critical: Checkout API High Latency (#5)](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD) service updated to APIs"
        self.check_webhook(
            "service_updated_v3",
            "Incident Critical: Checkout API High Latency (#5)",
            expected_message,
        )

    def test_workflow_started_v3(self) -> None:
        expected_message = "Incident [Critical: Checkout API High Latency](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD) workflow started: Incident WorkFlow (Manually Started)"
        self.check_webhook(
            "workflow_started_v3",
            "Incident Critical: Checkout API High Latency",
            expected_message,
        )

    def test_workflow_completed_v3(self) -> None:
        expected_message = "Incident [Critical: Checkout API High Latency](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD) workflow completed: Incident WorkFlow (Manually Started)"
        self.check_webhook(
            "workflow_completed_v3",
            "Incident Critical: Checkout API High Latency",
            expected_message,
        )

    def test_workflow_completed_no_summary_v3(self) -> None:
        expected_message = "Incident [Critical: Checkout API High Latency](https://harsh0303.pagerduty.com/incidents/Q3B15VLMF3ASBD) workflow completed: Incident WorkFlow"
        self.check_webhook(
            "workflow_completed_no_summary_v3",
            "Incident Critical: Checkout API High Latency",
            expected_message,
        )

    def test_unsupported_webhook_event(self) -> None:
        for version in range(1, 4):
            payload = self.get_body(f"unsupported_v{version}")
            result = self.client_post(self.url, payload, content_type="application/json")
            self.assert_json_success(result)
            self.assert_in_response(
                "The 'incident.unsupported' event isn't currently supported by the PagerDuty webhook; ignoring",
                result,
            )
