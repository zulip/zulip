import datetime
import hashlib
import secrets
import time
from collections import defaultdict
from datetime import timedelta
from email.headerregistry import Address
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
)
from uuid import uuid4

import django.contrib.auth
import orjson
import re2
import uri_template
from bitfield import BitField
from bitfield.types import Bit, BitHandler
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    AnonymousUser,
    PermissionsMixin,
    UserManager,
)
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinLengthValidator, RegexValidator, validate_email
from django.db import models, transaction
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models import CASCADE, Exists, F, OuterRef, Q, QuerySet, Sum
from django.db.models.functions import Lower, Upper
from django.db.models.signals import post_delete, post_save, pre_delete
from django.db.models.sql.compiler import SQLCompiler
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django_cte import CTEManager
from django_stubs_ext import StrPromise, ValuesQuerySet

from confirmation import settings as confirmation_settings
from zerver.lib import cache
from zerver.lib.cache import (
    active_non_guest_user_ids_cache_key,
    active_user_ids_cache_key,
    bot_dict_fields,
    bot_dicts_in_realm_cache_key,
    bot_profile_cache_key,
    cache_delete,
    cache_set,
    cache_with_key,
    flush_message,
    flush_muting_users_cache,
    flush_realm,
    flush_stream,
    flush_submessage,
    flush_used_upload_space_cache,
    flush_user_profile,
    get_realm_used_upload_space_cache_key,
    realm_alert_words_automaton_cache_key,
    realm_alert_words_cache_key,
    realm_user_dict_fields,
    realm_user_dicts_cache_key,
    user_profile_by_api_key_cache_key,
    user_profile_by_id_cache_key,
    user_profile_cache_key,
)
from zerver.lib.exceptions import JsonableError, RateLimitedError
from zerver.lib.per_request_cache import (
    flush_per_request_cache,
    return_same_value_during_entire_request,
)
from zerver.lib.pysa import mark_sanitized
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.types import (
    DefaultStreamDict,
    ExtendedFieldElement,
    ExtendedValidator,
    FieldElement,
    GroupPermissionSetting,
    LinkifierDict,
    ProfileData,
    ProfileDataElementBase,
    ProfileDataElementValue,
    RealmPlaygroundDict,
    RealmUserValidator,
    UnspecifiedValue,
    UserDisplayRecipient,
    UserFieldElement,
    Validator,
)
from zerver.lib.utils import generate_api_key
from zerver.lib.validator import (
    check_date,
    check_int,
    check_list,
    check_long_string,
    check_short_string,
    check_url,
    validate_select_field,
)

MAX_TOPIC_NAME_LENGTH = 60
MAX_LANGUAGE_ID_LENGTH: int = 50

SECONDS_PER_DAY = 86400

if TYPE_CHECKING:
    # We use ModelBackend only for typing. Importing it otherwise causes circular dependency.
    from django.contrib.auth.backends import ModelBackend


class EmojiInfo(TypedDict):
    id: str
    name: str
    source_url: str
    deactivated: bool
    author_id: Optional[int]
    still_url: Optional[str]


@models.Field.register_lookup
class AndZero(models.Lookup[int]):
    lookup_name = "andz"

    def as_sql(
        self, compiler: SQLCompiler, connection: BaseDatabaseWrapper
    ) -> Tuple[str, List[Union[str, int]]]:  # nocoverage # currently only used in migrations
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f"{lhs} & {rhs} = 0", lhs_params + rhs_params


@models.Field.register_lookup
class AndNonZero(models.Lookup[int]):
    lookup_name = "andnz"

    def as_sql(
        self, compiler: SQLCompiler, connection: BaseDatabaseWrapper
    ) -> Tuple[str, List[Union[str, int]]]:  # nocoverage # currently only used in migrations
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f"{lhs} & {rhs} != 0", lhs_params + rhs_params


ModelT = TypeVar("ModelT", bound=models.Model)
RowT = TypeVar("RowT")


def query_for_ids(
    query: ValuesQuerySet[ModelT, RowT],
    user_ids: List[int],
    field: str,
) -> ValuesQuerySet[ModelT, RowT]:
    """
    This function optimizes searches of the form
    `user_profile_id in (1, 2, 3, 4)` by quickly
    building the where clauses.  Profiling shows significant
    speedups over the normal Django-based approach.

    Use this very carefully!  Also, the caller should
    guard against empty lists of user_ids.
    """
    assert user_ids
    clause = f"{field} IN %s"
    query = query.extra(
        where=[clause],
        params=(tuple(user_ids),),
    )
    return query


@return_same_value_during_entire_request
def get_display_recipient_by_id(
    recipient_id: int, recipient_type: int, recipient_type_id: Optional[int]
) -> List[UserDisplayRecipient]:
    """
    returns: an object describing the recipient (using a cache).
    If the type is a stream, the type_id must be an int; a string is returned.
    Otherwise, type_id may be None; an array of recipient dicts is returned.
    """
    # Have to import here, to avoid circular dependency.
    from zerver.lib.display_recipient import get_display_recipient_remote_cache

    return get_display_recipient_remote_cache(recipient_id, recipient_type, recipient_type_id)


def get_display_recipient(recipient: "Recipient") -> List[UserDisplayRecipient]:
    return get_display_recipient_by_id(
        recipient.id,
        recipient.type,
        recipient.type_id,
    )


def get_recipient_ids(
    recipient: Optional["Recipient"], user_profile_id: int
) -> Tuple[List[int], str]:
    if recipient is None:
        recipient_type_str = ""
        to = []
    elif recipient.type == Recipient.STREAM:
        recipient_type_str = "stream"
        to = [recipient.type_id]
    else:
        recipient_type_str = "private"
        if recipient.type == Recipient.PERSONAL:
            to = [recipient.type_id]
        else:
            to = []
            for r in get_display_recipient(recipient):
                assert not isinstance(r, str)  # It will only be a string for streams
                if r["id"] != user_profile_id:
                    to.append(r["id"])
    return to, recipient_type_str


def get_all_custom_emoji_for_realm_cache_key(realm_id: int) -> str:
    return f"realm_emoji:{realm_id}"


# This simple call-once caching saves ~500us in auth_enabled_helper,
# which is a significant optimization for common_context.  Note that
# these values cannot change in a running production system, but do
# regularly change within unit tests; we address the latter by calling
# clear_supported_auth_backends_cache in our standard tearDown code.
supported_backends: Optional[List["ModelBackend"]] = None


def supported_auth_backends() -> List["ModelBackend"]:
    global supported_backends
    # Caching temporarily disabled for debugging
    supported_backends = django.contrib.auth.get_backends()
    assert supported_backends is not None
    return supported_backends


def clear_supported_auth_backends_cache() -> None:
    global supported_backends
    supported_backends = None


class RealmAuthenticationMethod(models.Model):
    """
    Tracks which authentication backends are enabled for a realm.
    An enabled backend is represented in this table a row with appropriate
    .realm value and .name matching the name of the target backend in the
    AUTH_BACKEND_NAME_MAP dict.
    """

    realm = models.ForeignKey("Realm", on_delete=CASCADE, db_index=True)
    name = models.CharField(max_length=80)

    class Meta:
        unique_together = ("realm", "name")


