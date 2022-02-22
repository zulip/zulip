from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

SONARR_TOPIC_TEMPLATE = "{series_title}".strip()
SONARR_TOPIC_TEMPLATE_TEST = "Sonarr - Test".strip()
SONARR_TOPIC_TEMPLATE_HEALTH_CHECK = "Health {level}".strip()

SONARR_MESSAGE_TEMPLATE_SERIES_DELETED = "{series_title} has been deleted.".strip()
SONARR_MESSAGE_TEMPLATE_HEALTH_CHECK = "{message}.".strip()
SONARR_MESSAGE_TEMPLATE_EPISODES_RENAMED = "{series_title} episodes have been renamed.".strip()
SONARR_MESSAGE_TEMPLATE_EPISODE_IMPORTED = (
    "{series_title} - {series_number}x{episode_number} - {episode_name} has been imported.".strip()
)
SONARR_MESSAGE_TEMPLATE_EPISODE_IMPORTED_UPGRADE = "{series_title} - {series_number}x{episode_number} - {episode_name} has been upgraded from {old_quality} to {new_quality}.".strip()
SONARR_MESSAGE_TEMPLATE_EPISODE_GRABBED = (
    "{series_title} - {series_number}x{episode_number} - {episode_name} has been grabbed.".strip()
)
SONARR_MESSAGE_TEMPLATE_EPISODE_DELETED = (
    "{series_title} - {series_number}x{episode_number} - {episode_name} has been deleted.".strip()
)
SONARR_MESSAGE_TEMPLATE_EPISODE_DELETED_UPGRADE = "{series_title} - {series_number}x{episode_number} - {episode_name} has been deleted due to quality upgrade.".strip()

ALL_EVENT_TYPES = [
    "Grab",
    "EpisodeFileDelete",
    "Test",
    "Download",
    "SeriesDelete",
    "Health",
    "Rename",
]


@webhook_view("Sonarr", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_sonarr_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    body = get_body_for_http_request(payload)
    subject = get_subject_for_http_request(payload)

    check_send_webhook_message(request, user_profile, subject, body, payload["eventType"])
    return json_success(request)


def get_subject_for_http_request(payload: Dict[str, Any]) -> str:
    if payload["eventType"] != "Test" and payload["eventType"] != "Health":
        topic = SONARR_TOPIC_TEMPLATE.format(series_title=payload["series"]["title"])
    elif payload["eventType"] == "Test":
        topic = SONARR_TOPIC_TEMPLATE_TEST
    elif payload["eventType"] == "Health":
        topic = SONARR_TOPIC_TEMPLATE_HEALTH_CHECK.format(level=payload["level"])

    return topic


def get_body_for_health_check_event(payload: Dict[str, Any]) -> str:
    return SONARR_MESSAGE_TEMPLATE_HEALTH_CHECK.format(message=payload["message"])


def get_body_for_episodes_renamed_event(payload: Dict[str, Any]) -> str:
    return SONARR_MESSAGE_TEMPLATE_EPISODES_RENAMED.format(series_title=payload["series"]["title"])


def get_body_for_series_deleted_event(payload: Dict[str, Any]) -> str:
    return SONARR_MESSAGE_TEMPLATE_SERIES_DELETED.format(series_title=payload["series"]["title"])


def get_body_for_episode_imported_upgrade_event(payload: Dict[str, Any]) -> str:
    data = {
        "series_title": payload["series"]["title"],
        "series_number": payload["episodes"][0]["seasonNumber"],
        "episode_number": payload["episodes"][0]["episodeNumber"],
        "episode_name": payload["episodes"][0]["title"],
        "new_quality": payload["episodeFile"]["quality"],
        "old_quality": payload["deletedFiles"][0]["quality"],
    }

    return SONARR_MESSAGE_TEMPLATE_EPISODE_IMPORTED_UPGRADE.format(**data)


def get_body_for_episode_imported_event(payload: Dict[str, Any]) -> str:
    data = {
        "series_title": payload["series"]["title"],
        "series_number": payload["episodes"][0]["seasonNumber"],
        "episode_number": payload["episodes"][0]["episodeNumber"],
        "episode_name": payload["episodes"][0]["title"],
    }

    return SONARR_MESSAGE_TEMPLATE_EPISODE_IMPORTED.format(**data)


def get_body_for_episode_grabbed_event(payload: Dict[str, Any]) -> str:
    data = {
        "series_title": payload["series"]["title"],
        "series_number": payload["episodes"][0]["seasonNumber"],
        "episode_number": payload["episodes"][0]["episodeNumber"],
        "episode_name": payload["episodes"][0]["title"],
    }

    return SONARR_MESSAGE_TEMPLATE_EPISODE_GRABBED.format(**data)


def get_body_for_episode_deleted_upgrade_event(payload: Dict[str, Any]) -> str:
    data = {
        "series_title": payload["series"]["title"],
        "series_number": payload["episodes"][0]["seasonNumber"],
        "episode_number": payload["episodes"][0]["episodeNumber"],
        "episode_name": payload["episodes"][0]["title"],
    }

    return SONARR_MESSAGE_TEMPLATE_EPISODE_DELETED_UPGRADE.format(**data)


def get_body_for_episode_deleted_event(payload: Dict[str, Any]) -> str:
    data = {
        "series_title": payload["series"]["title"],
        "series_number": payload["episodes"][0]["seasonNumber"],
        "episode_number": payload["episodes"][0]["episodeNumber"],
        "episode_name": payload["episodes"][0]["title"],
    }

    return SONARR_MESSAGE_TEMPLATE_EPISODE_DELETED.format(**data)


def get_body_for_http_request(payload: Dict[str, Any]) -> str:
    if payload["eventType"] == "Test":
        return get_setup_webhook_message("Sonarr")
    elif payload["eventType"] == "Health":
        return get_body_for_health_check_event(payload)
    elif payload["eventType"] == "Rename":
        return get_body_for_episodes_renamed_event(payload)
    elif payload["eventType"] == "SeriesDelete":
        return get_body_for_series_deleted_event(payload)
    elif payload["eventType"] == "Download" and "isUpgrade" in payload:
        if payload["isUpgrade"]:
            return get_body_for_episode_imported_upgrade_event(payload)
        else:
            return get_body_for_episode_imported_event(payload)
    elif payload["eventType"] == "Grab":
        return get_body_for_episode_grabbed_event(payload)
    elif payload["eventType"] == "EpisodeFileDelete" and "deleteReason" in payload:
        if payload["deleteReason"] == "upgrade":
            return get_body_for_episode_deleted_upgrade_event(payload)
        else:
            return get_body_for_episode_deleted_event(payload)
    else:
        raise UnsupportedWebhookEventType(payload["eventType"])
