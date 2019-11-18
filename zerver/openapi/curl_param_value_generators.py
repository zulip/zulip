from typing import Dict, Any, Callable, Set, List, Optional, Tuple

from functools import wraps

from django.utils.timezone import now as timezone_now

from zerver.models import Client, UserPresence, UserGroup, get_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.events import do_events_register
from zerver.lib.actions import update_user_presence, do_add_realm_filter

GENERATOR_FUNCTIONS = dict()  # type: Dict[str, Callable[..., Dict[Any, Any]]]
REGISTERED_GENERATOR_FUNCTIONS = set()  # type: Set[str]
CALLED_GENERATOR_FUNCTIONS = set()  # type: Set[str]

helpers = ZulipTestCase()

def openapi_param_value_generator(endpoints: List[str]) -> Callable[[Callable[..., Any]],
                                                                    Callable[..., Any]]:
    """This decorator is used to register openapi param value genarator functions
    with endpoints. Example usage:

    @openapi_param_value_generator(["/messages/render:post"])
    def ...
    """
    def wrapper(generator_func: Callable[..., Dict[Any, Any]]) -> Callable[..., Dict[Any, Any]]:
        @wraps(generator_func)
        def _record_calls_wrapper(*args: Any, **kwargs: Any) -> Dict[Any, Any]:
            CALLED_GENERATOR_FUNCTIONS.add(generator_func.__name__)
            return generator_func(*args, **kwargs)

        REGISTERED_GENERATOR_FUNCTIONS.add(generator_func.__name__)
        for endpoint in endpoints:
            GENERATOR_FUNCTIONS[endpoint] = _record_calls_wrapper

        return _record_calls_wrapper
    return wrapper

def patch_openapi_example_values(entry: str, params: List[Dict[str, Any]],
                                 request_body: Optional[Dict[str, Any]]=None) \
        -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if entry not in GENERATOR_FUNCTIONS:
        return params, request_body
    func = GENERATOR_FUNCTIONS[entry]
    realm_example_values = func()  # type: Dict[str, Any]

    for param in params:
        param_name = param["name"]
        if param_name in realm_example_values:
            param["example"] = realm_example_values[param_name]

    if request_body is not None:
        properties = request_body["content"]["multipart/form-data"]["schema"]["properties"]
        for key, property in properties.items():
            if key in realm_example_values:
                property["example"] = realm_example_values[key]
    return params, request_body

@openapi_param_value_generator(["/messages/{message_id}:get", "/messages/{message_id}/history:get",
                                "/messages/{message_id}:patch", "/messages/{message_id}:delete"])
def iago_message_id() -> Dict[str, int]:
    return {
        "message_id": helpers.send_stream_message(helpers.example_email("iago"), "Denmark")
    }

@openapi_param_value_generator(["/messages/flags:post"])
def update_flags_message_ids() -> Dict[str, List[int]]:
    stream_name = "Venice"
    helpers.subscribe(helpers.example_user("iago"), stream_name)

    messages = []
    for _ in range(3):
        messages.append(helpers.send_stream_message(helpers.example_email("iago"), stream_name))
    return {
        "messages": messages,
    }

@openapi_param_value_generator(["/mark_stream_as_read:post", "/users/me/{stream_id}/topics:get"])
def get_venice_stream_id() -> Dict[str, int]:
    return {
        "stream_id": helpers.get_stream_id("Venice"),
    }

@openapi_param_value_generator(["/streams/{stream_id}:patch"])
def update_stream() -> Dict[str, Any]:
    stream = helpers.subscribe(helpers.example_user("iago"), "temp_stream 1")
    return {
        "stream_id": stream.id,
    }

@openapi_param_value_generator(["/streams/{stream_id}:delete"])
def create_temp_stream_and_get_id() -> Dict[str, int]:
    stream = helpers.subscribe(helpers.example_user("iago"), "temp_stream 2")
    return {
        "stream_id": stream.id,
    }

