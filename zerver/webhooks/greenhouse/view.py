from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string, check_url
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MESSAGE_TEMPLATE = """
{action} {first_name} {last_name} (ID: {candidate_id}), applying for:
* **Role**: {role}
* **Emails**: {emails}
* **Attachments**: {attachments}
""".strip()


def dict_list_to_string(some_list: WildValue) -> str:
    internal_template = ""
    for item in some_list:
        item_type = item.get("type", "").tame(check_string).title()
        item_value = item.get("value").tame(check_none_or(check_string))
        item_url = item.get("url").tame(check_none_or(check_url))
        if item_type and item_value:
            internal_template += f"{item_value} ({item_type}), "
        elif item_type and item_url:
            internal_template += f"[{item_type}]({item_url}), "

    internal_template = internal_template[:-2]
    return internal_template


@webhook_view("Greenhouse")
@typed_endpoint
def api_greenhouse_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    action = payload["action"].tame(check_string)
    if action == "ping":
        return json_success(request)

    if action == "update_candidate":
        candidate = payload["payload"]["candidate"]
    else:
        candidate = payload["payload"]["application"]["candidate"]
    action = action.replace("_", " ").title()
    application = payload["payload"]["application"]

    body = MESSAGE_TEMPLATE.format(
        action=action,
        first_name=candidate["first_name"].tame(check_string),
        last_name=candidate["last_name"].tame(check_string),
        candidate_id=str(candidate["id"].tame(check_int)),
        role=application["jobs"][0]["name"].tame(check_string),
        emails=dict_list_to_string(application["candidate"]["email_addresses"]),
        attachments=dict_list_to_string(application["candidate"]["attachments"]),
    )

    topic = "{} - {}".format(action, str(candidate["id"].tame(check_int)))

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)
