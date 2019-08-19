# -*- coding: utf-8 -*-

import re
import sys
import mock
import inspect
import typing
from typing import Dict, Any, Set, Union, List, Callable, Tuple, Optional, Iterable, Mapping, Sequence
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.http import HttpResponse

import zerver.lib.openapi as openapi
from zerver.lib.bugdown.api_code_examples import generate_curl_example, \
    render_curl_example, parse_language_and_options
from zerver.lib.request import _REQ
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.openapi import (
    get_openapi_fixture, get_openapi_parameters,
    validate_against_openapi_schema, to_python_type,
    SchemaError, openapi_spec, get_openapi_paths
)
from zerver.lib.request import arguments_map

TEST_ENDPOINT = '/messages/{message_id}'
TEST_METHOD = 'patch'
TEST_RESPONSE_BAD_REQ = '400'
TEST_RESPONSE_SUCCESS = '200'

VARMAP = {
    'integer': int,
    'string': str,
    'boolean': bool,
    'array': list,
    'Typing.List': list,
    'object': dict,
    'NoneType': type(None),
}

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
            }  # type: Dict[str, object]
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

class OpenAPIArgumentsTest(ZulipTestCase):
    # This will be filled during test_openapi_arguments:
    checked_endpoints = set()  # type: Set[str]
    # TODO: These endpoints need to be documented:
    pending_endpoints = set([
        '/users/me/avatar',
        '/settings/display',
        '/users/me/profile_data',
        '/users/me/pointer',
        '/users/me/presence',
        '/bot_storage',
        '/users/me/api_key/regenerate',
        '/default_streams',
        '/default_stream_groups/create',
        '/users/me/alert_words',
        '/users/me/status',
        '/messages/matches_narrow',
        '/dev_fetch_api_key',
        '/dev_list_users',
        '/fetch_api_key',
        '/fetch_google_client_id',
        '/get_auth_backends',
        '/settings',
        '/submessage',
        '/attachments',
        '/calls/create',
        '/export/realm',
        '/export/realm/{export_id}',
        '/zcommand',
        '/realm',
        '/realm/deactivate',
        '/realm/domains',
        '/realm/icon',
        '/realm/logo',
        '/realm/presence',
        '/realm/profile_fields',
        '/queue_id',
        '/invites',
        '/invites/multiuse',
        '/bots',
        # Used for desktop app to test connectivity.
        '/generate_204',
        # Mobile-app only endpoints
        '/users/me/android_gcm_reg_id',
        '/users/me/apns_device_token',
        # Regex based urls
        '/realm/domains/{domain}',
        '/realm/profile_fields/{field_id}',
        '/realm/subdomain/{subdomain}',
        '/users/{user_id}/reactivate',
        '/users/{user_id}',
        '/bots/{bot_id}/api_key/regenerate',
        '/bots/{bot_id}',
        '/invites/{prereg_id}',
        '/invites/{prereg_id}/resend',
        '/invites/multiuse/{invite_id}',
        '/users/me/subscriptions/{stream_id}',
        '/messages/{message_id}/reactions',
        '/messages/{message_id}/emoji_reactions/{emoji_name}',
        '/attachments/{attachment_id}',
        '/user_groups/{user_group_id}/members',
        '/streams/{stream_id}/members',
        '/streams/{stream_id}/delete_topic',
        '/default_stream_groups/{group_id}',
        '/default_stream_groups/{group_id}/streams',
        # Regex with an unnamed capturing group.
        '/users/(?!me/)(?P<email>[^/]*)/presence',
        # Actually '/user_groups/<user_group_id>' in urls.py but fails the reverse mapping
        # test because of the variable name mismatch. So really, it's more of a buggy endpoint.
        '/user_groups/{group_id}',  # Equivalent of what's in urls.py
        '/user_groups/{user_group_id}',  # What's in the OpenAPI docs
    ])
    # TODO: These endpoints have a mismatch between the
    # documentation and the actual API and need to be fixed:
    buggy_documentation_endpoints = set([
        '/events',
        '/users/me/subscriptions/muted_topics',
        # List of flags is broader in actual code; fix is to just add them
        '/settings/notifications',
        # Docs need update for subject -> topic migration
        '/messages/{message_id}',
    ])

    def convert_regex_to_url_pattern(self, regex_pattern: str) -> str:
        """ Convert regular expressions style URL patterns to their
            corresponding OpenAPI style formats. All patterns are
            expected to start with ^ and end with $.
            Examples:
                1. /messages/{message_id} <-> r'^messages/(?P<message_id>[0-9]+)$'
                2. /events <-> r'^events$'
        """

        # TODO: Probably we should be able to address the below
        # through alternative solutions (e.g. reordering urls.py
        # entries or similar url organization, but for now these let
        # us test more endpoints and so are worth doing).
        me_pattern = '/(?!me/)'
        if me_pattern in regex_pattern:
            # Remove the exclude-me pattern if present.
            regex_pattern = regex_pattern.replace(me_pattern, "/")
        if '[^/]*' in regex_pattern:
            # Handle the presence-email code which has a non-slashes syntax.
            regex_pattern = regex_pattern.replace('[^/]*', '.*')

        self.assertTrue(regex_pattern.startswith("^"))
        self.assertTrue(regex_pattern.endswith("$"))
        url_pattern = '/' + regex_pattern[1:][:-1]
        url_pattern = re.sub(r"\(\?P<(\w+)>[^/]+\)", r"{\1}", url_pattern)
        return url_pattern

    def ensure_no_documentation_if_intentionally_undocumented(self, url_pattern: str,
                                                              method: str,
                                                              msg: Optional[str]=None) -> None:
        try:
            get_openapi_parameters(url_pattern, method)
            if not msg:  # nocoverage
                msg = """
We found some OpenAPI documentation for {method} {url_pattern},
so maybe we shouldn't mark it as intentionally undocumented in the urls.
""".format(method=method, url_pattern=url_pattern)
            raise AssertionError(msg)  # nocoverage
        except KeyError:
            return

    def check_for_non_existant_openapi_endpoints(self) -> None:
        """ Here, we check to see if every endpoint documented in the openapi
        documentation actually exists in urls.py and thus in actual code.
        Note: We define this as a helper called at the end of
        test_openapi_arguments instead of as a separate test to ensure that
        this test is only executed after test_openapi_arguments so that it's
        results can be used here in the set operations. """
        openapi_paths = set(get_openapi_paths())
        undocumented_paths = openapi_paths - self.checked_endpoints
        undocumented_paths -= self.buggy_documentation_endpoints
        undocumented_paths -= self.pending_endpoints
        try:
            self.assertEqual(len(undocumented_paths), 0)
        except AssertionError:  # nocoverage
            msg = "The following endpoints have been documented but can't be found in urls.py:"
            for undocumented_path in undocumented_paths:
                msg += "\n + {}".format(undocumented_path)
            raise AssertionError(msg)

    def get_type_by_priority(self, types: Sequence[Union[type, Tuple[type, object]]]) -> Union[type, Tuple[type, object]]:
        priority = {list: 1, dict: 2, str: 3, int: 4, bool: 5}
        tyiroirp = {1: list, 2: dict, 3: str, 4: int, 5: bool}
        val = 6
        for t in types:
            if isinstance(t, tuple):
                return t  # e.g. (list, dict) or (list ,str)
            v = priority.get(t, 6)
            if v < val:
                val = v
        return tyiroirp.get(val, types[0])

    def get_standardized_argument_type(self, t: Any) -> Union[type, Tuple[type, object]]:
        """ Given a type from the typing module such as List[str] or Union[str, int],
        convert it into a corresponding Python type. Unions are mapped to a canonical
        choice among the options.
        E.g. typing.Union[typing.List[typing.Dict[str, typing.Any]], NoneType]
        needs to be mapped to list."""

        if sys.version_info < (3, 6) and type(t) == typing.UnionMeta:  # nocoverage # in python3.6+
            origin = Union
        else:  # nocoverage  # in python3.5. I.E. this is used in python3.6+
            origin = getattr(t, "__origin__", None)

        if not origin:
            # Then it's most likely one of the fundamental data types
            # I.E. Not one of the data types from the "typing" module.
            return t
        elif origin == Union:
            subtypes = []
            if sys.version_info < (3, 6):  # nocoverage # in python3.6+
                args = t.__union_params__
            else:  # nocoverage # in python3.5
                args = t.__args__
            for st in args:
                subtypes.append(self.get_standardized_argument_type(st))
            return self.get_type_by_priority(subtypes)
        elif origin in [List, Iterable]:
            subtypes = [self.get_standardized_argument_type(st) for st in t.__args__]
            return (list, self.get_type_by_priority(subtypes))
        elif origin in [Dict, Mapping]:
            return dict
        return self.get_standardized_argument_type(t.__args__[0])

    def render_openapi_type_exception(self, function:  Callable[..., HttpResponse],
                                      openapi_params: Set[Tuple[str, Union[type, Tuple[type, object]]]],
                                      function_params: Set[Tuple[str, Union[type, Tuple[type, object]]]],
                                      diff: Set[Tuple[str, Union[type, Tuple[type, object]]]]) -> None:  # nocoverage
        """ Print a *VERY* clear and verbose error message for when the types
        (between the OpenAPI documentation and the function declaration) don't match. """

        msg = """
The types for the request parameters in zerver/openapi/zulip.yaml
do not match the types declared in the implementation of {}.\n""".format(function.__name__)
        msg += '='*65 + '\n'
        msg += "{:<10s}{:^30s}{:>10s}\n".format("Parameter", "OpenAPI Type",
                                                "Function Declaration Type")
        msg += '='*65 + '\n'
        opvtype = None
        fdvtype = None
        for element in diff:
            vname = element[0]
            for element in openapi_params:
                if element[0] == vname:
                    opvtype = element[1]
                    break
            for element in function_params:
                if element[0] == vname:
                    fdvtype = element[1]
                    break
        msg += "{:<10s}{:^30s}{:>10s}\n".format(vname, str(opvtype), str(fdvtype))
        raise AssertionError(msg)

    def check_argument_types(self, function: Callable[..., HttpResponse],
                             openapi_parameters: List[Dict[str, Any]]) -> None:
        """ We construct for both the OpenAPI data and the function's definition a set of
        tuples of the form (var_name, type) and then compare those sets to see if the
        OpenAPI data defines a different type than that actually accepted by the function.
        Otherwise, we print out the exact differences for convenient debugging and raise an
        AssertionError. """
        openapi_params = set()  # type: Set[Tuple[str, Union[type, Tuple[type, object]]]]
        for element in openapi_parameters:
            name = element["name"]  # type: str
            _type = VARMAP[element["schema"]["type"]]
            if _type == list:
                items = element["schema"]["items"]
                if "anyOf" in items.keys():
                    subtypes = []
                    for st in items["anyOf"]:
                        st = st["type"]
                        subtypes.append(VARMAP[st])
                    self.assertTrue(len(subtypes) > 1)
                    sub_type = self.get_type_by_priority(subtypes)
                else:
                    sub_type = VARMAP[element["schema"]["items"]["type"]]
                    self.assertIsNotNone(sub_type)
                openapi_params.add((name, (_type, sub_type)))
            else:
                openapi_params.add((name, _type))

        function_params = set()  # type: Set[Tuple[str, Union[type, Tuple[type, object]]]]

        # Iterate through the decorators to find the original
        # function, wrapped by has_request_variables, so we can parse
        # its arguments.
        while getattr(function, "__wrapped__", None):
            function = getattr(function, "__wrapped__", None)
            # Tell mypy this is never None.
            assert function is not None

        # Now, we do inference mapping each REQ parameter's
        # declaration details to the Python/mypy types for the
        # arguments passed to it.
        #
        # Because the mypy types are the types used inside the inner
        # function (after the original data is processed by any
        # validators, converters, etc.), they will not always match
        # the API-level argument types.  The main case where this
        # happens is when a `converter` is used that changes the types
        # of its parameters.
        for vname, defval in inspect.signature(function).parameters.items():
            defval = defval.default
            if defval.__class__ is _REQ:
                # TODO: The below inference logic in cases where
                # there's a converter function declared is incorrect.
                # Theoretically, we could restructure the converter
                # function model so that we can check what type it
                # excepts to be passed to make validation here
                # possible.

                vtype = self.get_standardized_argument_type(function.__annotations__[vname])
                vname = defval.post_var_name  # type: ignore # See zerver/lib/request.py
                function_params.add((vname, vtype))

        diff = openapi_params - function_params
        if diff:  # nocoverage
            self.render_openapi_type_exception(function, openapi_params, function_params, diff)

    def test_openapi_arguments(self) -> None:
        """This end-to-end API documentation test compares the arguments
        defined in the actual code using @has_request_variables and
        REQ(), with the arguments declared in our API documentation
        for every API endpoint in Zulip.

        First, we import the fancy-Django version of zproject/urls.py
        by doing this, each has_request_variables wrapper around each
        imported view function gets called to generate the wrapped
        view function and thus filling the global arguments_map variable.
        Basically, we're exploiting code execution during import.

            Then we need to import some view modules not already imported in
        urls.py. We use this different syntax because of the linters complaining
        of an unused import (which is correct, but we do this for triggering the
        has_request_variables decorator).

            At the end, we perform a reverse mapping test that verifies that
        every url pattern defined in the openapi documentation actually exists
        in code.
        """

        urlconf = __import__(getattr(settings, "ROOT_URLCONF"), {}, {}, [''])

        # We loop through all the API patterns, looking in particular
        # for those using the rest_dispatch decorator; we then parse
        # its mapping of (HTTP_METHOD -> FUNCTION).
        for p in urlconf.v1_api_and_json_patterns + urlconf.v1_api_mobile_patterns:
            if p.lookup_str != 'zerver.lib.rest.rest_dispatch':
                # Endpoints not using rest_dispatch don't have extra data.
                methods_endpoints = dict(
                    GET=p.lookup_str,
                )
            else:
                methods_endpoints = p.default_args

            # since the module was already imported and is now residing in
            # memory, we won't actually face any performance penalties here.
            for method, value in methods_endpoints.items():
                if isinstance(value, str):
                    function_name = value
                    tags = set()  # type: Set[str]
                else:
                    function_name, tags = value

                lookup_parts = function_name.split('.')
                module = __import__('.'.join(lookup_parts[:-1]), {}, {}, [''])
                function = getattr(module, lookup_parts[-1])

                # Our accounting logic in the `has_request_variables()`
                # code means we have the list of all arguments
                # accepted by every view function in arguments_map.
                accepted_arguments = set(arguments_map[function_name])

                regex_pattern = p.regex.pattern
                url_pattern = self.convert_regex_to_url_pattern(regex_pattern)

                if "intentionally_undocumented" in tags:
                    self.ensure_no_documentation_if_intentionally_undocumented(url_pattern, method)
                    continue

                if url_pattern in self.pending_endpoints:
                    # HACK: After all pending_endpoints have been resolved, we should remove
                    # this segment and the "msg" part of the `ensure_no_...` method.
                    msg = """
We found some OpenAPI documentation for {method} {url_pattern},
so maybe we shouldn't include it in pending_endpoints.
""".format(method=method, url_pattern=url_pattern)
                    self.ensure_no_documentation_if_intentionally_undocumented(url_pattern,
                                                                               method, msg)
                    continue

                try:
                    # Don't include OpenAPI parameters that live in
                    # the path; these are not extracted by REQ.
                    openapi_parameters = get_openapi_parameters(url_pattern, method,
                                                                include_url_parameters=False)
                except Exception:  # nocoverage
                    raise AssertionError("Could not find OpenAPI docs for %s %s" %
                                         (method, url_pattern))

                # We now have everything we need to understand the
                # function as defined in our urls.py:
                #
                # * method is the HTTP method, e.g. GET, POST, or PATCH
                #
                # * p.regex.pattern is the URL pattern; might require
                #   some processing to match with OpenAPI rules
                #
                # * accepted_arguments is the full set of arguments
                #   this method accepts (from the REQ declarations in
                #   code).
                #
                # * The documented parameters for the endpoint as recorded in our
                #   OpenAPI data in zerver/openapi/zulip.yaml.
                #
                # We now compare these to confirm that the documented
                # argument list matches what actually appears in the
                # codebase.

                openapi_parameter_names = set(
                    [parameter['name'] for parameter in openapi_parameters]
                )

                if len(openapi_parameter_names - accepted_arguments) > 0:
                    print("Undocumented parameters for",
                          url_pattern, method, function_name)
                    print(" +", openapi_parameter_names)
                    print(" -", accepted_arguments)
                    assert(url_pattern in self.buggy_documentation_endpoints)
                elif len(accepted_arguments - openapi_parameter_names) > 0:
                    print("Documented invalid parameters for",
                          url_pattern, method, function_name)
                    print(" -", openapi_parameter_names)
                    print(" +", accepted_arguments)
                    assert(url_pattern in self.buggy_documentation_endpoints)
                else:
                    self.assertEqual(openapi_parameter_names, accepted_arguments)
                    self.check_argument_types(function, openapi_parameters)
                    self.checked_endpoints.add(url_pattern)

        self.check_for_non_existant_openapi_endpoints()


