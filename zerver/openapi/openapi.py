# Set of helper functions to manipulate the OpenAPI files that define our REST
# API's specification.
import os
import re
from typing import Any, Dict, List, Optional, Set

from openapi_core import create_spec
from openapi_core.testing import MockRequest
from openapi_core.validation.request.validators import RequestValidator
from openapi_schema_validator import OAS30Validator

OPENAPI_SPEC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    '../openapi/zulip.yaml'))

# A list of endpoint-methods such that the endpoint
# has documentation but not with this particular method.
EXCLUDE_UNDOCUMENTED_ENDPOINTS = {"/realm/emoji/{emoji_name}:delete", "/users:patch"}
# Consists of endpoints with some documentation remaining.
# These are skipped but return true as the validator cannot exclude objects
EXCLUDE_DOCUMENTED_ENDPOINTS = {"/settings/notifications:patch"}
class OpenAPISpec():
    def __init__(self, path: str) -> None:
        self.path = path
        self.last_update: Optional[float] = None
        self.data: Dict[str, Any] = {}
        self.regex_dict: Dict[str, str] = {}
        self.core_data: Any = None
        self.documented_events: Set[str] = set()

    def reload(self) -> None:
        # Because importing yamole (and in turn, yaml) takes
        # significant time, and we only use python-yaml for our API
        # docs, importing it lazily here is a significant optimization
        # to `manage.py` startup.
        #
        # There is a bit of a race here...we may have two processes
        # accessing this module level object and both trying to
        # populate self.data at the same time.  Hopefully this will
        # only cause some extra processing at startup and not data
        # corruption.
        from yamole import YamoleParser
        with open(self.path) as f:
            yaml_parser = YamoleParser(f)
        self.data = yaml_parser.data
        validator_spec = create_spec(self.data)
        self.core_data = RequestValidator(validator_spec)
        self.create_regex_dict()
        self.last_update = os.path.getmtime(self.path)

    def create_regex_dict(self) -> None:
        # Alogrithm description:
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

        email_regex = r'([a-zA-Z0-9_\-\.]+)@([a-zA-Z0-9_\-\.]+)\.([a-zA-Z]{2,5})'
        self.regex_dict = {}
        for key in self.data['paths']:
            if '{' not in key:
                continue
            regex_key = '^' + key + '$'
            # Numeric arguments have id at their end
            # so find such arguments and replace them with numeric
            # regex
            regex_key = re.sub(r'{[^}]*id}', r'[0-9]*', regex_key)
            # Email arguments end with email
            regex_key = re.sub(r'{[^}]*email}', email_regex, regex_key)
            # All other types of arguments are supposed to be
            # all-encompassing string.
            regex_key = re.sub(r'{[^}]*}', r'[^\/]*', regex_key)
            regex_key = regex_key.replace(r'/', r'\/')
            regex_key = fr'{regex_key}'
            self.regex_dict[regex_key] = key

    def spec(self) -> Dict[str, Any]:
        """Reload the OpenAPI file if it has been modified after the last time
        it was read, and then return the parsed data.
        """
        last_modified = os.path.getmtime(self.path)
        # Using != rather than < to cover the corner case of users placing an
        # earlier version than the current one
        if self.last_update != last_modified:
            self.reload()
        assert(len(self.data) > 0)
        return self.data

    def regex_keys(self) -> Dict[str, str]:
        """Reload the OpenAPI file if it has been modified after the last time
        it was read, and then return the parsed data.
        """
        last_modified = os.path.getmtime(self.path)
        # Using != rather than < to cover the corner case of users placing an
        # earlier version than the current one
        if self.last_update != last_modified:
            self.reload()
        assert(len(self.regex_dict) > 0)
        return self.regex_dict

    def core_validator(self) -> Any:
        """Reload the OpenAPI file if it has been modified after the last time
        it was read, and then return the openapi_core validator object. Similar
        to preceding functions. Used for proper access to OpenAPI objects.
        """
        last_modified = os.path.getmtime(self.path)
        # Using != rather than < to cover the corner case of users placing an
        # earlier version than the current one
        if self.last_update != last_modified:
            self.reload()
        return self.core_data

class SchemaError(Exception):
    pass

openapi_spec = OpenAPISpec(OPENAPI_SPEC_PATH)