class Realm(models.Model):  # type: ignore[django-manager-missing] # django-stubs cannot resolve the custom CTEManager yet https://github.com/typeddjango/django-stubs/issues/1023
    MAX_REALM_NAME_LENGTH = 40
    MAX_REALM_DESCRIPTION_LENGTH = 1000
    MAX_REALM_SUBDOMAIN_LENGTH = 40
    MAX_REALM_REDIRECT_URL_LENGTH = 128

    INVITES_STANDARD_REALM_DAILY_MAX = 3000
    MESSAGE_VISIBILITY_LIMITED = 10000
    SUBDOMAIN_FOR_ROOT_DOMAIN = ""
    WILDCARD_MENTION_THRESHOLD = 15

    # User-visible display name and description used on e.g. the organization homepage
    name = models.CharField(max_length=MAX_REALM_NAME_LENGTH)
    description = models.TextField(default="")

    # A short, identifier-like name for the organization.  Used in subdomains;
    # e.g. on a server at example.com, an org with string_id `foo` is reached
    # at `foo.example.com`.
    string_id = models.CharField(max_length=MAX_REALM_SUBDOMAIN_LENGTH, unique=True)

    date_created = models.DateTimeField(default=timezone_now)
    demo_organization_scheduled_deletion_date = models.DateTimeField(default=None, null=True)
    deactivated = models.BooleanField(default=False)

    # Redirect URL if the Realm has moved to another server
    deactivated_redirect = models.URLField(max_length=MAX_REALM_REDIRECT_URL_LENGTH, null=True)

    # See RealmDomain for the domains that apply for a given organization.
    emails_restricted_to_domains = models.BooleanField(default=False)

    invite_required = models.BooleanField(default=True)

    _max_invites = models.IntegerField(null=True, db_column="max_invites")
    disallow_disposable_email_addresses = models.BooleanField(default=True)

    # Allow users to access web-public streams without login. This
    # setting also controls API access of web-public streams.
    enable_spectator_access = models.BooleanField(default=False)

    # Whether organization has given permission to be advertised in the
    # Zulip communities directory.
    want_advertise_in_communities_directory = models.BooleanField(default=False, db_index=True)

    # Whether the organization has enabled inline image and URL previews.
    inline_image_preview = models.BooleanField(default=True)
    inline_url_embed_preview = models.BooleanField(default=False)

    # Whether digest emails are enabled for the organization.
    digest_emails_enabled = models.BooleanField(default=False)
    # Day of the week on which the digest is sent (default: Tuesday).
    digest_weekday = models.SmallIntegerField(default=1)

    send_welcome_emails = models.BooleanField(default=True)
    message_content_allowed_in_email_notifications = models.BooleanField(default=True)

    mandatory_topics = models.BooleanField(default=False)

    name_changes_disabled = models.BooleanField(default=False)
    email_changes_disabled = models.BooleanField(default=False)
    avatar_changes_disabled = models.BooleanField(default=False)

    POLICY_MEMBERS_ONLY = 1
    POLICY_ADMINS_ONLY = 2
    POLICY_FULL_MEMBERS_ONLY = 3
    POLICY_MODERATORS_ONLY = 4
    POLICY_EVERYONE = 5
    POLICY_NOBODY = 6
    POLICY_OWNERS_ONLY = 7

    COMMON_POLICY_TYPES = [
        POLICY_MEMBERS_ONLY,
        POLICY_ADMINS_ONLY,
        POLICY_FULL_MEMBERS_ONLY,
        POLICY_MODERATORS_ONLY,
    ]

    COMMON_MESSAGE_POLICY_TYPES = [
        POLICY_MEMBERS_ONLY,
        POLICY_ADMINS_ONLY,
        POLICY_FULL_MEMBERS_ONLY,
        POLICY_MODERATORS_ONLY,
        POLICY_EVERYONE,
    ]

    INVITE_TO_REALM_POLICY_TYPES = [
        POLICY_MEMBERS_ONLY,
        POLICY_ADMINS_ONLY,
        POLICY_FULL_MEMBERS_ONLY,
        POLICY_MODERATORS_ONLY,
        POLICY_NOBODY,
    ]

    # We don't allow granting roles less than Moderator access to
    # create web-public streams, since it's a sensitive feature that
    # can be used to send spam.
    CREATE_WEB_PUBLIC_STREAM_POLICY_TYPES = [
        POLICY_ADMINS_ONLY,
        POLICY_MODERATORS_ONLY,
        POLICY_OWNERS_ONLY,
        POLICY_NOBODY,
    ]

    EDIT_TOPIC_POLICY_TYPES = [
        POLICY_MEMBERS_ONLY,
        POLICY_ADMINS_ONLY,
        POLICY_FULL_MEMBERS_ONLY,
        POLICY_MODERATORS_ONLY,
        POLICY_EVERYONE,
        POLICY_NOBODY,
    ]

    MOVE_MESSAGES_BETWEEN_STREAMS_POLICY_TYPES = INVITE_TO_REALM_POLICY_TYPES

    DEFAULT_MOVE_MESSAGE_LIMIT_SECONDS = 7 * SECONDS_PER_DAY

    move_messages_within_stream_limit_seconds = models.PositiveIntegerField(
        default=DEFAULT_MOVE_MESSAGE_LIMIT_SECONDS, null=True
    )

    move_messages_between_streams_limit_seconds = models.PositiveIntegerField(
        default=DEFAULT_MOVE_MESSAGE_LIMIT_SECONDS, null=True
    )

    # Who in the organization is allowed to add custom emojis.
    add_custom_emoji_policy = models.PositiveSmallIntegerField(default=POLICY_MEMBERS_ONLY)

    # Who in the organization is allowed to create streams.
    create_public_stream_policy = models.PositiveSmallIntegerField(default=POLICY_MEMBERS_ONLY)
    create_private_stream_policy = models.PositiveSmallIntegerField(default=POLICY_MEMBERS_ONLY)
    create_web_public_stream_policy = models.PositiveSmallIntegerField(default=POLICY_OWNERS_ONLY)

    # Who in the organization is allowed to delete messages they themselves sent.
    delete_own_message_policy = models.PositiveSmallIntegerField(default=POLICY_ADMINS_ONLY)

    # Who in the organization is allowed to edit topics of any message.
    edit_topic_policy = models.PositiveSmallIntegerField(default=POLICY_EVERYONE)

    # Who in the organization is allowed to invite other users to organization.
    invite_to_realm_policy = models.PositiveSmallIntegerField(default=POLICY_MEMBERS_ONLY)

    # UserGroup whose members are allowed to create invite link.
    create_multiuse_invite_group = models.ForeignKey(
        "UserGroup", on_delete=models.RESTRICT, related_name="+"
    )

    # Who in the organization is allowed to invite other users to streams.
    invite_to_stream_policy = models.PositiveSmallIntegerField(default=POLICY_MEMBERS_ONLY)

    # Who in the organization is allowed to move messages between streams.
    move_messages_between_streams_policy = models.PositiveSmallIntegerField(
        default=POLICY_ADMINS_ONLY
    )

    user_group_edit_policy = models.PositiveSmallIntegerField(default=POLICY_MEMBERS_ONLY)

    PRIVATE_MESSAGE_POLICY_UNLIMITED = 1
    PRIVATE_MESSAGE_POLICY_DISABLED = 2
    private_message_policy = models.PositiveSmallIntegerField(
        default=PRIVATE_MESSAGE_POLICY_UNLIMITED
    )
    PRIVATE_MESSAGE_POLICY_TYPES = [
        PRIVATE_MESSAGE_POLICY_UNLIMITED,
        PRIVATE_MESSAGE_POLICY_DISABLED,
    ]

    # Global policy for who is allowed to use wildcard mentions in
    # streams with a large number of subscribers.  Anyone can use
    # wildcard mentions in small streams regardless of this setting.
    WILDCARD_MENTION_POLICY_EVERYONE = 1
    WILDCARD_MENTION_POLICY_MEMBERS = 2
    WILDCARD_MENTION_POLICY_FULL_MEMBERS = 3
    WILDCARD_MENTION_POLICY_ADMINS = 5
    WILDCARD_MENTION_POLICY_NOBODY = 6
    WILDCARD_MENTION_POLICY_MODERATORS = 7
    wildcard_mention_policy = models.PositiveSmallIntegerField(
        default=WILDCARD_MENTION_POLICY_ADMINS,
    )
    WILDCARD_MENTION_POLICY_TYPES = [
        WILDCARD_MENTION_POLICY_EVERYONE,
        WILDCARD_MENTION_POLICY_MEMBERS,
        WILDCARD_MENTION_POLICY_FULL_MEMBERS,
        WILDCARD_MENTION_POLICY_ADMINS,
        WILDCARD_MENTION_POLICY_NOBODY,
        WILDCARD_MENTION_POLICY_MODERATORS,
    ]

    # Threshold in days for new users to create streams, and potentially take
    # some other actions.
    waiting_period_threshold = models.PositiveIntegerField(default=0)

    DEFAULT_MESSAGE_CONTENT_DELETE_LIMIT_SECONDS = (
        600  # if changed, also change in admin.js, setting_org.js
    )
    MESSAGE_TIME_LIMIT_SETTING_SPECIAL_VALUES_MAP = {
        "unlimited": None,
    }
    message_content_delete_limit_seconds = models.PositiveIntegerField(
        default=DEFAULT_MESSAGE_CONTENT_DELETE_LIMIT_SECONDS, null=True
    )

    allow_message_editing = models.BooleanField(default=True)
    DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS = (
        600  # if changed, also change in admin.js, setting_org.js
    )
    message_content_edit_limit_seconds = models.PositiveIntegerField(
        default=DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS, null=True
    )

    # Whether users have access to message edit history
    allow_edit_history = models.BooleanField(default=True)

    # Defaults for new users
    default_language = models.CharField(default="en", max_length=MAX_LANGUAGE_ID_LENGTH)

    DEFAULT_NOTIFICATION_STREAM_NAME = "general"
    INITIAL_PRIVATE_STREAM_NAME = "core team"
    STREAM_EVENTS_NOTIFICATION_TOPIC = gettext_lazy("stream events")
    notifications_stream = models.ForeignKey(
        "Stream",
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    signup_notifications_stream = models.ForeignKey(
        "Stream",
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    MESSAGE_RETENTION_SPECIAL_VALUES_MAP = {
        "unlimited": -1,
    }
    # For old messages being automatically deleted
    message_retention_days = models.IntegerField(null=False, default=-1)

    # When non-null, all but the latest this many messages in the organization
    # are inaccessible to users (but not deleted).
    message_visibility_limit = models.IntegerField(null=True)

    # Messages older than this message ID in the organization are inaccessible.
    first_visible_message_id = models.IntegerField(default=0)

    # Valid org types
    ORG_TYPES: Dict[str, Dict[str, Any]] = {
        "unspecified": {
            "name": "Unspecified",
            "id": 0,
            "hidden": True,
            "display_order": 0,
            "onboarding_zulip_guide_url": None,
        },
        "business": {
            "name": "Business",
            "id": 10,
            "hidden": False,
            "display_order": 1,
            "onboarding_zulip_guide_url": "https://zulip.com/for/business/",
        },
        "opensource": {
            "name": "Open-source project",
            "id": 20,
            "hidden": False,
            "display_order": 2,
            "onboarding_zulip_guide_url": "https://zulip.com/for/open-source/",
        },
        "education_nonprofit": {
            "name": "Education (non-profit)",
            "id": 30,
            "hidden": False,
            "display_order": 3,
            "onboarding_zulip_guide_url": "https://zulip.com/for/education/",
        },
        "education": {
            "name": "Education (for-profit)",
            "id": 35,
            "hidden": False,
            "display_order": 4,
            "onboarding_zulip_guide_url": "https://zulip.com/for/education/",
        },
        "research": {
            "name": "Research",
            "id": 40,
            "hidden": False,
            "display_order": 5,
            "onboarding_zulip_guide_url": "https://zulip.com/for/research/",
        },
        "event": {
            "name": "Event or conference",
            "id": 50,
            "hidden": False,
            "display_order": 6,
            "onboarding_zulip_guide_url": "https://zulip.com/for/events/",
        },
        "nonprofit": {
            "name": "Non-profit (registered)",
            "id": 60,
            "hidden": False,
            "display_order": 7,
            "onboarding_zulip_guide_url": "https://zulip.com/for/communities/",
        },
        "government": {
            "name": "Government",
            "id": 70,
            "hidden": False,
            "display_order": 8,
            "onboarding_zulip_guide_url": None,
        },
        "political_group": {
            "name": "Political group",
            "id": 80,
            "hidden": False,
            "display_order": 9,
            "onboarding_zulip_guide_url": None,
        },
        "community": {
            "name": "Community",
            "id": 90,
            "hidden": False,
            "display_order": 10,
            "onboarding_zulip_guide_url": "https://zulip.com/for/communities/",
        },
        "personal": {
            "name": "Personal",
            "id": 100,
            "hidden": False,
            "display_order": 100,
            "onboarding_zulip_guide_url": None,
        },
        "other": {
            "name": "Other",
            "id": 1000,
            "hidden": False,
            "display_order": 1000,
            "onboarding_zulip_guide_url": None,
        },
    }

    ORG_TYPE_IDS: List[int] = [t["id"] for t in ORG_TYPES.values()]

    org_type = models.PositiveSmallIntegerField(
        default=ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in ORG_TYPES.values()],
    )

    UPGRADE_TEXT_STANDARD = gettext_lazy("Available on Zulip Cloud Standard. Upgrade to access.")
    # plan_type controls various features around resource/feature
    # limitations for a Zulip organization on multi-tenant installations
    # like Zulip Cloud.
    PLAN_TYPE_SELF_HOSTED = 1
    PLAN_TYPE_LIMITED = 2
    PLAN_TYPE_STANDARD = 3
    PLAN_TYPE_STANDARD_FREE = 4
    PLAN_TYPE_PLUS = 10
    plan_type = models.PositiveSmallIntegerField(default=PLAN_TYPE_SELF_HOSTED)

    # This value is also being used in web/src/settings_bots.bot_creation_policy_values.
    # On updating it here, update it there as well.
    BOT_CREATION_EVERYONE = 1
    BOT_CREATION_LIMIT_GENERIC_BOTS = 2
    BOT_CREATION_ADMINS_ONLY = 3
    bot_creation_policy = models.PositiveSmallIntegerField(default=BOT_CREATION_EVERYONE)
    BOT_CREATION_POLICY_TYPES = [
        BOT_CREATION_EVERYONE,
        BOT_CREATION_LIMIT_GENERIC_BOTS,
        BOT_CREATION_ADMINS_ONLY,
    ]

    # See upload_quota_bytes; don't interpret upload_quota_gb directly.
    UPLOAD_QUOTA_LIMITED = 5
    UPLOAD_QUOTA_STANDARD = 50
    upload_quota_gb = models.IntegerField(null=True)

    VIDEO_CHAT_PROVIDERS = {
        "disabled": {
            "name": "None",
            "id": 0,
        },
        "jitsi_meet": {
            "name": "Jitsi Meet",
            "id": 1,
        },
        # ID 2 was used for the now-deleted Google Hangouts.
        # ID 3 reserved for optional Zoom, see below.
        # ID 4 reserved for optional BigBlueButton, see below.
    }

    if settings.VIDEO_ZOOM_CLIENT_ID is not None and settings.VIDEO_ZOOM_CLIENT_SECRET is not None:
        VIDEO_CHAT_PROVIDERS["zoom"] = {
            "name": "Zoom",
            "id": 3,
        }

    if settings.BIG_BLUE_BUTTON_SECRET is not None and settings.BIG_BLUE_BUTTON_URL is not None:
        VIDEO_CHAT_PROVIDERS["big_blue_button"] = {"name": "BigBlueButton", "id": 4}

    video_chat_provider = models.PositiveSmallIntegerField(
        default=VIDEO_CHAT_PROVIDERS["jitsi_meet"]["id"]
    )

    # Please access this via get_giphy_rating_options.
    GIPHY_RATING_OPTIONS = {
        "disabled": {
            "name": gettext_lazy("GIPHY integration disabled"),
            "id": 0,
        },
        # Source: https://github.com/Giphy/giphy-js/blob/master/packages/fetch-api/README.md#shared-options
        "y": {
            "name": gettext_lazy("Allow GIFs rated Y (Very young audience)"),
            "id": 1,
        },
        "g": {
            "name": gettext_lazy("Allow GIFs rated G (General audience)"),
            "id": 2,
        },
        "pg": {
            "name": gettext_lazy("Allow GIFs rated PG (Parental guidance)"),
            "id": 3,
        },
        "pg-13": {
            "name": gettext_lazy("Allow GIFs rated PG-13 (Parental guidance - under 13)"),
            "id": 4,
        },
        "r": {
            "name": gettext_lazy("Allow GIFs rated R (Restricted)"),
            "id": 5,
        },
    }

    # maximum rating of the GIFs that will be retrieved from GIPHY
    giphy_rating = models.PositiveSmallIntegerField(default=GIPHY_RATING_OPTIONS["g"]["id"])

    default_code_block_language = models.TextField(default="")

    # Whether read receipts are enabled in the organization. If disabled,
    # they will not be available regardless of users' personal settings.
    enable_read_receipts = models.BooleanField(default=False)

    # Duplicates of names for system group; TODO: Clean this up.
    ADMINISTRATORS_GROUP_NAME = "role:administrators"

    # Define the types of the various automatically managed properties
    property_types: Dict[str, Union[type, Tuple[type, ...]]] = dict(
        add_custom_emoji_policy=int,
        allow_edit_history=bool,
        allow_message_editing=bool,
        avatar_changes_disabled=bool,
        bot_creation_policy=int,
        create_private_stream_policy=int,
        create_public_stream_policy=int,
        create_web_public_stream_policy=int,
        default_code_block_language=str,
        default_language=str,
        delete_own_message_policy=int,
        description=str,
        digest_emails_enabled=bool,
        digest_weekday=int,
        disallow_disposable_email_addresses=bool,
        edit_topic_policy=int,
        email_changes_disabled=bool,
        emails_restricted_to_domains=bool,
        enable_read_receipts=bool,
        enable_spectator_access=bool,
        giphy_rating=int,
        inline_image_preview=bool,
        inline_url_embed_preview=bool,
        invite_required=bool,
        invite_to_realm_policy=int,
        invite_to_stream_policy=int,
        mandatory_topics=bool,
        message_content_allowed_in_email_notifications=bool,
        message_content_edit_limit_seconds=(int, type(None)),
        message_content_delete_limit_seconds=(int, type(None)),
        move_messages_between_streams_limit_seconds=(int, type(None)),
        move_messages_within_stream_limit_seconds=(int, type(None)),
        message_retention_days=(int, type(None)),
        move_messages_between_streams_policy=int,
        name=str,
        name_changes_disabled=bool,
        private_message_policy=int,
        send_welcome_emails=bool,
        user_group_edit_policy=int,
        video_chat_provider=int,
        waiting_period_threshold=int,
        want_advertise_in_communities_directory=bool,
        wildcard_mention_policy=int,
    )

    REALM_PERMISSION_GROUP_SETTINGS: Dict[str, GroupPermissionSetting] = dict(
        create_multiuse_invite_group=GroupPermissionSetting(
            require_system_group=True,
            allow_internet_group=False,
            allow_owners_group=False,
            allow_nobody_group=True,
            allow_everyone_group=False,
            default_group_name=ADMINISTRATORS_GROUP_NAME,
            id_field_name="create_multiuse_invite_group_id",
        ),
    )

    DIGEST_WEEKDAY_VALUES = [0, 1, 2, 3, 4, 5, 6]

    # Icon is the square mobile icon.
    ICON_FROM_GRAVATAR = "G"
    ICON_UPLOADED = "U"
    ICON_SOURCES = (
        (ICON_FROM_GRAVATAR, "Hosted by Gravatar"),
        (ICON_UPLOADED, "Uploaded by administrator"),
    )
    icon_source = models.CharField(
        default=ICON_FROM_GRAVATAR,
        choices=ICON_SOURCES,
        max_length=1,
    )
    icon_version = models.PositiveSmallIntegerField(default=1)

    # Logo is the horizontal logo we show in top-left of web app navbar UI.
    LOGO_DEFAULT = "D"
    LOGO_UPLOADED = "U"
    LOGO_SOURCES = (
        (LOGO_DEFAULT, "Default to Zulip"),
        (LOGO_UPLOADED, "Uploaded by administrator"),
    )
    logo_source = models.CharField(
        default=LOGO_DEFAULT,
        choices=LOGO_SOURCES,
        max_length=1,
    )
    logo_version = models.PositiveSmallIntegerField(default=1)

    night_logo_source = models.CharField(
        default=LOGO_DEFAULT,
        choices=LOGO_SOURCES,
        max_length=1,
    )
    night_logo_version = models.PositiveSmallIntegerField(default=1)

    def __str__(self) -> str:
        return f"{self.string_id} {self.id}"

    def get_giphy_rating_options(self) -> Dict[str, Dict[str, object]]:
        """Wrapper function for GIPHY_RATING_OPTIONS that ensures evaluation
        of the lazily evaluated `name` field without modifying the original."""
        return {
            rating_type: {"name": str(rating["name"]), "id": rating["id"]}
            for rating_type, rating in self.GIPHY_RATING_OPTIONS.items()
        }

    def authentication_methods_dict(self) -> Dict[str, bool]:
        """Returns the mapping from authentication flags to their status,
        showing only those authentication flags that are supported on
        the current server (i.e. if EmailAuthBackend is not configured
        on the server, this will not return an entry for "Email")."""
        # This mapping needs to be imported from here due to the cyclic
        # dependency.
        from zproject.backends import AUTH_BACKEND_NAME_MAP, all_implemented_backend_names

        ret: Dict[str, bool] = {}
        supported_backends = [type(backend) for backend in supported_auth_backends()]

        for backend_name in all_implemented_backend_names():
            backend_class = AUTH_BACKEND_NAME_MAP[backend_name]
            if backend_class in supported_backends:
                ret[backend_name] = False
        for realm_authentication_method in RealmAuthenticationMethod.objects.filter(
            realm_id=self.id
        ):
            backend_class = AUTH_BACKEND_NAME_MAP[realm_authentication_method.name]
            if backend_class in supported_backends:
                ret[realm_authentication_method.name] = True
        return ret

    def get_admin_users_and_bots(
        self, include_realm_owners: bool = True
    ) -> QuerySet["UserProfile"]:
        """Use this in contexts where we want administrative users as well as
        bots with administrator privileges, like send_event calls for
        notifications to all administrator users.
        """
        if include_realm_owners:
            roles = [UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_REALM_OWNER]
        else:
            roles = [UserProfile.ROLE_REALM_ADMINISTRATOR]

        return UserProfile.objects.filter(
            realm=self,
            is_active=True,
            role__in=roles,
        )

    def get_human_admin_users(self, include_realm_owners: bool = True) -> QuerySet["UserProfile"]:
        """Use this in contexts where we want only human users with
        administrative privileges, like sending an email to all of a
        realm's administrators (bots don't have real email addresses).
        """
        if include_realm_owners:
            roles = [UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_REALM_OWNER]
        else:
            roles = [UserProfile.ROLE_REALM_ADMINISTRATOR]

        return UserProfile.objects.filter(
            realm=self,
            is_bot=False,
            is_active=True,
            role__in=roles,
        )

    def get_human_billing_admin_and_realm_owner_users(self) -> QuerySet["UserProfile"]:
        return UserProfile.objects.filter(
            Q(role=UserProfile.ROLE_REALM_OWNER) | Q(is_billing_admin=True),
            realm=self,
            is_bot=False,
            is_active=True,
        )

    def get_active_users(self) -> QuerySet["UserProfile"]:
        return UserProfile.objects.filter(realm=self, is_active=True)

    def get_first_human_user(self) -> Optional["UserProfile"]:
        """A useful value for communications with newly created realms.
        Has a few fundamental limitations:

        * Its value will be effectively random for realms imported from Slack or
          other third-party tools.
        * The user may be deactivated, etc., so it's not something that's useful
          for features, permissions, etc.
        """
        return UserProfile.objects.filter(realm=self, is_bot=False).order_by("id").first()

    def get_human_owner_users(self) -> QuerySet["UserProfile"]:
        return UserProfile.objects.filter(
            realm=self, is_bot=False, role=UserProfile.ROLE_REALM_OWNER, is_active=True
        )

    def get_bot_domain(self) -> str:
        return get_fake_email_domain(self)

    def get_notifications_stream(self) -> Optional["Stream"]:
        if self.notifications_stream is not None and not self.notifications_stream.deactivated:
            return self.notifications_stream
        return None

    def get_signup_notifications_stream(self) -> Optional["Stream"]:
        if (
            self.signup_notifications_stream is not None
            and not self.signup_notifications_stream.deactivated
        ):
            return self.signup_notifications_stream
        return None

    @property
    def max_invites(self) -> int:
        if self._max_invites is None:
            return settings.INVITES_DEFAULT_REALM_DAILY_MAX
        return self._max_invites

    @max_invites.setter
    def max_invites(self, value: Optional[int]) -> None:
        self._max_invites = value

    def upload_quota_bytes(self) -> Optional[int]:
        if self.upload_quota_gb is None:
            return None
        # We describe the quota to users in "GB" or "gigabytes", but actually apply
        # it as gibibytes (GiB) to be a bit more generous in case of confusion.
        return self.upload_quota_gb << 30

    # `realm` instead of `self` here to make sure the parameters of the cache key
    # function matches the original method.
    @cache_with_key(
        lambda realm: get_realm_used_upload_space_cache_key(realm.id), timeout=3600 * 24 * 7
    )
    def currently_used_upload_space_bytes(realm) -> int:  # noqa: N805
        used_space = Attachment.objects.filter(realm=realm).aggregate(Sum("size"))["size__sum"]
        if used_space is None:
            return 0
        return used_space

    def ensure_not_on_limited_plan(self) -> None:
        if self.plan_type == Realm.PLAN_TYPE_LIMITED:
            raise JsonableError(str(self.UPGRADE_TEXT_STANDARD))

    @property
    def subdomain(self) -> str:
        return self.string_id

    @property
    def display_subdomain(self) -> str:
        """Likely to be temporary function to avoid signup messages being sent
        to an empty topic"""
        if self.string_id == "":
            return "."
        return self.string_id

    @property
    def uri(self) -> str:
        return settings.EXTERNAL_URI_SCHEME + self.host

    @property
    def host(self) -> str:
        # Use mark sanitized to prevent false positives from Pysa thinking that
        # the host is user controlled.
        return mark_sanitized(self.host_for_subdomain(self.subdomain))

    @staticmethod
    def host_for_subdomain(subdomain: str) -> str:
        if subdomain == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
            return settings.EXTERNAL_HOST
        default_host = f"{subdomain}.{settings.EXTERNAL_HOST}"
        return settings.REALM_HOSTS.get(subdomain, default_host)

    @property
    def is_zephyr_mirror_realm(self) -> bool:
        return self.string_id == "zephyr"

    @property
    def webathena_enabled(self) -> bool:
        return self.is_zephyr_mirror_realm

    @property
    def presence_disabled(self) -> bool:
        return self.is_zephyr_mirror_realm

    def web_public_streams_enabled(self) -> bool:
        if not settings.WEB_PUBLIC_STREAMS_ENABLED:
            # To help protect against accidentally web-public streams in
            # self-hosted servers, we require the feature to be enabled at
            # the server level before it is available to users.
            return False

        if self.plan_type == Realm.PLAN_TYPE_LIMITED:
            # In Zulip Cloud, we also require a paid or sponsored
            # plan, to protect against the spam/abuse attacks that
            # target every open Internet service that can host files.
            return False

        if not self.enable_spectator_access:
            return False

        return True

    def has_web_public_streams(self) -> bool:
        if not self.web_public_streams_enabled():
            return False

        from zerver.lib.streams import get_web_public_streams_queryset

        return get_web_public_streams_queryset(self).exists()

    def allow_web_public_streams_access(self) -> bool:
        """
        If any of the streams in the realm is web
        public and `enable_spectator_access` and
        settings.WEB_PUBLIC_STREAMS_ENABLED is True,
        then the Realm is web-public.
        """
        return self.has_web_public_streams()


post_save.connect(flush_realm, sender=Realm)


# We register realm cache flushing in a duplicate way to be run both
# pre_delete and post_delete on purpose:
# 1. pre_delete is needed because flush_realm wants to flush the UserProfile caches,
#    and UserProfile objects are deleted via on_delete=CASCADE before the post_delete handler
#    is called, which results in the `flush_realm` logic not having access to the details
#    for the deleted users if called at that time.
# 2. post_delete is run as a precaution to reduce the risk of races where items might be
#    added to the cache after the pre_delete handler but before the save.
#    Note that it does not eliminate this risk, not least because it only flushes
#    the realm cache, and not the user caches, for the reasons explained above.
def realm_pre_and_post_delete_handler(*, instance: Realm, **kwargs: object) -> None:
    # This would be better as a functools.partial, but for some reason
    # Django doesn't call it even when it's registered as a post_delete handler.
    flush_realm(instance=instance, from_deletion=True)


pre_delete.connect(realm_pre_and_post_delete_handler, sender=Realm)
post_delete.connect(realm_pre_and_post_delete_handler, sender=Realm)


def get_realm(string_id: str) -> Realm:
    return Realm.objects.get(string_id=string_id)


def get_realm_by_id(realm_id: int) -> Realm:
    return Realm.objects.get(id=realm_id)


def name_changes_disabled(realm: Optional[Realm]) -> bool:
    if realm is None:
        return settings.NAME_CHANGES_DISABLED
    return settings.NAME_CHANGES_DISABLED or realm.name_changes_disabled


def avatar_changes_disabled(realm: Realm) -> bool:
    return settings.AVATAR_CHANGES_DISABLED or realm.avatar_changes_disabled


def get_org_type_display_name(org_type: int) -> str:
    for realm_type_details in Realm.ORG_TYPES.values():
        if realm_type_details["id"] == org_type:
            return realm_type_details["name"]

    return ""


class RealmDomain(models.Model):
    """For an organization with emails_restricted_to_domains enabled, the list of
    allowed domains"""

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    # should always be stored lowercase
    domain = models.CharField(max_length=80, db_index=True)
    allow_subdomains = models.BooleanField(default=False)

    class Meta:
        unique_together = ("realm", "domain")


class DomainNotAllowedForRealmError(Exception):
    pass


class DisposableEmailError(Exception):
    pass


class EmailContainsPlusError(Exception):
    pass


class RealmDomainDict(TypedDict):
    domain: str
    allow_subdomains: bool


def get_realm_domains(realm: Realm) -> List[RealmDomainDict]:
    return list(realm.realmdomain_set.values("domain", "allow_subdomains"))


class RealmEmoji(models.Model):
    author = models.ForeignKey(
        "UserProfile",
        blank=True,
        null=True,
        on_delete=CASCADE,
    )
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    name = models.TextField(
        validators=[
            MinLengthValidator(1),
            # The second part of the regex (negative lookbehind) disallows names
            # ending with one of the punctuation characters.
            RegexValidator(
                regex=r"^[0-9a-z.\-_]+(?<![.\-_])$",
                message=gettext_lazy("Invalid characters in emoji name"),
            ),
        ]
    )

    # The basename of the custom emoji's filename; see PATH_ID_TEMPLATE for the full path.
    file_name = models.TextField(db_index=True, null=True, blank=True)

    # Whether this custom emoji is an animated image.
    is_animated = models.BooleanField(default=False)

    deactivated = models.BooleanField(default=False)

    PATH_ID_TEMPLATE = "{realm_id}/emoji/images/{emoji_file_name}"
    STILL_PATH_ID_TEMPLATE = "{realm_id}/emoji/images/still/{emoji_filename_without_extension}.png"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["realm", "name"],
                condition=Q(deactivated=False),
                name="unique_realm_emoji_when_false_deactivated",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.realm.string_id}: {self.id} {self.name} {self.deactivated} {self.file_name}"


def get_all_custom_emoji_for_realm_uncached(realm_id: int) -> Dict[str, EmojiInfo]:
    # RealmEmoji objects with file_name=None are still in the process
    # of being uploaded, and we expect to be cleaned up by a
    # try/finally block if the upload fails, so it's correct to
    # exclude them.
    query = RealmEmoji.objects.filter(realm_id=realm_id).exclude(
        file_name=None,
    )
    d = {}
    from zerver.lib.emoji import get_emoji_url

    for realm_emoji in query.all():
        author_id = realm_emoji.author_id
        assert realm_emoji.file_name is not None
        emoji_url = get_emoji_url(realm_emoji.file_name, realm_emoji.realm_id)

        emoji_dict: EmojiInfo = dict(
            id=str(realm_emoji.id),
            name=realm_emoji.name,
            source_url=emoji_url,
            deactivated=realm_emoji.deactivated,
            author_id=author_id,
            still_url=None,
        )

        if realm_emoji.is_animated:
            # For animated emoji, we include still_url with a static
            # version of the image, so that clients can display the
            # emoji in a less distracting (not animated) fashion when
            # desired.
            emoji_dict["still_url"] = get_emoji_url(
                realm_emoji.file_name, realm_emoji.realm_id, still=True
            )

        d[str(realm_emoji.id)] = emoji_dict

    return d


@cache_with_key(get_all_custom_emoji_for_realm_cache_key, timeout=3600 * 24 * 7)
def get_all_custom_emoji_for_realm(realm_id: int) -> Dict[str, EmojiInfo]:
    return get_all_custom_emoji_for_realm_uncached(realm_id)


def get_name_keyed_dict_for_active_realm_emoji(realm_id: int) -> Dict[str, EmojiInfo]:
    # It's important to use the cached version here.
    realm_emojis = get_all_custom_emoji_for_realm(realm_id)
    return {row["name"]: row for row in realm_emojis.values() if not row["deactivated"]}


def flush_realm_emoji(*, instance: RealmEmoji, **kwargs: object) -> None:
    if instance.file_name is None:
        # Because we construct RealmEmoji.file_name using the ID for
        # the RealmEmoji object, it will always have file_name=None,
        # and then it'll be updated with the actual filename as soon
        # as the upload completes successfully.
        #
        # Doing nothing when file_name=None is the best option, since
        # such an object shouldn't have been cached yet, and this
        # function will be called again when file_name is set.
        return
    realm_id = instance.realm_id
    cache_set(
        get_all_custom_emoji_for_realm_cache_key(realm_id),
        get_all_custom_emoji_for_realm_uncached(realm_id),
        timeout=3600 * 24 * 7,
    )


post_save.connect(flush_realm_emoji, sender=RealmEmoji)
post_delete.connect(flush_realm_emoji, sender=RealmEmoji)


def filter_pattern_validator(value: str) -> Pattern[str]:
    try:
        # Do not write errors to stderr (this still raises exceptions)
        options = re2.Options()
        options.log_errors = False

        regex = re2.compile(value, options=options)
    except re2.error as e:
        if len(e.args) >= 1:
            if isinstance(e.args[0], str):  # nocoverage
                raise ValidationError(_("Bad regular expression: {regex}").format(regex=e.args[0]))
            if isinstance(e.args[0], bytes):
                raise ValidationError(
                    _("Bad regular expression: {regex}").format(regex=e.args[0].decode())
                )
        raise ValidationError(_("Unknown regular expression error"))  # nocoverage

    return regex


def url_template_validator(value: str) -> None:
    """Validate as a URL template"""
    if not uri_template.validate(value):
        raise ValidationError(_("Invalid URL template."))


