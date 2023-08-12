from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_string
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
@typed_endpoint
def api_sonarr_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    body = get_body_for_http_request(payload)
    topic = get_topic_for_http_request(payload)

    check_send_webhook_message(
        request, user_profile, topic, body, payload["eventType"].tame(check_string)
    )
    return json_success(request)


def get_topic_for_http_request(payload: WildValue) -> str:
    event_type = payload["eventType"].tame(check_string)
    if event_type == "Test":
        topic = SONARR_TOPIC_TEMPLATE_TEST
    elif event_type == "Health":
        topic = SONARR_TOPIC_TEMPLATE_HEALTH_CHECK.format(level=payload["level"].tame(check_string))
    else:
        topic = SONARR_TOPIC_TEMPLATE.format(
            series_title=payload["series"]["title"].tame(check_string)
        )

    return topic


def get_body_for_health_check_event(payload: WildValue) -> str:
    return SONARR_MESSAGE_TEMPLATE_HEALTH_CHECK.format(
        message=payload["message"].tame(check_string)
    )


def get_body_for_episodes_renamed_event(payload: WildValue) -> str:
    return SONARR_MESSAGE_TEMPLATE_EPISODES_RENAMED.format(
        series_title=payload["series"]["title"].tame(check_string)
    )


def get_body_for_series_deleted_event(payload: WildValue) -> str:
    return SONARR_MESSAGE_TEMPLATE_SERIES_DELETED.format(
        series_title=payload["series"]["title"].tame(check_string)
    )


def get_body_for_episode_imported_upgrade_event(payload: WildValue) -> str:
    data = {
        "series_title": payload["series"]["title"].tame(check_string),
        "series_number": payload["episodes"][0]["seasonNumber"].tame(check_int),
        "episode_number": payload["episodes"][0]["episodeNumber"].tame(check_int),
        "episode_name": payload["episodes"][0]["title"].tame(check_string),
        "new_quality": payload["episodeFile"]["quality"].tame(check_string),
        "old_quality": payload["deletedFiles"][0]["quality"].tame(check_string),
    }

    return SONARR_MESSAGE_TEMPLATE_EPISODE_IMPORTED_UPGRADE.format(**data)


def get_body_for_episode_imported_event(payload: WildValue) -> str:
    data = {
        "series_title": payload["series"]["title"].tame(check_string),
        "series_number": payload["episodes"][0]["seasonNumber"].tame(check_int),
        "episode_number": payload["episodes"][0]["episodeNumber"].tame(check_int),
        "episode_name": payload["episodes"][0]["title"].tame(check_string),
    }

    return SONARR_MESSAGE_TEMPLATE_EPISODE_IMPORTED.format(**data)


def get_body_for_episode_grabbed_event(payload: WildValue) -> str:
    data = {
        "series_title": payload["series"]["title"].tame(check_string),
        "series_number": payload["episodes"][0]["seasonNumber"].tame(check_int),
        "episode_number": payload["episodes"][0]["episodeNumber"].tame(check_int),
        "episode_name": payload["episodes"][0]["title"].tame(check_string),
    }

    return SONARR_MESSAGE_TEMPLATE_EPISODE_GRABBED.format(**data)


def get_body_for_episode_deleted_upgrade_event(payload: WildValue) -> str:
    data = {
        "series_title": payload["series"]["title"].tame(check_string),
        "series_number": payload["episodes"][0]["seasonNumber"].tame(check_int),
        "episode_number": payload["episodes"][0]["episodeNumber"].tame(check_int),
        "episode_name": payload["episodes"][0]["title"].tame(check_string),
    }

    return SONARR_MESSAGE_TEMPLATE_EPISODE_DELETED_UPGRADE.format(**data)


def get_body_for_episode_deleted_event(payload: WildValue) -> str:
    data = {
        "series_title": payload["series"]["title"].tame(check_string),
        "series_number": payload["episodes"][0]["seasonNumber"].tame(check_int),
        "episode_number": payload["episodes"][0]["episodeNumber"].tame(check_int),
        "episode_name": payload["episodes"][0]["title"].tame(check_string),
    }

    return SONARR_MESSAGE_TEMPLATE_EPISODE_DELETED.format(**data)


def get_body_for_http_request(payload: WildValue) -> str:
    event_type = payload["eventType"].tame(check_string)

    if event_type == "Test":
        return get_setup_webhook_message("Sonarr")
    elif event_type == "Health":
        return get_body_for_health_check_event(payload)
    elif event_type == "Rename":
        return get_body_for_episodes_renamed_event(payload)
    elif event_type == "SeriesDelete":
        return get_body_for_series_deleted_event(payload)
    elif event_type == "Download" and "isUpgrade" in payload:
        if payload["isUpgrade"].tame(check_bool):
            return get_body_for_episode_imported_upgrade_event(payload)
        else:
            return get_body_for_episode_imported_event(payload)
    elif event_type == "Grab":
        return get_body_for_episode_grabbed_event(payload)
    elif event_type == "EpisodeFileDelete" and "deleteReason" in payload:
        if payload["deleteReason"].tame(check_string) == "upgrade":
            return get_body_for_episode_deleted_upgrade_event(payload)
        else:
            return get_body_for_episode_deleted_event(payload)
    else:
        raise UnsupportedWebhookEventTypeError(event_type)
