import inspect
import json
from dataclasses import dataclass
from enum import Enum, auto
from functools import wraps
from typing import Callable, Generic, List, Optional, Sequence, Tuple, Type, TypeVar, Union

from django.http import HttpRequest
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints, TypeAdapter, ValidationError
from typing_extensions import (
    Annotated,
    Concatenate,
    ParamSpec,
    TypeAlias,
    get_args,
    get_origin,
    get_type_hints,
)

from zerver.lib.exceptions import ApiParamValidationError, JsonableError
from zerver.lib.request import (
    _REQ,
    RequestConfusingParamsError,
    RequestNotes,
    RequestVariableMissingError,
    arguments_map,
)
from zerver.lib.response import MutableJsonResponse

T = TypeVar("T")
ParamT = ParamSpec("ParamT")
ReturnT = TypeVar("ReturnT")


class DocumentationStatus(Enum):
    DOCUMENTED = auto()
    INTENTIONALLY_UNDOCUMENTED = auto()
    DOCUMENTATION_PENDING = auto()


DOCUMENTED = DocumentationStatus.DOCUMENTED
INTENTIONALLY_UNDOCUMENTED = DocumentationStatus.INTENTIONALLY_UNDOCUMENTED
DOCUMENTATION_PENDING = DocumentationStatus.DOCUMENTATION_PENDING


@dataclass(frozen=True)
class ApiParamConfig:
    """The metadata associated with a view function parameter as an annotation
    to configure how the typed_endpoint decorator should process it.

    It should be used with Annotated as the type annotation of a parameter
    in a @typed_endpoint-decorated function:
    ```
    @typed_endpoint
    def view(
        request: HttpRequest,
        *,
        flag_value: Annotated[Json[bool], ApiParamConfig(
            whence="flag",
            documentation_status=INTENTIONALLY_UNDOCUMENTED,
        )]
    ) -> HttpResponse:
        ...
    ```

    For a parameter that is not annotated with ApiParamConfig, typed_endpoint
    will construct a configuration using the defaults.

    whence:
    The name of the request variable that should be used for this parameter.
    If None, it is set to the name of the function parameter.

    path_only:
    Used for parameters included in the URL.

    argument_type_is_body:
    When set to true, the value of the parameter will be extracted from the
    request body instead of a single query parameter.

    documentation_status:
    The OpenAPI documentation status of this parameter. Unless it is set to
    INTENTIONALLY_UNDOCUMENTED or DOCUMENTATION_PENDING, the test suite is
    configured to raise an error when its documentation cannot be found.

    aliases:
    The names allowed for the request variable other than that specified with
    "whence".
    """

    whence: Optional[str] = None
    path_only: bool = False
    argument_type_is_body: bool = False
    documentation_status: DocumentationStatus = DOCUMENTED
    aliases: Tuple[str, ...] = ()


# TypeAliases for common Annotated types

# Commonly used for webhook views, where the payload has a content type of
# application/json. It reads the data from request body and parse it from JSON.
JsonBodyPayload: TypeAlias = Annotated[Json[T], ApiParamConfig(argument_type_is_body=True)]
# A shorthand to declare path only variables that should not be parsed from the
# request by the @typed_endpoint decorator.
PathOnly: TypeAlias = Annotated[T, ApiParamConfig(path_only=True)]
OptionalTopic: TypeAlias = Annotated[
    Optional[str],
    StringConstraints(strip_whitespace=True),
    ApiParamConfig(whence="topic", aliases=("subject",)),
]
ApnsAppId: TypeAlias = Annotated[str, StringConstraints(pattern="^[.a-zA-Z0-9-]+$")]

# Reusable annotation metadata for Annotated types

# This disallows strings of length 0 after stripping.
# Example usage: Annotated[T, StringRequiredConstraint()]
RequiredStringConstraint = lambda: StringConstraints(strip_whitespace=True, min_length=1)

# Implementation


class _NotSpecified:
    pass


NotSpecified = _NotSpecified()


