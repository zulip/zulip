from django.http import HttpRequest, HttpResponse
from zerver.lib.scheduled_messages import do_create_scheduled_messages
from zerver.models import Draft, ScheduledMessage, UserProfile
from zerver.lib.response import json_success
from zerver.lib.request import REQ, has_request_variables
from typing import Any, Dict, List
from zerver.lib.validator import check_anything, check_dict, check_list, check_string, check_union, check_int, check_float
from zerver.lib.drafts import (
    do_create_drafts,
    do_delete_draft,
    do_edit_draft,
    draft_dict_validator,
    draft_endpoint,
)

def fetch_scheduled_messages(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    user_scheduled_messages = ScheduledMessage.objects.filter(sender=user_profile)
    print(user_scheduled_messages)
    scheduled_messages_dicts = [scheduled_message.to_dict() for scheduled_message in user_scheduled_messages]
    
    return json_success(request, data={"count": user_scheduled_messages.count(), "scheduled_messages": scheduled_messages_dicts})
  
@has_request_variables
def create_scheduled_messages(
    request: HttpRequest,
    user_profile: UserProfile,
    scheduled_messages: List[Dict[str, Any]] = REQ(
        json_validator=check_list(check_dict([("type", check_string), ("deliver_at", check_anything)]))
    ),
) -> HttpResponse:
    print("in create_scheduled_messages")
    print("scheduled_messages_dicts: ")
    print(scheduled_messages)
    created_scheduled_message_objects = do_create_scheduled_messages(scheduled_messages, user_profile)
    scheduled_messages_ids = [scheduled_message_object.id for scheduled_message_object in created_scheduled_message_objects]
    return json_success(request, data={"ids": scheduled_messages_ids})