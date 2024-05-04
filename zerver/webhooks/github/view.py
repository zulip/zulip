import re
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import log_unsupported_webhook_event, webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import (
    OptionalUserSpecifiedTopicStr,
    check_send_webhook_message,
    get_http_headers_from_filename,
    get_setup_webhook_message,
    validate_extract_webhook_http_header,
)
from zerver.lib.webhooks.git import (
    CONTENT_MESSAGE_TEMPLATE,
    TOPIC_WITH_BRANCH_TEMPLATE,
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE,
    get_commits_comment_action_message,
    get_issue_event_message,
    get_issue_labeled_or_unlabeled_event_message,
    get_issue_milestoned_or_demilestoned_event_message,
    get_pull_request_event_message,
    get_push_commits_event_message,
    get_push_tag_event_message,
    get_release_event_message,
    get_short_sha,
)
from zerver.models import UserProfile

fixture_to_headers = get_http_headers_from_filename("HTTP_X_GITHUB_EVENT")

TOPIC_FOR_DISCUSSION = "{repo} discussion #{number}: {title}"
DISCUSSION_TEMPLATE = "{author} created [discussion #{discussion_id}]({url}) in {category}:\n\n~~~ quote\n### {title}\n{body}\n~~~"


class Helper:
    def __init__(
        self,
        request: HttpRequest,
        payload: WildValue,
        include_title: bool,
    ) -> None:
        self.request = request
        self.payload = payload
        self.include_title = include_title

    def log_unsupported(self, event: str) -> None:
        summary = f"The '{event}' event isn't currently supported by the GitHub webhook; ignoring"
        log_unsupported_webhook_event(request=self.request, summary=summary)


def get_opened_or_update_pull_request_body(helper: Helper) -> str:
    payload = helper.payload
    include_title = helper.include_title
    pull_request = payload["pull_request"]
    action = payload["action"].tame(check_string)
    if action == "synchronize":
        action = "updated"
    assignee = None
    if pull_request.get("assignee"):
        assignee = pull_request["assignee"]["login"].tame(check_string)
    description = None
    changes = payload.get("changes", {})
    if "body" in changes or action == "opened":
        description = pull_request["body"].tame(check_none_or(check_string))
    target_branch = None
    base_branch = None
    if action in ("opened", "merged"):
        target_branch = pull_request["head"]["label"].tame(check_string)
        base_branch = pull_request["base"]["label"].tame(check_string)

    return get_pull_request_event_message(
        user_name=get_sender_name(payload),
        action=action,
        url=pull_request["html_url"].tame(check_string),
        target_branch=target_branch,
        base_branch=base_branch,
        message=description,
        assignee=assignee,
        number=pull_request["number"].tame(check_int),
        title=pull_request["title"].tame(check_string) if include_title else None,
    )


def get_assigned_or_unassigned_pull_request_body(helper: Helper) -> str:
    payload = helper.payload
    include_title = helper.include_title
    pull_request = payload["pull_request"]
    assignee = pull_request.get("assignee")
    if assignee:
        stringified_assignee = assignee["login"].tame(check_string)

    base_message = get_pull_request_event_message(
        user_name=get_sender_name(payload),
        action=payload["action"].tame(check_string),
        url=pull_request["html_url"].tame(check_string),
        number=pull_request["number"].tame(check_int),
        title=pull_request["title"].tame(check_string) if include_title else None,
    )
    if assignee:
        return base_message.replace("assigned", f"assigned {stringified_assignee} to", 1)
    return base_message


def get_closed_pull_request_body(helper: Helper) -> str:
    payload = helper.payload
    include_title = helper.include_title
    pull_request = payload["pull_request"]
    action = "merged" if pull_request["merged"].tame(check_bool) else "closed without merge"
    return get_pull_request_event_message(
        user_name=get_sender_name(payload),
        action=action,
        url=pull_request["html_url"].tame(check_string),
        number=pull_request["number"].tame(check_int),
        title=pull_request["title"].tame(check_string) if include_title else None,
    )