def get_schema(endpoint: str, method: str, response: str) -> Dict[str, Any]:
    if len(response) == 3 and ('oneOf' in (openapi_spec.spec())['paths'][endpoint]
                               [method.lower()]['responses'][response]['content']
                               ['application/json']['schema']):
        # Currently at places where multiple schemas are defined they only
        # differ in example so either can be used.
        response += '_0'
    if len(response) == 3:
        schema = (openapi_spec.spec()['paths'][endpoint][method.lower()]['responses']
                  [response]['content']['application/json']['schema'])
        return schema
    else:
        resp_code = int(response[4])
        response = response[0:3]
        schema = (openapi_spec.spec()['paths'][endpoint][method.lower()]['responses']
                  [response]['content']['application/json']['schema']["oneOf"][resp_code])
        return schema

def get_openapi_fixture(endpoint: str, method: str,
                        response: str='200') -> Dict[str, Any]:
    """Fetch a fixture from the full spec object.
    """
    return (get_schema(endpoint, method, response)['example'])

def get_openapi_description(endpoint: str, method: str) -> str:
    """Fetch a description from the full spec object.
    """
    description = openapi_spec.spec()['paths'][endpoint][method.lower()]['description']
    return description

def get_openapi_paths() -> Set[str]:
    return set(openapi_spec.spec()['paths'].keys())

def get_openapi_parameters(endpoint: str, method: str,
                           include_url_parameters: bool=True) -> List[Dict[str, Any]]:
    openapi_endpoint = openapi_spec.spec()['paths'][endpoint][method.lower()]
    # We do a `.get()` for this last bit to distinguish documented
    # endpoints with no parameters (empty list) from undocumented
    # endpoints (KeyError exception).
    parameters = openapi_endpoint.get('parameters', [])
    # Also, we skip parameters defined in the URL.
    if not include_url_parameters:
        parameters = [parameter for parameter in parameters if
                      parameter['in'] != 'path']
    return parameters

def get_openapi_return_values(endpoint: str, method: str,
                              include_url_parameters: bool=True) -> List[Dict[str, Any]]:
    openapi_endpoint = openapi_spec.spec()['paths'][endpoint][method.lower()]
    response = openapi_endpoint['responses']['200']['content']['application/json']['schema']
    # In cases where we have used oneOf, the schemas only differ in examples
    # So we can choose any.
    if 'oneOf' in response:
        response = response['oneOf'][0]
    response = response['properties']
    return response

def match_against_openapi_regex(endpoint: str) -> Optional[str]:
    for key in openapi_spec.regex_keys():
        matches = re.match(fr'{key}', endpoint)
        if matches:
            return openapi_spec.regex_keys()[key]
    return None

def get_event_type(event: Dict[str, Any]) -> str:
    return event['type'] + ':' + event.get('op', '')

def fix_events(content: Dict[str, Any]) -> None:
    """Remove undocumented events from events array. This is a makeshift
    function so that further documentation of `/events` can happen with
    only zulip.yaml changes and minimal other changes. It should be removed
    as soon as `/events` documentation is complete.
    """
    # 'user' is deprecated so remove its occurences from the events array
    for event in content['events']:
        event.pop('user', None)

def validate_against_openapi_schema(content: Dict[str, Any], endpoint: str,
                                    method: str, response: str) -> bool:
    """Compare a "content" dict with the defined schema for a specific method
    in an endpoint. Return true if validated and false if skipped.
    """

    # This first set of checks are primarily training wheels that we
    # hope to eliminate over time as we improve our API documentation.

    # No 500 responses have been documented, so skip them
    if response.startswith('5'):
        return False
    if endpoint not in openapi_spec.spec()['paths'].keys():
        match = match_against_openapi_regex(endpoint)
        # If it doesn't match it hasn't been documented yet.
        if match is None:
            return False
        endpoint = match
    # Excluded endpoint/methods
    if endpoint + ':' + method in EXCLUDE_UNDOCUMENTED_ENDPOINTS:
        return False
    # Return true for endpoints with only response documentation remaining
    if endpoint + ':' + method in EXCLUDE_DOCUMENTED_ENDPOINTS:
        return True
    # Check if the response matches its code
    if response.startswith('2') and (content.get('result', 'success').lower() != 'success'):
        raise SchemaError("Response is not 200 but is validating against 200 schema")
    # Code is not declared but appears in various 400 responses. If
    # common, it can be added to 400 response schema
    if response.startswith('4'):
        # This return statement should ideally be not here. But since
        # we have not defined 400 responses for various paths this has
        # been added as all 400 have the same schema.  When all 400
        # response have been defined this should be removed.
        return True
    # The actual work of validating that the response matches the
    # schema is done via the third-party OAS30Validator.
    schema = get_schema(endpoint, method, response)
    if endpoint == '/events' and method == 'get':
        # This a temporary function for checking only documented events
        # as all events haven't been documented yet.
        # TODO: Remove this after all events have been documented.
        fix_events(content)
    validator = OAS30Validator(schema)
    validator.validate(content)
    return True

