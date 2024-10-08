# Webhooks for external integrations.

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

AIRBYTE_TOPIC_TEMPLATE = "{workspace} - {connection} - {source} - {destination}"

AIRBYTE_MESSAGE_TEMPLATE = """
Airbyte job {jobId} **{status}** in {durationFormatted}.

Connection: [{connection_name}]({connection_url})
**Details:**
* **Source:** [{source_name}]({source_url})
* **Destination:** [{destination_name}]({destination_url})
* **Records:** {recordsEmitted} emitted, {recordsCommitted} committed
* **Bytes:** {bytesEmittedFormatted} emitted, {bytesCommittedFormatted} committed
"""

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
    connection_name = payload["data"]["connection"]["name"].tame(check_string)
    connection_url = payload["data"]["connection"]["url"].tame(check_string)
    source_name = payload["data"]["source"]["name"].tame(check_string)
    source_url = payload["data"]["source"]["url"].tame(check_string)
    destination_name = payload["data"]["destination"]["name"].tame(check_string)
    destination_url = payload["data"]["destination"]["url"].tame(check_string)

    # Constructing the topic
    topic = AIRBYTE_TOPIC_TEMPLATE.format(
        workspace=workspace,
        connection=connection_name,
        source=source_name,
        destination=destination_name,
    )

    # Extracting data from the payload
    job_id = payload["data"]["jobId"].tame(check_int)
    success = payload["data"]["success"].tame(check_bool)
    duration_formatted = payload["data"]["durationFormatted"].tame(check_string)
    records_emitted = payload["data"]["recordsEmitted"].tame(check_int)
    records_committed = payload["data"]["recordsCommitted"].tame(check_int)
    bytes_emitted_formatted = payload["data"]["bytesEmittedFormatted"].tame(check_string)
    bytes_committed_formatted = payload["data"]["bytesCommittedFormatted"].tame(check_string)

    status = AIRBYTE_SUCCESS_MESSAGE if success else AIRBYTE_FAILURE_MESSAGE

    content = AIRBYTE_MESSAGE_TEMPLATE.format(
        jobId=job_id,
        status=status,
        connection_name=connection_name,
        connection_url=connection_url,
        source_name=source_name,
        source_url=source_url,
        destination_name=destination_name,
        destination_url=destination_url,
        durationFormatted=duration_formatted,
        recordsEmitted=records_emitted,
        recordsCommitted=records_committed,
        bytesEmittedFormatted=bytes_emitted_formatted,
        bytesCommittedFormatted=bytes_committed_formatted,
    )

    if not success:
        error_message = payload["data"]["errorMessage"].tame(check_string)
        content += "* **Error message:** " + error_message

    return content, topic
