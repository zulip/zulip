# Zulip's OpenAPI-based API documentation system is documented at
#   https://zulip.readthedocs.io/en/latest/documentation/api.html
#
# This file contains helper functions for generating cURL examples
# based on Zulip's OpenAPI definitions, as well as test setup and
# fetching of appropriate parameter values to use when running the
# cURL examples as part of the tools/test-api test suite.
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from django.utils.timezone import now as timezone_now

from zerver.actions.create_user import do_create_user
from zerver.actions.presence import update_user_presence
from zerver.actions.reactions import do_add_reaction
from zerver.actions.realm_linkifiers import do_add_linkifier
from zerver.actions.realm_playgrounds import check_add_realm_playground
from zerver.lib.events import do_events_register
from zerver.lib.initial_password import initial_password
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.upload import upload_message_attachment
from zerver.lib.users import get_api_key
from zerver.models import Client, Message, NamedUserGroup, UserPresence
from zerver.models.realms import get_realm
from zerver.models.users import get_user
from zerver.openapi.openapi import Parameter

GENERATOR_FUNCTIONS: Dict[str, Callable[[], Dict[str, object]]] = {}
REGISTERED_GENERATOR_FUNCTIONS: Set[str] = set()
CALLED_GENERATOR_FUNCTIONS: Set[str] = set()
# This is a List rather than just a string in order to make it easier
# to write to it from another module.
AUTHENTICATION_LINE: List[str] = [""]

helpers = ZulipTestCase()


def openapi_param_value_generator(
    endpoints: List[str],
) -> Callable[[Callable[[], Dict[str, object]]], Callable[[], Dict[str, object]]]:
    """This decorator is used to register OpenAPI param value generator functions
    with endpoints. Example usage:

    @openapi_param_value_generator(["/messages/render:post"])
    def ...
    """

    def wrapper(generator_func: Callable[[], Dict[str, object]]) -> Callable[[], Dict[str, object]]:
        @wraps(generator_func)
        def _record_calls_wrapper() -> Dict[str, object]:
            CALLED_GENERATOR_FUNCTIONS.add(generator_func.__name__)
            return generator_func()

        REGISTERED_GENERATOR_FUNCTIONS.add(generator_func.__name__)
        for endpoint in endpoints:
            GENERATOR_FUNCTIONS[endpoint] = _record_calls_wrapper

        return _record_calls_wrapper

    return wrapper


def assert_all_helper_functions_called() -> None:
    """Throws an exception if any registered helpers were not called by tests"""
    if REGISTERED_GENERATOR_FUNCTIONS == CALLED_GENERATOR_FUNCTIONS:
        return

    uncalled_functions = str(REGISTERED_GENERATOR_FUNCTIONS - CALLED_GENERATOR_FUNCTIONS)

    raise Exception(f"Registered curl API generators were not called: {uncalled_functions}")


def patch_openapi_example_values(
    entry: str,
    parameters: List[Parameter],
    request_body: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Parameter], Optional[Dict[str, object]]]:
    if entry not in GENERATOR_FUNCTIONS:
        return parameters, request_body
    func = GENERATOR_FUNCTIONS[entry]
    realm_example_values: Dict[str, object] = func()

    for parameter in parameters:
        if parameter.name in realm_example_values:
            parameter.example = realm_example_values[parameter.name]

    if request_body is not None and "multipart/form-data" in (content := request_body["content"]):
        properties = content["multipart/form-data"]["schema"]["properties"]
        for key, property in properties.items():
            if key in realm_example_values:
                property["example"] = realm_example_values[key]
    return parameters, request_body


@openapi_param_value_generator(["/fetch_api_key:post"])
def fetch_api_key() -> Dict[str, object]:
    email = helpers.example_email("iago")
    password = initial_password(email)

    return {
        "username": email,
        "password": password,
    }


@openapi_param_value_generator(
    [
        "/messages/{message_id}:get",
        "/messages/{message_id}/history:get",
        "/messages/{message_id}:patch",
        "/messages/{message_id}:delete",
    ]
)
def iago_message_id() -> Dict[str, object]:
    iago = helpers.example_user("iago")
    helpers.subscribe(iago, "Denmark")
    return {
        "message_id": helpers.send_stream_message(iago, "Denmark"),
    }


