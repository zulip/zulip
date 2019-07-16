# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest import mock

from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.actions import internal_send_private_message, do_add_submessage
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.upload import create_attachment
from zerver.models import (Message, Realm, Stream, ArchivedUserMessage, SubMessage,
                           ArchivedMessage, Attachment, ArchivedAttachment, UserMessage,
                           Reaction, ArchivedReaction, ArchivedSubMessage, ArchiveTransaction,
                           get_realm, get_user_profile_by_email, get_stream, get_system_bot)
from zerver.lib.retention import (
    archive_messages,
    move_messages_to_archive,
    restore_all_data_from_archive,
    clean_archived_data,
)

# Class with helper functions useful for testing archiving of reactions:
from zerver.tests.test_reactions import EmojiReactionBase

ZULIP_REALM_DAYS = 30
MIT_REALM_DAYS = 100

class RetentionTestingBase(ZulipTestCase):
    def _get_usermessage_ids(self, message_ids: List[int]) -> List[int]:
        return list(UserMessage.objects.filter(message_id__in=message_ids).values_list('id', flat=True))

    def _verify_archive_data(self, expected_message_ids: List[int],
                             expected_usermessage_ids: List[int]) -> None:
        self.assertEqual(
            set(ArchivedMessage.objects.values_list('id', flat=True)),
            set(expected_message_ids)
        )

        self.assertEqual(
            set(ArchivedUserMessage.objects.values_list('id', flat=True)),
            set(expected_usermessage_ids)
        )

        # Archived Messages and UserMessages should have been removed from the normal tables:
        self.assertEqual(Message.objects.filter(id__in=expected_message_ids).count(), 0)
        self.assertEqual(UserMessage.objects.filter(id__in=expected_usermessage_ids).count(), 0)

    def _verify_restored_data(self, expected_message_ids: List[int],
                              expected_usermessage_ids: List[int]) -> None:
        # Check that the data was restored:
        self.assertEqual(
            set(Message.objects.filter(id__in=expected_message_ids).values_list('id', flat=True)),
            set(expected_message_ids)
        )

        self.assertEqual(
            set(UserMessage.objects.filter(id__in=expected_usermessage_ids).values_list('id', flat=True)),
            set(expected_usermessage_ids)
        )

        # The Messages and UserMessages should still be in the archive - we don't delete them.
        self.assertEqual(
            set(ArchivedMessage.objects.values_list('id', flat=True)),
            set(expected_message_ids)
        )

        self.assertEqual(
            set(ArchivedUserMessage.objects.values_list('id', flat=True)),
            set(expected_usermessage_ids)
        )

