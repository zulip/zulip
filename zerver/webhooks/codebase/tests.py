from zerver.lib.test_classes import WebhookTestCase


class CodebaseHookTests(WebhookTestCase):
    def test_ticket_creation(self) -> None:
        expected_topic_name = "Adding the brand new feature of auto tuning to my web app"
        expected_message = (
            "A ticket of **[Enhancement](http://travelalittle.codebasehq.com/projects/"
            "adding-support-for-checking-events/tickets/2)** type and category "
            "**General** has been created by **Sameer Choubey**."
        )
        self.check_webhook("ticket_creation", expected_topic_name, expected_message)

    def test_ticket_update(self) -> None:
        expected_topic_name = "Adding the brand new feature of auto tuning to my web app"
        expected_message = (
            "Ticket with ID **[2](http://travelalittle.codebasehq.com/projects/"
            "adding-support-for-checking-events)**, category "
            "**Refactoring** has been updated by **Sameer Choubey**."
        )
        self.check_webhook("ticket_update", expected_topic_name, expected_message)
