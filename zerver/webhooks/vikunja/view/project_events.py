from collections.abc import Mapping

from zerver.lib.validator import WildValue, check_int, check_string

SUPPORTED_PROJECT_EVENTS = [
    "project.updated",
    "project.deleted",
    "project.shared.user",
    "project.shared.team",
]

PROJECT_UPDATED = "project.updated"
PROJECT_DELETED = "project.deleted"
ADD_SHARE_USER = "project.shared.user"
ADD_SHARE_TEAM = "project.shared.team"

VIKUNJA_PROJECT_URL_TEMPLATE = "[{project_name}]({project_url})"

EVENTS_TO_MESSAGE_MAPPER = {
    PROJECT_UPDATED: "updated the project {project_url_template}.",
    PROJECT_DELETED: "deleted the project {project_url_template}.",
    ADD_SHARE_USER: "shared {project_url_template} with {share_user_name}.",
    ADD_SHARE_TEAM: "shared {project_url_template} with team `{share_team_name}` consisting of `{share_team_size}` member(s).",
}


# Data extraction helpers
def get_action_data(payload: WildValue) -> WildValue:
    return payload["data"]


def get_project_name(payload: WildValue) -> str:
    return get_action_data(payload)["project"]["title"].tame(check_string)


def get_project_url(host: str, payload: WildValue) -> str:
    id = get_action_data(payload)["project"].get("id").tame(check_int)
    return f"{host}/projects/{id}"


# Template filling helpers
def get_filled_project_url_template(host: str, payload: WildValue) -> str:
    if payload.get("event_name").tame(check_string) == "project.deleted":
        data = get_action_data(payload)
        project_id = data["project"]["id"].tame(check_int)
        return f"*{get_project_name(payload)}* `ID: {project_id!s}`"

    return VIKUNJA_PROJECT_URL_TEMPLATE.format(
        project_name=get_project_name(payload), project_url=get_project_url(host, payload)
    )


def fill_appropriate_message_content(
    host: str, payload: WildValue, event_name: str, data: Mapping[str, str] = {}
) -> str:
    data = dict(data)
    if "project_url_template" not in data:
        data["project_url_template"] = get_filled_project_url_template(host, payload)
    message_body = get_message_body(event_name)
    return message_body.format(**data)


def get_message_body(event_name: str) -> str:
    return EVENTS_TO_MESSAGE_MAPPER[event_name]


# Event-specific body builders
def get_body_by_action_type_without_data(host: str, payload: WildValue, action_type: str) -> str:
    return fill_appropriate_message_content(host, payload, action_type)


def get_share_user_body(host: str, payload: WildValue, event_name: str) -> str:
    data = {
        "share_user_name": get_action_data(payload)["user"]["name"].tame(check_string),
    }
    return fill_appropriate_message_content(host, payload, event_name, data)


def get_share_team_body(host: str, payload: WildValue, event_name: str) -> str:
    team = get_action_data(payload)["team"]
    data = {
        "share_team_name": team["name"].tame(check_string),
        "share_team_size": f"{len(team['members'])}",
    }
    return fill_appropriate_message_content(host, payload, event_name, data)


# Main entry point
def get_body(host: str, payload: WildValue, event_name: str) -> str:
    message_body = EVENTS_TO_FILL_BODY_MAPPER[event_name](host, payload, event_name)
    creator = get_action_data(payload)["doer"]["name"].tame(check_string)
    return f"{creator} {message_body}"


def get_topic(payload: WildValue) -> str:
    return get_project_name(payload)


def process_project_action(
    host: str, payload: WildValue, event_name: str
) -> tuple[str, str] | None:
    return get_topic(payload), get_body(host, payload, event_name)


EVENTS_TO_FILL_BODY_MAPPER = {
    PROJECT_UPDATED: get_body_by_action_type_without_data,
    PROJECT_DELETED: get_body_by_action_type_without_data,
    ADD_SHARE_USER: get_share_user_body,
    ADD_SHARE_TEAM: get_share_team_body,
}
