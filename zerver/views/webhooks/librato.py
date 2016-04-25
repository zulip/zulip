from __future__ import absolute_import

import itertools

from django.utils.datetime_safe import datetime

from zerver.decorator import api_key_only_webhook_view, REQ, has_request_variables
from zerver.lib.response import json_success, json_error
from zerver.models import get_client
from zerver.lib.actions import check_send_message

import ujson

ALERT_CLEAR = 'clear'
ALERT_VIOLATION = 'violations'
SNAPSHOT = 'image_url'

class LibratoWebhookParser(object):
    def __init__(self, payload, attachments):
        self.payload = payload
        self.attachments = attachments

    def parse_alert(self):
        alert = self.payload['alert']
        alert_id, alert_name, alert_runbook_url = alert['id'], alert['name'], alert['runbook_url']
        alert_url = self.generate_alert_url(alert_id)
        return alert_id, alert_name, alert_url, alert_runbook_url

    def parse_condition(self, condition):
        summary_function = condition['summary_function']
        threshold = condition.get('threshold', '')
        condition_type = condition['type']
        duration = condition.get('duration', '')
        return summary_function, threshold, condition_type, duration

    def parse_violation(self, violation):
        metric_name = violation['metric']
        recorded_at = datetime.fromtimestamp((violation['recorded_at']))
        return metric_name, recorded_at

    def parse_conditions(self):
        conditions = self.payload['conditions']
        return conditions

    def parse_violations(self):
        violations = self.payload['violations']['test-source']
        return violations

    def parse_snapshot(self, snapshot):
        author_name, image_url, title = snapshot['author_name'], snapshot['image_url'], snapshot['title']
        return author_name, image_url, title

class LibratoWebhookHandler(LibratoWebhookParser):
    def __init__(self, payload, attachments):
        super(LibratoWebhookHandler, self).__init__(payload, attachments)
        self.payload_available_types = {
            ALERT_CLEAR: self.handle_alert_clear_message,
            ALERT_VIOLATION: self.handle_alert_violation_message
        }

        self.attachments_available_types = {
            SNAPSHOT: self.handle_snapshots
        }

    def find_handle_method(self):
        for available_type in self.payload_available_types:
            if self.payload.get(available_type):
                return self.payload_available_types[available_type]
        for available_type in self.attachments_available_types:
            if self.attachments[0].get(available_type):
                return self.attachments_available_types[available_type]
        raise Exception("Unexcepted message type")

    def handle(self):
        handle_message_method = self.find_handle_method()
        content = handle_message_method()
        return content

    def generate_alert_url(self, alert_id):
        alert_url_template = "https://metrics.librato.com/alerts#/{alert_id}"
        return alert_url_template.format(alert_id=alert_id)

    def generate_topic(self):
        if self.attachments:
            return "Snapshots"
        topic_template = "Alert {alert_name}"
        alert_id, alert_name, alert_url, alert_runbook_url = self.parse_alert()
        return topic_template.format(alert_name=alert_name)

    def handle_alert_clear_message(self):
        alert_clear_template = "Alert [alert_name]({alert_url}) has cleared at {trigger_time}!"
        trigger_time = datetime.fromtimestamp((self.payload['trigger_time']))
        alert_id, alert_name, alert_url, alert_runbook_url = self.parse_alert()
        content = alert_clear_template.format(alert_name=alert_name, alert_url=alert_url, trigger_time=trigger_time)
        return content

    def handle_snapshots(self):
        content = ''
        for attachment in self.attachments:
            content += self.handle_snapshot(attachment)
        return content

    def handle_snapshot(self, snapshot):
        snapshot_template = "**{author_name}** send a [snapshot]({image_url}) of [metric]({title})"
        author_name, image_url, title = self.parse_snapshot(snapshot)
        content = snapshot_template.format(author_name=author_name, image_url=image_url, title=title)
        return content

    def handle_alert_violation_message(self):
        alert_violation_template = "Alert [alert_name]({alert_url}) has triggered! "
        alert_id, alert_name, alert_url, alert_runbook_url = self.parse_alert()
        content = alert_violation_template.format(alert_name=alert_name, alert_url=alert_url)
        if alert_runbook_url:
            alert_runbook_template = "[Reaction steps]({alert_runbook_url})"
            content += alert_runbook_template.format(alert_runbook_url=alert_runbook_url)
        content += self.generate_conditions_and_violations()
        return content

    def generate_conditions_and_violations(self):
        conditions = self.parse_conditions()
        violations = self.parse_violations()
        content = ""
        for condition, violation in itertools.izip(conditions, violations):
            content += self.generate_violated_metric_condition(violation, condition)
        return content

    def generate_violated_metric_condition(self, violation, condition):
        summary_function, threshold, condition_type, duration = self.parse_condition(condition)
        metric_name, recorded_at = self.parse_violation(violation)
        metric_condition_template = "\n>Metric `{metric_name}`, {summary_function} was {condition_type} {threshold}"
        content = metric_condition_template.format(
                metric_name=metric_name, summary_function=summary_function, condition_type=condition_type,
                threshold=threshold)
        if duration:
            content += " by {duration}s".format(duration=duration)
        content += ", recorded at {recorded_at}".format(recorded_at=recorded_at)
        return content

@api_key_only_webhook_view
@has_request_variables
def api_librato_webhook(request, user_profile, stream=REQ(default='librato'),
                        topic=REQ(default=None)):
    try:
        attachments = ujson.loads(request.body)['attachments']
    except:
        attachments = {}
    try:
        payload = ujson.loads(request.POST['payload'])
    except:
        payload = {}
    if not attachments and not payload:
        return json_error("Malformed JSON input")

    message_handler = LibratoWebhookHandler(payload, attachments)
    if not topic:
        topic = message_handler.generate_topic()
    try:
        content = message_handler.handle()
    except Exception as e:
        return json_error(e.message)
    check_send_message(user_profile, get_client("ZulipLibratoWebhook"), "stream",
                       [stream], topic, content)
    return json_success()