@openapi_param_value_generator(["/mark_topic_as_read:post"])
def get_denmark_stream_id_and_topic() -> Dict[str, Any]:
    stream_name = "Denmark"
    topic_name = "Tivoli Gardens"

    helpers.subscribe(helpers.example_user("iago"), stream_name)
    helpers.send_stream_message(helpers.example_email("hamlet"), stream_name, topic_name=topic_name)

    return {
        "stream_id": helpers.get_stream_id(stream_name),
        "topic_name": topic_name,
    }

@openapi_param_value_generator(["/users/me/subscriptions/properties:post"])
def update_subscription_data() -> Dict[str, List[Dict[str, Any]]]:
    profile = helpers.example_user("iago")
    helpers.subscribe(profile, "Verona")
    helpers.subscribe(profile, "social")
    return {
        "subscription_data": [
            {"stream_id": helpers.get_stream_id("Verona"), "property": "pin_to_top", "value": True},
            {"stream_id": helpers.get_stream_id("social"), "property": "color", "value": "#f00f00"}
        ]
    }

@openapi_param_value_generator(["/users/me/subscriptions:delete"])
def delete_subscription_data() -> Dict[str, List[Dict[None, None]]]:
    iago = helpers.example_user("iago")
    zoe = helpers.example_user("ZOE")
    helpers.subscribe(iago, "Verona")
    helpers.subscribe(iago, "social")
    helpers.subscribe(zoe, "Verona")
    helpers.subscribe(zoe, "social")
    return {}

@openapi_param_value_generator(["/events:get"])
def get_events() -> Dict[str, Any]:
    profile = helpers.example_user("iago")
    helpers.subscribe(profile, "Verona")
    client = Client.objects.create(name="curl-test-client-1")
    response = do_events_register(profile, client, event_types=['message', 'realm_emoji'])
    helpers.send_stream_message(helpers.example_email("hamlet"), "Verona")
    return {
        "queue_id": response["queue_id"],
        "last_event_id": response["last_event_id"],
    }

@openapi_param_value_generator(["/events:delete"])
def delete_event_queue() -> Dict[str, Any]:
    profile = helpers.example_user("iago")
    client = Client.objects.create(name="curl-test-client-2")
    response = do_events_register(profile, client, event_types=['message'])
    return {
        "queue_id": response["queue_id"],
        "last_event_id": response["last_event_id"],
    }

@openapi_param_value_generator(["/users/{email}/presence:get"])
def get_user_presence() -> Dict[None, None]:
    iago = helpers.example_user("iago")
    client = Client.objects.create(name="curl-test-client-3")
    update_user_presence(iago, client, timezone_now(), UserPresence.ACTIVE, False)
    return {}

@openapi_param_value_generator(["/users:post"])
def create_user() -> Dict[str, str]:
    return {
        "email": helpers.nonreg_email("test")
    }

@openapi_param_value_generator(["/user_groups/create:post"])
def create_user_group_data() -> Dict[str, Any]:
    return {
        "members": [helpers.example_user("hamlet").id, helpers.example_user("othello").id]
    }

@openapi_param_value_generator(["/user_groups/{group_id}:patch", "/user_groups/{group_id}:delete"])
def get_temp_user_group_id() -> Dict[str, str]:
    user_group, _ = UserGroup.objects.get_or_create(name="temp", realm=get_realm("zulip"))
    return {
        "group_id": user_group.id,
    }

@openapi_param_value_generator(["/realm/filters/{filter_id}:delete"])
def remove_realm_filters() -> Dict[str, Any]:
    filter_id = do_add_realm_filter(get_realm("zulip"), "#(?P<id>[0-9]{2,8})", "https://github.com/zulip/zulip/pull/%(id)s")
    return {
        "filter_id": filter_id
    }

@openapi_param_value_generator(["/realm/emoji/{emoji_name}:post", "/user_uploads:post"])
def upload_custom_emoji() -> Dict[str, Any]:
    return {
        "filename": "zerver/tests/images/animated_img.gif",
    }