class RealmFilter(models.Model):
    """Realm-specific regular expressions to automatically linkify certain
    strings inside the Markdown processor.  See "Custom filters" in the settings UI.
    """

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    pattern = models.TextField()
    url_template = models.TextField(validators=[url_template_validator])
    # Linkifiers are applied in a message/topic in order; the processing order
    # is important when there are overlapping patterns.
    order = models.IntegerField(default=0)

    class Meta:
        unique_together = ("realm", "pattern")

    def __str__(self) -> str:
        return f"{self.realm.string_id}: {self.pattern} {self.url_template}"

    def clean(self) -> None:
        """Validate whether the set of parameters in the URL template
        match the set of parameters in the regular expression.

        Django's `full_clean` calls `clean_fields` followed by `clean` method
        and stores all ValidationErrors from all stages to return as JSON.
        """

        # Extract variables present in the pattern
        pattern = filter_pattern_validator(self.pattern)
        group_set = set(pattern.groupindex.keys())

        # Do not continue the check if the url template is invalid to begin with.
        # The ValidationError for invalid template will only be raised by the validator
        # set on the url_template field instead of here to avoid duplicates.
        if not uri_template.validate(self.url_template):
            return

        # Extract variables used in the URL template.
        template_variables_set = set(uri_template.URITemplate(self.url_template).variable_names)

        # Report patterns missing in linkifier pattern.
        missing_in_pattern_set = template_variables_set - group_set
        if len(missing_in_pattern_set) > 0:
            name = min(missing_in_pattern_set)
            raise ValidationError(
                _("Group %(name)r in URL template is not present in linkifier pattern."),
                params={"name": name},
            )

        missing_in_url_set = group_set - template_variables_set
        # Report patterns missing in URL template.
        if len(missing_in_url_set) > 0:
            # We just report the first missing pattern here. Users can
            # incrementally resolve errors if there are multiple
            # missing patterns.
            name = min(missing_in_url_set)
            raise ValidationError(
                _("Group %(name)r in linkifier pattern is not present in URL template."),
                params={"name": name},
            )


def get_linkifiers_cache_key(realm_id: int) -> str:
    return f"{cache.KEY_PREFIX}:all_linkifiers_for_realm:{realm_id}"


@return_same_value_during_entire_request
@cache_with_key(get_linkifiers_cache_key, timeout=3600 * 24 * 7)
def linkifiers_for_realm(realm_id: int) -> List[LinkifierDict]:
    return [
        LinkifierDict(
            pattern=linkifier.pattern,
            url_template=linkifier.url_template,
            id=linkifier.id,
        )
        for linkifier in RealmFilter.objects.filter(realm_id=realm_id).order_by("order")
    ]


def flush_linkifiers(*, instance: RealmFilter, **kwargs: object) -> None:
    realm_id = instance.realm_id
    cache_delete(get_linkifiers_cache_key(realm_id))
    flush_per_request_cache("linkifiers_for_realm")


post_save.connect(flush_linkifiers, sender=RealmFilter)
post_delete.connect(flush_linkifiers, sender=RealmFilter)


class RealmPlayground(models.Model):
    """Server side storage model to store playground information needed by our
    'view code in playground' feature in code blocks.
    """

    MAX_PYGMENTS_LANGUAGE_LENGTH = 40

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    url_template = models.TextField(validators=[url_template_validator])

    # User-visible display name used when configuring playgrounds in the settings page and
    # when displaying them in the playground links popover.
    name = models.TextField(db_index=True)

    # This stores the pygments lexer subclass names and not the aliases themselves.
    pygments_language = models.CharField(
        db_index=True,
        max_length=MAX_PYGMENTS_LANGUAGE_LENGTH,
        # We validate to see if this conforms to the character set allowed for a
        # language in the code block.
        validators=[
            RegexValidator(
                regex=r"^[ a-zA-Z0-9_+-./#]*$", message=_("Invalid characters in pygments language")
            )
        ],
    )

    class Meta:
        unique_together = (("realm", "pygments_language", "name"),)

    def __str__(self) -> str:
        return f"{self.realm.string_id}: {self.pygments_language} {self.name}"

    def clean(self) -> None:
        """Validate whether the URL template is valid for the playground,
        ensuring that "code" is the sole variable present in it.

        Django's `full_clean` calls `clean_fields` followed by `clean` method
        and stores all ValidationErrors from all stages to return as JSON.
        """

        # Do not continue the check if the url template is invalid to begin
        # with. The ValidationError for invalid template will only be raised by
        # the validator set on the url_template field instead of here to avoid
        # duplicates.
        if not uri_template.validate(self.url_template):
            return

        # Extract variables used in the URL template.
        template_variables = set(uri_template.URITemplate(self.url_template).variable_names)

        if "code" not in template_variables:
            raise ValidationError(_('Missing the required variable "code" in the URL template'))

        # The URL template should only contain a single variable, which is "code".
        if len(template_variables) != 1:
            raise ValidationError(
                _('"code" should be the only variable present in the URL template'),
            )


def get_realm_playgrounds(realm: Realm) -> List[RealmPlaygroundDict]:
    return [
        RealmPlaygroundDict(
            id=playground.id,
            name=playground.name,
            pygments_language=playground.pygments_language,
            url_template=playground.url_template,
        )
        for playground in RealmPlayground.objects.filter(realm=realm).all()
    ]


class Recipient(models.Model):
    """Represents an audience that can potentially receive messages in Zulip.

    This table essentially functions as a generic foreign key that
    allows Message.recipient_id to be a simple ForeignKey representing
    the audience for a message, while supporting the different types
    of audiences Zulip supports for a message.

    Recipient has just two attributes: The enum type, and a type_id,
    which is the ID of the UserProfile/Stream/Huddle object containing
    all the metadata for the audience. There are 3 recipient types:

    1. 1:1 direct message: The type_id is the ID of the UserProfile
       who will receive any message to this Recipient. The sender
       of such a message is represented separately.
    2. Stream message: The type_id is the ID of the associated Stream.
    3. Group direct message: In Zulip, group direct messages are
       represented by Huddle objects, which encode the set of users
       in the conversation. The type_id is the ID of the associated Huddle
       object; the set of users is usually retrieved via the Subscription
       table. See the Huddle model for details.

    See also the Subscription model, which stores which UserProfile
    objects are subscribed to which Recipient objects.
    """

    type_id = models.IntegerField(db_index=True)
    type = models.PositiveSmallIntegerField(db_index=True)
    # Valid types are {personal, stream, huddle}

    # The type for 1:1 direct messages.
    PERSONAL = 1
    # The type for stream messages.
    STREAM = 2
    # The type group direct messages.
    HUDDLE = 3

    class Meta:
        unique_together = ("type", "type_id")

    # N.B. If we used Django's choice=... we would get this for free (kinda)
    _type_names = {PERSONAL: "personal", STREAM: "stream", HUDDLE: "huddle"}

    def __str__(self) -> str:
        return f"{self.label()} ({self.type_id}, {self.type})"

    def label(self) -> str:
        if self.type == Recipient.STREAM:
            return Stream.objects.get(id=self.type_id).name
        else:
            return str(get_display_recipient(self))

    def type_name(self) -> str:
        # Raises KeyError if invalid
        return self._type_names[self.type]


class UserBaseSettings(models.Model):
    """This abstract class is the container for all preferences/personal
    settings for users that control the behavior of the application.

    It was extracted from UserProfile to support the RealmUserDefault
    model (i.e. allow individual realms to configure the default
    values of these preferences for new users in their organization).

    Changing the default value for a field declared here likely
    requires a migration to update all RealmUserDefault rows that had
    the old default value to have the new default value. Otherwise,
    the default change will only affect new users joining Realms
    created after the change.
    """

    ### Generic UI settings
    enter_sends = models.BooleanField(default=False)

    ### Display settings. ###
    # left_side_userlist was removed from the UI in Zulip 6.0; the
    # database model is being temporarily preserved in case we want to
    # restore a version of the setting, preserving who had it enabled.
    left_side_userlist = models.BooleanField(default=False)
    default_language = models.CharField(default="en", max_length=MAX_LANGUAGE_ID_LENGTH)
    # This setting controls which view is rendered first when Zulip loads.
    # Values for it are URL suffix after `#`.
    default_view = models.TextField(default="recent_topics")
    escape_navigates_to_default_view = models.BooleanField(default=True)
    dense_mode = models.BooleanField(default=True)
    fluid_layout_width = models.BooleanField(default=False)
    high_contrast_mode = models.BooleanField(default=False)
    translate_emoticons = models.BooleanField(default=False)
    display_emoji_reaction_users = models.BooleanField(default=True)
    twenty_four_hour_time = models.BooleanField(default=False)
    starred_message_counts = models.BooleanField(default=True)
    COLOR_SCHEME_AUTOMATIC = 1
    COLOR_SCHEME_NIGHT = 2
    COLOR_SCHEME_LIGHT = 3
    COLOR_SCHEME_CHOICES = [COLOR_SCHEME_AUTOMATIC, COLOR_SCHEME_NIGHT, COLOR_SCHEME_LIGHT]
    color_scheme = models.PositiveSmallIntegerField(default=COLOR_SCHEME_AUTOMATIC)

    # UI setting controlling Zulip's behavior of demoting in the sort
    # order and graying out streams with no recent traffic.  The
    # default behavior, automatic, enables this behavior once a user
    # is subscribed to 30+ streams in the web app.
    DEMOTE_STREAMS_AUTOMATIC = 1
    DEMOTE_STREAMS_ALWAYS = 2
    DEMOTE_STREAMS_NEVER = 3
    DEMOTE_STREAMS_CHOICES = [
        DEMOTE_STREAMS_AUTOMATIC,
        DEMOTE_STREAMS_ALWAYS,
        DEMOTE_STREAMS_NEVER,
    ]
    demote_inactive_streams = models.PositiveSmallIntegerField(default=DEMOTE_STREAMS_AUTOMATIC)

    # UI setting controlling whether or not the Zulip web app will
    # mark messages as read as it scrolls through the feed.

    MARK_READ_ON_SCROLL_ALWAYS = 1
    MARK_READ_ON_SCROLL_CONVERSATION_ONLY = 2
    MARK_READ_ON_SCROLL_NEVER = 3

    WEB_MARK_READ_ON_SCROLL_POLICY_CHOICES = [
        MARK_READ_ON_SCROLL_ALWAYS,
        MARK_READ_ON_SCROLL_CONVERSATION_ONLY,
        MARK_READ_ON_SCROLL_NEVER,
    ]

    web_mark_read_on_scroll_policy = models.SmallIntegerField(default=MARK_READ_ON_SCROLL_ALWAYS)

    # Emoji sets
    GOOGLE_EMOJISET = "google"
    GOOGLE_BLOB_EMOJISET = "google-blob"
    TEXT_EMOJISET = "text"
    TWITTER_EMOJISET = "twitter"
    EMOJISET_CHOICES = (
        (GOOGLE_EMOJISET, "Google"),
        (TWITTER_EMOJISET, "Twitter"),
        (TEXT_EMOJISET, "Plain text"),
        (GOOGLE_BLOB_EMOJISET, "Google blobs"),
    )
    emojiset = models.CharField(default=GOOGLE_EMOJISET, choices=EMOJISET_CHOICES, max_length=20)

    # User list style
    USER_LIST_STYLE_COMPACT = 1
    USER_LIST_STYLE_WITH_STATUS = 2
    USER_LIST_STYLE_WITH_AVATAR = 3
    USER_LIST_STYLE_CHOICES = [
        USER_LIST_STYLE_COMPACT,
        USER_LIST_STYLE_WITH_STATUS,
        USER_LIST_STYLE_WITH_AVATAR,
    ]
    user_list_style = models.PositiveSmallIntegerField(default=USER_LIST_STYLE_WITH_STATUS)

    # Show unread counts for
    WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_ALL_STREAMS = 1
    WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_UNMUTED_STREAMS = 2
    WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_NO_STREAMS = 3
    WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_CHOICES = [
        WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_ALL_STREAMS,
        WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_UNMUTED_STREAMS,
        WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_NO_STREAMS,
    ]
    web_stream_unreads_count_display_policy = models.PositiveSmallIntegerField(
        default=WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_UNMUTED_STREAMS
    )

    ### Notifications settings. ###

    email_notifications_batching_period_seconds = models.IntegerField(default=120)

    # Stream notifications.
    enable_stream_desktop_notifications = models.BooleanField(default=False)
    enable_stream_email_notifications = models.BooleanField(default=False)
    enable_stream_push_notifications = models.BooleanField(default=False)
    enable_stream_audible_notifications = models.BooleanField(default=False)
    notification_sound = models.CharField(max_length=20, default="zulip")
    wildcard_mentions_notify = models.BooleanField(default=True)

    # Followed Topics notifications.
    enable_followed_topic_desktop_notifications = models.BooleanField(default=True)
    enable_followed_topic_email_notifications = models.BooleanField(default=True)
    enable_followed_topic_push_notifications = models.BooleanField(default=True)
    enable_followed_topic_audible_notifications = models.BooleanField(default=True)
    enable_followed_topic_wildcard_mentions_notify = models.BooleanField(default=True)

    # Direct message + @-mention notifications.
    enable_desktop_notifications = models.BooleanField(default=True)
    pm_content_in_desktop_notifications = models.BooleanField(default=True)
    enable_sounds = models.BooleanField(default=True)
    enable_offline_email_notifications = models.BooleanField(default=True)
    message_content_in_email_notifications = models.BooleanField(default=True)
    enable_offline_push_notifications = models.BooleanField(default=True)
    enable_online_push_notifications = models.BooleanField(default=True)

    DESKTOP_ICON_COUNT_DISPLAY_MESSAGES = 1
    DESKTOP_ICON_COUNT_DISPLAY_NOTIFIABLE = 2
    DESKTOP_ICON_COUNT_DISPLAY_NONE = 3
    DESKTOP_ICON_COUNT_DISPLAY_CHOICES = [
        DESKTOP_ICON_COUNT_DISPLAY_MESSAGES,
        DESKTOP_ICON_COUNT_DISPLAY_NOTIFIABLE,
        DESKTOP_ICON_COUNT_DISPLAY_NONE,
    ]
    desktop_icon_count_display = models.PositiveSmallIntegerField(
        default=DESKTOP_ICON_COUNT_DISPLAY_MESSAGES
    )

    enable_digest_emails = models.BooleanField(default=True)
    enable_login_emails = models.BooleanField(default=True)
    enable_marketing_emails = models.BooleanField(default=True)
    presence_enabled = models.BooleanField(default=True)

    REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_AUTOMATIC = 1
    REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_ALWAYS = 2
    REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_NEVER = 3
    REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_CHOICES = [
        REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_AUTOMATIC,
        REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_ALWAYS,
        REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_NEVER,
    ]
    realm_name_in_email_notifications_policy = models.PositiveSmallIntegerField(
        default=REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_AUTOMATIC
    )

    # Whether or not the user wants to sync their drafts.
    enable_drafts_synchronization = models.BooleanField(default=True)

    # Privacy settings
    send_stream_typing_notifications = models.BooleanField(default=True)
    send_private_typing_notifications = models.BooleanField(default=True)
    send_read_receipts = models.BooleanField(default=True)

    # Who in the organization has access to users' actual email
    # addresses.  Controls whether the UserProfile.email field is
    # the same as UserProfile.delivery_email, or is instead a fake
    # generated value encoding the user ID and realm hostname.
    EMAIL_ADDRESS_VISIBILITY_EVERYONE = 1
    EMAIL_ADDRESS_VISIBILITY_MEMBERS = 2
    EMAIL_ADDRESS_VISIBILITY_ADMINS = 3
    EMAIL_ADDRESS_VISIBILITY_NOBODY = 4
    EMAIL_ADDRESS_VISIBILITY_MODERATORS = 5
    email_address_visibility = models.PositiveSmallIntegerField(
        default=EMAIL_ADDRESS_VISIBILITY_EVERYONE,
    )

    EMAIL_ADDRESS_VISIBILITY_ID_TO_NAME_MAP = {
        EMAIL_ADDRESS_VISIBILITY_EVERYONE: gettext_lazy("Admins, moderators, members and guests"),
        EMAIL_ADDRESS_VISIBILITY_MEMBERS: gettext_lazy("Admins, moderators and members"),
        EMAIL_ADDRESS_VISIBILITY_MODERATORS: gettext_lazy("Admins and moderators"),
        EMAIL_ADDRESS_VISIBILITY_ADMINS: gettext_lazy("Admins only"),
        EMAIL_ADDRESS_VISIBILITY_NOBODY: gettext_lazy("Nobody"),
    }

    EMAIL_ADDRESS_VISIBILITY_TYPES = list(EMAIL_ADDRESS_VISIBILITY_ID_TO_NAME_MAP.keys())

    display_settings_legacy = dict(
        # Don't add anything new to this legacy dict.
        # Instead, see `modern_settings` below.
        color_scheme=int,
        default_language=str,
        default_view=str,
        demote_inactive_streams=int,
        dense_mode=bool,
        emojiset=str,
        enable_drafts_synchronization=bool,
        enter_sends=bool,
        fluid_layout_width=bool,
        high_contrast_mode=bool,
        left_side_userlist=bool,
        starred_message_counts=bool,
        translate_emoticons=bool,
        twenty_four_hour_time=bool,
    )

    notification_settings_legacy = dict(
        # Don't add anything new to this legacy dict.
        # Instead, see `modern_notification_settings` below.
        desktop_icon_count_display=int,
        email_notifications_batching_period_seconds=int,
        enable_desktop_notifications=bool,
        enable_digest_emails=bool,
        enable_login_emails=bool,
        enable_marketing_emails=bool,
        enable_offline_email_notifications=bool,
        enable_offline_push_notifications=bool,
        enable_online_push_notifications=bool,
        enable_sounds=bool,
        enable_stream_audible_notifications=bool,
        enable_stream_desktop_notifications=bool,
        enable_stream_email_notifications=bool,
        enable_stream_push_notifications=bool,
        message_content_in_email_notifications=bool,
        notification_sound=str,
        pm_content_in_desktop_notifications=bool,
        presence_enabled=bool,
        realm_name_in_email_notifications_policy=int,
        wildcard_mentions_notify=bool,
    )

    modern_settings = dict(
        # Add new general settings here.
        display_emoji_reaction_users=bool,
        email_address_visibility=int,
        escape_navigates_to_default_view=bool,
        send_private_typing_notifications=bool,
        send_read_receipts=bool,
        send_stream_typing_notifications=bool,
        web_mark_read_on_scroll_policy=int,
        user_list_style=int,
        web_stream_unreads_count_display_policy=int,
    )

    modern_notification_settings: Dict[str, Any] = dict(
        # Add new notification settings here.
        enable_followed_topic_desktop_notifications=bool,
        enable_followed_topic_email_notifications=bool,
        enable_followed_topic_push_notifications=bool,
        enable_followed_topic_audible_notifications=bool,
        enable_followed_topic_wildcard_mentions_notify=bool,
    )

    notification_setting_types = {
        **notification_settings_legacy,
        **modern_notification_settings,
    }

    # Define the types of the various automatically managed properties
    property_types = {
        **display_settings_legacy,
        **notification_setting_types,
        **modern_settings,
    }

    class Meta:
        abstract = True

    @staticmethod
    def emojiset_choices() -> List[Dict[str, str]]:
        return [
            dict(key=emojiset[0], text=emojiset[1]) for emojiset in UserProfile.EMOJISET_CHOICES
        ]


class RealmUserDefault(UserBaseSettings):
    """This table stores realm-level default values for user preferences
    like notification settings, used when creating a new user account.
    """

    realm = models.OneToOneField(Realm, on_delete=CASCADE)


