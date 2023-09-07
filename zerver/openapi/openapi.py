# Zulip's OpenAPI-based API documentation system is documented at
#   https://zulip.readthedocs.io/en/latest/documentation/api.html
#
# This file contains helper functions to interact with the OpenAPI
# definitions and validate that Zulip's implementation matches what is
# described in our documentation.

import json
import os
import re
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple, Union, cast

import openapi_core
import orjson
from openapi_core import Spec
from openapi_core.protocols import Response
from openapi_core.testing import MockRequest, MockResponse
from openapi_core.validation.exceptions import ValidationError as OpenAPIValidationError

OPENAPI_SPEC_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../openapi/zulip.yaml")
)

# A list of endpoint-methods such that the endpoint
# has documentation but not with this particular method.
EXCLUDE_UNDOCUMENTED_ENDPOINTS = {
    ("/users", "patch"),
}
# Consists of endpoints with some documentation remaining.
# These are skipped but return true as the validator cannot exclude objects
EXCLUDE_DOCUMENTED_ENDPOINTS: Set[Tuple[str, str]] = set()


# Most of our code expects allOf to be preprocessed away because that is what
# yamole did.  Its algorithm for doing so is not standards compliant, but we
# replicate it here.
def naively_merge(a: Dict[str, object], b: Dict[str, object]) -> Dict[str, object]:
    ret: Dict[str, object] = a.copy()
    for key, b_value in b.items():
        if key == "example" or key not in ret:
            ret[key] = b_value
            continue
        a_value = ret[key]
        if isinstance(b_value, list):
            assert isinstance(a_value, list)
            ret[key] = a_value + b_value
        elif isinstance(b_value, dict):
            assert isinstance(a_value, dict)
            ret[key] = naively_merge(a_value, b_value)
    return ret


def naively_merge_allOf(obj: object) -> object:
    if isinstance(obj, dict):
        return naively_merge_allOf_dict(obj)
    elif isinstance(obj, list):
        return list(map(naively_merge_allOf, obj))
    else:
        return obj


def naively_merge_allOf_dict(obj: Dict[str, object]) -> Dict[str, object]:
    if "allOf" in obj:
        ret = obj.copy()
        subschemas = ret.pop("allOf")
        ret = naively_merge_allOf_dict(ret)
        assert isinstance(subschemas, list)
        for subschema in subschemas:
            assert isinstance(subschema, dict)
            ret = naively_merge(ret, naively_merge_allOf_dict(subschema))
        return ret
    return {key: naively_merge_allOf(value) for key, value in obj.items()}


class OpenAPISpec:
    def __init__(self, openapi_path: str) -> None:
        self.openapi_path = openapi_path
        self.mtime: Optional[float] = None
        self._openapi: Dict[str, Any] = {}
        self._endpoints_dict: Dict[str, str] = {}
        self._spec: Optional[Spec] = None

    def check_reload(self) -> None:
        # Because importing yaml takes significant time, and we only
        # use python-yaml for our API docs, importing it lazily here
        # is a significant optimization to `manage.py` startup.
        #
        # There is a bit of a race here...we may have two processes
        # accessing this module level object and both trying to
        # populate self.data at the same time.  Hopefully this will
        # only cause some extra processing at startup and not data
        # corruption.

        import yaml
        from jsonref import JsonRef

        with open(self.openapi_path) as f:
            mtime = os.fstat(f.fileno()).st_mtime
            # Using == rather than >= to cover the corner case of users placing an
            # earlier version than the current one
            if self.mtime == mtime:
                return

            openapi = yaml.load(f, Loader=yaml.CSafeLoader)

        spec = Spec.from_dict(openapi)
        self._spec = spec
        self._openapi = naively_merge_allOf_dict(JsonRef.replace_refs(openapi))
        self.create_endpoints_dict()
        self.mtime = mtime

    def create_endpoints_dict(self) -> None:
        # Algorithm description:
        # We have 2 types of endpoints
        # 1.with path arguments 2. without path arguments
        # In validate_against_openapi_schema we directly check
        # if we have a without path endpoint, since it does not
        # require regex. Hence they are not part of the regex dict
        # and now we are left with only:
        # endpoint with path arguments.
        # Now for this case, the regex has been created carefully,
        # numeric arguments are matched with [0-9] only and
        # emails are matched with their regex. This is why there are zero
        # collisions. Hence if this regex matches
        # an incorrect endpoint then there is some backend problem.
        # For example if we have users/{name}/presence then it will
        # conflict with users/me/presence even in the backend.
        # Care should be taken though that if we have special strings
        # such as email they must be substituted with proper regex.

        email_regex = r"([a-zA-Z0-9_\-\.]+)@([a-zA-Z0-9_\-\.]+)\.([a-zA-Z]{2,5})"
        self._endpoints_dict = {}
        for endpoint in self._openapi["paths"]:
            if "{" not in endpoint:
                continue
            path_regex = "^" + endpoint + "$"
            # Numeric arguments have id at their end
            # so find such arguments and replace them with numeric
            # regex
            path_regex = re.sub(r"{[^}]*id}", r"[0-9]*", path_regex)
            # Email arguments end with email
            path_regex = re.sub(r"{[^}]*email}", email_regex, path_regex)
            # All other types of arguments are supposed to be
            # all-encompassing string.
            path_regex = re.sub(r"{[^}]*}", r"[^\/]*", path_regex)
            path_regex = path_regex.replace(r"/", r"\/")
            self._endpoints_dict[path_regex] = endpoint

    def openapi(self) -> Dict[str, Any]:
        """Reload the OpenAPI file if it has been modified after the last time
        it was read, and then return the parsed data.
        """
        self.check_reload()
        assert len(self._openapi) > 0
        return self._openapi

    def endpoints_dict(self) -> Dict[str, str]:
        """Reload the OpenAPI file if it has been modified after the last time
        it was read, and then return the parsed data.
        """
        self.check_reload()
        assert len(self._endpoints_dict) > 0
        return self._endpoints_dict

    def spec(self) -> Spec:
        """Reload the OpenAPI file if it has been modified after the last time
        it was read, and then return the openapi_core validator object. Similar
        to preceding functions. Used for proper access to OpenAPI objects.
        """
        self.check_reload()
        assert self._spec is not None
        return self._spec


