# Zulip's OpenAPI-based API documentation system is documented at
#   https://zulip.readthedocs.io/en/latest/documentation/api.html
#
# This file contains helper functions to interact with the OpenAPI
# definitions and validate that Zulip's implementation matches what is
# described in our documentation.

import json
import os
import re
from collections.abc import Mapping
from typing import Any, Literal

import orjson
from openapi_core import OpenAPI
from openapi_core.protocols import Request, Response
from openapi_core.testing import MockRequest, MockResponse
from openapi_core.validation.exceptions import ValidationError as OpenAPIValidationError
from pydantic import BaseModel

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
EXCLUDE_DOCUMENTED_ENDPOINTS: set[tuple[str, str]] = set()


# Most of our code expects allOf to be preprocessed away because that is what
# yamole did.  Its algorithm for doing so is not standards compliant, but we
# replicate it here.
def naively_merge(a: dict[str, object], b: dict[str, object]) -> dict[str, object]:
    ret: dict[str, object] = a.copy()
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


def naively_merge_allOf_dict(obj: dict[str, object]) -> dict[str, object]:
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
        self.mtime: float | None = None
        self._openapi: dict[str, Any] = {}
        self._endpoints_dict: dict[str, str] = {}
        self._spec: OpenAPI | None = None

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

        spec = OpenAPI.from_dict(openapi)
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

    def openapi(self) -> dict[str, Any]:
        """Reload the OpenAPI file if it has been modified after the last time
        it was read, and then return the parsed data.
        """
        self.check_reload()
        assert len(self._openapi) > 0
        return self._openapi

    def endpoints_dict(self) -> dict[str, str]:
        """Reload the OpenAPI file if it has been modified after the last time
        it was read, and then return the parsed data.
        """
        self.check_reload()
        assert len(self._endpoints_dict) > 0
        return self._endpoints_dict

    def spec(self) -> OpenAPI:
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


def get_schema(endpoint: str, method: str, status_code: str) -> dict[str, Any]:
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


def get_openapi_fixture(
    endpoint: str, method: str, status_code: str = "200"
) -> list[dict[str, Any]]:
    """Fetch a fixture from the full spec object."""
    if "example" not in get_schema(endpoint, method, status_code):
        return openapi_spec.openapi()["paths"][endpoint][method.lower()]["responses"][status_code][
            "content"
        ]["application/json"]["examples"].values()
    return [
        {
            "description": get_schema(endpoint, method, status_code)["description"],
            "value": get_schema(endpoint, method, status_code)["example"],
        }
    ]


def get_curl_include_exclude(endpoint: str, method: str) -> list[dict[str, Any]]:
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


def check_additional_imports(endpoint: str, method: str) -> list[str] | None:
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


def generate_openapi_fixture(endpoint: str, method: str) -> list[str]:
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
            for example in fixture_dict:
                fixture_json = json.dumps(
                    example["value"], indent=4, sort_keys=True, separators=(",", ": ")
                )
                if "description" in example:
                    fixture.extend(example["description"].strip().splitlines())
                fixture.append("``` json")
                fixture.extend(fixture_json.splitlines())
                fixture.append("```")
    return fixture


def get_openapi_description(endpoint: str, method: str) -> str:
    """Fetch a description from the full spec object."""
    endpoint_documentation = openapi_spec.openapi()["paths"][endpoint][method.lower()]
    endpoint_description = endpoint_documentation["description"]
    check_deprecated_consistency(
        endpoint_documentation.get("deprecated", False), endpoint_description
    )
    return endpoint_description


def get_openapi_summary(endpoint: str, method: str) -> str:
    """Fetch a summary from the full spec object."""
    return openapi_spec.openapi()["paths"][endpoint][method.lower()]["summary"]


def get_endpoint_from_operationid(operationid: str) -> tuple[str, str]:
    for endpoint in openapi_spec.openapi()["paths"]:
        for method in openapi_spec.openapi()["paths"][endpoint]:
            operationId = openapi_spec.openapi()["paths"][endpoint][method].get("operationId")
            if operationId == operationid:
                return (endpoint, method)
    raise AssertionError("No such page exists in OpenAPI data.")


def get_openapi_paths() -> set[str]:
    return set(openapi_spec.openapi()["paths"].keys())


NO_EXAMPLE = object()


class Parameter(BaseModel):
    kind: Literal["query", "path", "formData"]
    name: str
    description: str
    json_encoded: bool
    value_schema: dict[str, Any]
    example: object
    required: bool
    deprecated: bool