@openapi_param_value_generator(["/messages/{message_id}/reactions:delete"])
def add_emoji_to_message() -> Dict[str, object]:
    user_profile = helpers.example_user("iago")

    # The message ID here is hardcoded based on the corresponding value
    # for the example message IDs we use in zulip.yaml.
    message_id = 47
    emoji_name = "octopus"
    emoji_code = "1f419"
    reaction_type = "unicode_emoji"

    message = Message.objects.select_related(*Message.DEFAULT_SELECT_RELATED).get(id=message_id)
    do_add_reaction(user_profile, message, emoji_name, emoji_code, reaction_type)

    return {}


@openapi_param_value_generator(["/messages/flags:post"])
def update_flags_message_ids() -> Dict[str, object]:
    stream_name = "Venice"
    helpers.subscribe(helpers.example_user("iago"), stream_name)

    messages = [
        helpers.send_stream_message(helpers.example_user("iago"), stream_name) for _ in range(3)
    ]
    return {
        "messages": messages,
    }


@openapi_param_value_generator(["/mark_stream_as_read:post", "/users/me/{stream_id}/topics:get"])
def get_venice_stream_id() -> Dict[str, object]:
    return {
        "stream_id": helpers.get_stream_id("Venice"),
    }


@openapi_param_value_generator(["/streams/{stream_id}:patch"])
def update_stream() -> Dict[str, object]:
    stream = helpers.subscribe(helpers.example_user("iago"), "temp_stream 1")
    return {
        "stream_id": stream.id,
    }


@openapi_param_value_generator(["/streams/{stream_id}:delete"])
def create_temp_stream_and_get_id() -> Dict[str, object]:
    stream = helpers.subscribe(helpers.example_user("iago"), "temp_stream 2")
    return {
        "stream_id": stream.id,
    }


@openapi_param_value_generator(["/mark_topic_as_read:post"])
def get_denmark_stream_id_and_topic() -> Dict[str, object]:
    stream_name = "Denmark"
    topic_name = "Tivoli Gardens"

    helpers.subscribe(helpers.example_user("iago"), stream_name)
    helpers.send_stream_message(helpers.example_user("hamlet"), stream_name, topic_name=topic_name)

    return {
        "stream_id": helpers.get_stream_id(stream_name),
        "topic_name": topic_name,
    }


@openapi_param_value_generator(["/users/me/subscriptions/properties:post"])
def update_subscription_data() -> Dict[str, object]:
    profile = helpers.example_user("iago")
    helpers.subscribe(profile, "Verona")
    helpers.subscribe(profile, "social")
    return {
        "subscription_data": [
            {"stream_id": helpers.get_stream_id("Verona"), "property": "pin_to_top", "value": True},
            {"stream_id": helpers.get_stream_id("social"), "property": "color", "value": "#f00f00"},
        ],
    }


@openapi_param_value_generator(["/users/me/subscriptions:delete"])
def delete_subscription_data() -> Dict[str, object]:
    iago = helpers.example_user("iago")
    zoe = helpers.example_user("ZOE")
    helpers.subscribe(iago, "Verona")
    helpers.subscribe(iago, "social")
    helpers.subscribe(zoe, "Verona")
    helpers.subscribe(zoe, "social")
    return {}


@openapi_param_value_generator(["/events:get"])
def get_events() -> Dict[str, object]:
    profile = helpers.example_user("iago")
    helpers.subscribe(profile, "Verona")
    client = Client.objects.create(name="curl-test-client-1")
    response = do_events_register(
        profile, profile.realm, client, event_types=["message", "realm_emoji"]
    )
    helpers.send_stream_message(helpers.example_user("hamlet"), "Verona")
    return {
        "queue_id": response["queue_id"],
        "last_event_id": response["last_event_id"],
    }


