from django.http import HttpRequest, HttpResponse

from zerver.actions.scheduled_messages import delete_scheduled_message
from zerver.lib.request import has_request_variables
from zerver.lib.response import json_success
from zerver.models import ScheduledMessage, UserProfile


@has_request_variables
def fetch_scheduled_messages(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    scheduled_messages = ScheduledMessage.objects.filter(
        sender=user_profile, delivered=False, delivery_type=ScheduledMessage.SEND_LATER
    ).order_by("scheduled_timestamp")
    scheduled_message_dicts = [
        scheduled_message.to_dict() for scheduled_message in scheduled_messages
    ]
    return json_success(request, data={"scheduled_messages": scheduled_message_dicts})


@has_request_variables
def delete_scheduled_messages(
    request: HttpRequest, user_profile: UserProfile, scheduled_message_id: int
) -> HttpResponse:
    delete_scheduled_message(user_profile, scheduled_message_id)
    return json_success(request)
