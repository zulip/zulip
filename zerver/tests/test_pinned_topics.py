from zerver.lib.pinned_topics import get_pinned_topics
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_stream


class BasicTests(ZulipTestCase):
    def test_add(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        stream = get_stream("Verona", user.realm)

        url = "/api/v1/pin_topic"

        data = dict(stream_id=stream.id, topic_name="fred")
        result = self.api_post(user, url, data)
        self.assert_json_success(result)

        self.assertEqual(get_pinned_topics(user), [dict(stream_id=stream.id, topic_name="fred")])

        url = "/api/v1/unpin_topic"
        result = self.api_post(user, url, data)
        self.assert_json_success(result)
        self.assertEqual(get_pinned_topics(user), [])
