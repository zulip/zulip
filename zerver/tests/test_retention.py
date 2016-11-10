# -*- coding: utf-8 -*-
from __future__ import absolute_import
import types
from datetime import datetime, timedelta

from django.utils import timezone
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Realm, Recipient, UserProfile
from zerver.lib.retention import get_expired_messages

from typing import Any

from six.moves import range


class TestRetentionLib(ZulipTestCase):
    """
        Test receiving expired messages retention tool.
    """

    def setUp(self):
        # type: () -> None
        super(TestRetentionLib, self).setUp()
        self.zulip_realm = self._set_realm_message_retention_value('zulip.com', 30)
        self.mit_realm = self._set_realm_message_retention_value('mit.edu', 100)

    @staticmethod
    def _set_realm_message_retention_value(domain, retention_period):
        # type: (str, int) -> Realm
        realm = Realm.objects.filter(domain=domain).first()
        realm.message_retention_days = retention_period
        realm.save()
        return realm

    @staticmethod
    def _change_messages_pub_date(msgs_ids, pub_date):
        # type: (List[int], datetime) -> Any
        messages = Message.objects.filter(id__in=msgs_ids).order_by('id')
        messages.update(pub_date=pub_date)
        return messages

    def _make_mit_messages(self, message_quantity, pub_date):
        # type: (int, datetime) -> Any
        # send messages from mit.edu realm and change messages pub date
        sender = UserProfile.objects.filter(email='espuser@mit.edu').first()
        recipient = UserProfile.objects.filter(email='starnine@mit.edu').first()
        msgs_ids = [self.send_message(sender.email, recipient.email, Recipient.PERSONAL) for i in
                    range(message_quantity)]
        mit_messages = self._change_messages_pub_date(msgs_ids, pub_date)
        return mit_messages

    def test_expired_messages_result_type(self):
        # type: () -> None
        # Check return type of get_expired_message method.
        result = get_expired_messages()
        self.assertIsInstance(result, types.GeneratorType)

    def test_no_expired_messages(self):
        # type: () -> None
        result = list(get_expired_messages())
        self.assertFalse(result)

    def test_expired_messages_in_each_realm(self):
        # type: () -> None
        # Check result realm messages order and result content
        # when all realm has expired messages.
        expired_mit_messages = self._make_mit_messages(3, timezone.now() - timedelta(days=101))
        self._make_mit_messages(4, timezone.now() - timedelta(days=50))
        zulip_messages_ids = Message.objects.order_by('id').filter(
            sender__realm=self.zulip_realm).values_list('id', flat=True)[3:10]
        expired_zulip_messages = self._change_messages_pub_date(zulip_messages_ids,
                                                                timezone.now() - timedelta(days=31))
        # Iterate by result
        expired_messages_result = [messages_list for messages_list in get_expired_messages()]
        self.assertEqual(len(expired_messages_result), 2)
        # Check mit.edu realm expired messages.
        self.assertEqual(len(expired_messages_result[0]['expired_messages']), 3)
        self.assertEqual(expired_messages_result[0]['realm_id'], self.mit_realm.id)
        # Check zulip.com realm expired messages.
        self.assertEqual(len(expired_messages_result[1]['expired_messages']), 7)
        self.assertEqual(expired_messages_result[1]['realm_id'], self.zulip_realm.id)
        # Compare expected messages ids with result messages ids.
        self.assertEqual(
            sorted([message.id for message in expired_mit_messages]),
            [message.id for message in expired_messages_result[0]['expired_messages']]
        )
        self.assertEqual(
            sorted([message.id for message in expired_zulip_messages]),
            [message.id for message in expired_messages_result[1]['expired_messages']]
        )

    def test_expired_messages_in_one_realm(self):
        # type: () -> None
        # Check realm with expired messages and messages
        # with one day to expiration data.
        expired_mit_messages = self._make_mit_messages(5, timezone.now() - timedelta(days=101))
        actual_mit_messages = self._make_mit_messages(3, timezone.now() - timedelta(days=99))
        expired_messages_result = list(get_expired_messages())
        expired_mit_messages_ids = [message.id for message in expired_mit_messages]
        expired_mit_messages_result_ids = [message.id for message in
                                           expired_messages_result[0]['expired_messages']]
        actual_mit_messages_ids = [message.id for message in actual_mit_messages]
        self.assertEqual(len(expired_messages_result), 1)
        self.assertEqual(len(expired_messages_result[0]['expired_messages']), 5)
        self.assertEqual(expired_messages_result[0]['realm_id'], self.mit_realm.id)
        # Compare expected messages ids with result messages ids.
        self.assertEqual(
            sorted(expired_mit_messages_ids),
            expired_mit_messages_result_ids
        )
        # Check actual mit.edu messages are not contained in expired messages list
        self.assertEqual(
            set(actual_mit_messages_ids) - set(expired_mit_messages_ids),
            set(actual_mit_messages_ids)
        )
