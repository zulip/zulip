# Webhooks for external integrations.

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import get_short_sha
from zerver.models import UserProfile

COMMIT_INFO_TEMPLATE = (
    """Triggered on [`{commit_details}`]({commit_link}) on branch `{branch_name}`."""
)
TOPIC_TEMPLATE = "{pipeline} / {stage}"

SCHEDULED_BODY_TEMPLATE = """
**Pipeline** {pipeline}/{stage}: {status}.
- **Commit**: {commit_details}
- **Started**: {start_time}
"""

COMPLETED_BODY_TEMPLATE = """
**Build** {pipeline}/{stage}: {status} {emoji}.
- **Commit**: {commit_details}
- **Started**: {start_time}
- **Finished**: {end_time}
"""


@webhook_view("Gocd")
@typed_endpoint
def api_gocd_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    type = payload["type"].tame(check_string)
    if type == "stage":
        body = get_body(payload)
        topic_name = get_topic(payload)
        check_send_webhook_message(request, user_profile, topic_name, body)
    return json_success(request)


def get_topic(payload: WildValue) -> str:
    return TOPIC_TEMPLATE.format(
        pipeline=payload["data"]["pipeline"]["name"].tame(check_string),
        stage=payload["data"]["pipeline"]["stage"]["name"].tame(check_string),
    )


def get_commit_details(payload: WildValue) -> str:
    material = payload["data"]["pipeline"]["build-cause"][0]["material"]
    url = material["git-configuration"]["url"].tame(check_string)
    revision = payload["data"]["pipeline"]["build-cause"][0]["modifications"][0]["revision"].tame(
        check_string
    )
    commit_sha = get_short_sha(revision)
    url = f"{url}/commit/{commit_sha}"
    branch = material["git-configuration"]["branch"].tame(check_string)
    return COMMIT_INFO_TEMPLATE.format(
        commit_details=commit_sha,
        commit_link=url,
        branch_name=branch,
    )


def get_body(payload: WildValue) -> str:
    state = payload["data"]["pipeline"]["stage"].get("state").tame(check_string)
    if state == "Building":
        commit = get_commit_details(payload)
        return SCHEDULED_BODY_TEMPLATE.format(
            pipeline=payload["data"]["pipeline"]["name"].tame(check_string),
            stage=payload["data"]["pipeline"]["stage"]["name"].tame(check_string),
            status=state,
            commit_details=commit,
            start_time=payload["data"]["pipeline"]["stage"]["create-time"].tame(check_string),
        )
    else:
        commit = get_commit_details(payload)
        result = payload["data"]["pipeline"]["stage"].get("result").tame(check_string)
        emoji = ":thumbs_up:" if result == "Passed" else ":thumbs_down:"
        return COMPLETED_BODY_TEMPLATE.format(
            pipeline=payload["data"]["pipeline"].get("name").tame(check_string),
            stage=payload["data"]["pipeline"]["stage"].get("name").tame(check_string),
            status=result,
            emoji=emoji,
            commit_details=commit,
            start_time=payload["data"]["pipeline"]["stage"].get("create-time").tame(check_string),
            end_time=payload["data"]["pipeline"]["stage"]
            .get("last-transition-time")
            .tame(check_string),
        )