# For performance reasons, attributes needed from ApiParamConfig are copied to
# FuncParam. We should use slotted dataclass once the entire codebase is
# switched to Python 3.10+
@dataclass(frozen=True)
class FuncParam(Generic[T]):
    # Default value of the parameter.
    default: Union[T, _NotSpecified]
    # Name of the function parameter as defined in the original function.
    param_name: str
    # Inspected the underlying type of the parameter by unwrapping the Annotated
    # type if there is one.
    param_type: Type[T]
    # The Pydantic TypeAdapter used to parse arbitrary input to the desired type.
    # We store it on the FuncParam object as soon as the view function is
    # decorated because it is expensive to construct.
    # See also: https://docs.pydantic.dev/latest/usage/type_adapter/
    type_adapter: TypeAdapter[T]

    # The following group of attributes are computed from the ApiParamConfig
    # annotation associated with this param:
    # Name of the corresponding variable in the request data to look
    # for. When argument_type_is_body is True, this is set to "request".
    aliases: Tuple[str, ...]
    argument_type_is_body: bool
    documentation_status: DocumentationStatus
    path_only: bool
    request_var_name: str


@dataclass(frozen=True)
class ViewFuncInfo:
    view_func_full_name: str
    parameters: Sequence[FuncParam[object]]


def is_annotated(type_annotation: Type[object]) -> bool:
    origin = get_origin(type_annotation)
    return origin is Annotated


def is_optional(type_annotation: Type[object]) -> bool:
    origin = get_origin(type_annotation)
    type_args = get_args(type_annotation)
    return origin is Union and type(None) in type_args and len(type_args) == 2


API_PARAM_CONFIG_USAGE_HINT = f"""
    Detected incorrect usage of Annotated types for parameter {{param_name}}!
    Check the placement of the {ApiParamConfig.__name__} object in the type annotation:

    {{param_name}}: {{param_type}}

    The Annotated[T, ...] type annotation containing the
    {ApiParamConfig.__name__} object should not be nested inside another type.

    Correct examples:

    # Using Optional inside Annotated
    param: Annotated[Optional[int], ApiParamConfig(...)]
    param: Annotated[Optional[int], ApiParamConfig(...)]] = None

    # Not using Optional when the default is not None
    param: Annotated[int, ApiParamConfig(...)]

    Incorrect examples:

    # Nesting Annotated inside Optional
    param: Optional[Annotated[int, ApiParamConfig(...)]]
    param: Optional[Annotated[int, ApiParamConfig(...)]] = None

    # Nesting the Annotated type carrying ApiParamConfig inside other types like Union
    param: Union[str, Annotated[int, ApiParamConfig(...)]]
"""


def parse_single_parameter(
    param_name: str, param_type: Type[T], parameter: inspect.Parameter
) -> FuncParam[T]:
    param_default = parameter.default
    # inspect._empty is the internal type used by inspect to indicate not
    # specified defaults.
    if param_default is inspect._empty:
        param_default = NotSpecified

    # Defaulting a value to None automatically wraps the type annotation with
    # Optional. We explicitly unwrap it for the case of Annotated, which
    # otherwise causes undesired behaviors that the annotated metadata gets
    # lost. This is fixed in Python 3.11:
    # https://github.com/python/cpython/issues/90353
    if param_default is None and is_optional(param_type):
        type_args = get_args(param_type)
        inner_type = type_args[0] if type_args[1] is type(None) else type_args[1]
        if is_annotated(inner_type):
            annotated_type, *annotations = get_args(inner_type)
            has_api_param_config = any(
                isinstance(annotation, ApiParamConfig) for annotation in annotations
            )
            # This prohibits the use of `Optional[Annotated[T, ApiParamConfig(...)]] = None`
            # and encourages `Annotated[Optional[T], ApiParamConfig(...)] = None`
            # to avoid confusion when the parameter metadata is unintentionally nested.
            assert not has_api_param_config or is_optional(
                annotated_type
            ), API_PARAM_CONFIG_USAGE_HINT.format(param_name=param_name, param_type=param_type)
            param_type = inner_type

    param_config: Optional[ApiParamConfig] = None
    if is_annotated(param_type):
        # The first type is the underlying type of the parameter, the rest are
        # metadata attached to Annotated. Note that we do not transform
        # param_type to its underlying type because the Annotated metadata might
        # still be needed by other parties like Pydantic.
        ignored_type, *annotations = get_args(param_type)
        for annotation in annotations:
            if not isinstance(annotation, ApiParamConfig):
                continue
            assert param_config is None, "ApiParamConfig can only be defined once per parameter"
            param_config = annotation
    else:
        # When no parameter configuration is found, assert that there is none
        # nested somewhere in a Union type to avoid silently ignoring it. If it
        # does present in the stringified parameter type, it is very likely a
        # programming error.
        assert ApiParamConfig.__name__ not in str(param_type), API_PARAM_CONFIG_USAGE_HINT.format(
            param_name=param_name, param_type=param_type
        )
    # If param_config is still None at this point, we could not find an instance
    # of it in the type annotation of the function parameter. In this case, we
    # fallback to the defaults by constructing ApiParamConfig here.
    # This is common for simple parameters of type str, Json[int] and etc.
    if param_config is None:
        param_config = ApiParamConfig()

    # Metadata defines a validator making sure that argument_type_is_body is
    # incompatible with whence.
    if param_config.argument_type_is_body:
        request_var_name = "request"
    else:
        request_var_name = param_config.whence if param_config.whence is not None else param_name

    return FuncParam(
        default=param_default,
        param_name=param_name,
        param_type=param_type,
        type_adapter=TypeAdapter(param_type),
        aliases=param_config.aliases,
        argument_type_is_body=param_config.argument_type_is_body,
        documentation_status=param_config.documentation_status,
        path_only=param_config.path_only,
        request_var_name=request_var_name,
    )


