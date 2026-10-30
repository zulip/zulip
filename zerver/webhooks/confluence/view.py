import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import unquote_plus

from django.http import HttpRequest, HttpResponse
from requests.exceptions import RequestException

from zerver.decorator import webhook_view
from zerver.lib.bot_config import ConfigError, get_bot_config
from zerver.lib.exceptions import AnomalousWebhookPayloadError, UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, get_service_api_data
from zerver.models import UserProfile

IGNORED_EVENTS = [
    "attachment_created",
    "attachment_removed",
    "attachment_restored",
    "attachment_trashed",
    "attachment_updated",
    "blueprint_page_created",
    "content_created",
    "content_permissions_updated",
    "content_restored",
    "content_trashed",
    "content_updated",
    "group_created",
    "group_removed",
    "label_added",
    "label_created",
    "label_deleted",
    "label_removed",
    "page_children_reordered",
    "relation_created",
    "relation_deleted",
    "space_created",
    "space_logo_updated",
    "space_permissions_updated",
    "space_removed",
    "space_updated",
    "theme_enabled",
    "user_created",
    "user_deactivated",
    "user_followed",
    "user_reactivated",
    "user_removed",
    "page_removed",
    "blog_removed",
]

REGULAR_PAGE_BLOG_TEMPLATE = "{user} {action} {entity} [{title}]({url}) in space **{space}**."

CONFLUENCE_PAGE_BLOG_TEMPLATES = {
    "created": REGULAR_PAGE_BLOG_TEMPLATE,
    "updated": REGULAR_PAGE_BLOG_TEMPLATE,
    "trashed": REGULAR_PAGE_BLOG_TEMPLATE,
    "restored": REGULAR_PAGE_BLOG_TEMPLATE,
    "moved": "{user} moved {entity} [{title}]({url}) to space **{space}**.",
    "removed": "{user} removed {entity} **{title}** from space **{space}**.",
}
CONFLUENCE_COMMENT_TEMPLATES = {
    "created": "{user} commented on [{title}]({url}).",
    "updated": "{user} updated a comment on [{title}]({url}).",
    "removed": "{user} removed a comment from [{title}]({url}).",
}

CONFLUENCE_FALLBACK_TEMPLATE = "{user} {action} a {entity}. Unable to fetch the specific content."


def fetch_user_name(base_url: str, user_key: str, token: str) -> str:
    url = f"{base_url.rstrip('/')}/rest/api/user"
    try:
        response = get_service_api_data(
            url,
            integration_name="Confluence",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"key": user_key},
            max_retries=3,
        )
        return response.json().get("displayName", "Unknown user")
    except (RequestException, ValueError):
        return "Unknown user"


def page_url(content: dict[str, Any]) -> str:
    links = content.get("_links", {})
    return links.get("base", "") + links.get("webui", "")


def comment_page_link(content: dict[str, Any]) -> tuple[str, str]:
    links = content.get("_links", {})
    base = links.get("base", "")
    webui = links.get("webui", "")
    page_path = webui.split("?")[0]
    page_title = unquote_plus(page_path.rstrip("/").rsplit("/", 1)[-1])
    segments = page_path.split("/")
    entity = "Page" if segments[3] == "pages" else "Blog"
    return f"{entity}: {page_title}", base + webui


def title_and_space(content: dict[str, Any]) -> tuple[str, str]:
    title = content.get("title", "unknown")
    # Pages, blogs, and comments always belong to a space, so this default is
    # only a defensive fallback for
    # unusual responses (e.g. a trashed item whose space link has been
    # severed, or otherwise partially-populated content).
    space_name = content.get("space", {}).get("name", "unknown space")
    return title, space_name


def fetch_event_content(
    payload: WildValue, payload_key: str, base_url: str, token: str
) -> dict[str, Any] | None:
    content_id = str(payload[payload_key]["id"].tame(check_int))
    url = f"{base_url.rstrip('/')}/rest/api/content/{content_id}"
    try:
        response = get_service_api_data(
            url,
            integration_name="Confluence",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"expand": "space,container,_links"},
            max_retries=0,
        )
        return response.json()
    except (RequestException, ValueError):
        return None


