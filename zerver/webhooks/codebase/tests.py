from zerver.lib.test_classes import WebhookTestCase

class CobebaseHookTests(WebhookTestCase):
    STREAM_NAME = 'codebase'
    URL_TEMPLATE = "/api/v1/external/codebase?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'codebase'


    def test_ticket_creation(self) -> None:
        expected_topic = u"Adding the brand new feature of auto tuning to my webapp"
        expected_message = u"A ticket of **[Enhancement](http://travelalittle.codebasehq.com/projects/adding-support-for-checking-events/tickets/2)** type and category **General** has been created by **Sameer Choubey**"

        self.send_and_test_stream_message('ticket_creation', expected_topic, expected_message)

    def test_ticket_update(self) -> None:
        expected_topic = u"Adding the brand new feature of auto tuning to my webapp"
        expected_message = u"Ticket with ID **[2](http://travelalittle.codebasehq.com/projects/adding-support-for-checking-events)**, category **Refactoring** has been updated by **Sameer Choubey**"
        self.send_and_test_stream_message('ticket_update', expected_topic, expected_message)