class SchemaError(Exception):
    pass


openapi_spec = OpenAPISpec(OPENAPI_SPEC_PATH)


def get_schema(endpoint: str, method: str, status_code: str) -> Dict[str, Any]:
    if len(status_code) == 3 and (
        "oneOf"
        in openapi_spec.openapi()["paths"][endpoint][method.lower()]["responses"][status_code][
            "content"
        ]["application/json"]["schema"]
    ):
        # Currently at places where multiple schemas are defined they only
        # differ in example so either can be used.
        status_code += "_0"
    if len(status_code) == 3:
        schema = openapi_spec.openapi()["paths"][endpoint][method.lower()]["responses"][
            status_code
        ]["content"]["application/json"]["schema"]
        return schema
    else:
        subschema_index = int(status_code[4])
        status_code = status_code[0:3]
        schema = openapi_spec.openapi()["paths"][endpoint][method.lower()]["responses"][
            status_code
        ]["content"]["application/json"]["schema"]["oneOf"][subschema_index]
        return schema


def get_openapi_fixture(endpoint: str, method: str, status_code: str = "200") -> Dict[str, Any]:
    """Fetch a fixture from the full spec object."""
    return get_schema(endpoint, method, status_code)["example"]


def get_openapi_fixture_description(endpoint: str, method: str, status_code: str = "200") -> str:
    """Fetch a fixture from the full spec object."""
    return get_schema(endpoint, method, status_code)["description"]


def get_curl_include_exclude(endpoint: str, method: str) -> List[Dict[str, Any]]:
    """Fetch all the kinds of parameters required for curl examples."""
    if (
        "x-curl-examples-parameters"
        not in openapi_spec.openapi()["paths"][endpoint][method.lower()]
    ):
        return [{"type": "exclude", "parameters": {"enum": [""]}}]
    return openapi_spec.openapi()["paths"][endpoint][method.lower()]["x-curl-examples-parameters"][
        "oneOf"
    ]


def check_requires_administrator(endpoint: str, method: str) -> bool:
    """Fetch if the endpoint requires admin config."""
    return openapi_spec.openapi()["paths"][endpoint][method.lower()].get(
        "x-requires-administrator", False
    )


def check_additional_imports(endpoint: str, method: str) -> Optional[List[str]]:
    """Fetch the additional imports required for an endpoint."""
    return openapi_spec.openapi()["paths"][endpoint][method.lower()].get(
        "x-python-examples-extra-imports", None
    )


def get_responses_description(endpoint: str, method: str) -> str:
    """Fetch responses description of an endpoint."""
    return openapi_spec.openapi()["paths"][endpoint][method.lower()].get(
        "x-response-description", ""
    )


def get_parameters_description(endpoint: str, method: str) -> str:
    """Fetch parameters description of an endpoint."""
    return openapi_spec.openapi()["paths"][endpoint][method.lower()].get(
        "x-parameter-description", ""
    )


