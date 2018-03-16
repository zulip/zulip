from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Text, Tuple

import ujson
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import utc as timezone_utc
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALERT_CLEAR = 'clear'
ALERT_VIOLATION = 'violations'
SNAPSHOT = 'image_url'

class LibratoWebhookParser:
    ALERT_URL_TEMPLATE = "https://metrics.librato.com/alerts#/{alert_id}"

    def __init__(self, payload: Dict[str, Any], attachments: List[Dict[str, Any]]) -> None:
        self.payload = payload
        self.attachments = attachments

    def generate_alert_url(self, alert_id: int) -> Text:
        return self.ALERT_URL_TEMPLATE.format(alert_id=alert_id)

    def parse_alert(self) -> Tuple[int, Text, Text, Text]:
        alert = self.payload['alert']
        alert_id = alert['id']
        return alert_id, alert['name'], self.generate_alert_url(alert_id), alert['runbook_url']

    def parse_condition(self, condition: Dict[str, Any]) -> Tuple[Text, Text, Text, Text]:
        summary_function = condition['summary_function']
        threshold = condition.get('threshold', '')
        condition_type = condition['type']
        duration = condition.get('duration', '')
        return summary_function, threshold, condition_type, duration

    def parse_violation(self, violation: Dict[str, Any]) -> Tuple[Text, Text]:
        metric_name = violation['metric']
        recorded_at = datetime.fromtimestamp((violation['recorded_at']),
                                             tz=timezone_utc).strftime('%Y-%m-%d %H:%M:%S')
        return metric_name, recorded_at

    def parse_conditions(self) -> List[Dict[str, Any]]:
        conditions = self.payload['conditions']
        return conditions

    def parse_violations(self) -> List[Dict[str, Any]]:
        violations = self.payload['violations']['test-source']
        return violations

    def parse_snapshot(self, snapshot: Dict[str, Any]) -> Tuple[Text, Text, Text]:
        author_name, image_url, title = snapshot['author_name'], snapshot['image_url'], snapshot['title']
        return author_name, image_url, title

class LibratoWebhookHandler(LibratoWebhookParser):
    def __init__(self, payload: Dict[str, Any], attachments: List[Dict[str, Any]]) -> None:
        super().__init__(payload, attachments)
        self.payload_available_types = {
            ALERT_CLEAR: self.handle_alert_clear_message,
            ALERT_VIOLATION: self.handle_alert_violation_message
        }

        self.attachments_available_types = {
            SNAPSHOT: self.handle_snapshots
        }

    def find_handle_method(self) -> Callable[[], Text]:
        for available_type in self.payload_available_types:
            if self.payload.get(available_type):
                return self.payload_available_types[available_type]
        for available_type in self.attachments_available_types:
            if self.attachments[0].get(available_type):
                return self.attachments_available_types[available_type]
        raise Exception("Unexcepted message type")

    def handle(self) -> Text:
        return self.find_handle_method()()

    def generate_topic(self) -> Text:
        if self.attachments:
            return "Snapshots"
        topic_template = "Alert {alert_name}"
        alert_id, alert_name, alert_url, alert_runbook_url = self.parse_alert()
        return topic_template.format(alert_name=alert_name)

    def handle_alert_clear_message(self) -> Text:
        alert_clear_template = "Alert [alert_name]({alert_url}) has cleared at {trigger_time} UTC!"
        trigger_time = datetime.fromtimestamp((self.payload['trigger_time']),
                                              tz=timezone_utc).strftime('%Y-%m-%d %H:%M:%S')
        alert_id, alert_name, alert_url, alert_runbook_url = self.parse_alert()
        content = alert_clear_template.format(alert_name=alert_name,
                                              alert_url=alert_url,
                                              trigger_time=trigger_time)
        return content

    def handle_snapshots(self) -> Text:
        content = u''
        for attachment in self.attachments:
            content += self.handle_snapshot(attachment)
        return content

    def handle_snapshot(self, snapshot: Dict[str, Any]) -> Text:
        snapshot_template = u"**{author_name}** sent a [snapshot]({image_url}) of [metric]({title})"
        author_name, image_url, title = self.parse_snapshot(snapshot)
        content = snapshot_template.format(author_name=author_name, image_url=image_url, title=title)
        return content

    def handle_alert_violation_message(self) -> Text:
        alert_violation_template = u"Alert [alert_name]({alert_url}) has triggered! "
        alert_id, alert_name, alert_url, alert_runbook_url = self.parse_alert()
        content = alert_violation_template.format(alert_name=alert_name, alert_url=alert_url)
        if alert_runbook_url:
            alert_runbook_template = u"[Reaction steps]({alert_runbook_url})"
            content += alert_runbook_template.format(alert_runbook_url=alert_runbook_url)
        content += self.generate_conditions_and_violations()
        return content

    def generate_conditions_and_violations(self) -> Text:
        conditions = self.parse_conditions()
        violations = self.parse_violations()
        content = u""
        for condition, violation in zip(conditions, violations):
            content += self.generate_violated_metric_condition(violation, condition)
        return content

    def generate_violated_metric_condition(self, violation: Dict[str, Any],
                                           condition: Dict[str, Any]) -> Text:
        summary_function, threshold, condition_type, duration = self.parse_condition(condition)
        metric_name, recorded_at = self.parse_violation(violation)
        metric_condition_template = (u"\n>Metric `{metric_name}`, {summary_function} "
                                     "was {condition_type} {threshold}")
        content = metric_condition_template.format(
            metric_name=metric_name, summary_function=summary_function, condition_type=condition_type,
            threshold=threshold)
        if duration:
            content += u" by {duration}s".format(duration=duration)
        content += u", recorded at {recorded_at} UTC".format(recorded_at=recorded_at)
        return content

@api_key_only_webhook_view('Librato')
@has_request_variables
def api_librato_webhook(request: HttpRequest, user_profile: UserProfile,
                        payload: Dict[str, Any]=REQ(converter=ujson.loads, default={})) -> HttpResponse:
    try:
        attachments = ujson.loads(request.body).get('attachments', [])
    except ValueError:
        attachments = []

    if not attachments and not payload:
        return json_error(_("Malformed JSON input"))

    message_handler = LibratoWebhookHandler(payload, attachments)
    topic = message_handler.generate_topic()

    try:
        content = message_handler.handle()
    except Exception as e:
        return json_error(_(str(e)))

    check_send_webhook_message(request, user_profile, topic, content)
    return json_success()
