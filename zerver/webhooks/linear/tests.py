from unittest.mock import patch

from zerver.lib.test_classes import WebhookTestCase


class LinearHookTests(WebhookTestCase):
    def test_issue_create_simple_without_description(self) -> None:
        expected_topic_name = "Issue: Drop-down overflow in the select menu."
        expected_message = "[Issue](https://linear.app/webhooks/issue/WEB-42/drop-down-overflow-in-the-select-menu) was created in team Webhooks.\nPriority: High, Status: Todo."
        self.check_webhook(
            "issue_create_simple_without_description",
            expected_topic_name,
            expected_message,
        )

    def test_issue_create_simple_without_description_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "[Issue](https://linear.app/webhooks/issue/WEB-42/drop-down-overflow-in-the-select-menu) was created in team Webhooks.\nPriority: High, Status: Todo."
        self.check_webhook(
            "issue_create_simple_without_description",
            expected_topic_name,
            expected_message,
        )

    def test_issue_create_simple(self) -> None:
        expected_topic_name = "Issue: Very small font in tooltip"
        expected_message = '[Issue](https://linear.app/webhooks/issue/WEB-43/very-small-font-in-tooltip) was created in team Webhooks:\n~~~ quote\nThe tooltips at the "Select Drawing" and "Edit Drawing" buttons have a very small font and therefore are not very legible. Apart from this, the wording of the text has to be changed to fit better with the overall design pattern.\n~~~\n\nStatus: Todo.'
        self.check_webhook("issue_create_simple", expected_topic_name, expected_message)

    def test_issue_create_complex(self) -> None:
        expected_topic_name = "Issue: This is regarding the outage that we faced during ..."
        expected_message = "[Issue](https://linear.app/webhooks/issue/WEB-44/this-is-regarding-the-outage-that-we-faced-during-111222-from-2000-to) was created in team Webhooks:\n~~~ quote\nThe outage that occurred on the above-mentioned date is a cause for concern as it could have significant implications for the organization and its users. A prolonged outage can result in lost revenue, productivity, and customer confidence. Therefore, it is essential to conduct a detailed assessment and analysis to identify the root cause of the outage and take appropriate measures to prevent its recurrence.\n\nThe analysis process may involve the use of specialized tools and techniques to help pinpoint the exact cause of the outage. Once the root cause has been identified, the organization can take steps to implement effective solutions that can mitigate the risk of a similar outage happening in the future. The assessment and analysis process will help the organization to develop a more robust and reliable IT infrastructure that can provide uninterrupted services to its users.\n~~~\n\nPriority: Urgent, Assignee: Satyam Bansal, Status: In Progress."
        self.check_webhook("issue_create_complex", expected_topic_name, expected_message)

    def test_comment_create(self) -> None:
        expected_topic_name = "Issue: Thorough Impact Analysis and Cost Realization"
        expected_message = "Satyam Bansal [commented](https://linear.app/webhooks/issue/WEB-46#comment-c7cafc52) on issue **Thorough Impact Analysis and Cost Realization**:\n~~~ quote\nPerforming a thorough impact analysis and cost realization is a crucial step in responding to any system outage or incident. By examining the extent of the outage, the affected systems or services, the number of users impacted, and any error messages or logs generated during the incident, we can gain a comprehensive understanding of the scope of the incident.\n\nThis information can then be used to prioritize the resolution efforts and minimize the impact on our organization's operations. Additionally, cost realization allows us to evaluate the financial impact of the outage on our organization and make informed decisions regarding resource allocation for future incidents.\n\nOverall, conducting a thorough impact analysis and cost realization can help us effectively manage incidents and prevent similar issues from occurring in the future.\n~~~"
        self.check_webhook("comment_create", expected_topic_name, expected_message)

    def test_comment_remove(self) -> None:
        expected_topic_name = "Issue: Thorough Impact Analysis and Cost Realization"
        expected_message = "Satyam Bansal has removed a comment."
        self.check_webhook("comment_remove", expected_topic_name, expected_message)

    def test_comment_update(self) -> None:
        expected_topic_name = "Issue: Thorough Impact Analysis and Cost Realization"
        expected_message = "Satyam Bansal [updated comment](https://linear.app/webhooks/issue/WEB-46#comment-c7cafc52) on issue **Thorough Impact Analysis and Cost Realization**:\n~~~ quote\nInvalid response to any system outage or incident, it is essential to perform a comprehensive impact analysis and cost evaluation. By examining factors such as the extent of the outage, the affected systems or services, the number of users affected, and any error messages or logs generated during the incident, we can gain a detailed understanding of the incident's scope.\n\nThis information is then critical in prioritizing resolution efforts and reducing the impact on our organization's operations. Additionally, conducting cost realization allows us to assess the financial implications of the outage and make informed decisions about allocating resources for future incidents.\n\nOverall, performing a thorough impact analysis and cost realization is an effective way to manage incidents and prevent similar issues from recurring.\n~~~"
        self.check_webhook("comment_update", expected_topic_name, expected_message)

    def test_issue_remove(self) -> None:
        expected_topic_name = "Issue: This is regarding the outage that we faced on 11/1..."
        expected_message = "This issue has been removed from team Webhooks."
        self.check_webhook("issue_remove", expected_topic_name, expected_message)

    def test_issue_sub_issue_create(self) -> None:
        expected_topic_name = "Sub-Issue: Impact Analysis"
        expected_message = "[Sub-Issue](https://linear.app/webhooks/issue/WEB-46/impact-analysis) was created in team Webhooks:\n~~~ quote\nExamining the extent of the outage, the affected systems or services, the number of users impacted, and any error messages or logs generated during the incident.\n~~~\n\nStatus: Todo."
        self.check_webhook("issue_sub_issue_create", expected_topic_name, expected_message)

    def test_issue_sub_issue_remove(self) -> None:
        expected_topic_name = "Sub-Issue: Thorough Impact Analysis and Cost Realization"
        expected_message = "This issue has been removed from team Webhooks."
        self.check_webhook("issue_sub_issue_remove", expected_topic_name, expected_message)

    def test_issue_sub_issue_update(self) -> None:
        expected_topic_name = "Sub-Issue: Thorough Impact Analysis and Cost Realization"
        expected_message = "[Sub-Issue](https://linear.app/webhooks/issue/WEB-46/thorough-impact-analysis-and-cost-realization) was updated in team Webhooks:\n~~~ quote\nExamining the extent of the outage, the affected systems or services, the number of users impacted, and any error messages or logs generated during the incident.\n~~~\n\nStatus: Todo."
        self.check_webhook("issue_sub_issue_update", expected_topic_name, expected_message)

    def test_issue_update(self) -> None:
        expected_topic_name = "Issue: This is regarding the outage that we faced on 11/1..."
        expected_message = "[Issue](https://linear.app/webhooks/issue/WEB-44/this-is-regarding-the-outage-that-we-faced-on-111222-from-2000-to-2200) was updated in team Webhooks:\n~~~ quote\nThe outage that occurred on the above-mentioned date is a cause for concern as it could have significant implications for the organization and its users. A prolonged outage can result in lost revenue, productivity, and customer confidence. Therefore, it is essential to conduct a detailed assessment and analysis to identify the root cause of the outage and take appropriate measures to prevent its recurrence.\n\nThe analysis process may involve the use of specialized tools and techniques to help pinpoint the exact cause of the outage. Once the root cause has been identified, the organization can take steps to implement effective solutions that can mitigate the risk of a similar outage happening in the future. The assessment and analysis process will help the organization to develop a more robust and reliable IT infrastructure that can provide uninterrupted services to its users.\n~~~\n\nPriority: Urgent, Assignee: Satyam Bansal, Status: In Progress."
        self.check_webhook("issue_update", expected_topic_name, expected_message)

    def test_project_create(self) -> None:
        expected_topic_name = "Project: Project-Zulip"
        expected_message = "Dhruv Shetty created project [Project-Zulip](https://linear.app/zulipdhruv/project/project-zulip-a98782de01a9):\n~~~ quote\nThis is a project for zulip\n~~~\n**Status:** Backlog"
        self.check_webhook("project_create", expected_topic_name, expected_message)

    def test_project_create_complex(self) -> None:
        expected_topic_name = "Project: Zulip-Project"
        expected_message = "Dhruv Shetty created project [Zulip-Project](https://linear.app/zulipdhruv/project/zulip-project-532c1333013b):\n~~~ quote\nSummary for the Project\n**Start date:** 2026-05-28 – **Target date:** 2026-05-30\n~~~\n**Status:** Planned · **Lead:** Dhruv Shetty · **Priority:** Urgent\n- **Milestone:** Phase 1"
        self.check_webhook("project_create_complex", expected_topic_name, expected_message)

    def test_project_create_without_description(self) -> None:
        expected_topic_name = "Project: Project-Manhattan"
        expected_message = "Dhruv Shetty created project [Project-Manhattan](https://linear.app/zulipdhruv/project/project-manhattan-9719af1a1893)\n**Status:** Backlog"
        self.check_webhook(
            "project_create_without_description", expected_topic_name, expected_message
        )

    def test_project_create_without_description_with_dates(self) -> None:
        expected_topic_name = "Project: Zulip-terminal"
        expected_message = "Dhruv Shetty created project [Zulip-terminal](https://linear.app/zulipdhruv/project/zulip-terminal-5bfd1327f54b)\n**Status:** Backlog\n- **Start date:** 2026-06-01\n- **Target date:** 2026-06-03"
        self.check_webhook(
            "project_create_without_description_with_dates", expected_topic_name, expected_message
        )

    def test_project_update_priority(self) -> None:
        expected_topic_name = "Project: Zulip-Project"
        expected_message = "Dhruv Shetty updated project [Zulip-Project](https://linear.app/zulipdhruv/project/zulip-project-532c1333013b).\nPriority is now set to High."
        self.check_webhook("project_update_priority", expected_topic_name, expected_message)

    def test_project_update_target_date(self) -> None:
        expected_topic_name = "Project: Zulip-Project"
        expected_message = "Dhruv Shetty updated project [Zulip-Project](https://linear.app/zulipdhruv/project/zulip-project-532c1333013b).\nTarget date is postponed to 2026-06-02."
        self.check_webhook("project_update_target_date", expected_topic_name, expected_message)

    def test_project_update_rename(self) -> None:
        expected_topic_name = "Project: Zulip-Test-Project"
        expected_message = "Dhruv Shetty updated project [Zulip-Test-Project](https://linear.app/zulipdhruv/project/zulip-test-project-532c1333013b).\nRenamed to Zulip-Test-Project."
        self.check_webhook("project_update_rename", expected_topic_name, expected_message)

    def test_project_update_status(self) -> None:
        expected_topic_name = "Project: Zulip-Test-Project"
        expected_message = "Dhruv Shetty updated project [Zulip-Test-Project](https://linear.app/zulipdhruv/project/zulip-test-project-532c1333013b).\nProject status is now In Progress."
        self.check_webhook("project_update_status", expected_topic_name, expected_message)

    def test_project_update_lead_set(self) -> None:
        expected_topic_name = "Project: Zulip-Test-Project"
        expected_message = "Dhruv Shetty updated project [Zulip-Test-Project](https://linear.app/zulipdhruv/project/zulip-test-project-532c1333013b).\nDhruv Shetty is now the project lead."
        self.check_webhook("project_update_lead_set", expected_topic_name, expected_message)

    def test_project_update_target_date_preponed(self) -> None:
        expected_topic_name = "Project: Zulip-Test-Project"
        expected_message = "Dhruv Shetty updated project [Zulip-Test-Project](https://linear.app/zulipdhruv/project/zulip-test-project-532c1333013b).\nTarget date is preponed to 2026-05-29."
        self.check_webhook(
            "project_update_target_date_preponed", expected_topic_name, expected_message
        )

    def test_project_update_target_date_set(self) -> None:
        expected_topic_name = "Project: Project Zulip"
        expected_message = "Dhruv Shetty updated project [Project Zulip](https://linear.app/zulipdhruv/project/project-zulip-c65c2156ca87).\nTarget date is set to 2026-05-30."
        self.check_webhook("project_update_target_date_set", expected_topic_name, expected_message)

    def test_project_update_description(self) -> None:
        expected_topic_name = "Project: Zulip-Test-Project"
        expected_message = "Dhruv Shetty updated project [Zulip-Test-Project](https://linear.app/zulipdhruv/project/zulip-test-project-532c1333013b).\nDescription is updated."
        self.check_webhook("project_update_description", expected_topic_name, expected_message)

    def test_project_remove(self) -> None:
        expected_topic_name = "Project: Project-Zulip"
        expected_message = "Dhruv Shetty removed project **Project-Zulip**."
        self.check_webhook("project_remove", expected_topic_name, expected_message)

    def test_projectUpdate_create(self) -> None:
        expected_topic_name = "Project: Zulip-terminal"
        expected_message = "Dhruv Shetty [posted](https://linear.app/zulipdhruv/project/zulip-terminal-5bfd1327f54b/activity#project-update-bd310e45) a status update on **Zulip-terminal** (health: At Risk):\n~~~ quote\nThis is a project status update\n**Imported User**[7:03 AM](<http://localhost:9991/#narrow/channel/10-design/topic/.E2.9C.94.20NEW.20router.20wasn.27t.20de-duping.20slowly/near/88>)\n\nExisting robust and atomic methodologies use suffix trees to evaluate trainable theory. The basic tenet of this approach is the development of checksums. Despite the fact that conventional wisdom states that this obstacle is regularly overcame by the deployment of the World Wide Web, we believe that a different approach is necessary.\n~~~"
        self.check_webhook("projectUpdate_create", expected_topic_name, expected_message)

    def test_projectUpdate_update(self) -> None:
        expected_topic_name = "Project: Project Zulip"
        expected_message = "Dhruv Shetty [edited](https://linear.app/zulipdhruv/project/project-zulip-c65c2156ca87/activity#project-update-4a0814c9) a status update on **Project Zulip** (health: Off Track):\n~~~ quote\nThere is a risk\n~~~\n\n**Priority**: Medium"
        self.check_webhook("projectUpdate_update", expected_topic_name, expected_message)

    def test_projectUpdate_remove(self) -> None:
        expected_topic_name = "Project: Project-Zulip"
        expected_message = "Dhruv Shetty removed a status update on **Project-Zulip**."
        self.check_webhook("projectUpdate_remove", expected_topic_name, expected_message)

    def test_projectUpdate_auto_update_after_create_is_suppressed(self) -> None:
        # Linear's auto-fire after a ProjectUpdate post (lastUpdateId in
        # updatedFrom) must not produce a duplicate Zulip message.
        with patch("zerver.webhooks.linear.view.check_send_webhook_message") as m:
            result = self.client_post(
                self.url,
                self.get_body("projectUpdate_auto_update_after_create"),
                content_type="application/json",
            )
        self.assertFalse(m.called)
        self.assert_json_success(result)

    def test_projectUpdate_auto_update_after_edit_is_suppressed(self) -> None:
        # Linear's auto-fire after editing a ProjectUpdate (health-only in
        # updatedFrom) must not produce a duplicate Zulip message.
        with patch("zerver.webhooks.linear.view.check_send_webhook_message") as m:
            result = self.client_post(
                self.url,
                self.get_body("projectUpdate_auto_update_after_edit"),
                content_type="application/json",
            )
        self.assertFalse(m.called)
        self.assert_json_success(result)

    def test_project_auto_update_after_create_is_suppressed(self) -> None:
        # Linear's auto-fire after Project.create (empty updatedFrom) must
        # not produce a Zulip message.
        with patch("zerver.webhooks.linear.view.check_send_webhook_message") as m:
            result = self.client_post(
                self.url,
                self.get_body("project_auto_update_after_create"),
                content_type="application/json",
            )
        self.assertFalse(m.called)
        self.assert_json_success(result)
