from collections.abc import Callable
from typing import Any

import requests
from django.http import HttpRequest
from django.http.response import HttpResponse
from pydantic import Json

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_dict, check_list, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ENTITY_TYPES = ("Page", "Datasource", "Comment", "Verification")

ENTITY_ACTION_TEMPLATE = (
    "{entity_type} **{entity_name}** was {action} by **{author_name}**",
    "{entity_type} **{entity_name}** was {action}",
    "{entity_type} was {action} by **{author_name}**",
    "{entity_type} was {action}",
)

ENTITY_UPDATED_TEMPLATE = (
    "**{author_name}** updated {entity_type} **{entity_name}'s** {suffix}",
    "{entity_type} **{entity_name}'s** {suffix} was updated",
    "**{author_name}** updated {entity_type}'s {suffix}",
    "{entity_type}'s {suffix} was updated",
)

ENTITY_PROPERTIES_UPDATED_TEMPLATE = (
    "**{author_name}** updated {entity_type} **{entity_name}**'s properties:\n{properties}",
    "{entity_type} **{entity_name}**'s properties were updated:\n{properties}",
    "**{author_name}** updated {entity_type}'s properties:\n{properties}",
    "{entity_type}'s properties were updated:\n{properties}",
)

NOTION_VERIFICATION_TOKEN_MESSAGE = """
This is a webhook configuration test message from Notion.

Your verification token is: `{token}`

Please copy this token and paste it into your Notion webhook configuration to complete the setup.
""".strip()


def get_entity_topic_name(entity_type: str, entity_name: str | None) -> str:
    if entity_name:
        return f"{entity_type.capitalize()}: {entity_name}"
    return entity_type.capitalize()


def get_notion_api_headers(notion_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json",
    }


def extract_page_title(page_data: dict[str, Any]) -> str:
    properties = page_data["properties"]

    for prop_value in properties.values():
        prop_type = prop_value["type"]
        if prop_type == "title":
            title_prop = prop_value[prop_type]
            if len(title_prop) > 0:
                plain_text = title_prop[0]["plain_text"]
                return plain_text
            else:
                return "Untitled Page"
    raise AssertionError("Page data should always contain a title property")


def extract_property_value(prop_value: dict[str, Any]) -> str:
    prop_type = prop_value["type"]
    value = prop_value[prop_type]

    if value is None:
        return "empty"

    match prop_type:
        case "rich_text" | "title":
            return value[0]["plain_text"] if len(value) > 0 else "empty"
        case "select" | "status" | "place":
            return value["name"]
        case "date":
            return value["start"]
        case "checkbox":
            return str(value).lower()
        case "files" | "people" | "multi_select":
            return ", ".join(f["name"] for f in value) if len(value) > 0 else "empty"
        case "formula" | "rollup":
            return extract_property_value(value)
        case "relation":
            return f"{len(value)} linked page(s)" if len(value) > 0 else "empty"
        case "unique_id":
            return str(value["number"])
        case _:
            return str(value)


def extract_property_updates(page_data: dict[str, Any], property_ids: list[str]) -> list[str]:
    properties = page_data["properties"]
    result = []
    for prop_name, prop_value in properties.items():
        if prop_value["id"] in property_ids:
            value = extract_property_value(prop_value)
            result.append(f"{prop_name} to {value}")
    return result


def get_page_data(notion_token: str, page_id: str) -> dict[str, Any] | None:
    if not notion_token:
        return None

    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = get_notion_api_headers(notion_token)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def get_user_name(notion_token: str, user_id: str) -> str | None:
    if not notion_token:
        return None

    url = f"https://api.notion.com/v1/users/{user_id}"
    headers = get_notion_api_headers(notion_token)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            user_data = response.json()
            name = user_data["name"]
            return name
        return None
    except Exception:
        return None


def get_author_name(payload: WildValue, notion_token: str) -> str | None:
    authors = payload["authors"]
    authors_list = authors.tame(
        check_list(check_dict([("id", check_string), ("type", check_string)]))
    )

    first_author = authors_list[0]
    user_id = str(first_author["id"])

    author_name = get_user_name(notion_token, user_id)
    if not author_name:
        return None

    if len(authors_list) > 1:
        others_count = len(authors_list) - 1
        return f"{author_name} (+{others_count} other{'s' if others_count > 1 else ''})"

    return author_name


def format_action_message(
    entity_type: str, entity_name: str | None, action: str, author_name: str | None
) -> str:
    if entity_name and author_name:
        return ENTITY_ACTION_TEMPLATE[0].format(
            entity_type=entity_type, entity_name=entity_name, action=action, author_name=author_name
        )
    elif entity_name:
        return ENTITY_ACTION_TEMPLATE[1].format(
            entity_type=entity_type, entity_name=entity_name, action=action
        )
    elif author_name:
        return ENTITY_ACTION_TEMPLATE[2].format(
            entity_type=entity_type, action=action, author_name=author_name
        )
    else:
        return ENTITY_ACTION_TEMPLATE[3].format(entity_type=entity_type, action=action)


