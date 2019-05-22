# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils.timezone import now as timezone_now

from zerver.lib.actions import internal_send_private_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.upload import create_attachment
from zerver.models import (Message, Realm, UserProfile, ArchivedUserMessage,
                           ArchivedMessage, Attachment, ArchivedAttachment, UserMessage,
                           get_user_profile_by_email, get_system_bot)
from zerver.lib.retention import (
    archive_messages,
    clean_unused_messages,
    delete_expired_messages,
    delete_expired_user_messages,
    move_expired_messages_to_archive,
    move_expired_user_messages_to_archive,
    move_messages_to_archive
)

ZULIP_REALM_DAYS = 30
MIT_REALM_DAYS = 100

class TestRetentionLib(ZulipTestCase):
    """
        Test receiving expired messages retention tool.
    """

    def setUp(self) -> None:
        super().setUp()
        self.zulip_realm = self._set_realm_message_retention_value('zulip', ZULIP_REALM_DAYS)
        self.mit_realm = self._set_realm_message_retention_value('zephyr', MIT_REALM_DAYS)
        Message.objects.all().update(pub_date=timezone_now())

    @staticmethod
    def _set_realm_message_retention_value(realm_str: str, retention_period: int) -> Realm:
        realm = Realm.objects.get(string_id=realm_str)
        realm.message_retention_days = retention_period
        realm.save()
        return realm

    @staticmethod
    def _change_messages_pub_date(msgs_ids: List[int], pub_date: datetime) -> Any:
        messages = Message.objects.filter(id__in=msgs_ids).order_by('id')
        messages.update(pub_date=pub_date)
        return messages

    def _make_mit_messages(self, message_quantity: int, pub_date: datetime) -> Any:
        # send messages from mit.edu realm and change messages pub date
        sender = self.mit_user('espuser')
        recipient = self.mit_user('starnine')
        msgs_ids = [self.send_personal_message(sender.email, recipient.email,
                                               sender_realm='zephyr') for i in
                    range(message_quantity)]
        mit_messages = self._change_messages_pub_date(msgs_ids, pub_date)
        return mit_messages

    def _send_cross_realm_message(self) -> int:
        # Send message from bot to users from different realm.
        bot_email = 'notification-bot@zulip.com'
        get_user_profile_by_email(bot_email)
        mit_user = UserProfile.objects.filter(realm=self.mit_realm).first()
        result = internal_send_private_message(
            realm=mit_user.realm,
            sender=get_system_bot(bot_email),
            recipient_user=mit_user,
            content='test message',
        )
        assert result is not None
        return result

    def _check_archive_data_by_realm(self, expected_messages: Any, realm: Realm) -> None:
        self._check_archived_messages_ids_by_realm(
            [msg.id for msg in expected_messages.order_by('id')],
            realm
        )
        user_messages = UserMessage.objects.filter(message__in=expected_messages).order_by('id')
        archived_user_messages = ArchivedUserMessage.objects.filter(
            user_profile__realm=realm).order_by('id')
        self.assertEqual(
            [user_msg.id for user_msg in user_messages],
            [arc_user_msg.id for arc_user_msg in archived_user_messages]
        )

    def _check_archived_messages_ids_by_realm(self, expected_message_ids: List[int],
                                              realm: Realm) -> None:
        arc_messages = ArchivedMessage.objects.filter(
            archivedusermessage__user_profile__realm=realm).distinct('id').order_by('id')
        self.assertEqual(
            expected_message_ids,
            [arc_msg.id for arc_msg in arc_messages]
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

    def _check_cross_realm_messages_archiving(self, arc_user_msg_qty: int, period: int,
                                              realm: Optional[Realm]=None) -> int:
        sent_message_id = self._send_cross_realm_message()
        all_user_messages_qty = UserMessage.objects.count()
        self._change_messages_pub_date([sent_message_id], timezone_now() - timedelta(days=period))
        realms = Realm.objects.filter(message_retention_days__isnull=False)
        for realm_instance in realms:
            move_expired_messages_to_archive(realm_instance)
            move_expired_user_messages_to_archive(realm_instance)
        user_messages_sent = UserMessage.objects.order_by('id').filter(
            message_id=sent_message_id)
        archived_messages = ArchivedMessage.objects.all()
        archived_user_messages = ArchivedUserMessage.objects.order_by('id')
        self.assertEqual(user_messages_sent.count(), 2)

        # Compare archived messages and user messages
        # with expired sent messages.
        self.assertEqual(archived_messages.count(), 1)
        self.assertEqual(archived_user_messages.count(), arc_user_msg_qty)
        if realm:
            user_messages_sent = user_messages_sent.filter(user_profile__realm=self.zulip_realm)
        self.assertEqual(
            [arc_user_msg.id for arc_user_msg in archived_user_messages],
            [user_msg.id for user_msg in user_messages_sent]
        )
        for realm_instance in realms:
            delete_expired_user_messages(realm_instance)
            delete_expired_messages(realm_instance)
        clean_unused_messages()

        # Check messages and user messages after deleting expired messages
        # from the main tables.
        self.assertEqual(
            UserMessage.objects.filter(message_id=sent_message_id).count(),
            2 - arc_user_msg_qty)
        self.assertEqual(
            UserMessage.objects.count(),
            all_user_messages_qty - arc_user_msg_qty)
        return sent_message_id

    def _make_expired_messages(self) -> Dict[str, List[int]]:
        # Create messages in Zephyr realm with already-expired date
        expected_mit_msgs = self._make_mit_messages(3, timezone_now() - timedelta(days=MIT_REALM_DAYS + 1))
        expected_mit_msgs_ids = [msg.id for msg in expected_mit_msgs.order_by('id')]
        self._make_mit_messages(4, timezone_now() - timedelta(days=MIT_REALM_DAYS - 1))

        # Move existing messages in Zulip realm to be expired
        expected_zulip_msgs_ids = list(Message.objects.order_by('id').filter(
            sender__realm=self.zulip_realm).values_list('id', flat=True)[3:10])
        self._change_messages_pub_date(expected_zulip_msgs_ids,
                                       timezone_now() - timedelta(days=ZULIP_REALM_DAYS + 1))
        return {
            "mit_msgs_ids": expected_mit_msgs_ids,
            "zulip_msgs_ids": expected_zulip_msgs_ids
        }

    def test_no_expired_messages(self) -> None:
        for realm_instance in Realm.objects.filter(message_retention_days__isnull=False):
            move_expired_messages_to_archive(realm_instance)
            move_expired_user_messages_to_archive(realm_instance)
        self.assertEqual(ArchivedUserMessage.objects.count(), 0)
        self.assertEqual(ArchivedMessage.objects.count(), 0)

    def test_expired_messages_in_each_realm(self) -> None:
        """General test for archiving expired messages properly with
        multiple realms involved"""
        expected_message_ids = []
        expected_mit_msgs = self._make_mit_messages(3, timezone_now() - timedelta(days=MIT_REALM_DAYS + 1))
        expected_message_ids.extend([msg.id for msg in expected_mit_msgs.order_by('id')])
        self._make_mit_messages(4, timezone_now() - timedelta(days=MIT_REALM_DAYS - 1))
        zulip_msgs_ids = list(Message.objects.order_by('id').filter(
            sender__realm=self.zulip_realm).values_list('id', flat=True)[3:10])
        expected_message_ids.extend(zulip_msgs_ids)
        expected_zulip_msgs = self._change_messages_pub_date(
            zulip_msgs_ids,
            timezone_now() - timedelta(days=ZULIP_REALM_DAYS + 1))

        for realm_instance in Realm.objects.filter(message_retention_days__isnull=False):
            move_expired_messages_to_archive(realm_instance)
            move_expired_user_messages_to_archive(realm_instance)
        self.assertEqual(ArchivedMessage.objects.count(), len(expected_message_ids))
        self.assertEqual(
            ArchivedUserMessage.objects.count(),
            UserMessage.objects.filter(message_id__in=expected_message_ids).count()
        )

        # Compare expected messages ids with archived messages for both realms
        self._check_archive_data_by_realm(expected_mit_msgs, self.mit_realm)
        self._check_archive_data_by_realm(expected_zulip_msgs, self.zulip_realm)

    def test_expired_messages_in_one_realm(self) -> None:
        """Test with a retention policy set for only the MIT realm"""
        expected_mit_msgs = self._make_mit_messages(
            5, timezone_now() - timedelta(days=MIT_REALM_DAYS + 1))

        for realm_instance in Realm.objects.filter(message_retention_days__isnull=False):
            move_expired_messages_to_archive(realm_instance)
            move_expired_user_messages_to_archive(realm_instance)

        self.assertEqual(ArchivedMessage.objects.count(), 5)
        self.assertEqual(ArchivedUserMessage.objects.count(), 10)

        # Compare expected messages ids with archived messages in mit realm
        self._check_archive_data_by_realm(expected_mit_msgs, self.mit_realm)
        # Check no archive messages for zulip realm.
        self.assertEqual(
            ArchivedMessage.objects.filter(
                archivedusermessage__user_profile__realm=self.zulip_realm).count(),
            0
        )
        self.assertEqual(
            ArchivedUserMessage.objects.filter(user_profile__realm=self.zulip_realm).count(),
            0
        )

    def test_cross_realm_messages_archiving_one_realm_expired(self) -> None:
        """Test that a cross-realm message that is expired in only
        one of the realms only has the UserMessage for that realm archived"""
        arc_msg_id = self._check_cross_realm_messages_archiving(
            1, ZULIP_REALM_DAYS + 1, realm=self.zulip_realm)
        self.assertTrue(Message.objects.filter(id=arc_msg_id).exists())

    def test_cross_realm_messages_archiving_two_realm_expired(self) -> None:
        """Check that archiving a message that's expired in both
        realms is archived both in Message and UserMessage."""
        arc_msg_id = self._check_cross_realm_messages_archiving(2, MIT_REALM_DAYS + 1)
        self.assertFalse(Message.objects.filter(id=arc_msg_id).exists())

    def test_archive_message_tool(self) -> None:
        """End-to-end test of the archiving tool, directly calling
        archive_messages."""
        expected_message_ids_dict = self._make_expired_messages()

        # We also include a cross-realm message in this test.
        sent_cross_realm_message_id = self._send_cross_realm_message()
        expected_message_ids_dict['mit_msgs_ids'].append(sent_cross_realm_message_id)
        self._change_messages_pub_date(
            [sent_cross_realm_message_id],
            timezone_now() - timedelta(days=MIT_REALM_DAYS + 1)
        )
        expected_message_ids = expected_message_ids_dict['mit_msgs_ids'] + expected_message_ids_dict['zulip_msgs_ids']

        # Get expired user messages by message ids
        expected_user_msgs_ids = list(UserMessage.objects.filter(
            message_id__in=expected_message_ids).order_by('id').values_list('id', flat=True))

        msgs_qty = Message.objects.count()
        archive_messages()

        # Compare archived messages and user messages with expired messages
        self.assertEqual(ArchivedMessage.objects.count(), len(expected_message_ids))
        self.assertEqual(ArchivedUserMessage.objects.count(), len(expected_user_msgs_ids))

        # Check non-archived messages messages after removing expired
        # messages from main tables without cross-realm messages.
        self.assertEqual(Message.objects.count(), msgs_qty - ArchivedMessage.objects.count())
        self.assertEqual(
            Message.objects.filter(id__in=expected_message_ids_dict['zulip_msgs_ids']).count(), 0)
        self.assertEqual(
            Message.objects.filter(id__in=expected_message_ids_dict['mit_msgs_ids']).count(), 0)
        self.assertEqual(
            Message.objects.filter(id__in=expected_message_ids_dict['zulip_msgs_ids']).count(), 0)

        # Check archived messages by realm using our standard checker
        # function; we add the cross-realm message ID to the
        # zulip_realm list for this test because its sender lives in
        # that realm in the development environment.
        expected_message_ids_dict['zulip_msgs_ids'].append(sent_cross_realm_message_id)
        self._check_archived_messages_ids_by_realm(
            expected_message_ids_dict['zulip_msgs_ids'], self.zulip_realm)
        self._check_archived_messages_ids_by_realm(
            expected_message_ids_dict['mit_msgs_ids'], self.mit_realm)

    def test_archiving_attachments(self) -> None:
        """End-to-end test for the logic for archiving attachments.  This test
        is hard to read without first reading _send_messages_with_attachments"""
        msgs_ids = self._send_messages_with_attachments()

        # First, confirm deleting the oldest message
        # (`expired_message_id`) creates ArchivedAttachment objects
        # and associates that message ID with them, but does not
        # delete the Attachment object.
        archive_messages()
        archived_attachment = ArchivedAttachment.objects.all()
        attachment = Attachment.objects.all()
        self.assertEqual(archived_attachment.count(), 3)
        self.assertEqual(
            list(archived_attachment.distinct('messages__id').values_list('messages__id',
                                                                          flat=True)),
            [msgs_ids['expired_message_id']])
        self.assertEqual(attachment.count(), 3)

        # Now make `actual_message_id` expired too.  We still don't
        # delete the Attachment objects.
        self._change_messages_pub_date([msgs_ids['actual_message_id']],
                                       timezone_now() - timedelta(days=MIT_REALM_DAYS + 1))
        archive_messages()
        self.assertEqual(attachment.count(), 3)

        # Finally, make the last message mentioning those attachments
        # expired.  We should now delete the Attachment objects and
        # each ArchivedAttachment object should list all 3 messages.
        self._change_messages_pub_date([msgs_ids['other_user_message_id']],
                                       timezone_now() - timedelta(days=MIT_REALM_DAYS + 1))

        archive_messages()
        self.assertEqual(attachment.count(), 0)
        self.assertEqual(archived_attachment.count(), 3)
        self.assertEqual(
            list(archived_attachment.distinct('messages__id').order_by('messages__id').values_list(
                'messages__id', flat=True)),
            sorted(msgs_ids.values()))


class TestMoveMessageToArchive(ZulipTestCase):

    def setUp(self) -> None:
        super().setUp()
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

    def _check_messages_before_archiving(self, msg_ids: List[int]) -> Tuple[List[int], List[int]]:
        user_msgs_ids_before  = list(UserMessage.objects.filter(
            message_id__in=msg_ids).order_by('id').values_list('id', flat=True))
        all_msgs_ids_before = list(Message.objects.filter().order_by('id').values_list('id', flat=True))
        self.assertEqual(ArchivedUserMessage.objects.count(), 0)
        self.assertEqual(ArchivedMessage.objects.count(), 0)
        return (user_msgs_ids_before,  all_msgs_ids_before)

    def _check_messages_after_archiving(self, msg_ids: List[int], user_msgs_ids_before: List[int],
                                        all_msgs_ids_before: List[int]) -> None:
        self.assertEqual(ArchivedMessage.objects.all().count(), len(msg_ids))
        self.assertEqual(Message.objects.filter().count(), len(all_msgs_ids_before) - len(msg_ids))
        self.assertEqual(UserMessage.objects.filter(message_id__in=msg_ids).count(), 0)
        arc_user_messages_ids_after = list(ArchivedUserMessage.objects.filter().order_by('id').values_list('id', flat=True))
        self.assertEqual(arc_user_messages_ids_after, user_msgs_ids_before)

    def test_personal_messages_archiving(self) -> None:
        msg_ids = []
        for i in range(0, 3):
            msg_ids.append(self.send_personal_message(self.sender, self.recipient))
        (user_msgs_ids_before, all_msgs_ids_before) = self._check_messages_before_archiving(msg_ids)
        move_messages_to_archive(message_ids=msg_ids)
        self._check_messages_after_archiving(msg_ids, user_msgs_ids_before, all_msgs_ids_before)

    def test_stream_messages_archiving(self) -> None:
        msg_ids = []
        for i in range(0, 3):
            msg_ids.append(self.send_stream_message(self.sender, "Verona"))
        (user_msgs_ids_before, all_msgs_ids_before) = self._check_messages_before_archiving(msg_ids)
        move_messages_to_archive(message_ids=msg_ids)
        self._check_messages_after_archiving(msg_ids, user_msgs_ids_before, all_msgs_ids_before)

    def test_archiving_messages_second_time(self) -> None:
        msg_ids = []
        for i in range(0, 3):
            msg_ids.append(self.send_stream_message(self.sender, "Verona"))
        (user_msgs_ids_before, all_msgs_ids_before) = self._check_messages_before_archiving(msg_ids)
        move_messages_to_archive(message_ids=msg_ids)
        self._check_messages_after_archiving(msg_ids, user_msgs_ids_before, all_msgs_ids_before)
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
        msg_ids = []
        msg_ids.append(self.send_personal_message(self.sender, self.recipient, body1))
        msg_ids.append(self.send_personal_message(self.sender, self.recipient, body2))

        attachment_id_to_message_ids = {}
        attachments = Attachment.objects.filter(messages__id__in=msg_ids)
        for attachment in attachments:
            attachment_id_to_message_ids[attachment.id] = {message.id for message in attachment.messages.all()}

        (user_msgs_ids_before, all_msgs_ids_before) = self._check_messages_before_archiving(msg_ids)
        attachments_ids_before = list(attachments.order_by("id").values_list("id", flat=True))
        self.assertEqual(ArchivedAttachment.objects.count(), 0)
        move_messages_to_archive(message_ids=msg_ids)
        self._check_messages_after_archiving(msg_ids, user_msgs_ids_before, all_msgs_ids_before)
        self.assertEqual(Attachment.objects.count(), 0)
        archived_attachments = ArchivedAttachment.objects.filter(messages__id__in=msg_ids)
        arc_attachments_ids_after = list(archived_attachments.order_by("id").values_list("id", flat=True))
        self.assertEqual(attachments_ids_before, arc_attachments_ids_after)
        for attachment in archived_attachments:
            self.assertEqual(attachment_id_to_message_ids[attachment.id],
                             {message.id for message in attachment.messages.all()})

    def test_archiving_message_with_shared_attachment(self) -> None:
        # Check do not removing attachments which is used in other messages.
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
        msg_id_shared_attachments = self.send_personal_message(
            from_email=self.recipient,
            to_email=self.sender,
            content=body,
        )

        (user_msgs_ids_before, all_msgs_ids_before) = self._check_messages_before_archiving([msg_id])
        attachments_ids_before = list(Attachment.objects.filter(
            messages__id=msg_id).order_by("id").values_list("id", flat=True))
        self.assertEqual(ArchivedAttachment.objects.count(), 0)
        move_messages_to_archive(message_ids=[msg_id])
        self._check_messages_after_archiving([msg_id], user_msgs_ids_before, all_msgs_ids_before)
        self.assertEqual(Attachment.objects.count(), 5)
        arc_attachments_ids_after = list(ArchivedAttachment.objects.filter(
            messages__id=msg_id).order_by("id").values_list("id", flat=True))
        self.assertEqual(attachments_ids_before, arc_attachments_ids_after)
        move_messages_to_archive(message_ids=[msg_id_shared_attachments])
        self.assertEqual(Attachment.objects.count(), 0)
