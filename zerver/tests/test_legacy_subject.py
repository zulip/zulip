import orjson

from zerver.lib.test_classes import ZulipTestCase


class LegacySubjectTest(ZulipTestCase):
    def test_legacy_subject(self) -> None:
        self.login("hamlet")

        payload = dict(
            type="stream",
            to=orjson.dumps("Verona").decode(),
            content="Test message",
        )

        payload["subject"] = "whatever"
        result = self.client_post("/json/messages", payload)
        self.assert_json_success(result)

        # You can't use both subject and topic.
        payload["topic"] = "whatever"
        result = self.client_post("/json/messages", payload)
        self.assert_json_error(result, "Can't decide between 'topic' and 'subject' arguments")
