# Webhooks for external integrations.

from typing import TypedDict

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

PRIORITIES = {
    "CRITICAL": ":red_circle:",
    "HIGH": ":orange_circle:",
    "MEDIUM": ":yellow:",
    "LOW": ":blue_circle:",
}

ALL_EVENT_TYPES = ["CREATED", "ACTIVATED", "CLOSED"]

DEFAULT_NEWRELIC_URL = "https://one.newrelic.com/alerts-ai"

NOTIFICATION_TEMPLATE = """
```spoiler {header}
{body}
```
"""
MISSING_FIELDS_NOTIFICATION_BODY = "**Warning**: Unable to use the default notification format because at least one expected field was missing from the incident payload. See [New Relic integration documentation](/integrations/doc/newrelic).\n\n**Missing fields**: {formatted_missing_fields}"

TIME_ELEMENT_TEMPLATE = "<time: {} >"

NOTIFICATION_HEADER = "{priority_symbol} {priority} **priority [issue]({incident_url}) has been **{status}** at** **{time_updated}**"

NOTIFICATION_BODY = """
**[{title}]({incident_url})**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: {alert_policy}|
|:spiral_notepad: Conditions: {conditions}|
|:warning: Total incidents: **{total_incidents}**|
|:clock: Incident created at: {time_created}|
"""

TOPIC_TEMPLATE = "{title}"

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


class TimestampData(TypedDict):
    created: str | None
    updated: str | None
    status: str


def get_timestamp_string(payload: WildValue, event_type: str) -> str | None:
    unix_time = payload.get(event_type, "N/A").tame(check_union([check_int, check_string]))

    if unix_time == "N/A":
        return None
    return str(unix_milliseconds_to_timestamp(unix_time, "newrelic"))


def get_timestamp_data(payload: WildValue) -> TimestampData:
    updated_at = get_timestamp_string(payload, "updatedAt")
    acknowledged_at = get_timestamp_string(payload, "acknowledgedAt")
    created_at = get_timestamp_string(payload, "createdAt")
    closed_at = get_timestamp_string(payload, "closedAt")

    if acknowledged_at and updated_at == acknowledged_at:
        status = "ACKNOWLEDGED"
    elif created_at and updated_at == created_at:
        status = "ACTIVATED"
    elif closed_at and updated_at == closed_at:
        status = "CLOSED"
    else:
        status = "UPDATED"

    return TimestampData(
        created=created_at,
        updated=updated_at,
        status=status,
    )


def check_for_expected_fields(payload: WildValue) -> list[str]:
    return [key for key in EXPECTED_FIELDS if key not in payload]


def parse_payload(payload: WildValue) -> dict[str, str]:
    timestamp_data = get_timestamp_data(payload)

    priority = payload["priority"].tame(check_string_in(PRIORITIES.keys()))
    priority_symbol = PRIORITIES.get(priority, ":alert:")
    conditions_list = payload.get("alertConditionNames", ["Unknown condition"]).tame(
        check_list(check_string)
    )
    conditions = ", ".join([f"**`{c}`**" for c in conditions_list])
    policy_list = payload.get("alertPolicyNames", ["Unknown policy"]).tame(check_list(check_string))
    alert_policy = ", ".join([f"**`{p}`**" for p in policy_list])

    message_context: dict[str, str] = {
        "title": payload["title"].tame(check_string),
        "conditions": conditions,
        "alert_policy": alert_policy,
        "time_created": (
            TIME_ELEMENT_TEMPLATE.format(timestamp_data["created"])
            if timestamp_data["created"]
            else "N/A"
        ),
        "time_updated": (
            TIME_ELEMENT_TEMPLATE.format(timestamp_data["updated"])
            if timestamp_data["updated"]
            else "N/A"
        ),
        "incident_url": payload.get("issueUrl", DEFAULT_NEWRELIC_URL).tame(check_string),
        "total_incidents": str(payload["totalIncidents"].tame(check_int)),
        "state": payload["state"].tame(check_string_in(ALL_EVENT_TYPES)),
        "status": timestamp_data["status"],
        "priority": priority,
        "priority_symbol": priority_symbol,
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
                custom_field_detail = ", ".join([f"**`{detail}`**" for detail in details])
            else:
                custom_field_detail = f"**{details}**"

            custom_field_message = f"|{custom_field_name}: {custom_field_detail}|\n"
            body_custom_field_detail += custom_field_message
        except ValidationError:
            invalid_field_message = (
                f"|The value of **{custom_field_name}** is not a supported data type.|\n"
            )
            body_custom_field_detail += invalid_field_message
    return body_custom_field_detail


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
        header = f":danger: An [incident]({DEFAULT_NEWRELIC_URL}) updated"
        body_detail = MISSING_FIELDS_NOTIFICATION_BODY.format(
            formatted_missing_fields=formatted_missing_fields
        )
        body = NOTIFICATION_TEMPLATE.format(header=header, body=body_detail)
        topic = "Incident alerts"
        check_send_webhook_message(request, user_profile, topic, body)
        return json_success(request)

    message_context = parse_payload(payload)
    body_detail = NOTIFICATION_BODY

    owner = payload.get("owner").tame(check_none_or(check_string))
    body_detail += f"|:silhouette: Acknowledged by **{owner}**|\n" if owner else ""

    body_detail += format_zulip_custom_fields(payload)

    body = NOTIFICATION_TEMPLATE.format(header=NOTIFICATION_HEADER, body=body_detail)
    body = body.format(**message_context)
    topic = TOPIC_TEMPLATE.format(**message_context)
    check_send_webhook_message(request, user_profile, topic, body, message_context["state"])
    return json_success(request)
