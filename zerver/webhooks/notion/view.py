from collections.abc import Callable
from typing import Any

import requests
from django.http import HttpRequest
from django.http.response import HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_dict, check_list, check_none_or, check_string
from zerver.lib.webhooks.common import (
    check_send_webhook_message,
    get_service_api_data,
    get_setup_webhook_message,
)
from zerver.models import UserProfile

NOTION_VERIFICATION_TOKEN_MESSAGE = """
{setup_message}
Your verification token is: `{token}`
Please copy this token and paste it into your Notion webhook configuration to complete the setup.
""".strip()


def get_entity_topic_name(entity_type: str, entity_name: str | None) -> str:
    return f"{entity_type}: {entity_name}" if entity_name else entity_type


def extract_page_title(page_data: dict[str, Any]) -> str:
    title_prop = next(
        (v["title"] for v in page_data["properties"].values() if v["type"] == "title"), None
    )
    if title_prop is None:
        raise AssertionError("Page data must contain a title property")
    return title_prop[0]["plain_text"] if title_prop else "Untitled Page"


def extract_property_value(prop_value: dict[str, Any]) -> str:
    prop_type = prop_value["type"]
    value = prop_value[prop_type]

    if value is None:
        return "empty"

    match prop_type:
        case "rich_text" | "title":
            return value[0]["plain_text"] if value else "empty"
        case "select" | "status" | "place":
            return value["name"]
        case "date":
            return value["start"]
        case "checkbox":
            return str(value).lower()
        case "files" | "people" | "multi_select":
            return ", ".join(f["name"] for f in value) if value else "empty"
        case "formula" | "rollup":
            return extract_property_value(value)
        case "relation":
            return f"{len(value)} linked page(s)" if value else "empty"
        case "unique_id":
            return str(value["number"])
        case _:
            return str(value)


def extract_property_updates(page_data: dict[str, Any], property_ids: list[str]) -> list[str]:
    return [
        f"{name} to {extract_property_value(val)}"
        for name, val in page_data["properties"].items()
        if val["id"] in property_ids
    ]


def get_notion_api_headers(notion_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json",
    }


def get_notion_data(notion_token: str, entity_type: str, entity_id: str) -> dict[str, Any] | None:
    if not notion_token:
        return None

    url = f"https://api.notion.com/v1/{entity_type}/{entity_id}"
    headers = get_notion_api_headers(notion_token)

    try:
        data = get_service_api_data(url, integration_name="Notion", headers=headers)
    except (requests.RequestException, ValueError):
        return None

    return data.json()


def get_author_name(payload: WildValue, notion_token: str) -> str | None:
    authors = payload["authors"]
    authors_list = authors.tame(
        check_list(check_dict([("id", check_string), ("type", check_string)]))
    )

    first_author = authors_list[0]
    user_id = str(first_author["id"])

    author_name = (get_notion_data(notion_token, "users", user_id) or {}).get("name")

    if not author_name:
        return None

    if len(authors_list) > 1:
        others_count = len(authors_list) - 1
        return f"{author_name} (+{others_count} other{'s' if others_count > 1 else ''})"

    return author_name


def format_message(
    entity_type: str,
    entity_name: str | None,
    action: str,
    suffix: str | None,
    author_name: str | None,
    properties: str | None = None,
) -> str:
    message_parts: list[str]
    entity_display = entity_type

    if entity_name:
        entity_display += f" **{entity_name}**"

    if suffix:
        entity_display += f"'s {suffix}"

    message_parts = [entity_display]
    message_parts.append(f"was {action}")

    if author_name:
        message_parts.append(f"by **{author_name}**")

    if properties:
        message_parts.append(f"with the following:\n{properties}")

    message = " ".join(message_parts)
    return message if properties else message + "."


def get_message(
    event_descriptor: str, entity_type: str, payload: WildValue, notion_token: str
) -> tuple[str, str]:
    entity_id = payload["entity"]["id"].tame(check_string)
    entity_data = get_notion_data(notion_token, "pages", entity_id)
    author_name = get_author_name(payload, notion_token)
    entity_title = extract_page_title(entity_data) if entity_data else None

    match event_descriptor:
        case "content":
            body = format_message(
                entity_type, entity_title, "updated", event_descriptor, author_name
            )
        case "properties":
            updated_property_ids = (
                payload["data"]["updated_properties"].tame(check_list(check_string))
                if entity_data
                else []
            )
            properties_list = (
                "\n".join(
                    f"- {prop}"
                    for prop in extract_property_updates(entity_data, updated_property_ids)
                )
                if entity_data
                else None
            )
            body = format_message(
                entity_type, entity_title, "updated", event_descriptor, author_name, properties_list
            )
        case _:
            body = format_message(entity_type, entity_title, event_descriptor, None, author_name)

    topic = get_entity_topic_name(entity_type, entity_title)
    return (topic, body)


def handle_verification_request(payload: WildValue, notion_token: str) -> tuple[str, str]:
    verification_token = payload["verification_token"].tame(check_string)
    setup_message = get_setup_webhook_message("Notion")
    body = NOTION_VERIFICATION_TOKEN_MESSAGE.format(
        setup_message=setup_message, token=verification_token
    )
    return ("Verification", body)


EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue, str], tuple[str, str]]] = {
    "verification": handle_verification_request,
    "page.created": partial(get_message, "created", "Page"),
    "page.deleted": partial(get_message, "moved to trash", "Page"),
    "page.undeleted": partial(get_message, "restored from trash", "Page"),
    "page.moved": partial(get_message, "moved", "Page"),
    "page.locked": partial(get_message, "locked", "Page"),
    "page.unlocked": partial(get_message, "unlocked", "Page"),
    "page.content_updated": partial(get_message, "content", "Page"),
    "page.properties_updated": partial(get_message, "properties", "Page"),
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
) -> HttpResponse:

    if is_verification(payload):
        event_type = "verification"
    else:
        event_type = payload.get("type").tame(check_string)

    handler = EVENT_TO_FUNCTION_MAPPER.get(event_type)
    if handler is None:
        raise UnsupportedWebhookEventTypeError(event_type)
    topic_name, body = handler(payload, "")

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)
