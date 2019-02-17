from typing import Dict, Any, Optional, Iterable

import json
import os

from zerver.lib import mdiff
from zerver.lib.openapi import validate_against_openapi_schema

if False:
    from zulip import Client

ZULIP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE_PATH = os.path.join(ZULIP_DIR, 'templates', 'zerver', 'api', 'fixtures.json')

def load_api_fixtures():
    # type: () -> Dict[str, Any]
    with open(FIXTURE_PATH, 'r') as fp:
        json_dict = json.loads(fp.read())
        return json_dict

FIXTURES = load_api_fixtures()

def add_subscriptions(client):
    # type: (Client) -> None

    # {code_example|start}
    # Subscribe to the stream "new stream"
    result = client.add_subscriptions(
        streams=[
            {
                'name': 'new stream',
                'description': 'New stream for testing'
            }
        ]
    )
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/me/subscriptions', 'post',
                                    '200_without_principals')

    # {code_example|start}
    # To subscribe another user to a stream, you may pass in
    # the `principals` argument, like so:
    result = client.add_subscriptions(
        streams=[
            {'name': 'new stream', 'description': 'New stream for testing'}
        ],
        principals=['newbie@zulip.com']
    )
    # {code_example|end}
    assert result['result'] == 'success'
    assert 'newbie@zulip.com' in result['subscribed']

def test_add_subscriptions_already_subscribed(client):
    # type: (Client) -> None
    result = client.add_subscriptions(
        streams=[
            {'name': 'new stream', 'description': 'New stream for testing'}
        ],
        principals=['newbie@zulip.com']
    )

    validate_against_openapi_schema(result, '/users/me/subscriptions', 'post',
                                    '200_already_subscribed')

def test_authorization_errors_fatal(client, nonadmin_client):
    # type: (Client, Client) -> None
    client.add_subscriptions(
        streams=[
            {'name': 'private_stream'}
        ],
    )

    stream_id = client.get_stream_id('private_stream')['stream_id']
    client.call_endpoint(
        'streams/{}'.format(stream_id),
        method='PATCH',
        request={'is_private': True}
    )

    result = nonadmin_client.add_subscriptions(
        streams=[
            {'name': 'private_stream'}
        ],
        authorization_errors_fatal=False,
    )

    validate_against_openapi_schema(result, '/users/me/subscriptions', 'post',
                                    '400_unauthorized_errors_fatal_false')

    result = nonadmin_client.add_subscriptions(
        streams=[
            {'name': 'private_stream'}
        ],
        authorization_errors_fatal=True,
    )

    validate_against_openapi_schema(result, '/users/me/subscriptions', 'post',
                                    '400_unauthorized_errors_fatal_true')

def get_user_presence(client):
    # type: (Client) -> None

    # {code_example|start}
    # Get presence information for "iago@zulip.com"
    result = client.get_user_presence('iago@zulip.com')
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/{email}/presence', 'get', '200')

