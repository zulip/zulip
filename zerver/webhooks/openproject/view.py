import logging
from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string, check_dict
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile
from django.http import HttpRequest, JsonResponse, HttpResponse
import json
import hmac
import hashlib
from zproject.config import get_secret

def verify_signature(request,SHARED_SECRET):
    signature = request.headers.get("x-op-signature")
    if not signature or not signature.startswith("sha1="):
        return False
    
    received_signature = signature.split("=")[1]

    expected_signature = hmac.new(
        SHARED_SECRET.encode('utf-8'),  
        request.body,                  
        hashlib.sha1                   
    ).hexdigest()

    
    return hmac.compare_digest(received_signature, expected_signature)




@webhook_view("OpenProject")
@typed_endpoint
def api_openproject_webhook(    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    #comment out the verification line to test the webhook
    secret_key = get_secret("openproject") 
    if not verify_signature(request,secret_key):
        return JsonResponse({"error": "Invalid signature"}, status=401)
    event_type_raw = list(payload.values())[0]
    event_type = event_type_raw.tame(check_string).split(':')[1]

    heading = list(payload.keys())[1]

    data_raw = list(payload.values())[1]
    data = data_raw.tame(check_dict({}))
    _type = data.get("_type")
    if not event_type:
        return JsonResponse({"error": "Missing 'event_type'"}, status=400)
    if not data:
        return JsonResponse({"error": "Missing 'data'"}, status=400)
    if not heading:
        return JsonResponse({"error": "Missing 'heading'"}, status=400)
    
    message = ''
    topic = ''
    if heading == "project":
        topic = "Project"
        name = data.get("name")
        message = f"**Project** {name} got {event_type}"
    elif heading == "work_package":
        topic = "Work Package"
        subject = data.get("subject")
        message = f"**Work Package** {subject} of type {_type} got {event_type}"
    elif heading == "time_entry":
        topic = "Time Entry"
        hours = data.get("hours")
        message = f"**Time Entry** of {hours.split('T')[1]} got {event_type}"
    elif heading == "attachment":
        topic = "File Uploaded"
        filename = data.get("fileName") 
        message = f"**File Uploaded** of name {filename}"
    
    check_send_webhook_message(
        request,user_profile, topic, message
    )
    return json_success(request)