def handle_page_event(
    action: str, user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content = fetch_event_content(payload, "page", base_url, token)
    if content is None:
        return (
            "Page unknown",
            CONFLUENCE_FALLBACK_TEMPLATE.format(user=user_name, action=action, entity="page"),
        )
    title, space_name = title_and_space(content)
    message = CONFLUENCE_PAGE_BLOG_TEMPLATES[action].format(
        user=user_name,
        action=action,
        entity="page",
        title=title,
        url=page_url(content),
        space=space_name,
    )
    return f"Page: {title}", message


def handle_blog_event(
    action: str, user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content = fetch_event_content(payload, "blog", base_url, token)
    if content is None:
        return (
            "Blog unknown",
            CONFLUENCE_FALLBACK_TEMPLATE.format(user=user_name, action=action, entity="blog"),
        )
    title, space_name = title_and_space(content)
    message = CONFLUENCE_PAGE_BLOG_TEMPLATES[action].format(
        user=user_name,
        action=action,
        entity="blog",
        title=title,
        url=page_url(content),
        space=space_name,
    )
    return f"Blog: {title}", message


def handle_comment_event(
    action: str, user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content = fetch_event_content(payload, "comment", base_url, token)
    if content is None:
        return (
            "Comment unknown",
            CONFLUENCE_FALLBACK_TEMPLATE.format(user=user_name, action=action, entity="comment"),
        )
    page_title, url = comment_page_link(content)
    message = CONFLUENCE_COMMENT_TEMPLATES[action].format(user=user_name, title=page_title, url=url)
    return page_title, message


CONFLUENCE_CONTENT_FUNCTION_MAPPER: dict[
    str, Callable[[str, WildValue, str, str], tuple[str, str]]
] = {
    "page_created": partial(handle_page_event, "created"),
    "page_updated": partial(handle_page_event, "updated"),
    "page_restored": partial(handle_page_event, "restored"),
    "page_trashed": partial(handle_page_event, "trashed"),
    "page_moved": partial(handle_page_event, "moved"),
    "blog_created": partial(handle_blog_event, "created"),
    "blog_updated": partial(handle_blog_event, "updated"),
    "blog_restored": partial(handle_blog_event, "restored"),
    "blog_trashed": partial(handle_blog_event, "trashed"),
    "comment_created": partial(handle_comment_event, "created"),
    "comment_updated": partial(handle_comment_event, "updated"),
    "comment_removed": partial(handle_comment_event, "removed"),
}

ALL_EVENT_TYPES = list(CONFLUENCE_CONTENT_FUNCTION_MAPPER.keys())


@webhook_view("Confluence", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_confluence_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    base_url: str,
) -> HttpResponse:
    try:
        config = get_bot_config(user_profile)
        token = config.get("confluence_token", "")
    except ConfigError:
        logging.warning(
            "Confluence webhook for bot %s has no confluence_token configured; "
            "unable to fetch the specific content for the events.",
            user_profile.id,
        )
        token = ""

    event = payload.get("event").tame(check_none_or(check_string))

    if event is None:
        raise AnomalousWebhookPayloadError

    if event in IGNORED_EVENTS:
        return json_success(request)

    content_func = CONFLUENCE_CONTENT_FUNCTION_MAPPER.get(event)

    if content_func is None:
        raise UnsupportedWebhookEventTypeError(event)

    user_key = payload.get("userKey").tame(check_none_or(check_string)) or ""
    user_name = fetch_user_name(base_url, user_key, token)

    topic_name, message = content_func(user_name, payload, base_url, token)

    check_send_webhook_message(
        request, user_profile, topic_name, message, event, unquote_url_parameters=True
    )
    return json_success(request)
