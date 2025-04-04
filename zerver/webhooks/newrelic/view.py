# Webhooks for external integrations.

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import (
    WildValue,
    check_float,
    check_int,
    check_list,
    check_none_or,
    check_string,
    check_string_in,
    check_union,
)
from zerver.lib.webhooks.common import check_send_webhook_message, unix_milliseconds_to_timestamp
from zerver.models import UserProfile

MISSING_FIELDS_NOTIFICATION = """
:danger: A New Relic [incident]({url}) updated

**Warning**: Unable to use the default notification format because at least one expected field was missing from the incident payload. See [New Relic integration documentation](/integrations/doc/newrelic).

**Missing fields**: {formatted_missing_fields}
"""

NOTIFICATION_TEMPLATE = """
{priority_symbol} **[{title}]({incident_url})**

```quote
**Priority**: {priority}
**State**: {state}
**Updated at**: {time_updated}
{owner}
```

```spoiler :file: Incident details
{details}
```
"""

NOTIFICATION_DETAILS = """
- **Alert policies**: {alert_policy}
- **Conditions**: {conditions}
- **Total incidents**: {total_incidents}
- **Incident created at**: {time_created}
"""

ALL_EVENT_TYPES = ["CREATED", "ACTIVATED", "CLOSED"]

PRIORITIES = {
    "CRITICAL": ":red_circle:",
    "HIGH": ":orange_circle:",
    "MEDIUM": ":yellow:",
    "LOW": ":blue_circle:",
}

DEFAULT_NEWRELIC_URL = "https://one.newrelic.com/alerts-ai"


EXPECTED_FIELDS = [
    "issueUrl",
    "title",
    "priority",
    "totalIncidents",
    "state",
    "createdAt",
    "updatedAt",
    "alertPolicyNames",
    "alertConditionNames",
]


def get_timestamp_string(payload: WildValue, event_type: str) -> str:
    # This function is intended to be used only for the "updatedAt"
    # and "createdAt" fields. Theoretically, neither field can be
    # None at any time.
    unix_time = payload[event_type].tame(check_union([check_int, check_string]))
    timestamp = str(unix_milliseconds_to_timestamp(unix_time, "newrelic"))
    return f"<time: {timestamp} >"


def parse_payload(payload: WildValue) -> dict[str, str]:
    priority = payload["priority"].tame(check_string_in(PRIORITIES.keys()))
    priority_symbol = PRIORITIES.get(priority, ":alert:")
    conditions_list = payload.get("alertConditionNames", ["Unknown condition"]).tame(
        check_list(check_string)
    )
    conditions = ", ".join([f"`{c}`" for c in conditions_list])
    policy_list = payload.get("alertPolicyNames", ["Unknown policy"]).tame(check_list(check_string))
    alert_policy = ", ".join([f"`{p}`" for p in policy_list])

    owner = payload.get("owner").tame(check_none_or(check_string))
    acknowledged = ""
    if owner and owner != "N/A":
        acknowledged = f"**Acknowledged by**: {owner}"

    message_context: dict[str, str] = {
        "title": payload["title"].tame(check_string),
        "incident_url": payload.get("issueUrl", DEFAULT_NEWRELIC_URL).tame(check_string),
        "total_incidents": str(payload["totalIncidents"].tame(check_int)),
        "state": payload["state"].tame(check_string_in(ALL_EVENT_TYPES)),
        "time_created": get_timestamp_string(payload, "createdAt"),
        "time_updated": get_timestamp_string(payload, "updatedAt"),
        "priority": priority,
        "priority_symbol": priority_symbol,
        "conditions": conditions,
        "alert_policy": alert_policy,
        "owner": acknowledged,
    }

    return message_context


def format_zulip_custom_fields(payload: WildValue) -> str:
    body_custom_field_detail: str = ""
    zulip_custom_fields = payload.get("zulipCustomFields", {})

    for key, value in zulip_custom_fields.items():
        custom_field_name = key.capitalize()
        try:
            details = value.tame(
                check_none_or(
                    check_union(
                        [
                            check_int,
                            check_float,
                            check_string,
                            check_list(
                                check_none_or(check_union([check_int, check_float, check_string]))
                            ),
                        ]
                    )
                )
            )
            if isinstance(details, list):
                custom_field_detail = ", ".join([f"{detail}" for detail in details])
            else:
                custom_field_detail = f"{details}"

            custom_field_message = f"- **{custom_field_name}**: {custom_field_detail}\n"
            body_custom_field_detail += custom_field_message
        except ValidationError:
            invalid_field_message = (
                f"- **{custom_field_name}**: *Value is not a supported data type*\n"
            )
            body_custom_field_detail += invalid_field_message
    return body_custom_field_detail


def check_for_expected_fields(payload: WildValue) -> list[str]:
    return [key for key in EXPECTED_FIELDS if key not in payload]


@webhook_view("NewRelic", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_newrelic_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    missing_fields = check_for_expected_fields(payload)
    if missing_fields:
        formatted_missing_fields = ", ".join([f"`{fields}`" for fields in missing_fields])
        content = MISSING_FIELDS_NOTIFICATION.format(
            url=DEFAULT_NEWRELIC_URL,
            formatted_missing_fields=formatted_missing_fields,
        )
        topic = "New Relic incident alerts"
        check_send_webhook_message(request, user_profile, topic, content)
        return json_success(request)

    message_context = parse_payload(payload)
    incident_details = NOTIFICATION_DETAILS.format(**message_context)
    incident_details += format_zulip_custom_fields(payload)
    content = NOTIFICATION_TEMPLATE.format(details=incident_details, **message_context)
    topic = message_context["title"]
    check_send_webhook_message(request, user_profile, topic, content, message_context["state"])
    return json_success(request)
