import json
import os
import sys
from functools import wraps
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, TypeVar, cast

from zulip import Client

from zerver.lib import mdiff
from zerver.models import get_realm, get_user
from zerver.openapi.openapi import validate_against_openapi_schema

ZULIP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_FUNCTIONS: Dict[str, Callable[..., object]] = dict()
REGISTERED_TEST_FUNCTIONS: Set[str] = set()
CALLED_TEST_FUNCTIONS: Set[str] = set()

FuncT = TypeVar("FuncT", bound=Callable[..., object])

def openapi_test_function(endpoint: str) -> Callable[[FuncT], FuncT]:
    """This decorator is used to register an openapi test function with
    its endpoint. Example usage:

    @openapi_test_function("/messages/render:post")
    def ...
    """
    def wrapper(test_func: FuncT) -> FuncT:
        @wraps(test_func)
        def _record_calls_wrapper(*args: object, **kwargs: object) -> object:
            CALLED_TEST_FUNCTIONS.add(test_func.__name__)
            return test_func(*args, **kwargs)

        REGISTERED_TEST_FUNCTIONS.add(test_func.__name__)
        TEST_FUNCTIONS[endpoint] = _record_calls_wrapper

        return cast(FuncT, _record_calls_wrapper)  # https://github.com/python/mypy/issues/1927
    return wrapper

def ensure_users(ids_list: List[int], user_names: List[str]) -> None:
    # Ensure that the list of user ids (ids_list)
    # matches the users we want to refer to (user_names).
    realm = get_realm("zulip")
    user_ids = [get_user(name + '@zulip.com', realm).id for name in user_names]

    assert ids_list == user_ids

@openapi_test_function("/users/me/subscriptions:post")
def add_subscriptions(client: Client) -> None:

    # {code_example|start}
    # Subscribe to the stream "new stream"
    result = client.add_subscriptions(
        streams=[
            {
                'name': 'new stream',
                'description': 'New stream for testing',
            },
        ],
    )
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/me/subscriptions', 'post',
                                    '200_0')

    # {code_example|start}
    # To subscribe other users to a stream, you may pass
    # the `principals` argument, like so:
    user_id = 25
    result = client.add_subscriptions(
        streams=[
            {'name': 'new stream', 'description': 'New stream for testing'},
        ],
        principals=[user_id],
    )
    # {code_example|end}
    assert result['result'] == 'success'
    assert 'newbie@zulip.com' in result['subscribed']

def test_add_subscriptions_already_subscribed(client: Client) -> None:
    result = client.add_subscriptions(
        streams=[
            {'name': 'new stream', 'description': 'New stream for testing'},
        ],
        principals=['newbie@zulip.com'],
    )

    validate_against_openapi_schema(result, '/users/me/subscriptions', 'post',
                                    '200_1')

def test_authorization_errors_fatal(client: Client, nonadmin_client: Client) -> None:
    client.add_subscriptions(
        streams=[
            {'name': 'private_stream'},
        ],
    )

    stream_id = client.get_stream_id('private_stream')['stream_id']
    client.call_endpoint(
        f'streams/{stream_id}',
        method='PATCH',
        request={'is_private': True},
    )

    result = nonadmin_client.add_subscriptions(
        streams=[
            {'name': 'private_stream'},
        ],
        authorization_errors_fatal=False,
    )

    validate_against_openapi_schema(result, '/users/me/subscriptions', 'post',
                                    '400_0')

    result = nonadmin_client.add_subscriptions(
        streams=[
            {'name': 'private_stream'},
        ],
        authorization_errors_fatal=True,
    )

    validate_against_openapi_schema(result, '/users/me/subscriptions', 'post',
                                    '400_1')

@openapi_test_function("/users/{email}/presence:get")
def get_user_presence(client: Client) -> None:

    # {code_example|start}
    # Get presence information for "iago@zulip.com"
    result = client.get_user_presence('iago@zulip.com')
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/{email}/presence', 'get', '200')

@openapi_test_function("/users/me/presence:post")
def update_presence(client: Client) -> None:
    request = {
        'status': 'active',
        'ping_only': False,
        'new_user_input': False,
    }

    result = client.update_presence(request)

    assert result['result'] == 'success'