def validate_schema_array(schema: Dict[str, Any]) -> None:
    """
    Helper function for validate_schema
    """
    if 'oneOf' in schema['items']:
        for oneof_schema in schema['items']['oneOf']:
            if oneof_schema['type'] == 'array':
                validate_schema_array(oneof_schema)
            elif oneof_schema['type'] == 'object':
                validate_schema(oneof_schema)
    else:
        if schema['items']['type'] == 'array':
            validate_schema_array(schema['items'])
        elif schema['items']['type'] == 'object':
            validate_schema(schema['items'])

def validate_schema(schema: Dict[str, Any]) -> None:
    """Check if opaque objects are present in the OpenAPI spec; this is an
    important part of our policy for ensuring every detail of Zulip's
    API responses is correct.

    This is done by checking for the presence of the
    `additionalProperties` attribute for all objects (dictionaries).
    """
    if 'additionalProperties' not in schema:
        raise SchemaError('additionalProperties needs to be defined for objects to make' +
                          'sure they have no additional properties left to be documented.')
    for key in schema.get('properties', dict()):
        if 'oneOf' in schema['properties'][key]:
            for types in schema['properties'][key]['oneOf']:
                if types['type'] == 'object':
                    validate_schema(types)
                elif types['type'] == 'array':
                    validate_schema_array(types)
        else:
            if schema['properties'][key]['type'] == 'object':
                validate_schema(schema['properties'][key])
            elif schema['properties'][key]['type'] == 'array':
                validate_schema_array(schema['properties'][key])
    if schema['additionalProperties']:
        if schema['additionalProperties']['type'] == 'array':
            validate_schema_array(schema['additionalProperties'])
        elif schema['additionalProperties']['type'] == 'object':
            validate_schema(schema['additionalProperties'])

def to_python_type(py_type: str) -> type:
    """Transform an OpenAPI-like type to a Python one.
    https://swagger.io/docs/specification/data-models/data-types
    """
    TYPES = {
        'string': str,
        'number': float,
        'integer': int,
        'boolean': bool,
        'array': list,
        'object': dict,
    }

    return TYPES[py_type]

def likely_deprecated_parameter(parameter_description: str) -> bool:
    if '**Changes**: Deprecated' in parameter_description:
        return True

    return "**Deprecated**" in parameter_description

# Skip those JSON endpoints whose query parameters are different from
# their `/api/v1` counterpart.  This is a legacy code issue that we
# plan to fix by changing the implementation.
SKIP_JSON = {'/fetch_api_key:post'}

def validate_request(url: str, method: str, data: Dict[str, Any],
                     http_headers: Dict[str, Any], json_url: bool,
                     status_code: str, intentionally_undocumented: bool=False) -> None:
    # Some JSON endpoints have different parameters compared to
    # their `/api/v1` counterparts.
    if json_url and url + ':' + method in SKIP_JSON:
        return

    # TODO: Add support for file upload endpoints that lack the /json/
    # or /api/v1/ prefix.
    if url == '/user_uploads' or url.startswith('/realm/emoji/'):
        return

    # Now using the openapi_core APIs, validate the request schema
    # against the OpenAPI documentation.
    mock_request = MockRequest('http://localhost:9991/', method, '/api/v1' + url,
                               headers=http_headers, args=data)
    result = openapi_spec.core_validator().validate(mock_request)
    if len(result.errors) != 0:
        # Requests that do not validate against the OpenAPI spec must either:
        # * Have returned a 400 (bad request) error
        # * Have returned a 200 (success) with this request marked as intentionally
        # undocumented behavior.
        if status_code.startswith('4'):
            return
        if status_code.startswith('2') and intentionally_undocumented:
            return

    # If no errors are raised, then validation is successful
    if len(result.errors) == 0:
        return

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

The errors logged by the OpenAPI validator are below:\n"""
    for error in result.errors:
        msg += f"* {str(error)}\n"
    raise SchemaError(msg)
