from datetime import time
from typing import Annotated, Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import Json, NonNegativeInt, StringConstraints

from zerver.actions.recurring_scheduled_messages import (
    do_cancel_recurring_scheduled_message,
    do_create_recurring_scheduled_message,
    do_get_recurring_scheduled_messages,
)
from zerver.lib.exceptions import DeliveryTimeNotInFutureError, JsonableError
from zerver.lib.recurring_scheduled_messages import validate_monthly_rule
from zerver.lib.response import json_success
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.lib.typed_endpoint_validators import check_string_in_validator
from zerver.models import UserProfile
from zerver.models.recurring_scheduled_messages import RecurringScheduledMessage

VALID_RECURRENCE_TYPES = [
    RecurringScheduledMessage.ONE_TIME,
    RecurringScheduledMessage.DAILY,
    RecurringScheduledMessage.WEEKLY,
    RecurringScheduledMessage.SPECIFIC_DAYS,
    RecurringScheduledMessage.MONTHLY,
]


def _parse_scheduled_time(scheduled_time_str: str) -> time:
    """Parse a "HH:MM" UTC string into a time object."""
    try:
        parts = scheduled_time_str.split(":")
        if len(parts) != 2:
            raise ValueError
        hour, minute = int(parts[0]), int(parts[1])
        return time(hour, minute)
    except (ValueError, AttributeError):
        raise JsonableError(_("Invalid scheduled_time format. Expected HH:MM in UTC."))


def _validate_destinations(destinations: list[dict[str, Any]]) -> None:
    """Validate that every entry in destinations is a well-formed stream or direct destination."""
    if not destinations:
        raise JsonableError(_("destinations must not be empty."))

    for dest in destinations:
        dest_type = dest.get("type")

        if dest_type == "stream":
            if not isinstance(dest.get("stream_id"), int):
                raise JsonableError(_("Each stream destination must include an integer stream_id."))
            if not isinstance(dest.get("topic"), str) or not dest["topic"].strip():
                raise JsonableError(_("Each stream destination must include a non-empty topic."))

        elif dest_type == "direct":
            user_ids = dest.get("user_ids")
            if not isinstance(user_ids, list) or not user_ids:
                raise JsonableError(
                    _("Each direct destination must include a non-empty user_ids list.")
                )
            if not all(isinstance(uid, int) for uid in user_ids):
                raise JsonableError(_("user_ids must be a list of integers."))

        else:
            raise JsonableError(
                _("Each destination must have type 'stream' or 'direct'.")
            )


def _validate_recurrence_days(
    recurrence_days: list[int] | dict[str, str | int], recurrence_type: str
) -> None:
    """Validate the recurrence_days value for the given recurrence_type."""
    if recurrence_type in (
        RecurringScheduledMessage.ONE_TIME,
        RecurringScheduledMessage.DAILY,
    ):
        if recurrence_days:
            raise JsonableError(
                _("recurrence_days must be empty for one_time and daily recurrence types.")
            )

    elif recurrence_type in (
        RecurringScheduledMessage.WEEKLY,
        RecurringScheduledMessage.SPECIFIC_DAYS,
    ):
        if not isinstance(recurrence_days, list) or not recurrence_days:
            raise JsonableError(
                _("recurrence_days is required for weekly and specific_days recurrence types.")
            )
        if not all(isinstance(d, int) and 0 <= d <= 6 for d in recurrence_days):
            raise JsonableError(
                _("recurrence_days must be integers between 0 (Monday) and 6 (Sunday).")
            )

    elif recurrence_type == RecurringScheduledMessage.MONTHLY:
        try:
            validate_monthly_rule(recurrence_days)
        except ValueError as e:
            raise JsonableError(_(str(e))) from e


def get_recurring_scheduled_messages(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    return json_success(
        request,
        data={"recurring_scheduled_messages": do_get_recurring_scheduled_messages(user_profile)},
    )


@typed_endpoint
def create_recurring_scheduled_message(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    content: Annotated[
        str,
        StringConstraints(
            min_length=1, max_length=settings.MAX_MESSAGE_LENGTH, strip_whitespace=True
        ),
    ],
    destinations: Json[list[dict[str, Any]]],
    recurrence_type: Annotated[
        str, check_string_in_validator(VALID_RECURRENCE_TYPES)
    ],
    recurrence_days: Json[list[int] | dict[str, str | int]] = [],
    scheduled_time: str = "00:00",
    scheduled_delivery_timestamp: Json[int] | None = None,
) -> HttpResponse:
    _validate_destinations(destinations)
    _validate_recurrence_days(recurrence_days, recurrence_type)

    parsed_time = _parse_scheduled_time(scheduled_time)

    deliver_at = None
    if recurrence_type == RecurringScheduledMessage.ONE_TIME:
        if scheduled_delivery_timestamp is None:
            raise JsonableError(
                _("scheduled_delivery_timestamp is required for one-time scheduled messages.")
            )
        deliver_at = timestamp_to_datetime(scheduled_delivery_timestamp)
        if deliver_at <= timezone_now():
            raise DeliveryTimeNotInFutureError

    job = do_create_recurring_scheduled_message(
        sender=user_profile,
        content=content,
        destinations=destinations,
        recurrence_type=recurrence_type,
        recurrence_days=recurrence_days,
        scheduled_time=parsed_time,
        deliver_at=deliver_at,
    )
    return json_success(request, data={"recurring_scheduled_message_id": job.id})


@typed_endpoint
def cancel_recurring_scheduled_message(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    recurring_scheduled_message_id: PathOnly[NonNegativeInt],
) -> HttpResponse:
    do_cancel_recurring_scheduled_message(recurring_scheduled_message_id, user_profile)
    return json_success(request)
