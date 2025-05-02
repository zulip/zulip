import re
from datetime import datetime, timezone
from typing import Protocol

from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import (
    OptionalUserSpecifiedTopicStr,
    check_send_webhook_message,
    validate_extract_webhook_http_header,
)
from zerver.lib.webhooks.git import (
    CONTENT_MESSAGE_TEMPLATE,
    EMPTY_SHA,
    RELEASE_MESSAGE_TEMPLATE_WITHOUT_USER_NAME,
    RELEASE_MESSAGE_TEMPLATE_WITHOUT_USER_NAME_WITHOUT_URL,
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE,
    get_commits_comment_action_message,
    get_issue_event_message,
    get_pull_request_event_message,
    get_push_commits_event_message,
    get_push_tag_event_message,
    get_remove_branch_event_message,
    is_branch_name_notifiable,
)
from zerver.models import UserProfile

TOPIC_WITH_DESIGN_INFO_TEMPLATE = "{repo} / {type} {design_name}"
DESIGN_COMMENT_MESSAGE_TEMPLATE = (
    "{user_name} {action} on design [{design_name}]({design_url}):\n{content_message}"
)

FEATURE_FLAG_MESSAGE_TEMPLATE = "{user} {action} the feature flag [{name}]({url})."

ACCESS_TOKEN_EXPIRY_MESSAGE_TEMPLATE = "The access token [{name}]({url}) will expire on {date}."


def fixture_to_headers(fixture_name: str) -> dict[str, str]:
    if fixture_name.startswith("build"):
        return {}  # Since there are 2 possible event types.

    # Map "push_hook__push_commits_more_than_limit.json" into GitLab's
    # HTTP event title "Push Hook".
    return {"HTTP_X_GITLAB_EVENT": fixture_name.split("__")[0].replace("_", " ").title()}


def get_push_event_body(payload: WildValue, include_title: bool) -> str:
    after = payload.get("after")
    if after:
        stringified_after = after.tame(check_string)
        if stringified_after == EMPTY_SHA:
            return get_remove_branch_event_body(payload)
    return get_normal_push_event_body(payload)


def get_normal_push_event_body(payload: WildValue) -> str:
    compare_url = "{}/-/compare/{}...{}".format(
        get_project_homepage(payload),
        payload["before"].tame(check_string),
        payload["after"].tame(check_string),
    )

    commits = [
        {
            "name": commit["author"]["name"].tame(check_string),
            "sha": commit["id"].tame(check_string),
            "message": commit["message"].tame(check_string),
            "url": commit["url"].tame(check_string),
        }
        for commit in payload["commits"]
    ]

    return get_push_commits_event_message(
        get_user_name(payload),
        compare_url,
        get_branch_name(payload),
        commits,
    )


def get_remove_branch_event_body(payload: WildValue) -> str:
    return get_remove_branch_event_message(
        get_user_name(payload),
        get_branch_name(payload),
    )


def get_tag_push_event_body(payload: WildValue, include_title: bool) -> str:
    return get_push_tag_event_message(
        get_user_name(payload),
        get_tag_name(payload),
        action="pushed" if payload.get("checkout_sha") else "removed",
    )


def get_issue_created_event_body(payload: WildValue, include_title: bool) -> str:
    description = payload["object_attributes"].get("description")
    # Filter out multiline hidden comments
    if description:
        stringified_description = description.tame(check_string)
        stringified_description = re.sub(
            r"<!--.*?-->", "", stringified_description, count=0, flags=re.DOTALL
        )
        stringified_description = stringified_description.rstrip()
    else:
        stringified_description = None

    return get_issue_event_message(
        user_name=get_issue_user_name(payload),
        action="created",
        url=get_object_url(payload),
        number=payload["object_attributes"]["iid"].tame(check_int),
        message=stringified_description,
        assignees=replace_assignees_username_with_name(get_assignees(payload)),
        title=payload["object_attributes"]["title"].tame(check_string) if include_title else None,
    )


def get_issue_event_body(action: str, payload: WildValue, include_title: bool) -> str:
    return get_issue_event_message(
        user_name=get_issue_user_name(payload),
        action=action,
        url=get_object_url(payload),
        number=payload["object_attributes"]["iid"].tame(check_int),
        title=payload["object_attributes"]["title"].tame(check_string) if include_title else None,
    )