class ArchiveMessagesTestingBase(RetentionTestingBase):
    def setUp(self) -> None:
        self.zulip_realm = get_realm('zulip')
        self.mit_realm = get_realm('zephyr')
        self._set_realm_message_retention_value(self.zulip_realm, ZULIP_REALM_DAYS)
        self._set_realm_message_retention_value(self.mit_realm, MIT_REALM_DAYS)

        # Set publication date of all existing messages to "now", so that we have full
        # control over what's expired and what isn't.
        Message.objects.all().update(pub_date=timezone_now())

    def _set_realm_message_retention_value(self, realm: Realm, retention_period: Optional[int]) -> None:
        realm.message_retention_days = retention_period
        realm.save()

    def _set_stream_message_retention_value(self, stream: Stream, retention_period: Optional[int]) -> None:
        stream.message_retention_days = retention_period
        stream.save()

    def _change_messages_pub_date(self, msgs_ids: List[int], pub_date: datetime) -> None:
        Message.objects.filter(id__in=msgs_ids).update(pub_date=pub_date)

    def _make_mit_messages(self, message_quantity: int, pub_date: datetime) -> Any:
        # send messages from mit.edu realm and change messages pub date
        sender = self.mit_user('espuser')
        recipient = self.mit_user('starnine')
        msg_ids = [self.send_personal_message(sender.email, recipient.email,
                                              sender_realm='zephyr')
                   for i in range(message_quantity)]

        self._change_messages_pub_date(msg_ids, pub_date)
        return msg_ids

    def _send_cross_realm_personal_message(self) -> int:
        # Send message from bot to users from different realm.
        bot_email = 'notification-bot@zulip.com'
        get_user_profile_by_email(bot_email)
        zulip_user = self.example_user("hamlet")
        msg_id = internal_send_private_message(
            realm=self.zulip_realm,
            sender=get_system_bot(bot_email),
            recipient_user=zulip_user,
            content='test message',
        )
        assert msg_id is not None
        return msg_id

    def _make_expired_zulip_messages(self, message_quantity: int) -> List[int]:
        msg_ids = list(Message.objects.order_by('id').filter(
                       sender__realm=self.zulip_realm).values_list('id', flat=True)[3:3 + message_quantity])
        self._change_messages_pub_date(
            msg_ids,
            timezone_now() - timedelta(ZULIP_REALM_DAYS+1)
        )

        return msg_ids

    def _send_messages_with_attachments(self) -> Dict[str, int]:
        user_profile = self.example_user("hamlet")
        sender_email = user_profile.email
        sample_size = 10
        realm_id = get_realm("zulip").id
        dummy_files = [
            ('zulip.txt', '%s/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt' % (realm_id,), sample_size),
            ('temp_file.py', '%s/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py' % (realm_id,), sample_size),
            ('abc.py', '%s/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py' % (realm_id,), sample_size)
        ]

        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, size)

        self.subscribe(user_profile, "Denmark")
        body = ("Some files here ...[zulip.txt](http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)" +
                "http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py.... Some more...." +
                "http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py").format(id=realm_id)

        expired_message_id = self.send_stream_message(sender_email, "Denmark", body)
        actual_message_id = self.send_stream_message(sender_email, "Denmark", body)
        other_message_id = self.send_stream_message("othello@zulip.com", "Denmark", body)
        self._change_messages_pub_date([expired_message_id], timezone_now() - timedelta(days=MIT_REALM_DAYS + 1))
        return {'expired_message_id': expired_message_id, 'actual_message_id': actual_message_id,
                'other_user_message_id': other_message_id}

