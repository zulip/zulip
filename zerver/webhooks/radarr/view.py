from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

RADARR_TOPIC_TEMPLATE = "{movie_title}".strip()
RADARR_TOPIC_TEMPLATE_TEST = "Radarr - Test".strip()
RADARR_TOPIC_TEMPLATE_HEALTH_CHECK = "Health {level}".strip()

RADARR_MESSAGE_TEMPLATE_HEALTH_CHECK = "{message}.".strip()
RADARR_MESSAGE_TEMPLATE_MOVIE_RENAMED = "The movie {movie_title} has been renamed.".strip()
RADARR_MESSAGE_TEMPLATE_MOVIE_IMPORTED = "The movie {movie_title} has been imported.".strip()
RADARR_MESSAGE_TEMPLATE_MOVIE_IMPORTED_UPGRADE = (
    "The movie {movie_title} has been upgraded from {old_quality} to {new_quality}.".strip()
)
RADARR_MESSAGE_TEMPLATE_MOVIE_GRABBED = "The movie {movie_title} has been grabbed.".strip()

ALL_EVENT_TYPES = ["Rename", "Test", "Download", "Health", "Grab"]


@webhook_view("Radarr", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_radarr_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    body = get_body_for_http_request(payload)
    subject = get_subject_for_http_request(payload)

    check_send_webhook_message(
        request, user_profile, subject, body, payload["eventType"].tame(check_string)
    )
    return json_success(request)


def get_subject_for_http_request(payload: WildValue) -> str:
    event_type = payload["eventType"].tame(check_string)
    if event_type != "Test" and event_type != "Health":
        topic = RADARR_TOPIC_TEMPLATE.format(
            movie_title=payload["movie"]["title"].tame(check_string)
        )
    elif event_type == "Test":
        topic = RADARR_TOPIC_TEMPLATE_TEST
    elif event_type == "Health":
        topic = RADARR_TOPIC_TEMPLATE_HEALTH_CHECK.format(level=payload["level"].tame(check_string))

    return topic


def get_body_for_health_check_event(payload: WildValue) -> str:
    return RADARR_MESSAGE_TEMPLATE_HEALTH_CHECK.format(
        message=payload["message"].tame(check_string)
    )


def get_body_for_movie_renamed_event(payload: WildValue) -> str:
    return RADARR_MESSAGE_TEMPLATE_MOVIE_RENAMED.format(
        movie_title=payload["movie"]["title"].tame(check_string)
    )


def get_body_for_movie_imported_upgrade_event(payload: WildValue) -> str:
    data = {
        "movie_title": payload["movie"]["title"].tame(check_string),
        "new_quality": payload["movieFile"]["quality"].tame(check_string),
        "old_quality": payload["deletedFiles"][0]["quality"].tame(check_string),
    }

    return RADARR_MESSAGE_TEMPLATE_MOVIE_IMPORTED_UPGRADE.format(**data)


def get_body_for_movie_imported_event(payload: WildValue) -> str:
    return RADARR_MESSAGE_TEMPLATE_MOVIE_IMPORTED.format(
        movie_title=payload["movie"]["title"].tame(check_string)
    )


def get_body_for_movie_grabbed_event(payload: WildValue) -> str:
    return RADARR_MESSAGE_TEMPLATE_MOVIE_GRABBED.format(
        movie_title=payload["movie"]["title"].tame(check_string)
    )


def get_body_for_http_request(payload: WildValue) -> str:
    event_type = payload["eventType"].tame(check_string)
    if event_type == "Test":
        return get_setup_webhook_message("Radarr")
    elif event_type == "Health":
        return get_body_for_health_check_event(payload)
    elif event_type == "Rename":
        return get_body_for_movie_renamed_event(payload)
    elif event_type == "Download" and "isUpgrade" in payload:
        if payload["isUpgrade"]:
            return get_body_for_movie_imported_upgrade_event(payload)
        else:
            return get_body_for_movie_imported_event(payload)
    elif event_type == "Grab":
        return get_body_for_movie_grabbed_event(payload)
    else:
        raise UnsupportedWebhookEventType(event_type)
