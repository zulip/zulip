# Webhooks for external integrations.
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import get_short_sha
from zerver.models import UserProfile

MESSAGE_TEMPLATE = """
Build update (see [build log]({build_log_url})):
* **Author**: {author}
* **Commit**: [{commit_id}]({commit_url})
* **Status**: {status} {emoji}
""".strip()

ALL_EVENT_TYPES = ["first-fail", "stop", "received"]


@webhook_view("SolanoLabs", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_solano_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    event = payload["event"].tame(check_string)
    topic = "build update"
    if event == "test":
        return handle_test_event(request, user_profile, topic)
    try:
        author = payload["committers"][0].tame(check_string)
    except ValidationError:
        author = "Unknown"
    status = payload["status"].tame(check_string)
    build_log = payload["url"].tame(check_string)
    repository = payload["repository"]["url"].tame(check_string)
    commit_id = payload["commit_id"].tame(check_string)

    good_status = ["passed"]
    bad_status = ["failed", "error"]
    neutral_status = ["running"]
    emoji = ""
    if status in good_status:
        emoji = ":thumbs_up:"
    elif status in bad_status:
        emoji = ":thumbs_down:"
    elif status in neutral_status:
        emoji = ":arrows_counterclockwise:"

    # If the service is not one of the following, the URL is of the repository home, not the individual
    # commit itself.
    commit_url = repository.split("@")[1]
    if "github" in repository:
        commit_url += f"/commit/{commit_id}"
    elif "bitbucket" in repository:
        commit_url += f"/commits/{commit_id}"
    elif "gitlab" in repository:
        commit_url += f"/pipelines/{commit_id}"

    body = MESSAGE_TEMPLATE.format(
        author=author,
        build_log_url=build_log,
        commit_id=get_short_sha(commit_id),
        commit_url=commit_url,
        status=status,
        emoji=emoji,
    )

    check_send_webhook_message(request, user_profile, topic, body, event)
    return json_success(request)


def handle_test_event(request: HttpRequest, user_profile: UserProfile, topic: str) -> HttpResponse:
    body = "Solano webhook set up correctly."
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)
