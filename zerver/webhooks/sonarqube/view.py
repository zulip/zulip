# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
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


def parse_condition(condition: WildValue) -> str:
    metric = condition["metric"].tame(check_string)

    metric_name = parse_metric_name(metric)
    operator = condition["operator"].tame(check_string)
    operator = INVERSE_OPERATORS.get(operator, operator)
    value = condition.get("value", "no value").tame(check_string)
    status = condition["status"].tame(check_string).lower()
    threshold = condition["errorThreshold"].tame(check_string)

    if value == "no value":
        return TEMPLATES["no_value"].format(metric_name, status)

    template = TEMPLATES["default"]

    return template.format(metric_name, status, value, operator, threshold)


def parse_conditions(conditions: WildValue) -> str:
    return "\n".join(
        [
            parse_condition(condition)
            for condition in conditions
            if condition["status"].tame(check_string).lower() != "ok"
            and condition["status"].tame(check_string).lower() != "no_value"
        ]
    )


def render_body_with_branch(payload: WildValue) -> str:
    project_name = payload["project"]["name"].tame(check_string)
    project_url = payload["project"]["url"].tame(check_string)
    quality_gate_status = payload["qualityGate"]["status"].tame(check_string).lower()
    if quality_gate_status == "ok":
        quality_gate_status = "success"
    else:
        quality_gate_status = "error"
    branch = payload["branch"]["name"].tame(check_string)

    conditions = parse_conditions(payload["qualityGate"]["conditions"])

    if not conditions:
        return MESSAGE_WITH_BRANCH_AND_WITHOUT_CONDITIONS.format(
            project_name, project_url, branch, quality_gate_status
        )
    msg = MESSAGE_WITH_BRANCH_AND_CONDITIONS.format(
        project_name, project_url, branch, quality_gate_status
    )
    msg += conditions

    return msg


def render_body_without_branch(payload: WildValue) -> str:
    project_name = payload["project"]["name"].tame(check_string)
    project_url = payload["project"]["url"].tame(check_string)
    quality_gate_status = payload["qualityGate"]["status"].tame(check_string).lower()
    if quality_gate_status == "ok":
        quality_gate_status = "success"
    else:
        quality_gate_status = "error"
    conditions = parse_conditions(payload["qualityGate"]["conditions"])

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
@typed_endpoint
def api_sonarqube_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    project = payload["project"]["name"].tame(check_string)
    branch = None
    if "branch" in payload:
        branch = payload["branch"].get("name").tame(check_none_or(check_string))
    if branch:
        topic = TOPIC_WITH_BRANCH.format(project, branch)
        message = render_body_with_branch(payload)
    else:
        topic = project
        message = render_body_without_branch(payload)
    check_send_webhook_message(request, user_profile, topic, message)
    return json_success(request)
