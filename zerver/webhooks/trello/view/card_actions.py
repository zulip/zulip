from typing import Mapping, Optional, Tuple

from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.validator import WildValue, check_bool, check_none_or, check_string

SUPPORTED_CARD_ACTIONS = [
    "updateCard",
    "createCard",
    "addLabelToCard",
    "removeLabelFromCard",
    "addMemberToCard",
    "removeMemberFromCard",
    "addAttachmentToCard",
    "addChecklistToCard",
    "commentCard",
    "updateCheckItemStateOnCard",
]

IGNORED_CARD_ACTIONS = [
    "copyCard",
    "createCheckItem",
    "updateCheckItem",
    "updateList",
]

CREATE = "createCard"
CHANGE_LIST = "changeList"
CHANGE_NAME = "changeName"
SET_DESC = "setDesc"
CHANGE_DESC = "changeDesc"
REMOVE_DESC = "removeDesc"
ARCHIVE = "archiveCard"
REOPEN = "reopenCard"
SET_DUE_DATE = "setDueDate"
CHANGE_DUE_DATE = "changeDueDate"
REMOVE_DUE_DATE = "removeDueDate"
ADD_LABEL = "addLabelToCard"
REMOVE_LABEL = "removeLabelFromCard"
ADD_MEMBER = "addMemberToCard"
REMOVE_MEMBER = "removeMemberFromCard"
ADD_ATTACHMENT = "addAttachmentToCard"
ADD_CHECKLIST = "addChecklistToCard"
COMMENT = "commentCard"
UPDATE_CHECK_ITEM_STATE = "updateCheckItemStateOnCard"

TRELLO_CARD_URL_TEMPLATE = "[{card_name}]({card_url})"

ACTIONS_TO_MESSAGE_MAPPER = {
    CREATE: "created {card_url_template}.",
    CHANGE_LIST: "moved {card_url_template} from {old_list} to {new_list}.",
    CHANGE_NAME: 'renamed the card from "{old_name}" to {card_url_template}.',
    SET_DESC: "set description for {card_url_template} to:\n~~~ quote\n{desc}\n~~~\n",
    CHANGE_DESC: (
        "changed description for {card_url_template} from\n"
        + "~~~ quote\n{old_desc}\n~~~\nto\n~~~ quote\n{desc}\n~~~\n"
    ),
    REMOVE_DESC: "removed description from {card_url_template}.",
    ARCHIVE: "archived {card_url_template}.",
    REOPEN: "reopened {card_url_template}.",
    SET_DUE_DATE: "set due date for {card_url_template} to {due_date}.",
    CHANGE_DUE_DATE: "changed due date for {card_url_template} from {old_due_date} to {due_date}.",
    REMOVE_DUE_DATE: "removed the due date from {card_url_template}.",
    ADD_LABEL: 'added a {color} label with "{text}" to {card_url_template}.',
    REMOVE_LABEL: 'removed a {color} label with "{text}" from {card_url_template}.',
    ADD_MEMBER: "added {member_name} to {card_url_template}.",
    REMOVE_MEMBER: "removed {member_name} from {card_url_template}.",
    ADD_ATTACHMENT: "added [{attachment_name}]({attachment_url}) to {card_url_template}.",
    ADD_CHECKLIST: "added the {checklist_name} checklist to {card_url_template}.",
    COMMENT: "commented on {card_url_template}:\n~~~ quote\n{text}\n~~~\n",
    UPDATE_CHECK_ITEM_STATE: "{action} **{item_name}** in **{checklist_name}** ({card_url_template}).",
}


def prettify_date(date_string: str) -> str:
    return date_string.replace("T", " ").replace(".000", "").replace("Z", " UTC")


def process_card_action(payload: WildValue, action_type: str) -> Optional[Tuple[str, str]]:
    proper_action = get_proper_action(payload, action_type)
    if proper_action is not None:
        return get_subject(payload), get_body(payload, proper_action)
    return None


def get_proper_action(payload: WildValue, action_type: str) -> Optional[str]:
    if action_type == "updateCard":
        data = get_action_data(payload)
        old_data = data["old"]
        card_data = data["card"]
        if data.get("listBefore"):
            return CHANGE_LIST
        if old_data.get("name").tame(check_none_or(check_string)):
            return CHANGE_NAME
        if old_data.get("desc").tame(check_none_or(check_string)) == "":
            return SET_DESC
        if old_data.get("desc").tame(check_none_or(check_string)):
            if card_data.get("desc").tame(check_none_or(check_string)) == "":
                return REMOVE_DESC
            else:
                return CHANGE_DESC
        if old_data.get("due", "").tame(check_none_or(check_string)) is None:
            return SET_DUE_DATE
        if old_data.get("due").tame(check_none_or(check_string)):
            if card_data.get("due", "").tame(check_none_or(check_string)) is None:
                return REMOVE_DUE_DATE
            else:
                return CHANGE_DUE_DATE
        if old_data.get("closed").tame(check_none_or(check_bool)) is False and card_data.get(
            "closed", False
        ).tame(check_bool):
            return ARCHIVE
        if (
            old_data.get("closed").tame(check_none_or(check_bool))
            and card_data.get("closed").tame(check_none_or(check_bool)) is False
        ):
            return REOPEN
        # We don't support events for when a card is moved up or down
        # within a single list (pos), or when the cover changes (cover).
        # We also don't know if "dueComplete" is just a new name for "due".
        ignored_fields = [
            "cover",
            "dueComplete",
            "idAttachmentCover",
            "pos",
        ]
        for field in ignored_fields:
            if field in old_data:
                return None
        raise UnsupportedWebhookEventTypeError(action_type)

    return action_type


