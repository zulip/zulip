from datetime import timedelta

from django.utils.timezone import now as timezone_now

from zerver.actions.message_send import (
    filter_presence_idle_user_ids,
    get_notifiable_if_idle_user_ids,
)
from zerver.actions.users import do_deactivate_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Recipient, Subscription, UserPresence, UserProfile
from zerver.models.recipients import (
    DirectMessageGroup,
    bulk_get_direct_message_group_user_ids,
    bulk_get_or_create_direct_message_groups,
    get_direct_message_group,
    get_direct_message_group_hash,
    get_direct_message_group_user_ids,
    get_or_create_direct_message_group,
)


class MissedMessageTest(ZulipTestCase):
    def test_presence_idle_user_ids(self) -> None:
        UserPresence.objects.all().delete()

        sender = self.example_user("cordelia")
        realm = sender.realm
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        hamlet_notifications_data = self.create_user_notifications_data_object(user_id=hamlet.id)
        othello_notifications_data = self.create_user_notifications_data_object(user_id=othello.id)

        def assert_presence_idle_user_ids(user_ids: list[int]) -> None:
            presence_idle_user_ids = filter_presence_idle_user_ids(
                get_notifiable_if_idle_user_ids(
                    realm=realm,
                    sender_id=sender.id,
                    user_notifications_data_list=[
                        hamlet_notifications_data,
                        othello_notifications_data,
                    ],
                )
            )
            self.assertEqual(sorted(user_ids), sorted(presence_idle_user_ids))

        def set_presence(user: UserProfile, client_name: str, ago: int) -> None:
            when = timezone_now() - timedelta(seconds=ago)
            UserPresence.objects.update_or_create(
                user_profile_id=user.id,
                defaults=dict(
                    realm_id=user.realm_id, last_active_time=when, last_connected_time=when
                ),
            )

        hamlet_notifications_data.dm_push_notify = True
        othello_notifications_data.dm_push_notify = True
        assert_presence_idle_user_ids([hamlet.id, othello.id])

        # We have already thoroughly tested the `is_notifiable` function elsewhere,
        # so we needn't test all cases here. This test exists mainly to avoid a bug
        # which existed earlier, where we only looked at `private_message` and the
        # `mentioned` flag, not stream level notifications.
        # Simulate Hamlet has turned on notifications for the stream, and test that he's
        # in the list.
        hamlet_notifications_data.dm_push_notify = False
        othello_notifications_data.dm_push_notify = False
        hamlet_notifications_data.stream_email_notify = True
        assert_presence_idle_user_ids([hamlet.id])

        # Hamlet is idle (and is supposed to receive stream notifications), so he should be in the list.
        set_presence(hamlet, "iPhone", ago=5000)
        assert_presence_idle_user_ids([hamlet.id])

        # If Hamlet is active, don't include him in the `presence_idle` list.
        set_presence(hamlet, "website", ago=15)
        assert_presence_idle_user_ids([])

        # Hamlet is active now, so only Othello should be in the list for a group
        # direct message.
        hamlet_notifications_data.stream_email_notify = False
        hamlet_notifications_data.dm_push_notify = False
        othello_notifications_data.dm_push_notify = True
        assert_presence_idle_user_ids([othello.id])


