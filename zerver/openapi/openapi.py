# Set of helper functions to manipulate the OpenAPI files that define our REST
# API's specification.
import os
from typing import Any, Dict, List, Optional, Set

OPENAPI_SPEC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    '../openapi/zulip.yaml'))

# A list of exceptions we allow when running validate_against_openapi_schema.
# The validator will ignore these keys when they appear in the "content"
# passed.
EXCLUDE_PROPERTIES = {
    '/register': {
        'post': {
            '200': ['max_message_id', 'realm_emoji'],
        },
    },
    '/zulip-outgoing-webhook': {
        'post': {
            '200': ['result', 'msg', 'message'],
        },
    },
}

class OpenAPISpec():
    def __init__(self, path: str) -> None:
        self.path = path
        self.last_update: Optional[float] = None
        self.data: Optional[Dict[str, Any]] = None

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
        self.last_update = os.path.getmtime(self.path)

    def spec(self) -> Dict[str, Any]:
        """Reload the OpenAPI file if it has been modified after the last time
        it was read, and then return the parsed data.
        """
        last_modified = os.path.getmtime(self.path)
        # Using != rather than < to cover the corner case of users placing an
        # earlier version than the current one
        if self.last_update != last_modified:
            self.reload()
        assert(self.data)
        return self.data

class SchemaError(Exception):
    pass

openapi_spec = OpenAPISpec(OPENAPI_SPEC_PATH)

def get_schema(endpoint: str, method: str, response: str) -> Dict[str, Any]:
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
                        response: Optional[str]='200') -> Dict[str, Any]:
    """Fetch a fixture from the full spec object.
    """
    if response is None:
        response = '200'
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

exclusion_list: List[str] = []

def validate_against_openapi_schema(content: Dict[str, Any], endpoint: str,
                                    method: str, response: str) -> None:
    """Compare a "content" dict with the defined schema for a specific method
    in an endpoint.
    """
    # Check if the response matches its code
    if response.startswith('2') and (content.get('result', 'success').lower() != 'success'):
        raise SchemaError("Response is not 200 but is validating against 200 schema")
    global exclusion_list
    schema = get_schema(endpoint, method, response)
    # In a single response schema we do not have two keys with the same name.
    # Hence exclusion list is declared globally
    exclusion_list = (EXCLUDE_PROPERTIES.get(endpoint, {}).get(method, {}).get(response, []))
    # Code is not declared but appears in various 400 responses. If common, it can be added
    # to 400 response schema
    if response.startswith('4'):
        exclusion_list.append('code')
    validate_object(content, schema)

def validate_array(content: List[Any], schema: Dict[str, Any]) -> None:
    valid_types: List[type] = []
    if 'oneOf' in schema['items']:
        for valid_type in schema['items']['oneOf']:
            valid_types.append(to_python_type(valid_type['type']))
    else:
        valid_types.append(to_python_type(schema['items']['type']))
    for item in content:
        if type(item) not in valid_types:
            raise SchemaError('Wrong data type in array')
        # We can directly check for objects and arrays as
        # there are no mixed arrays consisting of objects
        # and arrays.
        if 'object' in valid_types:
            if 'oneOf' not in schema['items']:
                validate_object(item, schema['items'])
            continue
        # If the object was not an opaque object then
        # the continue statement above should have
        # been executed.
        if type(item) is dict:
            raise SchemaError('Opaque object in array')
        if 'items' in schema['items']:
            validate_array(item, schema['items'])

def validate_object(content: Dict[str, Any], schema: Dict[str, Any]) -> None:
    for key, value in content.items():
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
        else:
            expected_type.append(to_python_type(schema['properties'][key]['type']))
        actual_type = type(value)
        # We have only define nullable property if it is nullable
        if value is None and 'nullable' in schema['properties'][key]:
            continue
        if actual_type not in expected_type:
            raise SchemaError('Expected type {} for key "{}", but actually '
                              'got {}'.format(expected_type, key, actual_type))
        if expected_type is list:
            validate_array(value, schema['properties'][key])
        if 'properties' in schema['properties'][key]:
            validate_object(value, schema['properties'][key])
            continue
        if 'additionalProperties' in schema['properties'][key]:
            for child_keys in value:
                if type(value[child_keys]) is list:
                    validate_array(value[child_keys],
                                   schema['properties'][key]['additionalProperties'])
                    continue
                validate_object(value[child_keys],
                                schema['properties'][key]['additionalProperties'])
            continue
        # If the object is not opaque then continue statements
        # will be executed above and this will be skipped
        if expected_type is dict:
            raise SchemaError(f'Opaque object "{key}"')
    # Check that at least all the required keys are present
    if 'required' in schema:
        for req_key in schema['required']:
            if req_key in exclusion_list:
                continue
            if req_key not in content.keys():
                raise SchemaError('Expected to find the "{}" required key'.format(req_key))

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
