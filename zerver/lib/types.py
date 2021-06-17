from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

from django.http import HttpResponse
from django.utils.functional import Promise
from typing_extensions import TypedDict

ViewFuncT = TypeVar("ViewFuncT", bound=Callable[..., HttpResponse])

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

FieldElement = Tuple[int, Promise, Validator[Union[int, str, List[int]]], Callable[[Any], Any], str]
ExtendedFieldElement = Tuple[int, Promise, ExtendedValidator, Callable[[Any], Any], str]
UserFieldElement = Tuple[int, Promise, RealmUserValidator, Callable[[Any], Any], str]

ProfileFieldData = Dict[str, Union[Dict[str, str], str]]


class UserDisplayRecipient(TypedDict):
    email: str
    full_name: str
    id: int
    is_mirror_dummy: bool


DisplayRecipientT = Union[str, List[UserDisplayRecipient]]


class LinkifierDict(TypedDict):
    pattern: str
    url_format: str
    render_format: str
    id: int


class SAMLIdPConfigDict(TypedDict, total=False):
    entity_id: str
    url: str
    attr_user_permanent_id: str
    attr_first_name: str
    attr_last_name: str
    attr_username: str
    attr_email: str
    attr_org_membership: str
    display_name: str
    display_icon: str
    limit_to_subdomains: List[str]
    extra_attrs: List[str]
    x509cert: str
    x509cert_path: str


class FullNameInfo(TypedDict):
    id: int
    email: str
    full_name: str