class TestArchiveMessagesGeneral(ArchiveMessagesTestingBase):
    def test_no_expired_messages(self) -> None:
        archive_messages()

        self.assertEqual(ArchivedUserMessage.objects.count(), 0)
        self.assertEqual(ArchivedMessage.objects.count(), 0)

    def test_expired_messages_in_each_realm(self) -> None:
        """General test for archiving expired messages properly with
        multiple realms involved"""
        # Make some expired messages in MIT:
        expired_mit_msg_ids = self._make_mit_messages(
            5,
            timezone_now() - timedelta(days=MIT_REALM_DAYS+1)
        )
        # Make some non-expired messages in MIT:
        self._make_mit_messages(4, timezone_now() - timedelta(days=MIT_REALM_DAYS-1))

        # Change some Zulip messages to be expired:
        expired_zulip_msg_ids = list(Message.objects.order_by('id').filter(
            sender__realm=self.zulip_realm).values_list('id', flat=True)[3:10])
        self._change_messages_pub_date(
            expired_zulip_msg_ids,
            timezone_now() - timedelta(ZULIP_REALM_DAYS+1)
        )

        expired_msg_ids = expired_mit_msg_ids + expired_zulip_msg_ids
        expired_usermsg_ids = self._get_usermessage_ids(expired_msg_ids)

        archive_messages()
        self._verify_archive_data(expired_msg_ids, expired_usermsg_ids)

        restore_all_data_from_archive()
        self._verify_restored_data(expired_msg_ids, expired_usermsg_ids)

    def test_expired_messages_in_one_realm(self) -> None:
        """Test with a retention policy set for only the MIT realm"""
        self._set_realm_message_retention_value(self.zulip_realm, None)

        # Make some expired messages in MIT:
        expired_mit_msg_ids = self._make_mit_messages(
            5,
            timezone_now() - timedelta(days=MIT_REALM_DAYS+1)
        )
        # Make some non-expired messages in MIT:
        self._make_mit_messages(4, timezone_now() - timedelta(days=MIT_REALM_DAYS-1))

        # Change some Zulip messages pub_date, but the realm has no retention policy,
        # so they shouldn't get archived
        zulip_msg_ids = list(Message.objects.order_by('id').filter(
            sender__realm=self.zulip_realm).values_list('id', flat=True)[3:10])
        self._change_messages_pub_date(
            zulip_msg_ids,
            timezone_now() - timedelta(ZULIP_REALM_DAYS+1)
        )

        # Only MIT has a retention policy:
        expired_msg_ids = expired_mit_msg_ids
        expired_usermsg_ids = self._get_usermessage_ids(expired_msg_ids)

        archive_messages()
        self._verify_archive_data(expired_msg_ids, expired_usermsg_ids)

        restore_all_data_from_archive()
        self._verify_restored_data(expired_msg_ids, expired_usermsg_ids)

        self._set_realm_message_retention_value(self.zulip_realm, ZULIP_REALM_DAYS)

    def test_different_stream_realm_policies(self) -> None:
        verona = get_stream("Verona", self.zulip_realm)
        hamlet = self.example_email("hamlet")

        msg_id = self.send_stream_message(hamlet, "Verona", "test")
        usermsg_ids = self._get_usermessage_ids([msg_id])
        self._change_messages_pub_date([msg_id], timezone_now() - timedelta(days=2))

        # Don't archive if stream's retention policy set to -1:
        self._set_realm_message_retention_value(self.zulip_realm, 1)
        self._set_stream_message_retention_value(verona, -1)
        archive_messages()
        self._verify_archive_data([], [])

        # Don't archive if stream and realm have no retention policy:
        self._set_realm_message_retention_value(self.zulip_realm, None)
        self._set_stream_message_retention_value(verona, None)
        archive_messages()
        self._verify_archive_data([], [])

        # Archive if stream has a retention policy set:
        self._set_realm_message_retention_value(self.zulip_realm, None)
        self._set_stream_message_retention_value(verona, 1)
        archive_messages()
        self._verify_archive_data([msg_id], usermsg_ids)

    def test_cross_realm_personal_message_archiving(self) -> None:
        """Check that cross-realm personal messages get correctly archived. """
        msg_ids = [self._send_cross_realm_personal_message() for i in range(1, 7)]
        usermsg_ids = self._get_usermessage_ids(msg_ids)
        # Make the message expired on the recipient's realm:
        self._change_messages_pub_date(msg_ids, timezone_now() - timedelta(ZULIP_REALM_DAYS+1))

        archive_messages()
        self._verify_archive_data(msg_ids, usermsg_ids)

    def test_archiving_interrupted(self) -> None:
        """ Check that queries get rolled back to a consistent state
        if archiving gets interrupted in the middle of processing a chunk. """
        expired_msg_ids = self._make_expired_zulip_messages(7)
        expired_usermsg_ids = self._get_usermessage_ids(expired_msg_ids)

        # Insert an exception near the end of the archiving process of a chunk:
        with mock.patch("zerver.lib.retention.delete_messages", side_effect=Exception):
            with self.assertRaises(Exception):
                archive_messages(chunk_size=1000)  # Specify large chunk_size to ensure things happen in a single batch

            # Archiving code has been executed, but because we got an exception, things should have been rolled back:
            self._verify_archive_data([], [])

            self.assertEqual(
                set(Message.objects.filter(id__in=expired_msg_ids).values_list('id', flat=True)),
                set(expired_msg_ids)
            )
            self.assertEqual(
                set(UserMessage.objects.filter(id__in=expired_usermsg_ids).values_list('id', flat=True)),
                set(expired_usermsg_ids)
            )

    def test_archive_message_tool(self) -> None:
        """End-to-end test of the archiving tool, directly calling
        archive_messages."""
        # Make some expired messages in MIT:
        expired_mit_msg_ids = self._make_mit_messages(
            5,
            timezone_now() - timedelta(days=MIT_REALM_DAYS+1)
        )
        # Make some non-expired messages in MIT:
        self._make_mit_messages(4, timezone_now() - timedelta(days=MIT_REALM_DAYS-1))

        # Change some Zulip messages to be expired:
        expired_zulip_msg_ids = self._make_expired_zulip_messages(7)

        expired_crossrealm_msg_id = self._send_cross_realm_personal_message()
        # Make the message expired in the recipient's realm:
        self._change_messages_pub_date(
            [expired_crossrealm_msg_id],
            timezone_now() - timedelta(ZULIP_REALM_DAYS+1)
        )

        expired_msg_ids = expired_mit_msg_ids + expired_zulip_msg_ids + [expired_crossrealm_msg_id]
        expired_usermsg_ids = self._get_usermessage_ids(expired_msg_ids)

        archive_messages(chunk_size=2)  # Specify low chunk_size to test batching.
        # Make sure we archived what neeeded:
        self._verify_archive_data(expired_msg_ids, expired_usermsg_ids)

        restore_all_data_from_archive()
        self._verify_restored_data(expired_msg_ids, expired_usermsg_ids)

    def test_archiving_attachments(self) -> None:
        """End-to-end test for the logic for archiving attachments.  This test
        is hard to read without first reading _send_messages_with_attachments"""
        msgs_ids = self._send_messages_with_attachments()

        # First, confirm deleting the oldest message
        # (`expired_message_id`) creates ArchivedAttachment objects
        # and associates that message ID with them, but does not
        # delete the Attachment object.
        archive_messages()
        self.assertEqual(ArchivedAttachment.objects.count(), 3)
        self.assertEqual(
            list(ArchivedAttachment.objects.distinct('messages__id').values_list('messages__id',
                 flat=True)),
            [msgs_ids['expired_message_id']]
        )
        self.assertEqual(Attachment.objects.count(), 3)

        # Now make `actual_message_id` expired too.  We still don't
        # delete the Attachment objects.
        self._change_messages_pub_date([msgs_ids['actual_message_id']],
                                       timezone_now() - timedelta(days=MIT_REALM_DAYS + 1))
        archive_messages()
        self.assertEqual(Attachment.objects.count(), 3)

        # Finally, make the last message mentioning those attachments
        # expired.  We should now delete the Attachment objects and
        # each ArchivedAttachment object should list all 3 messages.
        self._change_messages_pub_date([msgs_ids['other_user_message_id']],
                                       timezone_now() - timedelta(days=MIT_REALM_DAYS + 1))

        archive_messages()
        self.assertEqual(Attachment.objects.count(), 0)
        self.assertEqual(ArchivedAttachment.objects.count(), 3)
        self.assertEqual(
            list(ArchivedAttachment.objects.distinct('messages__id').order_by('messages__id').values_list(
                'messages__id', flat=True)),
            sorted(msgs_ids.values())
        )

        restore_all_data_from_archive()
        # Attachments should have been restored:
        self.assertEqual(Attachment.objects.count(), 3)
        self.assertEqual(ArchivedAttachment.objects.count(), 3)  # Archived data doesn't get deleted by restoring.
        self.assertEqual(
            list(Attachment.objects.distinct('messages__id').order_by('messages__id').values_list(
                'messages__id', flat=True)),
            sorted(msgs_ids.values())
        )

    def test_restoring_and_rearchiving(self) -> None:
        expired_msg_ids = self._make_mit_messages(
            7,
            timezone_now() - timedelta(days=MIT_REALM_DAYS+1)
        )
        expired_usermsg_ids = self._get_usermessage_ids(expired_msg_ids)

        archive_messages(chunk_size=4)
        self._verify_archive_data(expired_msg_ids, expired_usermsg_ids)

        transactions = ArchiveTransaction.objects.all()
        self.assertEqual(len(transactions), 2)  # With chunk_size 4, there should be 2 transactions

        restore_all_data_from_archive()
        transactions[0].refresh_from_db()
        transactions[1].refresh_from_db()
        self.assertTrue(transactions[0].restored)
        self.assertTrue(transactions[1].restored)

        archive_messages(chunk_size=10)
        self._verify_archive_data(expired_msg_ids, expired_usermsg_ids)

        transactions = ArchiveTransaction.objects.order_by("id")
        self.assertEqual(len(transactions), 3)

        archived_messages = ArchivedMessage.objects.filter(id__in=expired_msg_ids)
        # Check that the re-archived messages are correctly assigned to the new transaction:
        for message in archived_messages:
            self.assertEqual(message.archive_transaction_id, transactions[2].id)

