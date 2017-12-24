# This mypy stubs file ensures that mypy can correctly analyze REQ.
#
# Note that here REQ is claimed to be a function, with a return type to match
# that of the parameter of which it is the default value, allowing type
# checking. However, in request.py, REQ is a class to enable the decorator to
# scan the parameter list for REQ objects and patch the parameters as the true
# types.

from typing import Any, Callable, Text, TypeVar, Optional, Union
from django.http import HttpResponse

from zerver.lib.exceptions import JsonableError as JsonableError

Validator = Callable[[str, Any], Optional[str]]

ResultT = TypeVar('ResultT')
ViewFuncT = TypeVar('ViewFuncT', bound=Callable[..., HttpResponse])

class RequestVariableMissingError(JsonableError): ...
class RequestVariableConversionError(JsonableError): ...

class _NotSpecified: ...
NotSpecified = _NotSpecified()

def REQ(whence: Optional[str] = None,
        *,
        converter: Optional[Callable[[str], ResultT]] = None,
        default: Union[_NotSpecified, ResultT] = NotSpecified,
        validator: Optional[Validator] = None,
        argument_type: Optional[str] = None) -> ResultT: ...

def has_request_variables(view_func: ViewFuncT) -> ViewFuncT: ...
