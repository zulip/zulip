# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.utils.timezone import now as timezone_now

from zerver.lib.actions import internal_send_private_message, do_add_submessage
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.upload import create_attachment
from zerver.models import (Message, Realm, UserProfile, ArchivedUserMessage, SubMessage,
                           ArchivedMessage, Attachment, ArchivedAttachment, UserMessage,
                           Reaction,
                           get_realm, get_user_profile_by_email, get_system_bot)
from zerver.lib.retention import (
    archive_messages,
    clean_expired,
    move_expired_to_archive,
    move_messages_to_archive
)

# Class with helper functions useful for testing archiving of reactions:
from zerver.tests.test_reactions import EmojiReactionBase

ZULIP_REALM_DAYS = 30
MIT_REALM_DAYS = 100

class RetentionTestingBase(ZulipTestCase):
    """
        Test receiving expired messages retention tool.
    """

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

    def _send_cross_realm_message(self) -> int:
        # Send message from bot to users from different realm.
        bot_email = 'notification-bot@zulip.com'
        get_user_profile_by_email(bot_email)
        mit_user = UserProfile.objects.filter(realm=self.mit_realm).first()
        msg_id = internal_send_private_message(
            realm=mit_user.realm,
            sender=get_system_bot(bot_email),
            recipient_user=mit_user,
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

    def _verify_archive_data(self, expected_message_ids: List[int]) -> None:
        self.assertEqual(
            set(ArchivedMessage.objects.values_list('id', flat=True)),
            set(Message.objects.filter(id__in=expected_message_ids).values_list('id', flat=True))
        )

        self.assertEqual(
            set(ArchivedUserMessage.objects.values_list('id', flat=True)),
            set(UserMessage.objects.filter(message_id__in=expected_message_ids).values_list('id', flat=True))
        )

    def _send_messages_with_attachments(self) -> Dict[str, int]:
        user_profile = self.example_user("hamlet")
        sender_email = user_profile.email
        sample_size = 10
        dummy_files = [
            ('zulip.txt', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt', sample_size),
            ('temp_file.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py', sample_size),
            ('abc.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py', sample_size)
        ]

        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, size)

        self.subscribe(user_profile, "Denmark")
        body = "Some files here ...[zulip.txt](http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)" + \
               "http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py.... Some more...." + \
               "http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py"

        expired_message_id = self.send_stream_message(sender_email, "Denmark", body)
        actual_message_id = self.send_stream_message(sender_email, "Denmark", body)
        other_message_id = self.send_stream_message("othello@zulip.com", "Denmark", body)
        self._change_messages_pub_date([expired_message_id], timezone_now() - timedelta(days=MIT_REALM_DAYS + 1))
        return {'expired_message_id': expired_message_id, 'actual_message_id': actual_message_id,
                'other_user_message_id': other_message_id}

class TestArchivingGeneral(RetentionTestingBase):
    def test_no_expired_messages(self) -> None:
        move_expired_to_archive()

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
        move_expired_to_archive()

        self.assertEqual(ArchivedMessage.objects.count(), len(expired_msg_ids))
        self.assertEqual(
            ArchivedUserMessage.objects.count(),
            UserMessage.objects.filter(message_id__in=expired_msg_ids).count()
        )

        self._verify_archive_data(expired_msg_ids)

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
        move_expired_to_archive()

        self.assertEqual(ArchivedMessage.objects.count(), len(expired_msg_ids))
        self.assertEqual(
            ArchivedUserMessage.objects.count(),
            UserMessage.objects.filter(message_id__in=expired_msg_ids).count()
        )

        self._verify_archive_data(expired_msg_ids)

        self._set_realm_message_retention_value(self.zulip_realm, ZULIP_REALM_DAYS)

    """TODO: Cross realm message archiving and its testing  needs more work """

    def test_cross_realm_messages_archiving_one_realm_expired(self) -> None:
        """Test that a cross-realm message that is expired in only
        one of the realms only has the UserMessage for that realm archived"""
        msg_id = self._send_cross_realm_message()
        # Make the message expired on Zulip only:
        self._change_messages_pub_date([msg_id], timezone_now() - timedelta(ZULIP_REALM_DAYS+1))

        move_expired_to_archive()

        self.assertEqual(ArchivedMessage.objects.count(), 1)
        self.assertEqual(ArchivedUserMessage.objects.count(), 1)

        clean_expired()

        self.assertEqual(UserMessage.objects.filter(message_id=msg_id).count(), 1)
        self.assertTrue(Message.objects.filter(id=msg_id).exists())

    def test_cross_realm_messages_archiving_two_realm_expired(self) -> None:
        """Check that archiving a message that's expired in both
        realms is archived both in Message and UserMessage."""
        msg_id = self._send_cross_realm_message()
        # Make the message expired on both realms:
        self._change_messages_pub_date([msg_id], timezone_now() - timedelta(MIT_REALM_DAYS+1))

        move_expired_to_archive()

        self.assertEqual(ArchivedMessage.objects.count(), 1)
        self.assertEqual(ArchivedUserMessage.objects.count(), 2)

        clean_expired()

        self.assertEqual(UserMessage.objects.filter(message_id=msg_id).count(), 0)
        self.assertFalse(Message.objects.filter(id=msg_id).exists())

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

        expired_crossrealm_msg_id = self._send_cross_realm_message()
        # Make the message expired on both realms:
        self._change_messages_pub_date(
            [expired_crossrealm_msg_id],
            timezone_now() - timedelta(MIT_REALM_DAYS+1)
        )

        expired_msg_ids = expired_mit_msg_ids + expired_zulip_msg_ids + [expired_crossrealm_msg_id]
        # We explicitly call list() because we need to force evaluation of the query, before the
        # UserMessage objects get deleted from the database by archive_messages():
        expired_usermsg_ids = list(UserMessage.objects.filter(
            message_id__in=expired_msg_ids).values_list('id', flat=True))

        archive_messages()
        # Make sure we archived what neeeded:
        self.assertEqual(set(ArchivedMessage.objects.values_list('id', flat=True)),
                         set(expired_msg_ids))
        self.assertEqual(
            set(ArchivedUserMessage.objects.values_list('id', flat=True)),
            set(expired_usermsg_ids)
        )

        # Check that the archived messages were deleted:
        self.assertFalse(Message.objects.filter(id__in=expired_msg_ids).exists())
        self.assertFalse(UserMessage.objects.filter(id__in=expired_usermsg_ids).exists())

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

class TestArchivingSubMessages(RetentionTestingBase):
    def test_archiving_submessages(self) -> None:
        # TODO: Expand this accordingly, when archiving submessages is actually implemented.
        # For now, we just test if submessages of an archived message get correctly deleted.
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

class TestArchivingReactions(RetentionTestingBase, EmojiReactionBase):
    def test_archiving_reactions(self) -> None:
        # TODO: Expand this accordingly, when archiving reactions is actually implemented.
        # For now, we just test if reactions to an archived message get correctly deleted.
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

class TestMoveMessageToArchive(ZulipTestCase):
    def setUp(self) -> None:
        self.sender = 'hamlet@zulip.com'
        self.recipient = 'cordelia@zulip.com'

    def _create_attachments(self) -> None:
        sample_size = 10
        dummy_files = [
            ('zulip.txt', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt', sample_size),
            ('temp_file.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py', sample_size),
            ('abc.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py', sample_size),
            ('hello.txt', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/hello.txt', sample_size),
            ('new.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/new.py', sample_size)
        ]
        user_profile = self.example_user('hamlet')
        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, size)

    def _get_usermsg_ids(self, msg_ids: List[int]) -> List[int]:
        return list(UserMessage.objects.filter(
                    message_id__in=msg_ids).order_by('id').values_list('id', flat=True))

    def _assert_archive_empty(self) -> None:
        self.assertFalse(ArchivedUserMessage.objects.exists())
        self.assertFalse(ArchivedMessage.objects.exists())
        self.assertFalse(ArchivedAttachment.objects.exists())

    def _check_messages_after_archiving(self, msg_ids: List[int], usermsg_ids: List[int]) -> None:
        self.assertEqual(
            set(ArchivedMessage.objects.filter(id__in=msg_ids).values_list('id', flat=True)),
            set(msg_ids)
        )
        self.assertEqual(
            set(ArchivedUserMessage.objects.filter(id__in=usermsg_ids).values_list('id', flat=True)),
            set(usermsg_ids)
        )

        self.assertFalse(Message.objects.filter(id__in=msg_ids).exists())
        self.assertFalse(UserMessage.objects.filter(id__in=usermsg_ids).exists())

    def test_personal_messages_archiving(self) -> None:
        msg_ids = [self.send_personal_message(self.sender, self.recipient)
                   for i in range(0, 3)]
        usermsg_ids = self._get_usermsg_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._check_messages_after_archiving(msg_ids, usermsg_ids)

    def test_stream_messages_archiving(self) -> None:
        msg_ids = [self.send_stream_message(self.sender, "Verona")
                   for i in range(0, 3)]
        usermsg_ids = self._get_usermsg_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._check_messages_after_archiving(msg_ids, usermsg_ids)

    def test_archiving_messages_second_time(self) -> None:
        msg_ids = [self.send_stream_message(self.sender, "Verona")
                   for i in range(0, 3)]
        usermsg_ids = self._get_usermsg_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._check_messages_after_archiving(msg_ids, usermsg_ids)

        with self.assertRaises(Message.DoesNotExist):
            move_messages_to_archive(message_ids=msg_ids)

    def test_archiving_messages_with_attachment(self) -> None:
        self._create_attachments()

        body1 = """Some files here ...[zulip.txt](
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py ....
            Some more.... http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py
        """
        body2 = """Some files here
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt ...
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/hello.txt ....
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/new.py ....
        """

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

        usermsg_ids = self._get_usermsg_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._check_messages_after_archiving(msg_ids, usermsg_ids)

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

    def test_archiving_message_with_shared_attachment(self) -> None:
        # Make sure that attachments still in use in other messages don't get deleted:
        self._create_attachments()

        body = """Some files here ...[zulip.txt](
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py ....
            Some more.... http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py ...
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/new.py ....
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/hello.txt ....
        """

        msg_id = self.send_personal_message(self.sender, self.recipient, body)
        # Simulate a reply with the same contents.
        reply_msg_id = self.send_personal_message(
            from_email=self.recipient,
            to_email=self.sender,
            content=body,
        )

        usermsg_ids = self._get_usermsg_ids([msg_id])
        attachment_ids = list(
            Attachment.objects.filter(messages__id=msg_id).values_list("id", flat=True)
        )

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=[msg_id])
        self._check_messages_after_archiving([msg_id], usermsg_ids)
        self.assertEqual(Attachment.objects.count(), 5)

        self.assertEqual(
            set(ArchivedAttachment.objects.filter(messages__id=msg_id).values_list("id", flat=True)),
            set(attachment_ids)
        )

        move_messages_to_archive(message_ids=[reply_msg_id])
        # Now the attachment should have been deleted:
        self.assertEqual(Attachment.objects.count(), 0)
