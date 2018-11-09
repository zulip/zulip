from zerver.lib.test_classes import (
    ZulipTestCase,
)

class LegacySubjectTest(ZulipTestCase):
    def test_legacy_subject(self) -> None:
        self.login(self.example_email("hamlet"))

        payload = dict(
            type='stream',
            to='Verona',
            client='test suite',
            content='Test message',
        )

        payload['subject'] = 'whatever'
        result = self.client_post("/json/messages", payload)
        self.assert_json_success(result)

        # You can't use both subject and topic.
        payload['topic'] = 'whatever'
        result = self.client_post("/json/messages", payload)
        self.assert_json_error(result, "Can't decide between 'topic' and 'subject' arguments")