@openapi_test_function("/users:post")
def create_user(client: Client) -> None:

    # {code_example|start}
    # Create a user
    request = {
        'email': 'newbie@zulip.com',
        'password': 'temp',
        'full_name': 'New User',
    }
    result = client.create_user(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/users', 'post', '200')

    # Test "Email already used error"
    result = client.create_user(request)

    validate_against_openapi_schema(result, '/users', 'post', '400')

@openapi_test_function("/users:get")
def get_members(client: Client) -> None:

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

    # {code_example|start}
    # You may pass the `include_custom_profile_fields` query parameter as follows:
    result = client.get_members({'include_custom_profile_fields': True})
    # {code_example|end}

    validate_against_openapi_schema(result, '/users', 'get', '200')
    for member in result['members']:
        if member["is_bot"]:
            assert member.get('profile_data', None) is None
        else:
            assert member.get('profile_data', None) is not None

@openapi_test_function("/users/{user_id}:get")
def get_single_user(client: Client) -> None:

    # {code_example|start}
    # Fetch details on a user given a user ID
    user_id = 8
    result = client.get_user_by_id(user_id)
    # {code_example|end}
    validate_against_openapi_schema(result, '/users/{user_id}', 'get', '200')

    # {code_example|start}
    # If you'd like data on custom profile fields, you can request them as follows:
    result = client.get_user_by_id(user_id, include_custom_profile_fields=True)
    # {code_example|end}
    validate_against_openapi_schema(result, '/users/{user_id}', 'get', '200')

@openapi_test_function("/users/{user_id}:delete")
def deactivate_user(client: Client) -> None:

    # {code_example|start}
    # Deactivate a user
    user_id = 8
    result = client.deactivate_user_by_id(user_id)
    # {code_example|end}
    validate_against_openapi_schema(result, '/users/{user_id}', 'delete', '200')

@openapi_test_function("/users/{user_id}/reactivate:post")
def reactivate_user(client: Client) -> None:
    # {code_example|start}
    # Reactivate a user
    user_id = 8
    result = client.reactivate_user_by_id(user_id)
    # {code_example|end}
    validate_against_openapi_schema(result, '/users/{user_id}/reactivate', 'post', '200')

@openapi_test_function("/users/{user_id}:patch")
def update_user(client: Client) -> None:

    # {code_example|start}
    # Change a user's full name.
    user_id = 10
    result = client.update_user_by_id(user_id, full_name = "New Name")
    # {code_example|end}
    validate_against_openapi_schema(result, '/users/{user_id}', 'patch', '200')

    # {code_example|start}
    # Change value of the custom profile field with ID 9.
    user_id = 8
    result = client.update_user_by_id(user_id, profile_data = [{'id': 9, 'value': 'some data'}])
    # {code_example|end}
    validate_against_openapi_schema(result, '/users/{user_id}', 'patch', '400')

@openapi_test_function("/users/{user_id}/subscriptions/{stream_id}:get")
def get_subscription_status(client: Client) -> None:
    # {code_example|start}
    # Check whether a user is a subscriber to a given stream.
    user_id = 7
    stream_id = 1
    result = client.call_endpoint(
        url=f'/users/{user_id}/subscriptions/{stream_id}',
        method='GET',
    )
    # {code_example|end}
    validate_against_openapi_schema(result, '/users/{user_id}/subscriptions/{stream_id}', 'get', '200')

@openapi_test_function("/realm/filters:get")
def get_realm_filters(client: Client) -> None:

    # {code_example|start}
    # Fetch all the filters in this organization
    result = client.get_realm_filters()
    # {code_example|end}

    validate_against_openapi_schema(result, '/realm/filters', 'get', '200')

@openapi_test_function("/realm/filters:post")
def add_realm_filter(client: Client) -> None:

    # {code_example|start}
    # Add a filter to automatically linkify #<number> to the corresponding
    # issue in Zulip's server repo
    result = client.add_realm_filter('#(?P<id>[0-9]+)',
                                     'https://github.com/zulip/zulip/issues/%(id)s')
    # {code_example|end}

    validate_against_openapi_schema(result, '/realm/filters', 'post', '200')

@openapi_test_function("/realm/filters/{filter_id}:delete")
def remove_realm_filter(client: Client) -> None:

    # {code_example|start}
    # Remove the linkifier (realm_filter) with ID 1
    result = client.remove_realm_filter(1)
    # {code_example|end}

    validate_against_openapi_schema(result, '/realm/filters/{filter_id}', 'delete', '200')

@openapi_test_function("/users/me:get")
def get_profile(client: Client) -> None:

    # {code_example|start}
    # Get the profile of the user/bot that requests this endpoint,
    # which is `client` in this case:
    result = client.get_profile()
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/me', 'get', '200')

@openapi_test_function("/get_stream_id:get")
def get_stream_id(client: Client) -> int:

    # {code_example|start}
    # Get the ID of a given stream
    stream_name = 'new stream'
    result = client.get_stream_id(stream_name)
    # {code_example|end}

    validate_against_openapi_schema(result, '/get_stream_id', 'get', '200')

    return result['stream_id']

@openapi_test_function("/streams/{stream_id}:delete")
def delete_stream(client: Client, stream_id: int) -> None:
    result = client.add_subscriptions(
        streams=[
            {
                'name': 'stream to be deleted',
                'description': 'New stream for testing',
            },
        ],
    )

    # {code_example|start}
    # Delete the stream named 'new stream'
    stream_id = client.get_stream_id('stream to be deleted')['stream_id']
    result = client.delete_stream(stream_id)
    # {code_example|end}
    validate_against_openapi_schema(result, '/streams/{stream_id}', 'delete', '200')

    assert result['result'] == 'success'

@openapi_test_function("/streams:get")
def get_streams(client: Client) -> None:

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

@openapi_test_function("/streams/{stream_id}:patch")
def update_stream(client: Client, stream_id: int) -> None:

    # {code_example|start}
    # Update the stream by a given ID
    request = {
        'stream_id': stream_id,
        'stream_post_policy': 2,
        'is_private': True,
    }

    result = client.update_stream(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/streams/{stream_id}', 'patch', '200')
    assert result['result'] == 'success'

@openapi_test_function("/user_groups:get")
def get_user_groups(client: Client) -> int:

    # {code_example|start}
    # Get all user groups of the realm
    result = client.get_user_groups()
    # {code_example|end}

    validate_against_openapi_schema(result, '/user_groups', 'get', '200')
    hamlet_user_group = [u for u in result['user_groups']
                         if u['name'] == "hamletcharacters"][0]
    assert hamlet_user_group['description'] == 'Characters of Hamlet'

    marketing_user_group = [u for u in result['user_groups']
                            if u['name'] == "marketing"][0]
    return marketing_user_group['id']

def test_user_not_authorized_error(nonadmin_client: Client) -> None:
    result = nonadmin_client.get_streams(include_all_active=True)

    validate_against_openapi_schema(result, '/rest-error-handling', 'post', '400_2')

def get_subscribers(client: Client) -> None:

    result = client.get_subscribers(stream='new stream')
    assert result['subscribers'] == ['iago@zulip.com', 'newbie@zulip.com']

def get_user_agent(client: Client) -> None:

    result = client.get_user_agent()
    assert result.startswith('ZulipPython/')

@openapi_test_function("/users/me/subscriptions:get")
def list_subscriptions(client: Client) -> None:
    # {code_example|start}
    # Get all streams that the user is subscribed to
    result = client.list_subscriptions()
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/me/subscriptions',
                                    'get', '200')

    streams = [s for s in result['subscriptions'] if s['name'] == 'new stream']
    assert streams[0]['description'] == 'New stream for testing'

@openapi_test_function("/users/me/subscriptions:delete")
def remove_subscriptions(client: Client) -> None:

    # {code_example|start}
    # Unsubscribe from the stream "new stream"
    result = client.remove_subscriptions(
        ['new stream'],
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
        principals=['newbie@zulip.com'],
    )
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/me/subscriptions',
                                    'delete', '200')

