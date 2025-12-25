# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import OptionalUserSpecifiedTopicStr, check_send_webhook_message
from zerver.models import UserProfile

# Event type mappings for Anytype objects
EVENT_TYPE_MAPPING = {
    "object.created": "created",
    "object.updated": "updated", 
    "object.deleted": "deleted",
    "object.archived": "archived",
    "object.restored": "restored",
}

# Object type emojis for better visual representation
OBJECT_TYPE_EMOJIS = {
    "note": "📝",
    "page": "📄", 
    "task": "✅",
    "project": "📁",
    "contact": "👤",
    "bookmark": "🔖",
    "file": "📎",
    "image": "🖼️",
    "default": "📋",
}


def get_object_event_message(payload: WildValue, event_type: str) -> str:
    """Generate message for Anytype object events."""
    action = EVENT_TYPE_MAPPING.get(event_type, event_type)
    
    # Extract object details
    object_data = payload.get("object", payload)
    object_type = object_data.get("type", "object").tame(check_string)
    object_title = object_data.get("title", object_data.get("name", "Untitled")).tame(check_string)
    object_id = object_data.get("id", "").tame(check_string)
    
    # Get appropriate emoji
    emoji = OBJECT_TYPE_EMOJIS.get(object_type.lower(), OBJECT_TYPE_EMOJIS["default"])
    
    # Build base message
    if action == "created":
        message = f"{emoji} New **{object_type}** created: **{object_title}**"
    elif action == "updated":
        message = f"✏️ **{object_type}** updated: **{object_title}**"
    elif action == "deleted":
        message = f"🗑️ **{object_type}** deleted: **{object_title}**"
    elif action == "archived":
        message = f"📦 **{object_type}** archived: **{object_title}**"
    elif action == "restored":
        message = f"♻️ **{object_type}** restored: **{object_title}**"
    else:
        message = f"{emoji} **{object_type}** {action}: **{object_title}**"
    
    # Add description for created objects
    if action == "created":
        description = object_data.get("description")
        if description:
            desc_text = description.tame(check_string)
            if desc_text.strip():
                message += f"\n\n> {desc_text[:200]}{'...' if len(desc_text) > 200 else ''}"
    
    # Add optional details
    details = []
    
    # Add space information if available
    space_name = payload.get("space", {}).get("name")
    if space_name:
        space_name_str = space_name.tame(check_string)
        if space_name_str.strip():
            details.append(f"Space: {space_name_str}")
    
    # Add user information if available  
    user_name = payload.get("user", {}).get("name")
    if user_name:
        user_name_str = user_name.tame(check_string)
        if user_name_str.strip():
            details.append(f"by {user_name_str}")
    
    # Add details if any
    if details:
        message += f"\n*{' '.join(details)}*"
    
    return message


def get_topic_name(payload: WildValue, event_type: str) -> str:
    """Generate topic name for the message."""
    # Try to get space name first
    space_name = payload.get("space", {}).get("name")
    if space_name:
        return space_name.tame(check_string)
    
    # Fall back to object type
    object_data = payload.get("object", payload)
    object_type = object_data.get("type", "Anytype").tame(check_string)
    return object_type.title()


@webhook_view("Anytype")
@typed_endpoint
def api_anytype_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    """
    Handle Anytype webhook events.
    
    Supports a generic payload format that can work with:
    - Future native Anytype webhooks
    - Custom webhook bridges/middleware
    - Third-party automation tools (Zapier, Make.com)
    """
    
    # Extract event type
    event_type = payload.get("event", payload.get("type", "object.updated")).tame(check_string)
    
    # Validate event type
    if not event_type.startswith("object."):
        raise UnsupportedWebhookEventTypeError(event_type)
    
    # Generate message content
    body = get_object_event_message(payload, event_type)
    
    # Generate topic name
    if topic is None:
        topic = get_topic_name(payload, event_type)
    
    # Send the message
    check_send_webhook_message(request, user_profile, topic, body)
    
    return json_success(request)