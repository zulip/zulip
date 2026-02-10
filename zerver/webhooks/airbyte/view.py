# Webhooks for external integrations.

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

AIRBYTE_TOPIC_TEMPLATE = "{workspace} - {connection}"

AIRBYTE_MESSAGE_TEMPLATE = """\
{sync_status_emoji} Airbyte sync **{status}** for [{connection_name}]({connection_url}).


* **Source:** [{source_name}]({source_url})
* **Destination:** [{destination_name}]({destination_url})
* **Records:** {records_emitted} emitted, {records_committed} committed
* **Bytes:** {bytes_emitted} emitted, {bytes_committed} committed
* **Duration:** {duration}
"""


def extract_data_from_payload(payload_data: WildValue) -> dict[str, str | int | bool]:
    data: dict[str, str | int | bool] = {
        "workspace_name": payload_data["workspace"]["name"].tame(check_string),
        "connection_name": payload_data["connection"]["name"].tame(check_string),
        "source_name": payload_data["source"]["name"].tame(check_string),
        "destination_name": payload_data["destination"]["name"].tame(check_string),
        "connection_url": payload_data["connection"]["url"].tame(check_string),
        "source_url": payload_data["source"]["url"].tame(check_string),
        "destination_url": payload_data["destination"]["url"].tame(check_string),
        "successful_sync": payload_data["success"].tame(check_bool),
        "duration_formatted": payload_data["durationFormatted"].tame(check_string),
        "records_emitted": payload_data["recordsEmitted"].tame(check_int),
        "records_committed": payload_data["recordsCommitted"].tame(check_int),
        "bytes_emitted_formatted": payload_data["bytesEmittedFormatted"].tame(check_string),
        "bytes_committed_formatted": payload_data["bytesCommittedFormatted"].tame(check_string),
    }

    if not data["successful_sync"]:
        data["error_message"] = payload_data["errorMessage"].tame(check_string)

    return data


def format_message_from_data(data: dict[str, str | int | bool]) -> str:
    content = AIRBYTE_MESSAGE_TEMPLATE.format(
        sync_status_emoji=":green_circle:" if data["successful_sync"] else ":red_circle:",
        status="succeeded" if data["successful_sync"] else "failed",
        connection_name=data["connection_name"],
        connection_url=data["connection_url"],
        source_name=data["source_name"],
        source_url=data["source_url"],
        destination_name=data["destination_name"],
        destination_url=data["destination_url"],
        duration=data["duration_formatted"],
        records_emitted=data["records_emitted"],
        records_committed=data["records_committed"],
        bytes_emitted=data["bytes_emitted_formatted"],
        bytes_committed=data["bytes_committed_formatted"],
    )

    if not data["successful_sync"]:
        error_message = data["error_message"]
        content += f"\n**Error message:** {error_message}"

    return content


def create_topic_from_data(data: dict[str, str | int | bool]) -> str:
    return AIRBYTE_TOPIC_TEMPLATE.format(
        workspace=data["workspace_name"],
        connection=data["connection_name"],
    )


@webhook_view("Airbyte")
@typed_endpoint
def api_airbyte_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    if "data" in payload:
        data = extract_data_from_payload(payload["data"])
        content = format_message_from_data(data)
        topic = create_topic_from_data(data)
    else:
        # Test Airbyte notification payloads only contain this field.
        content = payload["text"].tame(check_string)
        topic = "Airbyte notification"
    check_send_webhook_message(request, user_profile, topic, content)
    return json_success(request)
