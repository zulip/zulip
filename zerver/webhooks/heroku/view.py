from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALL_EVENT_TYPES = [
    "build_succeeded",
    "build_failed",
    "build_pending",
    "release_succeeded",
    "release_failed",
    "release_pending",
]

EVENT_FUNCTION_MAPPER = {
    "build_succeeded": "handle_build_succeeded",
    "build_failed": "handle_build_failed",
    "build_pending": "handle_build_pending",
    "release_succeeded": "handle_release_succeeded",
    "release_failed": "handle_release_failed",
    "release_pending": "handle_release_pending",
}


def get_actor_email(payload: WildValue, data: WildValue) -> str:
    if "actor" in payload:
        return payload["actor"]["email"].tame(check_string)
    return data["user"]["email"].tame(check_string)


def handle_build_succeeded(
    request: HttpRequest, user_profile: UserProfile, data: WildValue, payload: WildValue
) -> None:
    app_name = data["app"]["name"].tame(check_string)
    user_email = get_actor_email(payload, data)

    output_stream_url = data.get("output_stream_url")
    if output_stream_url:
        details_url = output_stream_url.tame(check_string)
    else:
        details_url = f"https://dashboard.heroku.com/apps/{app_name}/activity"

    topic = f"{app_name} / Build"
    body = f"Build for **{app_name}** triggered by {user_email} **succeeded**. [View Log]({details_url})"

    check_send_webhook_message(request, user_profile, topic, body)


def handle_build_failed(
    request: HttpRequest, user_profile: UserProfile, data: WildValue, payload: WildValue
) -> None:
    app_name = data["app"]["name"].tame(check_string)
    user_email = get_actor_email(payload, data)

    output_stream_url = data.get("output_stream_url")
    if output_stream_url:
        details_url = output_stream_url.tame(check_string)
    else:
        details_url = f"https://dashboard.heroku.com/apps/{app_name}/activity"

    topic = f"{app_name} / Build"
    body = (
        f"Build for **{app_name}** triggered by {user_email} **failed**. [View Log]({details_url})"
    )

    check_send_webhook_message(request, user_profile, topic, body)


def handle_build_pending(
    request: HttpRequest, user_profile: UserProfile, data: WildValue, payload: WildValue
) -> None:
    app_name = data["app"]["name"].tame(check_string)
    user_email = get_actor_email(payload, data)

    topic = f"{app_name} / Build"
    body = f"Build for **{app_name}** triggered by {user_email} is **pending**."

    check_send_webhook_message(request, user_profile, topic, body)


def handle_release_succeeded(
    request: HttpRequest, user_profile: UserProfile, data: WildValue, payload: WildValue
) -> None:
    app_name = data["app"]["name"].tame(check_string)
    user_email = get_actor_email(payload, data)
    description = data["description"].tame(check_string)

    if "current" in data and data["current"].tame(check_bool) is False:
        return

    topic = f"{app_name} / Release"
    body = f"Release ({description}) for **{app_name}** triggered by {user_email} **succeeded**."

    check_send_webhook_message(request, user_profile, topic, body)


def handle_release_failed(
    request: HttpRequest, user_profile: UserProfile, data: WildValue, payload: WildValue
) -> None:
    app_name = data["app"]["name"].tame(check_string)
    user_email = get_actor_email(payload, data)
    description = data["description"].tame(check_string)

    topic = f"{app_name} / Release"
    body = f"Release ({description}) for **{app_name}** triggered by {user_email} **failed**."

    check_send_webhook_message(request, user_profile, topic, body)


def handle_release_pending(
    request: HttpRequest, user_profile: UserProfile, data: WildValue, payload: WildValue
) -> None:
    app_name = data["app"]["name"].tame(check_string)
    user_email = get_actor_email(payload, data)
    description = data["description"].tame(check_string)

    topic = f"{app_name} / Release"
    body = f"Release ({description}) for **{app_name}** triggered by {user_email} is **pending**."

    check_send_webhook_message(request, user_profile, topic, body)


@webhook_view("Heroku", notify_bot_owner_on_invalid_json=False, all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_heroku_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    data = payload["data"]
    resource = payload["resource"].tame(check_string)
    status = data["status"].tame(check_string)

    event_type = f"{resource}_{status}"

    if event_type in EVENT_FUNCTION_MAPPER:
        handler_name = EVENT_FUNCTION_MAPPER[event_type]
        handler = globals()[handler_name]

        handler(request, user_profile, data, payload)

    return json_success(request)
