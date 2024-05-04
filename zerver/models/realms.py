from email.headerregistry import Address
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, TypedDict, Union
from uuid import uuid4

import django.contrib.auth
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models import CASCADE, Q, QuerySet, Sum
from django.db.models.signals import post_delete, post_save, pre_delete
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext_lazy
from typing_extensions import override

from zerver.lib.cache import cache_with_key, flush_realm, get_realm_used_upload_space_cache_key
from zerver.lib.exceptions import JsonableError
from zerver.lib.pysa import mark_sanitized
from zerver.lib.types import GroupPermissionSetting
from zerver.lib.utils import generate_api_key
from zerver.models.constants import MAX_LANGUAGE_ID_LENGTH
from zerver.models.groups import SystemGroups
from zerver.models.users import UserProfile

if TYPE_CHECKING:
    # We use ModelBackend only for typing. Importing it otherwise causes circular dependency.
    from django.contrib.auth.backends import ModelBackend

    from zerver.models import Stream

SECONDS_PER_DAY = 86400


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


def generate_realm_uuid_owner_secret() -> str:
    token = generate_api_key()

    # We include a prefix to facilitate scanning for accidental
    # disclosure of secrets e.g. in Github commit pushes.
    return f"zuliprealm_{token}"


class OrgTypeEnum(Enum):
    Unspecified = 0
    Business = 10
    OpenSource = 20
    EducationNonProfit = 30
    Education = 35
    Research = 40
    Event = 50
    NonProfit = 60
    Government = 70
    PoliticalGroup = 80
    Community = 90
    Personal = 100
    Other = 1000


