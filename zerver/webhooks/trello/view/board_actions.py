from typing import Any, Dict, Mapping, MutableMapping, Optional, Text, Tuple

from .exceptions import UnknownUpdateBoardAction

SUPPORTED_BOARD_ACTIONS = [
    u'removeMemberFromBoard',
    u'addMemberToBoard',
    u'createList',
    u'updateBoard',
]

REMOVE_MEMBER = u'removeMemberFromBoard'
ADD_MEMBER = u'addMemberToBoard'
CREATE_LIST = u'createList'
CHANGE_NAME = u'changeName'

TRELLO_BOARD_URL_TEMPLATE = u'[{board_name}]({board_url})'

ACTIONS_TO_MESSAGE_MAPPER = {
    REMOVE_MEMBER: u'removed {member_name} from {board_url_template}.',
    ADD_MEMBER: u'added {member_name} to {board_url_template}.',
    CREATE_LIST: u'added {list_name} list to {board_url_template}.',
    CHANGE_NAME: u'renamed the board from {old_name} to {board_url_template}.'
}

def process_board_action(payload: Mapping[str, Any],
                         action_type: Optional[Text]) -> Optional[Tuple[Text, Text]]:
    action_type = get_proper_action(payload, action_type)
    if action_type is not None:
        return get_subject(payload), get_body(payload, action_type)
    return None

def get_proper_action(payload: Mapping[str, Any], action_type: Optional[Text]) -> Optional[Text]:
    if action_type == 'updateBoard':
        data = get_action_data(payload)
        # we don't support events for when a board's background
        # is changed
        if data['old'].get('prefs', {}).get('background') is not None:
            return None
        elif data['old']['name']:
            return CHANGE_NAME
        raise UnknownUpdateBoardAction()
    return action_type

def get_subject(payload: Mapping[str, Any]) -> Text:
    return get_action_data(payload)['board']['name']

def get_body(payload: Mapping[str, Any], action_type: Text) -> Text:
    message_body = ACTIONS_TO_FILL_BODY_MAPPER[action_type](payload, action_type)
    creator = payload['action']['memberCreator']['fullName']
    return u'{full_name} {rest}'.format(full_name=creator, rest=message_body)

def get_managed_member_body(payload: Mapping[str, Any], action_type: Text) -> Text:
    data = {
        'member_name': payload['action']['member']['fullName'],
    }
    return fill_appropriate_message_content(payload, action_type, data)

def get_create_list_body(payload: Mapping[str, Any], action_type: Text) -> Text:
    data = {
        'list_name': get_action_data(payload)['list']['name'],
    }
    return fill_appropriate_message_content(payload, action_type, data)

def get_change_name_body(payload: Mapping[str, Any], action_type: Text) -> Text:
    data = {
        'old_name': get_action_data(payload)['old']['name']
    }
    return fill_appropriate_message_content(payload, action_type, data)


def fill_appropriate_message_content(payload: Mapping[str, Any],
                                     action_type: Text,
                                     data: Optional[Dict[str, Any]]=None) -> Text:
    data = {} if data is None else data
    data['board_url_template'] = data.get('board_url_template', get_filled_board_url_template(payload))
    message_body = get_message_body(action_type)
    return message_body.format(**data)

def get_filled_board_url_template(payload: Mapping[str, Any]) -> Text:
    return TRELLO_BOARD_URL_TEMPLATE.format(board_name=get_board_name(payload),
                                            board_url=get_board_url(payload))

def get_board_name(payload: Mapping[str, Any]) -> Text:
    return get_action_data(payload)['board']['name']

def get_board_url(payload: Mapping[str, Any]) -> Text:
    return u'https://trello.com/b/{}'.format(get_action_data(payload)['board']['shortLink'])

def get_message_body(action_type: Text) -> Text:
    return ACTIONS_TO_MESSAGE_MAPPER[action_type]

def get_action_data(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return payload['action']['data']

ACTIONS_TO_FILL_BODY_MAPPER = {
    REMOVE_MEMBER: get_managed_member_body,
    ADD_MEMBER: get_managed_member_body,
    CREATE_LIST: get_create_list_body,
    CHANGE_NAME: get_change_name_body
}