class ModifyExampleGenerationTestCase(ZulipTestCase):

    def test_no_mod_argument(self) -> None:
        res = parse_language_and_options("python")
        self.assertEqual(res, ("python", {}))

    def test_single_simple_mod_argument(self) -> None:
        res = parse_language_and_options("curl, mod=1")
        self.assertEqual(res, ("curl", {"mod": 1}))

        res = parse_language_and_options("curl, mod='somevalue'")
        self.assertEqual(res, ("curl", {"mod": "somevalue"}))

        res = parse_language_and_options("curl, mod=\"somevalue\"")
        self.assertEqual(res, ("curl", {"mod": "somevalue"}))

    def test_multiple_simple_mod_argument(self) -> None:
        res = parse_language_and_options("curl, mod1=1, mod2='a'")
        self.assertEqual(res, ("curl", {"mod1": 1, "mod2": "a"}))

        res = parse_language_and_options("curl, mod1=\"asdf\", mod2='thing', mod3=3")
        self.assertEqual(res, ("curl", {"mod1": "asdf", "mod2": "thing", "mod3": 3}))

    def test_single_list_mod_argument(self) -> None:
        res = parse_language_and_options("curl, exclude=['param1', 'param2']")
        self.assertEqual(res, ("curl", {"exclude": ["param1", "param2"]}))

        res = parse_language_and_options("curl, exclude=[\"param1\", \"param2\"]")
        self.assertEqual(res, ("curl", {"exclude": ["param1", "param2"]}))

        res = parse_language_and_options("curl, exclude=['param1', \"param2\"]")
        self.assertEqual(res, ("curl", {"exclude": ["param1", "param2"]}))

    def test_multiple_list_mod_argument(self) -> None:
        res = parse_language_and_options("curl, exclude=['param1', \"param2\"], special=['param3']")
        self.assertEqual(res, ("curl", {"exclude": ["param1", "param2"], "special": ["param3"]}))

    def test_multiple_mixed_mod_arguments(self) -> None:
        res = parse_language_and_options("curl, exclude=[\"asdf\", 'sdfg'], other_key='asdf', more_things=\"asdf\", another_list=[1, \"2\"]")
        self.assertEqual(res, ("curl", {"exclude": ["asdf", "sdfg"], "other_key": "asdf", "more_things": "asdf", "another_list": [1, "2"]}))


