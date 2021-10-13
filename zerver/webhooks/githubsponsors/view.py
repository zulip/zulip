# datetime
import datetime
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


class DatetimeParser:
    def parse(self, date: str) -> str:
        date_frm_payload = [int(i) for i in date.split("T")[0].split("-")]
        date_string_object = datetime.datetime(
            date_frm_payload[0], date_frm_payload[1], date_frm_payload[2]
        )
        formatted_date = date_string_object.strftime("%d %B %Y, %A")
        return formatted_date


@webhook_view("GitHubSponsors")
@has_request_variables
def api_githubsponsors_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:

    # VARIABLES FROM THE PAYLOAD
    parser = (
        DatetimeParser()
    )  # helper function to parse datetime object received from the payload to readable string format
    ACTION = payload.get("action")
    SENDER = payload["sender"]["login"]
    if ACTION == "created":
        TIER_NAME = payload["sponsorship"]["tier"]["name"]
        DATE_SUBSCRIBED = parser.parse(payload["sponsorship"]["tier"]["created_at"])
    if ACTION == "pending_tier_change":
        DATE_CHANGED = parser.parse(payload["effective_date"])
        TIER_FROM = payload["changes"]["tier"]["from"]["name"]
        TIER_TO = payload["sponsorship"]["tier"]["name"]

    # MESSAGE CONSTRUCTION
    TOPICS = {
        "created": "New Sponsorship Subscription",
        "pending_tier_change": "Subscription Change",
        "cancelled": "Cancelled Subscription",
    }
    ACTIONS = {
        "created": ":confetti: New Subscription for a Sponsorship! :confetti:",
        "pending_tier_change": ":bullhorn: Subscription Tier Change :bullhorn:",
        "cancelled": ":warning: Sponsorship Cancelled! :warning:",
    }

    body = ACTIONS[ACTION]
    if ACTION == "created":
        body_template = '\n{sender} subscribed for a "{tier_name}" Sponsorship on {date_subscribed}'
        body += body_template.format(
            sender=SENDER, tier_name=TIER_NAME, date_subscribed=DATE_SUBSCRIBED
        )
    if ACTION == "pending_tier_change":
        body_template = '\n{sender} changed their Sponsor subscription from "{tier_from}" to "{tier_to}" effective from {date_changed}'
        body += body_template.format(
            sender=SENDER, tier_from=TIER_FROM, tier_to=TIER_TO, date_changed=DATE_CHANGED
        )
    if ACTION == "cancelled":
        body_template = "\nSomebody cancelled their sponsorship subscription"
        body += body_template

    topic = TOPICS[ACTION]

    # SENDING THE MESSAGE
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()
