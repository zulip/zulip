from datetime import timedelta
import orjson
from django.utils.timezone import now as timezone_now
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.meetings import Meeting, MeetingSlot
from zerver.lib.meeting_actions import do_create_meeting, check_meeting_deadlines
from zerver.lib.exceptions import JsonableError

class TestMeetingsCoverage(ZulipTestCase):
    def test_missing_coverage_edges(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user
        ("cordelia")
        self.login_user(hamlet)

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
        future_deadline = (timezone_now() + timedelta(days=1)).isoformat()
        
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

    def test_deadline_edge_cases(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        stream = self.make_stream("Deadline Stream")
        
        # Create a meeting that will expire
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
        
        # Error: Respond after deadline
        self.login_user(hamlet)
        result = self.client_patch(f"/json/meetings/{meeting.id}/responses", {
            "slot_responses": orjson.dumps({str(slot.id): True}).decode(),
        })
        self.assert_json_error(result, "The RSVP deadline has passed.")