def get_membership_body(helper: Helper) -> str:
    payload = helper.payload
    action = payload["action"].tame(check_string)
    member = payload["member"]
    team_name = payload["team"]["name"].tame(check_string)

    return "{sender} {action} [{username}]({html_url}) {preposition} the {team_name} team.".format(
        sender=get_sender_name(payload),
        action=action,
        username=member["login"].tame(check_string),
        html_url=member["html_url"].tame(check_string),
        preposition="from" if action == "removed" else "to",
        team_name=team_name,
    )


def get_member_body(helper: Helper) -> str:
    payload = helper.payload
    return "{} {} [{}]({}) to [{}]({}).".format(
        get_sender_name(payload),
        payload["action"].tame(check_string),
        payload["member"]["login"].tame(check_string),
        payload["member"]["html_url"].tame(check_string),
        get_repository_name(payload),
        payload["repository"]["html_url"].tame(check_string),
    )


def get_issue_body(helper: Helper) -> str:
    payload = helper.payload
    include_title = helper.include_title
    action = payload["action"].tame(check_string)
    issue = payload["issue"]
    has_assignee = "assignee" in payload
    base_message = get_issue_event_message(
        user_name=get_sender_name(payload),
        action=action,
        url=issue["html_url"].tame(check_string),
        number=issue["number"].tame(check_int),
        message=(
            None
            if action in ("assigned", "unassigned")
            else issue["body"].tame(check_none_or(check_string))
        ),
        title=issue["title"].tame(check_string) if include_title else None,
    )

    if has_assignee:
        stringified_assignee = payload["assignee"]["login"].tame(check_string)
        if action == "assigned":
            return base_message.replace("assigned", f"assigned {stringified_assignee} to", 1)
        elif action == "unassigned":
            return base_message.replace("unassigned", f"unassigned {stringified_assignee} from", 1)

    return base_message


def get_issue_comment_body(helper: Helper) -> str:
    payload = helper.payload
    include_title = helper.include_title
    comment = payload["comment"]
    issue = payload["issue"]

    return get_pull_request_event_message(
        user_name=get_sender_name(payload),
        action=get_comment_action(payload),
        url=issue["html_url"].tame(check_string),
        number=issue["number"].tame(check_int),
        message=comment["body"].tame(check_string),
        title=issue["title"].tame(check_string) if include_title else None,
        type="PR" if is_pull_request_comment_event(payload) else "issue",
    )


def get_issue_labeled_or_unlabeled_body(helper: Helper) -> str:
    payload = helper.payload
    include_title = helper.include_title
    issue = payload["issue"]

    return get_issue_labeled_or_unlabeled_event_message(
        user_name=get_sender_name(payload),
        action="added" if payload["action"].tame(check_string) == "labeled" else "removed",
        url=issue["html_url"].tame(check_string),
        number=issue["number"].tame(check_int),
        label_name=payload["label"]["name"].tame(check_string),
        user_url=get_sender_url(payload),
        title=issue["title"].tame(check_string) if include_title else None,
    )


def get_issue_milestoned_or_demilestoned_body(helper: Helper) -> str:
    payload = helper.payload
    include_title = helper.include_title
    issue = payload["issue"]

    return get_issue_milestoned_or_demilestoned_event_message(
        user_name=get_sender_name(payload),
        action="added" if payload["action"].tame(check_string) == "milestoned" else "removed",
        url=issue["html_url"].tame(check_string),
        number=issue["number"].tame(check_int),
        milestone_name=payload["milestone"]["title"].tame(check_string),
        milestone_url=payload["milestone"]["html_url"].tame(check_string),
        user_url=get_sender_url(payload),
        title=issue["title"].tame(check_string) if include_title else None,
    )


def get_fork_body(helper: Helper) -> str:
    payload = helper.payload
    forkee = payload["forkee"]
    return "{} forked [{}]({}).".format(
        get_sender_name(payload),
        forkee["name"].tame(check_string),
        forkee["html_url"].tame(check_string),
    )


def get_deployment_body(helper: Helper) -> str:
    payload = helper.payload
    return f"{get_sender_name(payload)} created new deployment."


def get_change_deployment_status_body(helper: Helper) -> str:
    payload = helper.payload
    return "Deployment changed status to {}.".format(
        payload["deployment_status"]["state"].tame(check_string),
    )


def get_create_or_delete_body(action: str, helper: Helper) -> str:
    payload = helper.payload
    ref_type = payload["ref_type"].tame(check_string)
    return "{} {} {} {}.".format(
        get_sender_name(payload),
        action,
        ref_type,
        payload["ref"].tame(check_string),
    ).rstrip()