class UserProfile(AbstractBaseUser, PermissionsMixin, UserBaseSettings):  # type: ignore[django-manager-missing] # django-stubs cannot resolve the custom CTEManager yet https://github.com/typeddjango/django-stubs/issues/1023
    USERNAME_FIELD = "email"
    MAX_NAME_LENGTH = 100
    MIN_NAME_LENGTH = 2
    API_KEY_LENGTH = 32
    NAME_INVALID_CHARS = ["*", "`", "\\", ">", '"', "@"]

    DEFAULT_BOT = 1
    """
    Incoming webhook bots are limited to only sending messages via webhooks.
    Thus, it is less of a security risk to expose their API keys to third-party services,
    since they can't be used to read messages.
    """
    INCOMING_WEBHOOK_BOT = 2
    # This value is also being used in web/src/settings_bots.js.
    # On updating it here, update it there as well.
    OUTGOING_WEBHOOK_BOT = 3
    """
    Embedded bots run within the Zulip server itself; events are added to the
    embedded_bots queue and then handled by a QueueProcessingWorker.
    """
    EMBEDDED_BOT = 4

    BOT_TYPES = {
        DEFAULT_BOT: "Generic bot",
        INCOMING_WEBHOOK_BOT: "Incoming webhook",
        OUTGOING_WEBHOOK_BOT: "Outgoing webhook",
        EMBEDDED_BOT: "Embedded bot",
    }

    SERVICE_BOT_TYPES = [
        OUTGOING_WEBHOOK_BOT,
        EMBEDDED_BOT,
    ]

    # For historical reasons, Zulip has two email fields.  The
    # `delivery_email` field is the user's email address, where all
    # email notifications will be sent, and is used for all
    # authentication use cases.
    #
    # The `email` field is the same as delivery_email in organizations
    # with EMAIL_ADDRESS_VISIBILITY_EVERYONE.  For other
    # organizations, it will be a unique value of the form
    # user1234@example.com.  This field exists for backwards
    # compatibility in Zulip APIs where users are referred to by their
    # email address, not their ID; it should be used in all API use cases.
    #
    # Both fields are unique within a realm (in a case-insensitive
    # fashion). Since Django's unique_together is case sensitive, this
    # is enforced via SQL indexes created by
    # zerver/migrations/0295_case_insensitive_email_indexes.py.
    delivery_email = models.EmailField(blank=False, db_index=True)
    email = models.EmailField(blank=False, db_index=True)

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    # Foreign key to the Recipient object for PERSONAL type messages to this user.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)

    # The user's name.  We prefer the model of a full_name
    # over first+last because cultures vary on how many
    # names one has, whether the family name is first or last, etc.
    # It also allows organizations to encode a bit of non-name data in
    # the "name" attribute if desired, like gender pronouns,
    # graduation year, etc.
    full_name = models.CharField(max_length=MAX_NAME_LENGTH)

    date_joined = models.DateTimeField(default=timezone_now)

    # Terms of Service version number that this user has accepted. We
    # use the special value TOS_VERSION_BEFORE_FIRST_LOGIN for users
    # whose account was created without direct user interaction (via
    # the API or a data import), and null for users whose account is
    # fully created on servers that do not have a configured ToS.
    TOS_VERSION_BEFORE_FIRST_LOGIN = "-1"
    tos_version = models.CharField(null=True, max_length=10)
    api_key = models.CharField(max_length=API_KEY_LENGTH, default=generate_api_key, unique=True)

    # A UUID generated on user creation. Introduced primarily to
    # provide a unique key for a user for the mobile push
    # notifications bouncer that will not have collisions after doing
    # a data export and then import.
    uuid = models.UUIDField(default=uuid4, unique=True)

    # Whether the user has access to server-level administrator pages, like /activity
    is_staff = models.BooleanField(default=False)

    # For a normal user, this is True unless the user or an admin has
    # deactivated their account.  The name comes from Django; this field
    # isn't related to presence or to whether the user has recently used Zulip.
    #
    # See also `long_term_idle`.
    is_active = models.BooleanField(default=True, db_index=True)

    is_billing_admin = models.BooleanField(default=False, db_index=True)

    is_bot = models.BooleanField(default=False, db_index=True)
    bot_type = models.PositiveSmallIntegerField(null=True, db_index=True)
    bot_owner = models.ForeignKey("self", null=True, on_delete=models.SET_NULL)

    # Each role has a superset of the permissions of the next higher
    # numbered role.  When adding new roles, leave enough space for
    # future roles to be inserted between currently adjacent
    # roles. These constants appear in RealmAuditLog.extra_data, so
    # changes to them will require a migration of RealmAuditLog.
    ROLE_REALM_OWNER = 100
    ROLE_REALM_ADMINISTRATOR = 200
    ROLE_MODERATOR = 300
    ROLE_MEMBER = 400
    ROLE_GUEST = 600
    role = models.PositiveSmallIntegerField(default=ROLE_MEMBER, db_index=True)

    ROLE_TYPES = [
        ROLE_REALM_OWNER,
        ROLE_REALM_ADMINISTRATOR,
        ROLE_MODERATOR,
        ROLE_MEMBER,
        ROLE_GUEST,
    ]

    # Whether the user has been "soft-deactivated" due to weeks of inactivity.
    # For these users we avoid doing UserMessage table work, as an optimization
    # for large Zulip organizations with lots of single-visit users.
    long_term_idle = models.BooleanField(default=False, db_index=True)

    # When we last added basic UserMessage rows for a long_term_idle user.
    last_active_message_id = models.IntegerField(null=True)

    # Mirror dummies are fake (!is_active) users used to provide
    # message senders in our cross-protocol Zephyr<->Zulip content
    # mirroring integration, so that we can display mirrored content
    # like native Zulip messages (with a name + avatar, etc.).
    is_mirror_dummy = models.BooleanField(default=False)

    # Users with this flag set are allowed to forge messages as sent by another
    # user and to send to private streams; also used for Zephyr/Jabber mirroring.
    can_forge_sender = models.BooleanField(default=False, db_index=True)
    # Users with this flag set can create other users via API.
    can_create_users = models.BooleanField(default=False, db_index=True)

    # Used for rate-limiting certain automated messages generated by bots
    last_reminder = models.DateTimeField(default=None, null=True)

    # Minutes to wait before warning a bot owner that their bot sent a message
    # to a nonexistent stream
    BOT_OWNER_STREAM_ALERT_WAITPERIOD = 1

    # API rate limits, formatted as a comma-separated list of range:max pairs
    rate_limits = models.CharField(default="", max_length=100)

    # Default streams for some deprecated/legacy classes of bot users.
    default_sending_stream = models.ForeignKey(
        "zerver.Stream",
        null=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    default_events_register_stream = models.ForeignKey(
        "zerver.Stream",
        null=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    default_all_public_streams = models.BooleanField(default=False)

    # A time zone name from the `tzdata` database, as found in zoneinfo.available_timezones().
    #
    # The longest existing name is 32 characters long, so max_length=40 seems
    # like a safe choice.
    #
    # In Django, the convention is to use an empty string instead of NULL/None
    # for text-based fields. For more information, see
    # https://docs.djangoproject.com/en/3.2/ref/models/fields/#django.db.models.Field.null.
    timezone = models.CharField(max_length=40, default="")

    AVATAR_FROM_GRAVATAR = "G"
    AVATAR_FROM_USER = "U"
    AVATAR_SOURCES = (
        (AVATAR_FROM_GRAVATAR, "Hosted by Gravatar"),
        (AVATAR_FROM_USER, "Uploaded by user"),
    )
    avatar_source = models.CharField(
        default=AVATAR_FROM_GRAVATAR, choices=AVATAR_SOURCES, max_length=1
    )
    avatar_version = models.PositiveSmallIntegerField(default=1)
    avatar_hash = models.CharField(null=True, max_length=64)

    TUTORIAL_WAITING = "W"
    TUTORIAL_STARTED = "S"
    TUTORIAL_FINISHED = "F"
    TUTORIAL_STATES = (
        (TUTORIAL_WAITING, "Waiting"),
        (TUTORIAL_STARTED, "Started"),
        (TUTORIAL_FINISHED, "Finished"),
    )
    tutorial_status = models.CharField(
        default=TUTORIAL_WAITING, choices=TUTORIAL_STATES, max_length=1
    )

    # Contains serialized JSON of the form:
    #    [("step 1", true), ("step 2", false)]
    # where the second element of each tuple is if the step has been
    # completed.
    onboarding_steps = models.TextField(default="[]")

    zoom_token = models.JSONField(default=None, null=True)

    objects = UserManager()

    ROLE_ID_TO_NAME_MAP = {
        ROLE_REALM_OWNER: gettext_lazy("Organization owner"),
        ROLE_REALM_ADMINISTRATOR: gettext_lazy("Organization administrator"),
        ROLE_MODERATOR: gettext_lazy("Moderator"),
        ROLE_MEMBER: gettext_lazy("Member"),
        ROLE_GUEST: gettext_lazy("Guest"),
    }

    def get_role_name(self) -> str:
        return str(self.ROLE_ID_TO_NAME_MAP[self.role])

    def profile_data(self) -> ProfileData:
        values = CustomProfileFieldValue.objects.filter(user_profile=self)
        user_data = {
            v.field_id: {"value": v.value, "rendered_value": v.rendered_value} for v in values
        }
        data: ProfileData = []
        for field in custom_profile_fields_for_realm(self.realm_id):
            field_values = user_data.get(field.id, None)
            if field_values:
                value, rendered_value = field_values.get("value"), field_values.get(
                    "rendered_value"
                )
            else:
                value, rendered_value = None, None
            field_type = field.field_type
            if value is not None:
                converter = field.FIELD_CONVERTERS[field_type]
                value = converter(value)

            field_data = field.as_dict()
            data.append(
                {
                    "id": field_data["id"],
                    "name": field_data["name"],
                    "type": field_data["type"],
                    "hint": field_data["hint"],
                    "field_data": field_data["field_data"],
                    "order": field_data["order"],
                    "value": value,
                    "rendered_value": rendered_value,
                }
            )

        return data

    def can_admin_user(self, target_user: "UserProfile") -> bool:
        """Returns whether this user has permission to modify target_user"""
        if target_user.bot_owner_id == self.id:
            return True
        elif self.is_realm_admin and self.realm == target_user.realm:
            return True
        else:
            return False

    def __str__(self) -> str:
        return f"{self.email} {self.realm!r}"

    @property
    def is_provisional_member(self) -> bool:
        if self.is_moderator:
            return False
        diff = (timezone_now() - self.date_joined).days
        if diff < self.realm.waiting_period_threshold:
            return True
        return False

    @property
    def is_realm_admin(self) -> bool:
        return self.role in (UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_REALM_OWNER)

    @is_realm_admin.setter
    def is_realm_admin(self, value: bool) -> None:
        if value:
            self.role = UserProfile.ROLE_REALM_ADMINISTRATOR
        elif self.role == UserProfile.ROLE_REALM_ADMINISTRATOR:
            # We need to be careful to not accidentally change
            # ROLE_GUEST to ROLE_MEMBER here.
            self.role = UserProfile.ROLE_MEMBER

    @property
    def has_billing_access(self) -> bool:
        return self.is_realm_owner or self.is_billing_admin

    @property
    def is_realm_owner(self) -> bool:
        return self.role == UserProfile.ROLE_REALM_OWNER

    @is_realm_owner.setter
    def is_realm_owner(self, value: bool) -> None:
        if value:
            self.role = UserProfile.ROLE_REALM_OWNER
        elif self.role == UserProfile.ROLE_REALM_OWNER:
            # We need to be careful to not accidentally change
            # ROLE_GUEST to ROLE_MEMBER here.
            self.role = UserProfile.ROLE_MEMBER

    @property
    def is_guest(self) -> bool:
        return self.role == UserProfile.ROLE_GUEST

    @is_guest.setter
    def is_guest(self, value: bool) -> None:
        if value:
            self.role = UserProfile.ROLE_GUEST
        elif self.role == UserProfile.ROLE_GUEST:
            # We need to be careful to not accidentally change
            # ROLE_REALM_ADMINISTRATOR to ROLE_MEMBER here.
            self.role = UserProfile.ROLE_MEMBER

    @property
    def is_moderator(self) -> bool:
        return self.role == UserProfile.ROLE_MODERATOR

    @is_moderator.setter
    def is_moderator(self, value: bool) -> None:
        if value:
            self.role = UserProfile.ROLE_MODERATOR
        elif self.role == UserProfile.ROLE_MODERATOR:
            # We need to be careful to not accidentally change
            # ROLE_GUEST to ROLE_MEMBER here.
            self.role = UserProfile.ROLE_MEMBER

    @property
    def is_incoming_webhook(self) -> bool:
        return self.bot_type == UserProfile.INCOMING_WEBHOOK_BOT

    @property
    def allowed_bot_types(self) -> List[int]:
        allowed_bot_types = []
        if (
            self.is_realm_admin
            or self.realm.bot_creation_policy != Realm.BOT_CREATION_LIMIT_GENERIC_BOTS
        ):
            allowed_bot_types.append(UserProfile.DEFAULT_BOT)
        allowed_bot_types += [
            UserProfile.INCOMING_WEBHOOK_BOT,
            UserProfile.OUTGOING_WEBHOOK_BOT,
        ]
        if settings.EMBEDDED_BOTS_ENABLED:
            allowed_bot_types.append(UserProfile.EMBEDDED_BOT)
        return allowed_bot_types

    def email_address_is_realm_public(self) -> bool:
        # Bots always have EMAIL_ADDRESS_VISIBILITY_EVERYONE.
        if self.email_address_visibility == UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE:
            return True
        return False

    def has_permission(self, policy_name: str) -> bool:
        from zerver.lib.user_groups import is_user_in_group

        if policy_name not in [
            "add_custom_emoji_policy",
            "create_multiuse_invite_group",
            "create_private_stream_policy",
            "create_public_stream_policy",
            "create_web_public_stream_policy",
            "delete_own_message_policy",
            "edit_topic_policy",
            "invite_to_stream_policy",
            "invite_to_realm_policy",
            "move_messages_between_streams_policy",
            "user_group_edit_policy",
        ]:
            raise AssertionError("Invalid policy")

        if policy_name in Realm.REALM_PERMISSION_GROUP_SETTINGS:
            allowed_user_group = getattr(self.realm, policy_name)
            return is_user_in_group(allowed_user_group, self)

        policy_value = getattr(self.realm, policy_name)
        if policy_value == Realm.POLICY_NOBODY:
            return False

        if policy_value == Realm.POLICY_EVERYONE:
            return True

        if self.is_realm_owner:
            return True

        if policy_value == Realm.POLICY_OWNERS_ONLY:
            return False

        if self.is_realm_admin:
            return True

        if policy_value == Realm.POLICY_ADMINS_ONLY:
            return False

        if self.is_moderator:
            return True

        if policy_value == Realm.POLICY_MODERATORS_ONLY:
            return False

        if self.is_guest:
            return False

        if policy_value == Realm.POLICY_MEMBERS_ONLY:
            return True

        assert policy_value == Realm.POLICY_FULL_MEMBERS_ONLY
        return not self.is_provisional_member

    def can_create_public_streams(self) -> bool:
        return self.has_permission("create_public_stream_policy")

    def can_create_private_streams(self) -> bool:
        return self.has_permission("create_private_stream_policy")

    def can_create_web_public_streams(self) -> bool:
        if not self.realm.web_public_streams_enabled():
            return False
        return self.has_permission("create_web_public_stream_policy")

    def can_subscribe_other_users(self) -> bool:
        return self.has_permission("invite_to_stream_policy")

    def can_invite_users_by_email(self) -> bool:
        return self.has_permission("invite_to_realm_policy")

    def can_create_multiuse_invite_to_realm(self) -> bool:
        return self.has_permission("create_multiuse_invite_group")

    def can_move_messages_between_streams(self) -> bool:
        return self.has_permission("move_messages_between_streams_policy")

    def can_edit_user_groups(self) -> bool:
        return self.has_permission("user_group_edit_policy")

    def can_move_messages_to_another_topic(self) -> bool:
        return self.has_permission("edit_topic_policy")

    def can_add_custom_emoji(self) -> bool:
        return self.has_permission("add_custom_emoji_policy")

    def can_delete_own_message(self) -> bool:
        return self.has_permission("delete_own_message_policy")

    def can_access_public_streams(self) -> bool:
        return not (self.is_guest or self.realm.is_zephyr_mirror_realm)

    def major_tos_version(self) -> int:
        if self.tos_version is not None:
            return int(self.tos_version.split(".")[0])
        else:
            return -1

    def format_requester_for_logs(self) -> str:
        return "{}@{}".format(self.id, self.realm.string_id or "root")

    def set_password(self, password: Optional[str]) -> None:
        if password is None:
            self.set_unusable_password()
            return

        from zproject.backends import check_password_strength

        if not check_password_strength(password):
            raise PasswordTooWeakError

        super().set_password(password)

    class Meta:
        indexes = [
            models.Index(Upper("email"), name="upper_userprofile_email_idx"),
        ]


class PasswordTooWeakError(Exception):
    pass


class UserGroup(models.Model):  # type: ignore[django-manager-missing] # django-stubs cannot resolve the custom CTEManager yet https://github.com/typeddjango/django-stubs/issues/1023
    MAX_NAME_LENGTH = 100
    INVALID_NAME_PREFIXES = ["@", "role:", "user:", "stream:", "channel:"]

    objects: CTEManager = CTEManager()
    name = models.CharField(max_length=MAX_NAME_LENGTH)
    direct_members = models.ManyToManyField(
        UserProfile, through="UserGroupMembership", related_name="direct_groups"
    )
    direct_subgroups = models.ManyToManyField(
        "self",
        symmetrical=False,
        through="GroupGroupMembership",
        through_fields=("supergroup", "subgroup"),
        related_name="direct_supergroups",
    )
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    description = models.TextField(default="")
    is_system_group = models.BooleanField(default=False)

    can_mention_group = models.ForeignKey("self", on_delete=models.RESTRICT)

    # Names for system groups.
    FULL_MEMBERS_GROUP_NAME = "role:fullmembers"
    EVERYONE_ON_INTERNET_GROUP_NAME = "role:internet"
    OWNERS_GROUP_NAME = "role:owners"
    ADMINISTRATORS_GROUP_NAME = "role:administrators"
    MODERATORS_GROUP_NAME = "role:moderators"
    MEMBERS_GROUP_NAME = "role:members"
    EVERYONE_GROUP_NAME = "role:everyone"
    NOBODY_GROUP_NAME = "role:nobody"

    # We do not have "Full members" and "Everyone on the internet"
    # group here since there isn't a separate role value for full
    # members and spectators.
    SYSTEM_USER_GROUP_ROLE_MAP = {
        UserProfile.ROLE_REALM_OWNER: {
            "name": OWNERS_GROUP_NAME,
            "description": "Owners of this organization",
        },
        UserProfile.ROLE_REALM_ADMINISTRATOR: {
            "name": ADMINISTRATORS_GROUP_NAME,
            "description": "Administrators of this organization, including owners",
        },
        UserProfile.ROLE_MODERATOR: {
            "name": MODERATORS_GROUP_NAME,
            "description": "Moderators of this organization, including administrators",
        },
        UserProfile.ROLE_MEMBER: {
            "name": MEMBERS_GROUP_NAME,
            "description": "Members of this organization, not including guests",
        },
        UserProfile.ROLE_GUEST: {
            "name": EVERYONE_GROUP_NAME,
            "description": "Everyone in this organization, including guests",
        },
    }

    GROUP_PERMISSION_SETTINGS = {
        "can_mention_group": GroupPermissionSetting(
            require_system_group=False,
            allow_internet_group=False,
            allow_owners_group=False,
            allow_nobody_group=True,
            allow_everyone_group=True,
            default_group_name=EVERYONE_GROUP_NAME,
            default_for_system_groups=NOBODY_GROUP_NAME,
            id_field_name="can_mention_group_id",
        ),
    }

    class Meta:
        unique_together = (("realm", "name"),)


class UserGroupMembership(models.Model):
    user_group = models.ForeignKey(UserGroup, on_delete=CASCADE, related_name="+")
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE, related_name="+")

    class Meta:
        unique_together = (("user_group", "user_profile"),)


class GroupGroupMembership(models.Model):
    supergroup = models.ForeignKey(UserGroup, on_delete=CASCADE, related_name="+")
    subgroup = models.ForeignKey(UserGroup, on_delete=CASCADE, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["supergroup", "subgroup"], name="zerver_groupgroupmembership_uniq"
            )
        ]


def remote_user_to_email(remote_user: str) -> str:
    if settings.SSO_APPEND_DOMAIN is not None:
        return Address(username=remote_user, domain=settings.SSO_APPEND_DOMAIN).addr_spec
    return remote_user


# Make sure we flush the UserProfile object from our remote cache
# whenever we save it.
post_save.connect(flush_user_profile, sender=UserProfile)


class PreregistrationRealm(models.Model):
    """Data on a partially created realm entered by a user who has
    completed the "new organization" form. Used to transfer the user's
    selections from the pre-confirmation "new organization" form to
    the post-confirmation user registration form.

    Note that the values stored here may not match those of the
    created realm (in the event the user creates a realm at all),
    because we allow the user to edit these values in the registration
    form (and in fact the user will be required to do so if the
    `string_id` is claimed by another realm before registraiton is
    completed).
    """

    name = models.CharField(max_length=Realm.MAX_REALM_NAME_LENGTH)
    org_type = models.PositiveSmallIntegerField(
        default=Realm.ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
    )
    string_id = models.CharField(max_length=Realm.MAX_REALM_SUBDOMAIN_LENGTH)
    email = models.EmailField()

    confirmation = GenericRelation("confirmation.Confirmation", related_query_name="prereg_realm")
    status = models.IntegerField(default=0)

    # The Realm created upon completion of the registration
    # for this PregistrationRealm
    created_realm = models.ForeignKey(Realm, null=True, related_name="+", on_delete=models.SET_NULL)

    # The UserProfile created upon completion of the registration
    # for this PregistrationRealm
    created_user = models.ForeignKey(
        UserProfile, null=True, related_name="+", on_delete=models.SET_NULL
    )


class PreregistrationUser(models.Model):
    # Data on a partially created user, before the completion of
    # registration.  This is used in at least three major code paths:
    # * Realm creation, in which case realm is None.
    #
    # * Invitations, in which case referred_by will always be set.
    #
    # * Social authentication signup, where it's used to store data
    #   from the authentication step and pass it to the registration
    #   form.

    email = models.EmailField()

    confirmation = GenericRelation("confirmation.Confirmation", related_query_name="prereg_user")
    # If the pre-registration process provides a suggested full name for this user,
    # store it here to use it to prepopulate the full name field in the registration form:
    full_name = models.CharField(max_length=UserProfile.MAX_NAME_LENGTH, null=True)
    full_name_validated = models.BooleanField(default=False)
    referred_by = models.ForeignKey(UserProfile, null=True, on_delete=CASCADE)
    streams = models.ManyToManyField("Stream")
    invited_at = models.DateTimeField(auto_now=True)
    realm_creation = models.BooleanField(default=False)
    # Indicates whether the user needs a password.  Users who were
    # created via SSO style auth (e.g. GitHub/Google) generally do not.
    password_required = models.BooleanField(default=True)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    # The realm should only ever be None for PreregistrationUser
    # objects created as part of realm creation.
    realm = models.ForeignKey(Realm, null=True, on_delete=CASCADE)

    # These values should be consistent with the values
    # in settings_config.user_role_values.
    INVITE_AS = dict(
        REALM_OWNER=100,
        REALM_ADMIN=200,
        MODERATOR=300,
        MEMBER=400,
        GUEST_USER=600,
    )
    invited_as = models.PositiveSmallIntegerField(default=INVITE_AS["MEMBER"])

    multiuse_invite = models.ForeignKey("MultiuseInvite", null=True, on_delete=models.SET_NULL)

    # The UserProfile created upon completion of the registration
    # for this PregistrationUser
    created_user = models.ForeignKey(
        UserProfile, null=True, related_name="+", on_delete=models.SET_NULL
    )

    class Meta:
        indexes = [
            models.Index(Upper("email"), name="upper_preregistration_email_idx"),
        ]


