from django.http import HttpRequest, HttpResponse

from zerver.actions.scheduled_messages import delete_scheduled_message
from zerver.lib.request import has_request_variables
from zerver.lib.response import json_success
from zerver.lib.scheduled_messages import get_all_scheduled_messages
from zerver.models import UserProfile


@has_request_variables
def fetch_scheduled_messages(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request, data={"scheduled_messages": get_all_scheduled_messages(user_profile)}
    )


@has_request_variables
def delete_scheduled_messages(
    request: HttpRequest, user_profile: UserProfile, scheduled_message_id: int
) -> HttpResponse:
    delete_scheduled_message(user_profile, scheduled_message_id)
    return json_success(request)
