import time as time_module
from datetime import datetime, time, timedelta, timezone
from typing import Any

import orjson
from django.utils.timezone import now as timezone_now

from zerver.actions.recurring_scheduled_messages import (
    do_cancel_recurring_scheduled_message,
    do_create_recurring_scheduled_message,
    do_deliver_recurring_scheduled_message,
    try_deliver_one_recurring_scheduled_message,
)
from zerver.actions.users import change_user_is_active
from zerver.lib.recurring_scheduled_messages import compute_next_delivery
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message
from zerver.models.recurring_scheduled_messages import RecurringScheduledMessage

UTC = timezone.utc

# Fixed "now" used for compute_next_delivery unit tests.
# Wednesday 2026-01-07 at 10:00 UTC  (weekday = 2)
NOW = datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Unit tests: compute_next_delivery
# ---------------------------------------------------------------------------


class ComputeNextDeliveryTest(ZulipTestCase):
    def test_one_time_raises(self) -> None:
        with self.assertRaises(ValueError):
            compute_next_delivery(RecurringScheduledMessage.ONE_TIME, [], time(9, 0), NOW)

    def test_daily_time_not_yet_passed_today(self) -> None:
        result = compute_next_delivery(RecurringScheduledMessage.DAILY, [], time(11, 0), NOW)
        self.assertEqual(result, datetime(2026, 1, 7, 11, 0, 0, tzinfo=UTC))

    def test_daily_time_already_passed_today(self) -> None:
        result = compute_next_delivery(RecurringScheduledMessage.DAILY, [], time(9, 0), NOW)
        self.assertEqual(result, datetime(2026, 1, 8, 9, 0, 0, tzinfo=UTC))

    def test_daily_exactly_at_now_counts_as_passed(self) -> None:
        result = compute_next_delivery(RecurringScheduledMessage.DAILY, [], time(10, 0), NOW)
        self.assertEqual(result, datetime(2026, 1, 8, 10, 0, 0, tzinfo=UTC))

    def test_weekly_today_is_matching_day_time_not_passed(self) -> None:
        result = compute_next_delivery(RecurringScheduledMessage.WEEKLY, [2], time(11, 0), NOW)
        self.assertEqual(result, datetime(2026, 1, 7, 11, 0, 0, tzinfo=UTC))

    def test_weekly_today_is_matching_day_time_passed(self) -> None:
        result = compute_next_delivery(RecurringScheduledMessage.WEEKLY, [2], time(9, 0), NOW)
        self.assertEqual(result, datetime(2026, 1, 14, 9, 0, 0, tzinfo=UTC))

    def test_weekly_next_occurrence_is_future_day(self) -> None:
        result = compute_next_delivery(RecurringScheduledMessage.WEEKLY, [4], time(9, 0), NOW)
        self.assertEqual(result, datetime(2026, 1, 9, 9, 0, 0, tzinfo=UTC))

    def test_weekly_next_occurrence_wraps_to_next_week(self) -> None:
        result = compute_next_delivery(RecurringScheduledMessage.WEEKLY, [0], time(9, 0), NOW)
        self.assertEqual(result, datetime(2026, 1, 12, 9, 0, 0, tzinfo=UTC))

    def test_weekly_empty_recurrence_days_raises(self) -> None:
        with self.assertRaises(ValueError):
            compute_next_delivery(RecurringScheduledMessage.WEEKLY, [], time(9, 0), NOW)

    def test_specific_days_picks_earliest_future_day(self) -> None:
        result = compute_next_delivery(
            RecurringScheduledMessage.SPECIFIC_DAYS, [0, 2, 4], time(11, 0), NOW
        )
        self.assertEqual(result, datetime(2026, 1, 7, 11, 0, 0, tzinfo=UTC))

    def test_specific_days_skips_to_next_matching_day(self) -> None:
        result = compute_next_delivery(
            RecurringScheduledMessage.SPECIFIC_DAYS, [0, 2, 4], time(9, 0), NOW
        )
        self.assertEqual(result, datetime(2026, 1, 9, 9, 0, 0, tzinfo=UTC))

    def test_specific_days_wraps_across_week_boundary(self) -> None:
        result = compute_next_delivery(
            RecurringScheduledMessage.SPECIFIC_DAYS, [1], time(9, 0), NOW
        )
        self.assertEqual(result, datetime(2026, 1, 13, 9, 0, 0, tzinfo=UTC))

    def test_specific_days_empty_recurrence_days_raises(self) -> None:
        with self.assertRaises(ValueError):
            compute_next_delivery(
                RecurringScheduledMessage.SPECIFIC_DAYS, [], time(9, 0), NOW
            )

    # ------------------------------------------------------------------
    # Monthly — calendar_day rules
    # ------------------------------------------------------------------

    def test_monthly_calendar_day_in_current_month(self) -> None:
        # day=15 has not yet passed in January; next delivery is Jan 15.
        result = compute_next_delivery(
            RecurringScheduledMessage.MONTHLY,
            {"type": "calendar_day", "day": 15},
            time(9, 0),
            NOW,
        )
        self.assertEqual(result, datetime(2026, 1, 15, 9, 0, 0, tzinfo=UTC))

    def test_monthly_calendar_day_past_this_month(self) -> None:
        # day=5 is before NOW (Jan 7); next delivery rolls over to Feb 5.
        result = compute_next_delivery(
            RecurringScheduledMessage.MONTHLY,
            {"type": "calendar_day", "day": 5},
            time(9, 0),
            NOW,
        )
        self.assertEqual(result, datetime(2026, 2, 5, 9, 0, 0, tzinfo=UTC))

    def test_monthly_calendar_day_last_day(self) -> None:
        # day=-1 resolves to Jan 31 (last day of January).
        result = compute_next_delivery(
            RecurringScheduledMessage.MONTHLY,
            {"type": "calendar_day", "day": -1},
            time(9, 0),
            NOW,
        )
        self.assertEqual(result, datetime(2026, 1, 31, 9, 0, 0, tzinfo=UTC))

    def test_monthly_calendar_day_last_day_is_leap_day(self) -> None:
        # 2024 is a leap year; last day of February is Feb 29.
        after = datetime(2024, 1, 31, 10, 0, 0, tzinfo=UTC)
        result = compute_next_delivery(
            RecurringScheduledMessage.MONTHLY,
            {"type": "calendar_day", "day": -1},
            time(9, 0),
            after,
        )
        self.assertEqual(result, datetime(2024, 2, 29, 9, 0, 0, tzinfo=UTC))

    def test_monthly_calendar_day_clamped_for_short_month(self) -> None:
        # day=31 does not exist in February; it is clamped to Feb 28 (non-leap year).
        after = datetime(2026, 1, 31, 10, 0, 0, tzinfo=UTC)
        result = compute_next_delivery(
            RecurringScheduledMessage.MONTHLY,
            {"type": "calendar_day", "day": 31},
            time(9, 0),
            after,
        )
        self.assertEqual(result, datetime(2026, 2, 28, 9, 0, 0, tzinfo=UTC))

    # ------------------------------------------------------------------
    # Monthly — ordinal_weekday rules
    # ------------------------------------------------------------------

    def test_monthly_ordinal_weekday_first_monday_past_this_month(self) -> None:
        # First Monday of January 2026 is Jan 5 — before NOW (Jan 7).
        # The next first Monday is Feb 2 (Feb 1 is Sunday).
        result = compute_next_delivery(
            RecurringScheduledMessage.MONTHLY,
            {"type": "ordinal_weekday", "ordinal": 1, "weekday": 0},
            time(9, 0),
            NOW,
        )
        self.assertEqual(result, datetime(2026, 2, 2, 9, 0, 0, tzinfo=UTC))

    def test_monthly_ordinal_weekday_last_friday(self) -> None:
        # Last Friday of January 2026: Jan 31 is Saturday, so last Friday is Jan 30.
        result = compute_next_delivery(
            RecurringScheduledMessage.MONTHLY,
            {"type": "ordinal_weekday", "ordinal": -1, "weekday": 4},
            time(9, 0),
            NOW,
        )
        self.assertEqual(result, datetime(2026, 1, 30, 9, 0, 0, tzinfo=UTC))

    def test_monthly_ordinal_weekday_fourth_in_current_month(self) -> None:
        # Jan 1 is Thursday; first Wednesday is Jan 7; fourth Wednesday is Jan 28.
        # Jan 28 09:00 is after NOW (Jan 7 10:00), so delivery is Jan 28.
        # Note: the 4th occurrence of any weekday always falls on day 22–28, so
        # it exists in every month and a month is never skipped for ordinal=4.
        result = compute_next_delivery(
            RecurringScheduledMessage.MONTHLY,
            {"type": "ordinal_weekday", "ordinal": 4, "weekday": 2},
            time(9, 0),
            NOW,
        )
        self.assertEqual(result, datetime(2026, 1, 28, 9, 0, 0, tzinfo=UTC))

    def test_monthly_ordinal_weekday_advances_to_next_month_when_past(self) -> None:
        # The fourth Wednesday of January (Jan 28) has already passed at 10:00.
        # Feb 1 is Sunday; first Wednesday is Feb 4; fourth Wednesday is Feb 25.
        after = datetime(2026, 1, 28, 10, 0, 0, tzinfo=UTC)
        result = compute_next_delivery(
            RecurringScheduledMessage.MONTHLY,
            {"type": "ordinal_weekday", "ordinal": 4, "weekday": 2},
            time(9, 0),
            after,
        )
        self.assertEqual(result, datetime(2026, 2, 25, 9, 0, 0, tzinfo=UTC))

    def test_monthly_invalid_rule_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            compute_next_delivery(
                RecurringScheduledMessage.MONTHLY,
                {"type": "biweekly"},
                time(9, 0),
                NOW,
            )