@openapi_test_function("/users/me/subscriptions/muted_topics:patch")
def toggle_mute_topic(client: Client) -> None:

    # Send a test message
    message = {
        'type': 'stream',
        'to': 'Denmark',
        'topic': 'boat party',
    }
    client.call_endpoint(
        url='messages',
        method='POST',
        request=message,
    )

    # {code_example|start}
    # Mute the topic "boat party" in the stream "Denmark"
    request = {
        'stream': 'Denmark',
        'topic': 'boat party',
        'op': 'add',
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
        'op': 'remove',
    }

    result = client.mute_topic(request)
    # {code_example|end}

    validate_against_openapi_schema(result,
                                    '/users/me/subscriptions/muted_topics',
                                    'patch', '200')

@openapi_test_function("/mark_all_as_read:post")
def mark_all_as_read(client: Client) -> None:

    # {code_example|start}
    # Mark all of the user's unread messages as read
    result = client.mark_all_as_read()
    # {code_example|end}

    validate_against_openapi_schema(result, '/mark_all_as_read', 'post', '200')

@openapi_test_function("/mark_stream_as_read:post")
def mark_stream_as_read(client: Client) -> None:

    # {code_example|start}
    # Mark the unread messages in stream with ID "1" as read
    result = client.mark_stream_as_read(1)
    # {code_example|end}

    validate_against_openapi_schema(result, '/mark_stream_as_read', 'post', '200')

