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


def get_openapi_fixture(endpoint: str, method: str,
                        response: Optional[str]='200') -> Dict[str, Any]:
    return (OPENAPI_SPEC['paths'][endpoint][method.lower()]['responses']
            [response]['content']['application/json']['schema']
            ['example'])

def get_openapi_parameters(endpoint: str,
                           method: str) -> List[Dict[str, Any]]:
    return (OPENAPI_SPEC['paths'][endpoint][method]['parameters'])
