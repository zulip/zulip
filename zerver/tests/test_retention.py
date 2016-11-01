# -*- coding: utf-8 -*-
from __future__ import absolute_import

from datetime import datetime, timedelta

from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.upload import create_attachment
from zerver.models import (Message, Realm, Recipient, UserProfile, ArchivedUserMessage,
                           ArchivedMessage, Attachment, ArchivedAttachment, UserMessage,
                           get_user_profile_by_email)
from zerver.lib.retention import (move_expired_messages_to_archive,
                                  move_expired_user_messages_to_archive, delete_expired_messages,
                                  clean_unused_messages,
                                  delete_expired_user_messages, archive_messages,
                                  move_message_to_archive)

from six.moves import range

from typing import Any, Dict, List


class TestRetentionLib(ZulipTestCase):
    """
        Test receiving expired messages retention tool.
    """

    def setUp(self):
        # type: () -> None
        super(TestRetentionLib, self).setUp()
        self.zulip_realm = self._set_realm_message_retention_value('zulip', 30)
        self.mit_realm = self._set_realm_message_retention_value('zephyr', 100)

    @staticmethod
    def _set_realm_message_retention_value(realm_str, retention_period):
        # type: (str, int) -> Realm
        # Change retention period for certain realm.
        realm = Realm.objects.get(string_id=realm_str)
        realm.message_retention_days = retention_period
        realm.save()
        return realm

    @staticmethod
    def _change_msgs_pub_date(msgs_ids, pub_date):
        # type: (List[int], datetime) -> Any
        # Update message pud_date value.
        msgs = Message.objects.filter(id__in=msgs_ids).order_by('id')
        msgs.update(pub_date=pub_date)
        return msgs

    def _make_mit_msgs(self, msg_qauntity, pub_date):
        # type: (int, datetime) -> Any
        # Send messages from mit.edu realm and change messages pub_date.
        sender = self.mit_user('espuser')
        recipient = self.mit_user('starnine')
        msgs_ids = [self.send_message(sender.email, recipient.email, Recipient.PERSONAL) for i in
                    range(msg_qauntity)]
        mit_msgs = self._change_msgs_pub_date(msgs_ids, pub_date)
        return mit_msgs

    def _send_cross_realm_message(self):
        # type: () -> int
        # Send message from bot to users from different realm.
        bot_email = 'notification-bot@zulip.com'
        get_user_profile_by_email(bot_email)
        mit_user = UserProfile.objects.filter(realm=self.mit_realm).first()
        return self.send_message(bot_email, [mit_user.email],
                                 Recipient.PERSONAL)

    def _check_archive_data_by_realm(self, exp_msgs, realm):
        # type: (Any, Realm) -> None
        self._check_archived_messages_ids_by_realm(
            [msg.id for msg in exp_msgs.order_by('id')],
            realm
        )
        user_messages = UserMessage.objects.filter(message__in=exp_msgs).order_by('id')
        archived_user_messages = ArchivedUserMessage.objects.filter(
            user_profile__realm=realm).order_by('id')
        self.assertEqual(
            [user_msg.id for user_msg in user_messages],
            [arc_user_msg.id for arc_user_msg in archived_user_messages]
        )

    def _check_archived_messages_ids_by_realm(self, exp_message_ids, realm):
        # type: (List[int], Realm) -> None
        arc_messages = ArchivedMessage.objects.filter(
            archivedusermessage__user_profile__realm=realm).distinct('id').order_by('id')
        self.assertEqual(
            exp_message_ids,
            [arc_msg.id for arc_msg in arc_messages]
        )

    def _check_cross_realm_messages_archiving(self, arc_user_msg_qty, period, realm=None):
        # type: (int, int, Realm) -> int
        sended_message_id = self._send_cross_realm_message()
        all_user_messages_qty = UserMessage.objects.count()
        self._change_msgs_pub_date([sended_message_id], timezone_now() - timedelta(days=period))
        realms = Realm.objects.filter(message_retention_days__isnull=False)
        for realm_instance in realms:
            move_expired_messages_to_archive(realm_instance)
            move_expired_user_messages_to_archive(realm_instance)
        user_messages_sended = UserMessage.objects.order_by('id').filter(
            message_id=sended_message_id)
        archived_messages = ArchivedMessage.objects.all()
        archived_user_messages = ArchivedUserMessage.objects.order_by('id')
        self.assertEqual(user_messages_sended.count(), 2)
        # Compare archived messages and user messages
        # with expired sended messages.
        self.assertEqual(archived_messages.count(), 1)
        self.assertEqual(archived_user_messages.count(), arc_user_msg_qty)
        if realm:
            user_messages_sended = user_messages_sended.filter(user_profile__realm=self.zulip_realm)
        self.assertEqual(
            [arc_user_msg.id for arc_user_msg in archived_user_messages],
            [user_msg.id for user_msg in user_messages_sended]
        )
        for realm_instance in realms:
            delete_expired_user_messages(realm_instance)
            delete_expired_messages(realm_instance)
        clean_unused_messages()
        # Check messages and user messages after deleting expired messages
        # from the main tables.
        self.assertEqual(
            UserMessage.objects.filter(message_id=sended_message_id).count(),
            2 - arc_user_msg_qty)
        self.assertEqual(
            UserMessage.objects.count(),
            all_user_messages_qty - arc_user_msg_qty)
        return sended_message_id

    def _make_expired_messages(self):
        # type: () -> Dict[str,List[int]]
        # Create messages with expired date
        exp_mit_msgs = self._make_mit_msgs(3, timezone_now() - timedelta(days=101))
        exp_mit_msgs_ids = [msg.id for msg in exp_mit_msgs.order_by('id')]
        self._make_mit_msgs(4, timezone_now() - timedelta(days=50))
        exp_zulip_msgs_ids = list(Message.objects.order_by('id').filter(
            sender__realm=self.zulip_realm).values_list('id', flat=True)[3:10])
        # Add expired zulip mesages ids.
        self._change_msgs_pub_date(exp_zulip_msgs_ids,
                                   timezone_now() - timedelta(days=31))
        return {
            "mit_msgs_ids": exp_mit_msgs_ids,
            "zulip_msgs_ids": exp_zulip_msgs_ids
        }

    def test_no_expired_messages(self):
        # type: () -> None
        for realm_instance in Realm.objects.filter(message_retention_days__isnull=False):
            move_expired_messages_to_archive(realm_instance)
            move_expired_user_messages_to_archive(realm_instance)
        self.assertEqual(ArchivedUserMessage.objects.count(), 0)
        self.assertEqual(ArchivedMessage.objects.count(), 0)

    def test_expired_msgs_in_each_realm(self):
        # type: () -> None
        # Check result realm messages order and result content
        # when all realm has expired messages.
        exp_messages_ids = []
        exp_mit_msgs = self._make_mit_msgs(3, timezone_now() - timedelta(days=101))
        exp_messages_ids.extend([msg.id for msg in exp_mit_msgs.order_by('id')])
        self._make_mit_msgs(4, timezone_now() - timedelta(days=50))
        zulip_msgs_ids = list(Message.objects.order_by('id').filter(
            sender__realm=self.zulip_realm).values_list('id', flat=True)[3:10])
        exp_messages_ids.extend(zulip_msgs_ids)
        exp_zulip_msgs = self._change_msgs_pub_date(zulip_msgs_ids,
                                                    timezone_now() - timedelta(days=31))
        for realm_instance in Realm.objects.filter(message_retention_days__isnull=False):
            move_expired_messages_to_archive(realm_instance)
            move_expired_user_messages_to_archive(realm_instance)
        self.assertEqual(ArchivedMessage.objects.count(), len(exp_messages_ids))
        self.assertEqual(
            ArchivedUserMessage.objects.count(),
            UserMessage.objects.filter(message_id__in=exp_messages_ids).count()
        )
        # Compare expected messages ids with archived messages by realm.
        self._check_archive_data_by_realm(exp_mit_msgs, self.mit_realm)
        self._check_archive_data_by_realm(exp_zulip_msgs, self.zulip_realm)

    def test_expired_messages_in_one_realm(self):
        # type: () -> None
        # Check realm with expired messages and messages
        # with one day to expiration data.
        exp_mit_msgs = self._make_mit_msgs(5, timezone_now() - timedelta(days=101))
        for realm_instance in Realm.objects.filter(message_retention_days__isnull=False):
            move_expired_messages_to_archive(realm_instance)
            move_expired_user_messages_to_archive(realm_instance)
        archived_user_messages = ArchivedUserMessage.objects.all()
        self.assertEqual(ArchivedMessage.objects.count(), 5)
        self.assertEqual(archived_user_messages.count(), 10)
        # Compare expected messages ids with archived messages in mit realm
        self._check_archive_data_by_realm(exp_mit_msgs, self.mit_realm)
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

    def test_cross_realm_messages_archiving_one_realm_expired(self):
        # type: () -> None
        # Check archiving messages which is sent to different realms
        # and expired just on on one of them.
        arc_msg_id = self._check_cross_realm_messages_archiving(1, 31, realm=self.zulip_realm)
        self.assertTrue(Message.objects.filter(id=arc_msg_id).exists())

    def test_cross_realm_messages_archiving_two_realm_expired(self):
        # type: () -> None
        # Check archiving cross realm message wich is expired on both realms.
        arc_msg_id = self._check_cross_realm_messages_archiving(2, 101)
        self.assertFalse(Message.objects.filter(id=arc_msg_id).exists())

    def test_archive_message_tool(self):
        # type: () -> None
        # Check archiving tool.
        exp_msgs_ids_dict = self._make_expired_messages()  # List of expired messages ids.
        sended_cross_realm_message_id = self._send_cross_realm_message()
        exp_msgs_ids_dict['mit_msgs_ids'].append(sended_cross_realm_message_id)
        # Add cross realm message id.
        self._change_msgs_pub_date(
            [sended_cross_realm_message_id],
            timezone_now() - timedelta(days=101)
        )
        exp_msgs_ids = exp_msgs_ids_dict['mit_msgs_ids'] + exp_msgs_ids_dict['zulip_msgs_ids']
        # Get expired user messages by message ids
        exp_user_msgs_ids = list(UserMessage.objects.filter(
            message_id__in=exp_msgs_ids).order_by('id').values_list('id', flat=True))
        msgs_qty = Message.objects.count()
        archive_messages()
        # Compare archived messages and user messages with expired messages
        self.assertEqual(ArchivedMessage.objects.count(), len(exp_msgs_ids))
        self.assertEqual(ArchivedUserMessage.objects.count(), len(exp_user_msgs_ids))
        # Check left messages after removing expired messages from main tables without cross-realm
        # messages.
        self.assertEqual(Message.objects.count(), msgs_qty - ArchivedMessage.objects.count())
        # Archiving cross-realm messages.
        self.assertEqual(
            Message.objects.filter(id__in=exp_msgs_ids_dict['zulip_msgs_ids']).count(), 0)
        self.assertEqual(
            Message.objects.filter(id__in=exp_msgs_ids_dict['mit_msgs_ids']).count(), 0)
        self.assertEqual(
            Message.objects.filter(id__in=exp_msgs_ids_dict['zulip_msgs_ids']).count(), 0)
        exp_msgs_ids_dict['zulip_msgs_ids'].append(sended_cross_realm_message_id)
        # Check archived messages by realm
        self._check_archived_messages_ids_by_realm(
            exp_msgs_ids_dict['zulip_msgs_ids'], self.zulip_realm)
        self._check_archived_messages_ids_by_realm(
            exp_msgs_ids_dict['mit_msgs_ids'], self.mit_realm)