@openapi_param_value_generator(["/events:delete"])
def delete_event_queue() -> Dict[str, object]:
    profile = helpers.example_user("iago")
    client = Client.objects.create(name="curl-test-client-2")
    response = do_events_register(profile, profile.realm, client, event_types=["message"])
    return {
        "queue_id": response["queue_id"],
        "last_event_id": response["last_event_id"],
    }


@openapi_param_value_generator(["/users/{user_id_or_email}/presence:get"])
def get_user_presence() -> Dict[str, object]:
    iago = helpers.example_user("iago")
    client = Client.objects.create(name="curl-test-client-3")
    update_user_presence(iago, client, timezone_now(), UserPresence.LEGACY_STATUS_ACTIVE_INT, False)
    return {}


@openapi_param_value_generator(["/users:post"])
def create_user() -> Dict[str, object]:
    return {
        "email": helpers.nonreg_email("test"),
    }


@openapi_param_value_generator(["/user_groups/create:post"])
def create_user_group_data() -> Dict[str, object]:
    return {
        "members": [helpers.example_user("hamlet").id, helpers.example_user("othello").id],
    }


@openapi_param_value_generator(
    ["/user_groups/{user_group_id}:patch", "/user_groups/{user_group_id}:delete"]
)
def get_temp_user_group_id() -> Dict[str, object]:
    user_group, _ = NamedUserGroup.objects.get_or_create(
        name="temp",
        realm=get_realm("zulip"),
        can_mention_group_id=11,
        realm_for_sharding=get_realm("zulip"),
    )
    return {
        "user_group_id": user_group.id,
    }


@openapi_param_value_generator(["/realm/filters/{filter_id}:delete"])
def remove_realm_filters() -> Dict[str, object]:
    filter_id = do_add_linkifier(
        get_realm("zulip"),
        "#(?P<id>[0-9]{2,8})",
        "https://github.com/zulip/zulip/pull/{id}",
        acting_user=None,
    )
    return {
        "filter_id": filter_id,
    }


@openapi_param_value_generator(["/realm/emoji/{emoji_name}:post", "/user_uploads:post"])
def upload_custom_emoji() -> Dict[str, object]:
    return {
        "filename": "zerver/tests/images/animated_img.gif",
    }


@openapi_param_value_generator(["/realm/playgrounds:post"])
def add_realm_playground() -> Dict[str, object]:
    return {
        "name": "Python2 playground",
        "pygments_language": "Python2",
        "url_template": "https://python2.example.com?code={code}",
    }


@openapi_param_value_generator(["/realm/playgrounds/{playground_id}:delete"])
def remove_realm_playground() -> Dict[str, object]:
    playground_id = check_add_realm_playground(
        get_realm("zulip"),
        acting_user=None,
        name="Python playground",
        pygments_language="Python",
        url_template="https://python.example.com?code={code}",
    )
    return {
        "playground_id": playground_id,
    }


@openapi_param_value_generator(["/users/{user_id}:delete"])
def deactivate_user() -> Dict[str, object]:
    user_profile = do_create_user(
        email="testuser@zulip.com",
        password=None,
        full_name="test_user",
        realm=get_realm("zulip"),
        acting_user=None,
    )
    return {"user_id": user_profile.id}


@openapi_param_value_generator(["/users/me:delete"])
def deactivate_own_user() -> Dict[str, object]:
    test_user_email = "delete-test@zulip.com"
    deactivate_test_user = do_create_user(
        test_user_email,
        "secret",
        get_realm("zulip"),
        "Mr. Delete",
        role=200,
        acting_user=None,
    )
    realm = get_realm("zulip")
    test_user = get_user(test_user_email, realm)
    test_user_api_key = get_api_key(test_user)
    # change authentication line to allow test_client to delete itself.
    AUTHENTICATION_LINE[0] = f"{deactivate_test_user.email}:{test_user_api_key}"
    return {}


@openapi_param_value_generator(["/attachments/{attachment_id}:delete"])
def remove_attachment() -> Dict[str, object]:
    user_profile = helpers.example_user("iago")
    url = upload_message_attachment(
        "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile
    )
    attachment_id = url.replace("/user_uploads/", "").split("/")[0]

    return {"attachment_id": attachment_id}