def format_update_message(
    entity_type: str, entity_name: str | None, suffix: str, author_name: str | None
) -> str:
    if entity_name and author_name:
        return ENTITY_UPDATED_TEMPLATE[0].format(
            entity_type=entity_type, entity_name=entity_name, suffix=suffix, author_name=author_name
        )
    elif entity_name:
        return ENTITY_UPDATED_TEMPLATE[1].format(
            entity_type=entity_type, entity_name=entity_name, suffix=suffix
        )
    elif author_name:
        return ENTITY_UPDATED_TEMPLATE[2].format(
            entity_type=entity_type, suffix=suffix, author_name=author_name
        )
    else:
        return ENTITY_UPDATED_TEMPLATE[3].format(entity_type=entity_type, suffix=suffix)


def format_properties_message(
    entity_type: str, entity_name: str | None, properties: str, author_name: str | None
) -> str:
    if entity_name and author_name:
        return ENTITY_PROPERTIES_UPDATED_TEMPLATE[0].format(
            entity_type=entity_type,
            entity_name=entity_name,
            properties=properties,
            author_name=author_name,
        )
    elif entity_name:
        return ENTITY_PROPERTIES_UPDATED_TEMPLATE[1].format(
            entity_type=entity_type, entity_name=entity_name, properties=properties
        )
    elif author_name:
        return ENTITY_PROPERTIES_UPDATED_TEMPLATE[2].format(
            entity_type=entity_type, properties=properties, author_name=author_name
        )
    else:
        return ENTITY_PROPERTIES_UPDATED_TEMPLATE[3].format(
            entity_type=entity_type, properties=properties
        )


def get_entity_data(
    payload: WildValue, notion_token: str
) -> tuple[dict[str, Any] | None, str | None]:
    entity_id = payload["entity"]["id"].tame(check_string)
    page_data = get_page_data(notion_token, entity_id)
    author_name = get_author_name(payload, notion_token)
    return (page_data, author_name)


def get_entity_action_message(
    action: str, entity_type: str, payload: WildValue, notion_token: str
) -> tuple[str, str]:
    page_data, author_name = get_entity_data(payload, notion_token)
    entity_name = extract_page_title(page_data) if page_data else None

    body = format_action_message(entity_type, entity_name, action, author_name)
    topic = get_entity_topic_name(entity_type, entity_name)

    return (topic, body)


def get_entity_update_message(
    suffix: str, entity_type: str, payload: WildValue, notion_token: str
) -> tuple[str, str]:
    page_data, author_name = get_entity_data(payload, notion_token)
    entity_name = extract_page_title(page_data) if page_data else None

    if suffix == "properties" and page_data:
        updated_property_ids = payload["data"]["updated_properties"].tame(check_list(check_string))
        property_updates = extract_property_updates(page_data, updated_property_ids)
        properties_list = "\n".join(f"- {prop}" for prop in property_updates)
        body = format_properties_message(entity_type, entity_name, properties_list, author_name)
        topic = get_entity_topic_name(entity_type, entity_name)
        return (topic, body)

    body = format_update_message(entity_type, entity_name, suffix, author_name)
    topic = get_entity_topic_name(entity_type, entity_name)

    return (topic, body)


def handle_verification_request(payload: WildValue, notion_token: str) -> tuple[str, str]:
    verification_token = payload["verification_token"].tame(check_string)
    body = NOTION_VERIFICATION_TOKEN_MESSAGE.format(token=verification_token)
    return (ENTITY_TYPES[3], body)


EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue, str], tuple[str, str]]] = {
    "page.created": partial(get_entity_action_message, "created", ENTITY_TYPES[0]),
    "page.deleted": partial(get_entity_action_message, "moved to trash", ENTITY_TYPES[0]),
    "page.undeleted": partial(get_entity_action_message, "restored from trash", ENTITY_TYPES[0]),
    "page.moved": partial(get_entity_action_message, "moved", ENTITY_TYPES[0]),
    "page.locked": partial(get_entity_action_message, "locked", ENTITY_TYPES[0]),
    "page.unlocked": partial(get_entity_action_message, "unlocked", ENTITY_TYPES[0]),
    "page.content_updated": partial(get_entity_update_message, "content", ENTITY_TYPES[0]),
    "page.properties_updated": partial(get_entity_update_message, "properties", ENTITY_TYPES[0]),
    "verification": handle_verification_request,
}


def is_verification(payload: WildValue) -> bool:
    return payload.get("verification_token").tame(check_none_or(check_string)) is not None


ALL_EVENT_TYPES = list(EVENT_TO_FUNCTION_MAPPER.keys())


@webhook_view("Notion", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_notion_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    notion_token: str = "",
    map_pages_and_datasources_to_topics: Json[bool] = True,
) -> HttpResponse:
    if is_verification(payload):
        event_type = "verification"
    else:
        event_type = payload.get("type").tame(check_string)

    if event_type not in EVENT_TO_FUNCTION_MAPPER:
        raise UnsupportedWebhookEventTypeError(event_type)

    handler_function = EVENT_TO_FUNCTION_MAPPER[event_type]
    topic_name, body = handler_function(payload, notion_token)

    if not map_pages_and_datasources_to_topics:
        topic_name = topic_name.split(":")[0].strip()

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)
