from typing import Any, Dict, List, Optional, Sequence

import orjson
from django.http import HttpRequest, HttpResponse

from zerver.lib.exceptions import JsonableError
from zerver.lib.request import (
    REQ,
    RequestConfusingParamsError,
    RequestVariableConversionError,
    RequestVariableMissingError,
    has_request_variables,
)
from zerver.lib.response import MutableJsonResponse, json_response, json_success
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.lib.validator import check_bool, check_int, check_list, check_string_fixed_length


class REQTestCase(ZulipTestCase):
    def test_REQ_aliases(self) -> None:
        @has_request_variables
        def double(
            request: HttpRequest,
            x: int = REQ(whence="number", aliases=["x", "n"], json_validator=check_int),
        ) -> HttpResponse:
            return json_response(data={"number": x + x})

        request = HostRequestMock(post_data={"bogus": "5555"})
        with self.assertRaises(RequestVariableMissingError):
            double(request)

        request = HostRequestMock(post_data={"number": "3"})
        self.assertEqual(orjson.loads(double(request).content).get("number"), 6)

        request = HostRequestMock(post_data={"x": "4"})
        self.assertEqual(orjson.loads(double(request).content).get("number"), 8)

        request = HostRequestMock(post_data={"n": "5"})
        self.assertEqual(orjson.loads(double(request).content).get("number"), 10)

        request = HostRequestMock(post_data={"number": "6", "x": "7"})
        with self.assertRaises(RequestConfusingParamsError) as cm:
            double(request)
        self.assertEqual(str(cm.exception), "Can't decide between 'number' and 'x' arguments")

    def test_REQ_converter(self) -> None:
        def my_converter(var_name: str, data: str) -> List[int]:
            lst = orjson.loads(data)
            if not isinstance(lst, list):
                raise ValueError("not a list")
            if 13 in lst:
                raise JsonableError("13 is an unlucky number!")
            return [int(elem) for elem in lst]

        @has_request_variables
        def get_total(
            request: HttpRequest, numbers: Sequence[int] = REQ(converter=my_converter)
        ) -> HttpResponse:
            return json_response(data={"number": sum(numbers)})

        request = HostRequestMock()

        with self.assertRaises(RequestVariableMissingError):
            get_total(request)

        request.POST["numbers"] = "bad_value"
        with self.assertRaises(RequestVariableConversionError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), "Bad value for 'numbers': bad_value")

        request.POST["numbers"] = orjson.dumps("{fun: unfun}").decode()
        with self.assertRaises(JsonableError) as jsonable_error_cm:
            get_total(request)
        self.assertEqual(
            str(jsonable_error_cm.exception), "Bad value for 'numbers': \"{fun: unfun}\""
        )

        request.POST["numbers"] = orjson.dumps([2, 3, 5, 8, 13, 21]).decode()
        with self.assertRaises(JsonableError) as jsonable_error_cm:
            get_total(request)
        self.assertEqual(str(jsonable_error_cm.exception), "13 is an unlucky number!")

        request.POST["numbers"] = orjson.dumps([1, 2, 3, 4, 5, 6]).decode()
        result = get_total(request)
        self.assertEqual(orjson.loads(result.content).get("number"), 21)

    def test_REQ_validator(self) -> None:
        @has_request_variables
        def get_total(
            request: HttpRequest, numbers: Sequence[int] = REQ(json_validator=check_list(check_int))
        ) -> HttpResponse:
            return json_response(data={"number": sum(numbers)})

        request = HostRequestMock()

        with self.assertRaises(RequestVariableMissingError):
            get_total(request)

        request.POST["numbers"] = "bad_value"
        with self.assertRaises(JsonableError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), 'Argument "numbers" is not valid JSON.')

        request.POST["numbers"] = orjson.dumps([1, 2, "what?", 4, 5, 6]).decode()
        with self.assertRaises(JsonableError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), "numbers[2] is not an integer")

        request.POST["numbers"] = orjson.dumps([1, 2, 3, 4, 5, 6]).decode()
        result = get_total(request)
        self.assertEqual(orjson.loads(result.content).get("number"), 21)

    def test_REQ_str_validator(self) -> None:
        @has_request_variables
        def get_middle_characters(
            request: HttpRequest, value: str = REQ(str_validator=check_string_fixed_length(5))
        ) -> HttpResponse:
            return json_response(data={"value": value[1:-1]})

        request = HostRequestMock()

        with self.assertRaises(RequestVariableMissingError):
            get_middle_characters(request)

        request.POST["value"] = "long_value"
        with self.assertRaises(JsonableError) as cm:
            get_middle_characters(request)
        self.assertEqual(str(cm.exception), "value has incorrect length 10; should be 5")

        request.POST["value"] = "valid"
        result = get_middle_characters(request)
        self.assertEqual(orjson.loads(result.content).get("value"), "ali")

    def test_REQ_argument_type(self) -> None:
        @has_request_variables
        def get_payload(
            request: HttpRequest, payload: Dict[str, Any] = REQ(argument_type="body")
        ) -> HttpResponse:
            return json_response(data={"payload": payload})

        request = HostRequestMock()
        request.body = b"\xde\xad\xbe\xef"
        with self.assertRaises(JsonableError) as cm:
            get_payload(request)
        self.assertEqual(str(cm.exception), "Malformed payload")

        request = HostRequestMock()
        request.body = b"notjson"
        with self.assertRaises(JsonableError) as cm:
            get_payload(request)
        self.assertEqual(str(cm.exception), "Malformed JSON")

        request.body = b'{"a": "b"}'
        self.assertEqual(orjson.loads(get_payload(request).content).get("payload"), {"a": "b"})