def get_subject(payload: WildValue) -> str:
    return get_action_data(payload)["board"]["name"].tame(check_string)


def get_body(payload: WildValue, action_type: str) -> str:
    message_body = ACTIONS_TO_FILL_BODY_MAPPER[action_type](payload, action_type)
    creator = payload["action"]["memberCreator"].get("fullName").tame(check_none_or(check_string))
    return f"{creator} {message_body}"


def get_added_checklist_body(payload: WildValue, action_type: str) -> str:
    data = {
        "checklist_name": get_action_data(payload)["checklist"]["name"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_update_check_item_body(payload: WildValue, action_type: str) -> str:
    action = get_action_data(payload)
    state = action["checkItem"]["state"].tame(check_string)
    data = {
        "action": "checked" if state == "complete" else "unchecked",
        "checklist_name": action["checklist"]["name"].tame(check_string),
        "item_name": action["checkItem"]["name"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_added_attachment_body(payload: WildValue, action_type: str) -> str:
    data = {
        "attachment_url": get_action_data(payload)["attachment"]["url"].tame(check_string),
        "attachment_name": get_action_data(payload)["attachment"]["name"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_updated_card_body(payload: WildValue, action_type: str) -> str:
    data = {
        "card_name": get_card_name(payload),
        "old_list": get_action_data(payload)["listBefore"]["name"].tame(check_string),
        "new_list": get_action_data(payload)["listAfter"]["name"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_renamed_card_body(payload: WildValue, action_type: str) -> str:
    data = {
        "old_name": get_action_data(payload)["old"]["name"].tame(check_string),
        "new_name": get_action_data(payload)["old"]["name"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_added_label_body(payload: WildValue, action_type: str) -> str:
    data = {
        "color": get_action_data(payload)["value"].tame(check_string),
        "text": get_action_data(payload)["text"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_managed_member_body(payload: WildValue, action_type: str) -> str:
    data = {
        "member_name": payload["action"]["member"]["fullName"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_comment_body(payload: WildValue, action_type: str) -> str:
    data = {
        "text": get_action_data(payload)["text"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_managed_due_date_body(payload: WildValue, action_type: str) -> str:
    data = {
        "due_date": prettify_date(get_action_data(payload)["card"]["due"].tame(check_string)),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_changed_due_date_body(payload: WildValue, action_type: str) -> str:
    data = {
        "due_date": prettify_date(get_action_data(payload)["card"]["due"].tame(check_string)),
        "old_due_date": prettify_date(get_action_data(payload)["old"]["due"].tame(check_string)),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_managed_desc_body(payload: WildValue, action_type: str) -> str:
    data = {
        "desc": get_action_data(payload)["card"]["desc"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_changed_desc_body(payload: WildValue, action_type: str) -> str:
    data = {
        "desc": get_action_data(payload)["card"]["desc"].tame(check_string),
        "old_desc": get_action_data(payload)["old"]["desc"].tame(check_string),
    }
    return fill_appropriate_message_content(payload, action_type, data)


def get_body_by_action_type_without_data(payload: WildValue, action_type: str) -> str:
    return fill_appropriate_message_content(payload, action_type)


def fill_appropriate_message_content(
    payload: WildValue, action_type: str, data: Mapping[str, str] = {}
) -> str:
    data = dict(data)
    if "card_url_template" not in data:
        data["card_url_template"] = get_filled_card_url_template(payload)
    message_body = get_message_body(action_type)
    return message_body.format(**data)


def get_filled_card_url_template(payload: WildValue) -> str:
    return TRELLO_CARD_URL_TEMPLATE.format(
        card_name=get_card_name(payload), card_url=get_card_url(payload)
    )


def get_card_url(payload: WildValue) -> str:
    return "https://trello.com/c/{}".format(
        get_action_data(payload)["card"]["shortLink"].tame(check_string)
    )


def get_message_body(action_type: str) -> str:
    return ACTIONS_TO_MESSAGE_MAPPER[action_type]


def get_card_name(payload: WildValue) -> str:
    return get_action_data(payload)["card"]["name"].tame(check_string)


def get_action_data(payload: WildValue) -> WildValue:
    return payload["action"]["data"]


ACTIONS_TO_FILL_BODY_MAPPER = {
    CREATE: get_body_by_action_type_without_data,
    CHANGE_LIST: get_updated_card_body,
    CHANGE_NAME: get_renamed_card_body,
    SET_DESC: get_managed_desc_body,
    CHANGE_DESC: get_changed_desc_body,
    REMOVE_DESC: get_body_by_action_type_without_data,
    ARCHIVE: get_body_by_action_type_without_data,
    REOPEN: get_body_by_action_type_without_data,
    SET_DUE_DATE: get_managed_due_date_body,
    CHANGE_DUE_DATE: get_changed_due_date_body,
    REMOVE_DUE_DATE: get_body_by_action_type_without_data,
    ADD_LABEL: get_added_label_body,
    REMOVE_LABEL: get_added_label_body,
    ADD_MEMBER: get_managed_member_body,
    REMOVE_MEMBER: get_managed_member_body,
    ADD_ATTACHMENT: get_added_attachment_body,
    ADD_CHECKLIST: get_added_checklist_body,
    COMMENT: get_comment_body,
    UPDATE_CHECK_ITEM_STATE: get_update_check_item_body,
}