def filter_to_valid_prereg_users(
    query: QuerySet[PreregistrationUser],
    invite_expires_in_minutes: Union[Optional[int], UnspecifiedValue] = UnspecifiedValue(),
) -> QuerySet[PreregistrationUser]:
    """
    If invite_expires_in_days is specified, we return only those PreregistrationUser
    objects that were created at most that many days in the past.
    """
    used_value = confirmation_settings.STATUS_USED
    revoked_value = confirmation_settings.STATUS_REVOKED

    query = query.exclude(status__in=[used_value, revoked_value])
    if invite_expires_in_minutes is None:
        # Since invite_expires_in_minutes is None, we're invitation will never
        # expire, we do not need to check anything else and can simply return
        # after excluding objects with active and revoked status.
        return query

    assert invite_expires_in_minutes is not None
    if not isinstance(invite_expires_in_minutes, UnspecifiedValue):
        lowest_datetime = timezone_now() - datetime.timedelta(minutes=invite_expires_in_minutes)
        return query.filter(invited_at__gte=lowest_datetime)
    else:
        return query.filter(
            Q(confirmation__expiry_date=None) | Q(confirmation__expiry_date__gte=timezone_now())
        )


class MultiuseInvite(models.Model):
    referred_by = models.ForeignKey(UserProfile, on_delete=CASCADE)
    streams = models.ManyToManyField("Stream")
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    invited_as = models.PositiveSmallIntegerField(default=PreregistrationUser.INVITE_AS["MEMBER"])

    # status for tracking whether the invite has been revoked.
    # If revoked, set to confirmation.settings.STATUS_REVOKED.
    # STATUS_USED is not supported, because these objects are supposed
    # to be usable multiple times.
    status = models.IntegerField(default=0)


class EmailChangeStatus(models.Model):
    new_email = models.EmailField()
    old_email = models.EmailField()
    updated_at = models.DateTimeField(auto_now=True)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    realm = models.ForeignKey(Realm, on_delete=CASCADE)


class RealmReactivationStatus(models.Model):
    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    realm = models.ForeignKey(Realm, on_delete=CASCADE)


class AbstractPushDeviceToken(models.Model):
    APNS = 1
    GCM = 2

    KINDS = (
        (APNS, "apns"),
        (GCM, "gcm"),
    )

    kind = models.PositiveSmallIntegerField(choices=KINDS)

    # The token is a unique device-specific token that is
    # sent to us from each device:
    #   - APNS token if kind == APNS
    #   - GCM registration id if kind == GCM
    token = models.CharField(max_length=4096, db_index=True)

    # TODO: last_updated should be renamed date_created, since it is
    # no longer maintained as a last_updated value.
    last_updated = models.DateTimeField(auto_now=True)

    # [optional] Contains the app id of the device if it is an iOS device
    ios_app_id = models.TextField(null=True)

    class Meta:
        abstract = True


class PushDeviceToken(AbstractPushDeviceToken):
    # The user whose device this is
    user = models.ForeignKey(UserProfile, db_index=True, on_delete=CASCADE)

    class Meta:
        unique_together = ("user", "kind", "token")


def generate_email_token_for_stream() -> str:
    return secrets.token_hex(16)


class Stream(models.Model):
    MAX_NAME_LENGTH = 60
    MAX_DESCRIPTION_LENGTH = 1024

    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)
    realm = models.ForeignKey(Realm, db_index=True, on_delete=CASCADE)
    date_created = models.DateTimeField(default=timezone_now)
    deactivated = models.BooleanField(default=False)
    description = models.CharField(max_length=MAX_DESCRIPTION_LENGTH, default="")
    rendered_description = models.TextField(default="")

    # Foreign key to the Recipient object for STREAM type messages to this stream.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)

    # Various permission policy configurations
    PERMISSION_POLICIES: Dict[str, Dict[str, Any]] = {
        "web_public": {
            "invite_only": False,
            "history_public_to_subscribers": True,
            "is_web_public": True,
            "policy_name": gettext_lazy("Web-public"),
        },
        "public": {
            "invite_only": False,
            "history_public_to_subscribers": True,
            "is_web_public": False,
            "policy_name": gettext_lazy("Public"),
        },
        "private_shared_history": {
            "invite_only": True,
            "history_public_to_subscribers": True,
            "is_web_public": False,
            "policy_name": gettext_lazy("Private, shared history"),
        },
        "private_protected_history": {
            "invite_only": True,
            "history_public_to_subscribers": False,
            "is_web_public": False,
            "policy_name": gettext_lazy("Private, protected history"),
        },
        # Public streams with protected history are currently only
        # available in Zephyr realms
        "public_protected_history": {
            "invite_only": False,
            "history_public_to_subscribers": False,
            "is_web_public": False,
            "policy_name": gettext_lazy("Public, protected history"),
        },
    }
    invite_only = models.BooleanField(default=False)
    history_public_to_subscribers = models.BooleanField(default=True)

    # Whether this stream's content should be published by the web-public archive features
    is_web_public = models.BooleanField(default=False)

    STREAM_POST_POLICY_EVERYONE = 1
    STREAM_POST_POLICY_ADMINS = 2
    STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS = 3
    STREAM_POST_POLICY_MODERATORS = 4
    # TODO: Implement policy to restrict posting to a user group or admins.

    # Who in the organization has permission to send messages to this stream.
    stream_post_policy = models.PositiveSmallIntegerField(default=STREAM_POST_POLICY_EVERYONE)
    POST_POLICIES: Dict[int, StrPromise] = {
        # These strings should match the strings in the
        # stream_post_policy_values object in stream_data.js.
        STREAM_POST_POLICY_EVERYONE: gettext_lazy("All stream members can post"),
        STREAM_POST_POLICY_ADMINS: gettext_lazy("Only organization administrators can post"),
        STREAM_POST_POLICY_MODERATORS: gettext_lazy(
            "Only organization administrators and moderators can post"
        ),
        STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS: gettext_lazy(
            "Only organization full members can post"
        ),
    }
    STREAM_POST_POLICY_TYPES = list(POST_POLICIES.keys())

    # The unique thing about Zephyr public streams is that we never list their
    # users.  We may try to generalize this concept later, but for now
    # we just use a concrete field.  (Zephyr public streams aren't exactly like
    # invite-only streams--while both are private in terms of listing users,
    # for Zephyr we don't even list users to stream members, yet membership
    # is more public in the sense that you don't need a Zulip invite to join.
    # This field is populated directly from UserProfile.is_zephyr_mirror_realm,
    # and the reason for denormalizing field is performance.
    is_in_zephyr_realm = models.BooleanField(default=False)

    # Used by the e-mail forwarder. The e-mail RFC specifies a maximum
    # e-mail length of 254, and our max stream length is 30, so we
    # have plenty of room for the token.
    email_token = models.CharField(
        max_length=32,
        default=generate_email_token_for_stream,
        unique=True,
    )

    # For old messages being automatically deleted.
    # Value NULL means "use retention policy of the realm".
    # Value -1 means "disable retention policy for this stream unconditionally".
    # Non-negative values have the natural meaning of "archive messages older than <value> days".
    MESSAGE_RETENTION_SPECIAL_VALUES_MAP = {
        "unlimited": -1,
        "realm_default": None,
    }
    message_retention_days = models.IntegerField(null=True, default=None)

    # on_delete field here is set to RESTRICT because we don't want to allow
    # deleting a user group in case it is referenced by this settig.
    # We are not using PROTECT since we want to allow deletion of user groups
    # when realm itself is deleted.
    can_remove_subscribers_group = models.ForeignKey(UserGroup, on_delete=models.RESTRICT)

    # The very first message ID in the stream.  Used to help clients
    # determine whether they might need to display "more topics" for a
    # stream based on what messages they have cached.
    first_message_id = models.IntegerField(null=True, db_index=True)

    stream_permission_group_settings = {
        "can_remove_subscribers_group": GroupPermissionSetting(
            require_system_group=True,
            allow_internet_group=False,
            allow_owners_group=False,
            allow_nobody_group=False,
            allow_everyone_group=True,
            default_group_name=UserGroup.ADMINISTRATORS_GROUP_NAME,
            id_field_name="can_remove_subscribers_group_id",
        ),
    }

    class Meta:
        indexes = [
            models.Index(Upper("name"), name="upper_stream_name_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def is_public(self) -> bool:
        # All streams are private in Zephyr mirroring realms.
        return not self.invite_only and not self.is_in_zephyr_realm

    def is_history_realm_public(self) -> bool:
        return self.is_public()

    def is_history_public_to_subscribers(self) -> bool:
        return self.history_public_to_subscribers

    # Stream fields included whenever a Stream object is provided to
    # Zulip clients via the API.  A few details worth noting:
    # * "id" is represented as "stream_id" in most API interfaces.
    # * "email_token" is not realm-public and thus is not included here.
    # * is_in_zephyr_realm is a backend-only optimization.
    # * "deactivated" streams are filtered from the API entirely.
    # * "realm" and "recipient" are not exposed to clients via the API.
    API_FIELDS = [
        "date_created",
        "description",
        "first_message_id",
        "history_public_to_subscribers",
        "id",
        "invite_only",
        "is_web_public",
        "message_retention_days",
        "name",
        "rendered_description",
        "stream_post_policy",
        "can_remove_subscribers_group_id",
    ]

    def to_dict(self) -> DefaultStreamDict:
        return DefaultStreamDict(
            can_remove_subscribers_group=self.can_remove_subscribers_group_id,
            date_created=datetime_to_timestamp(self.date_created),
            description=self.description,
            first_message_id=self.first_message_id,
            history_public_to_subscribers=self.history_public_to_subscribers,
            invite_only=self.invite_only,
            is_web_public=self.is_web_public,
            message_retention_days=self.message_retention_days,
            name=self.name,
            rendered_description=self.rendered_description,
            stream_id=self.id,
            stream_post_policy=self.stream_post_policy,
            is_announcement_only=self.stream_post_policy == Stream.STREAM_POST_POLICY_ADMINS,
        )


post_save.connect(flush_stream, sender=Stream)
post_delete.connect(flush_stream, sender=Stream)


class UserTopic(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    topic_name = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)
    # The default value for last_updated is a few weeks before tracking
    # of when topics were muted was first introduced.  It's designed
    # to be obviously incorrect so that one can tell it's backfilled data.
    last_updated = models.DateTimeField(
        default=datetime.datetime(2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
    )

    class VisibilityPolicy(models.IntegerChoices):
        # A normal muted topic. No notifications and unreads hidden.
        MUTED = 1, "Muted topic"

        # This topic will behave like an unmuted topic in an unmuted stream even if it
        # belongs to a muted stream.
        UNMUTED = 2, "Unmuted topic in muted stream"

        # This topic will behave like `UNMUTED`, plus some additional
        # display and/or notifications priority that is TBD and likely to
        # be configurable; see #6027. Not yet implemented.
        FOLLOWED = 3, "Followed topic"

        # Implicitly, if a UserTopic does not exist, the (user, topic)
        # pair should have normal behavior for that (user, stream) pair.

        # We use this in our code to represent the condition in the comment above.
        INHERIT = 0, "User's default policy for the stream."

    visibility_policy = models.SmallIntegerField(
        choices=VisibilityPolicy.choices, default=VisibilityPolicy.MUTED
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "user_profile",
                "stream",
                Lower("topic_name"),
                name="usertopic_case_insensitive_topic_uniq",
            ),
        ]

        indexes = [
            models.Index("stream", Upper("topic_name"), name="zerver_mutedtopic_stream_topic"),
            # This index is designed to optimize queries fetching the
            # set of users who have special policy for a stream,
            # e.g. for the send-message code paths.
            models.Index(
                fields=("stream", "topic_name", "visibility_policy", "user_profile"),
                name="zerver_usertopic_stream_topic_user_visibility_idx",
            ),
            # This index is useful for handling API requests fetching the
            # muted topics for a given user or user/stream pair.
            models.Index(
                fields=("user_profile", "visibility_policy", "stream", "topic_name"),
                name="zerver_usertopic_user_visibility_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"({self.user_profile.email}, {self.stream.name}, {self.topic_name}, {self.last_updated})"


class MutedUser(models.Model):
    user_profile = models.ForeignKey(UserProfile, related_name="muter", on_delete=CASCADE)
    muted_user = models.ForeignKey(UserProfile, related_name="muted", on_delete=CASCADE)
    date_muted = models.DateTimeField(default=timezone_now)

    class Meta:
        unique_together = ("user_profile", "muted_user")

    def __str__(self) -> str:
        return f"{self.user_profile.email} -> {self.muted_user.email}"


post_save.connect(flush_muting_users_cache, sender=MutedUser)
post_delete.connect(flush_muting_users_cache, sender=MutedUser)


class Client(models.Model):
    MAX_NAME_LENGTH = 30
    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True, unique=True)

    def __str__(self) -> str:
        return self.name


get_client_cache: Dict[str, Client] = {}


def clear_client_cache() -> None:  # nocoverage
    global get_client_cache
    get_client_cache = {}


def get_client(name: str) -> Client:
    # Accessing KEY_PREFIX through the module is necessary
    # because we need the updated value of the variable.
    cache_name = cache.KEY_PREFIX + name[0 : Client.MAX_NAME_LENGTH]
    if cache_name not in get_client_cache:
        result = get_client_remote_cache(name)
        get_client_cache[cache_name] = result
    return get_client_cache[cache_name]


def get_client_cache_key(name: str) -> str:
    return f"get_client:{hashlib.sha1(name.encode()).hexdigest()}"


@cache_with_key(get_client_cache_key, timeout=3600 * 24 * 7)
def get_client_remote_cache(name: str) -> Client:
    (client, _) = Client.objects.get_or_create(name=name[0 : Client.MAX_NAME_LENGTH])
    return client


def get_realm_stream(stream_name: str, realm_id: int) -> Stream:
    return Stream.objects.get(name__iexact=stream_name.strip(), realm_id=realm_id)


def get_active_streams(realm: Realm) -> QuerySet[Stream]:
    """
    Return all streams (including invite-only streams) that have not been deactivated.
    """
    return Stream.objects.filter(realm=realm, deactivated=False)


def get_linkable_streams(realm_id: int) -> QuerySet[Stream]:
    """
    This returns the streams that we are allowed to linkify using
    something like "#frontend" in our markup. For now the business
    rule is that you can link any stream in the realm that hasn't
    been deactivated (similar to how get_active_streams works).
    """
    return Stream.objects.filter(realm_id=realm_id, deactivated=False)


def get_stream(stream_name: str, realm: Realm) -> Stream:
    """
    Callers that don't have a Realm object already available should use
    get_realm_stream directly, to avoid unnecessarily fetching the
    Realm object.
    """
    return get_realm_stream(stream_name, realm.id)


def get_stream_by_id_in_realm(stream_id: int, realm: Realm) -> Stream:
    return Stream.objects.select_related("realm", "recipient").get(id=stream_id, realm=realm)


def bulk_get_streams(realm: Realm, stream_names: Set[str]) -> Dict[str, Any]:
    def fetch_streams_by_name(stream_names: Set[str]) -> QuerySet[Stream]:
        #
        # This should be just
        #
        # Stream.objects.select_related().filter(name__iexact__in=stream_names,
        #                                        realm_id=realm_id)
        #
        # But chaining __in and __iexact doesn't work with Django's
        # ORM, so we have the following hack to construct the relevant where clause
        where_clause = (
            "upper(zerver_stream.name::text) IN (SELECT upper(name) FROM unnest(%s) AS name)"
        )
        return get_active_streams(realm).extra(where=[where_clause], params=(list(stream_names),))

    if not stream_names:
        return {}
    streams = list(fetch_streams_by_name(stream_names))
    return {stream.name.lower(): stream for stream in streams}


def get_huddle_user_ids(recipient: Recipient) -> ValuesQuerySet["Subscription", int]:
    assert recipient.type == Recipient.HUDDLE

    return (
        Subscription.objects.filter(
            recipient=recipient,
        )
        .order_by("user_profile_id")
        .values_list("user_profile_id", flat=True)
    )


def bulk_get_huddle_user_ids(recipient_ids: List[int]) -> Dict[int, Set[int]]:
    """
    Takes a list of huddle-type recipient_ids, returns a dict
    mapping recipient id to list of user ids in the huddle.

    We rely on our caller to pass us recipient_ids that correspond
    to huddles, but technically this function is valid for any type
    of subscription.
    """
    if not recipient_ids:
        return {}

    subscriptions = Subscription.objects.filter(
        recipient_id__in=recipient_ids,
    ).only("user_profile_id", "recipient_id")

    result_dict: Dict[int, Set[int]] = defaultdict(set)
    for subscription in subscriptions:
        result_dict[subscription.recipient_id].add(subscription.user_profile_id)

    return result_dict


class AbstractMessage(models.Model):
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # The target of the message is signified by the Recipient object.
    # See the Recipient class for details.
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)

    realm = models.ForeignKey(Realm, on_delete=CASCADE)

    # The message's topic.
    #
    # Early versions of Zulip called this concept a "subject", as in an email
    # "subject line", before changing to "topic" in 2013 (commit dac5a46fa).
    # UI and user documentation now consistently say "topic".  New APIs and
    # new code should generally also say "topic".
    #
    # See also the `topic_name` method on `Message`.
    subject = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH, db_index=True)

    content = models.TextField()
    rendered_content = models.TextField(null=True)
    rendered_content_version = models.IntegerField(null=True)

    date_sent = models.DateTimeField("date sent", db_index=True)
    sending_client = models.ForeignKey(Client, on_delete=CASCADE)

    last_edit_time = models.DateTimeField(null=True)

    # A JSON-encoded list of objects describing any past edits to this
    # message, oldest first.
    edit_history = models.TextField(null=True)

    has_attachment = models.BooleanField(default=False, db_index=True)
    has_image = models.BooleanField(default=False, db_index=True)
    has_link = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.recipient.label()} / {self.subject} / {self.sender!r}"


class ArchiveTransaction(models.Model):
    timestamp = models.DateTimeField(default=timezone_now, db_index=True)
    # Marks if the data archived in this transaction has been restored:
    restored = models.BooleanField(default=False, db_index=True)

    type = models.PositiveSmallIntegerField(db_index=True)
    # Valid types:
    RETENTION_POLICY_BASED = 1  # Archiving was executed due to automated retention policies
    MANUAL = 2  # Archiving was run manually, via move_messages_to_archive function

    # ForeignKey to the realm with which objects archived in this transaction are associated.
    # If type is set to MANUAL, this should be null.
    realm = models.ForeignKey(Realm, null=True, on_delete=CASCADE)

    def __str__(self) -> str:
        return "id: {id}, type: {type}, realm: {realm}, timestamp: {timestamp}".format(
            id=self.id,
            type="MANUAL" if self.type == self.MANUAL else "RETENTION_POLICY_BASED",
            realm=self.realm.string_id if self.realm else None,
            timestamp=self.timestamp,
        )


class ArchivedMessage(AbstractMessage):
    """Used as a temporary holding place for deleted messages before they
    are permanently deleted.  This is an important part of a robust
    'message retention' feature.
    """

    archive_transaction = models.ForeignKey(ArchiveTransaction, on_delete=CASCADE)


class Message(AbstractMessage):
    # Recipient types used when a Message object is provided to
    # Zulip clients via the API.
    #
    # A detail worth noting:
    # * "direct" was introduced in 2023 with the goal of
    #   deprecating the original "private" and becoming the
    #   preferred way to indicate a personal or huddle
    #   Recipient type via the API.
    API_RECIPIENT_TYPES = ["direct", "private", "stream"]

    search_tsvector = SearchVectorField(null=True)

    DEFAULT_SELECT_RELATED = ["sender", "realm", "recipient", "sending_client"]

    def topic_name(self) -> str:
        """
        Please start using this helper to facilitate an
        eventual switch over to a separate topic table.
        """
        return self.subject

    def set_topic_name(self, topic_name: str) -> None:
        self.subject = topic_name

    def is_stream_message(self) -> bool:
        """
        Find out whether a message is a stream message by
        looking up its recipient.type.  TODO: Make this
        an easier operation by denormalizing the message
        type onto Message, either explicitly (message.type)
        or implicitly (message.stream_id is not None).
        """
        return self.recipient.type == Recipient.STREAM

    def get_realm(self) -> Realm:
        return self.realm

    def save_rendered_content(self) -> None:
        self.save(update_fields=["rendered_content", "rendered_content_version"])

    @staticmethod
    def need_to_render_content(
        rendered_content: Optional[str],
        rendered_content_version: Optional[int],
        markdown_version: int,
    ) -> bool:
        return (
            rendered_content is None
            or rendered_content_version is None
            or rendered_content_version < markdown_version
        )

    def sent_by_human(self) -> bool:
        """Used to determine whether a message was sent by a full Zulip UI
        style client (and thus whether the message should be treated
        as sent by a human and automatically marked as read for the
        sender).  The purpose of this distinction is to ensure that
        message sent to the user by e.g. a Google Calendar integration
        using the user's own API key don't get marked as read
        automatically.
        """
        sending_client = self.sending_client.name.lower()

        return (
            sending_client
            in (
                "zulipandroid",
                "zulipios",
                "zulipdesktop",
                "zulipmobile",
                "zulipelectron",
                "zulipterminal",
                "snipe",
                "website",
                "ios",
                "android",
            )
        ) or ("desktop app" in sending_client)

    @staticmethod
    def is_status_message(content: str, rendered_content: str) -> bool:
        """
        "status messages" start with /me and have special rendering:
            /me loves chocolate -> Full Name loves chocolate
        """
        if content.startswith("/me "):
            return True
        return False

    class Meta:
        indexes = [
            GinIndex("search_tsvector", fastupdate=False, name="zerver_message_search_tsvector"),
            models.Index(
                # For moving messages between streams or marking
                # streams as read.  The "id" at the end makes it easy
                # to scan the resulting messages in order, and perform
                # batching.
                "realm_id",
                "recipient_id",
                "id",
                name="zerver_message_realm_recipient_id",
            ),
            models.Index(
                # For generating digest emails and message archiving,
                # which both group by stream.
                "realm_id",
                "recipient_id",
                "date_sent",
                name="zerver_message_realm_recipient_date_sent",
            ),
            models.Index(
                # For exports, which want to limit both sender and
                # receiver.  The prefix of this index (realm_id,
                # sender_id) can be used for scrubbing users and/or
                # deleting users' messages.
                "realm_id",
                "sender_id",
                "recipient_id",
                name="zerver_message_realm_sender_recipient",
            ),
            models.Index(
                # For analytics queries
                "realm_id",
                "date_sent",
                name="zerver_message_realm_date_sent",
            ),
            models.Index(
                # For users searching by topic (but not stream), which
                # is done case-insensitively
                "realm_id",
                Upper("subject"),
                F("id").desc(nulls_last=True),
                name="zerver_message_realm_upper_subject",
            ),
            models.Index(
                # Most stream/topic searches are case-insensitive by
                # topic name (e.g. messages_for_topic).  The "id" at
                # the end makes it easy to scan the resulting messages
                # in order, and perform batching.
                "realm_id",
                "recipient_id",
                Upper("subject"),
                F("id").desc(nulls_last=True),
                name="zerver_message_realm_recipient_upper_subject",
            ),
            models.Index(
                # Only used by already_sent_mirrored_message_id
                "realm_id",
                "recipient_id",
                "subject",
                F("id").desc(nulls_last=True),
                name="zerver_message_realm_recipient_subject",
            ),
            models.Index(
                # Only used by update_first_visible_message_id
                "realm_id",
                F("id").desc(nulls_last=True),
                name="zerver_message_realm_id",
            ),
        ]