def create_user(client):
    # type: (Client) -> None

    # {code_example|start}
    # Create a user
    request = {
        'email': 'newbie@zulip.com',
        'password': 'temp',
        'full_name': 'New User',
        'short_name': 'newbie'
    }
    result = client.create_user(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/users', 'post', '200')

    # Test "Email already used error"
    result = client.create_user(request)

    validate_against_openapi_schema(result, '/users', 'post', '400')

def get_members(client):
    # type: (Client) -> None

    # {code_example|start}
    # Get all users in the realm
    result = client.get_members()
    # {code_example|end}

    validate_against_openapi_schema(result, '/users', 'get', '200')

    members = [m for m in result['members'] if m['email'] == 'newbie@zulip.com']
    assert len(members) == 1
    newbie = members[0]
    assert not newbie['is_admin']
    assert newbie['full_name'] == 'New User'

    # {code_example|start}
    # You may pass the `client_gravatar` query parameter as follows:
    result = client.get_members({'client_gravatar': True})
    # {code_example|end}

    validate_against_openapi_schema(result, '/users', 'get', '200')
    assert result['members'][0]['avatar_url'] is None

def get_realm_filters(client):
    # type: (Client) -> None

    # {code_example|start}
    # Fetch all the filters in this organization
    result = client.get_realm_filters()
    # {code_example|end}

    validate_against_openapi_schema(result, '/realm/filters', 'get', '200')

def add_realm_filter(client):
    # type: (Client) -> None

    # {code_example|start}
    # Add a filter to automatically linkify #<number> to the corresponding
    # issue in Zulip's server repo
    result = client.add_realm_filter('#(?P<id>[0-9]+)',
                                     'https://github.com/zulip/zulip/issues/%(id)s')
    # {code_example|end}

    validate_against_openapi_schema(result, '/realm/filters', 'post', '200')

def remove_realm_filter(client):
    # type: (Client) -> None

    # {code_example|start}
    # Remove the organization filter with ID 42
    result = client.remove_realm_filter(42)
    # {code_example|end}

    validate_against_openapi_schema(result, '/realm/filters/<filter_id>', 'delete', '200')

def get_profile(client):
    # type: (Client) -> None

    # {code_example|start}
    # Get the profile of the user/bot that requests this endpoint,
    # which is `client` in this case:
    result = client.get_profile()
    # {code_example|end}

    fixture = FIXTURES['get-profile']
    check_if_equal = ['email', 'full_name', 'msg', 'result', 'short_name']
    check_if_exists = ['client_id', 'is_admin', 'is_bot', 'max_message_id',
                       'pointer', 'user_id']
    test_against_fixture(result, fixture, check_if_equal=check_if_equal,
                         check_if_exists=check_if_exists)

def get_stream_id(client):
    # type: (Client) -> None

    # {code_example|start}
    # Get the ID of a given stream
    stream_name = 'new stream'
    result = client.get_stream_id(stream_name)
    # {code_example|end}

    validate_against_openapi_schema(result, '/get_stream_id', 'get', '200')

def get_streams(client):
    # type: (Client) -> None

    # {code_example|start}
    # Get all streams that the user has access to
    result = client.get_streams()
    # {code_example|end}

    validate_against_openapi_schema(result, '/streams', 'get', '200')
    streams = [s for s in result['streams'] if s['name'] == 'new stream']
    assert streams[0]['description'] == 'New stream for testing'

    # {code_example|start}
    # You may pass in one or more of the query parameters mentioned above
    # as keyword arguments, like so:
    result = client.get_streams(include_public=False)
    # {code_example|end}

    validate_against_openapi_schema(result, '/streams', 'get', '200')
    assert len(result['streams']) == 4

def get_user_groups(client):
    # type: (Client) -> None

    # {code_example|start}
    # Get all user groups of the realm
    result = client.get_user_groups()
    # {code_example|end}

    validate_against_openapi_schema(result, '/user_groups', 'get', '200')
    user_groups = [u for u in result['user_groups'] if u['name'] == "hamletcharacters"]
    assert user_groups[0]['description'] == 'Characters of Hamlet'

def test_user_not_authorized_error(nonadmin_client):
    # type: (Client) -> None
    result = nonadmin_client.get_streams(include_all_active=True)

    fixture = FIXTURES['user-not-authorized-error']
    test_against_fixture(result, fixture)

def get_subscribers(client):
    # type: (Client) -> None

    result = client.get_subscribers(stream='new stream')
    assert result['subscribers'] == ['iago@zulip.com', 'newbie@zulip.com']

def get_user_agent(client):
    # type: (Client) -> None

    result = client.get_user_agent()
    assert result.startswith('ZulipPython/')

def list_subscriptions(client):
    # type: (Client) -> None
    # {code_example|start}
    # Get all streams that the user is subscribed to
    result = client.list_subscriptions()
    # {code_example|end}

    fixture = FIXTURES['get-subscribed-streams']
    test_against_fixture(result, fixture, check_if_equal=['msg', 'result'],
                         check_if_exists=['subscriptions'])

    streams = [s for s in result['subscriptions'] if s['name'] == 'new stream']
    assert streams[0]['description'] == 'New stream for testing'

def remove_subscriptions(client):
    # type: (Client) -> None

    # {code_example|start}
    # Unsubscribe from the stream "new stream"
    result = client.remove_subscriptions(
        ['new stream']
    )
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/me/subscriptions',
                                    'delete', '200')

    # test it was actually removed
    result = client.list_subscriptions()
    assert result['result'] == 'success'
    streams = [s for s in result['subscriptions'] if s['name'] == 'new stream']
    assert len(streams) == 0

    # {code_example|start}
    # Unsubscribe another user from the stream "new stream"
    result = client.remove_subscriptions(
        ['new stream'],
        principals=['newbie@zulip.com']
    )
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/me/subscriptions',
                                    'delete', '200')

