# This mypy stubs file ensures that mypy can correctly analyze REQ.
#
# Note that here REQ is claimed to be a function, with a return type to match
# that of the parameter of which it is the default value, allowing type
# checking. However, in request.py, REQ is a class to enable the decorator to
# scan the parameter list for REQ objects and patch the parameters as the true
# types.

from typing import Any, List, Callable, TypeVar, Optional, Union, Type
from zerver.lib.types import ViewFuncT, Validator, ExtractRecipients
from zerver.lib.exceptions import JsonableError as JsonableError

ResultT = TypeVar('ResultT')

class RequestConfusingParmsError(JsonableError): ...
class RequestVariableMissingError(JsonableError): ...
class RequestVariableConversionError(JsonableError): ...

class _NotSpecified: ...
NotSpecified = _NotSpecified()

def REQ(whence: Optional[str] = None,
        *,
        type: Type[ResultT] = Type[None],
        converter: Union[Optional[Callable[[str], ResultT]], ExtractRecipients] = None,
        default: Union[_NotSpecified, ResultT, None] = Optional[NotSpecified],
        validator: Optional[Validator] = None,
        str_validator: Optional[Validator] = None,
        argument_type: Optional[str] = None,
        aliases: Optional[List[str]] = None) -> ResultT: ...

def has_request_variables(view_func: ViewFuncT) -> ViewFuncT: ...