def get_context_for_message(message: Message) -> QuerySet[Message]:
    return Message.objects.filter(
        # Uses index: zerver_message_realm_recipient_upper_subject
        realm_id=message.realm_id,
        recipient_id=message.recipient_id,
        subject__iexact=message.subject,
        id__lt=message.id,
        date_sent__gt=message.date_sent - timedelta(minutes=15),
    ).order_by("-id")[:10]


post_save.connect(flush_message, sender=Message)


class AbstractSubMessage(models.Model):
    # We can send little text messages that are associated with a regular
    # Zulip message.  These can be used for experimental widgets like embedded
    # games, surveys, mini threads, etc.  These are designed to be pretty
    # generic in purpose.

    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)
    msg_type = models.TextField()
    content = models.TextField()

    class Meta:
        abstract = True


class SubMessage(AbstractSubMessage):
    message = models.ForeignKey(Message, on_delete=CASCADE)

    @staticmethod
    def get_raw_db_rows(needed_ids: List[int]) -> List[Dict[str, Any]]:
        fields = ["id", "message_id", "sender_id", "msg_type", "content"]
        query = SubMessage.objects.filter(message_id__in=needed_ids).values(*fields)
        query = query.order_by("message_id", "id")
        return list(query)


class ArchivedSubMessage(AbstractSubMessage):
    message = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)


post_save.connect(flush_submessage, sender=SubMessage)


class Draft(models.Model):
    """Server-side storage model for storing drafts so that drafts can be synced across
    multiple clients/devices.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)
    topic = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH, db_index=True)
    content = models.TextField()  # Length should not exceed MAX_MESSAGE_LENGTH
    last_edit_time = models.DateTimeField(db_index=True)

    def __str__(self) -> str:
        return f"{self.user_profile.email} / {self.id} / {self.last_edit_time}"

    def to_dict(self) -> Dict[str, Any]:
        to, recipient_type_str = get_recipient_ids(self.recipient, self.user_profile_id)
        return {
            "id": self.id,
            "type": recipient_type_str,
            "to": to,
            "topic": self.topic,
            "content": self.content,
            "timestamp": int(self.last_edit_time.timestamp()),
        }


class AbstractEmoji(models.Model):
    """For emoji reactions to messages (and potentially future reaction types).

    Emoji are surprisingly complicated to implement correctly.  For details
    on how this subsystem works, see:
      https://zulip.readthedocs.io/en/latest/subsystems/emoji.html
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # The user-facing name for an emoji reaction.  With emoji aliases,
    # there may be multiple accepted names for a given emoji; this
    # field encodes which one the user selected.
    emoji_name = models.TextField()

    UNICODE_EMOJI = "unicode_emoji"
    REALM_EMOJI = "realm_emoji"
    ZULIP_EXTRA_EMOJI = "zulip_extra_emoji"
    REACTION_TYPES = (
        (UNICODE_EMOJI, gettext_lazy("Unicode emoji")),
        (REALM_EMOJI, gettext_lazy("Custom emoji")),
        (ZULIP_EXTRA_EMOJI, gettext_lazy("Zulip extra emoji")),
    )
    reaction_type = models.CharField(default=UNICODE_EMOJI, choices=REACTION_TYPES, max_length=30)

    # A string with the property that (realm, reaction_type,
    # emoji_code) uniquely determines the emoji glyph.
    #
    # We cannot use `emoji_name` for this purpose, since the
    # name-to-glyph mappings for unicode emoji change with time as we
    # update our emoji database, and multiple custom emoji can have
    # the same `emoji_name` in a realm (at most one can have
    # `deactivated=False`). The format for `emoji_code` varies by
    # `reaction_type`:
    #
    # * For Unicode emoji, a dash-separated hex encoding of the sequence of
    #   Unicode codepoints that define this emoji in the Unicode
    #   specification.  For examples, see "non_qualified" or "unified" in the
    #   following data, with "non_qualified" taking precedence when both present:
    #     https://raw.githubusercontent.com/iamcal/emoji-data/master/emoji_pretty.json
    #
    # * For user uploaded custom emoji (`reaction_type="realm_emoji"`), the stringified ID
    #   of the RealmEmoji object, computed as `str(realm_emoji.id)`.
    #
    # * For "Zulip extra emoji" (like :zulip:), the name of the emoji (e.g. "zulip").
    emoji_code = models.TextField()

    class Meta:
        abstract = True


class AbstractReaction(AbstractEmoji):
    class Meta:
        abstract = True
        unique_together = ("user_profile", "message", "reaction_type", "emoji_code")


class Reaction(AbstractReaction):
    message = models.ForeignKey(Message, on_delete=CASCADE)

    @staticmethod
    def get_raw_db_rows(needed_ids: List[int]) -> List[Dict[str, Any]]:
        fields = [
            "message_id",
            "emoji_name",
            "emoji_code",
            "reaction_type",
            "user_profile__email",
            "user_profile_id",
            "user_profile__full_name",
        ]
        # The ordering is important here, as it makes it convenient
        # for clients to display reactions in order without
        # client-side sorting code.
        return Reaction.objects.filter(message_id__in=needed_ids).values(*fields).order_by("id")

    def __str__(self) -> str:
        return f"{self.user_profile.email} / {self.message.id} / {self.emoji_name}"


class ArchivedReaction(AbstractReaction):
    message = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)


# Whenever a message is sent, for each user subscribed to the
# corresponding Recipient object (that is not long-term idle), we add
# a row to the UserMessage table indicating that that user received
# that message.  This table allows us to quickly query any user's last
# 1000 messages to generate the home view and search exactly the
# user's message history.
#
# The long-term idle optimization is extremely important for large,
# open organizations, and is described in detail here:
# https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html#soft-deactivation
#
# In particular, new messages to public streams will only generate
# UserMessage rows for Members who are long_term_idle if they would
# have nonzero flags for the message (E.g. a mention, alert word, or
# mobile push notification).
#
# The flags field stores metadata like whether the user has read the
# message, starred or collapsed the message, was mentioned in the
# message, etc. We use of postgres partial indexes on flags to make
# queries for "User X's messages with flag Y" extremely fast without
# consuming much storage space.
#
# UserMessage is the largest table in many Zulip installations, even
# though each row is only 4 integers.
class AbstractUserMessage(models.Model):
    id = models.BigAutoField(primary_key=True)

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    # The order here is important!  It's the order of fields in the bitfield.
    ALL_FLAGS = [
        "read",
        "starred",
        "collapsed",
        "mentioned",
        "wildcard_mentioned",
        # These next 4 flags are from features that have since been removed.
        "summarize_in_home",
        "summarize_in_stream",
        "force_expand",
        "force_collapse",
        # Whether the message contains any of the user's alert words.
        "has_alert_word",
        # The historical flag is used to mark messages which the user
        # did not receive when they were sent, but later added to
        # their history via e.g. starring the message.  This is
        # important accounting for the "Subscribed to stream" dividers.
        "historical",
        # Whether the message is a direct message; this flag is a
        # denormalization of message.recipient.type to support an
        # efficient index on UserMessage for a user's direct messages.
        "is_private",
        # Whether we've sent a push notification to the user's mobile
        # devices for this message that has not been revoked.
        "active_mobile_push_notification",
    ]
    # Certain flags are used only for internal accounting within the
    # Zulip backend, and don't make sense to expose to the API.
    NON_API_FLAGS = {"is_private", "active_mobile_push_notification"}
    # Certain additional flags are just set once when the UserMessage
    # row is created.
    NON_EDITABLE_FLAGS = {
        # These flags are bookkeeping and don't make sense to edit.
        "has_alert_word",
        "mentioned",
        "wildcard_mentioned",
        "historical",
        # Unused flags can't be edited.
        "force_expand",
        "force_collapse",
        "summarize_in_home",
        "summarize_in_stream",
    }
    flags: BitHandler = BitField(flags=ALL_FLAGS, default=0)

    class Meta:
        abstract = True
        unique_together = ("user_profile", "message")

    @staticmethod
    def where_flag_is_present(flagattr: Bit) -> str:
        # Use this for Django ORM queries to access starred messages.
        # This custom SQL plays nice with our partial indexes.  Grep
        # the code for example usage.
        #
        # The key detail is that e.g.
        #   UserMessage.objects.filter(user_profile=user_profile, flags=UserMessage.flags.starred)
        # will generate a query involving `flags & 2 = 2`, which doesn't match our index.
        return f"flags & {1 << flagattr.number} <> 0"

    @staticmethod
    def where_flag_is_absent(flagattr: Bit) -> str:
        return f"flags & {1 << flagattr.number} = 0"

    @staticmethod
    def where_unread() -> str:
        return AbstractUserMessage.where_flag_is_absent(AbstractUserMessage.flags.read)

    @staticmethod
    def where_read() -> str:
        return AbstractUserMessage.where_flag_is_present(AbstractUserMessage.flags.read)

    @staticmethod
    def where_starred() -> str:
        return AbstractUserMessage.where_flag_is_present(AbstractUserMessage.flags.starred)

    @staticmethod
    def where_active_push_notification() -> str:
        return AbstractUserMessage.where_flag_is_present(
            AbstractUserMessage.flags.active_mobile_push_notification
        )

    def flags_list(self) -> List[str]:
        flags = int(self.flags)
        return self.flags_list_for_flags(flags)

    @staticmethod
    def flags_list_for_flags(val: int) -> List[str]:
        """
        This function is highly optimized, because it actually slows down
        sending messages in a naive implementation.
        """
        flags = []
        mask = 1
        for flag in UserMessage.ALL_FLAGS:
            if (val & mask) and flag not in AbstractUserMessage.NON_API_FLAGS:
                flags.append(flag)
            mask <<= 1
        return flags


class UserMessage(AbstractUserMessage):
    message = models.ForeignKey(Message, on_delete=CASCADE)

    class Meta(AbstractUserMessage.Meta):
        indexes = [
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=AbstractUserMessage.flags.starred.mask),
                name="zerver_usermessage_starred_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=AbstractUserMessage.flags.mentioned.mask),
                name="zerver_usermessage_mentioned_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andz=AbstractUserMessage.flags.read.mask),
                name="zerver_usermessage_unread_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=AbstractUserMessage.flags.has_alert_word.mask),
                name="zerver_usermessage_has_alert_word_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=AbstractUserMessage.flags.mentioned.mask)
                | Q(flags__andnz=AbstractUserMessage.flags.wildcard_mentioned.mask),
                name="zerver_usermessage_wildcard_mentioned_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(flags__andnz=AbstractUserMessage.flags.is_private.mask),
                name="zerver_usermessage_is_private_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(
                    flags__andnz=AbstractUserMessage.flags.active_mobile_push_notification.mask
                ),
                name="zerver_usermessage_active_mobile_push_notification_id",
            ),
        ]

    def __str__(self) -> str:
        recipient_string = self.message.recipient.label()
        return f"{recipient_string} / {self.user_profile.email} ({self.flags_list()})"

    @staticmethod
    def select_for_update_query() -> QuerySet["UserMessage"]:
        """This SELECT FOR UPDATE query ensures consistent ordering on
        the row locks acquired by a bulk update operation to modify
        message flags using bitand/bitor.

        This consistent ordering is important to prevent deadlocks when
        2 or more bulk updates to the same rows in the UserMessage table
        race against each other (For example, if a client submits
        simultaneous duplicate API requests to mark a certain set of
        messages as read).
        """
        return UserMessage.objects.select_for_update().order_by("message_id")


def get_usermessage_by_message_id(
    user_profile: UserProfile, message_id: int
) -> Optional[UserMessage]:
    try:
        return UserMessage.objects.select_related().get(
            user_profile=user_profile, message_id=message_id
        )
    except UserMessage.DoesNotExist:
        return None


class ArchivedUserMessage(AbstractUserMessage):
    """Used as a temporary holding place for deleted UserMessages objects
    before they are permanently deleted.  This is an important part of
    a robust 'message retention' feature.
    """

    message = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)

    def __str__(self) -> str:
        recipient_string = self.message.recipient.label()
        return f"{recipient_string} / {self.user_profile.email} ({self.flags_list()})"


class AbstractAttachment(models.Model):
    file_name = models.TextField(db_index=True)

    # path_id is a storage location agnostic representation of the path of the file.
    # If the path of a file is http://localhost:9991/user_uploads/a/b/abc/temp_file.py
    # then its path_id will be a/b/abc/temp_file.py.
    path_id = models.TextField(db_index=True, unique=True)
    owner = models.ForeignKey(UserProfile, on_delete=CASCADE)
    realm = models.ForeignKey(Realm, on_delete=CASCADE)

    create_time = models.DateTimeField(
        default=timezone_now,
        db_index=True,
    )
    # Size of the uploaded file, in bytes
    size = models.IntegerField()

    # The two fields below serve as caches to let us avoid looking up
    # the corresponding messages/streams to check permissions before
    # serving these files.
    #
    # For both fields, the `null` state is used when a change in
    # message permissions mean that we need to determine their proper
    # value.

    # Whether this attachment has been posted to a public stream, and
    # thus should be available to all non-guest users in the
    # organization (even if they weren't a recipient of a message
    # linking to it).
    is_realm_public = models.BooleanField(default=False, null=True)
    # Whether this attachment has been posted to a web-public stream,
    # and thus should be available to everyone on the internet, even
    # if the person isn't logged in.
    is_web_public = models.BooleanField(default=False, null=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.file_name


class ArchivedAttachment(AbstractAttachment):
    """Used as a temporary holding place for deleted Attachment objects
    before they are permanently deleted.  This is an important part of
    a robust 'message retention' feature.

    Unlike the similar archive tables, ArchivedAttachment does not
    have an ArchiveTransaction foreign key, and thus will not be
    directly deleted by clean_archived_data. Instead, attachments that
    were only referenced by now fully deleted messages will leave
    ArchivedAttachment objects with empty `.messages`.

    A second step, delete_old_unclaimed_attachments, will delete the
    resulting orphaned ArchivedAttachment objects, along with removing
    the associated uploaded files from storage.
    """

    messages = models.ManyToManyField(
        ArchivedMessage, related_name="attachment_set", related_query_name="attachment"
    )


class Attachment(AbstractAttachment):
    messages = models.ManyToManyField(Message)

    # This is only present for Attachment and not ArchiveAttachment.
    # because ScheduledMessage is not subject to archiving.
    scheduled_messages = models.ManyToManyField("ScheduledMessage")

    def is_claimed(self) -> bool:
        return self.messages.exists() or self.scheduled_messages.exists()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.file_name,
            "path_id": self.path_id,
            "size": self.size,
            # convert to JavaScript-style UNIX timestamp so we can take
            # advantage of client time zones.
            "create_time": int(time.mktime(self.create_time.timetuple()) * 1000),
            "messages": [
                {
                    "id": m.id,
                    "date_sent": int(time.mktime(m.date_sent.timetuple()) * 1000),
                }
                for m in self.messages.all()
            ],
        }


post_save.connect(flush_used_upload_space_cache, sender=Attachment)
post_delete.connect(flush_used_upload_space_cache, sender=Attachment)


def validate_attachment_request_for_spectator_access(
    realm: Realm, attachment: Attachment
) -> Optional[bool]:
    if attachment.realm != realm:
        return False

    # Update cached is_web_public property, if necessary.
    if attachment.is_web_public is None:
        # Fill the cache in a single query. This is important to avoid
        # a potential race condition between checking and setting,
        # where the attachment could have been moved again.
        Attachment.objects.filter(id=attachment.id, is_web_public__isnull=True).update(
            is_web_public=Exists(
                Message.objects.filter(
                    # Uses index: zerver_attachment_messages_attachment_id_message_id_key
                    realm_id=realm.id,
                    attachment=OuterRef("id"),
                    recipient__stream__invite_only=False,
                    recipient__stream__is_web_public=True,
                ),
            ),
        )
        attachment.refresh_from_db()

    if not attachment.is_web_public:
        return False

    if settings.RATE_LIMITING:
        try:
            from zerver.lib.rate_limiter import rate_limit_spectator_attachment_access_by_file

            rate_limit_spectator_attachment_access_by_file(attachment.path_id)
        except RateLimitedError:
            return False

    return True


def validate_attachment_request(
    maybe_user_profile: Union[UserProfile, AnonymousUser],
    path_id: str,
    realm: Optional[Realm] = None,
) -> Optional[bool]:
    try:
        attachment = Attachment.objects.get(path_id=path_id)
    except Attachment.DoesNotExist:
        return None

    if isinstance(maybe_user_profile, AnonymousUser):
        assert realm is not None
        return validate_attachment_request_for_spectator_access(realm, attachment)

    user_profile = maybe_user_profile
    assert isinstance(user_profile, UserProfile)

    # Update cached is_realm_public property, if necessary.
    if attachment.is_realm_public is None:
        # Fill the cache in a single query. This is important to avoid
        # a potential race condition between checking and setting,
        # where the attachment could have been moved again.
        Attachment.objects.filter(id=attachment.id, is_realm_public__isnull=True).update(
            is_realm_public=Exists(
                Message.objects.filter(
                    # Uses index: zerver_attachment_messages_attachment_id_message_id_key
                    realm_id=user_profile.realm_id,
                    attachment=OuterRef("id"),
                    recipient__stream__invite_only=False,
                ),
            ),
        )
        attachment.refresh_from_db()

    if user_profile == attachment.owner:
        # If you own the file, you can access it.
        return True
    if (
        attachment.is_realm_public
        and attachment.realm == user_profile.realm
        and user_profile.can_access_public_streams()
    ):
        # Any user in the realm can access realm-public files
        return True

    messages = attachment.messages.all()
    if UserMessage.objects.filter(user_profile=user_profile, message__in=messages).exists():
        # If it was sent in a direct message or private stream
        # message, then anyone who received that message can access it.
        return True

    # The user didn't receive any of the messages that included this
    # attachment.  But they might still have access to it, if it was
    # sent to a stream they are on where history is public to
    # subscribers.

    # These are subscriptions to a stream one of the messages was sent to
    relevant_stream_ids = Subscription.objects.filter(
        user_profile=user_profile,
        active=True,
        recipient__type=Recipient.STREAM,
        recipient__in=[m.recipient_id for m in messages],
    ).values_list("recipient__type_id", flat=True)
    if len(relevant_stream_ids) == 0:
        return False

    return Stream.objects.filter(
        id__in=relevant_stream_ids, history_public_to_subscribers=True
    ).exists()


def get_old_unclaimed_attachments(
    weeks_ago: int,
) -> Tuple[QuerySet[Attachment], QuerySet[ArchivedAttachment]]:
    """
    The logic in this function is fairly tricky. The essence is that
    a file should be cleaned up if and only if it not referenced by any
    Message, ScheduledMessage or ArchivedMessage. The way to find that out is through the
    Attachment and ArchivedAttachment tables.
    The queries are complicated by the fact that an uploaded file
    may have either only an Attachment row, only an ArchivedAttachment row,
    or both - depending on whether some, all or none of the messages
    linking to it have been archived.
    """
    delta_weeks_ago = timezone_now() - datetime.timedelta(weeks=weeks_ago)

    # The Attachment vs ArchivedAttachment queries are asymmetric because only
    # Attachment has the scheduled_messages relation.
    old_attachments = Attachment.objects.annotate(
        has_other_messages=Exists(
            ArchivedAttachment.objects.filter(id=OuterRef("id")).exclude(messages=None)
        )
    ).filter(
        messages=None,
        scheduled_messages=None,
        create_time__lt=delta_weeks_ago,
        has_other_messages=False,
    )
    old_archived_attachments = ArchivedAttachment.objects.annotate(
        has_other_messages=Exists(
            Attachment.objects.filter(id=OuterRef("id")).exclude(
                messages=None, scheduled_messages=None
            )
        )
    ).filter(messages=None, create_time__lt=delta_weeks_ago, has_other_messages=False)

    return old_attachments, old_archived_attachments


