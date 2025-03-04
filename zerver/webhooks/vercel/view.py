from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string, check_url
from zerver.lib.webhooks.common import OptionalUserSpecifiedTopicStr, check_send_webhook_message
from zerver.models import UserProfile

# Events that are not yet supported by the integration.
IGNORED_EVENTS = {
    "deployment.ready",
    "deployment.check-rerequested",
    "integration-configuration.permission-upgraded",
    "integration-configuration.scope-change-confirmed",
    "integration-resource.project-connected",
    "integration-resource.project-disconnected",
    "firewall.attack",
    "domain.created",
    "project.removed",
    "project.created",
}

# These are the currently supported events, you can filter them more granually at
# https://vercel.com/dashboard/integrations/console > Manage > #settings-webhook
SUPPORTED_EVENTS = [
    "deployment.created",
    "deployment.canceled",
    "deployment.error",
    "deployment.promoted",
    "deployment.succeeded",
]


EVENT_DESCRIPTIONS = {
    "created": "created",
    "error": "failed",
    "canceled": "canceled",
    "promoted": "promoted",
    "succeeded": "succeeded",
}


@webhook_view("Vercel")
@typed_endpoint
def api_vercel_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    deployment_event_name = payload["type"].tame(check_string)
    if deployment_event_name in IGNORED_EVENTS:
        return json_success(request)

    meta = payload["payload"]["deployment"]["meta"]
    commit_author = meta["githubCommitAuthorLogin"].tame(check_string)
    commit_message = meta["githubCommitMessage"].tame(check_string)
    commit_hash = meta["githubCommitSha"].tame(check_string)
    repo = meta["githubCommitRepo"].tame(check_string)
    org = meta["githubCommitOrg"].tame(check_string)

    commit_url = f"https://github.com/{org}/{repo}/commit/{commit_hash}"
    deployment_url = payload["payload"]["links"]["deployment"].tame(check_url)
    project_name = payload["payload"]["name"].tame(check_string)
    project_url = payload["payload"]["links"]["project"].tame(check_url)

    # Derive the event description
    event_suffix = deployment_event_name.split(".")[-1]
    event_description = EVENT_DESCRIPTIONS.get(event_suffix, "unknown event")

    include_target = event_suffix in {"created", "succeeded"}
    target = (
        payload["payload"]["target"].tame(check_none_or(check_string)) if include_target else None
    )
    target_text = f"{target.capitalize()} deployment by " if target else "Deployment by "

    project_name_str = f"[{project_name}]({project_url})"
    include_title = user_specified_topic is None or user_specified_topic != project_name

    markdown_message = f"{target_text}{commit_author} **[{event_description}]({deployment_url})**"
    markdown_message += f" for {project_name_str}.\n" if include_title else ".\n"
    markdown_message += f">{commit_message} ([{commit_hash[:7]}]({commit_url}))"

    check_send_webhook_message(
        request, user_profile, user_specified_topic or project_name, markdown_message
    )

    return json_success(request)