class TestCurlExampleGeneration(ZulipTestCase):

    spec_mock_without_examples = {
        "paths": {
            "/mark_stream_as_read": {
                "post": {
                    "description": "Mark all the unread messages in a stream as read.",
                    "parameters": [
                        {
                            "name": "stream_id",
                            "in": "query",
                            "description": "The ID of the stream whose messages should be marked as read.",
                            "schema": {
                                "type": "integer"
                            },
                            "required": True
                        },
                        {
                            "name": "bool_param",
                            "in": "query",
                            "description": "Just a boolean parameter.",
                            "schema": {
                                "type": "boolean"
                            },
                            "required": True
                        }
                    ],
                }
            }
        }
    }

    spec_mock_with_invalid_method = {
        "paths": {
            "/endpoint": {
                "brew": {}  # the data is irrelevant as is should be rejected.
            }
        }
    }  # type: Dict[str, object]

    spec_mock_using_object = {
        "paths": {
            "/endpoint": {
                "get": {
                    "description": "Get some info.",
                    "parameters": [
                        {
                            "name": "param1",
                            "in": "path",
                            "description": "An object",
                            "schema": {
                                "type": "object"
                            },
                            "example": {
                                "key": "value"
                            },
                            "required": True
                        }
                    ]
                }
            }
        }
    }

    spec_mock_using_object_without_example = {
        "paths": {
            "/endpoint": {
                "get": {
                    "description": "Get some info.",
                    "parameters": [
                        {
                            "name": "param1",
                            "in": "path",
                            "description": "An object",
                            "schema": {
                                "type": "object"
                            },
                            "required": True
                        }
                    ]
                }
            }
        }
    }

    spec_mock_using_array_without_example = {
        "paths": {
            "/endpoint": {
                "get": {
                    "description": "Get some info.",
                    "parameters": [
                        {
                            "name": "param1",
                            "in": "path",
                            "description": "An array",
                            "schema": {
                                "type": "array"
                            },
                            "required": True
                        }
                    ]
                }
            }
        }
    }

    def curl_example(self, endpoint: str, method: str, *args: Any, **kwargs: Any) -> List[str]:
        return generate_curl_example(endpoint, method,
                                     "http://localhost:9991/api", *args, **kwargs)

    def test_generate_and_render_curl_example(self) -> None:
        generated_curl_example = self.curl_example("/get_stream_id", "GET")
        expected_curl_example = [
            "```curl",
            "curl -sSX GET -G http://localhost:9991/api/v1/get_stream_id \\",
            "    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \\",
            "    -d 'stream=Denmark'",
            "```"
        ]
        self.assertEqual(generated_curl_example, expected_curl_example)

    def test_generate_and_render_curl_example_with_nonexistant_endpoints(self) -> None:
        with self.assertRaises(KeyError):
            self.curl_example("/mark_this_stream_as_read", "POST")
        with self.assertRaises(KeyError):
            self.curl_example("/mark_stream_as_read", "GET")

    def test_generate_and_render_curl_without_auth(self) -> None:
        generated_curl_example = self.curl_example("/dev_fetch_api_key", "POST")
        expected_curl_example = [
            "```curl",
            "curl -sSX POST http://localhost:9991/api/v1/dev_fetch_api_key \\",
            "    -d 'username=iago@zulip.com'",
            "```"
        ]
        self.assertEqual(generated_curl_example, expected_curl_example)

    @patch("zerver.lib.openapi.OpenAPISpec.spec")
    def test_generate_and_render_curl_with_default_examples(self, spec_mock: MagicMock) -> None:
        spec_mock.return_value = self.spec_mock_without_examples
        generated_curl_example = self.curl_example("/mark_stream_as_read", "POST")
        expected_curl_example = [
            "```curl",
            "curl -sSX POST http://localhost:9991/api/v1/mark_stream_as_read \\",
            "    -d 'stream_id=1' \\",
            "    -d 'bool_param=false'",
            "```"
        ]
        self.assertEqual(generated_curl_example, expected_curl_example)

    @patch("zerver.lib.openapi.OpenAPISpec.spec")
    def test_generate_and_render_curl_with_invalid_method(self, spec_mock: MagicMock) -> None:
        spec_mock.return_value = self.spec_mock_with_invalid_method
        with self.assertRaises(ValueError):
            self.curl_example("/endpoint", "BREW")  # see: HTCPCP

    def test_generate_and_render_curl_with_array_example(self) -> None:
        generated_curl_example = self.curl_example("/messages", "GET")
        expected_curl_example = [
            '```curl',
            'curl -sSX GET -G http://localhost:9991/api/v1/messages \\',
            '    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \\',
            "    -d 'anchor=42' \\",
            "    -d 'use_first_unread_anchor=true' \\",
            "    -d 'num_before=4' \\",
            "    -d 'num_after=8' \\",
            '    --data-urlencode narrow=\'[{"operand": "Denmark", "operator": "stream"}]\' \\',
            "    -d 'client_gravatar=true' \\",
            "    -d 'apply_markdown=false'",
            '```'
        ]
        self.assertEqual(generated_curl_example, expected_curl_example)

    @patch("zerver.lib.openapi.OpenAPISpec.spec")
    def test_generate_and_render_curl_with_object(self, spec_mock: MagicMock) -> None:
        spec_mock.return_value = self.spec_mock_using_object
        generated_curl_example = self.curl_example("/endpoint", "GET")
        expected_curl_example = [
            '```curl',
            'curl -sSX GET -G http://localhost:9991/api/v1/endpoint \\',
            '    --data-urlencode param1=\'{"key": "value"}\'',
            '```'
        ]
        self.assertEqual(generated_curl_example, expected_curl_example)

    @patch("zerver.lib.openapi.OpenAPISpec.spec")
    def test_generate_and_render_curl_with_object_without_example(self, spec_mock: MagicMock) -> None:
        spec_mock.return_value = self.spec_mock_using_object_without_example
        with self.assertRaises(ValueError):
            self.curl_example("/endpoint", "GET")

    @patch("zerver.lib.openapi.OpenAPISpec.spec")
    def test_generate_and_render_curl_with_array_without_example(self, spec_mock: MagicMock) -> None:
        spec_mock.return_value = self.spec_mock_using_array_without_example
        with self.assertRaises(ValueError):
            self.curl_example("/endpoint", "GET")

    def test_generate_and_render_curl_wrapper(self) -> None:
        generated_curl_example = render_curl_example("/get_stream_id:GET:email:key",
                                                     api_url="https://zulip.example.com/api")
        expected_curl_example = [
            "```curl",
            "curl -sSX GET -G https://zulip.example.com/api/v1/get_stream_id \\",
            "    -u email:key \\",
            "    -d 'stream=Denmark'",
            "```"
        ]
        self.assertEqual(generated_curl_example, expected_curl_example)

    def test_generate_and_render_curl_example_with_excludes(self) -> None:
        generated_curl_example = self.curl_example("/messages", "GET",
                                                   exclude=["client_gravatar", "apply_markdown"])
        expected_curl_example = [
            '```curl',
            'curl -sSX GET -G http://localhost:9991/api/v1/messages \\',
            '    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \\',
            "    -d 'anchor=42' \\",
            "    -d 'use_first_unread_anchor=true' \\",
            "    -d 'num_before=4' \\",
            "    -d 'num_after=8' \\",
            '    --data-urlencode narrow=\'[{"operand": "Denmark", "operator": "stream"}]\'',
            '```'
        ]
        self.assertEqual(generated_curl_example, expected_curl_example)