class Subscription(models.Model):
    """Keeps track of which users are part of the
    audience for a given Recipient object.

    For 1:1 and group direct message Recipient objects, only the
    user_profile and recipient fields have any meaning, defining the
    immutable set of users who are in the audience for that Recipient.

    For Recipient objects associated with a Stream, the remaining
    fields in this model describe the user's subscription to that stream.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)

    # Whether the user has since unsubscribed.  We mark Subscription
    # objects as inactive, rather than deleting them, when a user
    # unsubscribes, so we can preserve user customizations like
    # notification settings, stream color, etc., if the user later
    # resubscribes.
    active = models.BooleanField(default=True)
    # This is a denormalization designed to improve the performance of
    # bulk queries of Subscription objects, Whether the subscribed user
    # is active tends to be a key condition in those queries.
    # We intentionally don't specify a default value to promote thinking
    # about this explicitly, as in some special cases, such as data import,
    # we may be creating Subscription objects for a user that's deactivated.
    is_user_active = models.BooleanField()

    # Whether this user had muted this stream.
    is_muted = models.BooleanField(default=False)

    DEFAULT_STREAM_COLOR = "#c2c2c2"
    color = models.CharField(max_length=10, default=DEFAULT_STREAM_COLOR)
    pin_to_top = models.BooleanField(default=False)

    # These fields are stream-level overrides for the user's default
    # configuration for notification, configured in UserProfile.  The
    # default, None, means we just inherit the user-level default.
    desktop_notifications = models.BooleanField(null=True, default=None)
    audible_notifications = models.BooleanField(null=True, default=None)
    push_notifications = models.BooleanField(null=True, default=None)
    email_notifications = models.BooleanField(null=True, default=None)
    wildcard_mentions_notify = models.BooleanField(null=True, default=None)

    class Meta:
        unique_together = ("user_profile", "recipient")
        indexes = [
            models.Index(
                fields=("recipient", "user_profile"),
                name="zerver_subscription_recipient_id_user_profile_id_idx",
                condition=Q(active=True, is_user_active=True),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_profile!r} -> {self.recipient!r}"

    # Subscription fields included whenever a Subscription object is provided to
    # Zulip clients via the API.  A few details worth noting:
    # * These fields will generally be merged with Stream.API_FIELDS
    #   data about the stream.
    # * "user_profile" is usually implied as full API access to Subscription
    #   is primarily done for the current user; API access to other users'
    #   subscriptions is generally limited to boolean yes/no.
    # * "id" and "recipient_id" are not included as they are not used
    #   in the Zulip API; it's an internal implementation detail.
    #   Subscription objects are always looked up in the API via
    #   (user_profile, stream) pairs.
    # * "active" is often excluded in API use cases where it is implied.
    # * "is_muted" often needs to be copied to not "in_home_view" for
    #   backwards-compatibility.
    API_FIELDS = [
        "audible_notifications",
        "color",
        "desktop_notifications",
        "email_notifications",
        "is_muted",
        "pin_to_top",
        "push_notifications",
        "wildcard_mentions_notify",
    ]


@cache_with_key(user_profile_by_id_cache_key, timeout=3600 * 24 * 7)
def get_user_profile_by_id(user_profile_id: int) -> UserProfile:
    return UserProfile.objects.select_related("realm", "bot_owner").get(id=user_profile_id)


def get_user_profile_by_email(email: str) -> UserProfile:
    """This function is intended to be used for
    manual manage.py shell work; robust code must use get_user or
    get_user_by_delivery_email instead, because Zulip supports
    multiple users with a given (delivery) email address existing on a
    single server (in different realms).
    """
    return UserProfile.objects.select_related("realm").get(delivery_email__iexact=email.strip())


@cache_with_key(user_profile_by_api_key_cache_key, timeout=3600 * 24 * 7)
def maybe_get_user_profile_by_api_key(api_key: str) -> Optional[UserProfile]:
    try:
        return UserProfile.objects.select_related("realm", "bot_owner").get(api_key=api_key)
    except UserProfile.DoesNotExist:
        # We will cache failed lookups with None.  The
        # use case here is that broken API clients may
        # continually ask for the same wrong API key, and
        # we want to handle that as quickly as possible.
        return None


def get_user_profile_by_api_key(api_key: str) -> UserProfile:
    user_profile = maybe_get_user_profile_by_api_key(api_key)
    if user_profile is None:
        raise UserProfile.DoesNotExist

    return user_profile


def get_user_by_delivery_email(email: str, realm: Realm) -> UserProfile:
    """Fetches a user given their delivery email.  For use in
    authentication/registration contexts.  Do not use for user-facing
    views (e.g. Zulip API endpoints) as doing so would violate the
    EMAIL_ADDRESS_VISIBILITY_ADMINS security model.  Use get_user in
    those code paths.
    """
    return UserProfile.objects.select_related("realm", "bot_owner").get(
        delivery_email__iexact=email.strip(), realm=realm
    )


def get_users_by_delivery_email(emails: Set[str], realm: Realm) -> QuerySet[UserProfile]:
    """This is similar to get_user_by_delivery_email, and
    it has the same security caveats.  It gets multiple
    users and returns a QuerySet, since most callers
    will only need two or three fields.

    If you are using this to get large UserProfile objects, you are
    probably making a mistake, but if you must,
    then use `select_related`.
    """

    """
    Django doesn't support delivery_email__iexact__in, so
    we simply OR all the filters that we'd do for the
    one-email case.
    """
    email_filter = Q()
    for email in emails:
        email_filter |= Q(delivery_email__iexact=email.strip())

    return UserProfile.objects.filter(realm=realm).filter(email_filter)


@cache_with_key(user_profile_cache_key, timeout=3600 * 24 * 7)
def get_user(email: str, realm: Realm) -> UserProfile:
    """Fetches the user by its visible-to-other users username (in the
    `email` field).  For use in API contexts; do not use in
    authentication/registration contexts as doing so will break
    authentication in organizations using
    EMAIL_ADDRESS_VISIBILITY_ADMINS.  In those code paths, use
    get_user_by_delivery_email.
    """
    return UserProfile.objects.select_related("realm", "bot_owner").get(
        email__iexact=email.strip(), realm=realm
    )


def get_active_user(email: str, realm: Realm) -> UserProfile:
    """Variant of get_user_by_email that excludes deactivated users.
    See get_user docstring for important usage notes."""
    user_profile = get_user(email, realm)
    if not user_profile.is_active:
        raise UserProfile.DoesNotExist
    return user_profile


def get_user_profile_by_id_in_realm(uid: int, realm: Realm) -> UserProfile:
    return UserProfile.objects.select_related("realm", "bot_owner").get(id=uid, realm=realm)


def get_active_user_profile_by_id_in_realm(uid: int, realm: Realm) -> UserProfile:
    user_profile = get_user_profile_by_id_in_realm(uid, realm)
    if not user_profile.is_active:
        raise UserProfile.DoesNotExist
    return user_profile


def get_user_including_cross_realm(email: str, realm: Realm) -> UserProfile:
    if is_cross_realm_bot_email(email):
        return get_system_bot(email, realm.id)
    assert realm is not None
    return get_user(email, realm)


@cache_with_key(bot_profile_cache_key, timeout=3600 * 24 * 7)
def get_system_bot(email: str, realm_id: int) -> UserProfile:
    """
    This function doesn't use the realm_id argument yet, but requires
    passing it as preparation for adding system bots to each realm instead
    of having them all in a separate system bot realm.
    If you're calling this function, use the id of the realm in which the system
    bot will be after that migration. If the bot is supposed to send a message,
    the same realm as the one *to* which the message will be sent should be used - because
    cross-realm messages will be eliminated as part of the migration.
    """
    return UserProfile.objects.select_related("realm").get(email__iexact=email.strip())


def get_user_by_id_in_realm_including_cross_realm(
    uid: int,
    realm: Optional[Realm],
) -> UserProfile:
    user_profile = get_user_profile_by_id(uid)
    if user_profile.realm == realm:
        return user_profile

    # Note: This doesn't validate whether the `realm` passed in is
    # None/invalid for the is_cross_realm_bot_email case.
    if is_cross_realm_bot_email(user_profile.delivery_email):
        return user_profile

    raise UserProfile.DoesNotExist


@cache_with_key(realm_user_dicts_cache_key, timeout=3600 * 24 * 7)
def get_realm_user_dicts(realm_id: int) -> List[Dict[str, Any]]:
    return list(
        UserProfile.objects.filter(
            realm_id=realm_id,
        ).values(*realm_user_dict_fields)
    )


@cache_with_key(active_user_ids_cache_key, timeout=3600 * 24 * 7)
def active_user_ids(realm_id: int) -> List[int]:
    query = UserProfile.objects.filter(
        realm_id=realm_id,
        is_active=True,
    ).values_list("id", flat=True)
    return list(query)


@cache_with_key(active_non_guest_user_ids_cache_key, timeout=3600 * 24 * 7)
def active_non_guest_user_ids(realm_id: int) -> List[int]:
    query = (
        UserProfile.objects.filter(
            realm_id=realm_id,
            is_active=True,
        )
        .exclude(
            role=UserProfile.ROLE_GUEST,
        )
        .values_list("id", flat=True)
    )
    return list(query)


def bot_owner_user_ids(user_profile: UserProfile) -> Set[int]:
    is_private_bot = (
        user_profile.default_sending_stream
        and user_profile.default_sending_stream.invite_only
        or user_profile.default_events_register_stream
        and user_profile.default_events_register_stream.invite_only
    )
    assert user_profile.bot_owner_id is not None
    if is_private_bot:
        return {user_profile.bot_owner_id}
    else:
        users = {user.id for user in user_profile.realm.get_human_admin_users()}
        users.add(user_profile.bot_owner_id)
        return users


def get_source_profile(email: str, realm_id: int) -> Optional[UserProfile]:
    try:
        return get_user_by_delivery_email(email, get_realm_by_id(realm_id))
    except (Realm.DoesNotExist, UserProfile.DoesNotExist):
        return None


@cache_with_key(lambda realm: bot_dicts_in_realm_cache_key(realm.id), timeout=3600 * 24 * 7)
def get_bot_dicts_in_realm(realm: Realm) -> List[Dict[str, Any]]:
    return list(UserProfile.objects.filter(realm=realm, is_bot=True).values(*bot_dict_fields))


def is_cross_realm_bot_email(email: str) -> bool:
    return email.lower() in settings.CROSS_REALM_BOT_EMAILS


class Huddle(models.Model):
    """
    Represents a group of individuals who may have a
    group direct message conversation together.

    The membership of the Huddle is stored in the Subscription table just like with
    Streams - for each user in the Huddle, there is a Subscription object
    tied to the UserProfile and the Huddle's recipient object.

    A hash of the list of user IDs is stored in the huddle_hash field
    below, to support efficiently mapping from a set of users to the
    corresponding Huddle object.
    """

    # TODO: We should consider whether using
    # CommaSeparatedIntegerField would be better.
    huddle_hash = models.CharField(max_length=40, db_index=True, unique=True)
    # Foreign key to the Recipient object for this Huddle.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)


def get_huddle_hash(id_list: List[int]) -> str:
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    return hashlib.sha1(hash_key.encode()).hexdigest()


def huddle_hash_cache_key(huddle_hash: str) -> str:
    return f"huddle_by_hash:{huddle_hash}"


def get_or_create_huddle(id_list: List[int]) -> Huddle:
    """
    Takes a list of user IDs and returns the Huddle object for the
    group consisting of these users. If the Huddle object does not
    yet exist, it will be transparently created.
    """
    huddle_hash = get_huddle_hash(id_list)
    return get_or_create_huddle_backend(huddle_hash, id_list)


@cache_with_key(
    lambda huddle_hash, id_list: huddle_hash_cache_key(huddle_hash), timeout=3600 * 24 * 7
)
def get_or_create_huddle_backend(huddle_hash: str, id_list: List[int]) -> Huddle:
    with transaction.atomic():
        (huddle, created) = Huddle.objects.get_or_create(huddle_hash=huddle_hash)
        if created:
            recipient = Recipient.objects.create(type_id=huddle.id, type=Recipient.HUDDLE)
            huddle.recipient = recipient
            huddle.save(update_fields=["recipient"])
            subs_to_create = [
                Subscription(
                    recipient=recipient,
                    user_profile_id=user_profile_id,
                    is_user_active=is_active,
                )
                for user_profile_id, is_active in UserProfile.objects.filter(id__in=id_list)
                .distinct("id")
                .values_list("id", "is_active")
            ]
            Subscription.objects.bulk_create(subs_to_create)
        return huddle


class UserActivity(models.Model):
    """Data table recording the last time each user hit Zulip endpoints
    via which Clients; unlike UserPresence, these data are not exposed
    to users via the Zulip API.

    Useful for debugging as well as to answer analytics questions like
    "How many users have accessed the Zulip mobile app in the last
    month?" or "Which users/organizations have recently used API
    endpoint X that is about to be desupported" for communications
    and database migration purposes.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    client = models.ForeignKey(Client, on_delete=CASCADE)
    query = models.CharField(max_length=50, db_index=True)

    count = models.IntegerField()
    last_visit = models.DateTimeField("last visit")

    class Meta:
        unique_together = ("user_profile", "client", "query")


class UserActivityInterval(models.Model):
    MIN_INTERVAL_LENGTH = datetime.timedelta(minutes=15)

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    start = models.DateTimeField("start time", db_index=True)
    end = models.DateTimeField("end time", db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user_profile", "end"],
                name="zerver_useractivityinterval_user_profile_id_end_bb3bfc37_idx",
            ),
        ]


class UserPresence(models.Model):
    """A record from the last time we heard from a given user on a given client.

    NOTE: Users can disable updates to this table (see UserProfile.presence_enabled),
    so this cannot be used to determine if a user was recently active on Zulip.
    The UserActivity table is recommended for that purpose.

    This is a tricky subsystem, because it is highly optimized.  See the docs:
      https://zulip.readthedocs.io/en/latest/subsystems/presence.html
    """

    user_profile = models.OneToOneField(UserProfile, on_delete=CASCADE, unique=True)

    # Realm is just here as denormalization to optimize database
    # queries to fetch all presence data for a given realm.
    realm = models.ForeignKey(Realm, on_delete=CASCADE)

    # The last time the user had a client connected to Zulip,
    # including idle clients where the user hasn't interacted with the
    # system recently (and thus might be AFK).
    last_connected_time = models.DateTimeField(default=timezone_now, db_index=True, null=True)
    # The last time a client connected to Zulip reported that the user
    # was actually present (E.g. via focusing a browser window or
    # interacting with a computer running the desktop app)
    last_active_time = models.DateTimeField(default=timezone_now, db_index=True, null=True)

    # The following constants are used in the presence API for
    # communicating whether a user is active (last_active_time recent)
    # or idle (last_connected_time recent) or offline (neither
    # recent).  They're no longer part of the data model.
    LEGACY_STATUS_ACTIVE = "active"
    LEGACY_STATUS_IDLE = "idle"
    LEGACY_STATUS_ACTIVE_INT = 1
    LEGACY_STATUS_IDLE_INT = 2

    class Meta:
        indexes = [
            models.Index(
                fields=["realm", "last_active_time"],
                name="zerver_userpresence_realm_id_last_active_time_1c5aa9a2_idx",
            ),
            models.Index(
                fields=["realm", "last_connected_time"],
                name="zerver_userpresence_realm_id_last_connected_time_98d2fc9f_idx",
            ),
        ]

    @staticmethod
    def status_from_string(status: str) -> Optional[int]:
        if status == "active":
            return UserPresence.LEGACY_STATUS_ACTIVE_INT
        elif status == "idle":
            return UserPresence.LEGACY_STATUS_IDLE_INT

        return None


class UserStatus(AbstractEmoji):
    user_profile = models.OneToOneField(UserProfile, on_delete=CASCADE)

    timestamp = models.DateTimeField()
    client = models.ForeignKey(Client, on_delete=CASCADE)

    # Override emoji_name and emoji_code field of (AbstractReaction model) to accept
    # default value.
    emoji_name = models.TextField(default="")
    emoji_code = models.TextField(default="")

    status_text = models.CharField(max_length=255, default="")


class DefaultStream(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, on_delete=CASCADE)

    class Meta:
        unique_together = ("realm", "stream")


class DefaultStreamGroup(models.Model):
    MAX_NAME_LENGTH = 60

    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    streams = models.ManyToManyField("Stream")
    description = models.CharField(max_length=1024, default="")

    class Meta:
        unique_together = ("realm", "name")

    def to_dict(self) -> Dict[str, Any]:
        return dict(
            name=self.name,
            id=self.id,
            description=self.description,
            streams=[stream.to_dict() for stream in self.streams.all().order_by("name")],
        )


def get_default_stream_groups(realm: Realm) -> QuerySet[DefaultStreamGroup]:
    return DefaultStreamGroup.objects.filter(realm=realm)


class AbstractScheduledJob(models.Model):
    scheduled_timestamp = models.DateTimeField(db_index=True)
    # JSON representation of arguments to consumer
    data = models.TextField()
    realm = models.ForeignKey(Realm, on_delete=CASCADE)

    class Meta:
        abstract = True


class ScheduledEmail(AbstractScheduledJob):
    # Exactly one of users or address should be set. These are
    # duplicate values, used to efficiently filter the set of
    # ScheduledEmails for use in clear_scheduled_emails; the
    # recipients used for actually sending messages are stored in the
    # data field of AbstractScheduledJob.
    users = models.ManyToManyField(UserProfile)
    # Just the address part of a full "name <address>" email address
    address = models.EmailField(null=True, db_index=True)

    # Valid types are below
    WELCOME = 1
    DIGEST = 2
    INVITATION_REMINDER = 3
    type = models.PositiveSmallIntegerField()

    def __str__(self) -> str:
        return f"{self.type} {self.address or list(self.users.all())} {self.scheduled_timestamp}"


