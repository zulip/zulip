from six import text_type
from typing import Dict, Tuple, Any, Optional, MutableMapping, Mapping
from datetime import datetime
from .exceptions import UnknownUpdateCardAction
from .templates import TRELLO_SUBJECT_TEMPLATE, TRELLO_MESSAGE_TEMPLATE

SUPPORTED_CARD_ACTIONS = [
    u'updateCard',
    u'createCard',
    u'addLabelToCard',
    u'removeLabelFromCard',
    u'addMemberToCard',
    u'removeMemberFromCard',
    u'addAttachmentToCard',
    u'addChecklistToCard',
    u'commentCard'
]

CREATE = u'createCard'
CHANGE_LIST = u'changeList'
CHANGE_NAME = u'changeName'
ARCHIVE = u'archiveCard'
REOPEN = u'reopenCard'
SET_DUE_DATE = u'setDueDate'
CHANGE_DUE_DATE = u'changeDueDate'
REMOVE_DUE_DATE = u'removeDueDate'
ADD_LABEL = u'addLabelToCard'
REMOVE_LABEL = u'removeLabelFromCard'
ADD_MEMBER = u'addMemberToCard'
REMOVE_MEMBER = u'removeMemberFromCard'
ADD_ATTACHMENT = u'addAttachmentToCard'
ADD_CHECKLIST = u'addChecklistToCard'
COMMENT = u'commentCard'

TRELLO_CARD_URL_TEMPLATE = u'[{card_name}]({card_url})'

ACTIONS_TO_MESSAGE_MAPPER = {
    CREATE: u'created {card_url_template}',
    CHANGE_LIST: u'moved {card_url_template} from {old_list} to {new_list}',
    CHANGE_NAME: u'renamed the card from "{old_name}" to {card_url_template}',
    ARCHIVE: u'archived {card_url_template}',
    REOPEN: u'reopened {card_url_template}',
    SET_DUE_DATE: u'set due date for {card_url_template} to {due_date}',
    CHANGE_DUE_DATE: u'changed due date for {card_url_template} from {old_due_date} to {due_date}',
    REMOVE_DUE_DATE: u'removed the due date from {card_url_template}',
    ADD_LABEL: u'added a {color} label with \"{text}\" to {card_url_template}',
    REMOVE_LABEL: u'removed a {color} label with \"{text}\" from {card_url_template}',
    ADD_MEMBER: u'added {member_name} to {card_url_template}',
    REMOVE_MEMBER: u'removed {member_name} from {card_url_template}',
    ADD_ATTACHMENT: u'added [{attachment_name}]({attachment_url}) to {card_url_template}',
    ADD_CHECKLIST: u'added the {checklist_name} checklist to {card_url_template}',
    COMMENT: u'commented on {card_url_template}'
}

