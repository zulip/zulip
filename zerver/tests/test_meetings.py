from datetime import datetime, timedelta, timezone

import time_machine

from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.exceptions import JsonableError
from zerver.lib.meeting_actions import (
    access_meeting_for_user,
    assert_user_can_submit_meeting_responses,
    check_meeting_deadlines,
    do_confirm_meeting,
    do_create_meeting,
    do_upsert_responses,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.meetings import Meeting
from zerver.models.streams import get_stream


class MeetingsBackendTest(ZulipTestCase):
    def _future_deadline(self) -> datetime:
        return datetime.now(tz=timezone.utc) + timedelta(days=7)

    def _slot_pair(self) -> tuple[datetime, datetime | None]:
        start = datetime.now(tz=timezone.utc) + timedelta(days=8)
        return (start, start + timedelta(hours=1))

    def test_private_stream_meeting_invisible_to_non_subscriber(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        self.login_user(hamlet)
        stream_name = "zulip_meetings_private_test"
        self.subscribe_via_post(hamlet, [stream_name], invite_only=True)
        stream = get_stream(stream_name, hamlet.realm)

        start, end = self._slot_pair()
        meeting = do_create_meeting(
            hamlet,
            "Planning sync",
            [(start, end)],
            self._future_deadline(),
            [],
            False,
            stream,
        )

        access_meeting_for_user(hamlet, meeting.id)

        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_meeting_for_user(othello, meeting.id)

    def test_invitee_subscribed_can_access_and_submit(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.login_user(hamlet)
        stream_name = "zulip_meetings_invite_test"
        self.subscribe_via_post(hamlet, [stream_name], invite_only=True)
        stream = get_stream(stream_name, hamlet.realm)
        bulk_add_subscriptions(hamlet.realm, [stream], [cordelia], acting_user=hamlet)

        start, end = self._slot_pair()
        meeting = do_create_meeting(
            hamlet,
            "Team lunch",
            [(start, end)],
            self._future_deadline(),
            [cordelia.id],
            False,
            stream,
        )

        access_meeting_for_user(cordelia, meeting.id)
        assert_user_can_submit_meeting_responses(cordelia, meeting)

        slot_id = meeting.slots.get().id
        do_upsert_responses(cordelia, meeting, {slot_id: True})

    def test_existing_channel_requires_invitees_already_subscribed(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.login_user(hamlet)
        stream_name = "zulip_meetings_existing_requires_subscribers"
        self.subscribe_via_post(hamlet, [stream_name], invite_only=True)
        stream = get_stream(stream_name, hamlet.realm)

        start, end = self._slot_pair()
        with self.assertRaisesRegex(JsonableError, "All invited users must already be subscribed"):
            do_create_meeting(
                hamlet,
                "Team lunch",
                [(start, end)],
                self._future_deadline(),
                [cordelia.id],
                False,
                stream,
            )

    def test_non_invitee_cannot_submit_responses(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        self.login_user(hamlet)
        stream_name = "zulip_meetings_rsvp_gate"
        self.subscribe_via_post(hamlet, [stream_name], invite_only=True)
        stream = get_stream(stream_name, hamlet.realm)

        start, end = self._slot_pair()
        meeting = do_create_meeting(
            hamlet,
            "Standup",
            [(start, end)],
            self._future_deadline(),
            [],
            False,
            stream,
        )

        slot_id = meeting.slots.get().id
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            assert_user_can_submit_meeting_responses(othello, meeting)

        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            do_upsert_responses(othello, meeting, {slot_id: True})

    def test_only_owner_can_confirm(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.login_user(hamlet)
        stream_name = "zulip_meetings_confirm"
        self.subscribe_via_post(hamlet, [stream_name], invite_only=True)
        stream = get_stream(stream_name, hamlet.realm)
        bulk_add_subscriptions(hamlet.realm, [stream], [cordelia], acting_user=hamlet)

        start, end = self._slot_pair()
        meeting = do_create_meeting(
            hamlet,
            "Review",
            [(start, end)],
            self._future_deadline(),
            [cordelia.id],
            False,
            stream,
        )
        slot_id = meeting.slots.get().id

        with self.assertRaisesRegex(JsonableError, "Only the meeting owner"):
            do_confirm_meeting(cordelia, meeting, slot_id)

        do_confirm_meeting(hamlet, meeting, slot_id)
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, Meeting.Status.CONFIRMED)

    def test_check_meeting_deadlines_marks_overdue(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        stream_name = "zulip_meetings_deadline"
        self.subscribe_via_post(hamlet, [stream_name], invite_only=True)
        stream = get_stream(stream_name, hamlet.realm)

        start, end = self._slot_pair()
        deadline = datetime.now(tz=timezone.utc) + timedelta(hours=2)
        meeting = do_create_meeting(
            hamlet,
            "Deadline test",
            [(start, end)],
            deadline,
            [],
            False,
            stream,
        )

        future = deadline + timedelta(days=1)
        with time_machine.travel(future, tick=False):
            check_meeting_deadlines()

        meeting.refresh_from_db()
        self.assertEqual(meeting.status, Meeting.Status.DEADLINE_PASSED)
