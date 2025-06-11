# Zulip's OpenAPI-based API documentation system is documented at
#   https://zulip.readthedocs.io/en/latest/documentation/api.html
#
# This file defines the Python code examples that appears in Zulip's
# REST API documentation, and also contains a system for running the
# example code as part of the `tools/test-api` test suite.
#
# The actual documentation appears within these blocks:
#   # {code_example|start}
#   Code here
#   # {code_example|end}
#
# Whereas the surrounding code is test setup logic.

import json
import os
import sys
from collections.abc import Callable
from email.headerregistry import Address
from functools import wraps
from typing import Any, TypeVar

from typing_extensions import ParamSpec
from zulip import Client

from zerver.models.realms import get_realm
from zerver.models.users import get_user
from zerver.openapi.openapi import validate_against_openapi_schema

ZULIP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_FUNCTIONS: dict[str, Callable[..., object]] = {}
REGISTERED_TEST_FUNCTIONS: set[str] = set()
CALLED_TEST_FUNCTIONS: set[str] = set()

ParamT = ParamSpec("ParamT")
ReturnT = TypeVar("ReturnT")


def openapi_test_function(
    endpoint: str,
) -> Callable[[Callable[ParamT, ReturnT]], Callable[ParamT, ReturnT]]:
    """This decorator is used to register an OpenAPI test function with
    its endpoint. Example usage:

    @openapi_test_function("/messages/render:post")
    def ...
    """

    def wrapper(test_func: Callable[ParamT, ReturnT]) -> Callable[ParamT, ReturnT]:
        @wraps(test_func)
        def _record_calls_wrapper(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
            CALLED_TEST_FUNCTIONS.add(test_func.__name__)
            return test_func(*args, **kwargs)

        REGISTERED_TEST_FUNCTIONS.add(test_func.__name__)
        TEST_FUNCTIONS[endpoint] = _record_calls_wrapper

        return _record_calls_wrapper

    return wrapper


def ensure_users(ids_list: list[int], user_names: list[str]) -> None:
    # Ensure that the list of user ids (ids_list)
    # matches the users we want to refer to (user_names).
    realm = get_realm("zulip")
    user_ids = [
        get_user(Address(username=name, domain="zulip.com").addr_spec, realm).id
        for name in user_names
    ]
    assert ids_list == user_ids


def assert_success_response(response: dict[str, Any]) -> None:
    assert "result" in response
    assert response["result"] == "success"


def assert_error_response(response: dict[str, Any], code: str = "BAD_REQUEST") -> None:
    assert "result" in response
    assert response["result"] == "error"
    assert "code" in response
    assert response["code"] == code


def get_subscribed_stream_ids(client: Client) -> list[int]:
    streams = client.get_subscriptions()
    stream_ids = [stream["stream_id"] for stream in streams["subscriptions"]]
    return stream_ids


def validate_message(client: Client, message_id: int, content: Any) -> None:
    url = "messages/" + str(message_id)
    result = client.call_endpoint(
        url=url,
        method="GET",
    )
    assert result["raw_content"] == content


def set_moderation_request_channel(client: Client, channel: str | None = "core team") -> None:
    if channel is None:
        # Disable moderation request feature
        channel_id = "-1"
    else:
        channel_id = client.get_stream_id(channel)["stream_id"]

    request = dict(moderation_request_channel_id=channel_id)
    result = client.call_endpoint("/realm", method="PATCH", request=request)
    assert_success_response(result)


def get_users_messages(client: Client, user_id: int) -> list[dict[str, Any]]:
    request: dict[str, Any] = {
        "anchor": "newest",
        "num_before": 100,
        "num_after": 0,
        "narrow": [{"operator": "sender", "operand": user_id}],
    }
    result = client.get_messages(request)
    assert_success_response(result)
    return result["messages"]


@openapi_test_function("/users/me/subscriptions:post")
def add_subscriptions(client: Client) -> None:
    # {code_example|start}
    # Create and subscribe to channel "python-test".
    result = client.add_subscriptions(
        streams=[
            {
                "name": "python-test",
                "description": "Channel for testing Python",
            },
        ],
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions", "post", "200")

    user_id = 25
    ensure_users([user_id], ["newbie"])
    # {code_example|start}
    # To subscribe other users to a channel, you may pass
    # the `principals` argument, like so:
    result = client.add_subscriptions(
        streams=[
            {"name": "python-test"},
        ],
        principals=[user_id],
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions", "post", "200")
    assert str(user_id) in result["subscribed"]


def test_add_subscriptions_already_subscribed(client: Client) -> None:
    result = client.add_subscriptions(
        streams=[
            {"name": "python-test"},
        ],
        principals=["newbie@zulip.com"],
    )
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions", "post", "200")


def test_authorization_errors_fatal(client: Client, nonadmin_client: Client) -> None:
    client.add_subscriptions(
        streams=[
            {"name": "private-channel"},
        ],
    )
    stream_id = client.get_stream_id("private-channel")["stream_id"]
    client.call_endpoint(
        f"streams/{stream_id}",
        method="PATCH",
        request={"is_private": True},
    )
    result = nonadmin_client.add_subscriptions(
        streams=[
            {"name": "private-channel"},
        ],
        authorization_errors_fatal=False,
    )
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions", "post", "200")

    result = nonadmin_client.add_subscriptions(
        streams=[
            {"name": "private-channel"},
        ],
        authorization_errors_fatal=True,
    )
    assert_error_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions", "post", "400")


@openapi_test_function("/realm/presence:get")
def get_presence(client: Client) -> None:
    # {code_example|start}
    # Get presence information of all the users in an organization.
    result = client.get_realm_presence()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/presence", "get", "200")


@openapi_test_function("/default_streams:post")
def add_default_stream(client: Client) -> None:
    client.add_subscriptions(
        streams=[
            {
                "name": "test channel",
                "description": "New channel for testing",
            },
        ],
    )
    stream_id = client.get_stream_id("test channel")["stream_id"]
    # {code_example|start}
    # Add a channel to the set of default channels for new users.
    result = client.add_default_stream(stream_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/default_streams", "post", "200")


@openapi_test_function("/default_streams:delete")
def remove_default_stream(client: Client) -> None:
    stream_id = client.get_stream_id("test channel")["stream_id"]
    # {code_example|start}
    # Remove a channel from the set of default channels for new users.
    request = {"stream_id": stream_id}
    result = client.call_endpoint(
        url="/default_streams",
        method="DELETE",
        request=request,
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/default_streams", "delete", "200")


@openapi_test_function("/users/{user_id_or_email}/presence:get")
def get_user_presence(client: Client) -> None:
    # {code_example|start}
    # Get presence information for "iago@zulip.com".
    result = client.get_user_presence("iago@zulip.com")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/{user_id_or_email}/presence", "get", "200")


@openapi_test_function("/users/{user_id}/status:get")
def get_user_status(client: Client) -> None:
    user_id = 11
    ensure_users([user_id], ["iago"])
    # {code_example|start}
    # Get the status currently set by a user.
    result = client.call_endpoint(
        url=f"/users/{user_id}/status",
        method="GET",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/{user_id}/status", "get", "200")


@openapi_test_function("/users/me/presence:post")
def update_presence(client: Client) -> None:
    # {code_example|start}
    # Update your presence.
    request = {
        "status": "active",
        "ping_only": False,
        "new_user_input": False,
        "last_update_id": -1,
    }
    result = client.update_presence(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/presence", "post", "200")


@openapi_test_function("/users:post")
def create_user(client: Client) -> None:
    # {code_example|start}
    # Create a user.
    request = {
        "email": "newbie@zulip.com",
        "password": "temp",
        "full_name": "New User",
    }
    result = client.create_user(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users", "post", "200")

    # Test "Email already used error".
    result = client.create_user(request)
    assert_error_response(result)
    validate_against_openapi_schema(result, "/users", "post", "400")


@openapi_test_function("/users/me/status:post")
def update_status(client: Client) -> None:
    # {code_example|start}
    # The request contains the new status and "away" boolean.
    request = {
        "status_text": "on vacation",
        "away": False,
        "emoji_name": "car",
        "emoji_code": "1f697",
        "reaction_type": "unicode_emoji",
        "scheduled_end_time": 1706625127,
    }
    result = client.call_endpoint(url="/users/me/status", method="POST", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/status", "post", "200")

    # Test "status_text is too long error".
    request = {
        "status_text": "This is a message that exceeds 60 characters, and so should throw an error.",
        "away": "false",
    }
    result = client.call_endpoint(url="/users/me/status", method="POST", request=request)
    assert_error_response(result)
    validate_against_openapi_schema(result, "/users/me/status", "post", "400")


@openapi_test_function("/users:get")
def get_members(client: Client) -> None:
    # {code_example|start}
    # Get all users in the organization.
    result = client.get_members()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users", "get", "200")
    members = [m for m in result["members"] if m["email"] == "newbie@zulip.com"]
    assert len(members) == 1
    newbie = members[0]
    assert not newbie["is_admin"]
    assert newbie["full_name"] == "New User"

    # {code_example|start}
    # You may pass the `client_gravatar` query parameter as follows:
    result = client.get_members({"client_gravatar": False})
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users", "get", "200")
    assert result["members"][0]["avatar_url"] is not None

    # {code_example|start}
    # You may pass the `include_custom_profile_fields` query parameter as follows:
    result = client.get_members({"include_custom_profile_fields": True})
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users", "get", "200")
    for member in result["members"]:
        if member["is_bot"]:
            assert member.get("profile_data", None) is None
        else:
            assert member.get("profile_data", None) is not None
        assert member["avatar_url"] is None


@openapi_test_function("/users/{email}:get")
def get_user_by_email(client: Client) -> None:
    email = "iago@zulip.com"
    # {code_example|start}
    result = client.call_endpoint(
        url=f"/users/{email}",
        method="GET",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/{email}", "get", "200")


@openapi_test_function("/invites:get")
def get_invitations(client: Client) -> None:
    # {code_example|start}
    # Get all invitations.
    result = client.call_endpoint(url="/invites", method="GET")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/invites", "get", "200")


@openapi_test_function("/invites:post")
def send_invitations(client: Client) -> None:
    stream_ids = get_subscribed_stream_ids(client)[:3]
    # {code_example|start}
    # Send invitations.
    request = {
        "invitee_emails": "example@zulip.com, logan@zulip.com",
        "invite_expires_in_minutes": 60 * 24 * 10,  # 10 days
        "invite_as": 400,
        "stream_ids": stream_ids,
    }
    result = client.call_endpoint(url="/invites", method="POST", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/invites", "post", "200")


@openapi_test_function("/invites/multiuse:post")
def create_reusable_invitation_link(client: Client) -> None:
    stream_ids = get_subscribed_stream_ids(client)[:3]
    # {code_example|start}
    # Create a reusable invitation link.
    request = {
        "invite_expires_in_minutes": 60 * 24 * 10,  # 10 days
        "invite_as": 400,
        "stream_ids": stream_ids,
    }
    result = client.call_endpoint(url="/invites/multiuse", method="POST", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/invites/multiuse", "post", "200")


@openapi_test_function("/invites/{invite_id}:delete")
def revoke_email_invitation(client: Client) -> None:
    # Send email invitation.
    email = "delete-invite@zulip.com"
    request = {
        "invitee_emails": email,
        "stream_ids": [],
    }
    client.call_endpoint(url="/invites", method="POST", request=request)
    # Get invitation ID.
    invites = client.call_endpoint(url="/invites", method="GET")["invites"]
    invite = [s for s in invites if not s["is_multiuse"] and s["email"] == email]
    assert len(invite) == 1
    invite_id = invite[0]["id"]
    # {code_example|start}
    # Revoke email invitation.
    result = client.call_endpoint(url=f"/invites/{invite_id}", method="DELETE")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/invites/{invite_id}", "delete", "200")


@openapi_test_function("/invites/multiuse/{invite_id}:delete")
def revoke_reusable_invitation_link(client: Client) -> None:
    # Create multiuse invitation link.
    invite_url = client.call_endpoint(url="/invites/multiuse", method="POST", request={})[
        "invite_link"
    ]
    # Get invitation ID.
    invites = client.call_endpoint(url="/invites", method="GET")["invites"]
    invite = [s for s in invites if s["is_multiuse"] and s["link_url"] == invite_url]
    assert len(invite) == 1
    invite_id = invite[0]["id"]
    # {code_example|start}
    # Revoke reusable invitation link.
    result = client.call_endpoint(url=f"/invites/multiuse/{invite_id}", method="DELETE")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/invites/multiuse/{invite_id}", "delete", "200")


@openapi_test_function("/invites/{invite_id}/resend:post")
def resend_email_invitation(client: Client) -> None:
    invites = client.call_endpoint(url="/invites", method="GET")["invites"]
    email_invites = [s for s in invites if not s["is_multiuse"]]
    assert len(email_invites) > 0
    invite_id = email_invites[0]["id"]
    # {code_example|start}
    # Resend email invitation.
    result = client.call_endpoint(url=f"/invites/{invite_id}/resend", method="POST")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/invites/{invite_id}/resend", "post", "200")


@openapi_test_function("/users/{user_id}:get")
def get_single_user(client: Client) -> None:
    user_id = 8
    ensure_users([user_id], ["cordelia"])
    # {code_example|start}
    # Fetch details on a user given a user ID.
    result = client.get_user_by_id(user_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/{user_id}", "get", "200")

    # {code_example|start}
    # If you'd like data on custom profile fields, you can request them as follows:
    result = client.get_user_by_id(user_id, include_custom_profile_fields=True)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/{user_id}", "get", "200")


@openapi_test_function("/users/{user_id}:delete")
def deactivate_user(client: Client) -> None:
    user_id = 8
    ensure_users([user_id], ["cordelia"])
    # {code_example|start}
    # Deactivate a user given a user ID.
    result = client.deactivate_user_by_id(user_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/{user_id}", "delete", "200")


@openapi_test_function("/users/{user_id}/reactivate:post")
def reactivate_user(client: Client) -> None:
    user_id = 8
    ensure_users([user_id], ["cordelia"])
    # {code_example|start}
    # Reactivate a user given a user ID.
    result = client.reactivate_user_by_id(user_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/{user_id}/reactivate", "post", "200")


@openapi_test_function("/users/{user_id}:patch")
def update_user(client: Client) -> None:
    ensure_users([8, 10], ["cordelia", "hamlet"])
    user_id = 10
    # {code_example|start}
    # Change a user's full name given a user ID.
    result = client.update_user_by_id(user_id, full_name="New Name")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/{user_id}", "patch", "200")

    user_id = 8
    # {code_example|start}
    # Change value of the custom profile field with ID 9.
    result = client.update_user_by_id(user_id, profile_data=[{"id": 9, "value": "some data"}])
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/{user_id}", "patch", "200")


@openapi_test_function("/users/{user_id}/subscriptions/{stream_id}:get")
def get_subscription_status(client: Client) -> None:
    user_id = 7
    ensure_users([user_id], ["zoe"])
    stream_id = client.get_subscriptions()["subscriptions"][0]["stream_id"]
    # {code_example|start}
    # Check whether a user is a subscriber to a given channel.
    result = client.call_endpoint(
        url=f"/users/{user_id}/subscriptions/{stream_id}",
        method="GET",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(
        result, "/users/{user_id}/subscriptions/{stream_id}", "get", "200"
    )


@openapi_test_function("/realm/linkifiers:get")
def get_realm_linkifiers(client: Client) -> None:
    # {code_example|start}
    # Fetch all the linkifiers in this organization.
    result = client.call_endpoint(
        url="/realm/linkifiers",
        method="GET",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/linkifiers", "get", "200")


@openapi_test_function("/realm/linkifiers:patch")
def reorder_realm_linkifiers(client: Client) -> None:
    realm_linkifiers = client.call_endpoint(
        url="/realm/linkifiers",
        method="GET",
    )
    reordered_linkifiers = [linkifier["id"] for linkifier in realm_linkifiers["linkifiers"]][::-1]
    # {code_example|start}
    # Reorder the linkifiers in the user's organization.
    request = {"ordered_linkifier_ids": json.dumps(reordered_linkifiers)}
    result = client.call_endpoint(url="/realm/linkifiers", method="PATCH", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/linkifiers", "patch", "200")


@openapi_test_function("/realm/profile_fields:get")
def get_realm_profile_fields(client: Client) -> None:
    # {code_example|start}
    # Fetch all the custom profile fields in the user's organization.
    result = client.call_endpoint(
        url="/realm/profile_fields",
        method="GET",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/profile_fields", "get", "200")


@openapi_test_function("/realm/profile_fields:patch")
def reorder_realm_profile_fields(client: Client) -> None:
    realm_profile_fields = client.call_endpoint(
        url="/realm/profile_fields",
        method="GET",
    )
    realm_profile_field_ids = [field["id"] for field in realm_profile_fields["custom_fields"]]
    reordered_profile_fields = realm_profile_field_ids[::-1]
    # {code_example|start}
    # Reorder the custom profile fields in the user's organization.
    request = {"order": json.dumps(reordered_profile_fields)}
    result = client.call_endpoint(url="/realm/profile_fields", method="PATCH", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/profile_fields", "patch", "200")


@openapi_test_function("/realm/profile_fields:post")
def create_realm_profile_field(client: Client) -> None:
    # {code_example|start}
    # Create a custom profile field in the user's organization.
    request = {"name": "Phone", "hint": "Contact no.", "field_type": 1}
    result = client.call_endpoint(url="/realm/profile_fields", method="POST", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/profile_fields", "post", "200")


@openapi_test_function("/realm/filters:post")
def add_realm_filter(client: Client) -> int:
    # TODO: Switch back to using client.add_realm_filter when python-zulip-api
    # begins to support url_template.

    # {code_example|start}
    # Add a filter to automatically linkify #<number> to the corresponding
    # issue in Zulip's server repository.
    request = {
        "pattern": "#(?P<id>[0-9]+)",
        "url_template": "https://github.com/zulip/zulip/issues/{id}",
    }
    result = client.call_endpoint("/realm/filters", method="POST", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/filters", "post", "200")
    return result["id"]


@openapi_test_function("/realm/filters/{filter_id}:patch")
def update_realm_filter(client: Client, filter_id: int) -> None:
    # {code_example|start}
    # Update a linkifier.
    request = {
        "pattern": "#(?P<id>[0-9]+)",
        "url_template": "https://github.com/zulip/zulip/issues/{id}",
    }
    result = client.call_endpoint(
        url=f"/realm/filters/{filter_id}", method="PATCH", request=request
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/filters/{filter_id}", "patch", "200")


@openapi_test_function("/realm/filters/{filter_id}:delete")
def remove_realm_filter(client: Client, filter_id: int) -> None:
    # {code_example|start}
    # Remove a linkifier.
    result = client.remove_realm_filter(filter_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/filters/{filter_id}", "delete", "200")


@openapi_test_function("/realm/playgrounds:post")
def add_realm_playground(client: Client) -> None:
    # {code_example|start}
    # Add a code playground for Python.
    request = {
        "name": "Python playground",
        "pygments_language": "Python",
        "url_template": "https://python.example.com?code={code}",
    }
    result = client.call_endpoint(url="/realm/playgrounds", method="POST", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/playgrounds", "post", "200")


@openapi_test_function("/realm/playgrounds/{playground_id}:delete")
def remove_realm_playground(client: Client) -> None:
    # {code_example|start}
    # Remove the code playground with ID 1.
    result = client.call_endpoint(url="/realm/playgrounds/1", method="DELETE")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/playgrounds/{playground_id}", "delete", "200")


@openapi_test_function("/export/realm:get")
def get_realm_exports(client: Client) -> None:
    # {code_example|start}
    # Get organization's public data exports.
    result = client.call_endpoint(url="/export/realm", method="GET")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/export/realm", "get", "200")


@openapi_test_function("/export/realm:post")
def export_realm(client: Client) -> None:
    # {code_example|start}
    # Create a public data export of the organization.
    result = client.call_endpoint(url="/export/realm", method="POST")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/export/realm", "post", "200")


@openapi_test_function("/export/realm/consents:get")
def get_realm_export_consents(client: Client) -> None:
    # {code_example|start}
    # Get the consents of users for their private data exports.
    result = client.call_endpoint(url="/export/realm/consents", method="GET")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/export/realm/consents", "get", "200")


@openapi_test_function("/users/me:get")
def get_profile(client: Client) -> None:
    # {code_example|start}
    # Get the profile of the user/bot that requests this endpoint,
    # which is `client` in this case.
    result = client.get_profile()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me", "get", "200")


@openapi_test_function("/users/me:delete")
def deactivate_own_user(client: Client, owner_client: Client) -> None:
    user_id = client.get_profile()["user_id"]
    # {code_example|start}
    # Deactivate the account of the current user/bot.
    result = client.call_endpoint(
        url="/users/me",
        method="DELETE",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me", "delete", "200")

    # Reactivate the account to avoid polluting other tests.
    owner_client.reactivate_user_by_id(user_id)


@openapi_test_function("/get_stream_id:get")
def get_stream_id(client: Client) -> int:
    name = "python-test"
    # {code_example|start}
    # Get the ID of a given channel name.
    result = client.get_stream_id(name)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/get_stream_id", "get", "200")
    return result["stream_id"]


@openapi_test_function("/streams/{stream_id}:delete")
def archive_stream(client: Client) -> None:
    client.add_subscriptions(
        streams=[
            {
                "name": "example to archive",
            },
        ],
    )
    stream_id = client.get_stream_id("example to archive")["stream_id"]
    # {code_example|start}
    # Archive a channel, given the channel's ID.
    result = client.delete_stream(stream_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/streams/{stream_id}", "delete", "200")


@openapi_test_function("/streams/{stream_id}/delete_topic:post")
def delete_topic(client: Client, stream_id: int, topic: str) -> None:
    # {code_example|start}
    # Delete a topic in a channel, given the channel's ID.
    request = {
        "topic_name": topic,
    }
    result = client.call_endpoint(
        url=f"/streams/{stream_id}/delete_topic", method="POST", request=request
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/streams/{stream_id}/delete_topic", "post", "200")


@openapi_test_function("/streams:get")
def get_streams(client: Client) -> None:
    # {code_example|start}
    # Get all channels that the user has access to.
    result = client.get_streams()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/streams", "get", "200")
    streams = [s for s in result["streams"] if s["name"] == "python-test"]
    assert streams[0]["description"] == "Channel for testing Python"

    # {code_example|start}
    # You may pass in one or more of the query parameters mentioned above
    # as keyword arguments, like so:
    result = client.get_streams(include_public=False)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/streams", "get", "200")
    assert len(result["streams"]) == 7


@openapi_test_function("/streams/{stream_id}:patch")
def update_stream(client: Client, stream_id: int) -> None:
    # {code_example|start}
    # Update settings for the channel with a given ID.
    request = {
        "stream_id": stream_id,
        "is_private": True,
    }
    result = client.update_stream(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/streams/{stream_id}", "patch", "200")


@openapi_test_function("/user_groups:get")
def get_user_groups(client: Client) -> int:
    # {code_example|start}
    # Get all user groups of the organization.
    result = client.get_user_groups()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/user_groups", "get", "200")
    [hamlet_user_group] = (u for u in result["user_groups"] if u["name"] == "hamletcharacters")
    assert hamlet_user_group["description"] == "Characters of Hamlet"
    [leadership_user_group] = (u for u in result["user_groups"] if u["name"] == "leadership")
    return leadership_user_group["id"]


@openapi_test_function("/streams/{stream_id}/members:get")
def get_subscribers(client: Client) -> None:
    user_ids = [11, 25]
    ensure_users(user_ids, ["iago", "newbie"])
    # {code_example|start}
    # Get the subscribers to a channel. Note that `client.get_subscribers`
    # takes a `stream` parameter with the channel's name and not the
    # channel's ID.
    result = client.get_subscribers(stream="python-test")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/streams/{stream_id}/members", "get", "200")
    assert result["subscribers"] == user_ids


def get_user_agent(client: Client) -> None:
    result = client.get_user_agent()
    assert result.startswith("ZulipPython/")


@openapi_test_function("/users/me/subscriptions:get")
def get_subscriptions(client: Client) -> None:
    # {code_example|start}
    # Get all channels that the user is subscribed to.
    result = client.get_subscriptions()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions", "get", "200")
    streams = [s for s in result["subscriptions"] if s["name"] == "python-test"]
    assert streams[0]["description"] == "Channel for testing Python"


@openapi_test_function("/users/me/subscriptions:delete")
def remove_subscriptions(client: Client) -> None:
    # {code_example|start}
    # Unsubscribe from channel "python-test".
    result = client.remove_subscriptions(
        ["python-test"],
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions", "delete", "200")

    # Confirm user is no longer subscribed to "python-test".
    subscriptions = client.get_subscriptions()["subscriptions"]
    streams = [s for s in subscriptions if s["name"] == "python-test"]
    assert len(streams) == 0

    # {code_example|start}
    # Unsubscribe another user from channel "python-test".
    result = client.remove_subscriptions(
        ["python-test"],
        principals=["newbie@zulip.com"],
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions", "delete", "200")


@openapi_test_function("/users/me/subscriptions/muted_topics:patch")
def toggle_mute_topic(client: Client) -> None:
    # Send a test message.
    message = {
        "type": "stream",
        "to": "Denmark",
        "topic": "boat party",
    }
    client.call_endpoint(
        url="messages",
        method="POST",
        request=message,
    )
    # {code_example|start}
    # Mute the topic "boat party" in the channel named "Denmark".
    request = {
        "stream": "Denmark",
        "topic": "boat party",
        "op": "add",
    }
    result = client.mute_topic(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions/muted_topics", "patch", "200")

    # {code_example|start}
    # Unmute the topic "boat party" in the channel named "Denmark".
    request = {
        "stream": "Denmark",
        "topic": "boat party",
        "op": "remove",
    }
    result = client.mute_topic(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions/muted_topics", "patch", "200")


@openapi_test_function("/user_topics:post")
def update_user_topic(client: Client) -> None:
    stream_id = client.get_stream_id("Denmark")["stream_id"]
    # {code_example|start}
    # Mute the topic "dinner" in a channel, given the channel's ID.
    request = {
        "stream_id": stream_id,
        "topic": "dinner",
        "visibility_policy": 1,
    }
    result = client.call_endpoint(
        url="user_topics",
        method="POST",
        request=request,
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/user_topics", "post", "200")

    # {code_example|start}
    # Remove mute from the topic "dinner" in a channel, given the channel's ID.
    request = {
        "stream_id": stream_id,
        "topic": "dinner",
        "visibility_policy": 0,
    }
    result = client.call_endpoint(
        url="user_topics",
        method="POST",
        request=request,
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/user_topics", "post", "200")


@openapi_test_function("/users/me/muted_users/{muted_user_id}:post")
def add_user_mute(client: Client) -> None:
    muted_user_id = 10
    ensure_users([muted_user_id], ["hamlet"])
    # {code_example|start}
    # Mute a user, given the user's ID.
    result = client.call_endpoint(url=f"/users/me/muted_users/{muted_user_id}", method="POST")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/muted_users/{muted_user_id}", "post", "200")


@openapi_test_function("/users/me/muted_users/{muted_user_id}:delete")
def remove_user_mute(client: Client) -> None:
    muted_user_id = 10
    ensure_users([muted_user_id], ["hamlet"])
    # {code_example|start}
    # Unmute a user, given the user's ID.
    result = client.call_endpoint(url=f"/users/me/muted_users/{muted_user_id}", method="DELETE")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(
        result, "/users/me/muted_users/{muted_user_id}", "delete", "200"
    )


@openapi_test_function("/mark_all_as_read:post")
def mark_all_as_read(client: Client) -> None:
    # {code_example|start}
    # Mark all of the user's unread messages as read.
    result = client.mark_all_as_read()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/mark_all_as_read", "post", "200")


@openapi_test_function("/mark_stream_as_read:post")
def mark_stream_as_read(client: Client) -> None:
    stream_id = client.get_subscriptions()["subscriptions"][0]["stream_id"]
    # {code_example|start}
    # Mark the unread messages in a channel as read, given the channel's ID.
    result = client.mark_stream_as_read(stream_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/mark_stream_as_read", "post", "200")


@openapi_test_function("/mark_topic_as_read:post")
def mark_topic_as_read(client: Client) -> None:
    stream_id = client.get_subscriptions()["subscriptions"][0]["stream_id"]
    topic_name = client.get_stream_topics(stream_id)["topics"][0]["name"]
    # {code_example|start}
    # Mark unread messages in a given topic/channel as read.
    result = client.mark_topic_as_read(stream_id, topic_name)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/mark_stream_as_read", "post", "200")


@openapi_test_function("/users/me/subscriptions/properties:post")
def update_subscription_settings(client: Client) -> None:
    subscriptions = client.get_subscriptions()["subscriptions"]
    assert len(subscriptions) >= 2
    stream_a_id = subscriptions[0]["stream_id"]
    stream_b_id = subscriptions[1]["stream_id"]
    # {code_example|start}
    # Update the user's subscription of the channel with ID `stream_a_id`
    # so that it's pinned to the top of the user's channel list, and in
    # the channel with ID `stream_b_id` so that it has the hex color "f00".
    request = [
        {
            "stream_id": stream_a_id,
            "property": "pin_to_top",
            "value": True,
        },
        {
            "stream_id": stream_b_id,
            "property": "color",
            "value": "#f00f00",
        },
    ]
    result = client.update_subscription_settings(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/subscriptions/properties", "POST", "200")


@openapi_test_function("/messages/render:post")
def render_message(client: Client) -> None:
    # {code_example|start}
    # Render a message.
    request = {
        "content": "**foo**",
    }
    result = client.render_message(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/render", "post", "200")


@openapi_test_function("/messages:get")
def get_messages(client: Client) -> None:
    # {code_example|start}
    # Get the 100 last messages sent by "iago@zulip.com" to
    # the channel named "Verona".
    request: dict[str, Any] = {
        "anchor": "newest",
        "num_before": 100,
        "num_after": 0,
        "narrow": [
            {"operator": "sender", "operand": "iago@zulip.com"},
            {"operator": "channel", "operand": "Verona"},
        ],
    }
    result = client.get_messages(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages", "get", "200")
    assert len(result["messages"]) <= request["num_before"]


@openapi_test_function("/messages/matches_narrow:get")
def check_messages_match_narrow(client: Client) -> None:
    message = {"type": "stream", "to": "Verona", "topic": "test_topic", "content": "http://foo.com"}
    msg_ids = []
    response = client.send_message(message)
    msg_ids.append(response["id"])
    message["content"] = "no link here"
    response = client.send_message(message)
    msg_ids.append(response["id"])
    # {code_example|start}
    # Check which messages, given the message IDs, match a narrow.
    request = {
        "msg_ids": msg_ids,
        "narrow": [{"operator": "has", "operand": "link"}],
    }
    result = client.call_endpoint(url="messages/matches_narrow", method="GET", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/matches_narrow", "get", "200")


@openapi_test_function("/messages/{message_id}:get")
def get_raw_message(client: Client, message_id: int) -> None:
    # {code_example|start}
    # Get the raw content of a message given the message's ID.
    result = client.get_raw_message(message_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/{message_id}", "get", "200")


@openapi_test_function("/attachments:get")
def get_attachments(client: Client) -> int:
    # {code_example|start}
    # Get your attachments.
    result = client.get_attachments()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/attachments", "get", "200")
    return result["attachments"][0]["id"]


@openapi_test_function("/attachments/{attachment_id}:delete")
def remove_attachment(client: Client, attachment_id: int) -> None:
    # {code_example|start}
    # Delete the attachment given the attachment's ID.
    url = "attachments/" + str(attachment_id)
    result = client.call_endpoint(
        url=url,
        method="DELETE",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/attachments/{attachment_id}", "delete", "200")


@openapi_test_function("/navigation_views:get")
def get_navigation_views(client: Client) -> None:
    # {code_example|start}
    # Get all navigation views for the user
    result = client.call_endpoint(
        url="navigation_views",
        method="GET",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/navigation_views", "get", "200")


@openapi_test_function("/navigation_views:post")
def add_navigation_views(client: Client) -> None:
    # {code_example|start}
    # Add a navigation view
    request = {
        "fragment": "narrow/is/alerted",
        "is_pinned": True,
        "name": "Alert Word",
    }
    result = client.call_endpoint(
        url="navigation_views",
        method="POST",
        request=request,
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/navigation_views", "post", "200")


@openapi_test_function("/navigation_views/{fragment}:patch")
def update_navigation_views(client: Client) -> None:
    # Fetch navigation views for updating
    result = client.call_endpoint(url="navigation_views", method="GET")
    fragment = result["navigation_views"][0]["fragment"]
    # {code_example|start}
    # Update a navigation view's location
    request = {
        "is_pinned": True,
    }
    result = client.call_endpoint(
        url=f"navigation_views/{fragment}",
        method="PATCH",
        request=request,
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/navigation_views/{fragment}", "patch", "200")


@openapi_test_function("/navigation_views/{fragment}:delete")
def remove_navigation_views(client: Client) -> None:
    # Fetch navigation views for deletion
    result = client.call_endpoint(url="navigation_views", method="GET")
    fragment = result["navigation_views"][0]["fragment"]
    # {code_example|start}
    # Remove a navigation views
    result = client.call_endpoint(
        url=f"navigation_views/{fragment}",
        method="DELETE",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/navigation_views/{fragment}", "delete", "200")


@openapi_test_function("/saved_snippets:post")
def create_saved_snippet(client: Client) -> None:
    # {code_example|start}
    # Create a saved snippet.
    request = {"title": "Welcome message", "content": "**Welcome** to the organization."}
    result = client.call_endpoint(
        request=request,
        url="/saved_snippets",
        method="POST",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/saved_snippets", "post", "200")


@openapi_test_function("/saved_snippets:get")
def get_saved_snippets(client: Client) -> int:
    # {code_example|start}
    # Get all the saved snippets.
    result = client.call_endpoint(
        url="/saved_snippets",
        method="GET",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/saved_snippets", "get", "200")

    return result["saved_snippets"][0]["id"]


@openapi_test_function("/saved_snippets/{saved_snippet_id}:patch")
def edit_saved_snippet(client: Client, saved_snippet_id: int) -> None:
    # {code_example|start}
    # Edit a saved snippet.
    request = {"title": "New welcome message", "content": "Welcome to Zulip!"}
    result = client.call_endpoint(
        request=request,
        url=f"/saved_snippets/{saved_snippet_id}",
        method="PATCH",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/saved_snippets/{saved_snippet_id}", "patch", "200")


@openapi_test_function("/saved_snippets/{saved_snippet_id}:delete")
def delete_saved_snippet(client: Client, saved_snippet_id: int) -> None:
    # {code_example|start}
    # Delete a saved snippet.
    result = client.call_endpoint(
        url=f"/saved_snippets/{saved_snippet_id}",
        method="DELETE",
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/saved_snippets/{saved_snippet_id}", "delete", "200")


@openapi_test_function("/messages:post")
def send_message(client: Client) -> tuple[int, str]:
    request: dict[str, Any] = {}
    # {code_example|start}
    # Send a channel message.
    request = {
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts.",
    }
    result = client.send_message(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages", "post", "200")

    # Confirm the message was actually sent.
    message_id = result["id"]
    validate_message(client, message_id, request["content"])

    user_id = 10
    ensure_users([user_id], ["hamlet"])
    # {code_example|start}
    # Send a direct message.
    request = {
        "type": "private",
        "to": [user_id],
        "content": "With mirth and laughter let old wrinkles come.",
    }
    result = client.send_message(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages", "post", "200")

    # Confirm the message was actually sent.
    message_id = result["id"]
    validate_message(client, message_id, request["content"])
    return message_id, request["content"]


@openapi_test_function("/messages/{message_id}/reactions:post")
def add_reaction(client: Client, message_id: int) -> None:
    request: dict[str, Any] = {}
    # {code_example|start}
    # Add an emoji reaction.
    request = {
        "message_id": message_id,
        "emoji_name": "octopus",
    }
    result = client.add_reaction(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/{message_id}/reactions", "post", "200")


@openapi_test_function("/messages/{message_id}/reactions:delete")
def remove_reaction(client: Client, message_id: int) -> None:
    request: dict[str, Any] = {}
    # {code_example|start}
    # Remove an emoji reaction.
    request = {
        "message_id": message_id,
        "emoji_name": "octopus",
    }
    result = client.remove_reaction(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/{message_id}/reactions", "delete", "200")


@openapi_test_function("/messages/{message_id}/read_receipts:get")
def get_read_receipts(client: Client, message_id: int) -> None:
    # {code_example|start}
    # Get read receipts for a message, given the message's ID.
    result = client.call_endpoint(f"/messages/{message_id}/read_receipts", method="GET")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/{message_id}/read_receipts", "get", "200")


def test_nonexistent_stream_error(client: Client) -> None:
    request = {
        "type": "stream",
        "to": "nonexistent-channel",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts.",
    }
    result = client.send_message(request)
    assert_error_response(result, code="STREAM_DOES_NOT_EXIST")
    validate_against_openapi_schema(result, "/messages", "post", "400")


def test_private_message_invalid_recipient(client: Client) -> None:
    request = {
        "type": "private",
        "to": "eeshan@zulip.com",
        "content": "With mirth and laughter let old wrinkles come.",
    }
    result = client.send_message(request)
    assert_error_response(result)
    validate_against_openapi_schema(result, "/messages", "post", "400")


@openapi_test_function("/messages/{message_id}:patch")
def update_message(client: Client, message_id: int, prev_content: str) -> None:
    # We elect not to pass prev_content_sha256, because at present, it
    # is likely to be experienced as clutter for almost all end users
    # of this API.
    #
    # {code_example|start}
    # Edit a message. Make sure that `message_id` is set to the ID of the
    # message you wish to update.
    request = {
        "message_id": message_id,
        "content": "New content",
    }
    result = client.update_message(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/{message_id}", "patch", "200")

    # Confirm the message was actually updated.
    validate_message(client, message_id, request["content"])


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
    assert_error_response(result)
    validate_against_openapi_schema(result, "/messages/{message_id}", "patch", "400")


@openapi_test_function("/messages/{message_id}:delete")
def delete_message(client: Client, message_id: int) -> None:
    # {code_example|start}
    # Delete a message, given the message's ID.
    result = client.delete_message(message_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/{message_id}", "delete", "200")


def test_delete_message_edit_permission_error(client: Client, nonadmin_client: Client) -> None:
    request = {
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts.",
    }
    result = client.send_message(request)
    result = nonadmin_client.delete_message(result["id"])
    assert_error_response(result)
    validate_against_openapi_schema(result, "/messages/{message_id}", "delete", "400")


@openapi_test_function("/messages/{message_id}/history:get")
def get_message_history(client: Client, message_id: int) -> None:
    # {code_example|start}
    # Get the edit history for a message, given the message's ID.
    result = client.get_message_history(message_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/{message_id}/history", "get", "200")


@openapi_test_function("/realm/emoji:get")
def get_realm_emoji(client: Client) -> None:
    # {code_example|start}
    result = client.get_realm_emoji()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/emoji", "GET", "200")


@openapi_test_function("/messages/flags:post")
def update_message_flags(client: Client) -> None:
    # Send a few test messages.
    request: dict[str, Any] = {
        "type": "stream",
        "to": "Denmark",
        "topic": "Castle",
        "content": "I come not, friends, to steal away your hearts.",
    }
    message_ids = [client.send_message(request)["id"] for i in range(3)]
    # {code_example|start}
    # Add the "read" flag to messages, given the messages' IDs.
    request = {
        "messages": message_ids,
        "op": "add",
        "flag": "read",
    }
    result = client.update_message_flags(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/flags", "post", "200")

    # {code_example|start}
    # Remove the "starred" flag from messages, given the messages' IDs.
    request = {
        "messages": message_ids,
        "op": "remove",
        "flag": "starred",
    }
    result = client.update_message_flags(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/flags", "post", "200")


@openapi_test_function("/messages/{message_id}/report:post")
def report_message(client: Client) -> None:
    set_moderation_request_channel(client)
    ensure_users([10], ["hamlet"])
    hamlets_messages = get_users_messages(client, 10)
    message_id = hamlets_messages[0]["id"]
    # {code_example|start}
    request = {
        "report_type": "harassment",
        "description": "Boromir is bullying Frodo.",
    }
    # Report a message, given the message's ID.
    result = client.call_endpoint(f"/messages/{message_id}/report", method="POST", request=request)
    # {code_example|end}
    assert_success_response(result)

    validate_against_openapi_schema(result, "/messages/{message_id}/report", "post", "200")


def register_queue_all_events(client: Client) -> str:
    # Register the queue and get all events.
    # Mainly for verifying schema of /register.
    result = client.register()
    assert_success_response(result)
    validate_against_openapi_schema(result, "/register", "post", "200")
    return result["queue_id"]


@openapi_test_function("/register:post")
def register_queue(client: Client) -> str:
    # {code_example|start}
    # Register the queue.
    result = client.register(
        event_types=["message", "realm_emoji"],
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/register", "post", "200")
    return result["queue_id"]


@openapi_test_function("/events:delete")
def deregister_queue(client: Client, queue_id: str) -> None:
    # {code_example|start}
    # Delete a queue, where `queue_id` is the ID of the queue
    # to be removed.
    result = client.deregister(queue_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/events", "delete", "200")

    # Test "BAD_EVENT_QUEUE_ID" error.
    result = client.deregister(queue_id)
    assert_error_response(result, code="BAD_EVENT_QUEUE_ID")
    validate_against_openapi_schema(result, "/events", "delete", "400")


@openapi_test_function("/events:get")
def get_queue(client: Client, queue_id: str) -> None:
    # {code_example|start}
    # If you already have a queue registered, and thus have a `queue_id`
    # on hand, you may use `client.get_events()` and pass in the below
    # parameters, like so:
    result = client.get_events(queue_id=queue_id, last_event_id=-1)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/events", "get", "200")


@openapi_test_function("/server_settings:get")
def get_server_settings(client: Client) -> None:
    # {code_example|start}
    # Fetch the settings for this server.
    result = client.get_server_settings()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/server_settings", "get", "200")


@openapi_test_function("/settings:patch")
def update_settings(client: Client) -> None:
    # {code_example|start}
    # Enable push notifications even when online and change emoji set.
    request = {
        "enable_offline_push_notifications": True,
        "enable_online_push_notifications": True,
        "emojiset": "google",
    }
    result = client.call_endpoint("/settings", method="PATCH", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/settings", "patch", "200")


@openapi_test_function("/user_uploads:post")
def upload_file(client: Client) -> None:
    path_to_file = os.path.join(ZULIP_DIR, "zerver", "tests", "images", "img.jpg")
    # {code_example|start}
    # Upload a file.
    with open(path_to_file, "rb") as fp:
        result = client.upload_file(fp)
    # Share the file by including it in a message.
    client.send_message(
        {
            "type": "stream",
            "to": "Denmark",
            "topic": "Castle",
            "content": "Check out [this picture]({}) of my castle!".format(result["url"]),
        }
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/user_uploads", "post", "200")


@openapi_test_function("/users/me/{stream_id}/topics:get")
def get_stream_topics(client: Client, stream_id: int) -> None:
    # {code_example|start}
    result = client.get_stream_topics(stream_id)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/{stream_id}/topics", "get", "200")


@openapi_test_function("/users/me/apns_device_token:post")
def add_apns_token(client: Client) -> None:
    # {code_example|start}
    request = {"token": "apple-tokenbb", "appid": "org.zulip.Zulip"}
    result = client.call_endpoint(url="/users/me/apns_device_token", method="POST", request=request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/apns_device_token", "post", "200")


@openapi_test_function("/users/me/apns_device_token:delete")
def remove_apns_token(client: Client) -> None:
    # {code_example|start}
    request = {
        "token": "apple-tokenbb",
    }
    result = client.call_endpoint(
        url="/users/me/apns_device_token", method="DELETE", request=request
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/apns_device_token", "delete", "200")


@openapi_test_function("/users/me/android_gcm_reg_id:post")
def add_fcm_token(client: Client) -> None:
    # {code_example|start}
    request = {"token": "android-token"}
    result = client.call_endpoint(
        url="/users/me/android_gcm_reg_id", method="POST", request=request
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/android_gcm_reg_id", "post", "200")


@openapi_test_function("/users/me/android_gcm_reg_id:delete")
def remove_fcm_token(client: Client) -> None:
    # {code_example|start}
    request = {
        "token": "android-token",
    }
    result = client.call_endpoint(
        url="/users/me/android_gcm_reg_id", method="DELETE", request=request
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/android_gcm_reg_id", "delete", "200")


@openapi_test_function("/typing:post")
def set_typing_status(client: Client) -> None:
    ensure_users([10, 11], ["hamlet", "iago"])
    user_a_id = 10
    user_b_id = 11
    # {code_example|start}
    # The user has started typing in the group direct message
    # with two users, "user_a" and "user_b".
    request = {
        "op": "start",
        "to": [user_a_id, user_b_id],
    }
    result = client.set_typing_status(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/typing", "post", "200")

    # {code_example|start}
    # The user has finished typing in the group direct message
    # with "user_a" and "user_b".
    request = {
        "op": "stop",
        "to": [user_a_id, user_b_id],
    }
    result = client.set_typing_status(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/typing", "post", "200")

    stream_id = client.get_stream_id("Denmark")["stream_id"]
    topic = "typing status"
    # {code_example|start}
    # The user has started typing in a topic/channel.
    request = {
        "type": "stream",
        "op": "start",
        "stream_id": stream_id,
        "topic": topic,
    }
    result = client.set_typing_status(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/typing", "post", "200")

    # {code_example|start}
    # The user has finished typing in a topic/channel.
    request = {
        "type": "stream",
        "op": "stop",
        "stream_id": stream_id,
        "topic": topic,
    }
    result = client.set_typing_status(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/typing", "post", "200")


@openapi_test_function("/messages/{message_id}/typing:post")
def set_message_edit_typing_status(client: Client, message_id: int) -> None:
    # {code_example|start}
    # The user has started typing while editing a message.
    request = {
        "op": "start",
    }
    result = client.call_endpoint(
        f"/messages/{message_id}/typing",
        method="POST",
        request=request,
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, f"/messages/{message_id}/typing", "post", "200")

    # {code_example|start}
    # The user has stopped typing while editing a message.
    request = {
        "op": "stop",
    }
    result = client.call_endpoint(
        f"/messages/{message_id}/typing",
        method="POST",
        request=request,
    )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/messages/{message_id}/typing", "post", "200")


@openapi_test_function("/realm/emoji/{emoji_name}:post")
def upload_custom_emoji(client: Client) -> None:
    emoji_path = os.path.join(ZULIP_DIR, "zerver", "tests", "images", "img.jpg")
    # {code_example|start}
    # Upload a custom emoji; assume `emoji_path` is the path to your image.
    with open(emoji_path, "rb") as fp:
        emoji_name = "my_custom_emoji"
        result = client.call_endpoint(
            f"realm/emoji/{emoji_name}",
            method="POST",
            files=[fp],
        )
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/emoji/{emoji_name}", "post", "200")


@openapi_test_function("/realm/emoji/{emoji_name}:delete")
def delete_custom_emoji(client: Client) -> None:
    emoji_name = "my_custom_emoji"
    # {code_example|start}
    # Delete a custom emoji.
    result = client.call_endpoint(f"realm/emoji/{emoji_name}", method="DELETE")
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/realm/emoji/{emoji_name}", "delete", "200")


@openapi_test_function("/users/me/alert_words:get")
def get_alert_words(client: Client) -> None:
    # {code_example|start}
    # Get all of the user's configured alert words.
    result = client.get_alert_words()
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/alert_words", "get", "200")


@openapi_test_function("/users/me/alert_words:post")
def add_alert_words(client: Client) -> None:
    words = ["foo", "bar"]
    # {code_example|start}
    # Add words (or phrases) to the user's set of configured alert words.
    result = client.add_alert_words(words)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/alert_words", "post", "200")


@openapi_test_function("/users/me/alert_words:delete")
def remove_alert_words(client: Client) -> None:
    words = client.get_alert_words()["alert_words"]
    assert len(words) > 0
    # {code_example|start}
    # Remove words (or phrases) from the user's set of configured alert words.
    result = client.remove_alert_words(words)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/users/me/alert_words", "delete", "200")


@openapi_test_function("/user_groups/create:post")
def create_user_group(client: Client) -> None:
    user_ids = [6, 7, 8, 10]
    ensure_users(user_ids, ["aaron", "zoe", "cordelia", "hamlet"])
    # {code_example|start}
    request = {
        "name": "leadership",
        "description": "The leadership team.",
        "members": user_ids,
    }
    result = client.create_user_group(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/user_groups/create", "post", "200")


@openapi_test_function("/user_groups/{user_group_id}:patch")
def update_user_group(client: Client, user_group_id: int) -> None:
    # {code_example|start}
    request = {
        "group_id": user_group_id,
        "name": "leadership",
        "description": "The leadership team.",
    }
    result = client.update_user_group(request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/user_groups/{user_group_id}", "patch", "200")


@openapi_test_function("/user_groups/{user_group_id}/members:post")
def update_user_group_members(client: Client, user_group_id: int) -> None:
    ensure_users([8, 10, 11], ["cordelia", "hamlet", "iago"])
    user_ids_to_add = [11]
    user_ids_to_remove = [8, 10]
    # {code_example|start}
    request = {
        "delete": user_ids_to_remove,
        "add": user_ids_to_add,
    }
    result = client.update_user_group_members(user_group_id, request)
    # {code_example|end}
    assert_success_response(result)
    validate_against_openapi_schema(result, "/user_groups/{group_id}/members", "post", "200")


def test_invalid_api_key(client_with_invalid_key: Client) -> None:
    result = client_with_invalid_key.get_subscriptions()
    assert_error_response(result, code="UNAUTHORIZED")
    validate_against_openapi_schema(result, "/rest-error-handling", "post", "400")


def test_missing_request_argument(client: Client) -> None:
    result = client.render_message({})
    assert_error_response(result, code="REQUEST_VARIABLE_MISSING")
    validate_against_openapi_schema(result, "/rest-error-handling", "post", "400")


def test_user_account_deactivated(client: Client) -> None:
    request = {
        "content": "**foo**",
    }
    result = client.render_message(request)
    validate_against_openapi_schema(result, "/rest-error-handling", "post", "403")


def test_realm_deactivated(client: Client) -> None:
    request = {
        "content": "**foo**",
    }
    result = client.render_message(request)
    validate_against_openapi_schema(result, "/rest-error-handling", "post", "403")


def test_invalid_stream_error(client: Client) -> None:
    result = client.get_stream_id("nonexistent")
    assert_error_response(result)
    validate_against_openapi_schema(result, "/get_stream_id", "get", "400")


# SETUP METHODS FOLLOW


def test_messages(client: Client, nonadmin_client: Client) -> None:
    render_message(client)
    message_id, content = send_message(client)
    set_message_edit_typing_status(client, message_id)
    add_reaction(client, message_id)
    remove_reaction(client, message_id)
    update_message(client, message_id, content)
    get_raw_message(client, message_id)
    get_messages(client)
    check_messages_match_narrow(client)
    get_message_history(client, message_id)
    get_read_receipts(client, message_id)
    delete_message(client, message_id)
    report_message(client)
    mark_all_as_read(client)
    mark_stream_as_read(client)
    mark_topic_as_read(client)
    update_message_flags(client)

    test_nonexistent_stream_error(client)
    test_private_message_invalid_recipient(client)
    test_update_message_edit_permission_error(client, nonadmin_client)
    test_delete_message_edit_permission_error(client, nonadmin_client)


def test_users(client: Client, owner_client: Client) -> None:
    create_user(client)
    get_members(client)
    get_single_user(client)
    deactivate_user(client)
    reactivate_user(client)
    update_user(client)
    update_status(client)
    get_user_status(client)
    get_user_by_email(client)
    get_subscription_status(client)
    get_profile(client)
    update_settings(client)
    upload_file(client)
    attachment_id = get_attachments(client)
    remove_attachment(client, attachment_id)
    set_typing_status(client)
    update_presence(client)
    get_user_presence(client)
    get_presence(client)
    create_user_group(client)
    user_group_id = get_user_groups(client)
    update_user_group(client, user_group_id)
    update_user_group_members(client, user_group_id)
    get_alert_words(client)
    add_alert_words(client)
    remove_alert_words(client)
    deactivate_own_user(client, owner_client)
    add_user_mute(client)
    remove_user_mute(client)
    get_alert_words(client)
    add_alert_words(client)
    add_navigation_views(client)
    get_navigation_views(client)
    update_navigation_views(client)
    remove_navigation_views(client)
    create_saved_snippet(client)
    # Calling this again to pass the curl examples tests as the
    # `delete-saved-snippet` endpoint is called before `edit-saved-snippet`
    # causing "Saved snippet does not exist." error.
    create_saved_snippet(client)
    saved_snippet_id = get_saved_snippets(client)
    edit_saved_snippet(client, saved_snippet_id)
    delete_saved_snippet(client, saved_snippet_id)
    remove_alert_words(client)
    add_apns_token(client)
    remove_apns_token(client)
    add_fcm_token(client)
    remove_fcm_token(client)


def test_streams(client: Client, nonadmin_client: Client) -> None:
    add_subscriptions(client)
    test_add_subscriptions_already_subscribed(client)
    get_subscriptions(client)
    stream_id = get_stream_id(client)
    update_stream(client, stream_id)
    get_streams(client)
    get_subscribers(client)
    remove_subscriptions(client)
    toggle_mute_topic(client)
    update_user_topic(client)
    update_subscription_settings(client)
    get_stream_topics(client, 1)
    delete_topic(client, 1, "test")
    archive_stream(client)
    add_default_stream(client)
    remove_default_stream(client)

    test_authorization_errors_fatal(client, nonadmin_client)


def test_queues(client: Client) -> None:
    # Note that the example for api/get-events is not tested here.
    #
    # Since, methods such as client.get_events() or client.call_on_each_message
    # are blocking calls and since the event queue backend is already
    # thoroughly tested in zerver/tests/test_event_queue.py, it is not worth
    # the effort to come up with asynchronous logic for testing those here.
    #
    # We do validate endpoint example responses in zerver/tests/test_openapi.py,
    # as well as the example events returned by api/get-events.
    queue_id = register_queue(client)
    get_queue(client, queue_id)
    deregister_queue(client, queue_id)
    register_queue_all_events(client)


def test_server_organizations(client: Client) -> None:
    get_realm_linkifiers(client)
    filter_id = add_realm_filter(client)
    update_realm_filter(client, filter_id)
    add_realm_playground(client)
    get_server_settings(client)
    reorder_realm_linkifiers(client)
    remove_realm_filter(client, filter_id)
    remove_realm_playground(client)
    get_realm_emoji(client)
    upload_custom_emoji(client)
    delete_custom_emoji(client)
    get_realm_profile_fields(client)
    reorder_realm_profile_fields(client)
    create_realm_profile_field(client)
    export_realm(client)
    get_realm_exports(client)
    get_realm_export_consents(client)


def test_errors(client: Client) -> None:
    test_missing_request_argument(client)
    test_invalid_stream_error(client)


def test_invitations(client: Client) -> None:
    send_invitations(client)
    revoke_email_invitation(client)
    create_reusable_invitation_link(client)
    revoke_reusable_invitation_link(client)
    get_invitations(client)
    resend_email_invitation(client)


def test_the_api(client: Client, nonadmin_client: Client, owner_client: Client) -> None:
    get_user_agent(client)
    test_users(client, owner_client)
    test_streams(client, nonadmin_client)
    test_messages(client, nonadmin_client)
    test_queues(client)
    test_server_organizations(client)
    test_errors(client)
    test_invitations(client)

    sys.stdout.flush()
    if REGISTERED_TEST_FUNCTIONS != CALLED_TEST_FUNCTIONS:
        print("Error!  Some @openapi_test_function tests were never called:")
        print("  ", REGISTERED_TEST_FUNCTIONS - CALLED_TEST_FUNCTIONS)
        sys.exit(1)
