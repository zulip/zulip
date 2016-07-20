# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.test import TestCase

import datetime
import mock
from six.moves import range

from zerver.lib.actions import (
    create_stream_if_needed,
)
from zerver.lib.migrate import (
    create_topics_for_message_range,
    migrate_all_messages,
)
from zerver.models import (
    Client,
    Message,
    Recipient,
    Topic,
    get_realm,
    get_user_profile_by_email,
)

class TestTopicMigration(TestCase):
    def test_create_topics_for_message_range(self):
        # type: () -> None
        realm = get_realm("zulip.com")
        sending_client, _ = Client.objects.get_or_create(name="test suite")
        sender = get_user_profile_by_email('othello@zulip.com')

        num_streams = 10
        num_topics = 3
        num_msgs_per_topic = 5

        low_msg_id = Message.objects.order_by('-id')[0].id + 1

        for i in range(num_streams):
            stream_name = 'stream %d' % (i,)
            stream, _ = create_stream_if_needed(realm, stream_name)
            stream_recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)

            for j in range(num_topics):
                topic_name = 'subject %d' % (j,)

                for k in range(num_msgs_per_topic):
                    content = 'msg (%d,%d,%d)' % (i, j, k)

                    message = Message(
                        sender=sender,
                        recipient=stream_recipient,
                        subject=topic_name,
                        content=content,
                        pub_date=datetime.datetime.now(),
                        sending_client=sending_client,
                        last_edit_time=datetime.datetime.now(),
                        edit_history='[]'
                    )
                    with mock.patch('zerver.models.Message.update_topic'):
                        message.save()

        high_msg_id = Message.objects.order_by('-id')[0].id + 1

        # Do some sanity checking on our message range.
        # Our message id range may be greater than expected_num_saved,
        # due to rollbacks from prior running tests, but that is ok
        # for our purposes.
        expected_num_saved = num_streams * num_topics * num_msgs_per_topic
        self.assertTrue((high_msg_id - low_msg_id) >= expected_num_saved)

        # Blow away Topic objects, because some may have been
        # created by our pre-save hooks.
        Topic.objects.all().delete()
        self.assertEqual(Topic.objects.count(), 0)

        status_update = create_topics_for_message_range(
            low_msg_id=low_msg_id,
            high_msg_id=high_msg_id,
        ) # type: str

        expected_num_topics = num_streams * num_topics # type: int
        self.assertEqual(Topic.objects.count(), expected_num_topics)
        expected_status_update = '%d Topic rows created' % (expected_num_topics,)
        self.assertEqual(status_update, expected_status_update)

        # Now, test idempotency..we can run this again, and it
        # won't try to create new topics.
        status_update = create_topics_for_message_range(
            low_msg_id=low_msg_id,
            high_msg_id=high_msg_id,
        )
        self.assertEqual(status_update, '0 Topic rows created')

        expected_num_topics = num_streams * num_topics
        self.assertEqual(Topic.objects.count(), expected_num_topics)

        # Make sure 'subject 1' has entries for each of its streams.
        self.assertEqual(Topic.objects.filter(name='subject 1').count(), num_streams)

    def test_full_migration(self):
        # type: () -> None
        # This is mostly a don't-explode test.  To debug
        # migrate_all_messages() while you are in test mode,
        # you can set verbose to True here.
        migrate_all_messages(
            range_method=create_topics_for_message_range,
            batch_size=10,
            max_num_batches=3,
            verbose=False,
        )
