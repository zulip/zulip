from zerver.lib.test_classes import WebhookTestCase


class LinearHookTests(WebhookTestCase):
    CHANNEL_NAME = "Linear"
    URL_TEMPLATE = "/api/v1/external/linear?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "linear"

    def test_issue_create_simple_without_description(self) -> None:
        expected_topic_name = "21e12515-fe5e-4923-88a1-e9ace5056473"
        expected_message = "Issue [#42 Drop-down overflow in the select menu.](https://linear.app/webhooks/issue/WEB-42/drop-down-overflow-in-the-select-menu) was created in team Webhooks.\nPriority: High, Status: Todo."
        self.check_webhook(
            "issue_create_simple_without_description",
            expected_topic_name,
            expected_message,
        )

    def test_issue_create_simple_without_description_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "Issue [#42 Drop-down overflow in the select menu.](https://linear.app/webhooks/issue/WEB-42/drop-down-overflow-in-the-select-menu) was created in team Webhooks.\nPriority: High, Status: Todo."
        self.check_webhook(
            "issue_create_simple_without_description",
            expected_topic_name,
            expected_message,
        )

    def test_issue_create_simple(self) -> None:
        expected_topic_name = "a4344dc7-7d8d-4b28-a93c-553ac9aba41a"
        expected_message = 'Issue [#43 Very small font in tooltip](https://linear.app/webhooks/issue/WEB-43/very-small-font-in-tooltip) was created in team Webhooks:\n~~~ quote\nThe tooltips at the "Select Drawing" and "Edit Drawing" buttons have a very small font and therefore are not very legible. Apart from this, the wording of the text has to be changed to fit better with the overall design pattern.\n~~~\n\nStatus: Todo.'
        self.check_webhook("issue_create_simple", expected_topic_name, expected_message)

    def test_issue_create_complex(self) -> None:
        expected_topic_name = "3443a709-f2b5-46f2-a136-a0445fd432be"
        expected_message = "Issue [#44 This is regarding the outage that we faced during 11/12/22 from 2000 to 2200.](https://linear.app/webhooks/issue/WEB-44/this-is-regarding-the-outage-that-we-faced-during-111222-from-2000-to) was created in team Webhooks:\n~~~ quote\nThe outage that occurred on the above-mentioned date is a cause for concern as it could have significant implications for the organization and its users. A prolonged outage can result in lost revenue, productivity, and customer confidence. Therefore, it is essential to conduct a detailed assessment and analysis to identify the root cause of the outage and take appropriate measures to prevent its recurrence.\n\nThe analysis process may involve the use of specialized tools and techniques to help pinpoint the exact cause of the outage. Once the root cause has been identified, the organization can take steps to implement effective solutions that can mitigate the risk of a similar outage happening in the future. The assessment and analysis process will help the organization to develop a more robust and reliable IT infrastructure that can provide uninterrupted services to its users.\n~~~\n\nPriority: Urgent, Assignee: Satyam Bansal, Status: In Progress."
        self.check_webhook("issue_create_complex", expected_topic_name, expected_message)

    def test_comment_create(self) -> None:
        expected_topic_name = "f9a37fcf-eb52-44be-a52c-0477f70e9952"
        expected_message = "Satyam Bansal [commented](https://linear.app/webhooks/issue/WEB-46#comment-c7cafc52) on issue **Thorough Impact Analysis and Cost Realization**:\n~~~ quote\nPerforming a thorough impact analysis and cost realization is a crucial step in responding to any system outage or incident. By examining the extent of the outage, the affected systems or services, the number of users impacted, and any error messages or logs generated during the incident, we can gain a comprehensive understanding of the scope of the incident.\n\nThis information can then be used to prioritize the resolution efforts and minimize the impact on our organization's operations. Additionally, cost realization allows us to evaluate the financial impact of the outage on our organization and make informed decisions regarding resource allocation for future incidents.\n\nOverall, conducting a thorough impact analysis and cost realization can help us effectively manage incidents and prevent similar issues from occurring in the future.\n~~~"
        self.check_webhook("comment_create", expected_topic_name, expected_message)

    def test_comment_remove(self) -> None:
        expected_topic_name = "f9a37fcf-eb52-44be-a52c-0477f70e9952"
        expected_message = "Satyam Bansal has removed a comment."
        self.check_webhook("comment_remove", expected_topic_name, expected_message)

    def test_comment_update(self) -> None:
        expected_topic_name = "f9a37fcf-eb52-44be-a52c-0477f70e9952"
        expected_message = "Satyam Bansal [updated comment](https://linear.app/webhooks/issue/WEB-46#comment-c7cafc52) on issue **Thorough Impact Analysis and Cost Realization**:\n~~~ quote\nInvalid response to any system outage or incident, it is essential to perform a comprehensive impact analysis and cost evaluation. By examining factors such as the extent of the outage, the affected systems or services, the number of users affected, and any error messages or logs generated during the incident, we can gain a detailed understanding of the incident's scope.\n\nThis information is then critical in prioritizing resolution efforts and reducing the impact on our organization's operations. Additionally, conducting cost realization allows us to assess the financial implications of the outage and make informed decisions about allocating resources for future incidents.\n\nOverall, performing a thorough impact analysis and cost realization is an effective way to manage incidents and prevent similar issues from recurring.\n~~~"
        self.check_webhook("comment_update", expected_topic_name, expected_message)

    def test_issue_remove(self) -> None:
        expected_topic_name = "3443a709-f2b5-46f2-a136-a0445fd432be"
        expected_message = "Issue **#44 This is regarding the outage that we faced on 11/12/22 from 2000 to 2200 and also on 25/12/22 from 0000 to 0230** has been removed from team Webhooks."
        self.check_webhook("issue_remove", expected_topic_name, expected_message)

    def test_issue_sub_issue_create(self) -> None:
        expected_topic_name = "3443a709-f2b5-46f2-a136-a0445fd432be"
        expected_message = "Sub-Issue [#46 Impact Analysis](https://linear.app/webhooks/issue/WEB-46/impact-analysis) was created in team Webhooks:\n~~~ quote\nExamining the extent of the outage, the affected systems or services, the number of users impacted, and any error messages or logs generated during the incident.\n~~~\n\nStatus: Todo."
        self.check_webhook("issue_sub_issue_create", expected_topic_name, expected_message)

    def test_issue_sub_issue_remove(self) -> None:
        expected_topic_name = "3443a709-f2b5-46f2-a136-a0445fd432be"
        expected_message = "Sub-Issue **#46 Thorough Impact Analysis and Cost Realization** has been removed from team Webhooks."
        self.check_webhook("issue_sub_issue_remove", expected_topic_name, expected_message)

    def test_issue_sub_issue_update(self) -> None:
        expected_topic_name = "3443a709-f2b5-46f2-a136-a0445fd432be"
        expected_message = "Sub-Issue [#46 Thorough Impact Analysis and Cost Realization](https://linear.app/webhooks/issue/WEB-46/thorough-impact-analysis-and-cost-realization) was updated in team Webhooks:\n~~~ quote\nExamining the extent of the outage, the affected systems or services, the number of users impacted, and any error messages or logs generated during the incident.\n~~~\n\nStatus: Todo."
        self.check_webhook("issue_sub_issue_update", expected_topic_name, expected_message)

    def test_issue_update(self) -> None:
        expected_topic_name = "3443a709-f2b5-46f2-a136-a0445fd432be"
        expected_message = "Issue [#44 This is regarding the outage that we faced on 11/12/22 from 2000 to 2200 and also on 25/12/22 from 0000 to 0230](https://linear.app/webhooks/issue/WEB-44/this-is-regarding-the-outage-that-we-faced-on-111222-from-2000-to-2200) was updated in team Webhooks:\n~~~ quote\nThe outage that occurred on the above-mentioned date is a cause for concern as it could have significant implications for the organization and its users. A prolonged outage can result in lost revenue, productivity, and customer confidence. Therefore, it is essential to conduct a detailed assessment and analysis to identify the root cause of the outage and take appropriate measures to prevent its recurrence.\n\nThe analysis process may involve the use of specialized tools and techniques to help pinpoint the exact cause of the outage. Once the root cause has been identified, the organization can take steps to implement effective solutions that can mitigate the risk of a similar outage happening in the future. The assessment and analysis process will help the organization to develop a more robust and reliable IT infrastructure that can provide uninterrupted services to its users.\n~~~\n\nPriority: Urgent, Assignee: Satyam Bansal, Status: In Progress."
        self.check_webhook("issue_update", expected_topic_name, expected_message)

    def test_project_create(self) -> None:
        payload = self.get_body("project_create")
        result = self.client_post(
            self.url,
            payload,
            content_type="application/json",
        )
        self.assert_json_success(result)