class TestArchivingSubMessages(ArchiveMessagesTestingBase):
    def test_archiving_submessages(self) -> None:
        expired_msg_ids = self._make_expired_zulip_messages(2)
        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')

        do_add_submessage(
            realm=self.zulip_realm,
            sender_id=cordelia.id,
            message_id=expired_msg_ids[0],
            msg_type='whatever',
            content='{"name": "alice", "salary": 20}'
        )
        do_add_submessage(
            realm=self.zulip_realm,
            sender_id=hamlet.id,
            message_id=expired_msg_ids[0],
            msg_type='whatever',
            content='{"name": "john", "salary": 30}'
        )

        do_add_submessage(
            realm=self.zulip_realm,
            sender_id=cordelia.id,
            message_id=expired_msg_ids[1],
            msg_type='whatever',
            content='{"name": "jack", "salary": 10}'
        )

        submessage_ids = list(
            SubMessage.objects.filter(message_id__in=expired_msg_ids).values_list('id', flat=True)
        )

        self.assertEqual(len(submessage_ids), 3)
        self.assertEqual(SubMessage.objects.filter(id__in=submessage_ids).count(), 3)
        archive_messages()
        self.assertEqual(SubMessage.objects.filter(id__in=submessage_ids).count(), 0)

        self.assertEqual(
            set(ArchivedSubMessage.objects.filter(id__in=submessage_ids).values_list('id', flat=True)),
            set(submessage_ids)
        )

        restore_all_data_from_archive()
        self.assertEqual(
            set(SubMessage.objects.filter(id__in=submessage_ids).values_list('id', flat=True)),
            set(submessage_ids)
        )

