from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

from django.http import HttpResponse
from typing_extensions import TypedDict

ViewFuncT = TypeVar('ViewFuncT', bound=Callable[..., HttpResponse])

# See zerver/lib/validator.py for more details of Validators,
# including many examples
ResultT = TypeVar("ResultT")
Validator = Callable[[str, object], ResultT]
ExtendedValidator = Callable[[str, str, object], str]
RealmUserValidator = Callable[[int, object, bool], List[int]]

class ProfileDataElementBase(TypedDict):
    id: int
    name: str
    type: int
    hint: Optional[str]
    field_data: Optional[str]
    order: int

class ProfileDataElement(ProfileDataElementBase):
    value: str
    rendered_value: Optional[str]

ProfileData = List[ProfileDataElement]

FieldElement = Tuple[int, str, Validator[Union[int, str, List[int]]], Callable[[Any], Any], str]
ExtendedFieldElement = Tuple[int, str, ExtendedValidator, Callable[[Any], Any], str]
UserFieldElement = Tuple[int, str, RealmUserValidator, Callable[[Any], Any], str]

ProfileFieldData = Dict[str, Union[Dict[str, str], str]]

class UserDisplayRecipient(TypedDict):
    email: str
    full_name: str
    id: int
    is_mirror_dummy: bool
DisplayRecipientT = Union[str, List[UserDisplayRecipient]]
