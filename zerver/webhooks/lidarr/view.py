from typing import Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_string
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


def get_tracks_content(tracks_data: List[Dict[str, str]]) -> str:
    tracks_content = ""
    for track in tracks_data[:LIDARR_TRACKS_LIMIT]:
        tracks_content += LIDARR_TRACKS_ROW_TEMPLATE.format(track_title=track.get("title"))

    if len(tracks_data) > LIDARR_TRACKS_LIMIT:
        tracks_content += LIDARR_TRACKS_OTHERS_ROW_TEMPLATE.format(
            tracks_number=len(tracks_data) - LIDARR_TRACKS_LIMIT,
        )

    return tracks_content.rstrip()


@webhook_view("Lidarr", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_lidarr_webhook(
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
    if payload["eventType"].tame(check_string) == "Test":
        topic = LIDARR_TOPIC_TEMPLATE_TEST
    else:
        topic = LIDARR_TOPIC_TEMPLATE.format(
            artist_name=payload["artist"]["name"].tame(check_string)
        )

    return topic


def get_body_for_album_grabbed_event(payload: WildValue) -> str:
    return LIDARR_MESSAGE_TEMPLATE_ALBUM_GRABBED.format(
        artist_name=payload["artist"]["name"].tame(check_string),
        album_name=payload["albums"][0]["title"].tame(check_string),
    )


def get_body_for_tracks_renamed_event(payload: WildValue) -> str:
    return LIDARR_MESSAGE_TEMPLATE_TRACKS_RENAMED.format(
        artist_name=payload["artist"]["name"].tame(check_string)
    )


def get_body_for_tracks_retagged_event(payload: WildValue) -> str:
    return LIDARR_MESSAGE_TEMPLATE_TRACKS_RETAGGED.format(
        artist_name=payload["artist"]["name"].tame(check_string)
    )


def get_body_for_tracks_imported_upgrade_event(payload: WildValue) -> str:
    tracks_data = [{"title": track["title"].tame(check_string)} for track in payload["tracks"]]
    data = {
        "artist_name": payload["artist"]["name"].tame(check_string),
        "tracks_final_data": get_tracks_content(tracks_data),
    }

    return LIDARR_MESSAGE_TEMPLATE_TRACKS_IMPORTED_UPGRADE.format(**data)


def get_body_for_tracks_imported_event(payload: WildValue) -> str:
    tracks_data = [{"title": track["title"].tame(check_string)} for track in payload["tracks"]]
    data = {
        "artist_name": payload["artist"]["name"].tame(check_string),
        "tracks_final_data": get_tracks_content(tracks_data),
    }

    return LIDARR_MESSAGE_TEMPLATE_TRACKS_IMPORTED.format(**data)


def get_body_for_http_request(payload: WildValue) -> str:
    event_type = payload["eventType"].tame(check_string)
    if event_type == "Test":
        return get_setup_webhook_message("Lidarr")
    elif event_type == "Grab":
        return get_body_for_album_grabbed_event(payload)
    elif event_type == "Rename":
        return get_body_for_tracks_renamed_event(payload)
    elif event_type == "Retag":
        return get_body_for_tracks_retagged_event(payload)
    elif event_type == "Download" and "isUpgrade" in payload:
        if payload["isUpgrade"].tame(check_bool):
            return get_body_for_tracks_imported_upgrade_event(payload)
        else:
            return get_body_for_tracks_imported_event(payload)
    else:
        raise UnsupportedWebhookEventTypeError(event_type)