class TestArchivingReactions(ArchiveMessagesTestingBase, EmojiReactionBase):
    def test_archiving_reactions(self) -> None:
        expired_msg_ids = self._make_expired_zulip_messages(2)

        self.post_zulip_reaction(expired_msg_ids[0], 'hamlet')
        self.post_zulip_reaction(expired_msg_ids[0], 'cordelia')

        self.post_zulip_reaction(expired_msg_ids[1], 'hamlet')

        reaction_ids = list(
            Reaction.objects.filter(message_id__in=expired_msg_ids).values_list('id', flat=True)
        )

        self.assertEqual(len(reaction_ids), 3)
        self.assertEqual(Reaction.objects.filter(id__in=reaction_ids).count(), 3)
        archive_messages()
        self.assertEqual(Reaction.objects.filter(id__in=reaction_ids).count(), 0)

        self.assertEqual(
            set(ArchivedReaction.objects.filter(id__in=reaction_ids).values_list('id', flat=True)),
            set(reaction_ids)
        )

        restore_all_data_from_archive()
        self.assertEqual(
            set(Reaction.objects.filter(id__in=reaction_ids).values_list('id', flat=True)),
            set(reaction_ids)
        )

class MoveMessageToArchiveBase(RetentionTestingBase):
    def setUp(self) -> None:
        self.sender = 'hamlet@zulip.com'
        self.recipient = 'cordelia@zulip.com'

    def _create_attachments(self) -> None:
        sample_size = 10
        realm_id = get_realm("zulip").id
        dummy_files = [
            ('zulip.txt', '%s/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt' % (realm_id,), sample_size),
            ('temp_file.py', '%s/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py' % (realm_id,), sample_size),
            ('abc.py', '%s/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py' % (realm_id,), sample_size),
            ('hello.txt', '%s/31/4CBjtTLYZhk66pZrF8hnYGwc/hello.txt' % (realm_id,), sample_size),
            ('new.py', '%s/31/4CBjtTLYZhk66pZrF8hnYGwc/new.py' % (realm_id,), sample_size)
        ]
        user_profile = self.example_user('hamlet')
        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, size)

    def _assert_archive_empty(self) -> None:
        self.assertFalse(ArchivedUserMessage.objects.exists())
        self.assertFalse(ArchivedMessage.objects.exists())
        self.assertFalse(ArchivedAttachment.objects.exists())