def process_card_action(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> Tuple[text_type, text_type]
    action_type = get_proper_action(payload, action_type)
    return get_subject(payload), get_body(payload, action_type)

def get_proper_action(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    if action_type == 'updateCard':
        data = get_action_data(payload)
        if data.get('listBefore'):
            return CHANGE_LIST
        if data.get('old').get('name'):
            return CHANGE_NAME
        if data.get('old').get('due', False) is None:
            return SET_DUE_DATE
        if data.get('old').get('due'):
            if data.get('card').get('due', False) is None:
                return REMOVE_DUE_DATE
            else:
                return CHANGE_DUE_DATE
        if data.get('old').get('closed') is False and data.get('card').get('closed'):
            return ARCHIVE
        if data.get('old').get('closed') and data.get('card').get('closed') is False:
            return REOPEN
        raise UnknownUpdateCardAction()

    return action_type

def get_subject(payload):
    # type: (Mapping[str, Any]) -> text_type
    data = {
        'board_name': get_action_data(payload).get('board').get('name')
    }
    return TRELLO_SUBJECT_TEMPLATE.format(**data)

def get_body(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    message_body = ACTIONS_TO_FILL_BODY_MAPPER.get(action_type)(payload, action_type)
    creator = payload.get('action').get('memberCreator').get('fullName')
    return TRELLO_MESSAGE_TEMPLATE.format(full_name=creator, rest=message_body)

def get_added_checklist_body(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    data = {
        'checklist_name': get_action_data(payload).get('checklist').get('name'),
    }
    return fill_appropriate_message_content(payload, action_type, data)

def get_added_attachment_body(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    data = {
        'attachment_url': get_action_data(payload).get('attachment').get('url'),
        'attachment_name': get_action_data(payload).get('attachment').get('name'),
    }
    return fill_appropriate_message_content(payload, action_type, data)

def get_updated_card_body(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    data = {
        'card_name': get_card_name(payload),
        'old_list': get_action_data(payload).get('listBefore').get('name'),
        'new_list': get_action_data(payload).get('listAfter').get('name'),
    }
    return fill_appropriate_message_content(payload, action_type, data)

def get_renamed_card_body(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    data = {
        'old_name': get_action_data(payload).get('old').get('name'),
        'new_name': get_action_data(payload).get('card').get('name'),
    }
    return fill_appropriate_message_content(payload, action_type, data)

def get_added_label_body(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    data = {
        'color': get_action_data(payload).get('value'),
        'text': get_action_data(payload).get('text'),
    }
    return fill_appropriate_message_content(payload, action_type, data)

def get_managed_member_body(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    data = {
        'member_name': payload.get('action').get('member').get('fullName')
    }
    return fill_appropriate_message_content(payload, action_type, data)

def get_managed_due_date_body(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    date_format = "%Y-%m-%dT%H:%M:%S.000Z"
    display_date_format = '%m/%d/%Y %I:%M%p'
    new_date = datetime.strptime(get_action_data(payload).get('card').get('due'), date_format)
    data = {
        'due_date': new_date.strftime(display_date_format),
    }
    return fill_appropriate_message_content(payload, action_type, data)

def get_changed_due_date_body(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    date_format = "%Y-%m-%dT%H:%M:%S.000Z"
    display_date_format = '%m/%d/%Y %I:%M%p'
    new_date = datetime.strptime(get_action_data(payload).get('card').get('due'), date_format)
    old_date = datetime.strptime(get_action_data(payload).get('old').get('due'), date_format)
    data = {
        'due_date': new_date.strftime(display_date_format),
        'old_due_date': old_date.strftime(display_date_format)
    }
    return fill_appropriate_message_content(payload, action_type, data)

def get_body_by_action_type_without_data(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> text_type
    return fill_appropriate_message_content(payload, action_type)

def fill_appropriate_message_content(payload, action_type, data=None):
    # type: (Mapping[str, Any], text_type, Optional[Dict[str, Any]]) -> text_type
    data = {} if data is None else data
    data['card_url_template'] = data.get('card_url_template', get_filled_card_url_template(payload))
    message_body = get_message_body(action_type)
    return message_body.format(**data)

def get_filled_card_url_template(payload):
    # type: (Mapping[str, Any]) -> text_type
    return TRELLO_CARD_URL_TEMPLATE.format(card_name=get_card_name(payload), card_url=get_card_url(payload))

def get_card_url(payload):
    # type: (Mapping[str, Any]) -> text_type
    return u'https://trello.com/c/{}'.format(get_action_data(payload).get('card').get('shortLink'))

def get_message_body(action_type):
    # type: (text_type) -> text_type
    return ACTIONS_TO_MESSAGE_MAPPER.get(action_type)

def get_card_name(payload):
    # type: (Mapping[str, Any]) -> text_type
    return get_action_data(payload).get('card').get('name')

def get_action_data(payload):
    # type: (Mapping[str, Any]) -> Mapping[str, Any]
    return payload.get('action').get('data')

ACTIONS_TO_FILL_BODY_MAPPER = {
    CREATE: get_body_by_action_type_without_data,
    CHANGE_LIST: get_updated_card_body,
    CHANGE_NAME: get_renamed_card_body,
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
    COMMENT: get_body_by_action_type_without_data,
}
