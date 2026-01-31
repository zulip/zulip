from collections.abc import Callable
from typing import Any

import requests
from django.http import HttpRequest
from django.http.response import HttpResponse
from pydantic import Json

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_dict, check_list, check_none_or, check_string
from zerver.lib.webhooks.common import OptionalUserSpecifiedTopicStr, check_send_webhook_message
from zerver.models import UserProfile

# Message templates: (author_template, no_author_template)
ENTITY_CREATED_TEMPLATE = (
    "**{author}** created {entity_type} **{entity}**",
    "New {entity_type} **{entity}** was created",
)
ENTITY_UPDATED_TEMPLATE = (
    "**{author}** updated {entity_type} **{entity}'s**{suffix}",
    "{entity_type} **{entity}'s**{suffix} was updated",
)
ENTITY_DELETED_TEMPLATE = (
    "**{author}** moved {entity_type} **{entity}** to trash",
    "{entity_type} **{entity}** was moved to trash",
)
ENTITY_UNDELETED_TEMPLATE = (
    "**{author}** restored {entity_type} **{entity}** from trash",
    "{entity_type} **{entity}** was restored from trash",
)
ENTITY_MOVED_TEMPLATE = (
    "**{author}** moved {entity_type} **{entity}**",
    "{entity_type} **{entity}** was moved",
)
ENTITY_LOCKED_TEMPLATE = (
    "**{author}** locked {entity_type} **{entity}**",
    "{entity_type} **{entity}** was locked",
)
ENTITY_UNLOCKED_TEMPLATE = (
    "**{author}** unlocked {entity_type} **{entity}**",
    "{entity_type} **{entity}** was unlocked",
)

# Comment-specific templates: (author_template, no_author_template)
COMMENT_CREATED_TEMPLATE = (
    "**{author}** added a comment on {target}",
    "New comment added on {target}",
)
COMMENT_UPDATED_TEMPLATE = (
    "**{author}** updated a comment on {target}",
    "Comment updated on {target}",
)
COMMENT_DELETED_TEMPLATE = (
    "**{author}** deleted a comment on {target}",
    "Comment deleted on {target}",
)

# Entity type prefixes for topics
TOPIC_PREFIX_PAGE = "page"
TOPIC_PREFIX_DATABASE = "db"
TOPIC_PREFIX_DATA_SOURCE = "ds"

ENTITY_TYPES = ("page", "database", "data source", "comment")

NOTION_VERIFICATION_TOKEN_MESSAGE = """
This is a webhook configuration test message from Notion.

Your verification token is: `{token}`

Please copy this token and paste it into your Notion webhook configuration to complete the setup.
""".strip()


def get_notion_api_headers(notion_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json",
    }


def extract_page_title(page_data: dict[str, Any]) -> str:
    if not page_data or "properties" not in page_data:
        return "Untitled Page"

    properties = page_data.get("properties", {})

    # The title property can have various names - try common ones first
    for common_name in ["title", "Title", "Name", "name"]:
        if common_name in properties:
            prop_value = properties[common_name]
            if isinstance(prop_value, dict) and prop_value.get("type") == "title":
                title_content = prop_value.get("title", [])
                if title_content and isinstance(title_content, list) and len(title_content) > 0:
                    plain_text = title_content[0].get("plain_text")
                    if plain_text:
                        return plain_text

    # Fallback: iterate through all properties
    for prop_value in properties.values():
        if isinstance(prop_value, dict) and prop_value.get("type") == "title":
            title_content = prop_value.get("title", [])
            if title_content and isinstance(title_content, list) and len(title_content) > 0:
                plain_text = title_content[0].get("plain_text")
                if plain_text:
                    return plain_text

    return "Untitled Page"


def extract_datasource_title(datasource_data: dict[str, Any]) -> str:
    if not datasource_data:
        return "Untitled Data Source"

    # Database titles are in a simpler structure
    title_list = datasource_data.get("title", [])
    if title_list and isinstance(title_list, list):
        for title_obj in title_list:
            if isinstance(title_obj, dict):
                plain_text = title_obj.get("plain_text")
                if plain_text:
                    return plain_text

    return "Untitled Data Source"


def get_page_title(notion_token: str, page_id: str) -> str:
    if not notion_token:
        return "Unknown Page"

    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = get_notion_api_headers(notion_token)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return extract_page_title(response.json())
        return "Unknown Page"
    except Exception:
        return "Unknown Page"


