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


ProfileDataElementValue = Union[str, List[int]]


class ProfileDataElementBase(TypedDict):
    id: int
    name: str
    type: int
    hint: Optional[str]
    field_data: Optional[str]
    order: int


class ProfileDataElement(ProfileDataElementBase):
    value: ProfileDataElementValue
    rendered_value: Optional[str]


ProfileData = List[ProfileDataElement]

FieldElement = Tuple[int, Promise, Validator[ProfileDataElementValue], Callable[[Any], Any], str]
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
    id: int


class SAMLIdPConfigDict(TypedDict, total=False):
    entity_id: str
    url: str
    slo_url: str
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


class UnspecifiedValue:
    """In most API endpoints, we use a default value of `None"` to encode
    parameters that the client did not pass, which is nicely Pythonic.

    However, that design does not work for those few endpoints where
    we want to allow clients to pass an explicit `null` (which
    JSON-decodes to `None`).

    We use this type as an explicit sentinel value for such endpoints.

    TODO: Can this be merged with the _NotSpecified class, which is
    currently an internal implementation detail of the REQ class?
    """

    pass


class EditHistoryEvent(TypedDict, total=False):
    """
    Database format for edit history events.
    """

    # user_id is null for precisely those edit history events
    # predating March 2017, when we started tracking the person who
    # made edits, which is still years after the introduction of topic
    # editing support in Zulip.
    user_id: Optional[int]
    timestamp: int
    prev_stream: int
    stream: int
    prev_topic: str
    topic: str
    prev_content: str
    prev_rendered_content: Optional[str]
    prev_rendered_content_version: Optional[int]


class FormattedEditHistoryEvent(TypedDict, total=False):
    """
    Extended format used in the edit history endpoint.
    """

    # See EditHistoryEvent for details on when this can be null.
    user_id: Optional[int]
    timestamp: int
    prev_stream: int
    stream: int
    prev_topic: str
    topic: str
    prev_content: str
    content: str
    prev_rendered_content: Optional[str]
    rendered_content: Optional[str]
    content_html_diff: str