def get_merge_request_updated_event_body(payload: WildValue, include_title: bool) -> str:
    if payload["object_attributes"].get("oldrev"):
        return get_merge_request_event_body(
            "added commit(s) to",
            payload,
            include_title=include_title,
        )

    return get_merge_request_open_or_updated_body(
        "updated",
        payload,
        include_title=include_title,
    )


def get_merge_request_event_body(action: str, payload: WildValue, include_title: bool) -> str:
    pull_request = payload["object_attributes"]
    target_branch = None
    base_branch = None
    if action == "merged":
        target_branch = pull_request["source_branch"].tame(check_string)
        base_branch = pull_request["target_branch"].tame(check_string)

    return get_pull_request_event_message(
        user_name=get_issue_user_name(payload),
        action=action,
        url=pull_request["url"].tame(check_string),
        number=pull_request["iid"].tame(check_int),
        target_branch=target_branch,
        base_branch=base_branch,
        type="MR",
        title=payload["object_attributes"]["title"].tame(check_string) if include_title else None,
    )


def get_merge_request_open_or_updated_body(
    action: str, payload: WildValue, include_title: bool
) -> str:
    pull_request = payload["object_attributes"]
    return get_pull_request_event_message(
        user_name=get_issue_user_name(payload),
        action=action,
        url=pull_request["url"].tame(check_string),
        number=pull_request["iid"].tame(check_int),
        target_branch=(
            pull_request["source_branch"].tame(check_string) if action == "created" else None
        ),
        base_branch=(
            pull_request["target_branch"].tame(check_string) if action == "created" else None
        ),
        message=pull_request["description"].tame(check_none_or(check_string)),
        assignees=replace_assignees_username_with_name(get_assignees(payload)),
        type="MR",
        title=payload["object_attributes"]["title"].tame(check_string) if include_title else None,
    )


def get_assignees(payload: WildValue) -> list[WildValue] | WildValue:
    assignee_details = payload.get("assignees")
    if not assignee_details:
        single_assignee_details = payload.get("assignee")
        if not single_assignee_details:
            transformed_assignee_details = []
        else:
            transformed_assignee_details = [single_assignee_details]
        return transformed_assignee_details
    return assignee_details


def replace_assignees_username_with_name(
    assignees: list[WildValue] | WildValue,
) -> list[dict[str, str]]:
    """Replace the username of each assignee with their (full) name.

    This is a hack-like adaptor so that when assignees are passed to
    `get_pull_request_event_message` we can use the assignee's name
    and not their username (for more consistency).
    """
    formatted_assignees = []
    for assignee in assignees:
        formatted_assignee = {}
        formatted_assignee["username"] = assignee["name"].tame(check_string)
        formatted_assignees.append(formatted_assignee)
    return formatted_assignees


def parse_design_comment(comment: WildValue, repository_url: str) -> tuple[str, str, str]:
    note_id = comment["id"].tame(check_int)

    # As there is no issue field in the payloads related to designs,
    # we need to parse the issue number from the new_path field.
    design_path = comment["position"]["new_path"].tame(check_string)

    # Sample design_path: "designs/issue-1/Screenshot_20250302_230445.png"
    _, issue_subpath, design_name = design_path.split("/")

    issue_number = issue_subpath.split("-")[-1]
    design_url = f"{repository_url}/-/issues/{issue_number}/designs/{design_name}"
    comment_url = f"{design_url}#note_{note_id}"

    return comment_url, design_url, design_name


def get_commented_commit_event_body(payload: WildValue, include_title: bool) -> str:
    comment = payload["object_attributes"]
    action = "[commented]({})".format(comment["url"].tame(check_string))
    return get_commits_comment_action_message(
        get_issue_user_name(payload),
        action,
        payload["commit"]["url"].tame(check_string),
        payload["commit"]["id"].tame(check_string),
        comment["note"].tame(check_string),
    )


