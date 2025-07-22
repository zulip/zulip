from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
import json

from zerver.decorator import webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Redmine")
def api_redmine_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: dict[str, Any] = None,
    **kwargs: Any,
) -> HttpResponse:
    if payload is None:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"result": "error", "msg": "Invalid JSON payload"}, status=400)
    event = payload.get("event")
    if event == "issue_created":
        issue = payload["issue"]
        project = issue["project"]["name"]
        tracker = issue["tracker"]["name"]
        status = issue["status"]["name"]
        priority = issue["priority"]["name"]
        author = issue["author"]["name"]
        assigned_to = issue.get("assigned_to", {}).get("name", "Unassigned")
        subject = issue["subject"]
        description = issue.get("description", "")
        url = issue["url"]
        issue_id = issue["id"]

        topic = f"Issue #{issue_id}: {subject}"
        content = (
            f"**New issue created in _{project}_**\n"
            f"**Type:** {tracker}\n"
            f"**Status:** {status}\n"
            f"**Priority:** {priority}\n"
            f"**Author:** {author}\n"
            f"**Assigned to:** {assigned_to}\n"
            f"**Description:**\n{description}\n"
            f"[View issue]({url})"
        )
        check_send_webhook_message(request, user_profile, topic, content)
        from zerver.lib.response import json_success
        return json_success(request)
    else:
        return JsonResponse(
            {"result": "error", "msg": f"Unsupported event type: {event}"}, status=400
        )
