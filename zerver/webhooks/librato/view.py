from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Tuple

import orjson
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALERT_CLEAR = "clear"
ALERT_VIOLATION = "violations"
SNAPSHOT = "image_url"


class LibratoWebhookParser:
    ALERT_URL_TEMPLATE = "https://metrics.librato.com/alerts#/{alert_id}"

    def __init__(self, payload: Mapping[str, Any], attachments: List[Dict[str, Any]]) -> None:
        self.payload = payload
        self.attachments = attachments

    def generate_alert_url(self, alert_id: int) -> str:
        return self.ALERT_URL_TEMPLATE.format(alert_id=alert_id)

    def parse_alert(self) -> Tuple[int, str, str, str]:
        alert = self.payload["alert"]
        alert_id = alert["id"]
        return alert_id, alert["name"], self.generate_alert_url(alert_id), alert["runbook_url"]

    def parse_condition(self, condition: Dict[str, Any]) -> Tuple[str, str, str, str]:
        summary_function = condition["summary_function"]
        threshold = condition.get("threshold", "")
        condition_type = condition["type"]
        duration = condition.get("duration", "")
        return summary_function, threshold, condition_type, duration

    def parse_violation(self, violation: Dict[str, Any]) -> Tuple[str, str]:
        metric_name = violation["metric"]
        recorded_at = datetime.fromtimestamp(violation["recorded_at"], tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return metric_name, recorded_at

    def parse_conditions(self) -> List[Dict[str, Any]]:
        conditions = self.payload["conditions"]
        return conditions

    def parse_violations(self) -> List[Dict[str, Any]]:
        violations = self.payload["violations"]["test-source"]
        return violations

    def parse_snapshot(self, snapshot: Dict[str, Any]) -> Tuple[str, str, str]:
        author_name, image_url, title = (
            snapshot["author_name"],
            snapshot["image_url"],
            snapshot["title"],
        )
        return author_name, image_url, title


class LibratoWebhookHandler(LibratoWebhookParser):
    def __init__(self, payload: Mapping[str, Any], attachments: List[Dict[str, Any]]) -> None:
        super().__init__(payload, attachments)
        self.payload_available_types = {
            ALERT_CLEAR: self.handle_alert_clear_message,
            ALERT_VIOLATION: self.handle_alert_violation_message,
        }

        self.attachments_available_types = {
            SNAPSHOT: self.handle_snapshots,
        }

    def find_handle_method(self) -> Callable[[], str]:
        for available_type in self.payload_available_types:
            if self.payload.get(available_type):
                return self.payload_available_types[available_type]
        for available_type in self.attachments_available_types:
            if len(self.attachments) > 0 and self.attachments[0].get(available_type):
                return self.attachments_available_types[available_type]
        raise Exception("Unexpected message type")

    def handle(self) -> str:
        return self.find_handle_method()()

    def generate_topic(self) -> str:
        if self.attachments:
            return "Snapshots"
        topic_template = "Alert {alert_name}"
        alert_id, alert_name, alert_url, alert_runbook_url = self.parse_alert()
        return topic_template.format(alert_name=alert_name)

    def handle_alert_clear_message(self) -> str:
        alert_clear_template = "Alert [alert_name]({alert_url}) has cleared at {trigger_time} UTC!"
        trigger_time = datetime.fromtimestamp(
            self.payload["trigger_time"], tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")
        alert_id, alert_name, alert_url, alert_runbook_url = self.parse_alert()
        content = alert_clear_template.format(
            alert_name=alert_name, alert_url=alert_url, trigger_time=trigger_time
        )
        return content

    def handle_snapshots(self) -> str:
        content = ""
        for attachment in self.attachments:
            content += self.handle_snapshot(attachment)
        return content

    def handle_snapshot(self, snapshot: Dict[str, Any]) -> str:
        snapshot_template = "**{author_name}** sent a [snapshot]({image_url}) of [metric]({title})."
        author_name, image_url, title = self.parse_snapshot(snapshot)
        content = snapshot_template.format(
            author_name=author_name, image_url=image_url, title=title
        )
        return content

    def handle_alert_violation_message(self) -> str:
        alert_violation_template = "Alert [alert_name]({alert_url}) has triggered! "
        alert_id, alert_name, alert_url, alert_runbook_url = self.parse_alert()
        content = alert_violation_template.format(alert_name=alert_name, alert_url=alert_url)
        if alert_runbook_url:
            alert_runbook_template = "[Reaction steps]({alert_runbook_url}):"
            content += alert_runbook_template.format(alert_runbook_url=alert_runbook_url)
        content += self.generate_conditions_and_violations()
        return content

    def generate_conditions_and_violations(self) -> str:
        conditions = self.parse_conditions()
        violations = self.parse_violations()
        content = ""
        for condition, violation in zip(conditions, violations):
            content += self.generate_violated_metric_condition(violation, condition)
        return content

    def generate_violated_metric_condition(
        self, violation: Dict[str, Any], condition: Dict[str, Any]
    ) -> str:
        summary_function, threshold, condition_type, duration = self.parse_condition(condition)
        metric_name, recorded_at = self.parse_violation(violation)
        metric_condition_template = (
            "\n * Metric `{metric_name}`, {summary_function} was {condition_type} {threshold}"
        )
        content = metric_condition_template.format(
            metric_name=metric_name,
            summary_function=summary_function,
            condition_type=condition_type,
            threshold=threshold,
        )
        if duration:
            content += f" by {duration}s"
        content += f", recorded at {recorded_at} UTC."
        return content


@webhook_view("Librato")
@typed_endpoint
def api_librato_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: Json[
        Mapping[str, Any]
    ] = {},  # noqa: B006 # Mapping is indeed immutable, but Json's type annotation drops that information
) -> HttpResponse:
    try:
        attachments = orjson.loads(request.body).get("attachments", [])
    except orjson.JSONDecodeError:
        attachments = []

    if not attachments and not payload:
        raise JsonableError(_("Malformed JSON input"))

    message_handler = LibratoWebhookHandler(payload, attachments)
    topic = message_handler.generate_topic()

    try:
        content = message_handler.handle()
    except Exception as e:
        raise JsonableError(str(e))

    check_send_webhook_message(request, user_profile, topic, content)
    return json_success(request)
