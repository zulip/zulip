

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import delete_topic, update_topic
from zerver.models import get_stream, Topic


class TopicTest(ZulipTestCase):
    def test_topic_update_existing(self) -> None:
        user = self.example_user("aaron")
        stream = get_stream("Verona", user.realm)
        topic_name = "Topic"
        new_topic_name = "New Topic"
        new_stream = stream = get_stream("Denmark", user.realm)

        Topic.objects.create(
            realm=user.realm,
            stream=stream,
            topic_name=topic_name,
            locked=True
        )

        updated_topic = update_topic(
            realm_id=user.realm.id,
            stream_id=stream.id,
            topic_name=topic_name,
            new_topic_name=new_topic_name,
            new_stream_id=new_stream.id,
            toggle_locked=True,
        )

        self.assertFalse(updated_topic.locked)
        self.assertEqual(updated_topic.topic_name, new_topic_name)
        self.assertEqual(updated_topic.stream.id, new_stream.id)


    def test_topic_update_no_topic(self) -> None:
        user = self.example_user("aaron")
        stream = get_stream("Verona", user.realm)
        topic_name = "No Topic"

        updated_topic = update_topic(
            realm_id=user.realm.id,
            stream_id=stream.id,
            topic_name=topic_name,
        )

        self.assertEqual(updated_topic, None)


    def test_topic_delete_exists(self) -> None:
        user = self.example_user("aaron")
        stream = get_stream("Verona", user.realm)
        topic_name = "Delete Topic"

        Topic.objects.create(
            realm=user.realm,
            stream=stream,
            topic_name=topic_name,
            locked=True
        )

        topic_deleted = delete_topic(
            realm_id=user.realm.id,
            stream_id=stream.id,
            topic_name=topic_name,
        )

        self.assertTrue(topic_deleted)


    def test_topic_delete_noexists(self) -> None:
        user = self.example_user("aaron")
        stream = get_stream("Verona", user.realm)
        topic_name = "No Topic"

        topic_deleted = delete_topic(
            realm_id=user.realm.id,
            stream_id=stream.id,
            topic_name=topic_name,
        )

        self.assertFalse(topic_deleted)