class MoveMessageToArchiveGeneral(MoveMessageToArchiveBase):
    def test_personal_messages_archiving(self) -> None:
        msg_ids = [self.send_personal_message(self.sender, self.recipient)
                   for i in range(0, 3)]
        usermsg_ids = self._get_usermessage_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._verify_archive_data(msg_ids, usermsg_ids)

        restore_all_data_from_archive()
        self._verify_restored_data(msg_ids, usermsg_ids)

    def test_stream_messages_archiving(self) -> None:
        msg_ids = [self.send_stream_message(self.sender, "Verona")
                   for i in range(0, 3)]
        usermsg_ids = self._get_usermessage_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._verify_archive_data(msg_ids, usermsg_ids)

        restore_all_data_from_archive()
        self._verify_restored_data(msg_ids, usermsg_ids)

    def test_archiving_messages_second_time(self) -> None:
        msg_ids = [self.send_stream_message(self.sender, "Verona")
                   for i in range(0, 3)]
        usermsg_ids = self._get_usermessage_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._verify_archive_data(msg_ids, usermsg_ids)

        with self.assertRaises(Message.DoesNotExist):
            move_messages_to_archive(message_ids=msg_ids)

    def test_archiving_messages_with_attachment(self) -> None:
        self._create_attachments()
        realm_id = get_realm("zulip").id

        body1 = """Some files here ...[zulip.txt](
            http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)
            http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py ....
            Some more.... http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py
        """.format(id=realm_id)
        body2 = """Some files here
            http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt ...
            http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/hello.txt ....
            http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/new.py ....
        """.format(id=realm_id)

        msg_ids = [
            self.send_personal_message(self.sender, self.recipient, body1),
            self.send_personal_message(self.sender, self.recipient, body2)
        ]

        attachment_id_to_message_ids = {}  # type: Dict[int, List[int]]
        attachment_ids = list(
            Attachment.objects.filter(messages__id__in=msg_ids).values_list("id", flat=True)
        )
        for attachment_id in attachment_ids:
            attachment_id_to_message_ids[attachment_id] = list(
                Message.objects.filter(attachment__id=attachment_id).values_list("id", flat=True)
            )

        usermsg_ids = self._get_usermessage_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._verify_archive_data(msg_ids, usermsg_ids)

        self.assertFalse(Attachment.objects.exists())
        archived_attachment_ids = list(
            ArchivedAttachment.objects.filter(messages__id__in=msg_ids).values_list("id", flat=True)
        )

        self.assertEqual(set(attachment_ids), set(archived_attachment_ids))
        for attachment_id in archived_attachment_ids:
            self.assertEqual(
                set(attachment_id_to_message_ids[attachment_id]),
                set(ArchivedMessage.objects.filter(
                    archivedattachment__id=attachment_id).values_list("id", flat=True))
            )

        restore_all_data_from_archive()
        self._verify_restored_data(msg_ids, usermsg_ids)

        restored_attachment_ids = list(
            Attachment.objects.filter(messages__id__in=msg_ids).values_list("id", flat=True)
        )

        self.assertEqual(set(attachment_ids), set(restored_attachment_ids))
        for attachment_id in restored_attachment_ids:
            self.assertEqual(
                set(attachment_id_to_message_ids[attachment_id]),
                set(Message.objects.filter(attachment__id=attachment_id).values_list("id", flat=True))
            )

    def test_archiving_message_with_shared_attachment(self) -> None:
        # Make sure that attachments still in use in other messages don't get deleted:
        self._create_attachments()
        realm_id = get_realm("zulip").id

        body = """Some files here ...[zulip.txt](
            http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)
            http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py ....
            Some more.... http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py ...
            http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/new.py ....
            http://localhost:9991/user_uploads/{id}/31/4CBjtTLYZhk66pZrF8hnYGwc/hello.txt ....
        """.format(id=realm_id)

        msg_id = self.send_personal_message(self.sender, self.recipient, body)
        # Simulate a reply with the same contents.
        reply_msg_id = self.send_personal_message(
            from_email=self.recipient,
            to_email=self.sender,
            content=body,
        )

        usermsg_ids = self._get_usermessage_ids([msg_id])
        attachment_ids = list(
            Attachment.objects.filter(messages__id=msg_id).values_list("id", flat=True)
        )

        self._assert_archive_empty()
        # Archive one of the messages:
        move_messages_to_archive(message_ids=[msg_id])
        self._verify_archive_data([msg_id], usermsg_ids)
        # Attachments shouldn't have been deleted, as the second message links to them:
        self.assertEqual(Attachment.objects.count(), 5)

        self.assertEqual(
            set(ArchivedAttachment.objects.filter(messages__id=msg_id).values_list("id", flat=True)),
            set(attachment_ids)
        )

        # Restore the first message:
        restore_all_data_from_archive()
        # Archive the second:
        move_messages_to_archive(message_ids=[reply_msg_id])
        # The restored messages links to the Attachments, so they shouldn't be deleted:
        self.assertEqual(Attachment.objects.count(), 5)

        # Archive the first message again:
        move_messages_to_archive(message_ids=[msg_id])
        # Now the attachment should have been deleted:
        self.assertEqual(Attachment.objects.count(), 0)

        # Restore everything:
        restore_all_data_from_archive()
        self.assertEqual(
            set(Attachment.objects.filter(messages__id=msg_id).values_list("id", flat=True)),
            set(attachment_ids)
        )