def get_commented_merge_request_event_body(payload: WildValue, include_title: bool) -> str:
    comment = payload["object_attributes"]
    action = "[commented]({}) on".format(comment["url"].tame(check_string))
    url = payload["merge_request"]["url"].tame(check_string)

    return get_pull_request_event_message(
        user_name=get_issue_user_name(payload),
        action=action,
        url=url,
        number=payload["merge_request"]["iid"].tame(check_int),
        message=comment["note"].tame(check_string),
        type="MR",
        title=payload["merge_request"]["title"].tame(check_string) if include_title else None,
    )


def get_commented_issue_event_body(payload: WildValue, include_title: bool) -> str:
    comment = payload["object_attributes"]
    action = "[commented]({}) on".format(comment["url"].tame(check_string))
    url = payload["issue"]["url"].tame(check_string)

    return get_pull_request_event_message(
        user_name=get_issue_user_name(payload),
        action=action,
        url=url,
        number=payload["issue"]["iid"].tame(check_int),
        message=comment["note"].tame(check_string),
        type="issue",
        title=payload["issue"]["title"].tame(check_string) if include_title else None,
    )


def get_commented_design_event_body(payload: WildValue, include_title: bool) -> str:
    comment = payload["object_attributes"]
    repository_url = payload["repository"]["homepage"].tame(check_string)

    comment_url, design_url, design_name = parse_design_comment(comment, repository_url)
    action = f"[commented]({comment_url})"
    content_message = CONTENT_MESSAGE_TEMPLATE.format(message=comment["note"].tame(check_string))

    return DESIGN_COMMENT_MESSAGE_TEMPLATE.format(
        user_name=get_issue_user_name(payload),
        action=action,
        design_name=design_name,
        design_url=design_url,
        content_message=content_message,
    )


def get_commented_snippet_event_body(payload: WildValue, include_title: bool) -> str:
    comment = payload["object_attributes"]
    action = "[commented]({}) on".format(comment["url"].tame(check_string))
    # Snippet URL is only available in GitLab 16.1+
    if "url" in payload["snippet"]:
        url = payload["snippet"]["url"].tame(check_string)
    else:
        url = "{}/-/snippets/{}".format(
            payload["project"]["web_url"].tame(check_string),
            payload["snippet"]["id"].tame(check_int),
        )

    return get_pull_request_event_message(
        user_name=get_issue_user_name(payload),
        action=action,
        url=url,
        number=payload["snippet"]["id"].tame(check_int),
        message=comment["note"].tame(check_string),
        type="snippet",
        title=payload["snippet"]["title"].tame(check_string) if include_title else None,
    )


def get_wiki_page_event_body(action: str, payload: WildValue, include_title: bool) -> str:
    return '{} {} [wiki page "{}"]({}).'.format(
        get_issue_user_name(payload),
        action,
        payload["object_attributes"]["title"].tame(check_string),
        payload["object_attributes"]["url"].tame(check_string),
    )


def get_build_hook_event_body(payload: WildValue, include_title: bool) -> str:
    build_status = payload["build_status"].tame(check_string)
    if build_status == "created":
        action = "was created"
    elif build_status == "running":
        action = "started"
    else:
        action = f"changed status to {build_status}"
    return "Build {} from {} stage {}.".format(
        payload["build_name"].tame(check_string),
        payload["build_stage"].tame(check_string),
        action,
    )


def get_test_event_body(payload: WildValue, include_title: bool) -> str:
    return f"Webhook for **{get_repo_name(payload)}** has been configured successfully! :tada:"


def get_pipeline_event_body(payload: WildValue, include_title: bool) -> str:
    pipeline_status = payload["object_attributes"]["status"].tame(check_string)
    if pipeline_status == "pending":
        action = "was created"
    elif pipeline_status == "running":
        action = "started"
    else:
        action = f"changed status to {pipeline_status}"

    project_homepage = get_project_homepage(payload)
    pipeline_url = "{}/-/pipelines/{}".format(
        project_homepage,
        payload["object_attributes"]["id"].tame(check_int),
    )

    builds_status = ""
    for build in payload["builds"]:
        build_url = "{}/-/jobs/{}".format(
            project_homepage,
            build["id"].tame(check_int),
        )
        artifact_filename = build.get("artifacts_file", {}).get("filename", None)
        if artifact_filename:
            artifact_download_url = f"{build_url}/artifacts/download"
            artifact_browse_url = f"{build_url}/artifacts/browse"
            artifact_string = f"  * built artifact: *{artifact_filename.tame(check_string)}* [[Browse]({artifact_browse_url})|[Download]({artifact_download_url})]\n"
        else:
            artifact_string = ""
        builds_status += "* [{}]({}) - {}\n{}".format(
            build["name"].tame(check_string),
            build_url,
            build["status"].tame(check_string),
            artifact_string,
        )
    return "[Pipeline ({})]({}) {} with build(s):\n{}.".format(
        payload["object_attributes"]["id"].tame(check_int),
        pipeline_url,
        action,
        builds_status[:-1],
    )