class TestIgnoredParametersUnsupported(ZulipTestCase):
    def test_ignored_parameters_json_success(self) -> None:
        @has_request_variables
        def test_view(
            request: HttpRequest,
            name: Optional[str] = REQ(default=None),
            age: Optional[int] = 0,
        ) -> HttpResponse:
            return json_success(request)

        # ignored parameter (not processed through REQ)
        request = HostRequestMock()
        request.POST["age"] = "30"
        result = test_view(request)
        self.assert_json_success(result, ignored_parameters=["age"])

        # valid parameter, returns no ignored parameters
        request = HostRequestMock()
        request.POST["name"] = "Hamlet"
        result = test_view(request)
        self.assert_json_success(result)

        # both valid and ignored parameters
        request = HostRequestMock()
        request.POST["name"] = "Hamlet"
        request.POST["age"] = "30"
        request.POST["location"] = "Denmark"
        request.POST["dies"] = "True"
        result = test_view(request)
        ignored_parameters = ["age", "dies", "location"]
        json_result = self.assert_json_success(result, ignored_parameters=ignored_parameters)
        # check that results are sorted
        self.assertEqual(json_result["ignored_parameters_unsupported"], ignored_parameters)

    # Because `has_request_variables` can be called multiple times on a request,
    # here we test that parameters processed in separate, nested function calls
    # are not returned in the `ignored parameters_unsupported` array.
    def test_nested_has_request_variables(self) -> None:
        @has_request_variables
        def not_view_function_A(
            request: HttpRequest, dies: bool = REQ(json_validator=check_bool)
        ) -> None:
            return

        @has_request_variables
        def not_view_function_B(
            request: HttpRequest, married: bool = REQ(json_validator=check_bool)
        ) -> None:
            return

        @has_request_variables
        def view_B(request: HttpRequest, name: str = REQ()) -> MutableJsonResponse:
            return json_success(request)

        @has_request_variables
        def view_A(
            request: HttpRequest, age: int = REQ(json_validator=check_int)
        ) -> MutableJsonResponse:
            not_view_function_A(request)
            response = view_B(request)
            not_view_function_B(request)
            return response

        # valid parameters, returns no ignored parameters
        post_data = {"name": "Hamlet", "age": "30", "dies": "true", "married": "false"}
        request = HostRequestMock(post_data)

        result = view_A(request)
        result_iter = list(iter(result))
        self.assertEqual(result_iter, [b'{"result":"success","msg":""}\n'])
        self.assert_json_success(result)

        # ignored parameter
        post_data = {
            "name": "Hamlet",
            "age": "30",
            "dies": "true",
            "married": "false",
            "author": "William Shakespeare",
        }
        request = HostRequestMock(post_data)

        result = view_A(request)
        result_iter = list(iter(result))
        self.assertEqual(
            result_iter,
            [b'{"result":"success","msg":"","ignored_parameters_unsupported":["author"]}\n'],
        )
        self.assert_json_success(result, ignored_parameters=["author"])