def parse_view_func_signature(
    view_func: Callable[Concatenate[HttpRequest, ParamT], object],
) -> ViewFuncInfo:
    """This is responsible for inspecting the function signature and getting the
    metadata from the parameters. We want to keep this function as pure as
    possible not leaking side effects to the global state. Side effects should
    be executed separately after the ViewFuncInfo is returned.
    """
    type_hints = get_type_hints(view_func, include_extras=True)
    parameters = inspect.signature(view_func).parameters
    view_func_full_name = f"{view_func.__module__}.{view_func.__name__}"

    process_parameters: List[FuncParam[object]] = []

    for param_name, parameter in parameters.items():
        assert param_name in type_hints
        if parameter.kind != inspect.Parameter.KEYWORD_ONLY:
            continue
        param_info = parse_single_parameter(
            param_name=param_name, param_type=type_hints[param_name], parameter=parameter
        )
        process_parameters.append(param_info)

    return ViewFuncInfo(
        view_func_full_name=view_func_full_name,
        parameters=process_parameters,
    )


# TODO: To get coverage data, we should switch to match-case syntax when we
# upgrade to Python 3.10.
# This should be sorted alphabetically.
ERROR_TEMPLATES = {
    "bool_parsing": _("{var_name} is not a boolean"),
    "bool_type": _("{var_name} is not a boolean"),
    "datetime_parsing": _("{var_name} is not a date"),
    "datetime_type": _("{var_name} is not a date"),
    "dict_type": _("{var_name} is not a dict"),
    "extra_forbidden": _('Argument "{argument}" at {var_name} is unexpected'),
    "float_parsing": _("{var_name} is not a float"),
    "float_type": _("{var_name} is not a float"),
    "greater_than": _("{var_name} is too small"),
    "int_parsing": _("{var_name} is not an integer"),
    "int_type": _("{var_name} is not an integer"),
    "json_invalid": _("{var_name} is not valid JSON"),
    "json_type": _("{var_name} is not valid JSON"),
    "less_than": _("{var_name} is too large"),
    "list_type": _("{var_name} is not a list"),
    "literal_error": _("Invalid {var_name}"),
    "string_too_long": _("{var_name} is too long (limit: {max_length} characters)"),
    "string_too_short": _("{var_name} is too short."),
    "string_type": _("{var_name} is not a string"),
    "unexpected_keyword_argument": _('Argument "{argument}" at {var_name} is unexpected'),
    "string_pattern_mismatch": _("{var_name} has invalid format"),
    "string_fixed_length": _("{var_name} is not length {length}"),
}


