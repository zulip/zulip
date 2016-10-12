from typing import Any, Callable, TypeVar
from django.http import HttpResponse

ViewFuncT = TypeVar('ViewFuncT', bound=Callable[..., HttpResponse])

class JsonableError(Exception):
    error = ...  # type: Any
    def to_json_error_msg(self) -> Any: ...

class RequestVariableMissingError(JsonableError): ...

def REQ(*args: Any, **kwargs: Any) -> Any: ...

def has_request_variables(view_func: ViewFuncT) -> ViewFuncT: ...
