from collections.abc import Callable
from typing import Any
from urllib.parse import unquote_plus

from django.http import HttpRequest, HttpResponse
from requests.exceptions import RequestException

from zerver.decorator import webhook_view
from zerver.lib.exceptions import AnomalousWebhookPayloadError, UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string, check_string_or_int
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


def fetch_content(base_url: str, content_id: str, token: str) -> dict[str, Any] | None:
    url = f"{base_url.rstrip('/')}/rest/api/content/{content_id}"
    try:
        response = get_service_api_data(
            url,
            integration_name="Confluence",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"expand": "space,container,_links"},
            max_retries=0,
        )
    except RequestException:
        # Confluence Server returns 404 for content that no longer exists
        # (e.g. just-deleted page); treat that and any transient error as
        # "no content available" and render a fallback message.
        return None
    return response.json()


def fetch_user_name(base_url: str, user_key: str, token: str) -> str:
    url = f"{base_url.rstrip('/')}/rest/api/user"
    try:
        response = get_service_api_data(
            url,
            integration_name="Confluence",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"key": user_key},
            max_retries=0,
        )
    except RequestException:
        return user_key
    return response.json().get("displayName", user_key)


def page_url(content: dict[str, Any]) -> str:
    links = content.get("_links", {})
    return links.get("base", "") + links.get("webui", "")


def comment_page_link(content: dict[str, Any]) -> tuple[str, str]:
    # Confluence Server does not expand container inline; instead the comment's
    # own _links.webui encodes the parent page path:
    # "/spaces/KEY/pages/ID/Page+Title?focusedCommentId=...#comment-..."
    links = content.get("_links", {})
    base = links.get("base", "")
    webui = links.get("webui", "")
    page_path = webui.split("?")[0]
    page_title = unquote_plus(page_path.rstrip("/").rsplit("/", 1)[-1])
    return page_title, base + page_path


def title_and_space(content: dict[str, Any], content_id: str) -> tuple[str, str]:
    title = content.get("title", f"{content_id}")
    space_name = content.get("space", {}).get("name", "unknown space")
    return title, space_name


def fetch_event_content(
    payload: WildValue, payload_key: str, base_url: str, token: str
) -> tuple[str, dict[str, Any] | None]:
    content_id = str(payload[payload_key]["id"].tame(check_string_or_int))
    return content_id, fetch_content(base_url, content_id, token)


def handle_page_created_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "page", base_url, token)
    if content is None:
        return f"Page {content_id}", f"{user_name} permanently removed a page."
    title, space_name = title_and_space(content, content_id)
    url = page_url(content)
    return title, f"{user_name} created page [{title}]({url}) in space **{space_name}**."


def handle_page_updated_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "page", base_url, token)
    if content is None:
        return f"Page {content_id}", f"{user_name} permanently removed a page."
    title, space_name = title_and_space(content, content_id)
    url = page_url(content)
    return title, f"{user_name} updated page [{title}]({url}) in space **{space_name}**."


def handle_page_restored_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "page", base_url, token)
    if content is None:
        return f"Page {content_id}", f"{user_name} permanently removed a page."
    title, space_name = title_and_space(content, content_id)
    url = page_url(content)
    return title, f"{user_name} restored page [{title}]({url}) in space **{space_name}**."


def handle_page_trashed_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "page", base_url, token)
    if content is None:
        return f"Page {content_id}", f"{user_name} permanently removed a page."
    title, space_name = title_and_space(content, content_id)
    return title, f"{user_name} removed page **{title}** from space **{space_name}**."


def handle_page_moved_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "page", base_url, token)
    if content is None:
        return f"Page {content_id}", f"{user_name} permanently removed a page."
    title, space_name = title_and_space(content, content_id)
    url = page_url(content)
    return title, f"{user_name} moved page [{title}]({url}) to space **{space_name}**."


def handle_blog_created_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "blog", base_url, token)
    if content is None:
        return f"Page {content_id}", f"{user_name} permanently removed a page."
    title, space_name = title_and_space(content, content_id)
    url = page_url(content)
    return title, f"{user_name} created blog post [{title}]({url}) in space **{space_name}**."


def handle_blog_updated_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "blog", base_url, token)
    if content is None:
        return f"Page {content_id}", f"{user_name} permanently removed a page."
    title, space_name = title_and_space(content, content_id)
    url = page_url(content)
    return title, f"{user_name} updated blog post [{title}]({url}) in space **{space_name}**."


def handle_blog_restored_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "blog", base_url, token)
    if content is None:
        return f"Page {content_id}", f"{user_name} permanently removed a page."
    title, space_name = title_and_space(content, content_id)
    url = page_url(content)
    return title, f"{user_name} restored blog post [{title}]({url}) in space **{space_name}**."


def handle_blog_trashed_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "blog", base_url, token)
    if content is None:
        return f"Page {content_id}", f"{user_name} permanently removed a page."
    title, space_name = title_and_space(content, content_id)
    return title, f"{user_name} removed blog post **{title}** from space **{space_name}**."


def handle_comment_created_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "comment", base_url, token)
    if content is None:
        return f"Comment {content_id}", f"{user_name} removed a comment."
    page_title, url = comment_page_link(content)
    return f"{page_title} (comments)", f"{user_name} commented on [{page_title}]({url})."


def handle_comment_updated_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "comment", base_url, token)
    if content is None:
        return f"Comment {content_id}", f"{user_name} removed a comment."
    page_title, url = comment_page_link(content)
    return (
        f"{page_title} (comments)",
        f"{user_name} updated a comment on [{page_title}]({url}).",
    )


def handle_comment_removed_event(
    user_name: str, payload: WildValue, base_url: str, token: str
) -> tuple[str, str]:
    content_id, content = fetch_event_content(payload, "comment", base_url, token)
    if content is None:
        return f"Comment {content_id}", f"{user_name} removed a comment."
    page_title, url = comment_page_link(content)
    return (
        f"{page_title} (comments)",
        f"{user_name} removed a comment on [{page_title}]({url}).",
    )


CONFLUENCE_CONTENT_FUNCTION_MAPPER: dict[
    str, Callable[[str, WildValue, str, str], tuple[str, str]]
] = {
    "page_created": handle_page_created_event,
    "page_updated": handle_page_updated_event,
    "page_restored": handle_page_restored_event,
    "page_trashed": handle_page_trashed_event,
    "page_moved": handle_page_moved_event,
    "blog_created": handle_blog_created_event,
    "blog_updated": handle_blog_updated_event,
    "blog_restored": handle_blog_restored_event,
    "blog_trashed": handle_blog_trashed_event,
    "comment_created": handle_comment_created_event,
    "comment_updated": handle_comment_updated_event,
    "comment_removed": handle_comment_removed_event,
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
    token: str,
) -> HttpResponse:
    event = payload.get("event").tame(check_none_or(check_string))

    if event in IGNORED_EVENTS:
        return json_success(request)

    if event is None:
        raise AnomalousWebhookPayloadError

    content_func = CONFLUENCE_CONTENT_FUNCTION_MAPPER.get(event)

    if content_func is None:
        raise UnsupportedWebhookEventTypeError(event)

    user_key = payload.get("userKey").tame(check_none_or(check_string)) or ""
    user_name = fetch_user_name(base_url, user_key, token) if user_key else "Unknown user"

    topic_name, message = content_func(user_name, payload, base_url, token)

    check_send_webhook_message(
        request, user_profile, topic_name, message, event, unquote_url_parameters=True
    )
    return json_success(request)