def get_commit_comment_body(helper: Helper) -> str:
    payload = helper.payload
    comment = payload["comment"]
    comment_url = comment["html_url"].tame(check_string)
    commit_url = comment_url.split("#", 1)[0]
    action = f"[commented]({comment_url})"
    return get_commits_comment_action_message(
        get_sender_name(payload),
        action,
        commit_url,
        comment["commit_id"].tame(check_string),
        comment["body"].tame(check_string),
    )


def get_push_tags_body(helper: Helper) -> str:
    payload = helper.payload
    return get_push_tag_event_message(
        get_sender_name(payload),
        get_tag_name_from_ref(payload["ref"].tame(check_string)),
        action="pushed" if payload["created"].tame(check_bool) else "removed",
    )


def get_push_commits_body(helper: Helper) -> str:
    payload = helper.payload
    commits_data = []
    for commit in payload["commits"]:
        if commit["author"].get("username"):
            name = commit["author"]["username"].tame(check_string)
        else:
            name = commit["author"]["name"].tame(check_string)
        commits_data.append(
            {
                "name": name,
                "sha": commit["id"].tame(check_string),
                "url": commit["url"].tame(check_string),
                "message": commit["message"].tame(check_string),
            }
        )
    return get_push_commits_event_message(
        get_sender_name(payload),
        payload["compare"].tame(check_string),
        get_branch_name_from_ref(payload["ref"].tame(check_string)),
        commits_data,
        deleted=payload["deleted"].tame(check_bool),
        force_push=payload["forced"].tame(check_bool),
    )


def get_discussion_body(helper: Helper) -> str:
    payload = helper.payload
    return DISCUSSION_TEMPLATE.format(
        author=get_sender_name(payload),
        url=payload["discussion"]["html_url"].tame(check_string),
        body=payload["discussion"]["body"].tame(check_string),
        category=payload["discussion"]["category"]["name"].tame(check_string),
        discussion_id=payload["discussion"]["number"].tame(check_int),
        title=payload["discussion"]["title"].tame(check_string),
    )


def get_discussion_comment_body(helper: Helper) -> str:
    payload = helper.payload
    return get_pull_request_event_message(
        user_name=get_sender_name(payload),
        action=get_comment_action(payload),
        url=payload["discussion"]["html_url"].tame(check_string),
        number=payload["discussion"]["number"].tame(check_int),
        message=payload["comment"]["body"].tame(check_string),
        title=payload["discussion"]["title"].tame(check_string) if helper.include_title else None,
        type="discussion",
    )


def get_comment_action(payload: WildValue) -> str:
    action = payload["action"].tame(check_string)
    if action == "created":
        action = "[commented]"
    else:
        action = f"{action} a [comment]"
    action += "({}) on".format(payload["comment"]["html_url"].tame(check_string))
    return action


def get_public_body(helper: Helper) -> str:
    payload = helper.payload
    return "{} made the repository [{}]({}) public.".format(
        get_sender_name(payload),
        get_repository_full_name(payload),
        payload["repository"]["html_url"].tame(check_string),
    )


def get_wiki_pages_body(helper: Helper) -> str:
    payload = helper.payload
    wiki_page_info_template = "* {action} [{title}]({url})\n"
    wiki_info = ""
    for page in payload["pages"]:
        wiki_info += wiki_page_info_template.format(
            action=page["action"].tame(check_string),
            title=page["title"].tame(check_string),
            url=page["html_url"].tame(check_string),
        )
    return f"{get_sender_name(payload)}:\n{wiki_info.rstrip()}"


def get_watch_body(helper: Helper) -> str:
    payload = helper.payload
    return "{} starred the repository [{}]({}).".format(
        get_sender_name(payload),
        get_repository_full_name(payload),
        payload["repository"]["html_url"].tame(check_string),
    )


def get_repository_body(helper: Helper) -> str:
    payload = helper.payload
    return "{} {} the repository [{}]({}).".format(
        get_sender_name(payload),
        payload["action"].tame(check_string),
        get_repository_full_name(payload),
        payload["repository"]["html_url"].tame(check_string),
    )