def toggle_mute_topic(client):
    # type: (Client) -> None

    # Send a test message
    message = {
        'type': 'stream',
        'to': 'Denmark',
        'topic': 'boat party'
    }
    client.call_endpoint(
        url='messages',
        method='POST',
        request=message
    )

    # {code_example|start}
    # Mute the topic "boat party" in the stream "Denmark"
    request = {
        'stream': 'Denmark',
        'topic': 'boat party',
        'op': 'add'
    }
    result = client.mute_topic(request)
    # {code_example|end}

    validate_against_openapi_schema(result,
                                    '/users/me/subscriptions/muted_topics',
                                    'patch', '200')

    # {code_example|start}
    # Unmute the topic "boat party" in the stream "Denmark"
    request = {
        'stream': 'Denmark',
        'topic': 'boat party',
        'op': 'remove'
    }

    result = client.mute_topic(request)
    # {code_example|end}

    validate_against_openapi_schema(result,
                                    '/users/me/subscriptions/muted_topics',
                                    'patch', '200')

def mark_all_as_read(client):
    # type: (Client) -> None

    # {code_example|start}
    # Mark all of the user's unread messages as read
    result = client.mark_all_as_read()
    # {code_example|end}

    validate_against_openapi_schema(result, '/mark_all_as_read', 'post', '200')

def mark_stream_as_read(client):
    # type: (Client) -> None

    # {code_example|start}
    # Mark the unread messages in stream with ID "1" as read
    result = client.mark_stream_as_read(1)
    # {code_example|end}

    validate_against_openapi_schema(result, '/mark_stream_as_read', 'post', '200')

def mark_topic_as_read(client):
    # type: (Client) -> None

    # Grab an existing topic name
    topìc_name = client.get_stream_topics(1)['topics'][0]['name']

    # {code_example|start}
    # Mark the unread messages in stream 1's topic "topic_name" as read
    result = client.mark_topic_as_read(1, topìc_name)
    # {code_example|end}

    validate_against_openapi_schema(result, '/mark_stream_as_read', 'post', '200')

def update_subscription_settings(client):
    # type: (Client) -> None

    # {code_example|start}
    # Update the user's subscription in stream #1 to pin it to the top of the
    # stream list; and in stream #3 to have the hex color "f00"
    request = [{
        'stream_id': 1,
        'property': 'pin_to_top',
        'value': True
    }, {
        'stream_id': 3,
        'property': 'color',
        'value': 'f00'
    }]
    result = client.update_subscription_settings(request)
    # {code_example|end}

    validate_against_openapi_schema(result,
                                    '/users/me/subscriptions/properties',
                                    'POST', '200')

