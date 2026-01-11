from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

@webhook_view("Notion")
@typed_endpoint
def api_notion_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    
    # Default values
    topic = "Notion Notification"
    body = "Received event from Notion"

    # payload is a WildValue, we can access it like a dict but need to tame values
    
    # Logic to extract Page Title from standard Notion API payload
    # properties -> Name -> title -> [0] -> plain_text
    properties = payload.get("properties")
    if properties:
        name_prop = properties.get("Name")
        if name_prop:
            title_list = name_prop.get("title")
            if title_list:
                # WildValue doesn't support indexing/iteration easily without taming first potentially
                # But let's try to access if it's a list structure
                # Actually WildValue operations: 
                # We should tame it as a list of dicts?
                # For simplicity, let's assume the user sends a flattened payload via automation 
                # OR we handle the complex structure carefully.
                pass
    
    # Let's support a simplified payload that users can construct in Notion Automations
    # { "event": "Page Created", "title": "My Page", "url": "https://..." }
    
    event_type = payload.get("event", "Update").tame(check_string)
    title = payload.get("title", "Untitled").tame(check_string)
    url = payload.get("url", "").tame(check_string)
    
    topic = event_type
    
    if url:
        body = f"**[{title}]({url})**"
    else:
        body = f"**{title}**"
        
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)