def get_add_team_body(helper: Helper) -> str:
    payload = helper.payload
    return "The repository [{}]({}) was added to team {}.".format(
        get_repository_full_name(payload),
        payload["repository"]["html_url"].tame(check_string),
        payload["team"]["name"].tame(check_string),
    )


def get_team_body(helper: Helper) -> str:
    payload = helper.payload
    changes = payload["changes"]
    if "description" in changes:
        actor = get_sender_name(payload)
        new_description = payload["team"]["description"].tame(check_string)
        return f"**{actor}** changed the team description to:\n\n~~~ quote\n{new_description}\n~~~"
    if "name" in changes:
        original_name = changes["name"]["from"].tame(check_string)
        new_name = payload["team"]["name"].tame(check_string)
        return f"Team `{original_name}` was renamed to `{new_name}`."
    if "privacy" in changes:
        new_visibility = payload["team"]["privacy"].tame(check_string)
        return f"Team visibility changed to `{new_visibility}`"

    missing_keys = "/".join(sorted(changes.keys()))
    helper.log_unsupported(f"team/edited (changes: {missing_keys})")

    # Do our best to give useful info to the customer--at least
    # if they know something changed, they can go to GitHub for
    # more details.  And if it's just spam, you can control that
    # from GitHub.
    return f"Team has changes to `{missing_keys}` data."


def get_release_body(helper: Helper) -> str:
    payload = helper.payload
    if payload["release"]["name"]:
        release_name = payload["release"]["name"].tame(check_string)
    else:
        release_name = payload["release"]["tag_name"].tame(check_string)
    data = {
        "user_name": get_sender_name(payload),
        "action": payload["action"].tame(check_string),
        "tagname": payload["release"]["tag_name"].tame(check_string),
        # Not every GitHub release has a "name" set; if not there, use the tag name.
        "release_name": release_name,
        "url": payload["release"]["html_url"].tame(check_string),
    }

    return get_release_event_message(**data)


def get_page_build_body(helper: Helper) -> str:
    payload = helper.payload
    build = payload["build"]
    status = build["status"].tame(check_string)
    actions = {
        "null": "has yet to be built",
        "building": "is being built",
        "errored": "has failed: {}",
        "built": "has finished building",
    }

    action = actions.get(status, f"is {status}")
    if build["error"]["message"]:
        action = action.format(
            CONTENT_MESSAGE_TEMPLATE.format(message=build["error"]["message"].tame(check_string)),
        )

    return "GitHub Pages build, triggered by {}, {}.".format(
        payload["build"]["pusher"]["login"].tame(check_string),
        action,
    )


def get_status_body(helper: Helper) -> str:
    payload = helper.payload
    if payload["target_url"]:
        status = "[{}]({})".format(
            payload["state"].tame(check_string),
            payload["target_url"].tame(check_string),
        )
    else:
        status = payload["state"].tame(check_string)
    return "[{}]({}) changed its status to {}.".format(
        get_short_sha(payload["sha"].tame(check_string)),
        payload["commit"]["html_url"].tame(check_string),
        status,
    )


def get_locked_or_unlocked_pull_request_body(helper: Helper) -> str:
    payload = helper.payload

    action = payload["action"].tame(check_string)

    message = "{sender} has locked [PR #{pr_number}]({pr_url}) as {reason} and limited conversation to collaborators."
    if action == "unlocked":
        message = "{sender} has unlocked [PR #{pr_number}]({pr_url})."
    if payload["pull_request"]["active_lock_reason"]:
        active_lock_reason = payload["pull_request"]["active_lock_reason"].tame(check_string)
    else:
        active_lock_reason = None
    return message.format(
        sender=get_sender_name(payload),
        pr_number=payload["pull_request"]["number"].tame(check_int),
        pr_url=payload["pull_request"]["html_url"].tame(check_string),
        reason=active_lock_reason,
    )


def get_pull_request_auto_merge_body(helper: Helper) -> str:
    payload = helper.payload

    action = payload["action"].tame(check_string)

    message = "{sender} has enabled auto merge for [PR #{pr_number}]({pr_url})."
    if action == "auto_merge_disabled":
        message = "{sender} has disabled auto merge for [PR #{pr_number}]({pr_url})."
    return message.format(
        sender=get_sender_name(payload),
        pr_number=payload["pull_request"]["number"].tame(check_int),
        pr_url=payload["pull_request"]["html_url"].tame(check_string),
    )


