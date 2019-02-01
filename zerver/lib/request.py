# When adding new functions/classes to this file, you need to also add
# their types to request.pyi in this directory (a mypy stubs file that
# we use to ensure mypy does correct type inference with REQ, which it
# can't do by default due to the dynamic nature of REQ).
#
# Because request.pyi exists, the type annotations in this file are
# mostly not processed by mypy.
from functools import wraps
import ujson

from django.utils.translation import ugettext as _

from zerver.lib.exceptions import JsonableError, ErrorCode, \
    InvalidJSONError
from zerver.lib.types import ViewFuncT

from django.http import HttpRequest, HttpResponse

from typing import Any, Callable, List, Optional, Type

class RequestConfusingParmsError(JsonableError):
    code = ErrorCode.REQUEST_CONFUSING_VAR
    data_fields = ['var_name1', 'var_name2']

    def __init__(self, var_name1: str, var_name2: str) -> None:
        self.var_name1 = var_name1  # type: str
        self.var_name2 = var_name2  # type: str

    @staticmethod
    def msg_format() -> str:
        return _("Can't decide between '{var_name1}' and '{var_name2}' arguments")

class RequestVariableMissingError(JsonableError):
    code = ErrorCode.REQUEST_VARIABLE_MISSING
    data_fields = ['var_name']

    def __init__(self, var_name: str) -> None:
        self.var_name = var_name  # type: str

    @staticmethod
    def msg_format() -> str:
        return _("Missing '{var_name}' argument")

class RequestVariableConversionError(JsonableError):
    code = ErrorCode.REQUEST_VARIABLE_INVALID
    data_fields = ['var_name', 'bad_value']

    def __init__(self, var_name: str, bad_value: Any) -> None:
        self.var_name = var_name  # type: str
        self.bad_value = bad_value

    @staticmethod
    def msg_format() -> str:
        return _("Bad value for '{var_name}': {bad_value}")

# Used in conjunction with @has_request_variables, below
class REQ:
    # NotSpecified is a sentinel value for determining whether a
    # default value was specified for a request variable.  We can't
    # use None because that could be a valid, user-specified default
    class _NotSpecified:
        pass
    NotSpecified = _NotSpecified()

    def __init__(self, whence: str=None, *, converter: Callable[[Any], Any]=None,
                 default: Any=NotSpecified, validator: Callable[[Any], Any]=None,
                 str_validator: Callable[[Any], Any]=None,
                 argument_type: str=None, type: Type=None,
                 aliases: Optional[List[str]]=None) -> None:
        """whence: the name of the request variable that should be used
        for this parameter.  Defaults to a request variable of the
        same name as the parameter.

        converter: a function that takes a string and returns a new
        value.  If specified, this will be called on the request
        variable value before passing to the function

        default: a value to be used for the argument if the parameter
        is missing in the request

        validator: similar to converter, but takes an already parsed JSON
        data structure.  If specified, we will parse the JSON request
        variable value before passing to the function

        str_validator: Like validator, but doesn't parse JSON first.

        argument_type: pass 'body' to extract the parsed JSON
        corresponding to the request body

        type: a hint to typing (using mypy) what the type of this parameter is.
        Currently only typically necessary if default=None and the type cannot
        be inferred in another way (eg. via converter).

        aliases: alternate names for the POST var
        """

        self.post_var_name = whence
        self.func_var_name = None  # type: str
        self.converter = converter
        self.validator = validator
        self.str_validator = str_validator
        self.default = default
        self.argument_type = argument_type
        self.aliases = aliases

        if converter and (validator or str_validator):
            # Not user-facing, so shouldn't be tagged for translation
            raise AssertionError('converter and validator are mutually exclusive')
        if validator and str_validator:
            # Not user-facing, so shouldn't be tagged for translation
            raise AssertionError('validator and str_validator are mutually exclusive')

# Extracts variables from the request object and passes them as
# named function arguments.  The request object must be the first
# argument to the function.
#
# To use, assign a function parameter a default value that is an
# instance of the REQ class.  That parameter will then be automatically
# populated from the HTTP request.  The request object must be the
# first argument to the decorated function.
#
# This should generally be the innermost (syntactically bottommost)
# decorator applied to a view, since other decorators won't preserve
# the default parameter values used by has_request_variables.
#
# Note that this can't be used in helper functions which are not
# expected to call json_error or json_success, as it uses json_error
# internally when it encounters an error
def has_request_variables(view_func: ViewFuncT) -> ViewFuncT:
    num_params = view_func.__code__.co_argcount
    if view_func.__defaults__ is None:
        num_default_params = 0
    else:
        num_default_params = len(view_func.__defaults__)
    default_param_names = view_func.__code__.co_varnames[num_params - num_default_params:]
    default_param_values = view_func.__defaults__
    if default_param_values is None:
        default_param_values = []

    post_params = []

    for (name, value) in zip(default_param_names, default_param_values):
        if isinstance(value, REQ):
            value.func_var_name = name
            if value.post_var_name is None:
                value.post_var_name = name
            post_params.append(value)

    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        for param in post_params:
            if param.func_var_name in kwargs:
                continue

            if param.argument_type == 'body':
                try:
                    val = ujson.loads(request.body)
                except ValueError:
                    raise InvalidJSONError(_("Malformed JSON"))
                kwargs[param.func_var_name] = val
                continue
            elif param.argument_type is not None:
                # This is a view bug, not a user error, and thus should throw a 500.
                raise Exception(_("Invalid argument type"))

            post_var_names = [param.post_var_name]
            if param.aliases:
                post_var_names += param.aliases

            default_assigned = False

            post_var_name = None  # type: Optional[str]

            query_params = request.GET.copy()
            query_params.update(request.POST)

            for req_var in post_var_names:
                try:
                    val = query_params[req_var]
                except KeyError:
                    continue
                if post_var_name is not None:
                    raise RequestConfusingParmsError(post_var_name, req_var)
                post_var_name = req_var

            if post_var_name is None:
                post_var_name = param.post_var_name
                if param.default is REQ.NotSpecified:
                    raise RequestVariableMissingError(post_var_name)
                val = param.default
                default_assigned = True

            if param.converter is not None and not default_assigned:
                try:
                    val = param.converter(val)
                except JsonableError:
                    raise
                except Exception:
                    raise RequestVariableConversionError(post_var_name, val)

            # Validators are like converters, but they don't handle JSON parsing; we do.
            if param.validator is not None and not default_assigned:
                try:
                    val = ujson.loads(val)
                except Exception:
                    raise JsonableError(_('Argument "%s" is not valid JSON.') % (post_var_name,))

                error = param.validator(post_var_name, val)
                if error:
                    raise JsonableError(error)

            # str_validators is like validator, but for direct strings (no JSON parsing).
            if param.str_validator is not None and not default_assigned:
                error = param.str_validator(post_var_name, val)
                if error:
                    raise JsonableError(error)

            kwargs[param.func_var_name] = val

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func
