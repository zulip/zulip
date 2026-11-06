from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import OptionalUserSpecifiedTopicStr, check_send_webhook_message
from zerver.lib.webhooks.git import get_short_sha
from zerver.models import UserProfile

MESSAGE_TEMPLATE = (
    "[{deployment_name}]({deployment_url}){author}{project} {event_description}{commit}"
)
AUTHOR_TEMPLATE = " by **{author}**"
PROJECT_TEMPLATE = " in [{project_name}]({project_url})"
COMMIT_TEMPLATE = ":\n> {commit_title} ([{short_sha}]({commit_url}))"

EVENT_DESCRIPTIONS = {
    "deployment.created": "was created",
    "deployment.succeeded": "succeeded",
    "deployment.error": "failed",
    "deployment.canceled": "was canceled",
    "deployment.promoted": "was promoted to production",
}

IGNORED_EVENTS = [
    # Rollback payloads don't include the project name or any links,
    # so we can't choose a topic or link to the deployment.
    "deployment.rollback",
    # Vercel integrations are automatically subscribed to these events,
    # which can't be deselected.
    "deployment.integration.action.cancel",
    "deployment.integration.action.cleanup",
    "deployment.integration.action.start",
    "integration-configuration.removed",
    "marketplace.invoice.created",
    "marketplace.invoice.notpaid",
    "marketplace.invoice.overdue",
    "marketplace.invoice.paid",
    "marketplace.invoice.refunded",
]


def get_deployment_body(event_type: str, event_payload: WildValue, include_project: bool) -> str:
    deployment_url = event_payload["links"]["deployment"].tame(check_string)
    if event_type == "deployment.promoted":
        # Promoted payloads have no target; promotion is always to production.
        deployment_name = "Deployment"
    else:
        target = event_payload["target"].tame(check_none_or(check_string))
        deployment_name = f"{(target or 'preview').capitalize()} deployment"

    meta = event_payload["deployment"]["meta"]
    author = ""
    if "githubCommitAuthorName" in meta:
        author = AUTHOR_TEMPLATE.format(author=meta["githubCommitAuthorName"].tame(check_string))

    project = ""
    if include_project:
        project = PROJECT_TEMPLATE.format(
            project_name=event_payload["name"].tame(check_string),
            project_url=event_payload["links"]["project"].tame(check_string),
        )

    commit = "."
    if "githubCommitMessage" in meta:
        org = meta["githubCommitOrg"].tame(check_string)
        repo = meta["githubCommitRepo"].tame(check_string)
        sha = meta["githubCommitSha"].tame(check_string)
        commit = COMMIT_TEMPLATE.format(
            commit_title=meta["githubCommitMessage"].tame(check_string).split("\n", 1)[0],
            short_sha=get_short_sha(sha),
            commit_url=f"https://github.com/{org}/{repo}/commit/{sha}",
        )

    return MESSAGE_TEMPLATE.format(
        deployment_name=deployment_name,
        deployment_url=deployment_url,
        author=author,
        project=project,
        event_description=EVENT_DESCRIPTIONS[event_type],
        commit=commit,
    )


# Event filtering via the integration URL isn't supported, since Vercel
# limits webhook URLs to 180 characters. Users can choose which events
# to send when configuring the webhook in Vercel instead.
@webhook_view("Vercel")
@typed_endpoint
def api_vercel_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    event_type = payload["type"].tame(check_string)
    if event_type in IGNORED_EVENTS:
        return json_success(request)
    if event_type not in EVENT_DESCRIPTIONS:
        raise UnsupportedWebhookEventTypeError(event_type)

    event_payload = payload["payload"]
    topic_name = event_payload["name"].tame(check_string)
    body = get_deployment_body(
        event_type, event_payload, include_project=user_specified_topic is not None
    )
    check_send_webhook_message(request, user_profile, topic_name, body)
    return json_success(request)
