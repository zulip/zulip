# This mypy stubs file ensures that mypy can correctly analyze REQ.
from typing import Any, Callable, Text, TypeVar
from django.http import HttpResponse

from zerver.lib.exceptions import JsonableError as JsonableError

ViewFuncT = TypeVar('ViewFuncT', bound=Callable[..., HttpResponse])

class RequestVariableMissingError(JsonableError): ...
class RequestVariableConversionError(JsonableError): ...

def REQ(*args: Any, **kwargs: Any) -> Any: ...

def has_request_variables(view_func: ViewFuncT) -> ViewFuncT: ...
