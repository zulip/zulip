from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALL_EVENT_TYPES = ["fired", "resolved"]


def get_body(alert_rule: str, essentials: WildValue) -> str:
    monitor_condition = essentials["monitorCondition"].tame(check_string)
    signal_type = essentials["signalType"].tame(check_string)
    severity = essentials["severity"].tame(check_string)
    monitoring_service = essentials["monitoringService"].tame(check_string)
    configuration_items = (
        ", ".join(item.tame(check_string) for item in essentials["configurationItems"]) or "None"
    )
    description = essentials.get("description").tame(check_none_or(check_string)) or ""

    if monitor_condition == "Fired":
        status_emoji = ":alert:"
        time_label = "Fired at"
        time = essentials["firedDateTime"].tame(check_string)
    elif monitor_condition == "Resolved":
        status_emoji = ":squared_ok:"
        time_label = "Resolved at"
        time = essentials["resolvedDateTime"].tame(check_string)
    else:
        raise UnsupportedWebhookEventTypeError(monitor_condition)

    lines = [
        f"{status_emoji} Alert rule **{alert_rule}** was {monitor_condition.lower()}.",
        "",
        f"* **Signal type**: {signal_type}",
        f"* **Severity**: {severity}",
        f"* **Monitoring service**: {monitoring_service}",
        f"* **Affected resources**: {configuration_items}",
        f"* **{time_label}**: {time}",
    ]
    if description:
        lines.append(f"* **Description**: {description}")

    return "\n".join(lines)


@webhook_view("AzureAlert", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_azurealert_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    essentials = payload["data"]["essentials"]
    alert_rule = essentials["alertRule"].tame(check_string)
    monitor_condition = essentials["monitorCondition"].tame(check_string)

    body = get_body(alert_rule, essentials)
    check_send_webhook_message(request, user_profile, alert_rule, body, monitor_condition.lower())

    return json_success(request)
