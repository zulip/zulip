from typing import Dict, Any, Callable, Set, List

from functools import wraps

from zerver.lib.test_classes import ZulipTestCase

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

def patch_openapi_params(openapi_entry: str, openapi_params: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if openapi_entry not in GENERATOR_FUNCTIONS:
        return openapi_params
    func = GENERATOR_FUNCTIONS[openapi_entry]
    realm_param_values = func()  # type: Dict[str, Any]
    for param in openapi_params:
        param_name = param["name"]
        if param_name in realm_param_values:
            param["example"] = realm_param_values[param_name]
    return openapi_params

@openapi_param_value_generator(["/messages/{message_id}:get"])
def iago_message_id() -> Dict[str, int]:
    return {
        "message_id": helpers.send_stream_message(helpers.example_email("iago"), "Denmark")
    }

@openapi_param_value_generator(["/messages/{message_id}:patch"])
def default_bot_message_id() -> Dict[str, int]:
    return {
        "message_id": helpers.send_stream_message("default-bot@zulip.com", "Denmark")
    }
