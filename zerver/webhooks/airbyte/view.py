# Webhooks for external integrations.

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

AIRBYTE_TOPIC_TEMPLATE = "{workspace} - {connection} - {source} - {destination}"
AIRBYTE_MESSAGE_TEMPLATE = (
    "**Job {jobId} {status}** in {durationFormatted}.\n\n"
    "**Details:**\n"
    "* **Source:** {source}\n"
    "* **Destination:** {destination}\n"
    "* **Bytes Emitted:** {bytesEmittedFormatted}\n"
    "* **Bytes Committed:** {bytesCommittedFormatted}\n"
    "* **Records Emitted:** {recordsEmitted}\n"
    "* **Records Committed:** {recordsCommitted}"
)
AIRBYTE_ERROR_MESSAGE_TEMPLATE = "**Job {jobId} failed.**\n" "* **Error Message:** {errorMessage}"
AIRBYTE_SUCCESS_MESSAGE = "succeeded"
AIRBYTE_FAILURE_MESSAGE = "failed"


@webhook_view("Airbyte")
@typed_endpoint
def api_airbyte_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    content, topic = create_airbyte_message(payload)
    check_send_webhook_message(request, user_profile, topic, content)
    return json_success(request)


def create_airbyte_message(payload: WildValue) -> tuple[str, str]:
    workspace = payload["data"]["workspace"]["name"].tame(check_string)
    connection = payload["data"]["connection"]["name"].tame(check_string)
    source = payload["data"]["source"]["name"].tame(check_string)
    destination = payload["data"]["destination"]["name"].tame(check_string)

    # Constructing the topic
    topic = AIRBYTE_TOPIC_TEMPLATE.format(
        workspace=workspace, connection=connection, source=source, destination=destination
    )

    # Extracting data from the payload
    job_id = payload["data"]["jobId"].tame(check_int)
    success = payload["data"]["success"].tame(check_bool)
    duration_formatted = payload["data"]["durationFormatted"].tame(check_string)
    records_emitted = payload["data"]["recordsEmitted"].tame(check_int)
    records_committed = payload["data"]["recordsCommitted"].tame(check_int)
    bytes_emitted_formatted = payload["data"]["bytesEmittedFormatted"].tame(check_string)
    bytes_committed_formatted = payload["data"]["bytesCommittedFormatted"].tame(check_string)

    # Check if the job succeeded or failed
    if success:
        content = AIRBYTE_MESSAGE_TEMPLATE.format(
            jobId=job_id,
            status=AIRBYTE_SUCCESS_MESSAGE,
            source=source,
            destination=destination,
            durationFormatted=duration_formatted,
            recordsEmitted=records_emitted,
            recordsCommitted=records_committed,
            bytesEmittedFormatted=bytes_emitted_formatted,
            bytesCommittedFormatted=bytes_committed_formatted,
        )
    else:
        error_message = payload["data"]["errorMessage"].tame(check_string)
        content = AIRBYTE_ERROR_MESSAGE_TEMPLATE.format(
            jobId=job_id,
            errorMessage=error_message,
        )
    return content, topic
