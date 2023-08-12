from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import (
    WildValue,
    check_int,
    check_none_or,
    check_string,
    check_string_in,
    check_url,
)
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import get_short_sha
from zerver.models import UserProfile

outcome_to_formatted_status_map = {
    "success": "has succeeded",
    "failed": "has failed",
    "canceled": "was canceled",
    "unauthorized": "was unauthorized",
    "error": "had an error",
}

GITHUB_COMMIT_LINK = "{target_repository_url}/commit/{commit_sha}"

BITBUCKET_COMMIT_LINK = "{target_repository_url}/commits/{commit_sha}"

GITLAB_COMMIT_LINK = "{web_url}/-/commit/{commit_sha}"

FULL_COMMIT_INFO_TEMPLATE = """
Triggered on [`{commit_details}`]({commit_link}) on branch `{branch_name}` by {author_name}.
"""

MANUAL_TRIGGER_INFO_TEMPLATE = """
Triggered on `{branch_name}`'s HEAD on [{commit_sha}]({commit_link}).
"""

TAG_TRIGGER_INFO_TEMPLATE = """
Triggered on the latest tag on [{commit_sha}]({commit_link}).
"""

WORKFLOW_BODY_TEMPLATE = """
Workflow [`{workflow_name}`]({workflow_url}) within Pipeline #{pipeline_number} {formatted_status}.
{commit_details}
"""

JOB_BODY_TEMPLATE = """
Job `{job_name}` within Pipeline #{pipeline_number} {formatted_status}.
{commit_details}
"""

ALL_EVENT_TYPES = ["ping", "job-completed", "workflow-completed"]


@webhook_view("CircleCI", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_circleci_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    type = payload["type"].tame(check_string)
    if type == "ping":
        # Ping events don't have full payloads, so our normal codepath won't work
        topic = "Test event"
        body = "Webhook '{name}' test event successful.".format(
            name=payload["webhook"]["name"].tame(check_string)
        )
    else:
        topic = get_topic(payload)
        body = get_body(payload)

        # We currently don't support projects using VCS providers other than GitHub,
        # BitBucket and GitLab.
        pipeline = payload["pipeline"]
        if "trigger_parameters" in pipeline and pipeline["trigger"]["type"] != "gitlab":
            raise JsonableError(
                _("Projects using this version control system provider aren't supported")
            )  # nocoverage

    check_send_webhook_message(
        request,
        user_profile,
        topic,
        body,
        payload["type"].tame(check_string),
    )
    return json_success(request)


def get_topic(payload: WildValue) -> str:
    return payload["project"]["name"].tame(check_string)


def get_commit_details(payload: WildValue) -> str:
    if "vcs" in payload["pipeline"]:  # GitHub and BitBucket associated pipelines.
        revision = payload["pipeline"]["vcs"]["revision"].tame(check_string)
        commit_id = get_short_sha(revision)

        if payload["pipeline"]["vcs"]["provider_name"] == "github":
            commit_link = GITHUB_COMMIT_LINK.format(
                target_repository_url=payload["pipeline"]["vcs"]["target_repository_url"].tame(
                    check_url
                ),
                commit_sha=revision,
            )
        else:
            commit_link = BITBUCKET_COMMIT_LINK.format(
                target_repository_url=payload["pipeline"]["vcs"]["target_repository_url"].tame(
                    check_url
                ),
                commit_sha=revision,
            )

        branch = payload["pipeline"]["vcs"]["branch"].tame(check_none_or(check_string))
        commit_subject = payload["pipeline"]["vcs"]["commit"]["subject"].tame(
            check_none_or(check_string)
        )
        if not commit_subject:
            # Manually triggered pipelines (possible only for GitHub and BitBucket projects currently).
            if not branch:
                return TAG_TRIGGER_INFO_TEMPLATE.format(
                    commit_sha=commit_id, commit_link=commit_link
                )
            return MANUAL_TRIGGER_INFO_TEMPLATE.format(
                branch_name=branch, commit_sha=commit_id, commit_link=commit_link
            )

        commit_details = f"{commit_id}: {commit_subject}"
        author_name = payload["pipeline"]["vcs"]["commit"]["author"]["name"].tame(check_string)

    else:  # Other providers (GitLab).
        commit_title = payload["pipeline"]["trigger_parameters"]["gitlab"]["commit_title"].tame(
            check_string
        )
        checkout_sha = payload["pipeline"]["trigger_parameters"]["gitlab"]["checkout_sha"].tame(
            check_string
        )
        commit_id = get_short_sha(checkout_sha)
        commit_details = f"{commit_id}: {commit_title}"

        author_name = payload["pipeline"]["trigger_parameters"]["gitlab"][
            "commit_author_name"
        ].tame(check_string)

        commit_link = GITLAB_COMMIT_LINK.format(
            web_url=payload["pipeline"]["trigger_parameters"]["gitlab"]["web_url"].tame(check_url),
            commit_sha=checkout_sha,
        )

        branch = payload["pipeline"]["trigger_parameters"]["gitlab"]["branch"].tame(check_string)

    return FULL_COMMIT_INFO_TEMPLATE.format(
        commit_details=commit_details,
        commit_link=commit_link,
        author_name=author_name,
        branch_name=branch,
    )


def get_body(payload: WildValue) -> str:
    pipeline_number = payload["pipeline"]["number"].tame(check_int)
    commit_details = get_commit_details(payload)
    payload_type = payload["type"].tame(check_string_in(["job-completed", "workflow-completed"]))

    if payload_type == "job-completed":
        job_name = payload["job"]["name"].tame(check_string)
        status = payload["job"]["status"].tame(check_string)
        formatted_status = outcome_to_formatted_status_map.get(status)
        return JOB_BODY_TEMPLATE.format(
            job_name=job_name,
            pipeline_number=pipeline_number,
            formatted_status=formatted_status,
            commit_details=commit_details,
        )

    else:
        workflow_name = payload["workflow"]["name"].tame(check_string)
        workflow_url = payload["workflow"]["url"].tame(check_url)
        status = payload["workflow"]["status"].tame(check_string)
        formatted_status = outcome_to_formatted_status_map.get(status)
        return WORKFLOW_BODY_TEMPLATE.format(
            workflow_name=workflow_name,
            workflow_url=workflow_url,
            pipeline_number=pipeline_number,
            formatted_status=formatted_status,
            commit_details=commit_details,
        )
