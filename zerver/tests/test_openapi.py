# -*- coding: utf-8 -*-

import mock
from typing import Dict, Any

import zerver.lib.openapi as openapi
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.openapi import (
    get_openapi_fixture, get_openapi_parameters,
    validate_against_openapi_schema, to_python_type, SchemaError, openapi_spec
)

TEST_ENDPOINT = '/messages/{message_id}'
TEST_METHOD = 'patch'
TEST_RESPONSE_BAD_REQ = '400'
TEST_RESPONSE_SUCCESS = '200'


class OpenAPIToolsTest(ZulipTestCase):
    """Make sure that the tools we use to handle our OpenAPI specification
    (located in zerver/lib/openapi.py) work as expected.

    These tools are mostly dedicated to fetching parts of the -already parsed-
    specification, and comparing them to objects returned by our REST API.
    """
    def test_get_openapi_fixture(self) -> None:
        actual = get_openapi_fixture(TEST_ENDPOINT, TEST_METHOD,
                                     TEST_RESPONSE_BAD_REQ)
        expected = {
            'code': 'BAD_REQUEST',
            'msg': 'You don\'t have permission to edit this message',
            'result': 'error'
        }
        self.assertEqual(actual, expected)

    def test_get_openapi_parameters(self) -> None:
        actual = get_openapi_parameters(TEST_ENDPOINT, TEST_METHOD)
        expected_item = {
            'name': 'message_id',
            'in': 'path',
            'description':
                'The ID of the message that you wish to edit/update.',
            'example': 42,
            'required': True,
            'schema': {'type': 'integer'}
        }
        assert(expected_item in actual)

    def test_validate_against_openapi_schema(self) -> None:
        with self.assertRaises(SchemaError,
                               msg=('Extraneous key "foo" in '
                                    'the response\'scontent')):
            bad_content = {
                'msg': '',
                'result': 'success',
                'foo': 'bar'
            }  # type: Dict[str, Any]
            validate_against_openapi_schema(bad_content,
                                            TEST_ENDPOINT,
                                            TEST_METHOD,
                                            TEST_RESPONSE_SUCCESS)

        with self.assertRaises(SchemaError,
                               msg=("Expected type <class 'str'> for key "
                                    "\"msg\", but actually got "
                                    "<class 'int'>")):
            bad_content = {
                'msg': 42,
                'result': 'success',
            }
            validate_against_openapi_schema(bad_content,
                                            TEST_ENDPOINT,
                                            TEST_METHOD,
                                            TEST_RESPONSE_SUCCESS)

        with self.assertRaises(SchemaError,
                               msg='Expected to find the "msg" required key'):
            bad_content = {
                'result': 'success',
            }
            validate_against_openapi_schema(bad_content,
                                            TEST_ENDPOINT,
                                            TEST_METHOD,
                                            TEST_RESPONSE_SUCCESS)

        # No exceptions should be raised here.
        good_content = {
            'msg': '',
            'result': 'success',
        }
        validate_against_openapi_schema(good_content,
                                        TEST_ENDPOINT,
                                        TEST_METHOD,
                                        TEST_RESPONSE_SUCCESS)

        # Overwrite the exception list with a mocked one
        openapi.EXCLUDE_PROPERTIES = {
            TEST_ENDPOINT: {
                TEST_METHOD: {
                    TEST_RESPONSE_SUCCESS: ['foo']
                }
            }
        }
        good_content = {
            'msg': '',
            'result': 'success',
            'foo': 'bar'
        }
        validate_against_openapi_schema(good_content,
                                        TEST_ENDPOINT,
                                        TEST_METHOD,
                                        TEST_RESPONSE_SUCCESS)

    def test_to_python_type(self) -> None:
        TYPES = {
            'string': str,
            'number': float,
            'integer': int,
            'boolean': bool,
            'array': list,
            'object': dict
        }

        for oa_type, py_type in TYPES.items():
            self.assertEqual(to_python_type(oa_type), py_type)

    def test_live_reload(self) -> None:
        # Force the reload by making the last update date < the file's last
        # modified date
        openapi_spec.last_update = 0
        get_openapi_fixture(TEST_ENDPOINT, TEST_METHOD)

        # Check that the file has been reloaded by verifying that the last
        # update date isn't zero anymore
        self.assertNotEqual(openapi_spec.last_update, 0)

        # Now verify calling it again doesn't call reload
        with mock.patch('zerver.lib.openapi.openapi_spec.reload') as mock_reload:
            get_openapi_fixture(TEST_ENDPOINT, TEST_METHOD)
            self.assertFalse(mock_reload.called)