def get_pull_request_ready_for_review_body(helper: Helper) -> str:
    payload = helper.payload

    message = "**{sender}** has marked [PR #{pr_number}]({pr_url}) as ready for review."
    return message.format(
        sender=get_sender_name(payload),
        pr_number=payload["pull_request"]["number"].tame(check_int),
        pr_url=payload["pull_request"]["html_url"].tame(check_string),
    )


def get_pull_request_review_body(helper: Helper) -> str:
    payload = helper.payload
    include_title = helper.include_title
    title = "for #{} {}".format(
        payload["pull_request"]["number"].tame(check_int),
        payload["pull_request"]["title"].tame(check_string),
    )
    return get_pull_request_event_message(
        user_name=get_sender_name(payload),
        action="submitted",
        url=payload["review"]["html_url"].tame(check_string),
        type="PR review",
        title=title if include_title else None,
        message=payload["review"]["body"].tame(check_none_or(check_string)),
    )


def get_pull_request_review_comment_body(helper: Helper) -> str:
    payload = helper.payload
    include_title = helper.include_title
    action = payload["action"].tame(check_string)
    message = None
    if action == "created":
        message = payload["comment"]["body"].tame(check_string)

    title = "on #{} {}".format(
        payload["pull_request"]["number"].tame(check_int),
        payload["pull_request"]["title"].tame(check_string),
    )

    return get_pull_request_event_message(
        user_name=get_sender_name(payload),
        action=action,
        url=payload["comment"]["html_url"].tame(check_string),
        message=message,
        type="PR review comment",
        title=title if include_title else None,
    )


def get_pull_request_review_requested_body(helper: Helper) -> str:
    payload = helper.payload
    include_title = helper.include_title

    sender = get_sender_name(payload)
    pr_number = payload["pull_request"]["number"].tame(check_int)
    pr_url = payload["pull_request"]["html_url"].tame(check_string)
    message = "**{sender}** requested {reviewers} for a review on [PR #{pr_number}]({pr_url})."
    message_with_title = (
        "**{sender}** requested {reviewers} for a review on [PR #{pr_number} {title}]({pr_url})."
    )
    body = message_with_title if include_title else message

    if "requested_reviewer" in payload:
        reviewer = payload["requested_reviewer"]
        reviewers = "[{login}]({html_url})".format(
            login=reviewer["login"].tame(check_string),
            html_url=reviewer["html_url"].tame(check_string),
        )
    else:
        team_reviewer = payload["requested_team"]
        reviewers = "[{name}]({html_url})".format(
            name=team_reviewer["name"].tame(check_string),
            html_url=team_reviewer["html_url"].tame(check_string),
        )

    return body.format(
        sender=sender,
        reviewers=reviewers,
        pr_number=pr_number,
        pr_url=pr_url,
        title=payload["pull_request"]["title"].tame(check_string) if include_title else None,
    )


def get_check_run_body(helper: Helper) -> str:
    payload = helper.payload
    template = """
Check [{name}]({html_url}) {status} ({conclusion}). ([{short_hash}]({commit_url}))
""".strip()

    kwargs = {
        "name": payload["check_run"]["name"].tame(check_string),
        "html_url": payload["check_run"]["html_url"].tame(check_string),
        "status": payload["check_run"]["status"].tame(check_string),
        "short_hash": get_short_sha(payload["check_run"]["head_sha"].tame(check_string)),
        "commit_url": "{}/commit/{}".format(
            payload["repository"]["html_url"].tame(check_string),
            payload["check_run"]["head_sha"].tame(check_string),
        ),
        "conclusion": payload["check_run"]["conclusion"].tame(check_string),
    }

    return template.format(**kwargs)


def get_star_body(helper: Helper) -> str:
    payload = helper.payload
    template = "[{user}]({user_url}) {action} the repository [{repo}]({url})."
    return template.format(
        user=get_sender_name(payload),
        user_url=get_sender_url(payload),
        action="starred" if payload["action"].tame(check_string) == "created" else "unstarred",
        repo=get_repository_full_name(payload),
        url=payload["repository"]["html_url"].tame(check_string),
    )


