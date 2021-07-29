from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
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
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    body = get_body_for_http_request(payload)
    subject = get_subject_for_http_request(payload)

    check_send_webhook_message(request, user_profile, subject, body, payload["eventType"])
    return json_success()


def get_subject_for_http_request(payload: Dict[str, Any]) -> str:
    if payload["eventType"] != "Test" and payload["eventType"] != "Health":
        topic = RADARR_TOPIC_TEMPLATE.format(movie_title=payload["movie"]["title"])
    elif payload["eventType"] == "Test":
        topic = RADARR_TOPIC_TEMPLATE_TEST
    elif payload["eventType"] == "Health":
        topic = RADARR_TOPIC_TEMPLATE_HEALTH_CHECK.format(level=payload["level"])

    return topic


def get_body_for_health_check_event(payload: Dict[str, Any]) -> str:
    return RADARR_MESSAGE_TEMPLATE_HEALTH_CHECK.format(message=payload["message"])


def get_body_for_movie_renamed_event(payload: Dict[str, Any]) -> str:
    return RADARR_MESSAGE_TEMPLATE_MOVIE_RENAMED.format(movie_title=payload["movie"]["title"])


def get_body_for_movie_imported_upgrade_event(payload: Dict[str, Any]) -> str:
    data = {
        "movie_title": payload["movie"]["title"],
        "new_quality": payload["movieFile"]["quality"],
        "old_quality": payload["deletedFiles"][0]["quality"],
    }

    return RADARR_MESSAGE_TEMPLATE_MOVIE_IMPORTED_UPGRADE.format(**data)


def get_body_for_movie_imported_event(payload: Dict[str, Any]) -> str:
    return RADARR_MESSAGE_TEMPLATE_MOVIE_IMPORTED.format(movie_title=payload["movie"]["title"])


def get_body_for_movie_grabbed_event(payload: Dict[str, Any]) -> str:
    return RADARR_MESSAGE_TEMPLATE_MOVIE_GRABBED.format(movie_title=payload["movie"]["title"])


def get_body_for_http_request(payload: Dict[str, Any]) -> str:
    if payload["eventType"] == "Test":
        return get_setup_webhook_message("Radarr")
    elif payload["eventType"] == "Health":
        return get_body_for_health_check_event(payload)
    elif payload["eventType"] == "Rename":
        return get_body_for_movie_renamed_event(payload)
    elif payload["eventType"] == "Download" and "isUpgrade" in payload:
        if payload["isUpgrade"]:
            return get_body_for_movie_imported_upgrade_event(payload)
        else:
            return get_body_for_movie_imported_event(payload)
    elif payload["eventType"] == "Grab":
        return get_body_for_movie_grabbed_event(payload)
    else:
        raise UnsupportedWebhookEventType(payload["eventType"])
