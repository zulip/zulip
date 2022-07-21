import datetime
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, TypeVar, Union

from django.http import HttpResponse
from django.utils.functional import Promise
from typing_extensions import NotRequired

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
    hint: str
    field_data: str
    order: int


class ProfileDataElement(ProfileDataElementBase):
    value: ProfileDataElementValue
    rendered_value: Optional[str]


class ProfileDataElementUpdateDict(TypedDict):
    id: int
    value: ProfileDataElementValue


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
    auto_signup: bool
    display_name: str
    display_icon: str
    limit_to_subdomains: List[str]
    extra_attrs: List[str]
    x509cert: str
    x509cert_path: str


class OIDCIdPConfigDict(TypedDict, total=False):
    oidc_url: str
    display_name: str
    display_icon: Optional[str]
    client_id: str
    secret: Optional[str]
    auto_signup: bool


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


# This next batch of types is for Stream/Subscription objects.
class RawStreamDict(TypedDict):
    """Dictionary containing fields fetched from the Stream model that
    are needed to encode the stream for the API.
    """

    date_created: datetime.datetime
    description: str
    email_token: str
    first_message_id: Optional[int]
    history_public_to_subscribers: bool
    id: int
    invite_only: bool
    is_web_public: bool
    message_retention_days: Optional[int]
    name: str
    rendered_description: str
    stream_post_policy: int


class RawSubscriptionDict(TypedDict):
    """Dictionary containing fields fetched from the Subscription model
    that are needed to encode the subscription for the API.
    """

    active: bool
    audible_notifications: Optional[bool]
    color: str
    desktop_notifications: Optional[bool]
    email_notifications: Optional[bool]
    is_muted: bool
    pin_to_top: bool
    push_notifications: Optional[bool]
    recipient_id: int
    wildcard_mentions_notify: Optional[bool]


class SubscriptionStreamDict(TypedDict):
    """Conceptually, the union of RawSubscriptionDict and RawStreamDict
    (i.e. containing all the user's personal settings for the stream
    as well as the stream's global settings), with a few additional
    computed fields.
    """

    audible_notifications: Optional[bool]
    color: str
    date_created: int
    description: str
    desktop_notifications: Optional[bool]
    email_address: str
    email_notifications: Optional[bool]
    first_message_id: Optional[int]
    history_public_to_subscribers: bool
    in_home_view: bool
    invite_only: bool
    is_announcement_only: bool
    is_muted: bool
    is_web_public: bool
    message_retention_days: Optional[int]
    name: str
    pin_to_top: bool
    push_notifications: Optional[bool]
    rendered_description: str
    stream_id: int
    stream_post_policy: int
    stream_weekly_traffic: Optional[int]
    subscribers: NotRequired[List[int]]
    wildcard_mentions_notify: Optional[bool]


class NeverSubscribedStreamDict(TypedDict):
    date_created: int
    description: str
    first_message_id: Optional[int]
    history_public_to_subscribers: bool
    invite_only: bool
    is_announcement_only: bool
    is_web_public: bool
    message_retention_days: Optional[int]
    name: str
    rendered_description: str
    stream_id: int
    stream_post_policy: int
    stream_weekly_traffic: Optional[int]
    subscribers: NotRequired[List[int]]


class APIStreamDict(TypedDict):
    """Stream information provided to Zulip clients as a dictionary via API.
    It should contain all the fields specified in `zerver.models.Stream.API_FIELDS`
    with few exceptions and possible additional fields.
    """

    date_created: int
    description: str
    first_message_id: Optional[int]
    history_public_to_subscribers: bool
    invite_only: bool
    is_web_public: bool
    message_retention_days: Optional[int]
    name: str
    rendered_description: str
    stream_id: int  # `stream_id`` represents `id` of the `Stream` object in `API_FIELDS`
    stream_post_policy: int
    # Computed fields not specified in `Stream.API_FIELDS`
    is_announcement_only: bool
    is_default: NotRequired[bool]


class APISubscriptionDict(APIStreamDict):
    """Similar to StreamClientDict, it should contain all the fields specified in
    `zerver.models.Subscription.API_FIELDS` and several additional fields.
    """

    audible_notifications: Optional[bool]
    color: str
    desktop_notifications: Optional[bool]
    email_notifications: Optional[bool]
    is_muted: bool
    pin_to_top: bool
    push_notifications: Optional[bool]
    wildcard_mentions_notify: Optional[bool]
    # Computed fields not specified in `Subscription.API_FIELDS`
    email_address: str
    in_home_view: bool
    stream_weekly_traffic: Optional[int]
    subscribers: List[int]


@dataclass
class SubscriptionInfo:
    subscriptions: List[SubscriptionStreamDict]
    unsubscribed: List[SubscriptionStreamDict]
    never_subscribed: List[NeverSubscribedStreamDict]


class RealmPlaygroundDict(TypedDict):
    id: int
    name: str
    pygments_language: str
    url_prefix: str


class SCIMConfigDict(TypedDict):
    bearer_token: str
    scim_client_name: str
    name_formatted_included: bool