def parse_value_for_parameter(parameter: FuncParam[T], value: object) -> T:
    try:
        return parameter.type_adapter.validate_python(value, strict=True)
    except ValidationError as exc:
        # If the validation fails, it is possible to get multiple errors from
        # Pydantic. We only send the first error back to the client.
        # See also on ValidationError:
        # https://docs.pydantic.dev/latest/errors/validation_errors/
        error = exc.errors()[0]
        # We require all Pydantic raised error types that we expect to be
        # explicitly handled here. The end result should either be a 400
        # error with an translated message or an internal server error.
        error_template = ERROR_TEMPLATES.get(error["type"])
        var_name = parameter.request_var_name + "".join(
            f"[{json.dumps(loc)}]" for loc in error["loc"]
        )
        context = {
            "var_name": var_name,
            **error.get("ctx", {}),
        }

        if error["type"] == "json_invalid" and parameter.argument_type_is_body:
            # argument_type_is_body is usually used by webhooks that do not
            # require a specific var_name for payload JSON decoding error.
            # We override it here.
            error_template = _("Malformed JSON")
        elif error["type"] in ("unexpected_keyword_argument", "extra_forbidden"):
            context["argument"] = error["loc"][-1]
        # This condition matches our StringRequiredConstraint
        elif error["type"] == "string_too_short" and error["ctx"].get("min_length") == 1:
            error_template = _("{var_name} cannot be blank")
        elif error["type"] == "value_error":
            context["msg"] = error["msg"]
            error_template = _("Invalid {var_name}: {msg}")

        assert error_template is not None, MISSING_ERROR_TEMPLATE.format(
            error_type=error["type"],
            url=error.get("url", "(documentation unavailable)"),
            error=json.dumps(error, indent=4),
        )
        raise ApiParamValidationError(error_template.format(**context), error["type"])


MISSING_ERROR_TEMPLATE = f"""
    Pydantic validation error of type "{{error_type}}" does not have the
    corresponding error message template or is not handled explicitly. We expect
    that every validation error is formatted into a client-facing error message.
    Consider adding this type to {__package__}.ERROR_TEMPLATES with the appropriate
    internationalized error message or handle it in {__package__}.{parse_value_for_parameter.__name__}.

    Documentation for "{{error_type}}" can be found at {{url}}.

    Error information:
{{error}}
"""


UNEXPECTEDLY_MISSING_KEYWORD_ONLY_PARAMETERS = """
Parameters expected to be parsed from the request should be defined as
keyword-only parameters, but there is no keyword-only parameter found in
{view_func_name}.

Example usage:

```
@typed_endpoint
def view(
    request: HttpRequest,
    *,
    flag_value: Annotated[Json[bool], ApiParamConfig(
        whence="flag", documentation_status=INTENTIONALLY_UNDOCUMENTED,
    )]
) -> HttpResponse:
    ...
```

This is likely a programming error. See https://peps.python.org/pep-3102/ for details on how
to correctly declare your parameters as keyword-only parameters.
Endpoints that do not accept parameters should use @typed_endpoint_without_parameters.
"""

UNEXPECTED_KEYWORD_ONLY_PARAMETERS = """
Unexpected keyword-only parameters found in {view_func_name}.
keyword-only parameters are treated as parameters to be parsed from the request,
but @typed_endpoint_without_parameters does not expect any.

Use @typed_endpoint instead.
"""


def typed_endpoint_without_parameters(
    view_func: Callable[Concatenate[HttpRequest, ParamT], ReturnT],
) -> Callable[Concatenate[HttpRequest, ParamT], ReturnT]:
    return typed_endpoint(view_func, expect_no_parameters=True)