def get_ping_body(helper: Helper) -> str:
    payload = helper.payload
    return get_setup_webhook_message("GitHub", get_sender_name(payload))


def get_cancelled_body(helper: Helper) -> str:
    payload = helper.payload
    template = "{user_name} cancelled their {subscription} subscription."
    return template.format(
        user_name=get_sender_name(payload),
        subscription=get_subscription(payload),
    ).rstrip()


def get_created_body(helper: Helper) -> str:
    payload = helper.payload
    template = "{user_name} subscribed for {subscription}."
    return template.format(
        user_name=get_sender_name(payload),
        subscription=get_subscription(payload),
    ).rstrip()


def get_edited_body(helper: Helper) -> str:
    payload = helper.payload
    template = "{user_name} changed who can see their sponsorship from {prior_privacy_level} to {privacy_level}."
    return template.format(
        user_name=get_sender_name(payload),
        prior_privacy_level=payload["changes"]["privacy_level"]["from"].tame(check_string),
        privacy_level=payload["sponsorship"]["privacy_level"].tame(check_string),
    ).rstrip()


def get_pending_cancellation_body(helper: Helper) -> str:
    payload = helper.payload
    template = "{user_name}'s {subscription} subscription will be cancelled on {effective_date}."
    return template.format(
        user_name=get_sender_name(payload),
        subscription=get_subscription(payload),
        effective_date=get_effective_date(payload),
    ).rstrip()


def get_pending_tier_change_body(helper: Helper) -> str:
    payload = helper.payload
    template = "{user_name}'s subscription will change from {prior_subscription} to {subscription} on {effective_date}."
    return template.format(
        user_name=get_sender_name(payload),
        prior_subscription=get_prior_subscription(payload),
        subscription=get_subscription(payload),
        effective_date=get_effective_date(payload),
    ).rstrip()


def get_tier_changed_body(helper: Helper) -> str:
    payload = helper.payload
    template = "{user_name} changed their subscription from {prior_subscription} to {subscription}."
    return template.format(
        user_name=get_sender_name(payload),
        prior_subscription=get_prior_subscription(payload),
        subscription=get_subscription(payload),
    ).rstrip()


def get_subscription(payload: WildValue) -> str:
    return payload["sponsorship"]["tier"]["name"].tame(check_string)


def get_effective_date(payload: WildValue) -> str:
    effective_date = payload["effective_date"].tame(check_string)[:10]
    return (
        datetime.strptime(effective_date, "%Y-%m-%d")
        .replace(tzinfo=timezone.utc)
        .strftime("%B %d, %Y")
    )


def get_prior_subscription(payload: WildValue) -> str:
    return payload["changes"]["tier"]["from"]["name"].tame(check_string)


def get_repository_name(payload: WildValue) -> str:
    return payload["repository"]["name"].tame(check_string)


def get_repository_full_name(payload: WildValue) -> str:
    return payload["repository"]["full_name"].tame(check_string)


def get_organization_name(payload: WildValue) -> str:
    return payload["organization"]["login"].tame(check_string)


def get_sender_name(payload: WildValue) -> str:
    return payload["sender"]["login"].tame(check_string)


def get_sender_url(payload: WildValue) -> str:
    return payload["sender"]["html_url"].tame(check_string)


def get_branch_name_from_ref(ref_string: str) -> str:
    return re.sub(r"^refs/heads/", "", ref_string)


def get_tag_name_from_ref(ref_string: str) -> str:
    return re.sub(r"^refs/tags/", "", ref_string)


def is_commit_push_event(payload: WildValue) -> bool:
    return payload["ref"].tame(check_string).startswith("refs/heads/")


def is_merge_queue_push_event(payload: WildValue) -> bool:
    return payload["ref"].tame(check_string).startswith("refs/heads/gh-readonly-queue/")


def is_pull_request_comment_event(payload: WildValue) -> bool:
    # When a comment is made on a PR, the event still has the header
    # "issue_comment", but the payload has a "pull_request" key.
    # This is just a workaround to get the correct topic.
    if "pull_request" in payload["issue"]:
        return True
    return False