def get_datasource_title(notion_token: str, datasource_id: str) -> str:
    if not notion_token:
        return "Unknown Data Source"

    url = f"https://api.notion.com/v1/data_sources/{datasource_id}"
    headers = get_notion_api_headers(notion_token)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return extract_datasource_title(response.json())
        return "Unknown Data Source"
    except Exception:
        return "Unknown Data Source"


def get_user_name(notion_token: str, user_id: str) -> str:
    if not notion_token:
        return "Unknown user"

    url = f"https://api.notion.com/v1/users/{user_id}"
    headers = get_notion_api_headers(notion_token)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            user_data = response.json()
            name = user_data.get("name")
            if name:
                return name

            if user_data.get("type") == "person":
                person = user_data.get("person", {})
                email = person.get("email", "")
                if email:
                    return email.split("@")[0].replace(".", " ").title()

            return "Unknown user"
        return "Unknown user"
    except Exception:
        return "Unknown user"


def get_author_name(payload: WildValue, notion_token: str) -> str:
    authors = payload.get("authors")
    if not authors:
        return ""

    authors_list = authors.tame(
        check_list(check_dict([("id", check_string), ("type", check_string)]))
    )

    first_author = authors_list[0]
    user_id = first_author.get("id")

    if not user_id or not isinstance(user_id, str):
        return ""

    author_name = get_user_name(notion_token, user_id)

    if len(authors_list) > 1:
        others_count = len(authors_list) - 1
        return f"{author_name} (+{others_count} other{'s' if others_count > 1 else ''})"

    return author_name


def format_message(
    template: tuple[str, str],
    author: str,
    entity: str,
    entity_type: str,
    suffix: str = "",
    content: str = "",
) -> str:
    if author:
        return template[0].format(
            author=author,
            entity=entity,
            entity_type=entity_type,
            suffix=suffix,
            content=content,
        )
    return template[1].format(
        entity=entity,
        entity_type=entity_type,
        suffix=suffix,
        content=content,
    )


def get_entity_event_message(
    payload: WildValue,
    notion_token: str,
    entity_type: str,
    topic_prefix: str,
    template: tuple[str, str],
    get_title_func: Callable[[str, str], str],
    suffix: str = "",
    fallback_topic: str = "Notion",
    fallback_message: str = "Entity was updated",
) -> tuple[str, str]:
    entity_id = payload["entity"]["id"].tame(check_string)
    if not entity_id:
        return (fallback_topic, fallback_message)

    entity_title = get_title_func(notion_token, entity_id)
    author = get_author_name(payload, notion_token)
    body = format_message(template, author, entity_title, entity_type, suffix)
    if entity_title.startswith("Unknown"):
        return (fallback_topic, body)
    return (f"{topic_prefix}: {entity_title}", body)


def get_comment_event_context(payload: WildValue, notion_token: str) -> tuple[str, str]:
    data = payload.get("data")
    parent = data.get("parent") if data else None
    parent_type = parent.get("type").tame(check_string) if parent else None
    topic_name = "Notion Comment"
    target_desc = "**Unknown Page**"
    if parent_type == "page":
        assert parent is not None
        page_id = parent.get("id").tame(check_string)
        entity_title = get_page_title(notion_token, page_id) if page_id else "Unknown Page"
        topic_name = f"{TOPIC_PREFIX_PAGE}: {entity_title}"
        target_desc = f"**{entity_title}**"
    elif parent_type == "block":
        assert parent is not None
        page_id = (data.get("page_id").tame(check_string) if data else None) or ""
        entity_title = get_page_title(notion_token, page_id) if page_id else "Unknown Page"
        topic_name = f"{TOPIC_PREFIX_PAGE}: {entity_title}"
        target_desc = f"a block in **{entity_title}**"

    return (topic_name, target_desc)


def format_comment_message(template: tuple[str, str], author: str, target: str) -> str:
    if author:
        return template[0].format(author=author, target=target)
    return template[1].format(target=target)


# Page event handlers
def get_page_created_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[0],
        TOPIC_PREFIX_PAGE,
        ENTITY_CREATED_TEMPLATE,
        get_page_title,
        fallback_topic="Notion Page",
        fallback_message="New page was created",
    )


