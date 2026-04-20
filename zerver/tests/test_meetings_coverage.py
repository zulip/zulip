from datetime import timedelta
import orjson
from django.utils.timezone import now as timezone_now
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.meetings import Meeting, MeetingSlot
from zerver.lib.meeting_actions import check_meeting_deadlines


class TestMeetings(ZulipTestCase):
    def test_get_meeting_candidates(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        # 1. No stream name - get all realm users
        result = self.client_get("/json/meetings/candidates")
        self.assert_json_success(result)
        content = orjson.loads(result.content)
        self.assertEqual(len(content["users"]), 11)

        # 2. With a fresh stream name
        stream_name = "Private Meeting Stream"
        self.make_stream(stream_name, invite_only=True)
        self.subscribe(hamlet, stream_name)

        result = self.client_get("/json/meetings/candidates", {"stream_name": stream_name})
        self.assert_json_success(result)
        content = orjson.loads(result.content)
        self.assertEqual(len(content["users"]), 1)

    def test_create_meeting_and_flow(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        self.login_user(hamlet)

        # 1. Error: Deadline in the past
        past_deadline = (timezone_now() - timedelta(days=1)).isoformat()
        result = self.client_post("/json/meetings", {
            "topic": "Past Meeting",
            "slots": orjson.dumps([{"start_time": timezone_now().isoformat()}]).decode(),
            "deadline": past_deadline,
            "invite_user_ids": orjson.dumps([cordelia.id]).decode(),
            "create_channel": orjson.dumps(True).decode(),
        })
        self.assert_json_error(result, "Deadline must be in the future.")

        # 2. Error: No slots
        future_deadline = (timezone_now() + timedelta(days=1)).isoformat()
        result = self.client_post("/json/meetings", {
            "topic": "No Slots Meeting",
            "slots": orjson.dumps([]).decode(),
            "deadline": future_deadline,
            "invite_user_ids": orjson.dumps([cordelia.id]).decode(),
            "create_channel": orjson.dumps(True).decode(),
        })
        self.assert_json_error(result, "At least one time slot is required.")

        # 3. Success: Create with channel
        slot1_start = (timezone_now() + timedelta(days=2)).replace(microsecond=0)
        slot2_start = (timezone_now() + timedelta(days=3)).replace(microsecond=0)
        result = self.client_post("/json/meetings", {
            "topic": "Project X Sync",
            "slots": orjson.dumps([
                {"start_time": slot1_start.isoformat()},
                {"start_time": slot2_start.isoformat(), "end_time": (slot2_start + timedelta(hours=1)).isoformat()},
            ]).decode(),
            "deadline": future_deadline,
            "invite_user_ids": orjson.dumps([cordelia.id, othello.id]).decode(),
            "create_channel": orjson.dumps(True).decode(),
        })
        self.assert_json_success(result)
        meeting_id = orjson.loads(result.content)["meeting_id"]

        # 4. Get details
        result = self.client_get(f"/json/meetings/{meeting_id}")
        self.assert_json_success(result)
        content = orjson.loads(result.content)
        slot_ids = [s["slot_id"] for s in content["slots"]]

        # 5. Respond
        self.login_user(cordelia)
        # Error: Unknown slot
        result = self.client_patch(f"/json/meetings/{meeting_id}/responses", {
            "slot_responses": orjson.dumps({"999999": True}).decode(),
        })
        self.assert_json_error(result, "Unknown slot IDs: [999999]")

        # Success
        result = self.client_patch(f"/json/meetings/{meeting_id}/responses", {
            "slot_responses": orjson.dumps({str(slot_ids[0]): True, str(slot_ids[1]): False}).decode(),
        })
        self.assert_json_success(result)

        # Othello
        self.login_user(othello)
        result = self.client_patch(f"/json/meetings/{meeting_id}/responses", {
            "slot_responses": orjson.dumps({str(slot_ids[0]): True}).decode(),
        })
        self.assert_json_success(result)

        # 6. Rank
        self.login_user(hamlet)
        result = self.client_get(f"/json/meetings/{meeting_id}/responses")
        self.assert_json_success(result)
        content = orjson.loads(result.content)
        self.assertEqual(content["slots"][0]["available_count"], 2)

        # 7. Confirm
        self.login_user(othello)
        result = self.client_post(f"/json/meetings/{meeting_id}/confirm", {
            "winning_slot_id": orjson.dumps(slot_ids[0]).decode(),
        })
        self.assert_json_error(result, "Only the meeting owner can confirm a time.")

        self.login_user(hamlet)
        result = self.client_post(f"/json/meetings/{meeting_id}/confirm", {
            "winning_slot_id": orjson.dumps(slot_ids[0]).decode(),
        })
        self.assert_json_success(result)

    def test_create_meeting_existing_stream(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        stream = self.make_stream("Existing Stream")
        future_deadline = (timezone_now() + timedelta(days=1)).isoformat()

        result = self.client_post("/json/meetings", {
            "topic": "Existing Stream Meeting",
            "slots": orjson.dumps([{"start_time": timezone_now().isoformat()}]).decode(),
            "deadline": future_deadline,
            "invite_user_ids": orjson.dumps([]).decode(),
            "create_channel": orjson.dumps(False).decode(),
            "stream_id": orjson.dumps(stream.id).decode(),
        })
        self.assert_json_success(result)

    def test_meeting_not_found(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        result = self.client_get("/json/meetings/999999")
        self.assert_json_error(result, "Meeting not found.")

    def test_check_meeting_deadlines(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        stream = self.make_stream("Deadline Stream")
        meeting = Meeting.objects.create(
            owner=hamlet,
            topic="Expiring Meeting",
            deadline=timezone_now() - timedelta(minutes=1),
            stream=stream,
        )
        slot = MeetingSlot.objects.create(meeting=meeting, start_time=timezone_now())

        check_meeting_deadlines()

        meeting.refresh_from_db()
        self.assertEqual(meeting.status, Meeting.Status.DEADLINE_PASSED)

        result = self.client_patch(f"/json/meetings/{meeting.id}/responses", {
            "slot_responses": orjson.dumps({str(slot.id): True}).decode(),
        })
        self.assert_json_error(result, "The RSVP deadline has passed.")

    def test_missing_coverage_edges(self) -> None:
        from zerver.lib.meeting_actions import do_create_meeting
        from zerver.lib.exceptions import JsonableError
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.login_user(hamlet)

        future_deadline = (timezone_now() + timedelta(days=1)).isoformat()
        future_deadline_dt = timezone_now() + timedelta(days=1)

        # Line 95: Directly call the library function to bypass view-level validation
        with self.assertRaisesRegex(JsonableError, "Either create_channel must be True or a stream must be provided."):
            do_create_meeting(
                owner=hamlet,
                topic="Direct Call Test",
                slots=[(timezone_now(), None)],
                deadline=future_deadline_dt,
                invite_user_ids=[],
                create_channel=False,
                stream=None
            )

        # Create a valid meeting for subsequent tests via API
        slot1_start = (timezone_now() + timedelta(days=2)).replace(microsecond=0)
        slot2_start = (timezone_now() + timedelta(days=3)).replace(microsecond=0)
        
        result = self.client_post("/json/meetings", {
            "topic": "Coverage Sync",
            "slots": orjson.dumps([
                {"start_time": slot1_start.isoformat()},
                {"start_time": slot2_start.isoformat(), "end_time": (slot2_start + timedelta(hours=1)).isoformat()},
            ]).decode(),
            "deadline": future_deadline,
            "invite_user_ids": orjson.dumps([cordelia.id]).decode(),
            "create_channel": orjson.dumps(True).decode(),
        })
        self.assert_json_success(result)
        meeting_id = orjson.loads(result.content)["meeting_id"]

        result = self.client_get(f"/json/meetings/{meeting_id}")
        content = orjson.loads(result.content)
        slot_ids = [s["slot_id"] for s in content["slots"]]

        # Line 175-176: Confirm with invalid slot ID
        result = self.client_post(f"/json/meetings/{meeting_id}/confirm", {
            "winning_slot_id": orjson.dumps(999999).decode(),
        })
        self.assert_json_error(result, "Invalid slot ID.")

        # Line 184: Confirm with a slot that HAS an end_time (slot_ids[1])
        result = self.client_post(f"/json/meetings/{meeting_id}/confirm", {
            "winning_slot_id": orjson.dumps(slot_ids[1]).decode(),
        })
        self.assert_json_success(result)

        # Line 171: Try to confirm an ALREADY confirmed meeting
        result = self.client_post(f"/json/meetings/{meeting_id}/confirm", {
            "winning_slot_id": orjson.dumps(slot_ids[1]).decode(),
        })
        self.assert_json_error(result, "Meeting is already confirmed.")

        # Line 133: Try to upsert responses on an ALREADY confirmed meeting
        self.login_user(cordelia)
        result = self.client_patch(f"/json/meetings/{meeting_id}/responses", {
            "slot_responses": orjson.dumps({str(slot_ids[1]): True}).decode(),
        })
        self.assert_json_error(result, "This meeting has already been confirmed.")

    def test_additional_meeting_actions_coverage(self) -> None:
        from zerver.lib.meeting_actions import (
            do_create_meeting, 
            assert_user_can_submit_meeting_responses
        )
        from zerver.lib.exceptions import JsonableError
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        self.login_user(hamlet)
        future_dt = timezone_now() + timedelta(days=2)

        # 1. Actions L115-116: Invalid invite_user_ids (None-existent ID)
        stream = self.make_stream("test_stream")
        with self.assertRaisesRegex(JsonableError, "Invalid invite_user_ids: \[999999\]"):
            do_create_meeting(
                owner=hamlet, topic="Bad Invitees", slots=[(future_dt, None)],
                deadline=timezone_now() + timedelta(days=1), invite_user_ids=[999999],
                create_channel=False, stream=stream
            )

        # 2. Actions L120-124: Real user but NOT a subscriber of the existing channel
        with self.assertRaisesRegex(JsonableError, "All invited users must already be subscribed"):
            do_create_meeting(
                owner=hamlet, topic="Missing Subs", slots=[(future_dt, None)],
                deadline=timezone_now() + timedelta(days=1), invite_user_ids=[cordelia.id],
                create_channel=False, stream=stream
            )

        # 3. Actions L83-85: User not subscribed to a public stream meeting
        meeting = Meeting.objects.create(
            owner=hamlet, topic="Public Meeting", 
            deadline=timezone_now() + timedelta(days=1), stream=stream
        )
        stream.invite_only = False
        stream.save()
        with self.assertRaisesRegex(JsonableError, "You must be subscribed to this meeting's channel"):
            assert_user_can_submit_meeting_responses(othello, meeting)

        # 4. Views L131-132: Logic check for non-integer keys in responses
        future_deadline = (timezone_now() + timedelta(days=1)).isoformat()
        result = self.client_post("/json/meetings", {
            "topic": "Views Logic Test",
            "slots": orjson.dumps([{"start_time": timezone_now().isoformat()}]).decode(),
            "deadline": future_deadline,
            "invite_user_ids": "[]", "create_channel": "true",
        })
        m_id = orjson.loads(result.content)["meeting_id"]
        result = self.client_patch(f"/json/meetings/{m_id}/responses", {
            "slot_responses": orjson.dumps({"not_an_int": True}).decode(),
        })
        self.assert_json_error(result, "slot_responses keys must be integer slot IDs.")

        # 5. Views L66: stream_id is required when create_channel is False.
        result = self.client_post("/json/meetings", {
            "topic": "Missing Stream ID",
            "slots": orjson.dumps([{"start_time": timezone_now().isoformat()}]).decode(),
            "deadline": future_deadline,
            "invite_user_ids": "[]",
            "create_channel": orjson.dumps(False).decode(),
        })
        self.assert_json_error(result, "stream_id is required when create_channel is False.")