def get_release_event_body(payload: WildValue, include_title: bool) -> str:
    action = payload["action"].tame(check_string)
    name = payload["name"].tame(check_string)
    tag = payload["tag"].tame(check_string)
    message_action = f"{action}d"

    if action == "delete":
        body = RELEASE_MESSAGE_TEMPLATE_WITHOUT_USER_NAME_WITHOUT_URL.format(
            release_name=name, tagname=tag, action=message_action
        )
    else:
        url = payload["url"].tame(check_string)
        body = RELEASE_MESSAGE_TEMPLATE_WITHOUT_USER_NAME.format(
            release_name=name, url=url, tagname=tag, action=message_action
        )

        if "description" in payload:
            description = payload["description"].tame(check_string)
            body += CONTENT_MESSAGE_TEMPLATE.format(message=description)

    return body


def get_feature_flag_event_body(payload: WildValue, include_title: bool) -> str:
    repo_url = payload["project"]["web_url"].tame(check_string)
    feature_flag = payload["object_attributes"]
    action = "activated" if feature_flag["active"] else "deactivated"

    return FEATURE_FLAG_MESSAGE_TEMPLATE.format(
        user=payload["user"]["username"].tame(check_string),
        action=action,
        name=feature_flag["name"].tame(check_string),
        url=f"{repo_url}/-/feature_flags",
    )


def get_access_token_page_url(payload: WildValue) -> str:
    """
    Generate the URL for the access tokens based on whether it's
    for a group or a project.
    """
    if "group" in payload:
        group_path = payload["group"]["group_path"].tame(check_string)
        return f"https://gitlab.com/groups/{group_path}/-/settings/access_tokens"

    project_url = payload["project"]["web_url"].tame(check_string)
    return f"{project_url}/-/settings/access_tokens"


def get_resource_access_token_expiry_event_body(payload: WildValue, include_title: bool) -> str:
    access_token = payload["object_attributes"]
    expiry_date = access_token["expires_at"].tame(check_string)
    formatted_date = (
        datetime.strptime(expiry_date, "%Y-%m-%d")
        .replace(tzinfo=timezone.utc)
        .strftime("%b %d, %Y")
    )

    return ACCESS_TOKEN_EXPIRY_MESSAGE_TEMPLATE.format(
        name=access_token["name"].tame(check_string),
        url=get_access_token_page_url(payload),
        date=formatted_date,
    )


def get_deployment_event_body(payload: WildValue, include_title: bool) -> str:
    user_text = (
        f"[{payload['user']['name'].tame(check_string)}]({payload['user_url'].tame(check_string)})"
    )

    deployment_status = payload["status"].tame(check_string)
    deployable_url = payload.get("deployable_url", "").tame(check_string)
    deployment_text = f"[deployment]({deployable_url})" if deployable_url else "deployment"

    commit_title = payload["commit_title"].tame(check_string)
    commit_url = payload["commit_url"].tame(check_string)
    commit_sha = commit_url.split("/")[-1][:7]

    deployment_event_body_map = {
        "running": f"{user_text} started a new {deployment_text}:\n> [{commit_sha}]({commit_url}) {commit_title}",
        "success": f"The {deployment_text} was successful.",
        "failed": f"The {deployment_text} failed.",
        "canceled": f"The {deployment_text} was canceled.",
    }

    return deployment_event_body_map[deployment_status]


def get_repo_name(payload: WildValue) -> str:
    if "project" in payload:
        return payload["project"]["name"].tame(check_string)

    # Apparently, Job Hook payloads don't have a `project` section,
    # but the repository name is accessible from the `repository`
    # section.
    return payload["repository"]["name"].tame(check_string)