# ---------------------------------------------------------------------------
# API tests: GET, POST, DELETE
# ---------------------------------------------------------------------------


class RecurringScheduledMessageAPITest(ZulipTestCase):
    def _stream_destination(self, stream_name: str = "Verona", topic: str = "standup") -> dict[str, Any]:
        return {
            "type": "stream",
            "stream_id": self.get_stream_id(stream_name),
            "topic": topic,
        }

    def _direct_destination(self, user_ids: list[int]) -> dict[str, Any]:
        return {"type": "direct", "user_ids": user_ids}

    def _post(self, payload: dict[str, Any]) -> Any:
        return self.client_post("/json/recurring_scheduled_messages", payload)

    def _make_weekly_payload(
        self,
        content: str = "Standup reminder",
        stream_name: str = "Verona",
        topic: str = "standup",
    ) -> dict[str, Any]:
        return {
            "content": content,
            "destinations": orjson.dumps([self._stream_destination(stream_name, topic)]).decode(),
            "recurrence_type": "weekly",
            "recurrence_days": orjson.dumps([0, 2, 4]).decode(),
            "scheduled_time": "09:00",
        }

    def _make_monthly_calendar_day_payload(
        self,
        day: int = 15,
        stream_name: str = "Verona",
        topic: str = "standup",
    ) -> dict[str, Any]:
        return {
            "content": "Monthly calendar day message",
            "destinations": orjson.dumps([self._stream_destination(stream_name, topic)]).decode(),
            "recurrence_type": "monthly",
            "recurrence_days": orjson.dumps({"type": "calendar_day", "day": day}).decode(),
            "scheduled_time": "09:00",
        }

    def _make_monthly_ordinal_weekday_payload(
        self,
        ordinal: int = 1,
        weekday: int = 0,
        stream_name: str = "Verona",
        topic: str = "standup",
    ) -> dict[str, Any]:
        return {
            "content": "Monthly ordinal weekday message",
            "destinations": orjson.dumps([self._stream_destination(stream_name, topic)]).decode(),
            "recurrence_type": "monthly",
            "recurrence_days": orjson.dumps(
                {"type": "ordinal_weekday", "ordinal": ordinal, "weekday": weekday}
            ).decode(),
            "scheduled_time": "09:00",
        }

    def _make_one_time_payload(
        self,
        content: str = "One-time message",
        user_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        ids = user_ids if user_ids is not None else [hamlet.id, othello.id]
        return {
            "content": content,
            "destinations": orjson.dumps([self._direct_destination(ids)]).decode(),
            "recurrence_type": "one_time",
            "recurrence_days": orjson.dumps([]).decode(),
            "scheduled_time": "09:00",
            "scheduled_delivery_timestamp": int(time_module.time()) + 86400,
        }

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def test_get_returns_empty_list_when_no_jobs(self) -> None:
        self.login("hamlet")
        result = self.client_get("/json/recurring_scheduled_messages")
        data = self.assert_json_success(result)
        self.assert_length(data["recurring_scheduled_messages"], 0)

    def test_get_returns_only_own_jobs(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Create a job for hamlet.
        do_create_recurring_scheduled_message(
            sender=hamlet,
            content="Hamlet's job",
            destinations=[self._stream_destination()],
            recurrence_type=RecurringScheduledMessage.DAILY,
            recurrence_days=[],
            scheduled_time=time(9, 0),
        )

        # Hamlet sees his own job.
        self.login_user(hamlet)
        result = self.client_get("/json/recurring_scheduled_messages")
        data = self.assert_json_success(result)
        self.assert_length(data["recurring_scheduled_messages"], 1)

        # Othello sees nothing.
        self.login_user(othello)
        result = self.client_get("/json/recurring_scheduled_messages")
        data = self.assert_json_success(result)
        self.assert_length(data["recurring_scheduled_messages"], 0)

    def test_get_excludes_inactive_jobs(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        result = self._post(self._make_weekly_payload())
        job_id = self.assert_json_success(result)["recurring_scheduled_message_id"]

        do_cancel_recurring_scheduled_message(job_id, hamlet)

        result = self.client_get("/json/recurring_scheduled_messages")
        data = self.assert_json_success(result)
        self.assert_length(data["recurring_scheduled_messages"], 0)

    # ------------------------------------------------------------------
    # POST — successful creation
    # ------------------------------------------------------------------

    def test_create_weekly_stream_job(self) -> None:
        self.login("hamlet")
        result = self._post(self._make_weekly_payload())
        data = self.assert_json_success(result)
        self.assertIn("recurring_scheduled_message_id", data)

        jobs = self.client_get("/json/recurring_scheduled_messages")
        self.assert_length(self.assert_json_success(jobs)["recurring_scheduled_messages"], 1)

    def test_create_daily_stream_job(self) -> None:
        self.login("hamlet")
        payload = {
            "content": "Daily reminder",
            "destinations": orjson.dumps([self._stream_destination()]).decode(),
            "recurrence_type": "daily",
            "recurrence_days": orjson.dumps([]).decode(),
            "scheduled_time": "08:00",
        }
        result = self._post(payload)
        self.assert_json_success(result)

    def test_create_one_time_direct_job(self) -> None:
        self.login("hamlet")
        result = self._post(self._make_one_time_payload())
        self.assert_json_success(result)

    def test_create_batch_job_multiple_destinations(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        self.login_user(hamlet)

        payload = {
            "content": "Batch message",
            "destinations": orjson.dumps([
                self._stream_destination("Verona", "general"),
                self._stream_destination("Denmark", "announcements"),
                self._direct_destination([hamlet.id, othello.id]),
            ]).decode(),
            "recurrence_type": "weekly",
            "recurrence_days": orjson.dumps([0]).decode(),
            "scheduled_time": "09:00",
        }
        result = self._post(payload)
        data = self.assert_json_success(result)

        job = RecurringScheduledMessage.objects.get(id=data["recurring_scheduled_message_id"])
        self.assert_length(job.destinations, 3)

    def test_create_specific_days_job(self) -> None:
        self.login("hamlet")
        payload = {
            "content": "Mon/Wed/Fri message",
            "destinations": orjson.dumps([self._stream_destination()]).decode(),
            "recurrence_type": "specific_days",
            "recurrence_days": orjson.dumps([0, 2, 4]).decode(),
            "scheduled_time": "09:00",
        }
        result = self._post(payload)
        self.assert_json_success(result)

    # ------------------------------------------------------------------
    # POST — validation errors
    # ------------------------------------------------------------------

    def test_create_requires_content(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload()
        del payload["content"]
        result = self._post(payload)
        self.assert_json_error(result, "Missing 'content' argument", status_code=400)

    def test_create_rejects_empty_content(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload(content="   ")
        result = self._post(payload)
        self.assert_json_error(result, "content cannot be blank", status_code=400)

    def test_create_rejects_empty_destinations(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload()
        payload["destinations"] = orjson.dumps([]).decode()
        result = self._post(payload)
        self.assert_json_error(result, "destinations must not be empty.", status_code=400)

    def test_create_rejects_invalid_destination_type(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload()
        payload["destinations"] = orjson.dumps([{"type": "unknown"}]).decode()
        result = self._post(payload)
        self.assert_json_error(
            result, "Each destination must have type 'stream' or 'direct'.", status_code=400
        )

    def test_create_rejects_stream_destination_missing_stream_id(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload()
        payload["destinations"] = orjson.dumps([{"type": "stream", "topic": "standup"}]).decode()
        result = self._post(payload)
        self.assert_json_error(
            result,
            "Each stream destination must include an integer stream_id.",
            status_code=400,
        )

    def test_create_rejects_stream_destination_missing_topic(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload()
        payload["destinations"] = orjson.dumps(
            [{"type": "stream", "stream_id": self.get_stream_id("Verona")}]
        ).decode()
        result = self._post(payload)
        self.assert_json_error(
            result,
            "Each stream destination must include a non-empty topic.",
            status_code=400,
        )

    def test_create_rejects_direct_destination_missing_user_ids(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload()
        payload["destinations"] = orjson.dumps([{"type": "direct", "user_ids": []}]).decode()
        result = self._post(payload)
        self.assert_json_error(
            result,
            "Each direct destination must include a non-empty user_ids list.",
            status_code=400,
        )

    def test_create_rejects_invalid_recurrence_type(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload()
        payload["recurrence_type"] = "quarterly"
        result = self._post(payload)
        self.assert_json_error(
            result,
            "Invalid recurrence_type: Value error, Not in the list of possible values",
            status_code=400,
        )

    def test_create_rejects_weekly_without_recurrence_days(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload()
        payload["recurrence_days"] = orjson.dumps([]).decode()
        result = self._post(payload)
        self.assert_json_error(
            result,
            "recurrence_days is required for weekly and specific_days recurrence types.",
            status_code=400,
        )

    def test_create_rejects_recurrence_days_out_of_range(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload()
        payload["recurrence_days"] = orjson.dumps([0, 7]).decode()  # 7 is invalid
        result = self._post(payload)
        self.assert_json_error(
            result,
            "recurrence_days must be integers between 0 (Monday) and 6 (Sunday).",
            status_code=400,
        )

    def test_create_rejects_invalid_scheduled_time_format(self) -> None:
        self.login("hamlet")
        payload = self._make_weekly_payload()
        payload["scheduled_time"] = "9am"
        result = self._post(payload)
        self.assert_json_error(
            result, "Invalid scheduled_time format. Expected HH:MM in UTC.", status_code=400
        )

    def test_create_one_time_requires_timestamp(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        payload = {
            "content": "One-time message",
            "destinations": orjson.dumps(
                [self._direct_destination([hamlet.id, othello.id])]
            ).decode(),
            "recurrence_type": "one_time",
            "recurrence_days": orjson.dumps([]).decode(),
            "scheduled_time": "09:00",
            # no scheduled_delivery_timestamp
        }
        result = self._post(payload)
        self.assert_json_error(
            result,
            "scheduled_delivery_timestamp is required for one-time scheduled messages.",
            status_code=400,
        )

    def test_create_one_time_rejects_past_timestamp(self) -> None:
        self.login("hamlet")
        payload = self._make_one_time_payload()
        payload["scheduled_delivery_timestamp"] = int(time_module.time()) - 3600  # 1 hour ago
        result = self._post(payload)
        self.assert_json_error(result, "Scheduled delivery time must be in the future.", status_code=400)

    # ------------------------------------------------------------------
    # DELETE (cancel)
    # ------------------------------------------------------------------

    def test_cancel_own_job(self) -> None:
        self.login("hamlet")
        result = self._post(self._make_weekly_payload())
        job_id = self.assert_json_success(result)["recurring_scheduled_message_id"]

        result = self.client_delete(f"/json/recurring_scheduled_messages/{job_id}")
        self.assert_json_success(result)

        job = RecurringScheduledMessage.objects.get(id=job_id)
        self.assertFalse(job.is_active)

    def test_cancel_removes_job_from_list(self) -> None:
        self.login("hamlet")
        result = self._post(self._make_weekly_payload())
        job_id = self.assert_json_success(result)["recurring_scheduled_message_id"]

        self.client_delete(f"/json/recurring_scheduled_messages/{job_id}")

        result = self.client_get("/json/recurring_scheduled_messages")
        data = self.assert_json_success(result)
        self.assert_length(data["recurring_scheduled_messages"], 0)

    def test_cancel_another_users_job_returns_404(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        result = self._post(self._make_weekly_payload())
        job_id = self.assert_json_success(result)["recurring_scheduled_message_id"]

        # Othello tries to cancel hamlet's job.
        self.login("othello")
        result = self.client_delete(f"/json/recurring_scheduled_messages/{job_id}")
        self.assert_json_error(
            result, "Recurring scheduled message does not exist.", status_code=404
        )

    def test_cancel_nonexistent_job_returns_404(self) -> None:
        self.login("hamlet")
        result = self.client_delete("/json/recurring_scheduled_messages/999999")
        self.assert_json_error(
            result, "Recurring scheduled message does not exist.", status_code=404
        )

    # ------------------------------------------------------------------
    # POST — monthly creation
    # ------------------------------------------------------------------

    def test_create_monthly_calendar_day_job(self) -> None:
        self.login("hamlet")
        result = self._post(self._make_monthly_calendar_day_payload(day=15))
        data = self.assert_json_success(result)

        job = RecurringScheduledMessage.objects.get(id=data["recurring_scheduled_message_id"])
        self.assertEqual(job.recurrence_type, RecurringScheduledMessage.MONTHLY)
        self.assertEqual(job.recurrence_days, {"type": "calendar_day", "day": 15})

    def test_create_monthly_last_day_job(self) -> None:
        self.login("hamlet")
        result = self._post(self._make_monthly_calendar_day_payload(day=-1))
        data = self.assert_json_success(result)

        job = RecurringScheduledMessage.objects.get(id=data["recurring_scheduled_message_id"])
        self.assertEqual(job.recurrence_days, {"type": "calendar_day", "day": -1})

    def test_create_monthly_ordinal_weekday_job(self) -> None:
        # "First Monday of the month"
        self.login("hamlet")
        result = self._post(self._make_monthly_ordinal_weekday_payload(ordinal=1, weekday=0))
        data = self.assert_json_success(result)

        job = RecurringScheduledMessage.objects.get(id=data["recurring_scheduled_message_id"])
        self.assertEqual(job.recurrence_type, RecurringScheduledMessage.MONTHLY)
        self.assertEqual(
            job.recurrence_days, {"type": "ordinal_weekday", "ordinal": 1, "weekday": 0}
        )

    def test_create_monthly_last_weekday_job(self) -> None:
        # "Last Friday of the month"
        self.login("hamlet")
        result = self._post(self._make_monthly_ordinal_weekday_payload(ordinal=-1, weekday=4))
        data = self.assert_json_success(result)

        job = RecurringScheduledMessage.objects.get(id=data["recurring_scheduled_message_id"])
        self.assertEqual(
            job.recurrence_days, {"type": "ordinal_weekday", "ordinal": -1, "weekday": 4}
        )

    # ------------------------------------------------------------------
    # POST — monthly validation errors
    # ------------------------------------------------------------------

    def test_create_monthly_rejects_list_for_recurrence_days(self) -> None:
        self.login("hamlet")
        payload = self._make_monthly_calendar_day_payload()
        payload["recurrence_days"] = orjson.dumps([0, 2, 4]).decode()
        result = self._post(payload)
        self.assert_json_error(
            result, "monthly recurrence_days must be a dict.", status_code=400
        )

    def test_create_monthly_rejects_unknown_rule_type(self) -> None:
        self.login("hamlet")
        payload = self._make_monthly_calendar_day_payload()
        payload["recurrence_days"] = orjson.dumps({"type": "biweekly"}).decode()
        result = self._post(payload)
        self.assert_json_error(
            result,
            "monthly recurrence_days must have type 'calendar_day' or 'ordinal_weekday', "
            "got 'biweekly'.",
            status_code=400,
        )

    def test_create_monthly_rejects_out_of_range_calendar_day(self) -> None:
        self.login("hamlet")
        payload = self._make_monthly_calendar_day_payload()
        payload["recurrence_days"] = orjson.dumps({"type": "calendar_day", "day": 32}).decode()
        result = self._post(payload)
        self.assert_json_error(
            result,
            "calendar_day rule requires 'day' as an integer 1\u201331 or -1 for last day.",
            status_code=400,
        )

    def test_create_monthly_rejects_invalid_ordinal(self) -> None:
        self.login("hamlet")
        payload = self._make_monthly_ordinal_weekday_payload()
        payload["recurrence_days"] = orjson.dumps(
            {"type": "ordinal_weekday", "ordinal": 5, "weekday": 0}
        ).decode()
        result = self._post(payload)
        self.assert_json_error(
            result,
            "ordinal_weekday rule requires 'ordinal' as 1\u20134 or -1 for last.",
            status_code=400,
        )

    def test_create_monthly_rejects_invalid_weekday(self) -> None:
        self.login("hamlet")
        payload = self._make_monthly_ordinal_weekday_payload()
        payload["recurrence_days"] = orjson.dumps(
            {"type": "ordinal_weekday", "ordinal": 1, "weekday": 7}
        ).decode()
        result = self._post(payload)
        self.assert_json_error(
            result,
            "ordinal_weekday rule requires 'weekday' as an integer "
            "0 (Monday) \u2013 6 (Sunday).",
            status_code=400,
        )


# ---------------------------------------------------------------------------
# Delivery tests
# ---------------------------------------------------------------------------


class RecurringScheduledMessageDeliveryTest(ZulipTestCase):
    def _make_stream_job(
        self,
        sender_name: str = "hamlet",
        stream_name: str = "Verona",
        topic: str = "test",
        recurrence_type: str = RecurringScheduledMessage.DAILY,
        recurrence_days: list[int] | None = None,
        overdue: bool = True,
    ) -> RecurringScheduledMessage:
        sender = self.example_user(sender_name)
        stream_id = self.get_stream_id(stream_name)
        next_delivery = (
            timezone_now() - timedelta(seconds=1) if overdue else timezone_now() + timedelta(hours=1)
        )
        return RecurringScheduledMessage.objects.create(
            sender=sender,
            realm=sender.realm,
            content="Automated test message",
            destinations=[{"type": "stream", "stream_id": stream_id, "topic": topic}],
            recurrence_type=recurrence_type,
            recurrence_days=recurrence_days or [],
            scheduled_time=time(9, 0),
            next_delivery=next_delivery,
            is_active=True,
        )

    def test_one_time_job_deactivated_after_delivery(self) -> None:
        job = self._make_stream_job(recurrence_type=RecurringScheduledMessage.ONE_TIME)
        do_deliver_recurring_scheduled_message(job)
        job.refresh_from_db()
        self.assertFalse(job.is_active)

    def test_daily_job_advances_next_delivery(self) -> None:
        job = self._make_stream_job(recurrence_type=RecurringScheduledMessage.DAILY)
        original_next = job.next_delivery
        do_deliver_recurring_scheduled_message(job)
        job.refresh_from_db()
        self.assertTrue(job.is_active)
        self.assertGreater(job.next_delivery, original_next)

    def test_delivery_sends_message_to_stream(self) -> None:
        hamlet = self.example_user("hamlet")
        job = self._make_stream_job(sender_name="hamlet", stream_name="Verona", topic="test")
        before_count = hamlet.realm.message_set.count()
        do_deliver_recurring_scheduled_message(job)
        after_count = hamlet.realm.message_set.count()
        self.assertGreater(after_count, before_count)

    def test_delivery_skips_failed_destination_continues_others(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        verona_id = self.get_stream_id("Verona")

        job = RecurringScheduledMessage.objects.create(
            sender=hamlet,
            realm=hamlet.realm,
            content="Batch test",
            destinations=[
                {"type": "stream", "stream_id": 999999, "topic": "bad"},  # non-existent stream
                {"type": "stream", "stream_id": verona_id, "topic": "good"},
            ],
            recurrence_type=RecurringScheduledMessage.DAILY,
            recurrence_days=[],
            scheduled_time=time(9, 0),
            next_delivery=timezone_now() - timedelta(seconds=1),
            is_active=True,
        )

        before_count = hamlet.realm.message_set.count()
        do_deliver_recurring_scheduled_message(job)
        after_count = hamlet.realm.message_set.count()

        # The good destination still sent despite the bad one failing.
        self.assertGreater(after_count, before_count)
        # Job is still active and rescheduled.
        job.refresh_from_db()
        self.assertTrue(job.is_active)

    def test_deactivated_realm_deactivates_job(self) -> None:
        job = self._make_stream_job()
        job.realm.deactivated = True
        job.realm.save()

        with self.assertRaises(Exception):
            do_deliver_recurring_scheduled_message(job)

        job.refresh_from_db()
        self.assertFalse(job.is_active)

        # Restore realm so other tests are not affected.
        job.realm.deactivated = False
        job.realm.save()

    def test_deactivated_sender_deactivates_job(self) -> None:
        hamlet = self.example_user("hamlet")
        job = self._make_stream_job(sender_name="hamlet")
        change_user_is_active(hamlet, False)

        # Refresh the job to clear the cached sender relation; otherwise
        # job.sender still reflects the pre-deactivation in-memory state.
        job.refresh_from_db()

        with self.assertRaises(Exception):
            do_deliver_recurring_scheduled_message(job)

        job.refresh_from_db()
        self.assertFalse(job.is_active)

        # Restore user.
        change_user_is_active(hamlet, True)

    def test_worker_skips_future_jobs(self) -> None:
        self._make_stream_job(overdue=False)
        result = try_deliver_one_recurring_scheduled_message()
        self.assertFalse(result)

    def test_worker_returns_true_when_job_due(self) -> None:
        self._make_stream_job(overdue=True)
        result = try_deliver_one_recurring_scheduled_message()
        self.assertTrue(result)
