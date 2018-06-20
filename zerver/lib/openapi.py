# Set of helper functions to manipulate the OpenAPI files that define our REST
# API's specification.
import os
from typing import Any, Dict, List, Optional

from yamole import YamoleParser

OPENAPI_SPEC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    '../openapi/zulip.yaml'))

with open(OPENAPI_SPEC_PATH) as file:
    yaml_parser = YamoleParser(file)

OPENAPI_SPEC = yaml_parser.data

# A list of exceptions we allow when running validate_against_openapi_schema.
# The validator will ignore these keys when they appear in the "content"
# passed.
EXCLUDE_PROPERTIES = {
}


class SchemaError(Exception):
    pass

def get_openapi_fixture(endpoint: str, method: str,
                        response: Optional[str]='200') -> Dict[str, Any]:
    """Fetch a fixture from the full spec object.
    """
    return (OPENAPI_SPEC['paths'][endpoint][method.lower()]['responses']
            [response]['content']['application/json']['schema']
            ['example'])

def get_openapi_parameters(endpoint: str,
                           method: str) -> List[Dict[str, Any]]:
    return (OPENAPI_SPEC['paths'][endpoint][method.lower()]['parameters'])

def validate_against_openapi_schema(content: Dict[str, Any], endpoint: str,
                                    method: str, response: str) -> None:
    """Compare a "content" dict with the defined schema for a specific method
    in an endpoint.
    """
    schema = (OPENAPI_SPEC['paths'][endpoint][method.lower()]['responses']
              [response]['content']['application/json']['schema'])

    exclusion_list = (EXCLUDE_PROPERTIES.get(endpoint, {}).get(method, {})
                                        .get(response, []))

    for key, value in content.items():
        # Ignore in the validation the keys in EXCLUDE_PROPERTIES
        if key in exclusion_list:
            continue

        # Check that the key is defined in the schema
        if key not in schema['properties']:
            raise SchemaError('Extraneous key "{}" in the response\'s '
                              'content'.format(key))

        # Check that the types match
        expected_type = to_python_type(schema['properties'][key]['type'])
        actual_type = type(value)
        if expected_type is not actual_type:
            raise SchemaError('Expected type {} for key "{}", but actually '
                              'got {}'.format(expected_type, key, actual_type))

    # Check that at least all the required keys are present
    for req_key in schema['required']:
        if req_key not in content.keys():
            raise SchemaError('Expected to find the "{}" required key')

def to_python_type(py_type: str) -> type:
    """Transform an OpenAPI-like type to a Pyton one.
    https://swagger.io/docs/specification/data-models/data-types
    """
    TYPES = {
        'string': str,
        'number': float,
        'integer': int,
        'boolean': bool,
        'array': list,
        'object': dict
    }

    return TYPES[py_type]
