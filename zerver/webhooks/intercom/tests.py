from zerver.lib.test_classes import WebhookTestCase


class IntercomWebHookTests(WebhookTestCase):
    def test_ping(self) -> None:
        expected_topic_name = "Intercom"
        expected_message = "Intercom webhook has been successfully configured."
        self.check_webhook("ping", expected_topic_name, expected_message)

    def test_company_created(self) -> None:
        expected_topic_name = "Company: 6961d175205cf6a4438f0c22-qualification-company"
        expected_message = "6961d175205cf6a4438f0c22-qualification-company was created."
        self.check_webhook("company_created", expected_topic_name, expected_message)

    def test_company_created_with_name(self) -> None:
        expected_topic_name = "Company: Acme Enterprises"
        expected_message = "Acme Enterprises was created."
        self.check_webhook("company_created_with_name", expected_topic_name, expected_message)

    def test_company_deleted(self) -> None:
        expected_topic_name = "Company: 6961d38729675009a437c3bf"
        expected_message = "6961d38729675009a437c3bf was deleted."
        self.check_webhook("company_deleted", expected_topic_name, expected_message)

    def test_company_updated(self) -> None:
        expected_topic_name = "Company: Acme Enterprises"
        expected_message = "Acme Enterprises was updated."
        self.check_webhook("company_updated", expected_topic_name, expected_message)

    def test_company_contact_attached(self) -> None:
        expected_topic_name = "user/lead: Jane Lead (6961d162fb0ef1f1ac90ce8c)"
        expected_message = "**Jane Lead** was attached to company **6961d175205cf6a4438f0c22-qualification-company**."
        self.check_webhook("company_contact_attached", expected_topic_name, expected_message)

    def test_company_contact_detached(self) -> None:
        expected_topic_name = "user/lead: Jane Smith (6961cf78fb9d13be07871c78)"
        expected_message = "**Jane Smith** was detached from company **Acme Corp**."
        self.check_webhook("company_contact_detached", expected_topic_name, expected_message)