class TestMoveMessageToArchive(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        super(TestMoveMessageToArchive, self).setUp()
        self.sender = 'hamlet@zulip.com'
        self.recipient = 'cordelia@zulip.com'

    def _create_attachments(self):
        # type: () -> None
        sample_size = 10
        dummy_files = [
            ('zulip.txt', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt', sample_size),
            ('temp_file.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py', sample_size),
            ('abc.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py', sample_size)
        ]
        user_profile = self.example_user('hamlet')
        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, size)

    def _check_messages_before_archiving(self, msg_id):
        # type: (int) -> List
        user_messages_ids_before = list(UserMessage.objects.filter(
            message_id=msg_id).order_by('id').values_list('id', flat=True))
        self.assertEqual(ArchivedUserMessage.objects.count(), 0)
        self.assertEqual(ArchivedMessage.objects.count(), 0)
        return user_messages_ids_before

    def _check_messages_after_archiving(self, msg_id, user_msgs_ids_before):
        # type: (int, List[int]) -> None
        self.assertEqual(ArchivedMessage.objects.filter(id=msg_id).count(), 1)
        self.assertEqual(Message.objects.filter(id=msg_id).count(), 0)
        self.assertEqual(UserMessage.objects.filter(message_id=msg_id).count(), 0)
        arc_user_messages_ids_after = list(ArchivedUserMessage.objects.filter(
            message_id=msg_id).order_by('id').values_list('id', flat=True))
        self.assertEqual(arc_user_messages_ids_after, user_msgs_ids_before)

    def test_personal_message_archiving(self):
        # type: ()-> None
        msg_id = self.send_message(self.sender, [self.recipient], Recipient.PERSONAL)
        user_messages_ids_before = self._check_messages_before_archiving(msg_id)
        move_message_to_archive(message_id=msg_id)
        self._check_messages_after_archiving(msg_id, user_messages_ids_before)

    def test_stream_message_archiving(self):
        # type: ()-> None
        msg_id = self.send_message(self.sender, "Verona", Recipient.STREAM)
        user_messages_ids_before = self._check_messages_before_archiving(msg_id)
        move_message_to_archive(message_id=msg_id)
        self._check_messages_after_archiving(msg_id, user_messages_ids_before)

    def test_archiving_message_second_time(self):
        # type: ()-> None
        msg_id = self.send_message(self.sender, "Verona", Recipient.STREAM)
        user_messages_ids_before = self._check_messages_before_archiving(msg_id)
        move_message_to_archive(message_id=msg_id)
        self._check_messages_after_archiving(msg_id, user_messages_ids_before)
        with self.assertRaises(Message.DoesNotExist):
            move_message_to_archive(message_id=msg_id)

    def test_archiving_message_with_attachment(self):
        # type: () -> None
        self._create_attachments()
        body = """Some files here ...[zulip.txt](
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py ....
            Some more.... http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py
        """
        msg_id = self.send_message(self.sender, [self.recipient], Recipient.PERSONAL, body)
        user_messages_ids_before = self._check_messages_before_archiving(msg_id)
        attachments_ids_before = list(Attachment.objects.filter(
            messages__id=msg_id).order_by("id").values_list("id", flat=True))
        self.assertEqual(ArchivedAttachment.objects.count(), 0)
        move_message_to_archive(message_id=msg_id)
        self._check_messages_after_archiving(msg_id, user_messages_ids_before)
        self.assertEqual(Attachment.objects.count(), 0)
        arc_attachments_ids_after = list(ArchivedAttachment.objects.filter(
            messages__id=msg_id).order_by("id").values_list("id", flat=True))
        self.assertEqual(attachments_ids_before, arc_attachments_ids_after)

    def test_archiving_message_with_shared_attachment(self):
        # type: () -> None
        # Check do not removing attachments which is used in other messages.
        self._create_attachments()
        body = """Some files here ...[zulip.txt](
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)
            http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py ....
            Some more.... http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py
        """
        msg_id = self.send_message(self.sender, [self.recipient], Recipient.PERSONAL, body)
        msg_id_shared_attachments = self.send_message(self.recipient, [self.sender],
                                                      Recipient.PERSONAL, body)
        user_messages_ids_before = self._check_messages_before_archiving(msg_id)
        attachments_ids_before = list(Attachment.objects.filter(
            messages__id=msg_id).order_by("id").values_list("id", flat=True))
        self.assertEqual(ArchivedAttachment.objects.count(), 0)
        move_message_to_archive(message_id=msg_id)
        self._check_messages_after_archiving(msg_id, user_messages_ids_before)
        self.assertEqual(Attachment.objects.count(), 3)
        arc_attachments_ids_after = list(ArchivedAttachment.objects.filter(
            messages__id=msg_id).order_by("id").values_list("id", flat=True))
        self.assertEqual(attachments_ids_before, arc_attachments_ids_after)
        move_message_to_archive(message_id=msg_id_shared_attachments)
        self.assertEqual(Attachment.objects.count(), 0)