def typed_endpoint(
    view_func: Callable[Concatenate[HttpRequest, ParamT], ReturnT],
    *,
    expect_no_parameters: bool = False,
) -> Callable[Concatenate[HttpRequest, ParamT], ReturnT]:
    # Extract all the type information from the view function.
    endpoint_info = parse_view_func_signature(view_func)
    if expect_no_parameters:
        assert len(endpoint_info.parameters) == 0, UNEXPECTED_KEYWORD_ONLY_PARAMETERS.format(
            view_func_name=endpoint_info.view_func_full_name
        )
    else:
        assert (
            len(endpoint_info.parameters) != 0
        ), UNEXPECTEDLY_MISSING_KEYWORD_ONLY_PARAMETERS.format(
            view_func_name=endpoint_info.view_func_full_name
        )
    for func_param in endpoint_info.parameters:
        assert not isinstance(
            func_param.default, _REQ
        ), f"Unexpected REQ for parameter {func_param.param_name}; REQ is incompatible with typed_endpoint"
        if func_param.path_only:
            assert (
                func_param.default is NotSpecified
            ), f"Path-only parameter {func_param.param_name} should not have a default value"
        # Record arguments that should be documented so that our
        # automated OpenAPI docs tests can compare these against the code.
        if (
            func_param.documentation_status is DocumentationStatus.DOCUMENTED
            and not func_param.path_only
        ):
            # TODO: Move arguments_map to here once zerver.lib.request does not
            # need it anymore.
            arguments_map[endpoint_info.view_func_full_name].append(func_param.request_var_name)

    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> ReturnT:
        request_notes = RequestNotes.get_notes(request)
        for parameter in endpoint_info.parameters:
            if parameter.path_only:
                # For path_only parameters, they should already have been passed via
                # the URL, so there's no need for us to do anything.
                #
                # TODO: Run validators for path_only parameters for NewType.
                assert (
                    parameter.param_name in kwargs
                ), f"Path-only variable {parameter.param_name} should be passed already"
            if parameter.param_name in kwargs:
                # Skip parameters that are already supplied by the caller.
                continue

            # Extract the value to parse from the request body if specified.
            if parameter.argument_type_is_body:
                try:
                    request_notes.processed_parameters.add(parameter.request_var_name)
                    kwargs[parameter.param_name] = parse_value_for_parameter(
                        parameter, request.body.decode(request.encoding or "utf-8")
                    )
                except UnicodeDecodeError:
                    raise JsonableError(_("Malformed payload"))
                # test_typed_endpoint.TestEndpoint.test_argument_type has
                # coverage of this, but coverage.py fails to recognize it for
                # some reason.
                continue  # nocoverage

            # Otherwise, try to find the matching request variable in one of the QueryDicts
            # This is a view bug, not a user error, and thus should throw a 500.
            possible_aliases = [parameter.request_var_name, *parameter.aliases]
            alias_used = None
            value_to_parse = None

            for current_alias in possible_aliases:
                if current_alias in request.POST:
                    value_to_parse = request.POST[current_alias]
                elif current_alias in request.GET:
                    value_to_parse = request.GET[current_alias]
                else:
                    # This is covered by
                    # test_typed_endpoint.TestEndpoint.test_aliases, but
                    # coverage.py fails to recognize this for some reason.
                    continue  # nocoverage
                if alias_used is not None:
                    raise RequestConfusingParamsError(alias_used, current_alias)
                alias_used = current_alias

            if alias_used is None:
                alias_used = parameter.request_var_name
                if parameter.default is NotSpecified:
                    raise RequestVariableMissingError(alias_used)
                # By skipping here, we leave it to Python to use the default value
                # of this parameter, because we cannot find the request variable in
                # the request.
                # This is tested test_typed_endpoint.TestEndpoint.test_json, but
                # coverage.py fails to recognize this for some reason.
                continue  # nocoverage

            # Note that value_to_parse comes from a QueryDict, so it has no chance
            # of having a user-provided None value.
            assert value_to_parse is not None
            request_notes.processed_parameters.add(alias_used)
            kwargs[parameter.param_name] = parse_value_for_parameter(parameter, value_to_parse)
        return_value = view_func(request, *args, **kwargs)

        if (
            isinstance(return_value, MutableJsonResponse)
            # TODO: Move is_webhook_view to the decorator
            and not request_notes.is_webhook_view
            # Implemented only for 200 responses.
            # TODO: Implement returning unsupported ignored parameters for 400
            # JSON error responses. This is complex because typed_endpoint can be
            # called multiple times, so when an error response is raised, there
            # may be supported parameters that have not yet been processed,
            # which could lead to inaccurate output.
            and 200 <= return_value.status_code < 300
        ):
            ignored_parameters = {*request.POST, *request.GET}.difference(
                request_notes.processed_parameters
            )

            # This will be called each time a function decorated with @typed_endpoint
            # returns a MutableJsonResponse with a success status_code. Because
            # a shared processed_parameters value is checked each time, the
            # value for the ignored_parameters_unsupported key is either
            # added/updated to the response data or it is removed in the case
            # that all of the request parameters have been processed.
            if ignored_parameters:
                return_value.get_data()["ignored_parameters_unsupported"] = sorted(
                    ignored_parameters
                )
            else:
                return_value.get_data().pop("ignored_parameters_unsupported", None)

        return return_value

    # TODO: Remove this once we replace has_request_variables with typed_endpoint.
    _wrapped_view_func.use_endpoint = True  # type: ignore[attr-defined] # Distinguish functions decorated with @typed_endpoint from those decorated with has_request_variables
    return _wrapped_view_func