def generate_openapi_fixture(endpoint: str, method: str) -> List[str]:
    """Generate fixture to be rendered"""
    fixture = []
    for status_code in sorted(
        openapi_spec.openapi()["paths"][endpoint][method.lower()]["responses"]
    ):
        if (
            "oneOf"
            in openapi_spec.openapi()["paths"][endpoint][method.lower()]["responses"][status_code][
                "content"
            ]["application/json"]["schema"]
        ):
            subschema_count = len(
                openapi_spec.openapi()["paths"][endpoint][method.lower()]["responses"][status_code][
                    "content"
                ]["application/json"]["schema"]["oneOf"]
            )
        else:
            subschema_count = 1
        for subschema_index in range(subschema_count):
            if subschema_count != 1:
                subschema_status_code = status_code + "_" + str(subschema_index)
            else:
                subschema_status_code = status_code
            fixture_dict = get_openapi_fixture(endpoint, method, subschema_status_code)
            fixture_description = get_openapi_fixture_description(
                endpoint, method, subschema_status_code
            ).strip()
            fixture_json = json.dumps(
                fixture_dict, indent=4, sort_keys=True, separators=(",", ": ")
            )

            fixture.extend(fixture_description.splitlines())
            fixture.append("``` json")
            fixture.extend(fixture_json.splitlines())
            fixture.append("```")
    return fixture


def get_openapi_description(endpoint: str, method: str) -> str:
    """Fetch a description from the full spec object."""
    return openapi_spec.openapi()["paths"][endpoint][method.lower()]["description"]


def get_openapi_summary(endpoint: str, method: str) -> str:
    """Fetch a summary from the full spec object."""
    return openapi_spec.openapi()["paths"][endpoint][method.lower()]["summary"]


def get_endpoint_from_operationid(operationid: str) -> Tuple[str, str]:
    for endpoint in openapi_spec.openapi()["paths"]:
        for method in openapi_spec.openapi()["paths"][endpoint]:
            operationId = openapi_spec.openapi()["paths"][endpoint][method].get("operationId")
            if operationId == operationid:
                return (endpoint, method)
    raise AssertionError("No such page exists in OpenAPI data.")


def get_openapi_paths() -> Set[str]:
    return set(openapi_spec.openapi()["paths"].keys())


def get_openapi_parameters(
    endpoint: str, method: str, include_url_parameters: bool = True
) -> List[Dict[str, Any]]:
    operation = openapi_spec.openapi()["paths"][endpoint][method.lower()]
    # We do a `.get()` for this last bit to distinguish documented
    # endpoints with no parameters (empty list) from undocumented
    # endpoints (KeyError exception).
    parameters = operation.get("parameters", [])
    # Also, we skip parameters defined in the URL.
    if not include_url_parameters:
        parameters = [parameter for parameter in parameters if parameter["in"] != "path"]
    return parameters


def get_openapi_return_values(endpoint: str, method: str) -> Dict[str, Any]:
    operation = openapi_spec.openapi()["paths"][endpoint][method.lower()]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    # We do not currently have documented endpoints that have multiple schemas
    # ("oneOf", "anyOf", "allOf") for success ("200") responses. If this changes,
    # then the assertion below will need to be removed, and this function updated
    # so that endpoint responses will be rendered as expected.
    assert "properties" in schema
    return schema["properties"]


def find_openapi_endpoint(path: str) -> Optional[str]:
    for path_regex, endpoint in openapi_spec.endpoints_dict().items():
        matches = re.match(path_regex, path)
        if matches:
            return endpoint
    return None


def fix_events(content: Dict[str, Any]) -> None:
    """Remove undocumented events from events array. This is a makeshift
    function so that further documentation of `/events` can happen with
    only zulip.yaml changes and minimal other changes. It should be removed
    as soon as `/events` documentation is complete.
    """
    # 'user' is deprecated so remove its occurrences from the events array
    for event in content["events"]:
        event.pop("user", None)


