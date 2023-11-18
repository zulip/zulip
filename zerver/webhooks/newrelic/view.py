# Webhooks for external integrations.

from typing import Dict, Optional

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
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

TIME_STAMPS_MAP: Dict[str, str] = {
    "CREATED": "createdAt",
    "ACTIVATED": "activatedAt",
    "UPDATED": "updatedAt",
    "CLOSED": "closedAt",
    "ACKNOWLEDGED": "acknowledgedAt",
}

INCIDENT_STATES = ["CREATED", "ACTIVATED", "CLOSED"]

DEFAULT_NEWRELIC_URL = "https://one.newrelic.com/alerts-ai"

INTEGRATION_LAST_UPDATED = "June 2024"

BASE_NOTIFICATION_WRAP_TEMPLATE = """
```spoiler {header}
{body}
```
"""

NOTIFICATION_HEADER = "{priority_symbol} {priority} **priority [issue]({incident_url}) has been **{status}** at** <time: {time_updated_str} >"

NOTIFICATION_BODY_TEMPLATE = """
**[{title}]({incident_url})**

| :file:  **Incident details**  |
|:--------|
|:checkbox: Alert policy: {alert_policy_str}|
|:spiral_notepad: Conditions: {conditions_str}|
|:warning: Total incidents: **{total_incidents}**|
|:clock: Incident created at: <time: {time_created_str} > |
"""

TOPIC_TEMPLATE = "{state} {priority} priority"

FALL_BACK_NOTIFICATION_TEMPLATE = """
```spoiler :danger: An [incident](https://one.newrelic.com/alerts-ai) updated

**Warning: Unable to send the default notification format**
At least one essential field is missing from the payload. Try
to reset the payload template to the default from New Relic
if you're unsure.

Please reach out to [the Zulip development community](https://chat.zulip.org/#narrow/stream/127-integrations)
if you think this integration is out-of-date.
> *Integration last updated: **{integration_last_updated}***
```
"""

FALL_BACK_TOPIC_TEMPLATE = "Incident alerts"

ZULIP_CUSTOM_FIELDS_KEY = "zulipCustomFields"

