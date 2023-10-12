from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.actions.reminders import check_reminders_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.validator import check_int
from zerver.models import UserProfile


@has_request_variables
def create_reminders_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int = REQ(json_validator=check_int),
    scheduled_delivery_timestamp: int = REQ(json_validator=check_int),
) -> HttpResponse:
    deliver_at = timestamp_to_datetime(scheduled_delivery_timestamp)
    if deliver_at <= timezone_now():
        raise JsonableError(_("Scheduled delivery time for reminder must be in the future."))

    client = RequestNotes.get_notes(request).client
    assert client is not None

    reminder_id = check_reminders_message(
        user_profile,
        client,
        message_id,
        deliver_at,
    )
    return json_success(request, data={"reminder_id": reminder_id})