def get_page_content_updated_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[0],
        TOPIC_PREFIX_PAGE,
        ENTITY_UPDATED_TEMPLATE,
        get_page_title,
        suffix=" content",
        fallback_topic="Notion Page",
        fallback_message="Page content was updated",
    )


def get_page_properties_updated_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[0],
        TOPIC_PREFIX_PAGE,
        ENTITY_UPDATED_TEMPLATE,
        get_page_title,
        suffix=" properties",
        fallback_topic="Notion Page",
        fallback_message="Page properties were updated",
    )


def get_page_deleted_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[0],
        TOPIC_PREFIX_PAGE,
        ENTITY_DELETED_TEMPLATE,
        get_page_title,
        fallback_topic="Notion Page",
        fallback_message="Page was moved to trash",
    )


def get_page_undeleted_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[0],
        TOPIC_PREFIX_PAGE,
        ENTITY_UNDELETED_TEMPLATE,
        get_page_title,
        fallback_topic="Notion Page",
        fallback_message="Page was restored from trash",
    )


def get_page_moved_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[0],
        TOPIC_PREFIX_PAGE,
        ENTITY_MOVED_TEMPLATE,
        get_page_title,
        fallback_topic="Notion Page",
        fallback_message="Page was moved",
    )


def get_page_locked_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[0],
        TOPIC_PREFIX_PAGE,
        ENTITY_LOCKED_TEMPLATE,
        get_page_title,
        fallback_topic="Notion Page",
        fallback_message="Page was locked",
    )


def get_page_unlocked_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[0],
        TOPIC_PREFIX_PAGE,
        ENTITY_UNLOCKED_TEMPLATE,
        get_page_title,
        fallback_topic="Notion Page",
        fallback_message="Page was unlocked",
    )


# Database event handlers
def get_database_created_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[1],
        TOPIC_PREFIX_DATABASE,
        ENTITY_CREATED_TEMPLATE,
        get_datasource_title,
        fallback_topic="Notion Database",
        fallback_message="New database was created",
    )


def get_database_content_updated_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[1],
        TOPIC_PREFIX_DATABASE,
        ENTITY_UPDATED_TEMPLATE,
        get_datasource_title,
        suffix=" content",
        fallback_topic="Notion Database",
        fallback_message="Database content was updated",
    )


def get_database_schema_updated_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[1],
        TOPIC_PREFIX_DATABASE,
        ENTITY_UPDATED_TEMPLATE,
        get_datasource_title,
        suffix=" schema",
        fallback_topic="Notion Database",
        fallback_message="Database schema was updated",
    )


def get_database_deleted_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[1],
        TOPIC_PREFIX_DATABASE,
        ENTITY_DELETED_TEMPLATE,
        get_datasource_title,
        fallback_topic="Notion Database",
        fallback_message="Database was moved to trash",
    )


def get_database_undeleted_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[1],
        TOPIC_PREFIX_DATABASE,
        ENTITY_UNDELETED_TEMPLATE,
        get_datasource_title,
        fallback_topic="Notion Database",
        fallback_message="Database was restored from trash",
    )


def get_database_moved_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[1],
        TOPIC_PREFIX_DATABASE,
        ENTITY_MOVED_TEMPLATE,
        get_datasource_title,
        fallback_topic="Notion Database",
        fallback_message="Database was moved",
    )


# Data source event handlers
def get_data_source_created_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[2],
        TOPIC_PREFIX_DATA_SOURCE,
        ENTITY_CREATED_TEMPLATE,
        get_datasource_title,
        fallback_topic="Notion Data Source",
        fallback_message="New data source was created",
    )


def get_data_source_content_updated_message(
    payload: WildValue, notion_token: str
) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[2],
        TOPIC_PREFIX_DATA_SOURCE,
        ENTITY_UPDATED_TEMPLATE,
        get_datasource_title,
        suffix=" content",
        fallback_topic="Notion Data Source",
        fallback_message="Data source content was updated",
    )


def get_data_source_schema_updated_message(
    payload: WildValue, notion_token: str
) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[2],
        TOPIC_PREFIX_DATA_SOURCE,
        ENTITY_UPDATED_TEMPLATE,
        get_datasource_title,
        suffix=" schema",
        fallback_topic="Notion Data Source",
        fallback_message="Data source schema was updated",
    )


def get_data_source_deleted_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[2],
        TOPIC_PREFIX_DATA_SOURCE,
        ENTITY_DELETED_TEMPLATE,
        get_datasource_title,
        fallback_topic="Notion Data Source",
        fallback_message="Data source was moved to trash",
    )