ESSENTIAL_FIELDS = [
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


def get_iso_timestamp_str(payload: WildValue, event_type: str) -> Optional[str]:
    unix_time = payload.get(event_type, "N/A").tame(check_union([check_int, check_string]))

    if unix_time == "N/A":
        return None
    else:
        return str(unix_milliseconds_to_timestamp(unix_time, "newrelic"))


def check_essential_fields(payload: WildValue) -> bool:
    """
    Checks if the essential fields are present in the payload.
    """
    return all(key in payload for key in ESSENTIAL_FIELDS)


def parse_payload(payload: WildValue) -> Dict[str, Optional[str]]:
    """
    Parses the payload and turn it into a dictionary of key-value
    pairs that can be used to format the message body.
    """
    TIME_STAMP_STR: Dict[str, Optional[str]] = {
        key: get_iso_timestamp_str(payload, value) for key, value in TIME_STAMPS_MAP.items()
    }

    priority = payload.get("priority").tame(check_string_in(PRIORITIES.keys()))
    priority_symbol = PRIORITIES.get(priority, ":alert:")
    conditions_list = payload.get("alertConditionNames", ["Unknown condition"]).tame(
        check_list(check_string)
    )
    conditions_str = ", ".join([f"**`{c}`**" for c in conditions_list])
    policy_list = payload.get("alertPolicyNames", ["Unknown policy"]).tame(check_list(check_string))
    alert_policy_str = ", ".join([f"**`{p}`**" for p in policy_list])

    message_context: Dict[str, Optional[str]] = {
        "title": payload.get("title", "No title.").tame(check_string),
        "conditions_str": conditions_str,
        "alert_policy_str": alert_policy_str,
        "time_created_str": TIME_STAMP_STR.get("CREATED"),
        "time_updated_str": TIME_STAMP_STR.get("UPDATED"),
        "incident_url": payload.get("issueUrl", DEFAULT_NEWRELIC_URL).tame(check_string),
        "total_incidents": str(payload["totalIncidents"].tame(check_int)),
        "state": payload.get("state", "UPDATED").tame(check_string_in(INCIDENT_STATES)),
        "status": determine_status(payload, TIME_STAMP_STR),
        "priority": priority,
        "priority_symbol": priority_symbol,
    }

    return message_context


def determine_status(payload: WildValue, time_stamp_map: Dict[str, Optional[str]]) -> str:
    """
    This function infers what type of action was taken on the incident based on the
    timestamps provided in the payload.

    Returns the action taken as a string.
    """
    updated_at = time_stamp_map.get("UPDATED")
    acknowledged_at = time_stamp_map.get("ACKNOWLEDGED")
    created_at = time_stamp_map.get("CREATED")
    closed_at = time_stamp_map.get("CLOSED")

    if updated_at:
        if acknowledged_at and updated_at == acknowledged_at:
            return "ACKNOWLEDGED"
        elif created_at and updated_at == created_at:
            return "ACTIVATED"
        elif closed_at and updated_at == closed_at:
            return "CLOSED"
        else:
            return "UPDATED"
    incident_title = payload.get("title", "No title.").tame(check_string)
    raise UnsupportedWebhookEventTypeError(incident_title)


def generate_additional_info_message(payload: WildValue) -> Optional[str]:
    """
    Parses additional fields from the recommended base payload
    into a presentable block of strings.
    Detail: zerver/webhooks/newrelic/doc.md/#recommended-base-payload-template

    Returns a block of formatted strings.
    """
    owner = payload.get("owner").tame(check_none_or(check_string))
    additional_info_str = f"|:silhouette:  Acknowledged by **{owner}**|\n"
    return None if owner is None else additional_info_str


def generate_custom_field_message(payload: WildValue) -> Optional[str]:
    """
    Parses the custom fields in the "zulipCustomFields" dict in
    the payload by turning the camel case key into words and
    formatting it together with the value into a presentable
    block of strings.
    Detail: zerver/webhooks/newrelic/doc.md/#displaying-custom-fields

    Returns a block of formatted strings.
    """
    body_custom_field_detail: str = ""
    zulip_custom_fields = payload.get(ZULIP_CUSTOM_FIELDS_KEY, {})

    for key, value in zulip_custom_fields.items():
        custom_field_name_str = key.capitalize()
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
                custom_field_detail_str = ", ".join([f"**`{detail}`**" for detail in details])
            else:
                custom_field_detail_str = f"**{details}**"

            custom_field_message = f"|{custom_field_name_str}: {custom_field_detail_str}|\n"
            body_custom_field_detail += custom_field_message
        except ValidationError:
            invalid_field_message = f"|*The **{custom_field_name_str}** contains [unsupported field](/integrations/doc/newrelic#displaying-custom-fields) format.* |\n"
            body_custom_field_detail += invalid_field_message
    return body_custom_field_detail


@webhook_view("NewRelic", all_event_types=INCIDENT_STATES)
@typed_endpoint
def api_newrelic_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    is_complete = check_essential_fields(payload)
    if is_complete:
        message_context = parse_payload(payload)
        body_detail = NOTIFICATION_BODY_TEMPLATE

        additional_info_block = generate_additional_info_message(payload)
        if additional_info_block:
            body_detail += additional_info_block

        custom_payload_block = generate_custom_field_message(payload)
        if custom_payload_block:
            body_detail += custom_payload_block

        body = BASE_NOTIFICATION_WRAP_TEMPLATE.format(header=NOTIFICATION_HEADER, body=body_detail)
        body = body.format(**message_context).strip()
        topic = TOPIC_TEMPLATE.format(
            state=message_context["state"], priority=message_context["priority"]
        ).title()
        check_send_webhook_message(request, user_profile, topic, body, message_context["state"])
    else:
        # Fallback notification
        body = FALL_BACK_NOTIFICATION_TEMPLATE.format(
            integration_last_updated=INTEGRATION_LAST_UPDATED
        )
        topic = FALL_BACK_TOPIC_TEMPLATE
        check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)
