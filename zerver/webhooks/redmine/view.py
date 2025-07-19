from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Redmine")
@typed_endpoint
def api_redmine_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    if "issue" in payload:
        issue = payload["issue"]
        action = payload.get("action", "updated").tame(check_string)

        # Extract issue details
        issue_id = issue.get("id", 0).tame(check_int) if "id" in issue else 0
        subject = issue["subject"].tame(check_string)
        project_name = issue["project"]["name"].tame(check_string)
        author = issue["author"]["name"].tame(check_string)

        # Create topic
        if issue_id:
            topic = f"{project_name} - Issue #{issue_id}"
        else:
            topic = f"{project_name} - Issue"

        # Create message body
        if action == "opened":
            body = f"**New issue created:** {subject}\n**Author:** {author}"
        elif action == "updated":
            body = f"**Issue updated:** {subject}\n**Updated by:** {author}"
        elif action == "closed":
            body = f"**Issue closed:** {subject}\n**Closed by:** {author}"
        else:
            body = f"**Issue {action}:** {subject}\n**Author:** {author}"

        # Add description if available
        description = issue.get("description")
        if description:
            desc_text = description.tame(check_none_or(check_string))
            if desc_text and action == "opened":
                body += f"\n**Description:** {desc_text}"

        check_send_webhook_message(request, user_profile, topic, body)

    elif "repository" in payload and "changesets" in payload:
        # Handle repository commits
        repository = payload["repository"]
        changesets = payload.get("changesets", [])

        if changesets:
            repo_name = repository["name"].tame(check_string)
            project_name = repository["project"]["name"].tame(check_string)

            topic = f"{project_name} - {repo_name}"
            body = f"**New commits to {repo_name}:**\n"

            for changeset in changesets:
                revision = changeset["revision"].tame(check_string)
                comments = changeset["comments"].tame(check_string)
                author = changeset["user"]["name"].tame(check_string)

                body += f"* [`{revision[:8]}`] {comments} ({author})\n"

            check_send_webhook_message(request, user_profile, topic, body.rstrip())

    return json_success(request)