class TestBulkGetDirectMessageGroupUserIds(ZulipTestCase):
    def test_bulk_get_direct_message_group_user_ids(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        iago = self.example_user("iago")
        message_ids = [
            self.send_group_direct_message(hamlet, [cordelia, othello], "test"),
            self.send_group_direct_message(cordelia, [hamlet, othello, iago], "test"),
        ]

        messages = Message.objects.filter(id__in=message_ids).order_by("id")

        first_direct_message_group_recipient = messages[0].recipient
        first_direct_message_group_user_ids = set(
            get_direct_message_group_user_ids(first_direct_message_group_recipient)
        )
        first_direct_message_group = get_or_create_direct_message_group(
            list(first_direct_message_group_user_ids)
        )

        second_direct_message_group_recipient = messages[1].recipient
        second_direct_message_group_user_ids = set(
            get_direct_message_group_user_ids(second_direct_message_group_recipient)
        )
        second_direct_message_group = get_or_create_direct_message_group(
            list(second_direct_message_group_user_ids)
        )

        direct_message_group_user_ids = bulk_get_direct_message_group_user_ids(
            [first_direct_message_group_recipient.id, second_direct_message_group_recipient.id]
        )

        self.assertEqual(
            direct_message_group_user_ids[first_direct_message_group_recipient.id],
            first_direct_message_group_user_ids,
        )
        self.assertEqual(
            first_direct_message_group.group_size, len(first_direct_message_group_user_ids)
        )

        self.assertEqual(
            direct_message_group_user_ids[second_direct_message_group_recipient.id],
            second_direct_message_group_user_ids,
        )
        self.assertEqual(
            second_direct_message_group.group_size, len(second_direct_message_group_user_ids)
        )

    def test_bulk_get_direct_message_group_user_ids_empty_list(self) -> None:
        self.assertEqual(bulk_get_direct_message_group_user_ids([]), {})


class TestGetDirectMessageGroup(ZulipTestCase):
    def test_get_direct_message_group_nonexistent(self) -> None:
        """Test that get_direct_message_group returns None when the group doesn't exist."""
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        # These users haven't had any group DM, so no DirectMessageGroup exists
        result = get_direct_message_group([hamlet.id, cordelia.id])
        self.assertIsNone(result)

    def test_get_direct_message_group_exists(self) -> None:
        """Test that get_direct_message_group returns the group when it exists."""
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        # Create a group DM which will create the DirectMessageGroup
        self.send_group_direct_message(hamlet, [cordelia, othello], "test")

        # Now the DirectMessageGroup should exist
        result = get_direct_message_group([hamlet.id, cordelia.id, othello.id])
        assert result is not None
        self.assertEqual(result.group_size, 3)


class TestBulkGetOrCreateDirectMessageGroups(ZulipTestCase):
    def test_bulk_get_or_create_direct_message_groups(self) -> None:
        """
        Groups created in bulk should be the same as those created one
        at a time, and creating more of them shouldn't take more
        queries.
        """
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        prospero = self.example_user("prospero")
        do_deactivate_user(prospero, acting_user=None)

        def group_data(
            direct_message_group: DirectMessageGroup,
        ) -> tuple[int, set[tuple[int, bool]]]:
            recipient = direct_message_group.recipient
            assert recipient is not None
            self.assertEqual(recipient.type, Recipient.DIRECT_MESSAGE_GROUP)
            self.assertEqual(recipient.type_id, direct_message_group.id)
            return (
                direct_message_group.group_size,
                set(
                    Subscription.objects.filter(recipient=recipient).values_list(
                        "user_profile_id", "is_user_active"
                    )
                ),
            )

        with self.assert_database_query_count(0):
            self.assertEqual(bulk_get_or_create_direct_message_groups([]), {})

        existing_group = get_or_create_direct_message_group([hamlet.id, cordelia.id])
        id_lists = [
            [hamlet.id, cordelia.id],
            [hamlet.id, othello.id],
            [othello.id, hamlet.id],
            [hamlet.id, cordelia.id, prospero.id],
            [hamlet.id],
        ]
        with self.assert_database_query_count(7):
            direct_message_groups = bulk_get_or_create_direct_message_groups(id_lists)

        self.assertEqual(
            set(direct_message_groups), {get_direct_message_group_hash(ids) for ids in id_lists}
        )
        self.assert_length(direct_message_groups, 4)
        self.assertEqual(
            direct_message_groups[get_direct_message_group_hash([hamlet.id, cordelia.id])].id,
            existing_group.id,
        )
        expected_data = {
            (hamlet.id, cordelia.id): (2, {(hamlet.id, True), (cordelia.id, True)}),
            (hamlet.id, othello.id): (2, {(hamlet.id, True), (othello.id, True)}),
            (hamlet.id, cordelia.id, prospero.id): (
                3,
                {(hamlet.id, True), (cordelia.id, True), (prospero.id, False)},
            ),
            (hamlet.id,): (1, {(hamlet.id, True)}),
        }
        for ids, data in expected_data.items():
            direct_message_group = get_direct_message_group(list(ids))
            assert direct_message_group is not None
            self.assertEqual(group_data(direct_message_group), data)
            self.assertEqual(
                direct_message_groups[get_direct_message_group_hash(list(ids))].id,
                direct_message_group.id,
            )

        # A group created on its own gets the same data.
        self.assertEqual(
            group_data(get_or_create_direct_message_group([cordelia.id, othello.id])),
            (2, {(cordelia.id, True), (othello.id, True)}),
        )

        # Creating a single group takes as many queries as creating three.
        with self.assert_database_query_count(7):
            bulk_get_or_create_direct_message_groups([[cordelia.id]])
        with self.assert_database_query_count(1):
            bulk_get_or_create_direct_message_groups(id_lists)