class MissedMessageEmailAddress(models.Model):
    message = models.ForeignKey(Message, on_delete=CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    email_token = models.CharField(max_length=34, unique=True, db_index=True)

    # Timestamp of when the missed message address generated.
    timestamp = models.DateTimeField(db_index=True, default=timezone_now)
    # Number of times the missed message address has been used.
    times_used = models.PositiveIntegerField(default=0, db_index=True)

    def __str__(self) -> str:
        return settings.EMAIL_GATEWAY_PATTERN % (self.email_token,)

    def increment_times_used(self) -> None:
        self.times_used += 1
        self.save(update_fields=["times_used"])


class NotificationTriggers:
    # "direct_message" is for 1:1 direct messages as well as huddles
    DIRECT_MESSAGE = "direct_message"
    MENTION = "mentioned"
    TOPIC_WILDCARD_MENTION = "topic_wildcard_mentioned"
    STREAM_WILDCARD_MENTION = "stream_wildcard_mentioned"
    STREAM_PUSH = "stream_push_notify"
    STREAM_EMAIL = "stream_email_notify"
    FOLLOWED_TOPIC_PUSH = "followed_topic_push_notify"
    FOLLOWED_TOPIC_EMAIL = "followed_topic_email_notify"
    TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC = "topic_wildcard_mentioned_in_followed_topic"
    STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC = "stream_wildcard_mentioned_in_followed_topic"


class ScheduledMessageNotificationEmail(models.Model):
    """Stores planned outgoing message notification emails. They may be
    processed earlier should Zulip choose to batch multiple messages
    in a single email, but typically will be processed just after
    scheduled_timestamp.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    message = models.ForeignKey(Message, on_delete=CASCADE)

    EMAIL_NOTIFICATION_TRIGGER_CHOICES = [
        (NotificationTriggers.DIRECT_MESSAGE, "Direct message"),
        (NotificationTriggers.MENTION, "Mention"),
        (NotificationTriggers.TOPIC_WILDCARD_MENTION, "Topic wildcard mention"),
        (NotificationTriggers.STREAM_WILDCARD_MENTION, "Stream wildcard mention"),
        (NotificationTriggers.STREAM_EMAIL, "Stream notifications enabled"),
        (NotificationTriggers.FOLLOWED_TOPIC_EMAIL, "Followed topic notifications enabled"),
        (
            NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
            "Topic wildcard mention in followed topic",
        ),
        (
            NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
            "Stream wildcard mention in followed topic",
        ),
    ]

    trigger = models.TextField(choices=EMAIL_NOTIFICATION_TRIGGER_CHOICES)
    mentioned_user_group = models.ForeignKey(UserGroup, null=True, on_delete=CASCADE)

    # Timestamp for when the notification should be processed and sent.
    # Calculated from the time the event was received and the batching period.
    scheduled_timestamp = models.DateTimeField(db_index=True)


class APIScheduledStreamMessageDict(TypedDict):
    scheduled_message_id: int
    to: int
    type: str
    content: str
    rendered_content: str
    topic: str
    scheduled_delivery_timestamp: int
    failed: bool


class APIScheduledDirectMessageDict(TypedDict):
    scheduled_message_id: int
    to: List[int]
    type: str
    content: str
    rendered_content: str
    scheduled_delivery_timestamp: int
    failed: bool


class ScheduledMessage(models.Model):
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    subject = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)
    content = models.TextField()
    rendered_content = models.TextField()
    sending_client = models.ForeignKey(Client, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    scheduled_timestamp = models.DateTimeField(db_index=True)
    delivered = models.BooleanField(default=False)
    delivered_message = models.ForeignKey(Message, null=True, on_delete=CASCADE)
    has_attachment = models.BooleanField(default=False, db_index=True)

    # Metadata for messages that failed to send when their scheduled
    # moment arrived.
    failed = models.BooleanField(default=False)
    failure_message = models.TextField(null=True)

    SEND_LATER = 1
    REMIND = 2

    DELIVERY_TYPES = (
        (SEND_LATER, "send_later"),
        (REMIND, "remind"),
    )

    delivery_type = models.PositiveSmallIntegerField(
        choices=DELIVERY_TYPES,
        default=SEND_LATER,
    )

    class Meta:
        indexes = [
            # We expect a large number of delivered scheduled messages
            # to accumulate over time. This first index is for the
            # deliver_scheduled_messages worker.
            models.Index(
                name="zerver_unsent_scheduled_messages_by_time",
                fields=["scheduled_timestamp"],
                condition=Q(
                    delivered=False,
                    failed=False,
                ),
            ),
            # This index is for displaying scheduled messages to the
            # user themself via the API; we don't filter failed
            # messages since we will want to display those so that
            # failures don't just disappear into a black hole.
            models.Index(
                name="zerver_realm_unsent_scheduled_messages_by_user",
                fields=["realm_id", "sender", "delivery_type", "scheduled_timestamp"],
                condition=Q(
                    delivered=False,
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.recipient.label()} {self.subject} {self.sender!r} {self.scheduled_timestamp}"

    def topic_name(self) -> str:
        return self.subject

    def set_topic_name(self, topic_name: str) -> None:
        self.subject = topic_name

    def is_stream_message(self) -> bool:
        return self.recipient.type == Recipient.STREAM

    def to_dict(self) -> Union[APIScheduledStreamMessageDict, APIScheduledDirectMessageDict]:
        recipient, recipient_type_str = get_recipient_ids(self.recipient, self.sender.id)

        if recipient_type_str == "private":
            # The topic for direct messages should always be an empty string.
            assert self.topic_name() == ""

            return APIScheduledDirectMessageDict(
                scheduled_message_id=self.id,
                to=recipient,
                type=recipient_type_str,
                content=self.content,
                rendered_content=self.rendered_content,
                scheduled_delivery_timestamp=datetime_to_timestamp(self.scheduled_timestamp),
                failed=self.failed,
            )

        # The recipient for stream messages should always just be the unique stream ID.
        assert len(recipient) == 1

        return APIScheduledStreamMessageDict(
            scheduled_message_id=self.id,
            to=recipient[0],
            type=recipient_type_str,
            content=self.content,
            rendered_content=self.rendered_content,
            topic=self.topic_name(),
            scheduled_delivery_timestamp=datetime_to_timestamp(self.scheduled_timestamp),
            failed=self.failed,
        )


EMAIL_TYPES = {
    "account_registered": ScheduledEmail.WELCOME,
    "onboarding_zulip_topics": ScheduledEmail.WELCOME,
    "onboarding_zulip_guide": ScheduledEmail.WELCOME,
    "digest": ScheduledEmail.DIGEST,
    "invitation_reminder": ScheduledEmail.INVITATION_REMINDER,
}


class AbstractRealmAuditLog(models.Model):
    """Defines fields common to RealmAuditLog and RemoteRealmAuditLog."""

    event_time = models.DateTimeField(db_index=True)
    # If True, event_time is an overestimate of the true time. Can be used
    # by migrations when introducing a new event_type.
    backfilled = models.BooleanField(default=False)

    # Keys within extra_data, when extra_data is a json dict. Keys are strings because
    # json keys must always be strings.
    OLD_VALUE = "1"
    NEW_VALUE = "2"
    ROLE_COUNT = "10"
    ROLE_COUNT_HUMANS = "11"
    ROLE_COUNT_BOTS = "12"

    extra_data = models.JSONField(default=dict, encoder=DjangoJSONEncoder)

    # Event types
    USER_CREATED = 101
    USER_ACTIVATED = 102
    USER_DEACTIVATED = 103
    USER_REACTIVATED = 104
    USER_ROLE_CHANGED = 105
    USER_DELETED = 106
    USER_DELETED_PRESERVING_MESSAGES = 107

    USER_SOFT_ACTIVATED = 120
    USER_SOFT_DEACTIVATED = 121
    USER_PASSWORD_CHANGED = 122
    USER_AVATAR_SOURCE_CHANGED = 123
    USER_FULL_NAME_CHANGED = 124
    USER_EMAIL_CHANGED = 125
    USER_TERMS_OF_SERVICE_VERSION_CHANGED = 126
    USER_API_KEY_CHANGED = 127
    USER_BOT_OWNER_CHANGED = 128
    USER_DEFAULT_SENDING_STREAM_CHANGED = 129
    USER_DEFAULT_REGISTER_STREAM_CHANGED = 130
    USER_DEFAULT_ALL_PUBLIC_STREAMS_CHANGED = 131
    USER_SETTING_CHANGED = 132
    USER_DIGEST_EMAIL_CREATED = 133

    REALM_DEACTIVATED = 201
    REALM_REACTIVATED = 202
    REALM_SCRUBBED = 203
    REALM_PLAN_TYPE_CHANGED = 204
    REALM_LOGO_CHANGED = 205
    REALM_EXPORTED = 206
    REALM_PROPERTY_CHANGED = 207
    REALM_ICON_SOURCE_CHANGED = 208
    REALM_DISCOUNT_CHANGED = 209
    REALM_SPONSORSHIP_APPROVED = 210
    REALM_BILLING_METHOD_CHANGED = 211
    REALM_REACTIVATION_EMAIL_SENT = 212
    REALM_SPONSORSHIP_PENDING_STATUS_CHANGED = 213
    REALM_SUBDOMAIN_CHANGED = 214
    REALM_CREATED = 215
    REALM_DEFAULT_USER_SETTINGS_CHANGED = 216
    REALM_ORG_TYPE_CHANGED = 217
    REALM_DOMAIN_ADDED = 218
    REALM_DOMAIN_CHANGED = 219
    REALM_DOMAIN_REMOVED = 220
    REALM_PLAYGROUND_ADDED = 221
    REALM_PLAYGROUND_REMOVED = 222
    REALM_LINKIFIER_ADDED = 223
    REALM_LINKIFIER_CHANGED = 224
    REALM_LINKIFIER_REMOVED = 225
    REALM_EMOJI_ADDED = 226
    REALM_EMOJI_REMOVED = 227
    REALM_LINKIFIERS_REORDERED = 228

    SUBSCRIPTION_CREATED = 301
    SUBSCRIPTION_ACTIVATED = 302
    SUBSCRIPTION_DEACTIVATED = 303
    SUBSCRIPTION_PROPERTY_CHANGED = 304

    USER_MUTED = 350
    USER_UNMUTED = 351

    STRIPE_CUSTOMER_CREATED = 401
    STRIPE_CARD_CHANGED = 402
    STRIPE_PLAN_CHANGED = 403
    STRIPE_PLAN_QUANTITY_RESET = 404

    CUSTOMER_CREATED = 501
    CUSTOMER_PLAN_CREATED = 502
    CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN = 503

    STREAM_CREATED = 601
    STREAM_DEACTIVATED = 602
    STREAM_NAME_CHANGED = 603
    STREAM_REACTIVATED = 604
    STREAM_MESSAGE_RETENTION_DAYS_CHANGED = 605
    STREAM_PROPERTY_CHANGED = 607
    STREAM_GROUP_BASED_SETTING_CHANGED = 608

    USER_GROUP_CREATED = 701
    USER_GROUP_DELETED = 702
    USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED = 703
    USER_GROUP_DIRECT_USER_MEMBERSHIP_REMOVED = 704
    USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED = 705
    USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_REMOVED = 706
    USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED = 707
    USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_REMOVED = 708
    # 709 to 719 reserved for membership changes
    USER_GROUP_NAME_CHANGED = 720
    USER_GROUP_DESCRIPTION_CHANGED = 721
    USER_GROUP_GROUP_BASED_SETTING_CHANGED = 722

    # The following values are only for RemoteZulipServerAuditLog
    # Values should be exactly 10000 greater than the corresponding
    # value used for the same purpose in RealmAuditLog (e.g.
    # REALM_DEACTIVATED = 201, and REMOTE_SERVER_DEACTIVATED = 10201).
    REMOTE_SERVER_CREATED = 10215
    REMOTE_SERVER_PLAN_TYPE_CHANGED = 10204
    REMOTE_SERVER_DEACTIVATED = 10201

    event_type = models.PositiveSmallIntegerField()

    # event_types synced from on-prem installations to Zulip Cloud when
    # billing for mobile push notifications is enabled.  Every billing
    # event_type should have ROLE_COUNT populated in extra_data.
    SYNCED_BILLING_EVENTS = [
        USER_CREATED,
        USER_ACTIVATED,
        USER_DEACTIVATED,
        USER_REACTIVATED,
        USER_ROLE_CHANGED,
        REALM_DEACTIVATED,
        REALM_REACTIVATED,
    ]

    class Meta:
        abstract = True


class RealmAuditLog(AbstractRealmAuditLog):
    """
    RealmAuditLog tracks important changes to users, streams, and
    realms in Zulip.  It is intended to support both
    debugging/introspection (e.g. determining when a user's left a
    given stream?) as well as help with some database migrations where
    we might be able to do a better data backfill with it.  Here are a
    few key details about how this works:

    * acting_user is the user who initiated the state change
    * modified_user (if present) is the user being modified
    * modified_stream (if present) is the stream being modified
    * modified_user_group (if present) is the user group being modified

    For example:
    * When a user subscribes another user to a stream, modified_user,
      acting_user, and modified_stream will all be present and different.
    * When an administrator changes an organization's realm icon,
      acting_user is that administrator and modified_user,
      modified_stream and modified_user_group will be None.
    """

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    acting_user = models.ForeignKey(
        UserProfile,
        null=True,
        related_name="+",
        on_delete=CASCADE,
    )
    modified_user = models.ForeignKey(
        UserProfile,
        null=True,
        related_name="+",
        on_delete=CASCADE,
    )
    modified_stream = models.ForeignKey(
        Stream,
        null=True,
        on_delete=CASCADE,
    )
    modified_user_group = models.ForeignKey(
        UserGroup,
        null=True,
        on_delete=CASCADE,
    )
    event_last_message_id = models.IntegerField(null=True)

    def __str__(self) -> str:
        if self.modified_user is not None:
            return f"{self.modified_user!r} {self.event_type} {self.event_time} {self.id}"
        if self.modified_stream is not None:
            return f"{self.modified_stream!r} {self.event_type} {self.event_time} {self.id}"
        if self.modified_user_group is not None:
            return f"{self.modified_user_group!r} {self.event_type} {self.event_time} {self.id}"
        return f"{self.realm!r} {self.event_type} {self.event_time} {self.id}"

    class Meta:
        indexes = [
            models.Index(
                name="zerver_realmauditlog_user_subscriptions_idx",
                fields=["modified_user", "modified_stream"],
                condition=Q(
                    event_type__in=[
                        AbstractRealmAuditLog.SUBSCRIPTION_CREATED,
                        AbstractRealmAuditLog.SUBSCRIPTION_ACTIVATED,
                        AbstractRealmAuditLog.SUBSCRIPTION_DEACTIVATED,
                    ]
                ),
            )
        ]


class UserHotspot(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=CASCADE)
    hotspot = models.CharField(max_length=30)
    timestamp = models.DateTimeField(default=timezone_now)

    class Meta:
        unique_together = ("user", "hotspot")


def check_valid_user_ids(realm_id: int, val: object, allow_deactivated: bool = False) -> List[int]:
    user_ids = check_list(check_int)("User IDs", val)
    realm = Realm.objects.get(id=realm_id)
    for user_id in user_ids:
        # TODO: Structurally, we should be doing a bulk fetch query to
        # get the users here, not doing these in a loop.  But because
        # this is a rarely used feature and likely to never have more
        # than a handful of users, it's probably mostly OK.
        try:
            user_profile = get_user_profile_by_id_in_realm(user_id, realm)
        except UserProfile.DoesNotExist:
            raise ValidationError(_("Invalid user ID: {user_id}").format(user_id=user_id))

        if not allow_deactivated and not user_profile.is_active:
            raise ValidationError(
                _("User with ID {user_id} is deactivated").format(user_id=user_id)
            )

        if user_profile.is_bot:
            raise ValidationError(_("User with ID {user_id} is a bot").format(user_id=user_id))

    return user_ids


class CustomProfileField(models.Model):
    """Defines a form field for the per-realm custom profile fields feature.

    See CustomProfileFieldValue for an individual user's values for one of
    these fields.
    """

    HINT_MAX_LENGTH = 80
    NAME_MAX_LENGTH = 40
    MAX_DISPLAY_IN_PROFILE_SUMMARY_FIELDS = 2

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    name = models.CharField(max_length=NAME_MAX_LENGTH)
    hint = models.CharField(max_length=HINT_MAX_LENGTH, default="")

    # Sort order for display of custom profile fields.
    order = models.IntegerField(default=0)

    # Whether the field should be displayed in smaller summary
    # sections of a page displaying custom profile fields.
    display_in_profile_summary = models.BooleanField(default=False)

    SHORT_TEXT = 1
    LONG_TEXT = 2
    SELECT = 3
    DATE = 4
    URL = 5
    USER = 6
    EXTERNAL_ACCOUNT = 7
    PRONOUNS = 8

    # These are the fields whose validators require more than var_name
    # and value argument. i.e. SELECT require field_data, USER require
    # realm as argument.
    SELECT_FIELD_TYPE_DATA: List[ExtendedFieldElement] = [
        (SELECT, gettext_lazy("List of options"), validate_select_field, str, "SELECT"),
    ]
    USER_FIELD_TYPE_DATA: List[UserFieldElement] = [
        (USER, gettext_lazy("Person picker"), check_valid_user_ids, orjson.loads, "USER"),
    ]

    SELECT_FIELD_VALIDATORS: Dict[int, ExtendedValidator] = {
        item[0]: item[2] for item in SELECT_FIELD_TYPE_DATA
    }
    USER_FIELD_VALIDATORS: Dict[int, RealmUserValidator] = {
        item[0]: item[2] for item in USER_FIELD_TYPE_DATA
    }

    FIELD_TYPE_DATA: List[FieldElement] = [
        # Type, display name, validator, converter, keyword
        (SHORT_TEXT, gettext_lazy("Short text"), check_short_string, str, "SHORT_TEXT"),
        (LONG_TEXT, gettext_lazy("Long text"), check_long_string, str, "LONG_TEXT"),
        (DATE, gettext_lazy("Date picker"), check_date, str, "DATE"),
        (URL, gettext_lazy("Link"), check_url, str, "URL"),
        (
            EXTERNAL_ACCOUNT,
            gettext_lazy("External account"),
            check_short_string,
            str,
            "EXTERNAL_ACCOUNT",
        ),
        (PRONOUNS, gettext_lazy("Pronouns"), check_short_string, str, "PRONOUNS"),
    ]

    ALL_FIELD_TYPES = [*FIELD_TYPE_DATA, *SELECT_FIELD_TYPE_DATA, *USER_FIELD_TYPE_DATA]

    FIELD_VALIDATORS: Dict[int, Validator[ProfileDataElementValue]] = {
        item[0]: item[2] for item in FIELD_TYPE_DATA
    }
    FIELD_CONVERTERS: Dict[int, Callable[[Any], Any]] = {
        item[0]: item[3] for item in ALL_FIELD_TYPES
    }
    FIELD_TYPE_CHOICES: List[Tuple[int, StrPromise]] = [
        (item[0], item[1]) for item in ALL_FIELD_TYPES
    ]

    field_type = models.PositiveSmallIntegerField(
        choices=FIELD_TYPE_CHOICES,
        default=SHORT_TEXT,
    )

    # A JSON blob of any additional data needed to define the field beyond
    # type/name/hint.
    #
    # The format depends on the type.  Field types SHORT_TEXT, LONG_TEXT,
    # DATE, URL, and USER leave this empty.  Fields of type SELECT store the
    # choices' descriptions.
    #
    # Note: There is no performance overhead of using TextField in PostgreSQL.
    # See https://www.postgresql.org/docs/9.0/static/datatype-character.html
    field_data = models.TextField(default="")

    class Meta:
        unique_together = ("realm", "name")

    def __str__(self) -> str:
        return f"{self.realm!r} {self.name} {self.field_type} {self.order}"

    def as_dict(self) -> ProfileDataElementBase:
        data_as_dict: ProfileDataElementBase = {
            "id": self.id,
            "name": self.name,
            "type": self.field_type,
            "hint": self.hint,
            "field_data": self.field_data,
            "order": self.order,
        }
        if self.display_in_profile_summary:
            data_as_dict["display_in_profile_summary"] = True

        return data_as_dict

    def is_renderable(self) -> bool:
        if self.field_type in [CustomProfileField.SHORT_TEXT, CustomProfileField.LONG_TEXT]:
            return True
        return False


def custom_profile_fields_for_realm(realm_id: int) -> QuerySet[CustomProfileField]:
    return CustomProfileField.objects.filter(realm=realm_id).order_by("order")


class CustomProfileFieldValue(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    field = models.ForeignKey(CustomProfileField, on_delete=CASCADE)
    value = models.TextField()
    rendered_value = models.TextField(null=True, default=None)

    class Meta:
        unique_together = ("user_profile", "field")

    def __str__(self) -> str:
        return f"{self.user_profile!r} {self.field!r} {self.value}"


# Interfaces for services
# They provide additional functionality like parsing message to obtain query URL, data to be sent to URL,
# and parsing the response.
GENERIC_INTERFACE = "GenericService"
SLACK_INTERFACE = "SlackOutgoingWebhookService"


# A Service corresponds to either an outgoing webhook bot or an embedded bot.
# The type of Service is determined by the bot_type field of the referenced
# UserProfile.
#
# If the Service is an outgoing webhook bot:
# - name is any human-readable identifier for the Service
# - base_url is the address of the third-party site
# - token is used for authentication with the third-party site
#
# If the Service is an embedded bot:
# - name is the canonical name for the type of bot (e.g. 'xkcd' for an instance
#   of the xkcd bot); multiple embedded bots can have the same name, but all
#   embedded bots with the same name will run the same code
# - base_url and token are currently unused
class Service(models.Model):
    name = models.CharField(max_length=UserProfile.MAX_NAME_LENGTH)
    # Bot user corresponding to the Service.  The bot_type of this user
    # determines the type of service.  If non-bot services are added later,
    # user_profile can also represent the owner of the Service.
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    base_url = models.TextField()
    token = models.TextField()
    # Interface / API version of the service.
    interface = models.PositiveSmallIntegerField(default=1)

    # Valid interfaces are {generic, zulip_bot_service, slack}
    GENERIC = 1
    SLACK = 2

    ALLOWED_INTERFACE_TYPES = [
        GENERIC,
        SLACK,
    ]
    # N.B. If we used Django's choice=... we would get this for free (kinda)
    _interfaces: Dict[int, str] = {
        GENERIC: GENERIC_INTERFACE,
        SLACK: SLACK_INTERFACE,
    }

    def interface_name(self) -> str:
        # Raises KeyError if invalid
        return self._interfaces[self.interface]


def get_bot_services(user_profile_id: int) -> List[Service]:
    return list(Service.objects.filter(user_profile_id=user_profile_id))


def get_service_profile(user_profile_id: int, service_name: str) -> Service:
    return Service.objects.get(user_profile_id=user_profile_id, name=service_name)


class BotStorageData(models.Model):
    bot_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    key = models.TextField(db_index=True)
    value = models.TextField()

    class Meta:
        unique_together = ("bot_profile", "key")


class BotConfigData(models.Model):
    bot_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    key = models.TextField(db_index=True)
    value = models.TextField()

    class Meta:
        unique_together = ("bot_profile", "key")


class InvalidFakeEmailDomainError(Exception):
    pass


def get_fake_email_domain(realm: Realm) -> str:
    try:
        # Check that realm.host can be used to form valid email addresses.
        validate_email(Address(username="bot", domain=realm.host).addr_spec)
        return realm.host
    except ValidationError:
        pass

    try:
        # Check that the fake email domain can be used to form valid email addresses.
        validate_email(Address(username="bot", domain=settings.FAKE_EMAIL_DOMAIN).addr_spec)
    except ValidationError:
        raise InvalidFakeEmailDomainError(
            settings.FAKE_EMAIL_DOMAIN + " is not a valid domain. "
            "Consider setting the FAKE_EMAIL_DOMAIN setting."
        )

    return settings.FAKE_EMAIL_DOMAIN


class AlertWord(models.Model):
    # Realm isn't necessary, but it's a nice denormalization.  Users
    # never move to another realm, so it's static, and having Realm
    # here optimizes the main query on this table, which is fetching
    # all the alert words in a realm.
    realm = models.ForeignKey(Realm, db_index=True, on_delete=CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    # Case-insensitive name for the alert word.
    word = models.TextField()

    class Meta:
        unique_together = ("user_profile", "word")


def flush_realm_alert_words(realm_id: int) -> None:
    cache_delete(realm_alert_words_cache_key(realm_id))
    cache_delete(realm_alert_words_automaton_cache_key(realm_id))


def flush_alert_word(*, instance: AlertWord, **kwargs: object) -> None:
    realm_id = instance.realm_id
    flush_realm_alert_words(realm_id)


post_save.connect(flush_alert_word, sender=AlertWord)
post_delete.connect(flush_alert_word, sender=AlertWord)
