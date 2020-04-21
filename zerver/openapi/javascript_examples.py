
from typing import Dict, Any, Callable, Set, List

import json
import subprocess

from functools import wraps

TEST_FUNCTIONS = dict()  # type: Dict[str, Callable[..., None]]
REGISTERED_TEST_FUNCTIONS = set()  # type: Set[str]
CALLED_TEST_FUNCTIONS = set()  # type: Set[str]

def openapi_test_function(endpoint: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """This decorator is used to register an openapi test function with
    its endpoint. Example usage:

    @openapi_test_function("/messages/render:post")
    def ...
    """
    def wrapper(test_func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(test_func)
        def _record_calls_wrapper(*args: Any, **kwargs: Any) -> Any:
            CALLED_TEST_FUNCTIONS.add(test_func.__name__)
            return test_func(*args, **kwargs)

        REGISTERED_TEST_FUNCTIONS.add(test_func.__name__)
        TEST_FUNCTIONS[endpoint] = _record_calls_wrapper

        return _record_calls_wrapper
    return wrapper

def run_js_code(js_code: str) -> List[Dict[str, Any]]:
    """Here, we run the JavaScript examples and return
    a list of all the responses from the code example
    as json."""

    responses_str = subprocess.check_output(
        args=['node'],
        input=js_code.replace(
            '.then(console.log)', '.then(JSON.stringify).then(console.log)'),
        universal_newlines=True)
    json_response_list = [json.loads(response) for response in responses_str.splitlines()]

    return json_response_list
