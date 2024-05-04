from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, TypeVar, Union

from django_stubs_ext import StrPromise
from typing_extensions import NotRequired, TypeAlias

# See zerver/lib/validator.py for more details of Validators,
# including many examples
ResultT = TypeVar("ResultT")
Validator: TypeAlias = Callable[[str, object], ResultT]
ExtendedValidator: TypeAlias = Callable[[str, str, object], str]
RealmUserValidator: TypeAlias = Callable[[int, object, bool], List[int]]


ProfileDataElementValue: TypeAlias = Union[str, List[int]]


class ProfileDataElementBase(TypedDict, total=False):
    id: int
    name: str
    type: int
    hint: str
    display_in_profile_summary: bool
    required: bool
    field_data: str
    order: int


class ProfileDataElement(ProfileDataElementBase):
    value: Optional[ProfileDataElementValue]
    rendered_value: Optional[str]


class ProfileDataElementUpdateDict(TypedDict):
    id: int
    value: ProfileDataElementValue


ProfileData: TypeAlias = List[ProfileDataElement]

FieldElement: TypeAlias = Tuple[
    int, StrPromise, Validator[ProfileDataElementValue], Callable[[Any], Any], str
]
ExtendedFieldElement: TypeAlias = Tuple[
    int, StrPromise, ExtendedValidator, Callable[[Any], Any], str
]
UserFieldElement: TypeAlias = Tuple[int, StrPromise, RealmUserValidator, Callable[[Any], Any], str]

ProfileFieldData: TypeAlias = Dict[str, Union[Dict[str, str], str]]


class UserDisplayRecipient(TypedDict):
    email: str
    full_name: str
    id: int
    is_mirror_dummy: bool


DisplayRecipientT: TypeAlias = Union[str, List[UserDisplayRecipient]]


class LinkifierDict(TypedDict):
    pattern: str
    url_template: str
    id: int


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


class UserTopicDict(TypedDict, total=False):
    """Dictionary containing fields fetched from the UserTopic model that
    are needed to encode the UserTopic object for the API.
    """

    stream_id: int
    stream__name: str
    topic_name: str
    last_updated: int
    visibility_policy: int


# This next batch of types is for Stream/Subscription objects.
class RawStreamDict(TypedDict):
    """Dictionary containing fields fetched from the Stream model that
    are needed to encode the stream for the API.
    """

    can_remove_subscribers_group_id: int
    creator_id: Optional[int]
    date_created: datetime
    description: str
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
    can_remove_subscribers_group: int
    color: str
    creator_id: Optional[int]
    date_created: int
    description: str
    desktop_notifications: Optional[bool]
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
    can_remove_subscribers_group: int
    creator_id: Optional[int]
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


class DefaultStreamDict(TypedDict):
    """Stream information provided to Zulip clients as a dictionary via API.
    It should contain all the fields specified in `zerver.models.Stream.API_FIELDS`
    with few exceptions and possible additional fields.
    """

    can_remove_subscribers_group: int
    creator_id: Optional[int]
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


class APIStreamDict(DefaultStreamDict):
    stream_weekly_traffic: Optional[int]


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
    in_home_view: bool
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
    url_template: str


@dataclass
class GroupPermissionSetting:
    require_system_group: bool
    allow_internet_group: bool
    allow_owners_group: bool
    allow_nobody_group: bool
    allow_everyone_group: bool
    default_group_name: str
    id_field_name: str
    default_for_system_groups: Optional[str] = None
    allowed_system_groups: List[str] = field(default_factory=list)


@dataclass
class ServerSupportedPermissionSettings:
    realm: Dict[str, GroupPermissionSetting]
    stream: Dict[str, GroupPermissionSetting]
    group: Dict[str, GroupPermissionSetting]


class RawUserDict(TypedDict):
    id: int
    full_name: str
    email: str
    avatar_source: str
    avatar_version: int
    is_active: bool
    role: int
    is_billing_admin: bool
    is_bot: bool
    timezone: str
    date_joined: datetime
    bot_owner_id: Optional[int]
    delivery_email: str
    bot_type: Optional[int]
    long_term_idle: bool
    email_address_visibility: int


class RemoteRealmDictValue(TypedDict):
    can_push: bool
    expected_end_timestamp: Optional[int]
