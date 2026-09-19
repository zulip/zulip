from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import AnomalousWebhookPayloadError, UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
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


def get_user_name(payload: WildValue) -> str:
    return payload["user"]["displayName"].tame(check_string)


def get_page_url(page: WildValue) -> str:
    base = page["_links"]["base"].tame(check_string)
    webui = page["_links"]["webui"].tame(check_string)
    return base + webui


def handle_page_event(action: str, payload: WildValue) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    kwargs: dict[str, str] = {
        "user": get_user_name(payload),
        "action": action,
        "entity": "page",
        "title": title,
        "space": page["space"]["name"].tame(check_string),
    }
    if action != "removed":
        kwargs["url"] = get_page_url(page)
    content = CONFLUENCE_PAGE_BLOG_TEMPLATES[action].format(**kwargs)
    return f"Page: {title}", content


def handle_blog_event(action: str, payload: WildValue) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    kwargs: dict[str, str] = {
        "user": get_user_name(payload),
        "action": action,
        "entity": "blog post",
        "title": title,
        "space": page["space"]["name"].tame(check_string),
    }
    if action != "removed":
        kwargs["url"] = get_page_url(page)
    content = CONFLUENCE_PAGE_BLOG_TEMPLATES[action].format(**kwargs)
    return f"Blog: {title}", content


def handle_comment_event(action: str, payload: WildValue) -> tuple[str, str]:
    container = payload["comment"]["container"]
    title = container["title"].tame(check_string)
    container_type = container["type"].tame(check_string)
    topic_prefix = "Blog" if container_type == "blogpost" else "Page"
    content = CONFLUENCE_COMMENT_TEMPLATES[action].format(
        user=get_user_name(payload),
        title=title,
        url=get_page_url(container),
    )
    return f"{topic_prefix}: {title}", content


CONFLUENCE_CONTENT_FUNCTION_MAPPER: dict[str, Callable[[WildValue], tuple[str, str]]] = {
    "page_created": partial(handle_page_event, "created"),
    "page_updated": partial(handle_page_event, "updated"),
    "page_trashed": partial(handle_page_event, "trashed"),
    "page_restored": partial(handle_page_event, "restored"),
    "page_moved": partial(handle_page_event, "moved"),
    "page_removed": partial(handle_page_event, "removed"),
    "blog_created": partial(handle_blog_event, "created"),
    "blog_updated": partial(handle_blog_event, "updated"),
    "blog_trashed": partial(handle_blog_event, "trashed"),
    "blog_restored": partial(handle_blog_event, "restored"),
    "blog_removed": partial(handle_blog_event, "removed"),
    "comment_created": partial(handle_comment_event, "created"),
    "comment_updated": partial(handle_comment_event, "updated"),
    "comment_removed": partial(handle_comment_event, "removed"),
}


ALL_EVENT_TYPES = list(CONFLUENCE_CONTENT_FUNCTION_MAPPER.keys())


@webhook_view("ConfluenceCloud", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_confluence_cloud_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    event = payload.get("webhookEvent").tame(check_none_or(check_string))

    if event is None:
        raise AnomalousWebhookPayloadError

    if event in IGNORED_EVENTS:
        return json_success(request)

    content_func = CONFLUENCE_CONTENT_FUNCTION_MAPPER.get(event)

    if content_func is None:
        raise UnsupportedWebhookEventTypeError(event)

    topic_name, content = content_func(payload)

    check_send_webhook_message(
        request, user_profile, topic_name, content, event, unquote_url_parameters=True
    )
    return json_success(request)