class OrgTypeDict(TypedDict):
    name: str
    id: int
    hidden: bool
    display_order: int
    onboarding_zulip_guide_url: Optional[str]


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

    # uuid and a secret for the sake of per-realm authentication with the push notification
    # bouncer.
    uuid = models.UUIDField(default=uuid4, unique=True)
    uuid_owner_secret = models.TextField(default=generate_realm_uuid_owner_secret)
    # Whether push notifications are working for this realm, and
    # whether there is a specific date at which we expect that to
    # cease to be the case.
    push_notifications_enabled = models.BooleanField(default=False, db_index=True)
    push_notifications_enabled_end_timestamp = models.DateTimeField(default=None, null=True)

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

    require_unique_names = models.BooleanField(default=False)
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
    delete_own_message_policy = models.PositiveSmallIntegerField(default=POLICY_EVERYONE)

    # Who in the organization is allowed to edit topics of any message.
    edit_topic_policy = models.PositiveSmallIntegerField(default=POLICY_EVERYONE)

    # Who in the organization is allowed to invite other users to organization.
    invite_to_realm_policy = models.PositiveSmallIntegerField(default=POLICY_MEMBERS_ONLY)

    # UserGroup whose members are allowed to create invite link.
    create_multiuse_invite_group = models.ForeignKey(
        "UserGroup", on_delete=models.RESTRICT, related_name="+"
    )

    # on_delete field here is set to RESTRICT because we don't want to allow
    # deleting a user group in case it is referenced by this setting.
    # We are not using PROTECT since we want to allow deletion of user groups
    # when realm itself is deleted.
    can_access_all_users_group = models.ForeignKey(
        "UserGroup", on_delete=models.RESTRICT, related_name="+"
    )

    # Who in the organization is allowed to invite other users to streams.
    invite_to_stream_policy = models.PositiveSmallIntegerField(default=POLICY_MEMBERS_ONLY)

    # Who in the organization is allowed to move messages between streams.
    move_messages_between_streams_policy = models.PositiveSmallIntegerField(
        default=POLICY_MEMBERS_ONLY
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
    STREAM_EVENTS_NOTIFICATION_TOPIC_NAME = gettext_lazy("channel events")
    new_stream_announcements_stream = models.ForeignKey(
        "Stream",
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    signup_announcements_stream = models.ForeignKey(
        "Stream",
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    ZULIP_UPDATE_ANNOUNCEMENTS_TOPIC_NAME = gettext_lazy("Zulip updates")
    zulip_update_announcements_stream = models.ForeignKey(
        "Stream",
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    zulip_update_announcements_level = models.PositiveIntegerField(null=True)

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
    ORG_TYPES: Dict[str, OrgTypeDict] = {
        "unspecified": {
            "name": "Unspecified",
            "id": OrgTypeEnum.Unspecified.value,
            "hidden": True,
            "display_order": 0,
            "onboarding_zulip_guide_url": None,
        },
        "business": {
            "name": "Business",
            "id": OrgTypeEnum.Business.value,
            "hidden": False,
            "display_order": 1,
            "onboarding_zulip_guide_url": "https://zulip.com/for/business/",
        },
        "opensource": {
            "name": "Open-source project",
            "id": OrgTypeEnum.OpenSource.value,
            "hidden": False,
            "display_order": 2,
            "onboarding_zulip_guide_url": "https://zulip.com/for/open-source/",
        },
        "education_nonprofit": {
            "name": "Education (non-profit)",
            "id": OrgTypeEnum.EducationNonProfit.value,
            "hidden": False,
            "display_order": 3,
            "onboarding_zulip_guide_url": "https://zulip.com/for/education/",
        },
        "education": {
            "name": "Education (for-profit)",
            "id": OrgTypeEnum.Education.value,
            "hidden": False,
            "display_order": 4,
            "onboarding_zulip_guide_url": "https://zulip.com/for/education/",
        },
        "research": {
            "name": "Research",
            "id": OrgTypeEnum.Research.value,
            "hidden": False,
            "display_order": 5,
            "onboarding_zulip_guide_url": "https://zulip.com/for/research/",
        },
        "event": {
            "name": "Event or conference",
            "id": OrgTypeEnum.Event.value,
            "hidden": False,
            "display_order": 6,
            "onboarding_zulip_guide_url": "https://zulip.com/for/events/",
        },
        "nonprofit": {
            "name": "Non-profit (registered)",
            "id": OrgTypeEnum.NonProfit.value,
            "hidden": False,
            "display_order": 7,
            "onboarding_zulip_guide_url": "https://zulip.com/for/communities/",
        },
        "government": {
            "name": "Government",
            "id": OrgTypeEnum.Government.value,
            "hidden": False,
            "display_order": 8,
            "onboarding_zulip_guide_url": None,
        },
        "political_group": {
            "name": "Political group",
            "id": OrgTypeEnum.PoliticalGroup.value,
            "hidden": False,
            "display_order": 9,
            "onboarding_zulip_guide_url": None,
        },
        "community": {
            "name": "Community",
            "id": OrgTypeEnum.Community.value,
            "hidden": False,
            "display_order": 10,
            "onboarding_zulip_guide_url": "https://zulip.com/for/communities/",
        },
        "personal": {
            "name": "Personal",
            "id": OrgTypeEnum.Personal.value,
            "hidden": False,
            "display_order": 100,
            "onboarding_zulip_guide_url": None,
        },
        "other": {
            "name": "Other",
            "id": OrgTypeEnum.Other.value,
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
    UPGRADE_TEXT_PLUS = gettext_lazy("Available on Zulip Cloud Plus. Upgrade to access.")
    # plan_type controls various features around resource/feature
    # limitations for a Zulip organization on multi-tenant installations
    # like Zulip Cloud.
    PLAN_TYPE_SELF_HOSTED = 1
    PLAN_TYPE_LIMITED = 2
    PLAN_TYPE_STANDARD = 3
    PLAN_TYPE_STANDARD_FREE = 4
    PLAN_TYPE_PLUS = 10

    # Used for creating realms with different plan types.
    ALL_PLAN_TYPES = {
        PLAN_TYPE_SELF_HOSTED: "self-hosted-plan",
        PLAN_TYPE_LIMITED: "limited-plan",
        PLAN_TYPE_STANDARD: "standard-plan",
        PLAN_TYPE_STANDARD_FREE: "standard-free-plan",
        PLAN_TYPE_PLUS: "plus-plan",
    }
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

    UPLOAD_QUOTA_LIMITED = 5
    UPLOAD_QUOTA_STANDARD_FREE = 50
    custom_upload_quota_gb = models.IntegerField(null=True)

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

    JITSI_SERVER_SPECIAL_VALUES_MAP = {"default": None}
    jitsi_server_url = models.URLField(null=True, default=None)

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

    # Whether clients should display "(guest)" after names of guest users.
    enable_guest_user_indicator = models.BooleanField(default=True)

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
        enable_guest_user_indicator=bool,
        enable_read_receipts=bool,
        enable_spectator_access=bool,
        giphy_rating=int,
        inline_image_preview=bool,
        inline_url_embed_preview=bool,
        invite_required=bool,
        invite_to_realm_policy=int,
        invite_to_stream_policy=int,
        jitsi_server_url=(str, type(None)),
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
        push_notifications_enabled=bool,
        require_unique_names=bool,
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
            default_group_name=SystemGroups.ADMINISTRATORS,
            id_field_name="create_multiuse_invite_group_id",
        ),
        can_access_all_users_group=GroupPermissionSetting(
            require_system_group=True,
            allow_internet_group=False,
            allow_owners_group=False,
            allow_nobody_group=False,
            allow_everyone_group=True,
            default_group_name=SystemGroups.EVERYONE,
            id_field_name="can_access_all_users_group_id",
            allowed_system_groups=[SystemGroups.EVERYONE, SystemGroups.MEMBERS],
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

    @override
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
        from zproject.backends import AUTH_BACKEND_NAME_MAP

        ret: Dict[str, bool] = {}
        supported_backends = [type(backend) for backend in supported_auth_backends()]

        for backend_name, backend_class in AUTH_BACKEND_NAME_MAP.items():
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
        return get_fake_email_domain(self.host)

    def get_new_stream_announcements_stream(self) -> Optional["Stream"]:
        if (
            self.new_stream_announcements_stream is not None
            and not self.new_stream_announcements_stream.deactivated
        ):
            return self.new_stream_announcements_stream
        return None

    def get_signup_announcements_stream(self) -> Optional["Stream"]:
        if (
            self.signup_announcements_stream is not None
            and not self.signup_announcements_stream.deactivated
        ):
            return self.signup_announcements_stream
        return None

    def get_zulip_update_announcements_stream(self) -> Optional["Stream"]:
        if (
            self.zulip_update_announcements_stream is not None
            and not self.zulip_update_announcements_stream.deactivated
        ):
            return self.zulip_update_announcements_stream
        return None

    @property
    def max_invites(self) -> int:
        if self._max_invites is None:
            return settings.INVITES_DEFAULT_REALM_DAILY_MAX
        return self._max_invites

    @max_invites.setter
    def max_invites(self, value: Optional[int]) -> None:
        self._max_invites = value

    @property
    def upload_quota_gb(self) -> Optional[int]:
        # See upload_quota_bytes; don't interpret upload_quota_gb directly.

        if self.custom_upload_quota_gb is not None:
            return self.custom_upload_quota_gb

        if not settings.CORPORATE_ENABLED:
            return None

        plan_type = self.plan_type
        if plan_type == Realm.PLAN_TYPE_SELF_HOSTED:  # nocoverage
            return None
        if plan_type == Realm.PLAN_TYPE_LIMITED:
            return Realm.UPLOAD_QUOTA_LIMITED
        elif plan_type == Realm.PLAN_TYPE_STANDARD_FREE:
            return Realm.UPLOAD_QUOTA_STANDARD_FREE
        elif plan_type in [Realm.PLAN_TYPE_STANDARD, Realm.PLAN_TYPE_PLUS]:
            from corporate.lib.stripe import get_cached_seat_count

            # Paying customers with few users should get a reasonable minimum quota.
            return max(
                get_cached_seat_count(self) * settings.UPLOAD_QUOTA_PER_USER_GB,
                Realm.UPLOAD_QUOTA_STANDARD_FREE,
            )
        else:
            raise AssertionError("Invalid plan type")

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
        from zerver.models import Attachment

        used_space = Attachment.objects.filter(realm=realm).aggregate(Sum("size"))["size__sum"]
        if used_space is None:
            return 0
        return used_space

    def ensure_not_on_limited_plan(self) -> None:
        if self.plan_type == Realm.PLAN_TYPE_LIMITED:
            raise JsonableError(str(self.UPGRADE_TEXT_STANDARD))

    def can_enable_restricted_user_access_for_guests(self) -> None:
        if self.plan_type not in [Realm.PLAN_TYPE_PLUS, Realm.PLAN_TYPE_SELF_HOSTED]:
            raise JsonableError(str(self.UPGRADE_TEXT_PLUS))

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


def require_unique_names(realm: Optional[Realm]) -> bool:
    if realm is None:
        # realm is None when a new realm is being created.
        return False
    return realm.require_unique_names


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


class InvalidFakeEmailDomainError(Exception):
    pass


def get_fake_email_domain(realm_host: str) -> str:
    try:
        # Check that realm.host can be used to form valid email addresses.
        validate_email(Address(username="bot", domain=realm_host).addr_spec)
        return realm_host
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