def get_topic_based_on_type(payload: WildValue, event: str) -> str:
    if "pull_request" in event:
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repository_name(payload),
            type="PR",
            id=payload["pull_request"]["number"].tame(check_int),
            title=payload["pull_request"]["title"].tame(check_string),
        )
    elif event.startswith("issue"):
        type_for_topic = "PR" if is_pull_request_comment_event(payload) else "issue"
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repository_name(payload),
            type=type_for_topic,
            id=payload["issue"]["number"].tame(check_int),
            title=payload["issue"]["title"].tame(check_string),
        )
    elif event.startswith("deployment"):
        return "{} / Deployment on {}".format(
            get_repository_name(payload),
            payload["deployment"]["environment"].tame(check_string),
        )
    elif event == "membership":
        return "{} organization".format(payload["organization"]["login"].tame(check_string))
    elif event == "team":
        return "team {}".format(payload["team"]["name"].tame(check_string))
    elif event == "push_commits":
        return TOPIC_WITH_BRANCH_TEMPLATE.format(
            repo=get_repository_name(payload),
            branch=get_branch_name_from_ref(payload["ref"].tame(check_string)),
        )
    elif event == "gollum":
        return TOPIC_WITH_BRANCH_TEMPLATE.format(
            repo=get_repository_name(payload),
            branch="wiki pages",
        )
    elif event == "ping":
        if not payload.get("repository"):
            return get_organization_name(payload)
    elif event == "check_run":
        return f"{get_repository_name(payload)} / checks"
    elif event.startswith("discussion"):
        return TOPIC_FOR_DISCUSSION.format(
            repo=get_repository_name(payload),
            number=payload["discussion"]["number"].tame(check_int),
            title=payload["discussion"]["title"].tame(check_string),
        )
    elif event in SPONSORS_EVENT_TYPES:
        return "sponsors"

    return get_repository_name(payload)


EVENT_FUNCTION_MAPPER: Dict[str, Callable[[Helper], str]] = {
    "commit_comment": get_commit_comment_body,
    "closed_pull_request": get_closed_pull_request_body,
    "create": partial(get_create_or_delete_body, "created"),
    "check_run": get_check_run_body,
    "delete": partial(get_create_or_delete_body, "deleted"),
    "deployment": get_deployment_body,
    "deployment_status": get_change_deployment_status_body,
    "discussion": get_discussion_body,
    "discussion_comment": get_discussion_comment_body,
    "fork": get_fork_body,
    "gollum": get_wiki_pages_body,
    "issue_comment": get_issue_comment_body,
    "issue_labeled_or_unlabeled": get_issue_labeled_or_unlabeled_body,
    "issue_milestoned_or_demilestoned": get_issue_milestoned_or_demilestoned_body,
    "issues": get_issue_body,
    "member": get_member_body,
    "membership": get_membership_body,
    "opened_pull_request": get_opened_or_update_pull_request_body,
    "updated_pull_request": get_opened_or_update_pull_request_body,
    "assigned_or_unassigned_pull_request": get_assigned_or_unassigned_pull_request_body,
    "page_build": get_page_build_body,
    "ping": get_ping_body,
    "public": get_public_body,
    "pull_request_ready_for_review": get_pull_request_ready_for_review_body,
    "pull_request_review": get_pull_request_review_body,
    "pull_request_review_comment": get_pull_request_review_comment_body,
    "pull_request_review_requested": get_pull_request_review_requested_body,
    "pull_request_auto_merge": get_pull_request_auto_merge_body,
    "locked_or_unlocked_pull_request": get_locked_or_unlocked_pull_request_body,
    "push_commits": get_push_commits_body,
    "push_tags": get_push_tags_body,
    "release": get_release_body,
    "repository": get_repository_body,
    "star": get_star_body,
    "status": get_status_body,
    "team": get_team_body,
    "team_add": get_add_team_body,
    "watch": get_watch_body,
    "cancelled": get_cancelled_body,
    "created": get_created_body,
    "edited": get_edited_body,
    "pending_cancellation": get_pending_cancellation_body,
    "pending_tier_change": get_pending_tier_change_body,
    "tier_changed": get_tier_changed_body,
}

SPONSORS_EVENT_TYPES = [
    "cancelled",
    "created",
    "edited",
    "pending_cancellation",
    "pending_tier_change",
    "tier_changed",
]

IGNORED_EVENTS = [
    "check_suite",
    "label",
    "meta",
    "milestone",
    "organization",
    "project_card",
    "push__merge_queue",
    "repository_vulnerability_alert",
]