def get_user_name(payload: WildValue) -> str:
    return payload["user_name"].tame(check_string)


def get_issue_user_name(payload: WildValue) -> str:
    return payload["user"]["name"].tame(check_string)


def get_project_homepage(payload: WildValue) -> str:
    if "project" in payload:
        return payload["project"]["web_url"].tame(check_string)
    return payload["repository"]["homepage"].tame(check_string)


def get_branch_name(payload: WildValue) -> str:
    return payload["ref"].tame(check_string).replace("refs/heads/", "")


def get_tag_name(payload: WildValue) -> str:
    return payload["ref"].tame(check_string).replace("refs/tags/", "")


def get_object_url(payload: WildValue) -> str:
    return payload["object_attributes"]["url"].tame(check_string)


def skip_previews(event: str) -> bool:
    # Add event names to this array for which previews should be skipped.
    return event in [
        # Design events link to images, but the images cannot be
        # accessed without authentication, so trying to preview them
        # doesn't work.
        "Note Hook DesignManagement::Design",
        "Confidential Note Hook DesignManagement::Design",
    ]


class EventFunction(Protocol):
    def __call__(self, payload: WildValue, include_title: bool) -> str: ...


EVENT_FUNCTION_MAPPER: dict[str, EventFunction] = {
    "Push Hook": get_push_event_body,
    "Tag Push Hook": get_tag_push_event_body,
    "Test Hook": get_test_event_body,
    "Issue Hook open": get_issue_created_event_body,
    "Issue Hook close": partial(get_issue_event_body, "closed"),
    "Issue Hook reopen": partial(get_issue_event_body, "reopened"),
    "Issue Hook update": partial(get_issue_event_body, "updated"),
    "Confidential Issue Hook open": get_issue_created_event_body,
    "Confidential Issue Hook close": partial(get_issue_event_body, "closed"),
    "Confidential Issue Hook reopen": partial(get_issue_event_body, "reopened"),
    "Confidential Issue Hook update": partial(get_issue_event_body, "updated"),
    "Note Hook Commit": get_commented_commit_event_body,
    "Note Hook MergeRequest": get_commented_merge_request_event_body,
    "Note Hook Issue": get_commented_issue_event_body,
    "Confidential Note Hook Issue": get_commented_issue_event_body,
    "Note Hook DesignManagement::Design": get_commented_design_event_body,
    "Confidential Note Hook DesignManagement::Design": get_commented_design_event_body,
    "Note Hook Snippet": get_commented_snippet_event_body,
    "Merge Request Hook approved": partial(get_merge_request_event_body, "approved"),
    "Merge Request Hook unapproved": partial(get_merge_request_event_body, "unapproved"),
    # approval and unapproval events are triggered only if there's more than one required approver
    # ref: https://gitlab.com/gitlab-org/gitlab/-/merge_requests/8742
    "Merge Request Hook approval": partial(get_merge_request_event_body, "approval"),
    "Merge Request Hook unapproval": partial(get_merge_request_event_body, "unapproval"),
    "Merge Request Hook open": partial(get_merge_request_open_or_updated_body, "created"),
    "Merge Request Hook update": get_merge_request_updated_event_body,
    "Merge Request Hook merge": partial(get_merge_request_event_body, "merged"),
    "Merge Request Hook close": partial(get_merge_request_event_body, "closed"),
    "Merge Request Hook reopen": partial(get_merge_request_event_body, "reopened"),
    "Wiki Page Hook create": partial(get_wiki_page_event_body, "created"),
    "Wiki Page Hook update": partial(get_wiki_page_event_body, "updated"),
    "Job Hook": get_build_hook_event_body,
    "Build Hook": get_build_hook_event_body,
    "Pipeline Hook": get_pipeline_event_body,
    "Release Hook": get_release_event_body,
    "Feature Flag Hook": get_feature_flag_event_body,
    "Resource Access Token Hook": get_resource_access_token_expiry_event_body,
    "Deployment Hook": get_deployment_event_body,
}

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


