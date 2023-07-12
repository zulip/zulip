from typing import Mapping, Optional, Tuple

from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.validator import WildValue, check_string

SUPPORTED_BOARD_ACTIONS = [
    "removeMemberFromBoard",
    "addMemberToBoard",
    "createList",
    "updateBoard",
]

REMOVE_MEMBER = "removeMemberFromBoard"
ADD_MEMBER = "addMemberToBoard"
CREATE_LIST = "createList"
CHANGE_NAME = "changeName"

TRELLO_BOARD_URL_TEMPLATE = "[{board_name}]({board_url})"

ACTIONS_TO_MESSAGE_MAPPER = {
    REMOVE_MEMBER: "removed {member_name} from {board_url_template}.",
    ADD_MEMBER: "added {member_name} to {board_url_template}.",
    CREATE_LIST: "added {list_name} list to {board_url_template}.",
    CHANGE_NAME: "renamed the board from {old_name} to {board_url_template}.",
}


def process_board_action(
    payload: WildValue, action_type: Optional[str]
) -> Optional[Tuple[str, str]]:
    action_type = get_proper_action(payload, action_type)
    if action_type is not None:
        return get_topic(payload), get_body(payload, action_type)
    return None


def get_proper_action(payload: WildValue, action_type: Optional[str]) -> Optional[str]:
    if action_type == "updateBoard":
        data = get_action_data(payload)
        # we don't support events for when a board's background
        # is changed
        if "background" in data["old"].get("prefs", {}):
            return None
        elif data["old"]["name"].tame(check_string):
            return CHANGE_NAME
        raise UnsupportedWebhookEventTypeError(action_type)
    return action_type


def get_topic(payload: WildValue) -> str:
    return get_action_data(payload)["board"]["name"].tame(check_string)


def get_body(payload: WildValue, action_type: str) -> str:
    message_body = ACTIONS_TO_FILL_BODY_MAPPER[action_type](payload, action_type)
    creator = payload["action"]["memberCreator"]["fullName"].tame(check_string)
    return f"{creator} {message_body}"


def get_managed_member_body(payload: WildValue, action_type: str) -> str:
    data = {
        "member_name": payload["action"]["member"]["fullName"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_create_list_body(payload: WildValue, action_type: str) -> str:
    data = {
        "list_name": get_action_data(payload)["list"]["name"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_change_name_body(payload: WildValue, action_type: str) -> str:
    data = {
        "old_name": get_action_data(payload)["old"]["name"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def fill_appropriate_message_content(
    payload: WildValue, action_type: str, data: Mapping[str, str] = {}
) -> str:
    data = dict(data)
    if "board_url_template" not in data:
        data["board_url_template"] = get_filled_board_url_template(payload)
    message_body = get_message_body(action_type)
    return message_body.format(**data)


def get_filled_board_url_template(payload: WildValue) -> str:
    return TRELLO_BOARD_URL_TEMPLATE.format(
        board_name=get_board_name(payload), board_url=get_board_url(payload)
    )


def get_board_name(payload: WildValue) -> str:
    return get_action_data(payload)["board"]["name"].tame(check_string)


def get_board_url(payload: WildValue) -> str:
    return "https://trello.com/b/{}".format(
        get_action_data(payload)["board"]["shortLink"].tame(check_string)
    )


def get_message_body(action_type: str) -> str:
    return ACTIONS_TO_MESSAGE_MAPPER[action_type]


def get_action_data(payload: WildValue) -> WildValue:
    return payload["action"]["data"]


ACTIONS_TO_FILL_BODY_MAPPER = {
    REMOVE_MEMBER: get_managed_member_body,
    ADD_MEMBER: get_managed_member_body,
    CREATE_LIST: get_create_list_body,
    CHANGE_NAME: get_change_name_body,
}