def get_data_source_undeleted_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[2],
        TOPIC_PREFIX_DATA_SOURCE,
        ENTITY_UNDELETED_TEMPLATE,
        get_datasource_title,
        fallback_topic="Notion Data Source",
        fallback_message="Data source was restored from trash",
    )


def get_data_source_moved_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    return get_entity_event_message(
        payload,
        notion_token,
        ENTITY_TYPES[2],
        TOPIC_PREFIX_DATA_SOURCE,
        ENTITY_MOVED_TEMPLATE,
        get_datasource_title,
        fallback_topic="Notion Data Source",
        fallback_message="Data source was moved",
    )


# Comment event handlers
def get_comment_created_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    topic_name, target_desc = get_comment_event_context(payload, notion_token)
    author = get_author_name(payload, notion_token)
    body = format_comment_message(COMMENT_CREATED_TEMPLATE, author, target_desc)
    return (topic_name, body)


def get_comment_updated_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    topic_name, target_desc = get_comment_event_context(payload, notion_token)
    author = get_author_name(payload, notion_token)
    body = format_comment_message(COMMENT_UPDATED_TEMPLATE, author, target_desc)
    return (topic_name, body)


def get_comment_deleted_message(payload: WildValue, notion_token: str) -> tuple[str, str]:
    topic_name, target_desc = get_comment_event_context(payload, notion_token)
    author = get_author_name(payload, notion_token)
    body = format_comment_message(COMMENT_DELETED_TEMPLATE, author, target_desc)
    return (topic_name, body)


# Event type to handler mapping
EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue, str], tuple[str, str]]] = {
    "page.content_updated": get_page_content_updated_message,
    "page.created": get_page_created_message,
    "page.deleted": get_page_deleted_message,
    "page.locked": get_page_locked_message,
    "page.moved": get_page_moved_message,
    "page.properties_updated": get_page_properties_updated_message,
    "page.undeleted": get_page_undeleted_message,
    "page.unlocked": get_page_unlocked_message,
    "database.content_updated": get_database_content_updated_message,
    "database.created": get_database_created_message,
    "database.deleted": get_database_deleted_message,
    "database.moved": get_database_moved_message,
    "database.schema_updated": get_database_schema_updated_message,
    "database.undeleted": get_database_undeleted_message,
    "data_source.content_updated": get_data_source_content_updated_message,
    "data_source.created": get_data_source_created_message,
    "data_source.deleted": get_data_source_deleted_message,
    "data_source.moved": get_data_source_moved_message,
    "data_source.schema_updated": get_data_source_schema_updated_message,
    "data_source.undeleted": get_data_source_undeleted_message,
    "comment.created": get_comment_created_message,
    "comment.updated": get_comment_updated_message,
    "comment.deleted": get_comment_deleted_message,
}

ALL_EVENT_TYPES = list(EVENT_TO_FUNCTION_MAPPER.keys())


def is_verification(payload: WildValue) -> bool:
    return payload.get("verification_token").tame(check_none_or(check_string)) is not None


def handle_verification_request(
    request: HttpRequest, user_profile: UserProfile, payload: WildValue
) -> HttpResponse:
    verification_token = payload["verification_token"].tame(check_string)
    body = NOTION_VERIFICATION_TOKEN_MESSAGE.format(token=verification_token)
    check_send_webhook_message(request, user_profile, "Notion Webhook Verification", body)
    return json_success(request)


@webhook_view("Notion", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_notion_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    notion_token: str = "",
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
    map_pages_to_topics: Json[bool] = False,
) -> HttpResponse:
    if is_verification(payload):
        return handle_verification_request(request, user_profile, payload)

    event_type = payload.get("type").tame(check_string)

    if event_type not in EVENT_TO_FUNCTION_MAPPER:
        raise UnsupportedWebhookEventTypeError(event_type)

    handler_function = EVENT_TO_FUNCTION_MAPPER[event_type]
    topic_name, body = handler_function(payload, notion_token)

    if user_specified_topic:
        topic_name = user_specified_topic
    elif not map_pages_to_topics or notion_token == "":
        topic_name = "Notion"

    check_send_webhook_message(
        request, user_profile, topic_name, body, complete_event_type=event_type
    )
    return json_success(request)
