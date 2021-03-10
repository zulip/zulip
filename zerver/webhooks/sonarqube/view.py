# Webhooks for external integrations.

from typing import Any, Dict, List, Mapping

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

TOPIC_WITH_BRANCH = "{} / {}"

MESSAGE_WITH_BRANCH_AND_CONDITIONS = "Project [{}]({}) analysis of branch {} resulted in {}:\n"
MESSAGE_WITH_BRANCH_AND_WITHOUT_CONDITIONS = (
    "Project [{}]({}) analysis of branch {} resulted in {}."
)
MESSAGE_WITHOUT_BRANCH_AND_WITH_CONDITIONS = "Project [{}]({}) analysis resulted in {}:\n"
MESSAGE_WITHOUT_BRANCH_AND_CONDITIONS = "Project [{}]({}) analysis resulted in {}."

INVERSE_OPERATORS = {
    "WORSE_THAN": "should be better or equal to",
    "GREATER_THAN": "should be less than or equal to",
    "LESS_THAN": "should be greater than or equal to",
}

TEMPLATES = {
    "default": "* {}: **{}** {} {} {}.",
    "no_value": "* {}: **{}**.",
}


def parse_metric_name(metric_name: str) -> str:
    return " ".join(metric_name.split("_"))


def parse_condition(condition: Mapping[str, Any]) -> str:
    metric = condition["metric"]

    metric_name = parse_metric_name(metric)
    operator = condition["operator"]
    operator = INVERSE_OPERATORS.get(operator, operator)
    value = condition.get("value", "no value")
    status = condition["status"].lower()
    threshold = condition["errorThreshold"]

    if value == "no value":
        return TEMPLATES["no_value"].format(metric_name, status)

    template = TEMPLATES["default"]

    return template.format(metric_name, status, value, operator, threshold)


def parse_conditions(conditions: List[Mapping[str, Any]]) -> str:
    return "\n".join(
        [
            parse_condition(condition)
            for condition in conditions
            if condition["status"].lower() != "ok" and condition["status"].lower() != "no_value"
        ]
    )


def render_body_with_branch(payload: Mapping[str, Any]) -> str:
    project_name = payload["project"]["name"]
    project_url = payload["project"]["url"]
    quality_gate_status = payload["qualityGate"]["status"].lower()
    if quality_gate_status == "ok":
        quality_gate_status = "success"
    else:
        quality_gate_status = "error"
    branch = payload["branch"]["name"]

    conditions = payload["qualityGate"]["conditions"]
    conditions = parse_conditions(conditions)

    if not conditions:
        return MESSAGE_WITH_BRANCH_AND_WITHOUT_CONDITIONS.format(
            project_name, project_url, branch, quality_gate_status
        )
    msg = MESSAGE_WITH_BRANCH_AND_CONDITIONS.format(
        project_name, project_url, branch, quality_gate_status
    )
    msg += conditions

    return msg


def render_body_without_branch(payload: Mapping[str, Any]) -> str:
    project_name = payload["project"]["name"]
    project_url = payload["project"]["url"]
    quality_gate_status = payload["qualityGate"]["status"].lower()
    if quality_gate_status == "ok":
        quality_gate_status = "success"
    else:
        quality_gate_status = "error"
    conditions = payload["qualityGate"]["conditions"]
    conditions = parse_conditions(conditions)

    if not conditions:
        return MESSAGE_WITHOUT_BRANCH_AND_CONDITIONS.format(
            project_name, project_url, quality_gate_status
        )
    msg = MESSAGE_WITHOUT_BRANCH_AND_WITH_CONDITIONS.format(
        project_name, project_url, quality_gate_status
    )
    msg += conditions

    return msg


@webhook_view("Sonarqube")
@has_request_variables
def api_sonarqube_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    project = payload["project"]["name"]
    branch = None
    if "branch" in payload.keys():
        branch = payload["branch"].get("name", None)
    if branch:
        topic = TOPIC_WITH_BRANCH.format(project, branch)
        message = render_body_with_branch(payload)
    else:
        topic = project
        message = render_body_without_branch(payload)
    check_send_webhook_message(request, user_profile, topic, message)
    return json_success()
