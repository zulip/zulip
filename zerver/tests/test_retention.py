from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from unittest import mock

from django.conf import settings
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.create_realm import do_create_realm
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_send import internal_send_private_message
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.scheduled_messages import check_schedule_message, delete_scheduled_message
from zerver.actions.submessage import do_add_submessage
from zerver.lib.retention import (
    archive_messages,
    clean_archived_data,
    get_realms_and_streams_for_archiving,
    move_messages_to_archive,
    restore_all_data_from_archive,
    restore_retention_policy_deletions_for_stream,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import zulip_reaction_info
from zerver.lib.upload.base import create_attachment
from zerver.models import (
    ArchivedAttachment,
    ArchivedMessage,
    ArchivedReaction,
    ArchivedSubMessage,
    ArchivedUserMessage,
    ArchiveTransaction,
    Attachment,
    Message,
    Reaction,
    Realm,
    Stream,
    SubMessage,
    UserMessage,
)
from zerver.models.clients import get_client
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot

# Class with helper functions useful for testing archiving of reactions:
from zerver.tornado.django_api import send_event

ZULIP_REALM_DAYS = 30
MIT_REALM_DAYS = 100


class RetentionTestingBase(ZulipTestCase):
    def _get_usermessage_ids(self, message_ids: List[int]) -> List[int]:
        return list(
            UserMessage.objects.filter(message_id__in=message_ids).values_list("id", flat=True)
        )

    def _verify_archive_data(
        self, expected_message_ids: List[int], expected_usermessage_ids: List[int]
    ) -> None:
        self.assertEqual(
            set(ArchivedMessage.objects.values_list("id", flat=True)),
            set(expected_message_ids),
        )

        self.assertEqual(
            set(ArchivedUserMessage.objects.values_list("id", flat=True)),
            set(expected_usermessage_ids),
        )

        # Archived Messages and UserMessages should have been removed from the normal tables:
        self.assertEqual(Message.objects.filter(id__in=expected_message_ids).count(), 0)
        self.assertEqual(UserMessage.objects.filter(id__in=expected_usermessage_ids).count(), 0)

    def _verify_restored_data(
        self, expected_message_ids: List[int], expected_usermessage_ids: List[int]
    ) -> None:
        # Check that the data was restored:
        self.assertEqual(
            set(Message.objects.filter(id__in=expected_message_ids).values_list("id", flat=True)),
            set(expected_message_ids),
        )

        self.assertEqual(
            set(
                UserMessage.objects.filter(id__in=expected_usermessage_ids).values_list(
                    "id", flat=True
                )
            ),
            set(expected_usermessage_ids),
        )

        # The Messages and UserMessages should still be in the archive - we don't delete them.
        self.assertEqual(
            set(ArchivedMessage.objects.values_list("id", flat=True)),
            set(expected_message_ids),
        )

        self.assertEqual(
            set(ArchivedUserMessage.objects.values_list("id", flat=True)),
            set(expected_usermessage_ids),
        )


class ArchiveMessagesTestingBase(RetentionTestingBase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.zulip_realm = get_realm("zulip")
        self.mit_realm = get_realm("zephyr")
        self._set_realm_message_retention_value(self.zulip_realm, ZULIP_REALM_DAYS)
        self._set_realm_message_retention_value(self.mit_realm, MIT_REALM_DAYS)

        # Set publication date of all existing messages to "now", so that we have full
        # control over what's expired and what isn't.
        Message.objects.all().update(date_sent=timezone_now())

    def _set_realm_message_retention_value(self, realm: Realm, retention_period: int) -> None:
        realm.message_retention_days = retention_period
        realm.save()

    def _set_stream_message_retention_value(
        self, stream: Stream, retention_period: Optional[int]
    ) -> None:
        stream.message_retention_days = retention_period
        stream.save()

    def _change_messages_date_sent(self, msgs_ids: List[int], date_sent: datetime) -> None:
        Message.objects.filter(id__in=msgs_ids).update(date_sent=date_sent)

    def _make_mit_messages(self, message_quantity: int, date_sent: datetime) -> Any:
        # send messages from mit.edu realm and change messages pub date
        sender = self.mit_user("espuser")
        recipient = self.mit_user("starnine")
        msg_ids = [self.send_personal_message(sender, recipient) for i in range(message_quantity)]

        self._change_messages_date_sent(msg_ids, date_sent)
        return msg_ids

    def _send_cross_realm_personal_message(self) -> int:
        # Send message from bot to users from different realm.
        bot_email = "notification-bot@zulip.com"
        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        zulip_user = self.example_user("hamlet")
        msg_id = internal_send_private_message(
            sender=get_system_bot(bot_email, internal_realm.id),
            recipient_user=zulip_user,
            content="test message",
        )
        assert msg_id is not None
        return msg_id

    def _send_personal_message_to_cross_realm_bot(self) -> int:
        # Send message from bot to users from different realm.
        bot_email = "notification-bot@zulip.com"
        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        zulip_user = self.example_user("hamlet")
        msg_id = internal_send_private_message(
            sender=zulip_user,
            recipient_user=get_system_bot(bot_email, internal_realm.id),
            content="test message",
        )
        assert msg_id is not None
        return msg_id

    def _make_expired_zulip_messages(self, message_quantity: int) -> List[int]:
        msg_ids = list(
            Message.objects.order_by("id")
            .filter(realm=self.zulip_realm)
            .values_list("id", flat=True)[3 : 3 + message_quantity]
        )
        self._change_messages_date_sent(
            msg_ids,
            timezone_now() - timedelta(days=ZULIP_REALM_DAYS + 1),
        )

        return msg_ids

    def _send_messages_with_attachments(self) -> Dict[str, int]:
        user_profile = self.example_user("hamlet")
        sample_size = 10
        host = user_profile.realm.host
        realm_id = get_realm("zulip").id
        dummy_files = [
            ("zulip.txt", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt", sample_size),
            ("temp_file.py", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py", sample_size),
            ("abc.py", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py", sample_size),
        ]

        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, user_profile.realm, size)

        self.subscribe(user_profile, "Denmark")
        body = (
            "Some files here ..."
            f" [zulip.txt](http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)"
            f" http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py.... Some"
            f" more.... http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py"
        )

        expired_message_id = self.send_stream_message(user_profile, "Denmark", body)
        actual_message_id = self.send_stream_message(user_profile, "Denmark", body)

        othello = self.example_user("othello")
        other_message_id = self.send_stream_message(othello, "Denmark", body)
        self._change_messages_date_sent(
            [expired_message_id], timezone_now() - timedelta(days=MIT_REALM_DAYS + 1)
        )
        return {
            "expired_message_id": expired_message_id,
            "actual_message_id": actual_message_id,
            "other_user_message_id": other_message_id,
        }


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
            timezone_now() - timedelta(days=MIT_REALM_DAYS + 1),
        )
        # Make some non-expired messages in MIT:
        self._make_mit_messages(4, timezone_now() - timedelta(days=MIT_REALM_DAYS - 1))

        # Change some Zulip messages to be expired:
        expired_zulip_msg_ids = list(
            Message.objects.order_by("id")
            .filter(realm=self.zulip_realm)
            .values_list("id", flat=True)[3:10]
        )
        self._change_messages_date_sent(
            expired_zulip_msg_ids,
            timezone_now() - timedelta(days=ZULIP_REALM_DAYS + 1),
        )

        expired_msg_ids = expired_mit_msg_ids + expired_zulip_msg_ids
        expired_usermsg_ids = self._get_usermessage_ids(expired_msg_ids)

        archive_messages()
        self._verify_archive_data(expired_msg_ids, expired_usermsg_ids)

        restore_all_data_from_archive()
        self._verify_restored_data(expired_msg_ids, expired_usermsg_ids)

    def test_expired_messages_in_one_realm(self) -> None:
        """Test with a retention policy set for only the MIT realm"""
        self._set_realm_message_retention_value(self.zulip_realm, -1)

        # Make some expired messages in MIT:
        expired_mit_msg_ids = self._make_mit_messages(
            5,
            timezone_now() - timedelta(days=MIT_REALM_DAYS + 1),
        )
        # Make some non-expired messages in MIT:
        self._make_mit_messages(4, timezone_now() - timedelta(days=MIT_REALM_DAYS - 1))

        # Change some Zulip messages date_sent, but the realm has no retention policy,
        # so they shouldn't get archived
        zulip_msg_ids = list(
            Message.objects.order_by("id")
            .filter(realm=self.zulip_realm)
            .values_list("id", flat=True)[3:10]
        )
        self._change_messages_date_sent(
            zulip_msg_ids,
            timezone_now() - timedelta(days=ZULIP_REALM_DAYS + 1),
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
        hamlet = self.example_user("hamlet")

        msg_id = self.send_stream_message(hamlet, "Verona", "test")
        usermsg_ids = self._get_usermessage_ids([msg_id])
        self._change_messages_date_sent([msg_id], timezone_now() - timedelta(days=2))

        # Don't archive if stream's retention policy set to -1:
        self._set_realm_message_retention_value(self.zulip_realm, 1)
        self._set_stream_message_retention_value(verona, -1)
        archive_messages()
        self._verify_archive_data([], [])

        # Don't archive if stream and realm have no retention policy:
        self._set_realm_message_retention_value(self.zulip_realm, -1)
        self._set_stream_message_retention_value(verona, None)
        archive_messages()
        self._verify_archive_data([], [])

        # Archive if stream has a retention policy set:
        self._set_realm_message_retention_value(self.zulip_realm, -1)
        self._set_stream_message_retention_value(verona, 1)
        archive_messages()
        self._verify_archive_data([msg_id], usermsg_ids)

    def test_cross_realm_personal_message_archiving(self) -> None:
        """Check that cross-realm personal messages get correctly archived."""

        # We want to test on a set of cross-realm messages of both kinds -
        # from a bot to a user, and from a user to a bot.
        msg_ids = [self._send_cross_realm_personal_message() for i in range(1, 7)]
        msg_ids += [self._send_personal_message_to_cross_realm_bot() for i in range(1, 7)]
        usermsg_ids = self._get_usermessage_ids(msg_ids)
        # Make the message expired in the Zulip realm.:
        self._change_messages_date_sent(
            msg_ids, timezone_now() - timedelta(days=ZULIP_REALM_DAYS + 1)
        )

        archive_messages()
        self._verify_archive_data(msg_ids, usermsg_ids)

    def test_archiving_interrupted(self) -> None:
        """Check that queries get rolled back to a consistent state
        if archiving gets interrupted in the middle of processing a chunk."""
        expired_msg_ids = self._make_expired_zulip_messages(7)
        expired_usermsg_ids = self._get_usermessage_ids(expired_msg_ids)

        # Insert an exception near the end of the archiving process of a chunk:
        with mock.patch(
            "zerver.lib.retention.delete_messages", side_effect=Exception("delete_messages error")
        ):
            with self.assertRaisesRegex(Exception, r"^delete_messages error$"):
                # Specify large chunk_size to ensure things happen in a single batch
                archive_messages(chunk_size=1000)

            # Archiving code has been executed, but because we got an exception, things should have been rolled back:
            self._verify_archive_data([], [])

            self.assertEqual(
                set(Message.objects.filter(id__in=expired_msg_ids).values_list("id", flat=True)),
                set(expired_msg_ids),
            )
            self.assertEqual(
                set(
                    UserMessage.objects.filter(id__in=expired_usermsg_ids).values_list(
                        "id", flat=True
                    )
                ),
                set(expired_usermsg_ids),
            )

    def test_archive_message_tool(self) -> None:
        """End-to-end test of the archiving tool, directly calling
        archive_messages."""
        # Make some expired messages in MIT:
        expired_mit_msg_ids = self._make_mit_messages(
            5,
            timezone_now() - timedelta(days=MIT_REALM_DAYS + 1),
        )
        # Make some non-expired messages in MIT:
        self._make_mit_messages(4, timezone_now() - timedelta(days=MIT_REALM_DAYS - 1))

        # Change some Zulip messages to be expired:
        expired_zulip_msg_ids = self._make_expired_zulip_messages(7)

        expired_crossrealm_msg_id = self._send_cross_realm_personal_message()
        # Make the message expired in the recipient's realm:
        self._change_messages_date_sent(
            [expired_crossrealm_msg_id],
            timezone_now() - timedelta(days=ZULIP_REALM_DAYS + 1),
        )

        expired_msg_ids = [*expired_mit_msg_ids, *expired_zulip_msg_ids, expired_crossrealm_msg_id]
        expired_usermsg_ids = self._get_usermessage_ids(expired_msg_ids)

        archive_messages(chunk_size=2)  # Specify low chunk_size to test batching.
        # Make sure we archived what needed:
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
            list(
                ArchivedAttachment.objects.distinct("messages__id").values_list(
                    "messages__id", flat=True
                )
            ),
            [msgs_ids["expired_message_id"]],
        )
        self.assertEqual(Attachment.objects.count(), 3)

        # Now make `actual_message_id` expired too.  We still don't
        # delete the Attachment objects.
        self._change_messages_date_sent(
            [msgs_ids["actual_message_id"]], timezone_now() - timedelta(days=MIT_REALM_DAYS + 1)
        )
        archive_messages()
        self.assertEqual(Attachment.objects.count(), 3)

        # Finally, make the last message mentioning those attachments
        # expired.  We should now delete the Attachment objects and
        # each ArchivedAttachment object should list all 3 messages.
        self._change_messages_date_sent(
            [msgs_ids["other_user_message_id"]], timezone_now() - timedelta(days=MIT_REALM_DAYS + 1)
        )

        archive_messages()
        self.assertEqual(Attachment.objects.count(), 0)
        self.assertEqual(ArchivedAttachment.objects.count(), 3)
        self.assertEqual(
            list(
                ArchivedAttachment.objects.distinct("messages__id")
                .order_by("messages__id")
                .values_list("messages__id", flat=True)
            ),
            sorted(msgs_ids.values()),
        )

        restore_all_data_from_archive()
        # Attachments should have been restored:
        self.assertEqual(Attachment.objects.count(), 3)
        # Archived data doesn't get deleted by restoring.
        self.assertEqual(ArchivedAttachment.objects.count(), 3)
        self.assertEqual(
            list(
                Attachment.objects.distinct("messages__id")
                .order_by("messages__id")
                .values_list("messages__id", flat=True)
            ),
            sorted(msgs_ids.values()),
        )

    def test_restoring_and_rearchiving(self) -> None:
        expired_msg_ids = self._make_mit_messages(
            7,
            timezone_now() - timedelta(days=MIT_REALM_DAYS + 1),
        )
        expired_usermsg_ids = self._get_usermessage_ids(expired_msg_ids)

        archive_messages(chunk_size=4)
        self._verify_archive_data(expired_msg_ids, expired_usermsg_ids)

        transactions = ArchiveTransaction.objects.all()
        self.assert_length(transactions, 2)  # With chunk_size 4, there should be 2 transactions

        restore_all_data_from_archive()
        transactions[0].refresh_from_db()
        transactions[1].refresh_from_db()
        self.assertTrue(transactions[0].restored)
        self.assertTrue(transactions[1].restored)

        archive_messages(chunk_size=10)
        self._verify_archive_data(expired_msg_ids, expired_usermsg_ids)

        transactions = ArchiveTransaction.objects.order_by("id")
        self.assert_length(transactions, 3)

        archived_messages = ArchivedMessage.objects.filter(id__in=expired_msg_ids)
        # Check that the re-archived messages are correctly assigned to the new transaction:
        for message in archived_messages:
            self.assertEqual(message.archive_transaction_id, transactions[2].id)


class TestArchivingSubMessages(ArchiveMessagesTestingBase):
    def test_archiving_submessages(self) -> None:
        expired_msg_ids = self._make_expired_zulip_messages(2)
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        do_add_submessage(
            realm=self.zulip_realm,
            sender_id=cordelia.id,
            message_id=expired_msg_ids[0],
            msg_type="whatever",
            content='{"name": "alice", "salary": 20}',
        )
        do_add_submessage(
            realm=self.zulip_realm,
            sender_id=hamlet.id,
            message_id=expired_msg_ids[0],
            msg_type="whatever",
            content='{"name": "john", "salary": 30}',
        )

        do_add_submessage(
            realm=self.zulip_realm,
            sender_id=cordelia.id,
            message_id=expired_msg_ids[1],
            msg_type="whatever",
            content='{"name": "jack", "salary": 10}',
        )

        submessage_ids = list(
            SubMessage.objects.filter(message_id__in=expired_msg_ids).values_list("id", flat=True),
        )

        self.assert_length(submessage_ids, 3)
        self.assertEqual(SubMessage.objects.filter(id__in=submessage_ids).count(), 3)
        archive_messages()
        self.assertEqual(SubMessage.objects.filter(id__in=submessage_ids).count(), 0)

        self.assertEqual(
            set(
                ArchivedSubMessage.objects.filter(id__in=submessage_ids).values_list(
                    "id", flat=True
                )
            ),
            set(submessage_ids),
        )

        restore_all_data_from_archive()
        self.assertEqual(
            set(SubMessage.objects.filter(id__in=submessage_ids).values_list("id", flat=True)),
            set(submessage_ids),
        )


class TestArchivingReactions(ArchiveMessagesTestingBase):
    def test_archiving_reactions(self) -> None:
        expired_msg_ids = self._make_expired_zulip_messages(2)

        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        for sender in [hamlet, cordelia]:
            self.api_post(
                sender,
                f"/api/v1/messages/{expired_msg_ids[0]}/reactions",
                zulip_reaction_info(),
            )

        self.api_post(
            hamlet,
            f"/api/v1/messages/{expired_msg_ids[1]}/reactions",
            zulip_reaction_info(),
        )

        reaction_ids = list(
            Reaction.objects.filter(message_id__in=expired_msg_ids).values_list("id", flat=True),
        )

        self.assert_length(reaction_ids, 3)
        self.assertEqual(Reaction.objects.filter(id__in=reaction_ids).count(), 3)
        archive_messages()
        self.assertEqual(Reaction.objects.filter(id__in=reaction_ids).count(), 0)

        self.assertEqual(
            set(ArchivedReaction.objects.filter(id__in=reaction_ids).values_list("id", flat=True)),
            set(reaction_ids),
        )

        restore_all_data_from_archive()
        self.assertEqual(
            set(Reaction.objects.filter(id__in=reaction_ids).values_list("id", flat=True)),
            set(reaction_ids),
        )


class MoveMessageToArchiveBase(RetentionTestingBase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.sender = self.example_user("hamlet")
        self.recipient = self.example_user("cordelia")

    def _create_attachments(self) -> None:
        sample_size = 10
        realm_id = get_realm("zulip").id
        dummy_files = [
            ("zulip.txt", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt", sample_size),
            ("temp_file.py", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py", sample_size),
            ("abc.py", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py", sample_size),
            ("hello.txt", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/hello.txt", sample_size),
            ("new.py", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/new.py", sample_size),
        ]
        user_profile = self.example_user("hamlet")
        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, user_profile.realm, size)

    def _assert_archive_empty(self) -> None:
        self.assertFalse(ArchivedUserMessage.objects.exists())
        self.assertFalse(ArchivedMessage.objects.exists())
        self.assertFalse(ArchivedAttachment.objects.exists())


class MoveMessageToArchiveGeneral(MoveMessageToArchiveBase):
    def test_personal_messages_archiving(self) -> None:
        msg_ids = [self.send_personal_message(self.sender, self.recipient) for i in range(3)]
        usermsg_ids = self._get_usermessage_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._verify_archive_data(msg_ids, usermsg_ids)

        restore_all_data_from_archive()
        self._verify_restored_data(msg_ids, usermsg_ids)

    def test_move_messages_to_archive_with_realm_argument(self) -> None:
        realm = get_realm("zulip")
        msg_ids = [self.send_personal_message(self.sender, self.recipient) for i in range(3)]
        usermsg_ids = self._get_usermessage_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids, realm=realm)
        self._verify_archive_data(msg_ids, usermsg_ids)

        archive_transaction = ArchiveTransaction.objects.last()
        assert archive_transaction is not None
        self.assertEqual(archive_transaction.realm, realm)

    def test_stream_messages_archiving(self) -> None:
        msg_ids = [self.send_stream_message(self.sender, "Verona") for i in range(3)]
        usermsg_ids = self._get_usermessage_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._verify_archive_data(msg_ids, usermsg_ids)

        restore_all_data_from_archive()
        self._verify_restored_data(msg_ids, usermsg_ids)

    def test_archiving_messages_second_time(self) -> None:
        msg_ids = [self.send_stream_message(self.sender, "Verona") for i in range(3)]
        usermsg_ids = self._get_usermessage_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._verify_archive_data(msg_ids, usermsg_ids)

        with self.assertRaises(Message.DoesNotExist):
            move_messages_to_archive(message_ids=msg_ids)

    def test_archiving_messages_multiple_realms(self) -> None:
        """
        Verifies that move_messages_to_archive works correctly
        if called on messages in multiple realms.
        """
        iago = self.example_user("iago")
        othello = self.example_user("othello")

        cordelia = self.lear_user("cordelia")
        king = self.lear_user("king")

        zulip_msg_ids = [self.send_personal_message(iago, othello) for i in range(3)]
        lear_msg_ids = [self.send_personal_message(cordelia, king) for i in range(3)]
        msg_ids = zulip_msg_ids + lear_msg_ids
        usermsg_ids = self._get_usermessage_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._verify_archive_data(msg_ids, usermsg_ids)

        restore_all_data_from_archive()
        self._verify_restored_data(msg_ids, usermsg_ids)

    def test_archiving_messages_with_attachment(self) -> None:
        self._create_attachments()
        realm_id = get_realm("zulip").id
        host = get_realm("zulip").host
        body1 = f"""Some files here ...[zulip.txt](
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py ....
            Some more.... http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py
        """
        body2 = f"""Some files here
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt ...
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/hello.txt ....
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/new.py ....
        """

        msg_ids = [
            self.send_personal_message(self.sender, self.recipient, body1),
            self.send_personal_message(self.sender, self.recipient, body2),
        ]

        attachment_id_to_message_ids: Dict[int, List[int]] = {}
        attachment_ids = list(
            Attachment.objects.filter(messages__id__in=msg_ids).values_list("id", flat=True),
        )
        for attachment_id in attachment_ids:
            attachment_id_to_message_ids[attachment_id] = list(
                Message.objects.filter(realm_id=realm_id, attachment__id=attachment_id).values_list(
                    "id", flat=True
                ),
            )

        usermsg_ids = self._get_usermessage_ids(msg_ids)

        self._assert_archive_empty()
        move_messages_to_archive(message_ids=msg_ids)
        self._verify_archive_data(msg_ids, usermsg_ids)

        self.assertFalse(Attachment.objects.exists())
        archived_attachment_ids = list(
            ArchivedAttachment.objects.filter(messages__id__in=msg_ids).values_list(
                "id", flat=True
            ),
        )

        self.assertEqual(set(attachment_ids), set(archived_attachment_ids))
        for attachment_id in archived_attachment_ids:
            self.assertEqual(
                set(attachment_id_to_message_ids[attachment_id]),
                set(
                    ArchivedMessage.objects.filter(attachment__id=attachment_id).values_list(
                        "id", flat=True
                    )
                ),
            )

        restore_all_data_from_archive()
        self._verify_restored_data(msg_ids, usermsg_ids)

        restored_attachment_ids = list(
            Attachment.objects.filter(messages__id__in=msg_ids).values_list("id", flat=True),
        )

        self.assertEqual(set(attachment_ids), set(restored_attachment_ids))
        for attachment_id in restored_attachment_ids:
            self.assertEqual(
                set(attachment_id_to_message_ids[attachment_id]),
                set(
                    Message.objects.filter(
                        realm_id=realm_id, attachment__id=attachment_id
                    ).values_list("id", flat=True)
                ),
            )

    def test_archiving_message_with_shared_attachment(self) -> None:
        # Make sure that attachments still in use in other messages don't get deleted:
        self._create_attachments()
        realm_id = get_realm("zulip").id
        host = get_realm("zulip").host
        body = f"""Some files here ...[zulip.txt](
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py ....
            Some more.... http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py ...
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/new.py ....
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/hello.txt ....
        """

        msg_id = self.send_personal_message(self.sender, self.recipient, body)
        # Simulate a reply with the same contents.
        reply_msg_id = self.send_personal_message(
            from_user=self.recipient,
            to_user=self.sender,
            content=body,
        )

        usermsg_ids = self._get_usermessage_ids([msg_id])
        attachment_ids = list(
            Attachment.objects.filter(messages__id=msg_id).values_list("id", flat=True),
        )

        self._assert_archive_empty()
        # Archive one of the messages:
        move_messages_to_archive(message_ids=[msg_id])
        self._verify_archive_data([msg_id], usermsg_ids)
        # Attachments shouldn't have been deleted, as the second message links to them:
        self.assertEqual(Attachment.objects.count(), 5)

        self.assertEqual(
            set(
                ArchivedAttachment.objects.filter(messages__id=msg_id).values_list("id", flat=True)
            ),
            set(attachment_ids),
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
            set(attachment_ids),
        )

    def test_archiving_message_with_scheduled_message(self) -> None:
        # Make sure that attachments referenced by scheduledmessages do't get deleted
        self._create_attachments()
        realm_id = get_realm("zulip").id
        host = get_realm("zulip").host
        body = f"""Some files here ...[zulip.txt](
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py ....
            Some more.... http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py ...
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/new.py ....
            http://{host}/user_uploads/{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/hello.txt ....
        """

        msg_id = self.send_personal_message(self.sender, self.recipient, body)

        # Schedule a message with the same contents
        scheduled_msg_id = check_schedule_message(
            sender=self.sender,
            client=get_client("website"),
            recipient_type_name="private",
            message_to=[self.recipient.id],
            topic_name=None,
            message_content=body,
            deliver_at=timezone_now() + timedelta(hours=1),
        )

        usermsg_ids = self._get_usermessage_ids([msg_id])
        attachment_ids = list(
            Attachment.objects.filter(messages__id=msg_id).values_list("id", flat=True),
        )

        self._assert_archive_empty()
        # Archive one of the messages:
        move_messages_to_archive(message_ids=[msg_id])
        self._verify_archive_data([msg_id], usermsg_ids)
        # Attachments shouldn't have been deleted, as the scheduled message links to them:
        self.assertEqual(Attachment.objects.count(), 5)

        self.assertEqual(
            set(
                ArchivedAttachment.objects.filter(messages__id=msg_id).values_list("id", flat=True)
            ),
            set(attachment_ids),
        )

        # Delete the ScheduledMessage
        delete_scheduled_message(self.sender, scheduled_msg_id)

        # The Attachment object exists, with no message or scheduledmessage attached
        self.assertEqual(Attachment.objects.count(), 5)
        self.assertEqual(
            Attachment.objects.filter(messages=None, scheduled_messages=None).count(), 5
        )

        # There is also the ArchivedAttachment for each of them
        self.assertEqual(
            set(
                ArchivedAttachment.objects.filter(messages__id=msg_id).values_list("id", flat=True)
            ),
            set(attachment_ids),
        )


class MoveMessageToArchiveWithSubMessages(MoveMessageToArchiveBase):
    def test_archiving_message_with_submessages(self) -> None:
        msg_id = self.send_stream_message(self.sender, "Verona")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        do_add_submessage(
            realm=get_realm("zulip"),
            sender_id=cordelia.id,
            message_id=msg_id,
            msg_type="whatever",
            content='{"name": "alice", "salary": 20}',
        )
        do_add_submessage(
            realm=get_realm("zulip"),
            sender_id=hamlet.id,
            message_id=msg_id,
            msg_type="whatever",
            content='{"name": "john", "salary": 30}',
        )

        submessage_ids = list(
            SubMessage.objects.filter(message_id=msg_id).values_list("id", flat=True),
        )

        self.assertEqual(SubMessage.objects.filter(id__in=submessage_ids).count(), 2)
        move_messages_to_archive(message_ids=[msg_id])

        self.assertEqual(
            set(ArchivedSubMessage.objects.filter(message_id=msg_id).values_list("id", flat=True)),
            set(submessage_ids),
        )
        self.assertEqual(SubMessage.objects.filter(id__in=submessage_ids).count(), 0)

        restore_all_data_from_archive()
        self.assertEqual(
            set(SubMessage.objects.filter(id__in=submessage_ids).values_list("id", flat=True)),
            set(submessage_ids),
        )


class MoveMessageToArchiveWithReactions(MoveMessageToArchiveBase):
    def test_archiving_message_with_reactions(self) -> None:
        msg_id = self.send_stream_message(self.sender, "Verona")

        for name in ["hamlet", "cordelia"]:
            self.api_post(
                self.example_user(name),
                f"/api/v1/messages/{msg_id}/reactions",
                zulip_reaction_info(),
            )

        reaction_ids = list(
            Reaction.objects.filter(message_id=msg_id).values_list("id", flat=True),
        )

        self.assertEqual(Reaction.objects.filter(id__in=reaction_ids).count(), 2)
        move_messages_to_archive(message_ids=[msg_id])

        self.assertEqual(
            set(ArchivedReaction.objects.filter(message_id=msg_id).values_list("id", flat=True)),
            set(reaction_ids),
        )
        self.assertEqual(Reaction.objects.filter(id__in=reaction_ids).count(), 0)

        restore_all_data_from_archive()
        self.assertEqual(
            set(Reaction.objects.filter(id__in=reaction_ids).values_list("id", flat=True)),
            set(reaction_ids),
        )


class TestCleaningArchive(ArchiveMessagesTestingBase):
    def test_clean_archived_data(self) -> None:
        self._make_expired_zulip_messages(7)
        archive_messages(chunk_size=2)  # Small chunk size to have multiple transactions

        transactions = list(ArchiveTransaction.objects.all())
        for transaction in transactions[0:-1]:
            transaction.timestamp = timezone_now() - timedelta(
                days=settings.ARCHIVED_DATA_VACUUMING_DELAY_DAYS + 1
            )
            transaction.save()

        message_ids_to_clean = list(
            ArchivedMessage.objects.filter(archive_transaction__in=transactions[0:-1]).values_list(
                "id", flat=True
            )
        )

        clean_archived_data()
        remaining_transactions = list(ArchiveTransaction.objects.all())
        self.assert_length(remaining_transactions, 1)
        # All transactions except the last one were deleted:
        self.assertEqual(remaining_transactions[0].id, transactions[-1].id)
        # And corresponding ArchivedMessages should have been deleted:
        self.assertFalse(ArchivedMessage.objects.filter(id__in=message_ids_to_clean).exists())
        self.assertFalse(
            ArchivedUserMessage.objects.filter(message_id__in=message_ids_to_clean).exists()
        )

        for message in ArchivedMessage.objects.all():
            self.assertEqual(message.archive_transaction_id, remaining_transactions[0].id)


class TestGetRealmAndStreamsForArchiving(ZulipTestCase):
    def fix_ordering_of_result(self, result: List[Tuple[Realm, List[Stream]]]) -> None:
        """
        This is a helper for giving the structure returned by get_realms_and_streams_for_archiving
        a consistent ordering.
        """
        # Sort the list of tuples by realm id:
        result.sort(key=lambda x: x[0].id)

        # Now we sort the lists of streams in each tuple:
        for realm, streams_list in result:
            streams_list.sort(key=lambda stream: stream.id)

    def simple_get_realms_and_streams_for_archiving(self) -> List[Tuple[Realm, List[Stream]]]:
        """
        This is an implementation of the function we're testing, but using the obvious,
        unoptimized algorithm. We can use this for additional verification of correctness,
        by comparing the output of the two implementations.
        """

        result = []
        for realm in Realm.objects.all():
            if realm.message_retention_days != -1:
                streams = Stream.objects.filter(realm=realm).exclude(message_retention_days=-1)
                result.append((realm, list(streams)))
            else:
                streams = (
                    Stream.objects.filter(realm=realm)
                    .exclude(message_retention_days__isnull=True)
                    .exclude(message_retention_days=-1)
                )
                if streams.exists():
                    result.append((realm, list(streams)))

        return result

    def test_get_realms_and_streams_for_archiving(self) -> None:
        zulip_realm = get_realm("zulip")
        zulip_realm.message_retention_days = 10
        zulip_realm.save()

        verona = get_stream("Verona", zulip_realm)
        verona.message_retention_days = -1  # Block archiving for this stream
        verona.save()
        denmark = get_stream("Denmark", zulip_realm)
        denmark.message_retention_days = 1
        denmark.save()

        zephyr_realm = get_realm("zephyr")
        zephyr_realm.message_retention_days = -1
        zephyr_realm.save()
        self.make_stream("normal stream", realm=zephyr_realm)

        archiving_blocked_zephyr_stream = self.make_stream("no archiving", realm=zephyr_realm)
        archiving_blocked_zephyr_stream.message_retention_days = -1
        archiving_blocked_zephyr_stream.save()

        archiving_enabled_zephyr_stream = self.make_stream("with archiving", realm=zephyr_realm)
        archiving_enabled_zephyr_stream.message_retention_days = 1
        archiving_enabled_zephyr_stream.save()

        no_archiving_realm = do_create_realm(string_id="no_archiving", name="no_archiving")
        do_set_realm_property(no_archiving_realm, "invite_required", False, acting_user=None)
        do_set_realm_property(no_archiving_realm, "message_retention_days", -1, acting_user=None)

        # Realm for testing the edge case where it has a default retention policy,
        # but all streams disable it.
        realm_all_streams_archiving_disabled = do_create_realm(
            string_id="with_archiving", name="with_archiving"
        )
        do_set_realm_property(
            realm_all_streams_archiving_disabled, "invite_required", False, acting_user=None
        )
        do_set_realm_property(
            realm_all_streams_archiving_disabled, "message_retention_days", 1, acting_user=None
        )
        Stream.objects.filter(realm=realm_all_streams_archiving_disabled).update(
            message_retention_days=-1
        )

        # We construct a list representing how the result of get_realms_and_streams_for_archiving should be.
        # One nuisance is that the ordering of the elements in the result structure is not deterministic,
        # so we use a helper to order both structures in a consistent manner. This wouldn't be necessary
        # if python had a true "unordered list" data structure. Set doesn't do the job, because it requires
        # elements to be hashable.
        expected_result: List[Tuple[Realm, List[Stream]]] = [
            (zulip_realm, list(Stream.objects.filter(realm=zulip_realm).exclude(id=verona.id))),
            (zephyr_realm, [archiving_enabled_zephyr_stream]),
            (realm_all_streams_archiving_disabled, []),
        ]
        self.fix_ordering_of_result(expected_result)

        simple_algorithm_result = self.simple_get_realms_and_streams_for_archiving()
        self.fix_ordering_of_result(simple_algorithm_result)

        result = get_realms_and_streams_for_archiving()
        self.fix_ordering_of_result(result)

        self.assert_length(result, len(expected_result))
        self.assertEqual(result, expected_result)

        self.assert_length(result, len(simple_algorithm_result))
        self.assertEqual(result, simple_algorithm_result)


class TestRestoreStreamMessages(ArchiveMessagesTestingBase):
    def test_restore_retention_policy_deletions_for_stream(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        realm = get_realm("zulip")
        stream_name = "Verona"
        stream = get_stream(stream_name, realm)

        message_ids_to_archive_manually = [
            self.send_stream_message(cordelia, stream_name, str(i)) for i in range(2)
        ]
        usermessage_ids_to_archive_manually = self._get_usermessage_ids(
            message_ids_to_archive_manually
        )
        message_ids_to_archive_by_policy = [
            self.send_stream_message(hamlet, stream_name, str(i)) for i in range(2)
        ]
        usermessage_ids_to_archive_by_policy = self._get_usermessage_ids(
            message_ids_to_archive_by_policy
        )

        expected_archived_message_ids = (
            message_ids_to_archive_manually + message_ids_to_archive_by_policy
        )
        expected_archived_usermessage_ids = (
            usermessage_ids_to_archive_manually + usermessage_ids_to_archive_by_policy
        )

        self._set_stream_message_retention_value(stream, 5)
        self._change_messages_date_sent(
            message_ids_to_archive_by_policy, timezone_now() - timedelta(days=6)
        )

        move_messages_to_archive(message_ids_to_archive_manually)
        archive_messages()

        self._verify_archive_data(expected_archived_message_ids, expected_archived_usermessage_ids)

        restore_retention_policy_deletions_for_stream(stream)

        # Verify that we restore the stream messages that were archived due to retention policy,
        # but not the ones manually deleted.
        self.assert_length(
            Message.objects.filter(id__in=message_ids_to_archive_by_policy),
            len(message_ids_to_archive_by_policy),
        )
        self.assertFalse(Message.objects.filter(id__in=message_ids_to_archive_manually))


class TestDoDeleteMessages(ZulipTestCase):
    def test_do_delete_messages_multiple(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        message_ids = [self.send_stream_message(cordelia, "Verona", str(i)) for i in range(10)]
        messages = Message.objects.filter(id__in=message_ids)

        with self.assert_database_query_count(21):
            do_delete_messages(realm, messages)
        self.assertFalse(Message.objects.filter(id__in=message_ids).exists())

        archived_messages = ArchivedMessage.objects.filter(id__in=message_ids)
        self.assertEqual(archived_messages.count(), len(message_ids))
        self.assert_length({message.archive_transaction_id for message in archived_messages}, 1)

    def test_old_event_format_processed_correctly(self) -> None:
        """
        do_delete_messages used to send events with users in dict format {"id": <int>}.
        We have a block in process_notification to deal with that old format, that should be
        deleted in a later release. This test is meant to ensure correctness of that block.
        """
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        message_id = self.send_personal_message(cordelia, hamlet)
        message = Message.objects.get(id=message_id)

        event = {
            "type": "delete_message",
            "sender": message.sender.email,
            "sender_id": message.sender_id,
            "message_id": message.id,
            "message_type": "private",
            "recipient_id": message.recipient_id,
        }
        move_messages_to_archive([message_id])
        # We only send the event to see no exception is thrown - as it would be if the block
        # in process_notification to handle this old format of "users to notify" wasn't correct.
        send_event(realm, event, [{"id": cordelia.id}, {"id": hamlet.id}])
