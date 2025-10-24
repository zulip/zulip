from zerver.lib.webhooks.common import do_rename_topic_for_webhook
from zerver.models import Stream, Message
from zerver.lib.test_classes import ZulipTestCase

class GitHubTopicRenameWebhookTest(ZulipTestCase):
    def test_do_rename_topic_for_webhook(self) -> None:
        user = self.example_user("iago")
        stream_name = "GitHub"
        old_topic = "Old Title"
        new_topic = "New Title"

        # Create a stream and subscribe the user
        stream = self.make_stream(stream_name)
        self.subscribe(user, stream_name)

        # Send a message to simulate an existing topic
        message_id = self.send_stream_message(
            sender=user,
            stream_name=stream_name,
            topic_name=old_topic,
            content="Initial message content",
        )
        message = Message.objects.get(id=message_id)

        # Run your webhook rename logic
        result = do_rename_topic_for_webhook(user, stream_name, old_topic, new_topic)

        # Confirm everything worked
        self.assertTrue(result)
        updated_message = Message.objects.get(id=message.id)
        self.assertEqual(updated_message.topic_name(), new_topic)

