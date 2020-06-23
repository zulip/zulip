# Set of helper functions to manipulate the OpenAPI files that define our REST
# API's specification.
import os
import re
from typing import Any, Dict, List, Optional, Set

OPENAPI_SPEC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    '../openapi/zulip.yaml'))

# A list of exceptions we allow when running validate_against_openapi_schema.
# The validator will ignore these keys when they appear in the "content"
# passed.
EXCLUDE_PROPERTIES = {
    '/events': {
        'get': {
            # Array with opaque object
            '200': ['events']
        }
    },
    '/register': {
        'post': {
            '200': ['max_message_id', 'realm_emoji', 'pointer'],
        },
    },
    '/settings/notifications': {
        'patch': {
            # Some responses contain undocumented keys
            '200': ['notification_sound', 'enable_login_emails',
                    'enable_stream_desktop_notifications', 'wildcard_mentions_notify',
                    'pm_content_in_desktop_notifications', 'desktop_icon_count_display',
                    'realm_name_in_notifications', 'presence_enabled'],
        },
    },
}

# A list of endpoint-methods such that the endpoint
# has documentation but not with this particular method.
EXCLUDE_ENDPOINTS = ["/realm/emoji/{emoji_name}:delete"]
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
    if endpoint + ':' + method in EXCLUDE_ENDPOINTS:
        return False

    # Check if the response matches its code
    if response.startswith('2') and (content.get('result', 'success').lower() != 'success'):
        raise SchemaError("Response is not 200 but is validating against 200 schema")
    # In a single response schema we do not have two keys with the same name.
    # Hence exclusion list is declared globally
    exclusion_list = (EXCLUDE_PROPERTIES.get(endpoint, {}).get(method.lower(), {}).get(response, []))
    # Code is not declared but appears in various 400 responses. If common, it can be added
    # to 400 response schema
    if response.startswith('4'):
        exclusion_list.append('code')
        # This return statement should ideally be not here. But since we have not defined 400
        # responses for various paths this has been added as all 400 have the same schema.
        # When all 400 response have been defined this should be removed.
        return True
    schema = get_schema(endpoint, method, response)
    validate_object(content, schema, exclusion_list)
    return True

def validate_array(content: List[Any], schema: Dict[str, Any], exclusion_list: List[str]) -> None:
    valid_types: List[type] = []
    object_schema: Optional[Dict[str, Any]] = None
    array_schema: Optional[Dict[str, Any]] = None
    if 'oneOf' in schema['items']:
        for oneof_schema in schema['items']['oneOf']:
            if oneof_schema['type'] == 'array':
                array_schema = oneof_schema
            elif oneof_schema['type'] == 'object':
                object_schema = oneof_schema
            valid_types.append(to_python_type(oneof_schema['type']))
    else:
        valid_types.append(to_python_type(schema['items']['type']))
        if schema['items']['type'] == 'array':
            array_schema = schema['items']
        elif schema['items']['type'] == 'object':
            object_schema = schema['items']

    for item in content:
        if type(item) not in valid_types:
            raise SchemaError('Wrong data type in array')
        # We can directly check for objects and arrays as
        # there are no mixed arrays consisting of objects
        # and arrays.
        if type(item) == dict:
            assert object_schema is not None
            if 'properties' not in object_schema:
                raise SchemaError('Opaque object in array')
            validate_object(item, object_schema, exclusion_list)
        if type(item) == list:
            assert(array_schema is not None)
            validate_array(item, array_schema, exclusion_list)

def validate_object(content: Dict[str, Any], schema: Dict[str, Any], exclusion_list: List[str]) -> None:
    for key, value in content.items():
        object_schema: Optional[Dict[str, Any]] = None
        array_schema: Optional[Dict[str, Any]] = None
        if key in exclusion_list:
            continue
        # Check that the key is defined in the schema
        if key not in schema['properties']:
            raise SchemaError('Extraneous key "{}" in the response\'s '
                              'content'.format(key))
        # Check that the types match
        expected_type: List[type] = []
        if 'oneOf' in schema['properties'][key]:
            for types in schema['properties'][key]['oneOf']:
                expected_type.append(to_python_type(types['type']))
                if types['type'] == 'object':
                    object_schema = types
                elif types['type'] == 'array':
                    array_schema = types
        else:
            expected_type.append(to_python_type(schema['properties'][key]['type']))
            if schema['properties'][key]['type'] == 'object':
                object_schema = schema['properties'][key]
            elif schema['properties'][key]['type'] == 'array':
                array_schema = schema['properties'][key]

        actual_type = type(value)
        # We have only define nullable property if it is nullable
        if value is None and 'nullable' in schema['properties'][key]:
            continue
        if actual_type not in expected_type:
            raise SchemaError('Expected type {} for key "{}", but actually '
                              'got {}'.format(expected_type, key, actual_type))
        if actual_type == list:
            assert array_schema is not None
            validate_array(value, array_schema, exclusion_list)
        if actual_type == dict:
            assert object_schema is not None
            if 'properties' in object_schema:
                validate_object(value, object_schema, exclusion_list)
                continue
        if 'additionalProperties' in schema['properties'][key]:
            for child_keys in value:
                if type(value[child_keys]) == list:
                    validate_array(value[child_keys],
                                   schema['properties'][key]['additionalProperties'], exclusion_list)
                    continue
                validate_object(value[child_keys],
                                schema['properties'][key]['additionalProperties'], exclusion_list)
            continue
        # If the object is not opaque then continue statements
        # will be executed above and this will be skipped
        if actual_type == dict:
            raise SchemaError(f'Opaque object "{key}"')
    # Check that at least all the required keys are present
    if 'required' in schema:
        for req_key in schema['required']:
            if req_key in exclusion_list:
                continue
            if req_key not in content.keys():
                raise SchemaError(f'Expected to find the "{req_key}" required key')

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