def get_openapi_parameters(
    endpoint: str, method: str, include_url_parameters: bool = True
) -> list[Parameter]:
    operation = openapi_spec.openapi()["paths"][endpoint][method.lower()]
    parameters = []

    # We do a `.get()` for this last bit to distinguish documented
    # endpoints with no parameters (empty list) from undocumented
    # endpoints (KeyError exception).
    for parameter in operation.get("parameters", []):
        # Also, we skip parameters defined in the URL.
        if not include_url_parameters and parameter["in"] == "path":
            continue

        json_encoded = "content" in parameter
        if json_encoded:
            schema = parameter["content"]["application/json"]["schema"]
        else:
            schema = parameter["schema"]

        if "example" in parameter:
            example = parameter["example"]
        elif json_encoded and "example" in parameter["content"]["application/json"]:
            example = parameter["content"]["application/json"]["example"]
        else:
            example = schema.get("example", NO_EXAMPLE)

        parameters.append(
            Parameter(
                kind=parameter["in"],
                name=parameter["name"],
                description=parameter["description"],
                json_encoded=json_encoded,
                value_schema=schema,
                example=example,
                required=parameter.get("required", False),
                deprecated=parameter.get("deprecated", False),
            )
        )

    if "requestBody" in operation and "application/x-www-form-urlencoded" in (
        content := operation["requestBody"]["content"]
    ):
        media_type = content["application/x-www-form-urlencoded"]
        required = media_type["schema"].get("required", [])
        for key, schema in media_type["schema"]["properties"].items():
            json_encoded = (
                "encoding" in media_type
                and key in (encodings := media_type["encoding"])
                and encodings[key].get("contentType") == "application/json"
            ) or schema.get("type") == "object"

            parameters.append(
                Parameter(
                    kind="formData",
                    name=key,
                    description=schema["description"],
                    json_encoded=json_encoded,
                    value_schema=schema,
                    example=schema.get("example"),
                    required=key in required,
                    deprecated=schema.get("deprecated", False),
                )
            )

    return parameters


def get_openapi_return_values(endpoint: str, method: str) -> dict[str, Any]:
    operation = openapi_spec.openapi()["paths"][endpoint][method.lower()]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    # We do not currently have documented endpoints that have multiple schemas
    # ("oneOf", "anyOf", "allOf") for success ("200") responses. If this changes,
    # then the assertion below will need to be removed, and this function updated
    # so that endpoint responses will be rendered as expected.
    assert "properties" in schema
    return schema["properties"]


def find_openapi_endpoint(path: str) -> str | None:
    for path_regex, endpoint in openapi_spec.endpoints_dict().items():
        matches = re.match(path_regex, path)
        if matches:
            return endpoint
    return None


def validate_against_openapi_schema(
    content: dict[str, Any], path: str, method: str, status_code: str
) -> bool:
    mock_request = MockRequest("http://localhost:9991/", method, "/api/v1" + path)
    mock_response = MockResponse(
        orjson.dumps(content),
        status_code=int(status_code),
    )
    return validate_test_response(mock_request, mock_response)


def validate_test_response(request: Request, response: Response) -> bool:
    """Compare a "content" dict with the defined schema for a specific method
    in an endpoint. Return true if validated and false if skipped.
    """

    if request.path.startswith("/json/"):
        path = request.path.removeprefix("/json")
    elif request.path.startswith("/api/v1/"):
        path = request.path.removeprefix("/api/v1")
    else:
        return False
    assert request.method is not None
    method = request.method.lower()
    status_code = str(response.status_code)

    # This first set of checks are primarily training wheels that we
    # hope to eliminate over time as we improve our API documentation.

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
    # Code is not declared but appears in various 400 responses. If
    # common, it can be added to 400 response schema
    if status_code.startswith("4"):
        # This return statement should ideally be not here. But since
        # we have not defined 400 responses for various paths this has
        # been added as all 400 have the same schema.  When all 400
        # response have been defined this should be removed.
        return True

    try:
        openapi_spec.spec().validate_response(request, response)
    except OpenAPIValidationError as error:
        message = f"Response validation error at {method} /api/v1{path} ({status_code}):"
        message += f"\n\n{type(error).__name__}: {error}"
        message += (
            "\n\nFor help debugging these errors see: "
            "https://zulip.readthedocs.io/en/latest/documentation/api.html#debugging-schema-validation-errors"
        )
        raise SchemaError(message) from None

    return True


def validate_schema(schema: dict[str, Any]) -> None:
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


def deprecated_note_in_description(description: str) -> bool:
    if "**Changes**: Deprecated" in description:
        return True

    return "**Deprecated**" in description


def check_deprecated_consistency(deprecated: bool, description: str) -> None:
    # Test to make sure deprecated parameters are marked so.
    if deprecated_note_in_description(description):
        assert deprecated, (
            f"Missing `deprecated: true` despite being described as deprecated:\n\n{description}\n"
        )
    if deprecated:
        assert deprecated_note_in_description(description), (
            f"Marked as `deprecated: true`, but changes documentation doesn't properly explain as **Deprecated** in the standard format\n\n:{description}\n"
        )


# Skip those JSON endpoints whose query parameters are different from
# their `/api/v1` counterpart.  This is a legacy code issue that we
# plan to fix by changing the implementation.
SKIP_JSON = {
    ("/fetch_api_key", "post"),
}


def validate_request(
    url: str,
    method: str,
    data: str | bytes | Mapping[str, Any],
    http_headers: dict[str, str],
    json_url: bool,
    status_code: str,
    intentionally_undocumented: bool = False,
) -> None:
    assert isinstance(data, dict)
    mock_request = MockRequest(
        "http://localhost:9991/",
        method,
        "/api/v1" + url,
        headers=http_headers,
        args={k: str(v) for k, v in data.items()},
    )
    validate_test_request(mock_request, status_code, intentionally_undocumented)


def validate_test_request(
    request: Request,
    status_code: str,
    intentionally_undocumented: bool = False,
) -> None:
    assert request.method is not None
    method = request.method.lower()
    if request.path.startswith("/json/"):
        url = request.path.removeprefix("/json")
        # Some JSON endpoints have different parameters compared to
        # their `/api/v1` counterparts.
        if (url, method) in SKIP_JSON:
            return
    else:
        assert request.path.startswith("/api/v1/")
        url = request.path.removeprefix("/api/v1")

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
    try:
        openapi_spec.spec().validate_request(request)
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
