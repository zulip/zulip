from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from pydantic import Json, NonNegativeInt

from zerver.actions.reminders import do_delete_reminder, schedule_reminder_for_message
from zerver.lib.exceptions import DeliveryTimeNotInFutureError
from zerver.lib.reminders import access_reminder
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models import UserProfile


@typed_endpoint
def create_reminders_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: Json[int],
    scheduled_delivery_timestamp: Json[int],
) -> HttpResponse:
    deliver_at = timestamp_to_datetime(scheduled_delivery_timestamp)
    if deliver_at <= timezone_now():
        raise DeliveryTimeNotInFutureError

    client = RequestNotes.get_notes(request).client
    assert client is not None

    reminder_id = schedule_reminder_for_message(
        user_profile,
        client,
        message_id,
        deliver_at,
    )
    return json_success(request, data={"reminder_id": reminder_id})


@typed_endpoint
def delete_reminder(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    reminder_id: PathOnly[NonNegativeInt],
) -> HttpResponse:
    reminder = access_reminder(user_profile, reminder_id)
    do_delete_reminder(user_profile, reminder)
    return json_success(request)
