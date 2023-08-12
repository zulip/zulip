from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_string, check_string_in
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

RADARR_TOPIC_TEMPLATE = "{movie_title}".strip()
RADARR_TOPIC_TEMPLATE_TEST = "Radarr - Test".strip()
RADARR_TOPIC_TEMPLATE_APPLICATION_UPDATE = "Radarr - Application update"
RADARR_TOPIC_TEMPLATE_HEALTH_CHECK = "Health {level}".strip()

RADARR_MESSAGE_TEMPLATE_HEALTH_CHECK = "{message}.".strip()
RADARR_MESSAGE_TEMPLATE_APPLICATION_UPDATE = (
    "Radarr was updated from {previous_version} to {new_version}."
)
RADARR_MESSAGE_TEMPLATE_MOVIE_RENAMED = "The movie {movie_title} has been renamed.".strip()
RADARR_MESSAGE_TEMPLATE_MOVIE_IMPORTED = "The movie {movie_title} has been imported.".strip()
RADARR_MESSAGE_TEMPLATE_MOVIE_IMPORTED_UPGRADE = (
    "The movie {movie_title} has been upgraded from {old_quality} to {new_quality}.".strip()
)
RADARR_MESSAGE_TEMPLATE_MOVIE_GRABBED = "The movie {movie_title} has been grabbed.".strip()
RADARR_MESSAGE_TEMPLATE_MOVIE_DELETED = (
    "The movie {movie_title} was deleted; its files were {deleted_files} deleted."
)
RADARR_MESSAGE_TEMPLATE_MOVIE_FILE_DELETED = (
    "A file with quality {quality} for the movie {movie_title} was deleted, {reason}."
)
RADARR_MESSAGE_TEMPLATE_MOVIE_ADDED = "The movie {movie_title} was added."

ALL_EVENT_TYPES = [
    "ApplicationUpdate",
    "Test",
    "Rename",
    "Download",
    "Health",
    "Grab",
    "MovieDelete",
    "MovieFileDelete",
    "MovieAdded",
]


@webhook_view("Radarr", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_radarr_webhook(
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
        return RADARR_TOPIC_TEMPLATE_TEST
    elif event_type == "ApplicationUpdate":
        return RADARR_TOPIC_TEMPLATE_APPLICATION_UPDATE
    elif event_type == "Health":
        return RADARR_TOPIC_TEMPLATE_HEALTH_CHECK.format(level=payload["level"].tame(check_string))
    else:
        return RADARR_TOPIC_TEMPLATE.format(
            movie_title=payload["movie"]["title"].tame(check_string)
        )


def get_body_for_health_check_event(payload: WildValue) -> str:
    return RADARR_MESSAGE_TEMPLATE_HEALTH_CHECK.format(
        message=payload["message"].tame(check_string)
    )


def get_body_for_application_update_event(payload: WildValue) -> str:
    return RADARR_MESSAGE_TEMPLATE_APPLICATION_UPDATE.format(
        previous_version=payload["previousVersion"].tame(check_string),
        new_version=payload["newVersion"].tame(check_string),
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


def get_body_for_movie_deleted_event(payload: WildValue) -> str:
    return RADARR_MESSAGE_TEMPLATE_MOVIE_DELETED.format(
        movie_title=payload["movie"]["title"].tame(check_string),
        deleted_files="also" if payload["deletedFiles"].tame(check_bool) else "not",
    )


def get_body_for_movie_file_deleted_event(payload: WildValue) -> str:
    reasons = {
        "missingFromDisk": "because it is missing from disk",
        "manual": "manually",
        "upgrade": "because an upgraded version exists",
        "noLinkedEpisodes": "because it has no linked episodes",
        "manualOverride": "via manual override",
    }
    return RADARR_MESSAGE_TEMPLATE_MOVIE_FILE_DELETED.format(
        movie_title=payload["movie"]["title"].tame(check_string),
        quality=payload["movieFile"]["quality"].tame(check_string),
        reason=reasons[payload["deleteReason"].tame(check_string_in(reasons.keys()))],
    )


def get_body_for_movie_added_event(payload: WildValue) -> str:
    return RADARR_MESSAGE_TEMPLATE_MOVIE_ADDED.format(
        movie_title=payload["movie"]["title"].tame(check_string)
    )


def get_body_for_http_request(payload: WildValue) -> str:
    event_type = payload["eventType"].tame(check_string)
    if event_type == "Test":
        return get_setup_webhook_message("Radarr")
    elif event_type == "ApplicationUpdate":
        return get_body_for_application_update_event(payload)
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
    elif event_type == "MovieDelete":
        return get_body_for_movie_deleted_event(payload)
    elif event_type == "MovieFileDelete":
        return get_body_for_movie_file_deleted_event(payload)
    elif event_type == "MovieAdded":
        return get_body_for_movie_added_event(payload)
    else:
        raise UnsupportedWebhookEventTypeError(event_type)
