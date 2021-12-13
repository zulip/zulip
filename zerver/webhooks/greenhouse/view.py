from typing import Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict, check_list, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MESSAGE_TEMPLATE = """
{action} {first_name} {last_name} (ID: {candidate_id}), applying for:
* **Role**: {role}
* **Emails**: {emails}
* **Attachments**: {attachments}
""".strip()


def dict_list_to_string(var_name: str, some_list: object) -> str:
    internal_template = ""
    for i, item in enumerate(check_list(check_dict())(var_name, some_list)):
        item_type = check_string(f"{var_name}[i] type", item.get("type", "")).title()
        item_value = item.get("value")
        item_url = item.get("url")
        if item_type and item_value:
            internal_template += f"{item_value} ({item_type}), "
        elif item_type and item_url:
            internal_template += f"[{item_type}]({item_url}), "

    internal_template = internal_template[:-2]
    return internal_template


@webhook_view("Greenhouse")
@has_request_variables
def api_greenhouse_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, object] = REQ(argument_type="body", json_validator=check_dict()),
) -> HttpResponse:
    if payload["action"] == "ping":
        return json_success()

    application = check_dict()(
        "payload application", check_dict()("payload", payload.get("payload")).get("application")
    )
    if payload["action"] == "update_candidate":
        candidate = check_dict()(
            "payload candidate", check_dict()("payload", payload.get("payload")).get("candidate")
        )
    else:
        candidate = check_dict()("payload application candidate", application.get("candidate"))
    action = check_string("action", payload.get("action")).replace("_", " ").title()

    body = MESSAGE_TEMPLATE.format(
        action=action,
        first_name=candidate["first_name"],
        last_name=candidate["last_name"],
        candidate_id=str(candidate["id"]),
        role=check_list(check_dict())("payload application jobs", application.get("jobs"))[0][
            "name"
        ],
        emails=dict_list_to_string(
            "payload application candidate email_addresses", candidate.get("email_addresses")
        ),
        attachments=dict_list_to_string(
            "payload application candidate attachments", candidate.get("attachments")
        ),
    )

    topic = "{} - {}".format(action, str(candidate["id"]))

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()
