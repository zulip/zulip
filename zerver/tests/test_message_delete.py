from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest import mock

import orjson
from django.db import IntegrityError
from django.utils.timezone import now as timezone_now

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.reactions import do_add_reaction
from zerver.actions.realm_settings import do_change_realm_permission_group_setting
from zerver.actions.streams import do_change_stream_group_based_setting, do_deactivate_stream
from zerver.actions.user_groups import check_add_user_group
from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    ArchiveTransaction,
    Message,
    NamedUserGroup,
    Reaction,
    UserMessage,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.views.message_edit import MAX_BULK_DELETE_MESSAGES, MESSAGE_DELETE_UNDO_WINDOW_SECONDS

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class DeleteMessageTest(ZulipTestCase):
    def test_do_delete_messages_with_empty_list(self) -> None:
        realm = get_realm("zulip")
        initial_count = Message.objects.count()
        do_delete_messages(realm, [], acting_user=None)
        final_count = Message.objects.count()
        self.assertEqual(initial_count, final_count)

    def test_archive_transaction_records_acting_user(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        # A manual deletion records the acting user on its archive transaction,
        # so a user-facing undo can later authorize the user who deleted.
        msg_id = self.send_personal_message(cordelia, hamlet, "Hello!")
        do_delete_messages(realm, [Message.objects.get(id=msg_id)], acting_user=iago)
        archive_transaction = ArchiveTransaction.objects.latest("id")
        self.assertEqual(archive_transaction.type, ArchiveTransaction.MANUAL)
        self.assertEqual(archive_transaction.acting_user, iago)

        # With no acting user (e.g. retention policy or management commands),
        # acting_user is left null.
        msg_id = self.send_personal_message(cordelia, hamlet, "Hello again!")
        do_delete_messages(realm, [Message.objects.get(id=msg_id)], acting_user=None)
        archive_transaction = ArchiveTransaction.objects.latest("id")
        self.assertIsNone(archive_transaction.acting_user)

    def test_bulk_delete_messages(self) -> None:
        # Administrators can delete any message by default, so iago can bulk
        # delete other users' messages in a single request.
        self.login("iago")
        hamlet = self.example_user("hamlet")
        msg_ids = [self.send_stream_message(hamlet, "Denmark", f"msg {i}") for i in range(3)]
        kept_msg_id = self.send_stream_message(hamlet, "Denmark", "keep me")

        result = self.client_delete(
            "/json/messages", {"message_ids": orjson.dumps(msg_ids).decode()}
        )
        self.assert_json_success(result)
        self.assertEqual(Message.objects.filter(id__in=msg_ids).count(), 0)
        self.assertTrue(Message.objects.filter(id=kept_msg_id).exists())

    def test_bulk_delete_messages_is_all_or_nothing(self) -> None:
        realm = get_realm("zulip")
        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=realm, is_system_group=True
        )
        administrators_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm_for_sharding=realm, is_system_group=True
        )
        # Members may delete their own messages, but not others'.
        do_change_realm_permission_group_setting(
            realm, "can_delete_own_message_group", members_group, acting_user=None
        )
        do_change_realm_permission_group_setting(
            realm, "can_delete_any_message_group", administrators_group, acting_user=None
        )

        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(cordelia, "Denmark")
        self.login_user(hamlet)
        own_msg_id = self.send_stream_message(hamlet, "Denmark", "mine")
        others_msg_id = self.send_stream_message(cordelia, "Denmark", "not mine")

        result = self.client_delete(
            "/json/messages",
            {"message_ids": orjson.dumps([own_msg_id, others_msg_id]).decode()},
        )
        self.assert_json_error(result, "You don't have permission to delete this message")
        # Neither message was deleted: the request is rejected as a whole.
        self.assertTrue(Message.objects.filter(id=own_msg_id).exists())
        self.assertTrue(Message.objects.filter(id=others_msg_id).exists())

    def test_bulk_delete_messages_invalid_id(self) -> None:
        self.login("iago")
        hamlet = self.example_user("hamlet")
        msg_id = self.send_stream_message(hamlet, "Denmark", "real")
        result = self.client_delete(
            "/json/messages",
            {"message_ids": orjson.dumps([msg_id, msg_id + 1000]).decode()},
        )
        self.assert_json_error(result, "Invalid message(s)")
        # The valid message is untouched, since deletion is all-or-nothing.
        self.assertTrue(Message.objects.filter(id=msg_id).exists())

    def test_bulk_delete_messages_requires_access(self) -> None:
        # A message that exists but the user cannot even access (here, someone
        # else's direct message) is rejected, before the delete-permission check.
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        dm_id = self.send_personal_message(hamlet, iago, "secret")
        self.login("cordelia")
        result = self.client_delete(
            "/json/messages", {"message_ids": orjson.dumps([dm_id]).decode()}
        )
        self.assert_json_error(result, "Invalid message(s)")
        self.assertTrue(Message.objects.filter(id=dm_id).exists())

    def test_bulk_delete_messages_already_deleted(self) -> None:
        # If the messages are deleted out from under us between locking and
        # archiving (a latency race), we surface a clean error, not a 500.
        self.login("iago")
        hamlet = self.example_user("hamlet")
        msg_id = self.send_stream_message(hamlet, "Denmark", "race")
        with mock.patch(
            "zerver.views.message_edit.do_delete_messages",
            side_effect=Message.DoesNotExist(),
        ):
            result = self.client_delete(
                "/json/messages", {"message_ids": orjson.dumps([msg_id]).decode()}
            )
        self.assert_json_error(result, "Message already deleted")

    def test_bulk_delete_messages_empty_and_over_limit(self) -> None:
        self.login("iago")
        result = self.client_delete("/json/messages", {"message_ids": orjson.dumps([]).decode()})
        self.assert_json_error(result, "Nothing to delete.")

        too_many = list(range(1, MAX_BULK_DELETE_MESSAGES + 2))
        result = self.client_delete(
            "/json/messages", {"message_ids": orjson.dumps(too_many).decode()}
        )
        self.assert_json_error(
            result, f"You can delete at most {MAX_BULK_DELETE_MESSAGES} messages at once."
        )

    def test_restore_messages(self) -> None:
        # iago bulk-deletes hamlet's messages, then undoes within the window;
        # the messages and their reactions come back, and the recipients who
        # saw them are told to re-display them.
        self.login("iago")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(cordelia, "Denmark")
        # An older message we never delete, so first_message_id is unaffected.
        self.send_stream_message(hamlet, "Denmark", "anchor")
        msg_ids = [self.send_stream_message(hamlet, "Denmark", f"msg {i}") for i in range(3)]
        do_add_reaction(
            hamlet, Message.objects.get(id=msg_ids[0]), "tada", "1f389", "unicode_emoji"
        )

        self.client_delete("/json/messages", {"message_ids": orjson.dumps(msg_ids).decode()})
        self.assertEqual(Message.objects.filter(id__in=msg_ids).count(), 0)
        self.assertEqual(Reaction.objects.filter(message_id=msg_ids[0]).count(), 0)

        with self.capture_send_event_calls(expected_num_events=3) as events:
            result = self.client_post(
                "/json/messages/restore", {"message_ids": orjson.dumps(msg_ids).decode()}
            )
        self.assert_json_success(result)

        # The messages and their related objects (reactions, UserMessage rows)
        # are restored with their original IDs.
        self.assertEqual(Message.objects.filter(id__in=msg_ids).count(), 3)
        self.assertEqual(Reaction.objects.filter(message_id=msg_ids[0]).count(), 1)

        # One restored_message event per message, delivered to the recipients
        # who had the message.
        self.assert_length(events, 3)
        restored_message_ids = set()
        for event in events:
            self.assertEqual(event["event"]["type"], "restored_message")
            restored_message_ids.add(event["event"]["message_dict"]["id"])
            notified_user_ids = {user["id"] for user in event["users"]}
            self.assertIn(hamlet.id, notified_user_ids)
            self.assertIn(cordelia.id, notified_user_ids)
        self.assertEqual(restored_message_ids, set(msg_ids))

        # The deletion cannot be undone a second time.
        result = self.client_post(
            "/json/messages/restore", {"message_ids": orjson.dumps(msg_ids).decode()}
        )
        self.assert_json_error(result, "Invalid message(s)")

    def test_restore_messages_notifies_acting_user_without_usermessage(self) -> None:
        # On undo, the acting user must be notified to re-display the messages
        # even when they have no UserMessage of their own (mirrors deletion).
        self.login("iago")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "unfollowed")
        # Anchor we never delete, so first_message_id (and the event count) is
        # unaffected by the restore.
        self.send_stream_message(hamlet, "unfollowed", "anchor")
        msg_ids = [self.send_stream_message(hamlet, "unfollowed", f"msg {i}") for i in range(2)]
        self.assertFalse(
            UserMessage.objects.filter(user_profile=iago, message_id__in=msg_ids).exists()
        )

        self.client_delete("/json/messages", {"message_ids": orjson.dumps(msg_ids).decode()})

        with self.capture_send_event_calls(expected_num_events=2) as events:
            result = self.client_post(
                "/json/messages/restore", {"message_ids": orjson.dumps(msg_ids).decode()}
            )
        self.assert_json_success(result)

        for event in events:
            users_by_id = {user["id"]: user for user in event["users"]}
            self.assertIn(iago.id, users_by_id)
            # The acting user is notified as read, since they aren't a recipient.
            self.assertEqual(users_by_id[iago.id]["flags"], ["read"])

    def test_restore_messages_only_by_the_user_who_deleted_them(self) -> None:
        # A different user cannot undo iago's deletion, even an administrator.
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        msg_ids = [self.send_stream_message(hamlet, "Denmark", f"msg {i}") for i in range(2)]
        self.login_user(iago)
        self.client_delete("/json/messages", {"message_ids": orjson.dumps(msg_ids).decode()})

        self.login_user(hamlet)
        result = self.client_post(
            "/json/messages/restore", {"message_ids": orjson.dumps(msg_ids).decode()}
        )
        self.assert_json_error(result, "Invalid message(s)")
        self.assertEqual(Message.objects.filter(id__in=msg_ids).count(), 0)

    def test_restore_messages_after_window_passes(self) -> None:
        self.login("iago")
        hamlet = self.example_user("hamlet")
        msg_ids = [self.send_stream_message(hamlet, "Denmark", f"msg {i}") for i in range(2)]
        self.client_delete("/json/messages", {"message_ids": orjson.dumps(msg_ids).decode()})

        # Backdate the deletion to just past the undo window.
        ArchiveTransaction.objects.filter(archivedmessage__id__in=msg_ids).update(
            timestamp=timezone_now() - timedelta(seconds=MESSAGE_DELETE_UNDO_WINDOW_SECONDS + 1)
        )
        result = self.client_post(
            "/json/messages/restore", {"message_ids": orjson.dumps(msg_ids).decode()}
        )
        self.assert_json_error(result, "The time limit for undoing this deletion has passed.")
        self.assertEqual(Message.objects.filter(id__in=msg_ids).count(), 0)

    def test_restore_messages_is_all_or_nothing(self) -> None:
        self.login("iago")
        hamlet = self.example_user("hamlet")
        deleted_id = self.send_stream_message(hamlet, "Denmark", "deleted")
        live_id = self.send_stream_message(hamlet, "Denmark", "still here")
        self.client_delete("/json/messages", {"message_ids": orjson.dumps([deleted_id]).decode()})

        # The live message is not in the archive, so the whole restore fails.
        result = self.client_post(
            "/json/messages/restore",
            {"message_ids": orjson.dumps([deleted_id, live_id]).decode()},
        )
        self.assert_json_error(result, "Invalid message(s)")
        self.assertFalse(Message.objects.filter(id=deleted_id).exists())

    def test_restore_messages_empty(self) -> None:
        self.login("iago")
        result = self.client_post(
            "/json/messages/restore", {"message_ids": orjson.dumps([]).decode()}
        )
        self.assert_json_error(result, "Nothing to restore.")

    def test_restore_messages_recomputes_first_message_id(self) -> None:
        # Restoring a channel's deleted first message lowers first_message_id
        # back, emitting a stream event alongside the restore.
        self.login("iago")
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "restore-first")
        first_id = self.send_stream_message(hamlet, "restore-first", "first")
        self.send_stream_message(hamlet, "restore-first", "second")
        stream = get_stream("restore-first", hamlet.realm)
        self.assertEqual(stream.first_message_id, first_id)

        self.client_delete("/json/messages", {"message_ids": orjson.dumps([first_id]).decode()})
        stream.refresh_from_db()
        self.assertNotEqual(stream.first_message_id, first_id)

        with self.capture_send_event_calls(expected_num_events=2) as events:
            result = self.client_post(
                "/json/messages/restore", {"message_ids": orjson.dumps([first_id]).decode()}
            )
        self.assert_json_success(result)
        stream.refresh_from_db()
        self.assertEqual(stream.first_message_id, first_id)
        self.assertTrue(
            any(
                event["event"]["type"] == "stream"
                and event["event"]["property"] == "first_message_id"
                for event in events
            )
        )

    def test_restore_messages_strips_inaccessible_guest_sender(self) -> None:
        # When the sender is a guest no longer accessible to all recipients,
        # the restore event strips their identity, like the send path.
        realm = get_realm("zulip")
        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_access_all_users_group", members_group, acting_user=None
        )
        polonius = self.example_user("polonius")  # a guest
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Denmark")
        self.subscribe(polonius, "Denmark")
        self.send_stream_message(hamlet, "Denmark", "anchor")
        msg_id = self.send_stream_message(polonius, "Denmark", "from the guest")
        # The guest leaves the channel, so they are no longer a subscriber.
        self.unsubscribe(polonius, "Denmark")

        self.login("iago")
        self.client_delete("/json/messages", {"message_ids": orjson.dumps([msg_id]).decode()})
        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.client_post(
                "/json/messages/restore", {"message_ids": orjson.dumps([msg_id]).decode()}
            )
        self.assert_json_success(result)
        self.assertIn("user_ids_without_access_to_sender", events[0]["event"])

    def test_do_delete_private_messages_with_acting_user(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        acting_user = self.example_user("iago")
        msg_id = self.send_personal_message(cordelia, hamlet, "Hello!")
        message = Message.objects.get(id=msg_id)

        with self.capture_send_event_calls(expected_num_events=1) as events:
            do_delete_messages(realm, [message], acting_user=acting_user)

        self.assert_length(events, 1)
        event = events[0]["event"]
        self.assertIn("type", event)
        self.assertEqual(event["type"], "delete_message")
        self.assertIn(msg_id, event["message_ids"])
        self.assertCountEqual([hamlet.id, cordelia.id], events[0]["users"])

        msg_id = self.send_group_direct_message(cordelia, [hamlet, acting_user], "Hello!")
        message = Message.objects.get(id=msg_id)

        with self.capture_send_event_calls(expected_num_events=1) as events:
            do_delete_messages(realm, [message], acting_user=acting_user)

        self.assert_length(events, 1)
        event = events[0]["event"]
        self.assertIn("type", event)
        self.assertEqual(event["type"], "delete_message")
        self.assertIn(msg_id, event["message_ids"])
        self.assertCountEqual([acting_user.id, hamlet.id, cordelia.id], events[0]["users"])

    def test_do_delete_stream_messages_without_acting_user(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")

        stream_name = "Denmark-Test"
        self.make_stream(stream_name)
        self.subscribe(cordelia, stream_name)

        msg_id = self.send_stream_message(cordelia, stream_name, "Hello, Denmark!")
        message = Message.objects.get(id=msg_id)

        with self.capture_send_event_calls(expected_num_events=2) as events:
            do_delete_messages(realm, [message], acting_user=None)

        self.assert_length(events, 2)
        self.assertIn("type", events[0]["event"])
        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertIn(msg_id, events[1]["event"]["message_ids"])

    def test_do_delete_stream_messages_with_acting_user(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")

        # For public stream, acting_user will receive the event even if
        # they are not subscribed and do not have UserMessage row.
        stream_name = "public_stream"
        stream = self.make_stream(stream_name)
        self.subscribe(cordelia, stream_name)
        msg_id = self.send_stream_message(cordelia, stream_name, "Hello!")
        message = Message.objects.get(id=msg_id)

        with self.capture_send_event_calls(expected_num_events=2) as events:
            do_delete_messages(realm, [message], acting_user=hamlet)

        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertIn(msg_id, events[1]["event"]["message_ids"])
        self.assertCountEqual([cordelia.id, hamlet.id], events[1]["users"])

        # For a private stream with public history, acting_user will receive
        # the event if they have content access to the stream even when they
        # were not subscribed to the stream when message was sent and do not
        # have a UserMessage row for the message.
        stream_name = "private_stream"
        stream = self.make_stream(stream_name, invite_only=True, history_public_to_subscribers=True)
        self.subscribe(cordelia, stream_name)
        msg_id = self.send_stream_message(cordelia, stream_name, "Hello!")
        message = Message.objects.get(id=msg_id)

        # Acting user does not receive the event since they do not have
        # content access to the stream.
        with self.capture_send_event_calls(expected_num_events=2) as events:
            do_delete_messages(realm, [message], acting_user=iago)

        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertIn(msg_id, events[1]["event"]["message_ids"])
        self.assertCountEqual([cordelia.id], events[1]["users"])

        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm_for_sharding=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            stream, "can_subscribe_group", admins_group, acting_user=iago
        )

        msg_id = self.send_stream_message(cordelia, stream_name, "Hello!")
        message = Message.objects.get(id=msg_id)

        # Acting user receives the event since they have content access
        # to the stream.
        with self.capture_send_event_calls(expected_num_events=2) as events:
            do_delete_messages(realm, [message], acting_user=iago)

        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertIn(msg_id, events[1]["event"]["message_ids"])
        self.assertCountEqual([cordelia.id, iago.id], events[1]["users"])

        # For a private stream with protected history, acting_user will receive
        # the event only if they have UserMessage rows for at least one of the
        # messages being deleted and have content access to the stream.
        stream_name = "protected_history_stream"
        stream = self.make_stream(stream_name, invite_only=True)
        self.subscribe(cordelia, stream_name)

        msg_id = self.send_stream_message(cordelia, stream_name, "Hello!")
        message = Message.objects.get(id=msg_id)

        # Acting user does not receive the event as they do not have UserMessage
        # row for any of the messages being deleted and they do not have content
        # access to the stream.
        with self.capture_send_event_calls(expected_num_events=2) as events:
            do_delete_messages(realm, [message], acting_user=iago)

        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertIn(msg_id, events[1]["event"]["message_ids"])
        self.assertCountEqual([cordelia.id], events[1]["users"])

        first_msg_id = self.send_stream_message(cordelia, stream_name, "Hello!")
        self.subscribe(iago, stream_name)
        second_msg_id = self.send_stream_message(cordelia, stream_name, "Hello again!")
        self.unsubscribe(iago, stream_name)
        messages = Message.objects.filter(id__in=[first_msg_id, second_msg_id])

        # Acting user does not receive the event as they do not have conte access
        # to the stream even if they have UserMessage row for at least one of the
        # messages being deleted.
        with self.capture_send_event_calls(expected_num_events=2) as events:
            do_delete_messages(realm, messages, acting_user=iago)
        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertCountEqual([first_msg_id, second_msg_id], events[1]["event"]["message_ids"])
        self.assertCountEqual([cordelia.id], events[1]["users"])

        do_change_stream_group_based_setting(
            stream, "can_subscribe_group", admins_group, acting_user=iago
        )

        first_msg_id = self.send_stream_message(cordelia, stream_name, "Hello!")
        second_msg_id = self.send_stream_message(cordelia, stream_name, "Hello again!")
        messages = Message.objects.filter(id__in=[first_msg_id, second_msg_id])

        # Acting user does not receive the event as they do not have
        # UserMessage row for any of the messages being deleted even
        # when they have content access to the stream.
        with self.capture_send_event_calls(expected_num_events=2) as events:
            do_delete_messages(realm, messages, acting_user=iago)
        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertCountEqual([first_msg_id, second_msg_id], events[1]["event"]["message_ids"])
        self.assertCountEqual([cordelia.id], events[1]["users"])

        first_msg_id = self.send_stream_message(cordelia, stream_name, "Hello!")
        self.subscribe(iago, stream_name)
        second_msg_id = self.send_stream_message(cordelia, stream_name, "Hello again!")
        self.unsubscribe(iago, stream_name)
        messages = Message.objects.filter(id__in=[first_msg_id, second_msg_id])

        # Acting user receives the event as they are subscribed to the stream
        # and also have UserMessage row for at least one of the messages being
        # deleted and the event includes messages with only UserMessage rows.
        with self.capture_send_event_calls(expected_num_events=3) as events:
            do_delete_messages(realm, messages, acting_user=iago)

        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertCountEqual([first_msg_id, second_msg_id], events[1]["event"]["message_ids"])
        self.assertCountEqual([cordelia.id], events[1]["users"])
        self.assertEqual(events[2]["event"]["type"], "delete_message")
        self.assertCountEqual([second_msg_id], events[2]["event"]["message_ids"])
        self.assertCountEqual([iago.id], events[2]["users"])

        first_msg_id = self.send_stream_message(cordelia, stream_name, "Hello!")
        self.subscribe(iago, stream_name)
        second_msg_id = self.send_stream_message(cordelia, stream_name, "Hello again!")
        messages = Message.objects.filter(id__in=[first_msg_id, second_msg_id])

        with self.capture_send_event_calls(expected_num_events=3) as events:
            do_delete_messages(realm, messages, acting_user=iago)

        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertCountEqual([first_msg_id, second_msg_id], events[1]["event"]["message_ids"])
        self.assertCountEqual([cordelia.id], events[1]["users"])
        self.assertEqual(events[2]["event"]["type"], "delete_message")
        self.assertCountEqual([second_msg_id], events[2]["event"]["message_ids"])
        self.assertCountEqual([iago.id], events[2]["users"])

        # If the acting_user has UserMessage row for all the messages being
        # deleted in a protected history stream, then we send the same event
        # to all the users with access.
        self.subscribe(iago, stream_name)
        first_msg_id = self.send_stream_message(cordelia, stream_name, "Hello!")
        second_msg_id = self.send_stream_message(cordelia, stream_name, "Hello again!")
        self.unsubscribe(iago, stream_name)
        messages = Message.objects.filter(id__in=[first_msg_id, second_msg_id])
        with self.capture_send_event_calls(expected_num_events=2) as events:
            do_delete_messages(realm, messages, acting_user=iago)

        self.assertEqual(events[1]["event"]["type"], "delete_message")
        self.assertCountEqual([first_msg_id, second_msg_id], events[1]["event"]["message_ids"])
        self.assertCountEqual([cordelia.id, iago.id], events[1]["users"])

    def test_do_delete_messages_grouping_logic(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        self.make_stream("stream1")
        self.make_stream("stream2")
        self.subscribe(cordelia, "stream1")
        self.subscribe(hamlet, "stream1")
        self.subscribe(cordelia, "stream2")
        self.subscribe(hamlet, "stream2")

        msg_id_1 = self.send_stream_message(
            cordelia, "stream1", topic_name="topic1", content="test1"
        )
        msg_id_2 = self.send_stream_message(hamlet, "stream1", topic_name="topic1", content="test2")
        msg_id_3 = self.send_stream_message(
            cordelia, "stream1", topic_name="topic2", content="test3"
        )
        msg_id_4 = self.send_stream_message(hamlet, "stream2", topic_name="topic3", content="test4")
        dm_id_1 = self.send_personal_message(cordelia, hamlet, "test5")
        dm_id_2 = self.send_personal_message(hamlet, iago, "test6")

        messages = Message.objects.filter(
            id__in=[msg_id_1, msg_id_2, msg_id_3, msg_id_4, dm_id_1, dm_id_2]
        )

        stream1 = get_stream("stream1", realm)
        stream2 = get_stream("stream2", realm)

        with self.capture_send_event_calls(expected_num_events=8) as events:
            do_delete_messages(realm, messages, acting_user=None)

        actual_events = [event["event"] for event in events]
        self.assert_length(actual_events, 8)

        # Messages are grouped by (recipient_id, topic) via a database
        # GROUP BY with no explicit ORDER BY, so the order of event
        # groups is non-deterministic. DMs use DIRECT_MESSAGE_GROUP
        # recipients, which shifts where DM events appear relative to
        # channel events. We verify events by category rather than by
        # position.

        # Verify DM delete events (order-independent).
        dm_delete_events = [
            e
            for e in actual_events
            if e["type"] == "delete_message" and e["message_type"] == "private"
        ]
        self.assert_length(dm_delete_events, 2)
        dm_message_id_sets = [set(e["message_ids"]) for e in dm_delete_events]
        self.assertIn({dm_id_1}, dm_message_id_sets)
        self.assertIn({dm_id_2}, dm_message_id_sets)

        # Verify channel events maintain their expected relative order.
        # Within a channel, topic groups are processed deterministically
        # (same recipient_id), and each group produces a paired
        # (first_message_id update, delete_message) sequence.
        channel_events = [
            e
            for e in actual_events
            if not (e["type"] == "delete_message" and e["message_type"] == "private")
        ]
        expected_channel_events: list[dict[str, Any]] = [
            {
                "type": "stream",
                "op": "update",
                "property": "first_message_id",
                "value": msg_id_3,
                "stream_id": stream1.id,
                "name": "stream1",
            },
            {
                "type": "delete_message",
                "message_ids": [msg_id_1, msg_id_2],
                "stream_id": stream1.id,
                "topic": "topic1",
                "message_type": "stream",
            },
            {
                "type": "stream",
                "op": "update",
                "property": "first_message_id",
                "value": None,
                "stream_id": stream1.id,
                "name": "stream1",
            },
            {
                "type": "delete_message",
                "message_ids": [msg_id_3],
                "stream_id": stream1.id,
                "topic": "topic2",
                "message_type": "stream",
            },
            {
                "type": "stream",
                "op": "update",
                "property": "first_message_id",
                "value": None,
                "stream_id": stream2.id,
                "name": "stream2",
            },
            {
                "type": "delete_message",
                "message_ids": [msg_id_4],
                "stream_id": stream2.id,
                "topic": "topic3",
                "message_type": "stream",
            },
        ]

        self.assert_length(channel_events, len(expected_channel_events))
        for actual, expected in zip(channel_events, expected_channel_events, strict=True):
            for key, value in expected.items():
                if key == "message_ids":
                    self.assertEqual(set(actual[key]), set(value))
                else:
                    self.assertEqual(actual[key], value)

    def test_delete_message_invalid_request_format(self) -> None:
        self.login("iago")
        hamlet = self.example_user("hamlet")
        msg_id = self.send_stream_message(hamlet, "Denmark")
        result = self.client_delete(f"/json/messages/{msg_id + 1}", {"message_id": msg_id})
        self.assert_json_error(result, "Invalid message(s)")
        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_success(result)

    def test_delete_message_by_user(self) -> None:
        def set_message_deleting_params(
            can_delete_any_message_group: NamedUserGroup,
            can_delete_own_message_group: NamedUserGroup,
            message_content_delete_limit_seconds: int | str,
        ) -> None:
            self.login("iago")
            result = self.client_patch(
                "/json/realm",
                {
                    "can_delete_any_message_group": orjson.dumps(
                        {"new": can_delete_any_message_group.id}
                    ).decode(),
                    "can_delete_own_message_group": orjson.dumps(
                        {"new": can_delete_own_message_group.id}
                    ).decode(),
                    "message_content_delete_limit_seconds": orjson.dumps(
                        message_content_delete_limit_seconds
                    ).decode(),
                },
            )
            self.assert_json_success(result)

        def test_delete_message_by_admin(msg_id: int) -> "TestHttpResponse":
            self.login("iago")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        def test_delete_message_by_moderator(msg_id: int) -> "TestHttpResponse":
            self.login("shiva")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        def test_delete_message_by_sender(msg_id: int) -> "TestHttpResponse":
            self.login("hamlet")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        def test_delete_message_by_other_user(msg_id: int) -> "TestHttpResponse":
            self.login("cordelia")
            result = self.client_delete(f"/json/messages/{msg_id}")
            return result

        realm = get_realm("zulip")

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm_for_sharding=realm, is_system_group=True
        )
        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=realm, is_system_group=True
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=realm, is_system_group=True
        )
        everyone_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm_for_sharding=realm, is_system_group=True
        )

        # Test if message deleting is not allowed(default).
        set_message_deleting_params(
            administrators_system_group, administrators_system_group, "unlimited"
        )
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        msg_id = self.send_stream_message(hamlet, "Denmark")

        result = test_delete_message_by_sender(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_other_user(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_admin(msg_id=msg_id)
        self.assert_json_success(result)

        # Test if message deleting is allowed.
        # Test if time limit is None(no limit).
        set_message_deleting_params(administrators_system_group, everyone_system_group, "unlimited")
        msg_id = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id)
        message.date_sent -= timedelta(seconds=600)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_sender(msg_id=msg_id)
        self.assert_json_success(result)

        # Test if time limit is non-zero.
        set_message_deleting_params(administrators_system_group, everyone_system_group, 240)
        msg_id_1 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_1)
        message.date_sent -= timedelta(seconds=120)
        message.save()

        msg_id_2 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_2)
        message.date_sent -= timedelta(seconds=360)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_sender(msg_id=msg_id_1)
        self.assert_json_success(result)
        result = test_delete_message_by_sender(msg_id=msg_id_2)
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        # No limit for admin.
        result = test_delete_message_by_admin(msg_id=msg_id_2)
        self.assert_json_success(result)

        # Test multiple delete requests with no latency issues
        msg_id = self.send_stream_message(hamlet, "Denmark")
        result = test_delete_message_by_sender(msg_id=msg_id)
        self.assert_json_success(result)
        result = test_delete_message_by_sender(msg_id=msg_id)
        self.assert_json_error(result, "Invalid message(s)")

        # Test if message deletion is allowed when every member can delete any message.
        set_message_deleting_params(members_system_group, administrators_system_group, "unlimited")
        msg_id_1 = self.send_stream_message(hamlet, "Denmark")
        msg_id_2 = self.send_stream_message(hamlet, "Denmark")
        msg_id_3 = self.send_stream_message(hamlet, "Denmark")

        result = test_delete_message_by_other_user(msg_id=msg_id_1)
        self.assert_json_success(result)

        result = test_delete_message_by_sender(msg_id=msg_id_2)
        self.assert_json_success(result)

        result = test_delete_message_by_admin(msg_id=msg_id_3)
        self.assert_json_success(result)

        # Test if there is no time limit to delete messages for users who can delete
        # any message.
        set_message_deleting_params(moderators_system_group, everyone_system_group, 240)
        msg_id_1 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_1)
        message.date_sent -= timedelta(seconds=120)
        message.save()

        msg_id_2 = self.send_stream_message(hamlet, "Denmark")
        message = Message.objects.get(id=msg_id_2)
        message.date_sent -= timedelta(seconds=360)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_sender(msg_id=msg_id_1)
        self.assert_json_success(result)

        result = test_delete_message_by_sender(msg_id=msg_id_2)
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        result = test_delete_message_by_moderator(msg_id=msg_id_2)
        self.assert_json_success(result)

        # Test handling of 500 error caused by multiple delete requests due to latency.
        # see issue #11219.
        with (
            mock.patch("zerver.views.message_edit.do_delete_messages") as m,
            mock.patch("zerver.views.message_edit.validate_can_delete_message", return_value=None),
            mock.patch("zerver.views.message_edit.access_message", return_value=(None, None)),
        ):
            m.side_effect = IntegrityError()
            result = test_delete_message_by_sender(msg_id=msg_id)
            self.assert_json_error(result, "Message already deleted")
            m.side_effect = Message.DoesNotExist()
            result = test_delete_message_by_sender(msg_id=msg_id)
            self.assert_json_error(result, "Message already deleted")

    def test_delete_message_sent_by_bots(self) -> None:
        iago = self.example_user("iago")
        shiva = self.example_user("shiva")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        def set_message_deleting_params(
            can_delete_any_message_group: NamedUserGroup,
            can_delete_own_message_group: NamedUserGroup,
            message_content_delete_limit_seconds: int | str,
        ) -> None:
            result = self.api_patch(
                iago,
                "/api/v1/realm",
                {
                    "can_delete_any_message_group": orjson.dumps(
                        {"new": can_delete_any_message_group.id}
                    ).decode(),
                    "can_delete_own_message_group": orjson.dumps(
                        {"new": can_delete_own_message_group.id}
                    ).decode(),
                    "message_content_delete_limit_seconds": orjson.dumps(
                        message_content_delete_limit_seconds
                    ).decode(),
                },
            )
            self.assert_json_success(result)

        def test_delete_message_by_admin(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(iago, f"/api/v1/messages/{msg_id}")
            return result

        def test_delete_message_by_moderator(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(shiva, f"/api/v1/messages/{msg_id}")
            return result

        def test_delete_message_by_bot_owner(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(hamlet, f"/api/v1/messages/{msg_id}")
            return result

        def test_delete_message_by_other_user(msg_id: int) -> "TestHttpResponse":
            result = self.api_delete(cordelia, f"/api/v1/messages/{msg_id}")
            return result

        realm = get_realm("zulip")

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm_for_sharding=realm, is_system_group=True
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=realm, is_system_group=True
        )
        everyone_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm_for_sharding=realm, is_system_group=True
        )

        set_message_deleting_params(
            moderators_system_group, administrators_system_group, "unlimited"
        )

        hamlet = self.example_user("hamlet")
        test_bot = self.create_test_bot("test-bot", hamlet)
        msg_id_1 = self.send_stream_message(test_bot, "Denmark")
        msg_id_2 = self.send_stream_message(test_bot, "Denmark")

        result = test_delete_message_by_other_user(msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_bot_owner(msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        # Admins and moderators can delete any message.
        result = test_delete_message_by_moderator(msg_id_1)
        self.assert_json_success(result)

        result = test_delete_message_by_admin(msg_id_2)
        self.assert_json_success(result)

        msg_id = self.send_stream_message(test_bot, "Denmark")
        set_message_deleting_params(administrators_system_group, everyone_system_group, "unlimited")

        result = test_delete_message_by_other_user(msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_bot_owner(msg_id)
        self.assert_json_success(result)

        msg_id = self.send_stream_message(test_bot, "Denmark")
        set_message_deleting_params(administrators_system_group, everyone_system_group, 600)

        message = Message.objects.get(id=msg_id)
        message.date_sent = timezone_now() - timedelta(seconds=700)
        message.save()

        result = test_delete_message_by_other_user(msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_bot_owner(msg_id)
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        result = test_delete_message_by_admin(msg_id)
        self.assert_json_success(result)

        # Check that the bot can also delete the messages sent by them
        # depending on the realm permissions for message deletion.
        set_message_deleting_params(administrators_system_group, administrators_system_group, 600)
        msg_id = self.send_stream_message(test_bot, "Denmark")
        result = self.api_delete(test_bot, f"/api/v1/messages/{msg_id}")
        self.assert_json_error(result, "You don't have permission to delete this message")

        set_message_deleting_params(administrators_system_group, everyone_system_group, 600)
        message = Message.objects.get(id=msg_id)
        message.date_sent = timezone_now() - timedelta(seconds=700)
        message.save()

        result = self.api_delete(test_bot, f"/api/v1/messages/{msg_id}")
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        message.date_sent = timezone_now() - timedelta(seconds=400)
        message.save()
        result = self.api_delete(test_bot, f"/api/v1/messages/{msg_id}")
        self.assert_json_success(result)

    def test_delete_message_according_to_can_delete_any_message_group(self) -> None:
        def check_delete_message_by_sender(
            sender_name: str, error_msg: str | None = None, is_stream_message: bool = True
        ) -> None:
            sender = self.example_user(sender_name)
            if is_stream_message:
                msg_id = self.send_stream_message(sender, "Verona")
            else:
                msg_id = self.send_personal_message(sender, self.example_user("desdemona"))

            self.login_user(sender)
            result = self.client_delete(f"/json/messages/{msg_id}")
            if error_msg is None:
                self.assert_json_success(result)
            else:
                self.assert_json_error(result, error_msg)

        def check_delete_message_by_other_user(
            sender_name: str,
            other_user_name: str,
            error_msg: str | None = None,
            is_stream_message: bool = True,
        ) -> None:
            sender = self.example_user(sender_name)
            other_user = self.example_user(other_user_name)
            if is_stream_message:
                msg_id = self.send_stream_message(sender, "Verona")
            else:
                msg_id = self.send_personal_message(sender, other_user)
            self.login_user(other_user)
            result = self.client_delete(f"/json/messages/{msg_id}")
            if error_msg is None:
                self.assert_json_success(result)
            else:
                self.assert_json_error(result, error_msg)

        realm = get_realm("zulip")
        stream = get_stream("Verona", realm)
        iago = self.example_user("iago")

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm_for_sharding=realm, is_system_group=True
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=realm, is_system_group=True
        )
        everyone_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm_for_sharding=realm, is_system_group=True
        )
        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_any_message_group",
            administrators_system_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            everyone_system_group,
            acting_user=None,
        )

        # Only admins can delete any message. Everyone else can only delete their
        # own message.
        check_delete_message_by_sender("shiva")
        check_delete_message_by_other_user(
            "hamlet", "shiva", "You don't have permission to delete this message"
        )
        check_delete_message_by_other_user("hamlet", "iago")

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_any_message_group",
            moderators_system_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            administrators_system_group,
            acting_user=None,
        )

        # Admins and moderators can delete any message. No one else can delete any
        # message.

        # Test deleting channel messages
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message"
        )
        check_delete_message_by_sender("shiva")
        check_delete_message_by_other_user("iago", "shiva")
        check_delete_message_by_other_user(
            "hamlet", "cordelia", "You don't have permission to delete this message"
        )
        # Test deleting DMs
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message", is_stream_message=False
        )
        check_delete_message_by_sender("shiva", is_stream_message=False)
        check_delete_message_by_other_user("iago", "shiva", is_stream_message=False)
        check_delete_message_by_other_user(
            "hamlet",
            "cordelia",
            "You don't have permission to delete this message",
            is_stream_message=False,
        )

        # Check that guest cannot delete any message even when they are member
        # of the group which is allowed to delete any message.
        polonius = self.example_user("polonius")
        hamlet = self.example_user("hamlet")
        user_group = check_add_user_group(
            realm, "test-group", [hamlet, polonius], acting_user=hamlet
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_delete_any_message_group",
            user_group,
            acting_user=None,
        )
        # Test deleting channel messages
        check_delete_message_by_other_user("cordelia", "hamlet")
        check_delete_message_by_other_user(
            "cordelia", "polonius", "You don't have permission to delete this message"
        )
        # Test deleting DMs
        check_delete_message_by_other_user(
            "cordelia",
            "polonius",
            "You don't have permission to delete this message",
            is_stream_message=False,
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_any_message_group",
            nobody_system_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            nobody_system_group,
            acting_user=None,
        )

        check_delete_message_by_other_user(
            "cordelia", "shiva", "You don't have permission to delete this message"
        )
        check_delete_message_by_other_user(
            "cordelia",
            "shiva",
            "You don't have permission to delete this message",
            is_stream_message=False,
        )

        do_change_stream_group_based_setting(
            stream,
            "can_delete_any_message_group",
            moderators_system_group,
            acting_user=iago,
        )
        # Users in channel-level `can_delete_any_message_group` can delete
        # any message in the channel.
        check_delete_message_by_other_user("cordelia", "shiva")
        check_delete_message_by_sender(
            "polonius", "You don't have permission to delete this message"
        )

        do_change_stream_group_based_setting(
            stream,
            "can_delete_any_message_group",
            nobody_system_group,
            acting_user=iago,
        )
        do_change_stream_group_based_setting(
            stream,
            "can_administer_channel_group",
            moderators_system_group,
            acting_user=iago,
        )
        # Channel administrators can't delete messages if they don't have
        # the required permissions.
        check_delete_message_by_other_user(
            "cordelia", "shiva", "You don't have permission to delete this message"
        )
        check_delete_message_by_other_user(
            "cordelia", "iago", "You don't have permission to delete this message"
        )

        do_change_stream_group_based_setting(
            stream,
            "can_delete_any_message_group",
            everyone_system_group,
            acting_user=iago,
        )
        # Everyone is allowed to delete any message in the channel.
        check_delete_message_by_other_user("cordelia", "polonius")
        check_delete_message_by_other_user("cordelia", "iago")

        # Cannot delete DMs as organization-level permission is set to nobody.
        check_delete_message_by_other_user(
            "cordelia",
            "iago",
            "You don't have permission to delete this message",
            is_stream_message=False,
        )
        check_delete_message_by_sender(
            "iago", "You don't have permission to delete this message", is_stream_message=False
        )

    def test_delete_message_according_to_can_delete_own_message_group(self) -> None:
        def check_delete_message_by_sender(
            sender_name: str, error_msg: str | None = None, is_stream_message: bool = True
        ) -> None:
            sender = self.example_user(sender_name)
            if is_stream_message:
                msg_id = self.send_stream_message(sender, "Verona")
            else:
                msg_id = self.send_personal_message(sender, self.example_user("desdemona"))

            self.login_user(sender)
            result = self.client_delete(f"/json/messages/{msg_id}")
            if error_msg is None:
                self.assert_json_success(result)
            else:
                self.assert_json_error(result, error_msg)

        realm = get_realm("zulip")
        stream = get_stream("Verona", realm)
        iago = self.example_user("iago")

        administrators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm_for_sharding=realm, is_system_group=True
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=realm, is_system_group=True
        )
        everyone_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm_for_sharding=realm, is_system_group=True
        )
        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=realm, is_system_group=True
        )
        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            administrators_system_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_delete_any_message_group",
            nobody_system_group,
            acting_user=None,
        )
        # Test deleting channel messages
        check_delete_message_by_sender("shiva", "You don't have permission to delete this message")
        check_delete_message_by_sender("iago")
        # Test deleting DMs
        check_delete_message_by_sender(
            "shiva", "You don't have permission to delete this message", is_stream_message=False
        )
        check_delete_message_by_sender("iago", is_stream_message=False)

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            moderators_system_group,
            acting_user=None,
        )
        # Test deleting channel messages
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message"
        )
        check_delete_message_by_sender("shiva")
        # Test deleting DMs
        check_delete_message_by_sender(
            "cordelia", "You don't have permission to delete this message", is_stream_message=False
        )
        check_delete_message_by_sender("shiva", is_stream_message=False)

        do_change_realm_permission_group_setting(
            realm,
            "can_delete_own_message_group",
            members_system_group,
            acting_user=None,
        )
        check_delete_message_by_sender(
            "polonius", "You don't have permission to delete this message"
        )
        check_delete_message_by_sender("cordelia")

        do_change_realm_permission_group_setting(
            realm, "can_delete_own_message_group", everyone_system_group, acting_user=None
        )
        # Test deleting channel messages
        check_delete_message_by_sender("cordelia")
        check_delete_message_by_sender("polonius")
        # Test deleting DMs
        check_delete_message_by_sender("cordelia", is_stream_message=False)
        check_delete_message_by_sender("polonius", is_stream_message=False)

        do_change_realm_permission_group_setting(
            realm, "can_delete_own_message_group", nobody_system_group, acting_user=None
        )

        do_change_stream_group_based_setting(
            stream,
            "can_delete_own_message_group",
            members_system_group,
            acting_user=iago,
        )
        # Users in per-channel `can_delete_own_message_group` can delete their
        # own messages.
        check_delete_message_by_sender("hamlet")
        check_delete_message_by_sender(
            "polonius", "You don't have permission to delete this message"
        )

        do_change_stream_group_based_setting(
            stream,
            "can_delete_own_message_group",
            nobody_system_group,
            acting_user=iago,
        )
        do_change_stream_group_based_setting(
            stream,
            "can_administer_channel_group",
            moderators_system_group,
            acting_user=iago,
        )
        # Channel administrators can't delete messages if they don't have
        # the required permissions.
        check_delete_message_by_sender("shiva", "You don't have permission to delete this message")
        check_delete_message_by_sender("iago", "You don't have permission to delete this message")

        do_change_stream_group_based_setting(
            stream,
            "can_delete_own_message_group",
            everyone_system_group,
            acting_user=iago,
        )
        check_delete_message_by_sender("iago")

        # Cannot delete DMs as organization-level permission is set to nobody.
        check_delete_message_by_sender(
            "iago", "You don't have permission to delete this message", is_stream_message=False
        )

    def test_delete_event_sent_after_transaction_commits(self) -> None:
        """
        Tests that `send_event_rollback_unsafe` is hooked to `transaction.on_commit`.
        This is important, because we don't want to end up holding locks on message rows
        for too long if the event queue runs into a problem.
        """
        hamlet = self.example_user("hamlet")
        self.send_stream_message(hamlet, "Denmark")
        message = self.get_last_message()

        with (
            self.capture_send_event_calls(expected_num_events=1),
            mock.patch("zerver.tornado.django_api.queue_json_publish_rollback_unsafe") as m,
        ):
            m.side_effect = AssertionError(
                "Events should be sent only after the transaction commits."
            )
            do_delete_messages(hamlet.realm, [message], acting_user=None)

    def test_delete_message_in_unsubscribed_private_stream(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        self.assertEqual(iago.role, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login("hamlet")

        self.make_stream("privatestream", invite_only=True, history_public_to_subscribers=False)
        self.subscribe(hamlet, "privatestream")
        self.subscribe(iago, "privatestream")
        msg_id = self.send_stream_message(
            hamlet, "privatestream", topic_name="editing", content="before edit"
        )
        self.unsubscribe(iago, "privatestream")
        self.logout()
        self.login("iago")
        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_error(result, "Invalid message(s)")
        self.assertTrue(Message.objects.filter(id=msg_id).exists())

        # Ensure iago can delete the message after resubscribing, to be certain
        # it's the subscribed/unsubscribed status that's the decisive factor in the
        # permission to do so.
        self.subscribe(iago, "privatestream")
        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_success(result)
        self.assertFalse(Message.objects.filter(id=msg_id).exists())

    def test_delete_message_from_archived_channel(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")

        stream = self.make_stream("stream1")
        self.subscribe(hamlet, "stream1")
        msg_id = self.send_stream_message(
            hamlet, "stream1", topic_name="editing", content="before edit"
        )
        do_deactivate_stream(stream, acting_user=hamlet)

        result = self.client_delete(f"/json/messages/{msg_id}")
        self.assert_json_error(result, "Invalid message(s)")

    def test_update_first_message_id_on_stream_message_deletion(self) -> None:
        realm = get_realm("zulip")
        stream_name = "test"
        cordelia = self.example_user("cordelia")
        self.make_stream(stream_name)
        self.subscribe(cordelia, stream_name)
        message_ids = [self.send_stream_message(cordelia, stream_name) for _ in range(5)]
        first_message_id = message_ids[0]

        message = Message.objects.get(id=message_ids[3])
        do_delete_messages(realm, [message], acting_user=None)
        stream = get_stream(stream_name, realm)
        self.assertEqual(stream.first_message_id, first_message_id)

        first_message = Message.objects.get(id=first_message_id)
        do_delete_messages(realm, [first_message], acting_user=None)
        stream = get_stream(stream_name, realm)
        self.assertEqual(stream.first_message_id, message_ids[1])

        all_messages = Message.objects.filter(id__in=message_ids)
        with self.assert_database_query_count(26):
            do_delete_messages(realm, all_messages, acting_user=None)
        stream = get_stream(stream_name, realm)
        self.assertEqual(stream.first_message_id, None)

    @mock.patch("zerver.lib.push_notifications.send_push_notifications")
    @mock.patch("zerver.lib.push_notifications.push_notifications_configured", return_value=True)
    def test_clear_push_notifications_on_message_deletion(
        self,
        mock_push_notifications: mock.MagicMock,
        mock_send_push_notifications: mock.MagicMock,
    ) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.register_push_device(cordelia.id)
        do_change_user_setting(cordelia, "enable_stream_push_notifications", True, acting_user=None)

        def get_message_ids_with_active_push_notification(user_profile: UserProfile) -> list[int]:
            return list(
                UserMessage.objects.filter(
                    user_profile=user_profile,
                )
                .extra(  # noqa: S610
                    where=[UserMessage.where_active_push_notification()],
                )
                .order_by("message_id")
                .values_list("message_id", flat=True)
            )

        # Initially, no active push notifications.
        self.assertEqual(get_message_ids_with_active_push_notification(cordelia), [])

        self.subscribe(cordelia, "Verona")
        message_ids = [self.send_stream_message(hamlet, "Verona")]

        # Verify push notifications sent to `cordelia` for `message_ids`
        self.assertEqual(
            get_message_ids_with_active_push_notification(cordelia),
            message_ids,
        )

        messages = Message.objects.filter(id__in=message_ids)
        with (
            mock.patch(
                "zerver.worker.missedmessage_mobile_notifications.handle_remove_push_notification"
            ) as mock_handle_remove_push_notification,
            self.captureOnCommitCallbacks(execute=True),
        ):
            do_delete_messages(realm, messages, acting_user=None)

        # Verify messages deleted, `handle_remove_push_notification` called
        # to clear/revoke push notifications, usermessages deleted.
        self.assertFalse(Message.objects.filter(id__in=message_ids).exists())
        mock_handle_remove_push_notification.assert_called_once()
        self.assertEqual(
            get_message_ids_with_active_push_notification(cordelia),
            [],
        )
