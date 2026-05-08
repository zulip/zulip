from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import AnomalousWebhookPayloadError, UnsupportedWebhookEventTypeError
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


def get_user_name(payload: WildValue) -> str:
    return payload["user"]["displayName"].tame(check_string)


def get_page_url(page: WildValue) -> str:
    base = page["_links"]["base"].tame(check_string)
    webui = page["_links"]["webui"].tame(check_string)
    return base + webui


def handle_page_created_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    url = get_page_url(page)
    content = f"{get_user_name(payload)} created [{title}]({url}) in space **{space_name}**."
    return title, content


def handle_page_updated_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    url = get_page_url(page)
    content = f"{get_user_name(payload)} updated [{title}]({url}) in space **{space_name}**."
    return title, content


def handle_page_trashed_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    url = get_page_url(page)
    content = f"{get_user_name(payload)} trashed [{title}]({url}) in space **{space_name}**."
    return title, content


def handle_page_restored_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    url = get_page_url(page)
    content = f"{get_user_name(payload)} restored [{title}]({url}) in space **{space_name}**."
    return title, content


def handle_page_removed_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    content = f"{get_user_name(payload)} removed **{title}** from space **{space_name}**."
    return title, content


def handle_page_moved_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    url = get_page_url(page)
    content = f"{get_user_name(payload)} moved [{title}]({url}) to space **{space_name}**."
    return title, content


def handle_blog_created_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    url = get_page_url(page)
    content = (
        f"{get_user_name(payload)} created blog post [{title}]({url}) in space **{space_name}**."
    )
    return title, content


def handle_blog_updated_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    url = get_page_url(page)
    content = (
        f"{get_user_name(payload)} updated blog post [{title}]({url}) in space **{space_name}**."
    )
    return title, content


def handle_blog_removed_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    content = f"{get_user_name(payload)} removed blog post **{title}** from space **{space_name}**."
    return title, content


def handle_blog_trashed_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    url = get_page_url(page)
    content = (
        f"{get_user_name(payload)} trashed blog post [{title}]({url}) in space **{space_name}**."
    )
    return title, content


def handle_blog_restored_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    page = payload["page"]
    title = page["title"].tame(check_string)
    space_name = page["space"]["name"].tame(check_string)
    url = get_page_url(page)
    content = (
        f"{get_user_name(payload)} restored blog post [{title}]({url}) in space **{space_name}**."
    )
    return title, content


def handle_comment_created_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    comment = payload["comment"]
    container = comment["container"]
    title = container["title"].tame(check_string)
    url = get_page_url(container)
    content = f"{get_user_name(payload)} commented on [{title}]({url})."
    return f"{title} (comments)", content


def handle_comment_updated_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    comment = payload["comment"]
    container = comment["container"]
    title = container["title"].tame(check_string)
    url = get_page_url(container)
    content = f"{get_user_name(payload)} updated a comment on [{title}]({url})."
    return f"{title} (comments)", content


def handle_comment_removed_event(payload: WildValue, user_profile: UserProfile) -> tuple[str, str]:
    comment = payload["comment"]
    container = comment["container"]
    title = container["title"].tame(check_string)
    url = get_page_url(container)
    content = f"{get_user_name(payload)} removed a comment from [{title}]({url})."
    return f"{title} (comments)", content


CONFLUENCE_CONTENT_FUNCTION_MAPPER: dict[
    str, Callable[[WildValue, UserProfile], tuple[str, str]] | None
] = {
    "page_created": handle_page_created_event,
    "page_updated": handle_page_updated_event,
    "page_trashed": handle_page_trashed_event,
    "page_restored": handle_page_restored_event,
    "page_removed": handle_page_removed_event,
    "page_moved": handle_page_moved_event,
    "blog_created": handle_blog_created_event,
    "blog_updated": handle_blog_updated_event,
    "blog_trashed": handle_blog_trashed_event,
    "blog_restored": handle_blog_restored_event,
    "blog_removed": handle_blog_removed_event,
    "comment_created": handle_comment_created_event,
    "comment_updated": handle_comment_updated_event,
    "comment_removed": handle_comment_removed_event,
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

    if event in IGNORED_EVENTS:
        return json_success(request)

    if event is None:
        raise AnomalousWebhookPayloadError

    content_func = CONFLUENCE_CONTENT_FUNCTION_MAPPER.get(event)

    if content_func is None:
        raise UnsupportedWebhookEventTypeError(event)

    topic_name, content = content_func(payload, user_profile)

    check_send_webhook_message(
        request, user_profile, topic_name, content, event, unquote_url_parameters=True
    )
    return json_success(request)