class MoveMessageToArchiveWithSubMessages(MoveMessageToArchiveBase):
    def test_archiving_message_with_submessages(self) -> None:
        msg_id = self.send_stream_message(self.sender, "Verona")
        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')

        do_add_submessage(
            realm=get_realm('zulip'),
            sender_id=cordelia.id,
            message_id=msg_id,
            msg_type='whatever',
            content='{"name": "alice", "salary": 20}'
        )
        do_add_submessage(
            realm=get_realm('zulip'),
            sender_id=hamlet.id,
            message_id=msg_id,
            msg_type='whatever',
            content='{"name": "john", "salary": 30}'
        )

        submessage_ids = list(
            SubMessage.objects.filter(message_id=msg_id).values_list('id', flat=True)
        )

        self.assertEqual(SubMessage.objects.filter(id__in=submessage_ids).count(), 2)
        move_messages_to_archive(message_ids=[msg_id])

        self.assertEqual(
            set(ArchivedSubMessage.objects.filter(message_id=msg_id).values_list("id", flat=True)),
            set(submessage_ids)
        )
        self.assertEqual(SubMessage.objects.filter(id__in=submessage_ids).count(), 0)

        restore_all_data_from_archive()
        self.assertEqual(
            set(SubMessage.objects.filter(id__in=submessage_ids).values_list('id', flat=True)),
            set(submessage_ids)
        )

class MoveMessageToArchiveWithReactions(MoveMessageToArchiveBase, EmojiReactionBase):
    def test_archiving_message_with_reactions(self) -> None:
        msg_id = self.send_stream_message(self.sender, "Verona")

        self.post_zulip_reaction(msg_id, 'hamlet')
        self.post_zulip_reaction(msg_id, 'cordelia')

        reaction_ids = list(
            Reaction.objects.filter(message_id=msg_id).values_list('id', flat=True)
        )

        self.assertEqual(Reaction.objects.filter(id__in=reaction_ids).count(), 2)
        move_messages_to_archive(message_ids=[msg_id])

        self.assertEqual(
            set(ArchivedReaction.objects.filter(message_id=msg_id).values_list("id", flat=True)),
            set(reaction_ids)
        )
        self.assertEqual(Reaction.objects.filter(id__in=reaction_ids).count(), 0)

        restore_all_data_from_archive()
        self.assertEqual(
            set(Reaction.objects.filter(id__in=reaction_ids).values_list('id', flat=True)),
            set(reaction_ids)
        )

class TestCleaningArchive(ArchiveMessagesTestingBase):
    def test_clean_archived_data(self) -> None:
        self._make_expired_zulip_messages(7)
        archive_messages(chunk_size=2)  # Small chunk size to have multiple transactions

        transactions = list(ArchiveTransaction.objects.all())
        for transaction in transactions[0:-1]:
            transaction.timestamp = timezone_now() - timedelta(
                days=settings.ARCHIVED_DATA_VACUUMING_DELAY_DAYS + 1)
            transaction.save()

        message_ids_to_clean = list(ArchivedMessage.objects.filter(
            archive_transaction__in=transactions[0:-1]).values_list('id', flat=True))

        clean_archived_data()
        remaining_transactions = list(ArchiveTransaction.objects.all())
        self.assertEqual(len(remaining_transactions), 1)
        # All transactions except the last one were deleted:
        self.assertEqual(remaining_transactions[0].id, transactions[-1].id)
        # And corresponding ArchivedMessages should have been deleted:
        self.assertFalse(ArchivedMessage.objects.filter(id__in=message_ids_to_clean).exists())
        self.assertFalse(ArchivedUserMessage.objects.filter(message_id__in=message_ids_to_clean).exists())

        for message in ArchivedMessage.objects.all():
            self.assertEqual(message.archive_transaction_id, remaining_transactions[0].id)