def validate_against_openapi_schema(
    content: Dict[str, Any],
    path: str,
    method: str,
    status_code: str,
    display_brief_error: bool = False,
) -> bool:
    """Compare a "content" dict with the defined schema for a specific method
    in an endpoint. Return true if validated and false if skipped.
    """

    # This first set of checks are primarily training wheels that we
    # hope to eliminate over time as we improve our API documentation.

    # No 500 responses have been documented, so skip them
    if status_code.startswith("5"):
        return False
    if path not in openapi_spec.openapi()["paths"]:
        endpoint = find_openapi_endpoint(path)
        # If it doesn't match it hasn't been documented yet.
        if endpoint is None:
            return False
    else:
        endpoint = path
    # Excluded endpoint/methods
    if (endpoint, method) in EXCLUDE_UNDOCUMENTED_ENDPOINTS:
        return False
    # Return true for endpoints with only response documentation remaining
    if (endpoint, method) in EXCLUDE_DOCUMENTED_ENDPOINTS:  # nocoverage
        return True
    # Check if the response matches its code
    if status_code.startswith("2") and (
        content.get("result", "success").lower() != "success"
    ):  # nocoverage
        raise SchemaError("Response is not 200 but is validating against 200 schema")
    # Code is not declared but appears in various 400 responses. If
    # common, it can be added to 400 response schema
    if status_code.startswith("4"):
        # This return statement should ideally be not here. But since
        # we have not defined 400 responses for various paths this has
        # been added as all 400 have the same schema.  When all 400
        # response have been defined this should be removed.
        return True

    if endpoint == "/events" and method == "get":
        # This a temporary function for checking only documented events
        # as all events haven't been documented yet.
        # TODO: Remove this after all events have been documented.
        fix_events(content)

    mock_request = MockRequest("http://localhost:9991/", method, "/api/v1" + path)
    mock_response = MockResponse(
        # TODO: Use original response content instead of re-serializing it.
        orjson.dumps(content).decode(),
        status_code=int(status_code),
    )
    try:
        openapi_core.validate_response(
            mock_request, cast(Response, mock_response), spec=openapi_spec.spec()
        )
    except OpenAPIValidationError as error:
        message = f"Response validation error at {method} /api/v1{path} ({status_code}):"
        message += f"\n\n{type(error).__name__}: {error}"
        message += (
            "\n\nFor help debugging these errors see: "
            "https://zulip.readthedocs.io/en/latest/documentation/api.html#debugging-schema-validation-errors"
        )
        raise SchemaError(message) from None

    return True


def validate_schema(schema: Dict[str, Any]) -> None:
    """Check if opaque objects are present in the OpenAPI spec; this is an
    important part of our policy for ensuring every detail of Zulip's
    API responses is correct.

    This is done by checking for the presence of the
    `additionalProperties` attribute for all objects (dictionaries).
    """
    if "oneOf" in schema:
        for subschema in schema["oneOf"]:
            validate_schema(subschema)
    elif schema["type"] == "array":
        validate_schema(schema["items"])
    elif schema["type"] == "object":
        if "additionalProperties" not in schema:
            raise SchemaError(
                "additionalProperties needs to be defined for objects to make sure they have no"
                " additional properties left to be documented."
            )
        for property_schema in schema.get("properties", {}).values():
            validate_schema(property_schema)
        if schema["additionalProperties"]:
            validate_schema(schema["additionalProperties"])


def likely_deprecated_parameter(parameter_description: str) -> bool:
    if "**Changes**: Deprecated" in parameter_description:
        return True

    return "**Deprecated**" in parameter_description


def check_deprecated_consistency(argument: Mapping[str, Any], description: str) -> None:
    # Test to make sure deprecated parameters are marked so.
    if likely_deprecated_parameter(description):
        assert argument["deprecated"]
    if "deprecated" in argument:
        assert likely_deprecated_parameter(description)


# Skip those JSON endpoints whose query parameters are different from
# their `/api/v1` counterpart.  This is a legacy code issue that we
# plan to fix by changing the implementation.
SKIP_JSON = {
    ("/fetch_api_key", "post"),
}


def validate_request(
    url: str,
    method: str,
    data: Union[str, bytes, Mapping[str, Any]],
    http_headers: Dict[str, str],
    json_url: bool,
    status_code: str,
    intentionally_undocumented: bool = False,
) -> None:
    # Some JSON endpoints have different parameters compared to
    # their `/api/v1` counterparts.
    if json_url and (url, method) in SKIP_JSON:
        return

    # TODO: Add support for file upload endpoints that lack the /json/
    # or /api/v1/ prefix.
    if url == "/user_uploads" or url.startswith("/realm/emoji/"):
        return

    # Requests that do not validate against the OpenAPI spec must either:
    # * Have returned a 400 (bad request) error
    # * Have returned a 200 (success) with this request marked as intentionally
    # undocumented behavior.
    if status_code.startswith("4"):
        return
    if status_code.startswith("2") and intentionally_undocumented:
        return

    # Now using the openapi_core APIs, validate the request schema
    # against the OpenAPI documentation.
    assert isinstance(data, dict)
    mock_request = MockRequest(
        "http://localhost:9991/", method, "/api/v1" + url, headers=http_headers, args=data
    )
    try:
        openapi_core.validate_request(mock_request, spec=openapi_spec.spec())
    except OpenAPIValidationError as error:
        # Show a block error message explaining the options for fixing it.
        msg = f"""

Error!  The OpenAPI schema for {method} {url} is not consistent
with the parameters passed in this HTTP request.  Consider:

* Updating the OpenAPI schema defined in zerver/openapi/zulip.yaml
* Adjusting the test to pass valid parameters.  If the test
  fails due to intentionally_undocumented features, you need to pass
  `intentionally_undocumented=True` to self.client_{method.lower()} or
  self.api_{method.lower()} to document your intent.

See https://zulip.readthedocs.io/en/latest/documentation/api.html for help.

The error logged by the OpenAPI validator is below:
{error}
"""
        raise SchemaError(msg)
