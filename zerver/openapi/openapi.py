# Set of helper functions to manipulate the OpenAPI files that define our REST
# API's specification.
import os
import re
from typing import Any, Dict, List, Optional, Set

from openapi_schema_validator import OAS30Validator

OPENAPI_SPEC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    '../openapi/zulip.yaml'))

# A list of endpoint-methods such that the endpoint
# has documentation but not with this particular method.
EXCLUDE_UNDOCUMENTED_ENDPOINTS = {"/realm/emoji/{emoji_name}:delete"}
# Consists of endpoints with some documentation remaining.
# These are skipped but return true as the validator cannot exclude objects
EXCLUDE_DOCUMENTED_ENDPOINTS = {"/events:get", "/register:post", "/settings/notifications:patch"}
class OpenAPISpec():
    def __init__(self, path: str) -> None:
        self.path = path
        self.last_update: Optional[float] = None
        self.data: Dict[str, Any] = {}
        self.regex_dict: Dict[str, str] = {}

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

def validate_against_openapi_schema(content: Dict[str, Any], endpoint: str,
                                    method: str, response: str) -> bool:
    """Compare a "content" dict with the defined schema for a specific method
    in an endpoint. Return true if validated and false if skipped.
    """
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
    # Code is not declared but appears in various 400 responses. If common, it can be added
    # to 400 response schema
    if response.startswith('4'):
        # This return statement should ideally be not here. But since we have not defined 400
        # responses for various paths this has been added as all 400 have the same schema.
        # When all 400 response have been defined this should be removed.
        return True
    schema = get_schema(endpoint, method, response)
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
    """
    Check if opaque objects are present in the OpenAPI spec. This is done by checking
    the presence of `additionalProperties` attribute for all object types. The attribute
    indicates to the openapi_schema_validator how extraneous keys should be treated.
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