IGNORED_PULL_REQUEST_ACTIONS = [
    "approved",
    "converted_to_draft",
    "labeled",
    "review_request_removed",
    "unlabeled",
]

IGNORED_TEAM_ACTIONS = [
    # These are actions that are well documented by github
    # (https://docs.github.com/en/developers/webhooks-and-events/webhook-events-and-payloads)
    # but we ignore them for now, possibly just due to laziness.
    # One curious example here is team/added_to_repository, which is
    # possibly the same as team_add.
    "added_to_repository",
    "created",
    "deleted",
    "removed_from_repository",
]

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


@webhook_view("GitHub", notify_bot_owner_on_invalid_json=True, all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_github_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    branches: Optional[str] = None,
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    """
    GitHub sends the event as an HTTP header.  We have our
    own Zulip-specific concept of an event that often maps
    directly to the X-GitHub-Event header's event, but we sometimes
    refine it based on the payload.
    """
    header_event = validate_extract_webhook_http_header(request, "X-GitHub-Event", "GitHub")

    event = get_zulip_event_name(header_event, payload, branches)
    if event is None:
        # This is nothing to worry about--get_event() returns None
        # for events that are valid but not yet handled by us.
        # See IGNORED_EVENTS, for example.
        return json_success(request)
    topic_name = get_topic_based_on_type(payload, event)

    body_function = EVENT_FUNCTION_MAPPER[event]

    helper = Helper(
        request=request,
        payload=payload,
        include_title=user_specified_topic is not None,
    )
    body = body_function(helper)

    check_send_webhook_message(request, user_profile, topic_name, body, event)
    return json_success(request)


def get_zulip_event_name(
    header_event: str,
    payload: WildValue,
    branches: Optional[str],
) -> Optional[str]:
    """
    Usually, we return an event name that is a key in EVENT_FUNCTION_MAPPER.

    We return None for an event that we know we don't want to handle.
    """
    if header_event == "pull_request":
        action = payload["action"].tame(check_string)
        if action in ("opened", "reopened"):
            return "opened_pull_request"
        elif action in ("synchronize", "edited"):
            return "updated_pull_request"
        if action in ("assigned", "unassigned"):
            return "assigned_or_unassigned_pull_request"
        if action == "closed":
            return "closed_pull_request"
        if action == "review_requested":
            return "pull_request_review_requested"
        if action == "ready_for_review":
            return "pull_request_ready_for_review"
        if action in ("locked", "unlocked"):
            return "locked_or_unlocked_pull_request"
        if action in ("auto_merge_enabled", "auto_merge_disabled"):
            return "pull_request_auto_merge"
        if action in IGNORED_PULL_REQUEST_ACTIONS:
            return None
    elif header_event == "push":
        if is_merge_queue_push_event(payload):
            return None
        if is_commit_push_event(payload):
            if branches is not None:
                branch = get_branch_name_from_ref(payload["ref"].tame(check_string))
                if branches.find(branch) == -1:
                    return None
            return "push_commits"
        else:
            return "push_tags"
    elif header_event == "check_run":
        if payload["check_run"]["status"].tame(check_string) != "completed":
            return None
        return header_event
    elif header_event == "team":
        action = payload["action"].tame(check_string)
        if action == "edited":
            return "team"
        if action in IGNORED_TEAM_ACTIONS:
            # no need to spam our logs, we just haven't implemented it yet
            return None
        else:
            # this means GH has actually added new actions since September 2020,
            # so it's a bit more cause for alarm
            raise UnsupportedWebhookEventTypeError(f"unsupported team action {action}")
    elif header_event == "issues":
        action = payload["action"].tame(check_string)
        if action in ("labeled", "unlabeled"):
            return "issue_labeled_or_unlabeled"
        if action in ("milestoned", "demilestoned"):
            return "issue_milestoned_or_demilestoned"
        else:
            return "issues"
    elif header_event in EVENT_FUNCTION_MAPPER:
        return header_event
    elif header_event in IGNORED_EVENTS:
        return None

    complete_event = "{}:{}".format(
        header_event, payload.get("action", "???").tame(check_string)
    )  # nocoverage
    raise UnsupportedWebhookEventTypeError(complete_event)