def render_message(client):
    # type: (Client) -> None

    # {code_example|start}
    # Render a message
    request = {
        'content': '**foo**'
    }
    result = client.render_message(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/render', 'post', '200')

def get_messages(client):
    # type: (Client) -> None

    # {code_example|start}
    # Get the 3 last messages sent by "iago@zulip.com" to the stream "Verona"
    request = {
        'use_first_unread_anchor': True,
        'num_before': 3,
        'num_after': 0,
        'narrow': [{'operator': 'sender', 'operand': 'iago@zulip.com'},
                   {'operator': 'stream', 'operand': 'Verona'}],
        'client_gravatar': True,
        'apply_markdown': True
    }  # type: Dict[str, Any]
    result = client.get_messages(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages', 'get', '200')
    assert len(result['messages']) <= request['num_before']

def get_raw_message(client, message_id):
    # type: (Client, int) -> None

    assert int(message_id)

    # {code_example|start}
    # Get the raw content of the message with ID "message_id"
    result = client.get_raw_message(message_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/{message_id}', 'get',
                                    '200')

def send_message(client):
    # type: (Client) -> int

    # {code_example|start}
    # Send a stream message
    request = {
        "type": "stream",
        "to": "Denmark",
        "subject": "Castle",
        "content": "I come not, friends, to steal away your hearts."
    }
    result = client.send_message(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages', 'post', '200')

    # test that the message was actually sent
    message_id = result['id']
    url = 'messages/' + str(message_id)
    result = client.call_endpoint(
        url=url,
        method='GET'
    )
    assert result['result'] == 'success'
    assert result['raw_content'] == request['content']

    # {code_example|start}
    # Send a private message
    request = {
        "type": "private",
        "to": "iago@zulip.com",
        "content": "With mirth and laughter let old wrinkles come."
    }
    result = client.send_message(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages', 'post', '200')

    # test that the message was actually sent
    message_id = result['id']
    url = 'messages/' + str(message_id)
    result = client.call_endpoint(
        url=url,
        method='GET'
    )
    assert result['result'] == 'success'
    assert result['raw_content'] == request['content']

    return message_id

def add_reaction(client, message_id):
    # type: (Client, int) -> None
    request = {
        'message_id': message_id,
        'emoji_name': 'joy',
        'emoji_code': '1f602',
        'emoji_type': 'unicode_emoji'
    }
    result = client.add_reaction(request)

    assert result['result'] == 'success'

def test_nonexistent_stream_error(client):
    # type: (Client) -> None
    request = {
        "type": "stream",
        "to": "nonexistent_stream",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts."
    }
    result = client.send_message(request)

    validate_against_openapi_schema(result, '/messages', 'post',
                                    '400_non_existing_stream')

def test_private_message_invalid_recipient(client):
    # type: (Client) -> None
    request = {
        "type": "private",
        "to": "eeshan@zulip.com",
        "content": "With mirth and laughter let old wrinkles come."
    }
    result = client.send_message(request)

    validate_against_openapi_schema(result, '/messages', 'post',
                                    '400_non_existing_user')

def update_message(client, message_id):
    # type: (Client, int) -> None

    assert int(message_id)

    # {code_example|start}
    # Edit a message
    # (make sure that message_id below is set to the ID of the
    # message you wish to update)
    request = {
        "message_id": message_id,
        "content": "New content"
    }
    result = client.update_message(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/{message_id}', 'patch',
                                    '200')

    # test it was actually updated
    url = 'messages/' + str(message_id)
    result = client.call_endpoint(
        url=url,
        method='GET'
    )
    assert result['result'] == 'success'
    assert result['raw_content'] == request['content']

def test_update_message_edit_permission_error(client, nonadmin_client):
    # type: (Client, Client) -> None
    request = {
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts."
    }
    result = client.send_message(request)

    request = {
        "message_id": result["id"],
        "content": "New content"
    }
    result = nonadmin_client.update_message(request)

    fixture = FIXTURES['update-message-edit-permission-error']
    test_against_fixture(result, fixture)

def delete_message(client, message_id):
    # type: (Client, int) -> None

    # {code_example|start}
    # Delete the message with ID "message_id"
    result = client.delete_message(message_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/{message_id}', 'delete',
                                    '200')

def test_delete_message_edit_permission_error(client, nonadmin_client):
    # type: (Client, Client) -> None
    request = {
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts."
    }
    result = client.send_message(request)

    result = nonadmin_client.delete_message(result['id'])

    validate_against_openapi_schema(result, '/messages/{message_id}', 'delete',
                                    '400_not_admin')

def get_message_history(client, message_id):
    # type: (Client, int) -> None

    # {code_example|start}
    # Get the edit history for message with ID "message_id"
    result = client.get_message_history(message_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/{message_id}/history',
                                    'get', '200')

def get_realm_emoji(client):
    # type: (Client) -> None

    # {code_example|start}
    result = client.get_realm_emoji()
    # {code_example|end}

    validate_against_openapi_schema(result, '/realm/emoji', 'GET', '200')

def update_message_flags(client):
    # type: (Client) -> None

    # Send a few test messages
    request = {
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts."
    }  # type: Dict[str, Any]
    message_ids = []
    for i in range(0, 3):
        message_ids.append(client.send_message(request)['id'])

    # {code_example|start}
    # Add the "read" flag to the messages with IDs in "message_ids"
    request = {
        'messages': message_ids,
        'op': 'add',
        'flag': 'read'
    }
    result = client.update_message_flags(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/flags', 'post',
                                    '200')

    # {code_example|start}
    # Remove the "starred" flag from the messages with IDs in "message_ids"
    request = {
        'messages': message_ids,
        'op': 'remove',
        'flag': 'starred'
    }
    result = client.update_message_flags(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/flags', 'post',
                                    '200')

def register_queue(client):
    # type: (Client) -> str

    # {code_example|start}
    # Register the queue
    result = client.register(
        event_types=['message', 'realm_emoji']
    )
    # {code_example|end}

    validate_against_openapi_schema(result, '/register', 'post', '200')
    return result['queue_id']

def deregister_queue(client, queue_id):
    # type: (Client, str) -> None

    # {code_example|start}
    # Delete a queue (queue_id is the ID of the queue
    # to be removed)
    result = client.deregister(queue_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/events', 'delete', '200')

    # Test "BAD_EVENT_QUEUE_ID" error
    result = client.deregister(queue_id)
    validate_against_openapi_schema(result, '/events', 'delete', '400')

def get_server_settings(client):
    # type: (Client) -> None

    # {code_example|start}
    # Fetch the settings for this server
    result = client.get_server_settings()
    # {code_example|end}

    validate_against_openapi_schema(result, '/server_settings', 'get', '200')

def upload_file(client):
    # type: (Client) -> None
    path_to_file = os.path.join(ZULIP_DIR, 'zerver', 'tests', 'images', 'img.jpg')

    # {code_example|start}
    # Upload a file
    fp = open(path_to_file, 'rb')
    result = client.call_endpoint(
        'user_uploads',
        method='POST',
        files=[fp]
    )
    # {code_example|end}

    validate_against_openapi_schema(result, '/user_uploads', 'post', '200')

def get_stream_topics(client, stream_id):
    # type: (Client, int) -> None

    # {code_example|start}
    result = client.get_stream_topics(stream_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/me/{stream_id}/topics',
                                    'get', '200')

def set_typing_status(client):
    # type: (Client) -> None

    # {code_example|start}
    # The user has started to type in the group PM with Iago and Polonius
    request = {
        'op': 'start',
        'to': ['iago@zulip.com', 'polonius@zulip.com']
    }
    result = client.set_typing_status(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/typing', 'post', '200')

    # {code_example|start}
    # The user has finished typing in the group PM with Iago and Polonius
    request = {
        'op': 'stop',
        'to': ['iago@zulip.com', 'polonius@zulip.com']
    }
    result = client.set_typing_status(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/typing', 'post', '200')

def upload_custom_emoji(client):
    # type: (Client) -> None
    emoji_path = os.path.join(ZULIP_DIR, 'zerver', 'tests', 'images', 'img.jpg')

    # {code_example|start}
    # Upload a custom emoji; assume `emoji_path` is the path to your image.
    fp = open(emoji_path, 'rb')
    emoji_name = 'my_custom_emoji'
    result = client.call_endpoint(
        'realm/emoji/{}'.format(emoji_name),
        method='POST',
        files=[fp]
    )
    # {code_example|end}
    fp.close()
    validate_against_openapi_schema(result,
                                    '/realm/emoji/<emoji_name>',
                                    'post', '200')

def test_invalid_api_key(client_with_invalid_key):
    # type: (Client) -> None
    result = client_with_invalid_key.list_subscriptions()
    fixture = FIXTURES['invalid-api-key']
    test_against_fixture(result, fixture)

def test_missing_request_argument(client):
    # type: (Client) -> None
    result = client.render_message({})

    fixture = FIXTURES['missing-request-argument-error']
    test_against_fixture(result, fixture)

def test_invalid_stream_error(client):
    # type: (Client) -> None
    result = client.get_stream_id('nonexistent')

    validate_against_openapi_schema(result, '/get_stream_id', 'get', '400')

TEST_FUNCTIONS = {
    '/mark_all_as_read:post': mark_all_as_read,
    '/mark_stream_as_read:post': mark_stream_as_read,
    '/mark_topic_as_read:post': mark_topic_as_read,
    '/messages/render:post': render_message,
    '/messages:get': get_messages,
    '/messages:post': send_message,
    '/messages/{message_id}:get': get_raw_message,
    '/messages/{message_id}:patch': update_message,
    '/messages/{message_id}:delete': delete_message,
    '/messages/{message_id}/history:get': get_message_history,
    '/messages/flags:post': update_message_flags,
    '/get_stream_id:get': get_stream_id,
    'get-subscribed-streams': list_subscriptions,
    '/streams:get': get_streams,
    '/users:post': create_user,
    'get-profile': get_profile,
    'add-subscriptions': add_subscriptions,
    '/users/{email}/presence:get': get_user_presence,
    '/users/me/subscriptions:delete': remove_subscriptions,
    '/users/me/subscriptions/muted_topics:patch': toggle_mute_topic,
    '/users/me/subscriptions/properties:post': update_subscription_settings,
    '/users:get': get_members,
    '/realm/emoji:get': get_realm_emoji,
    '/realm/emoji/<emoji_name>:post': upload_custom_emoji,
    '/realm/filters:get': get_realm_filters,
    '/realm/filters:post': add_realm_filter,
    '/realm/filters/<filter_id>:delete': remove_realm_filter,
    '/register:post': register_queue,
    '/events:delete': deregister_queue,
    '/server_settings:get': get_server_settings,
    '/user_uploads:post': upload_file,
    '/users/me/{stream_id}/topics:get': get_stream_topics,
    '/typing:post': set_typing_status,
    '/user_groups:get': get_user_groups,
}

# SETUP METHODS FOLLOW

def test_against_fixture(result, fixture, check_if_equal=[], check_if_exists=[]):
    # type: (Dict[str, Any], Dict[str, Any], Optional[Iterable[str]], Optional[Iterable[str]]) -> None
    assertLength(result, fixture)

    if not check_if_equal and not check_if_exists:
        for key, value in fixture.items():
            assertEqual(key, result, fixture)

    if check_if_equal:
        for key in check_if_equal:
            assertEqual(key, result, fixture)

    if check_if_exists:
        for key in check_if_exists:
            assertIn(key, result)

def assertEqual(key, result, fixture):
    # type: (str, Dict[str, Any], Dict[str, Any]) -> None
    if result[key] != fixture[key]:
        first = "{key} = {value}".format(key=key, value=result[key])
        second = "{key} = {value}".format(key=key, value=fixture[key])
        raise AssertionError("Actual and expected outputs do not match; showing diff:\n" +
                             mdiff.diff_strings(first, second))
    else:
        assert result[key] == fixture[key]

def assertLength(result, fixture):
    # type: (Dict[str, Any], Dict[str, Any]) -> None
    if len(result) != len(fixture):
        result_string = json.dumps(result, indent=4, sort_keys=True)
        fixture_string = json.dumps(fixture, indent=4, sort_keys=True)
        raise AssertionError("The lengths of the actual and expected outputs do not match; showing diff:\n" +
                             mdiff.diff_strings(result_string, fixture_string))
    else:
        assert len(result) == len(fixture)

def assertIn(key, result):
    # type: (str, Dict[str, Any]) -> None
    if key not in result.keys():
        raise AssertionError(
            "The actual output does not contain the the key `{key}`.".format(key=key)
        )
    else:
        assert key in result

def test_messages(client, nonadmin_client):
    # type: (Client, Client) -> None

    render_message(client)
    message_id = send_message(client)
    add_reaction(client, message_id)
    update_message(client, message_id)
    get_raw_message(client, message_id)
    get_messages(client)
    get_message_history(client, message_id)
    delete_message(client, message_id)
    mark_all_as_read(client)
    mark_stream_as_read(client)
    mark_topic_as_read(client)
    update_message_flags(client)

    test_nonexistent_stream_error(client)
    test_private_message_invalid_recipient(client)
    test_update_message_edit_permission_error(client, nonadmin_client)
    test_delete_message_edit_permission_error(client, nonadmin_client)

def test_users(client):
    # type: (Client) -> None

    create_user(client)
    get_members(client)
    get_profile(client)
    upload_file(client)
    set_typing_status(client)
    get_user_presence(client)
    get_user_groups(client)

def test_streams(client, nonadmin_client):
    # type: (Client, Client) -> None

    add_subscriptions(client)
    test_add_subscriptions_already_subscribed(client)
    list_subscriptions(client)
    get_stream_id(client)
    get_streams(client)
    get_subscribers(client)
    remove_subscriptions(client)
    toggle_mute_topic(client)
    update_subscription_settings(client)
    get_stream_topics(client, 1)

    test_user_not_authorized_error(nonadmin_client)
    test_authorization_errors_fatal(client, nonadmin_client)


def test_queues(client):
    # type: (Client) -> None
    # Note that the example for api/get-events-from-queue is not tested.
    # Since, methods such as client.get_events() or client.call_on_each_message
    # are blocking calls and since the event queue backend is already
    # thoroughly tested in zerver/tests/test_event_queue.py, it is not worth
    # the effort to come up with asynchronous logic for testing those here.
    queue_id = register_queue(client)
    deregister_queue(client, queue_id)

def test_server_organizations(client):
    # type: (Client) -> None

    get_realm_filters(client)
    add_realm_filter(client)
    get_server_settings(client)
    remove_realm_filter(client)
    get_realm_emoji(client)
    upload_custom_emoji(client)

def test_errors(client):
    # type: (Client) -> None
    test_missing_request_argument(client)
    test_invalid_stream_error(client)

def test_the_api(client, nonadmin_client):
    # type: (Client, Client) -> None

    get_user_agent(client)
    test_users(client)
    test_streams(client, nonadmin_client)
    test_messages(client, nonadmin_client)
    test_queues(client)
    test_server_organizations(client)
    test_errors(client)
