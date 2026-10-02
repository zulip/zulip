from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_float, check_int, check_string, check_union
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

# Azure Monitor sends alerts using the "common alert schema"; see:
# https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-common-schema

# Supported Azure Monitor alert types. New signal types (e.g. "Log",
# "Activity Log") will be added here alongside their handlers.
ALL_EVENT_TYPES = ["metric_alert"]

SIGNAL_TYPE_TO_EVENT_TYPE = {
    "Metric": "metric_alert",
}

# Azure sends operators as SDK enum values; render them as natural English.
# https://learn.microsoft.com/en-us/rest/api/monitor/metric-alerts/create-or-update#operator
OPERATOR_PHRASE = {
    "GreaterThan": "greater than",
    "GreaterThanOrEqual": "greater than or equal to",
    "LessThan": "less than",
    "LessThanOrEqual": "less than or equal to",
    "Equals": "equal to",
}

METRIC_ALERT_HEADER_FIRED = ":alert: **FIRING** (severity {severity})"
METRIC_ALERT_HEADER_RESOLVED = ":squared_ok: **RESOLVED**"

METRIC_ALERT_CRITERION_FIRED = (
    "**{metric_name}** ({aggregation}) is **{metric_value}**, "
    "which is {operator_phrase} the threshold of **{threshold}**."
)
METRIC_ALERT_CRITERION_RESOLVED = (
    "**{metric_name}** ({aggregation}) is **{metric_value}**, "
    "no longer {operator_phrase} the threshold of **{threshold}**."
)


def format_metric_criterion(criterion: WildValue, monitor_condition: str) -> str:
    operator = criterion["operator"].tame(check_string)
    operator_phrase = OPERATOR_PHRASE.get(operator)
    if operator_phrase is None:
        raise UnsupportedWebhookEventTypeError(operator)  # nocoverage

    template = (
        METRIC_ALERT_CRITERION_FIRED
        if monitor_condition == "Fired"
        else METRIC_ALERT_CRITERION_RESOLVED
    )
    return template.format(
        metric_name=criterion["metricName"].tame(check_string),
        aggregation=criterion["timeAggregation"].tame(check_string),
        metric_value=criterion["metricValue"].tame(check_union([check_int, check_float])),
        operator_phrase=operator_phrase,
        threshold=criterion["threshold"].tame(check_string),
    )


def get_metric_alert_body(essentials: WildValue, alert_context: WildValue) -> str:
    # Possible values for monitorCondition ("Fired", "Resolved"); see:
    # https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-common-schema#essentials-fields
    monitor_condition = essentials["monitorCondition"].tame(check_string)
    if monitor_condition == "Fired":
        header = METRIC_ALERT_HEADER_FIRED.format(
            severity=essentials["severity"].tame(check_string)
        )
    elif monitor_condition == "Resolved":
        header = METRIC_ALERT_HEADER_RESOLVED
    else:
        raise UnsupportedWebhookEventTypeError(monitor_condition)  # nocoverage

    return "\n\n".join(
        [
            header,
            *(
                format_metric_criterion(criterion, monitor_condition)
                for criterion in alert_context["condition"]["allOf"]
            ),
        ]
    )


@webhook_view("AzureMonitor", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_azuremonitor_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    essentials = payload["data"]["essentials"]
    alert_context = payload["data"]["alertContext"]
    signal_type = essentials["signalType"].tame(check_string)

    event_type = SIGNAL_TYPE_TO_EVENT_TYPE.get(signal_type)
    if event_type is None:
        raise UnsupportedWebhookEventTypeError(signal_type)  # nocoverage

    alert_rule = essentials["alertRule"].tame(check_string)
    body = get_metric_alert_body(essentials, alert_context)

    check_send_webhook_message(request, user_profile, alert_rule, body, event_type)
    return json_success(request)
