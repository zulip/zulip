from typing import Any, Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

LIDARR_TOPIC_TEMPLATE = "{artist_name}".strip()
LIDARR_TOPIC_TEMPLATE_TEST = "Lidarr - Test".strip()

LIDARR_MESSAGE_TEMPLATE_TRACKS_RENAMED = (
    "The artist {artist_name} has had its tracks renamed.".strip()
)
LIDARR_MESSAGE_TEMPLATE_TRACKS_RETAGGED = (
    "The artist {artist_name} has had its tracks retagged.".strip()
)
LIDARR_MESSAGE_TEMPLATE_ALBUM_GRABBED = (
    "The album {album_name} by {artist_name} has been grabbed.".strip()
)

LIDARR_MESSAGE_TEMPLATE_TRACKS_IMPORTED = """
The following tracks by {artist_name} have been imported:
{tracks_final_data}
""".strip()

LIDARR_MESSAGE_TEMPLATE_TRACKS_IMPORTED_UPGRADE = """
The following tracks by {artist_name} have been imported due to upgrade:
{tracks_final_data}
""".strip()

LIDARR_TRACKS_ROW_TEMPLATE = "* {track_title}\n"
LIDARR_TRACKS_OTHERS_ROW_TEMPLATE = "[and {tracks_number} more tracks(s)]"
LIDARR_TRACKS_LIMIT = 20

ALL_EVENT_TYPES = ["Test", "Grab", "Rename", "Retag", "Download"]


def get_tracks_content(tracks_data: List[Dict[str, Any]]) -> str:
    tracks_content = ""
    for track in tracks_data[:LIDARR_TRACKS_LIMIT]:
        tracks_content += LIDARR_TRACKS_ROW_TEMPLATE.format(track_title=track.get("title"))

    if len(tracks_data) > LIDARR_TRACKS_LIMIT:
        tracks_content += LIDARR_TRACKS_OTHERS_ROW_TEMPLATE.format(
            tracks_number=len(tracks_data) - LIDARR_TRACKS_LIMIT,
        )

    return tracks_content.rstrip()


@webhook_view("Lidarr", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_lidarr_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    body = get_body_for_http_request(payload)
    subject = get_subject_for_http_request(payload)

    check_send_webhook_message(request, user_profile, subject, body, payload["eventType"])
    return json_success(request)


def get_subject_for_http_request(payload: Dict[str, Any]) -> str:
    if payload["eventType"] == "Test":
        topic = LIDARR_TOPIC_TEMPLATE_TEST
    else:
        topic = LIDARR_TOPIC_TEMPLATE.format(artist_name=payload["artist"]["name"])

    return topic


def get_body_for_album_grabbed_event(payload: Dict[str, Any]) -> str:
    return LIDARR_MESSAGE_TEMPLATE_ALBUM_GRABBED.format(
        artist_name=payload["artist"]["name"], album_name=payload["albums"][0]["title"]
    )


def get_body_for_tracks_renamed_event(payload: Dict[str, Any]) -> str:
    return LIDARR_MESSAGE_TEMPLATE_TRACKS_RENAMED.format(artist_name=payload["artist"]["name"])


def get_body_for_tracks_retagged_event(payload: Dict[str, Any]) -> str:
    return LIDARR_MESSAGE_TEMPLATE_TRACKS_RETAGGED.format(artist_name=payload["artist"]["name"])


def get_body_for_tracks_imported_upgrade_event(payload: Dict[str, Any]) -> str:
    tracks_data = []
    for track in payload["tracks"]:
        tracks_data.append({"title": track["title"]})

    data = {
        "artist_name": payload["artist"]["name"],
        "tracks_final_data": get_tracks_content(tracks_data),
    }

    return LIDARR_MESSAGE_TEMPLATE_TRACKS_IMPORTED_UPGRADE.format(**data)


def get_body_for_tracks_imported_event(payload: Dict[str, Any]) -> str:
    tracks_data = []
    for track in payload["tracks"]:
        tracks_data.append({"title": track["title"]})

    data = {
        "artist_name": payload["artist"]["name"],
        "tracks_final_data": get_tracks_content(tracks_data),
    }

    return LIDARR_MESSAGE_TEMPLATE_TRACKS_IMPORTED.format(**data)


def get_body_for_http_request(payload: Dict[str, Any]) -> str:
    if payload["eventType"] == "Test":
        return get_setup_webhook_message("Lidarr")
    elif payload["eventType"] == "Grab":
        return get_body_for_album_grabbed_event(payload)
    elif payload["eventType"] == "Rename":
        return get_body_for_tracks_renamed_event(payload)
    elif payload["eventType"] == "Retag":
        return get_body_for_tracks_retagged_event(payload)
    elif payload["eventType"] == "Download" and "isUpgrade" in payload:
        if payload["isUpgrade"]:
            return get_body_for_tracks_imported_upgrade_event(payload)
        else:
            return get_body_for_tracks_imported_event(payload)
    else:
        raise UnsupportedWebhookEventType(payload["eventType"])