@openapi_test_function("/mark_topic_as_read:post")
def mark_topic_as_read(client: Client) -> None:

    # Grab an existing topic name
    topic_name = client.get_stream_topics(1)['topics'][0]['name']

    # {code_example|start}
    # Mark the unread messages in stream 1's topic "topic_name" as read
    result = client.mark_topic_as_read(1, topic_name)
    # {code_example|end}

    validate_against_openapi_schema(result, '/mark_stream_as_read', 'post', '200')

@openapi_test_function("/users/me/subscriptions/properties:post")
def update_subscription_settings(client: Client) -> None:

    # {code_example|start}
    # Update the user's subscription in stream #1 to pin it to the top of the
    # stream list; and in stream #3 to have the hex color "f00"
    request = [{
        'stream_id': 1,
        'property': 'pin_to_top',
        'value': True,
    }, {
        'stream_id': 3,
        'property': 'color',
        'value': '#f00f00',
    }]
    result = client.update_subscription_settings(request)
    # {code_example|end}

    validate_against_openapi_schema(result,
                                    '/users/me/subscriptions/properties',
                                    'POST', '200')

@openapi_test_function("/messages/render:post")
def render_message(client: Client) -> None:

    # {code_example|start}
    # Render a message
    request = {
        'content': '**foo**',
    }
    result = client.render_message(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/render', 'post', '200')

@openapi_test_function("/messages:get")
def get_messages(client: Client) -> None:

    # {code_example|start}
    # Get the 100 last messages sent by "iago@zulip.com" to the stream "Verona"
    request: Dict[str, Any] = {
        'anchor': 'newest',
        'num_before': 100,
        'num_after': 0,
        'narrow': [{'operator': 'sender', 'operand': 'iago@zulip.com'},
                   {'operator': 'stream', 'operand': 'Verona'}],
    }
    result = client.get_messages(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages', 'get', '200')
    assert len(result['messages']) <= request['num_before']

@openapi_test_function("/messages/matches_narrow:get")
def check_messages_match_narrow(client: Client) -> None:
    message = {
        "type": "stream",
        "to": "Verona",
        "topic": "test_topic",
        "content": "http://foo.com"
    }
    msg_ids = []
    response = client.send_message(message)
    msg_ids.append(response['id'])
    message['content'] = "no link here"
    response = client.send_message(message)
    msg_ids.append(response['id'])

    # {code_example|start}
    # Check which messages within an array match a narrow.
    request = {
        'msg_ids': msg_ids,
        'narrow': [{'operator': 'has', 'operand': 'link'}],
    }

    result = client.call_endpoint(
        url='messages/matches_narrow',
        method='GET',
        request=request
    )
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/matches_narrow', 'get', '200')

@openapi_test_function("/messages/{message_id}:get")
def get_raw_message(client: Client, message_id: int) -> None:

    assert int(message_id)

    # {code_example|start}
    # Get the raw content of the message with ID "message_id"
    result = client.get_raw_message(message_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/{message_id}', 'get',
                                    '200')

@openapi_test_function("/attachments:get")
def get_attachments(client: Client) -> None:
    # {code_example|start}
    # Get your attachments.

    result = client.get_attachments()
    # {code_example|end}
    validate_against_openapi_schema(result, '/attachments', 'get', '200')

@openapi_test_function("/messages:post")
def send_message(client: Client) -> int:

    request: Dict[str, Any] = {}

    # {code_example|start}
    # Send a stream message
    request = {
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts.",
    }
    result = client.send_message(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages', 'post', '200')

    # test that the message was actually sent
    message_id = result['id']
    url = 'messages/' + str(message_id)
    result = client.call_endpoint(
        url=url,
        method='GET',
    )
    assert result['result'] == 'success'
    assert result['raw_content'] == request['content']

    ensure_users([10], ['hamlet'])

    # {code_example|start}
    # Send a private message
    user_id = 10
    request = {
        "type": "private",
        "to": [user_id],
        "content": "With mirth and laughter let old wrinkles come.",
    }
    result = client.send_message(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages', 'post', '200')

    # test that the message was actually sent
    message_id = result['id']
    url = 'messages/' + str(message_id)
    result = client.call_endpoint(
        url=url,
        method='GET',
    )
    assert result['result'] == 'success'
    assert result['raw_content'] == request['content']

    return message_id

@openapi_test_function("/messages/{message_id}/reactions:post")
def add_reaction(client: Client, message_id: int) -> None:
    # {code_example|start}
    # Add an emoji reaction
    request = {
        'message_id': str(message_id),
        'emoji_name': 'octopus',
    }

    result = client.add_reaction(request)
    # {code_example|end}
    validate_against_openapi_schema(result, '/messages/{message_id}/reactions', 'post', '200')

@openapi_test_function("/messages/{message_id}/reactions:delete")
def remove_reaction(client: Client, message_id: int) -> None:
    # {code_example|start}
    # Remove an emoji reaction
    request = {
        'message_id': str(message_id),
        'emoji_name': 'octopus',
    }

    result = client.remove_reaction(request)
    # {code_example|end}
    validate_against_openapi_schema(result, '/messages/{message_id}/reactions', 'delete', '200')

def test_nonexistent_stream_error(client: Client) -> None:
    request = {
        "type": "stream",
        "to": "nonexistent_stream",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts.",
    }
    result = client.send_message(request)

    validate_against_openapi_schema(result, '/messages', 'post',
                                    '400_0')

def test_private_message_invalid_recipient(client: Client) -> None:
    request = {
        "type": "private",
        "to": "eeshan@zulip.com",
        "content": "With mirth and laughter let old wrinkles come.",
    }
    result = client.send_message(request)

    validate_against_openapi_schema(result, '/messages', 'post',
                                    '400_1')

@openapi_test_function("/messages/{message_id}:patch")
def update_message(client: Client, message_id: int) -> None:

    assert int(message_id)

    # {code_example|start}
    # Edit a message
    # (make sure that message_id below is set to the ID of the
    # message you wish to update)
    request = {
        "message_id": message_id,
        "content": "New content",
    }
    result = client.update_message(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/{message_id}', 'patch',
                                    '200')

    # test it was actually updated
    url = 'messages/' + str(message_id)
    result = client.call_endpoint(
        url=url,
        method='GET',
    )
    assert result['result'] == 'success'
    assert result['raw_content'] == request['content']

def test_update_message_edit_permission_error(client: Client, nonadmin_client: Client) -> None:
    request = {
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts.",
    }
    result = client.send_message(request)

    request = {
        "message_id": result["id"],
        "content": "New content",
    }
    result = nonadmin_client.update_message(request)

    validate_against_openapi_schema(result, '/messages/{message_id}', 'patch', '400')

@openapi_test_function("/messages/{message_id}:delete")
def delete_message(client: Client, message_id: int) -> None:

    # {code_example|start}
    # Delete the message with ID "message_id"
    result = client.delete_message(message_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/{message_id}', 'delete',
                                    '200')

def test_delete_message_edit_permission_error(client: Client, nonadmin_client: Client) -> None:
    request = {
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts.",
    }
    result = client.send_message(request)

    result = nonadmin_client.delete_message(result['id'])

    validate_against_openapi_schema(result, '/messages/{message_id}', 'delete',
                                    '400_1')

@openapi_test_function("/messages/{message_id}/history:get")
def get_message_history(client: Client, message_id: int) -> None:

    # {code_example|start}
    # Get the edit history for message with ID "message_id"
    result = client.get_message_history(message_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/{message_id}/history',
                                    'get', '200')

@openapi_test_function("/realm/emoji:get")
def get_realm_emoji(client: Client) -> None:

    # {code_example|start}
    result = client.get_realm_emoji()
    # {code_example|end}

    validate_against_openapi_schema(result, '/realm/emoji', 'GET', '200')

@openapi_test_function("/messages/flags:post")
def update_message_flags(client: Client) -> None:

    # Send a few test messages
    request: Dict[str, Any] = {
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts.",
    }
    message_ids = []
    for i in range(0, 3):
        message_ids.append(client.send_message(request)['id'])

    # {code_example|start}
    # Add the "read" flag to the messages with IDs in "message_ids"
    request = {
        'messages': message_ids,
        'op': 'add',
        'flag': 'read',
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
        'flag': 'starred',
    }
    result = client.update_message_flags(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/messages/flags', 'post',
                                    '200')

def register_queue_all_events(client: Client) -> str:

    # Register the queue and get all events
    # Mainly for verifying schema of /register.
    result = client.register()

    validate_against_openapi_schema(result, '/register', 'post', '200')
    return result['queue_id']

@openapi_test_function("/register:post")
def register_queue(client: Client) -> str:

    # {code_example|start}
    # Register the queue
    result = client.register(
        event_types=['message', 'realm_emoji'],
    )
    # {code_example|end}

    validate_against_openapi_schema(result, '/register', 'post', '200')
    return result['queue_id']

@openapi_test_function("/events:delete")
def deregister_queue(client: Client, queue_id: str) -> None:

    # {code_example|start}
    # Delete a queue (queue_id is the ID of the queue
    # to be removed)
    result = client.deregister(queue_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/events', 'delete', '200')

    # Test "BAD_EVENT_QUEUE_ID" error
    result = client.deregister(queue_id)
    validate_against_openapi_schema(result, '/events', 'delete', '400')

@openapi_test_function("/server_settings:get")
def get_server_settings(client: Client) -> None:

    # {code_example|start}
    # Fetch the settings for this server
    result = client.get_server_settings()
    # {code_example|end}

    validate_against_openapi_schema(result, '/server_settings', 'get', '200')

@openapi_test_function("/settings/notifications:patch")
def update_notification_settings(client: Client) -> None:

    # {code_example|start}
    # Enable push notifications even when online
    request = {
        'enable_offline_push_notifications': True,
        'enable_online_push_notifications': True,
    }
    result = client.update_notification_settings(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/settings/notifications', 'patch', '200')

@openapi_test_function("/user_uploads:post")
def upload_file(client: Client) -> None:
    path_to_file = os.path.join(ZULIP_DIR, 'zerver', 'tests', 'images', 'img.jpg')

    # {code_example|start}
    # Upload a file
    with open(path_to_file, 'rb') as fp:
        result = client.call_endpoint(
            'user_uploads',
            method='POST',
            files=[fp],
        )

    client.send_message({
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "Check out [this picture]({}) of my castle!".format(result['uri']),
    })
    # {code_example|end}

    validate_against_openapi_schema(result, '/user_uploads', 'post', '200')

@openapi_test_function("/users/me/{stream_id}/topics:get")
def get_stream_topics(client: Client, stream_id: int) -> None:

    # {code_example|start}
    result = client.get_stream_topics(stream_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/users/me/{stream_id}/topics',
                                    'get', '200')

@openapi_test_function("/typing:post")
def set_typing_status(client: Client) -> None:
    ensure_users([10, 11], ['hamlet', 'iago'])

    # {code_example|start}
    # The user has started to type in the group PM with Iago and Polonius
    user_id1 = 10
    user_id2 = 11

    request = {
        'op': 'start',
        'to': [user_id1, user_id2],
    }
    result = client.set_typing_status(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/typing', 'post', '200')

    # {code_example|start}
    # The user has finished typing in the group PM with Iago and Polonius
    user_id1 = 10
    user_id2 = 11

    request = {
        'op': 'stop',
        'to': [user_id1, user_id2],
    }
    result = client.set_typing_status(request)
    # {code_example|end}

    validate_against_openapi_schema(result, '/typing', 'post', '200')

@openapi_test_function("/realm/emoji/{emoji_name}:post")
def upload_custom_emoji(client: Client) -> None:
    emoji_path = os.path.join(ZULIP_DIR, 'zerver', 'tests', 'images', 'img.jpg')

    # {code_example|start}
    # Upload a custom emoji; assume `emoji_path` is the path to your image.
    with open(emoji_path, 'rb') as fp:
        emoji_name = 'my_custom_emoji'
        result = client.call_endpoint(
            f'realm/emoji/{emoji_name}',
            method='POST',
            files=[fp],
        )
    # {code_example|end}

    validate_against_openapi_schema(result,
                                    '/realm/emoji/{emoji_name}',
                                    'post', '200')

@openapi_test_function("/users/me/alert_words:get")
def get_alert_words(client: Client) -> None:
    result = client.get_alert_words()

    assert result['result'] == 'success'

@openapi_test_function("/users/me/alert_words:post")
def add_alert_words(client: Client) -> None:
    word = ['foo', 'bar']

    result = client.add_alert_words(word)

    assert result['result'] == 'success'

@openapi_test_function("/users/me/alert_words:delete")
def remove_alert_words(client: Client) -> None:
    word = ['foo']

    result = client.remove_alert_words(word)

    assert result['result'] == 'success'

@openapi_test_function("/user_groups/create:post")
def create_user_group(client: Client) -> None:
    ensure_users([6, 7, 8, 10], ['aaron', 'zoe', 'cordelia', 'hamlet'])

    # {code_example|start}
    request = {
        'name': 'marketing',
        'description': 'The marketing team.',
        'members': [6, 7, 8, 10],
    }

    result = client.create_user_group(request)
    # {code_example|end}
    validate_against_openapi_schema(result, '/user_groups/create', 'post', '200')

    assert result['result'] == 'success'

@openapi_test_function("/user_groups/{group_id}:patch")
def update_user_group(client: Client, group_id: int) -> None:
    # {code_example|start}
    request = {
        'group_id': group_id,
        'name': 'marketing',
        'description': 'The marketing team.',
    }

    result = client.update_user_group(request)
    # {code_example|end}
    assert result['result'] == 'success'

@openapi_test_function("/user_groups/{group_id}:delete")
def remove_user_group(client: Client, group_id: int) -> None:
    # {code_example|start}
    result = client.remove_user_group(group_id)
    # {code_example|end}

    validate_against_openapi_schema(result, '/user_groups/{group_id}', 'delete', '200')
    assert result['result'] == 'success'

@openapi_test_function("/user_groups/{group_id}/members:post")
def update_user_group_members(client: Client, group_id: int) -> None:
    ensure_users([8, 10, 11], ['cordelia', 'hamlet', 'iago'])

    request = {
        'group_id': group_id,
        'delete': [8, 10],
        'add': [11],
    }

    result = client.update_user_group_members(request)

    assert result['result'] == 'success'

def test_invalid_api_key(client_with_invalid_key: Client) -> None:
    result = client_with_invalid_key.list_subscriptions()
    validate_against_openapi_schema(result, '/rest-error-handling', 'post', '400_0')

def test_missing_request_argument(client: Client) -> None:
    result = client.render_message({})

    validate_against_openapi_schema(result, '/rest-error-handling', 'post', '400_1')


def test_invalid_stream_error(client: Client) -> None:
    result = client.get_stream_id('nonexistent')

    validate_against_openapi_schema(result, '/get_stream_id', 'get', '400')


# SETUP METHODS FOLLOW
def test_against_fixture(result: Dict[str, Any], fixture: Dict[str, Any], check_if_equal: Optional[Iterable[str]] = None, check_if_exists: Optional[Iterable[str]] = None) -> None:
    assertLength(result, fixture)

    if check_if_equal is None and check_if_exists is None:
        for key, value in fixture.items():
            assertEqual(key, result, fixture)

    if check_if_equal is not None:
        for key in check_if_equal:
            assertEqual(key, result, fixture)

    if check_if_exists is not None:
        for key in check_if_exists:
            assertIn(key, result)

def assertEqual(key: str, result: Dict[str, Any], fixture: Dict[str, Any]) -> None:
    if result[key] != fixture[key]:
        first = f"{key} = {result[key]}"
        second = f"{key} = {fixture[key]}"
        raise AssertionError("Actual and expected outputs do not match; showing diff:\n" +
                             mdiff.diff_strings(first, second))
    else:
        assert result[key] == fixture[key]

def assertLength(result: Dict[str, Any], fixture: Dict[str, Any]) -> None:
    if len(result) != len(fixture):
        result_string = json.dumps(result, indent=4, sort_keys=True)
        fixture_string = json.dumps(fixture, indent=4, sort_keys=True)
        raise AssertionError("The lengths of the actual and expected outputs do not match; showing diff:\n" +
                             mdiff.diff_strings(result_string, fixture_string))
    else:
        assert len(result) == len(fixture)

def assertIn(key: str, result: Dict[str, Any]) -> None:
    if key not in result.keys():
        raise AssertionError(
            f"The actual output does not contain the the key `{key}`.",
        )
    else:
        assert key in result

def test_messages(client: Client, nonadmin_client: Client) -> None:

    render_message(client)
    message_id = send_message(client)
    add_reaction(client, message_id)
    remove_reaction(client, message_id)
    update_message(client, message_id)
    get_raw_message(client, message_id)
    get_messages(client)
    check_messages_match_narrow(client)
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

def test_users(client: Client) -> None:

    create_user(client)
    get_members(client)
    get_single_user(client)
    deactivate_user(client)
    reactivate_user(client)
    update_user(client)
    get_subscription_status(client)
    get_profile(client)
    update_notification_settings(client)
    upload_file(client)
    get_attachments(client)
    set_typing_status(client)
    update_presence(client)
    get_user_presence(client)
    create_user_group(client)
    group_id = get_user_groups(client)
    update_user_group(client, group_id)
    update_user_group_members(client, group_id)
    remove_user_group(client, group_id)
    get_alert_words(client)
    add_alert_words(client)
    remove_alert_words(client)

def test_streams(client: Client, nonadmin_client: Client) -> None:

    add_subscriptions(client)
    test_add_subscriptions_already_subscribed(client)
    list_subscriptions(client)
    stream_id = get_stream_id(client)
    update_stream(client, stream_id)
    get_streams(client)
    get_subscribers(client)
    remove_subscriptions(client)
    toggle_mute_topic(client)
    update_subscription_settings(client)
    update_notification_settings(client)
    get_stream_topics(client, 1)
    delete_stream(client, stream_id)

    test_user_not_authorized_error(nonadmin_client)
    test_authorization_errors_fatal(client, nonadmin_client)


def test_queues(client: Client) -> None:
    # Note that the example for api/get-events is not tested.
    # Since, methods such as client.get_events() or client.call_on_each_message
    # are blocking calls and since the event queue backend is already
    # thoroughly tested in zerver/tests/test_event_queue.py, it is not worth
    # the effort to come up with asynchronous logic for testing those here.
    queue_id = register_queue(client)
    deregister_queue(client, queue_id)
    register_queue_all_events(client)

def test_server_organizations(client: Client) -> None:

    get_realm_filters(client)
    add_realm_filter(client)
    get_server_settings(client)
    remove_realm_filter(client)
    get_realm_emoji(client)
    upload_custom_emoji(client)

def test_errors(client: Client) -> None:
    test_missing_request_argument(client)
    test_invalid_stream_error(client)

def test_the_api(client: Client, nonadmin_client: Client) -> None:

    get_user_agent(client)
    test_users(client)
    test_streams(client, nonadmin_client)
    test_messages(client, nonadmin_client)
    test_queues(client)
    test_server_organizations(client)
    test_errors(client)

    sys.stdout.flush()
    if REGISTERED_TEST_FUNCTIONS != CALLED_TEST_FUNCTIONS:
        print("Error!  Some @openapi_test_function tests were never called:")
        print("  ", REGISTERED_TEST_FUNCTIONS - CALLED_TEST_FUNCTIONS)
        sys.exit(1)