@webhook_view("GitLab", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_gitlab_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    branches: str | None = None,
    use_merge_request_title: Json[bool] = True,
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    event = get_event(request, payload, branches)
    if event is not None:
        event_body_function = get_body_based_on_event(event)
        body = event_body_function(
            payload,
            include_title=user_specified_topic is not None,
        )

        # Add a link to the project if a custom topic is set
        if user_specified_topic:
            project_url = f"[{get_repo_name(payload)}]({get_project_homepage(payload)})"
            body = f"[{project_url}] {body}"

        topic_name = get_topic_based_on_event(event, payload, use_merge_request_title)
        check_send_webhook_message(
            request, user_profile, topic_name, body, event, no_previews=skip_previews(event)
        )
    return json_success(request)


def get_body_based_on_event(event: str) -> EventFunction:
    return EVENT_FUNCTION_MAPPER[event]


def get_topic_based_on_event(event: str, payload: WildValue, use_merge_request_title: bool) -> str:
    if event == "Push Hook":
        return f"{get_repo_name(payload)} / {get_branch_name(payload)}"
    elif event in ("Job Hook", "Build Hook"):
        return "{} / {}".format(
            payload["repository"]["name"].tame(check_string), get_branch_name(payload)
        )
    elif event == "Pipeline Hook":
        return "{} / {}".format(
            get_repo_name(payload),
            payload["object_attributes"]["ref"].tame(check_string).replace("refs/heads/", ""),
        )
    elif event.startswith("Merge Request Hook"):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type="MR",
            id=payload["object_attributes"]["iid"].tame(check_int),
            title=(
                payload["object_attributes"]["title"].tame(check_string)
                if use_merge_request_title
                else ""
            ),
        )
    elif event.startswith(("Issue Hook", "Confidential Issue Hook")):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type="issue",
            id=payload["object_attributes"]["iid"].tame(check_int),
            title=payload["object_attributes"]["title"].tame(check_string),
        )
    elif event in ("Note Hook Issue", "Confidential Note Hook Issue"):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type="issue",
            id=payload["issue"]["iid"].tame(check_int),
            title=payload["issue"]["title"].tame(check_string),
        )
    elif event in (
        "Note Hook DesignManagement::Design",
        "Confidential Note Hook DesignManagement::Design",
    ):
        design_path = payload["object_attributes"]["position"]["new_path"].tame(check_string)
        design_name = design_path.split("/")[-1]

        return TOPIC_WITH_DESIGN_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type="design",
            design_name=design_name,
        )
    elif event == "Note Hook MergeRequest":
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type="MR",
            id=payload["merge_request"]["iid"].tame(check_int),
            title=(
                payload["merge_request"]["title"].tame(check_string)
                if use_merge_request_title
                else ""
            ),
        )

    elif event == "Note Hook Snippet":
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type="snippet",
            id=payload["snippet"]["id"].tame(check_int),
            title=payload["snippet"]["title"].tame(check_string),
        )

    elif event == "Resource Access Token Hook" and payload.get("group"):
        return payload["group"]["group_name"].tame(check_string)
    elif event == "Deployment Hook":
        return "{} / {}".format(
            get_repo_name(payload),
            payload["environment"].tame(check_string),
        )
    return get_repo_name(payload)


def get_event(request: HttpRequest, payload: WildValue, branches: str | None) -> str | None:
    event = validate_extract_webhook_http_header(request, "X-GitLab-Event", "GitLab")
    if event == "System Hook":
        # Convert the event name to a GitLab event title
        if "event_name" in payload:
            event_name = payload["event_name"].tame(check_string)
        else:
            event_name = payload["object_kind"].tame(check_string)
        event = event_name.split("__")[0].replace("_", " ").title()
        event = f"{event} Hook"
    if event in ["Confidential Issue Hook", "Issue Hook", "Merge Request Hook", "Wiki Page Hook"]:
        action = payload["object_attributes"].get("action", "open").tame(check_string)
        event = f"{event} {action}"
    elif event in ["Confidential Note Hook", "Note Hook"]:
        action = payload["object_attributes"]["noteable_type"].tame(check_string)
        event = f"{event} {action}"
    elif event == "Push Hook" and branches is not None:
        branch = get_branch_name(payload)
        if not is_branch_name_notifiable(branch, branches):
            return None

    if event in EVENT_FUNCTION_MAPPER:
        return event

    raise UnsupportedWebhookEventTypeError(event)
