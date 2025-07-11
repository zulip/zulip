from email.headerregistry import Address
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.db import models
from django.db.models import CASCADE, F, Q, QuerySet
from django.db.models.functions import Upper
from django.db.models.signals import post_save
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext_lazy
from typing_extensions import override

from zerver.lib.cache import (
    active_non_guest_user_ids_cache_key,
    active_user_ids_cache_key,
    bot_dict_fields,
    bot_dicts_in_realm_cache_key,
    bot_profile_cache_key,
    cache_with_key,
    flush_user_profile,
    realm_user_dict_fields,
    realm_user_dicts_cache_key,
    user_profile_by_api_key_cache_key,
    user_profile_by_email_realm_cache_key,
    user_profile_by_id_cache_key,
    user_profile_narrow_by_id_cache_key,
)
from zerver.lib.types import ProfileData, RawUserDict
from zerver.lib.utils import generate_api_key
from zerver.models.constants import MAX_LANGUAGE_ID_LENGTH

if TYPE_CHECKING:
    from zerver.models import Realm


class ResolvedTopicNoticeAutoReadPolicyEnum(Enum):
    # The case is used by Pydantic in the API
    always = 1
    except_followed = 2
    never = 3


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

    ### Preferences. ###
    # left_side_userlist was removed from the UI in Zulip 6.0; the
    # database model is being temporarily preserved in case we want to
    # restore a version of the setting, preserving who had it enabled.
    left_side_userlist = models.BooleanField(default=False)
    default_language = models.CharField(default="en", max_length=MAX_LANGUAGE_ID_LENGTH)
    # This setting controls which view is rendered first when Zulip loads.
    # Values for it are URL suffix after `#`.
    web_home_view = models.TextField(default="inbox")
    web_escape_navigates_to_home_view = models.BooleanField(default=True)
    fluid_layout_width = models.BooleanField(default=False)
    high_contrast_mode = models.BooleanField(default=False)
    translate_emoticons = models.BooleanField(default=False)
    display_emoji_reaction_users = models.BooleanField(default=True)
    twenty_four_hour_time = models.BooleanField(default=False)
    starred_message_counts = models.BooleanField(default=True)
    web_suggest_update_timezone = models.BooleanField(default=True)
    COLOR_SCHEME_AUTOMATIC = 1
    COLOR_SCHEME_DARK = 2
    COLOR_SCHEME_LIGHT = 3
    COLOR_SCHEME_CHOICES = [COLOR_SCHEME_AUTOMATIC, COLOR_SCHEME_DARK, COLOR_SCHEME_LIGHT]
    color_scheme = models.PositiveSmallIntegerField(default=COLOR_SCHEME_AUTOMATIC)

    # Information density is established through
    # adjustments to the font size and line height.
    WEB_FONT_SIZE_PX_COMPACT = 14
    WEB_FONT_SIZE_PX_DEFAULT = 16
    WEB_LINE_HEIGHT_PERCENT_COMPACT = 122
    WEB_LINE_HEIGHT_PERCENT_DEFAULT = 140
    web_font_size_px = models.PositiveSmallIntegerField(default=WEB_FONT_SIZE_PX_DEFAULT)
    web_line_height_percent = models.PositiveSmallIntegerField(
        default=WEB_LINE_HEIGHT_PERCENT_DEFAULT
    )

    # UI setting to control how animated images are played.
    web_animate_image_previews = models.TextField(default="on_hover")

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

    # UI setting controlling if clicking on a channel link should open
    # the channel feed (interleaved view) or narrow to the first topic
    # in the channel.

    WEB_CHANNEL_DEFAULT_VIEW_FIRST_TOPIC = 1
    WEB_CHANNEL_DEFAULT_VIEW_CHANNEL_FEED = 2
    WEB_CHANNEL_DEFAULT_VIEW_TOPIC_LIST = 3
    WEB_CHANNEL_DEFAULT_VIEW_TOP_UNREAD = 4

    WEB_CHANNEL_DEFAULT_VIEW_CHOICES = [
        WEB_CHANNEL_DEFAULT_VIEW_FIRST_TOPIC,
        WEB_CHANNEL_DEFAULT_VIEW_TOPIC_LIST,
        WEB_CHANNEL_DEFAULT_VIEW_CHANNEL_FEED,
        WEB_CHANNEL_DEFAULT_VIEW_TOP_UNREAD,
    ]

    web_channel_default_view = models.SmallIntegerField(
        default=WEB_CHANNEL_DEFAULT_VIEW_FIRST_TOPIC,
        db_default=WEB_CHANNEL_DEFAULT_VIEW_FIRST_TOPIC,
    )

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
    user_list_style = models.PositiveSmallIntegerField(default=USER_LIST_STYLE_WITH_AVATAR)

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

    web_left_sidebar_unreads_count_summary = models.BooleanField(default=True, db_default=True)

    # Setting to control whether to automatically go to the
    # conversation where message was sent.
    web_navigate_to_sent_message = models.BooleanField(default=True)

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
    DESKTOP_ICON_COUNT_DISPLAY_DM_MENTION_FOLLOWED_TOPIC = 2
    DESKTOP_ICON_COUNT_DISPLAY_DM_MENTION = 3
    DESKTOP_ICON_COUNT_DISPLAY_NONE = 4
    DESKTOP_ICON_COUNT_DISPLAY_CHOICES = [
        DESKTOP_ICON_COUNT_DISPLAY_MESSAGES,
        DESKTOP_ICON_COUNT_DISPLAY_DM_MENTION,
        DESKTOP_ICON_COUNT_DISPLAY_DM_MENTION_FOLLOWED_TOPIC,
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

    # The following two settings control which topics to automatically
    # 'follow' or 'unmute in a muted stream', respectively.
    # Follow or unmute a topic automatically on:
    # - PARTICIPATION: Send a message, React to a message, Participate in a poll or Edit a TO-DO list.
    # - SEND: Send a message.
    # - INITIATION: Send the first message in the topic.
    # - NEVER: Never automatically follow or unmute a topic.
    AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_PARTICIPATION = 1
    AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_SEND = 2
    AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_INITIATION = 3
    AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER = 4
    AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES = [
        AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_PARTICIPATION,
        AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_SEND,
        AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_INITIATION,
        AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER,
    ]
    automatically_follow_topics_policy = models.PositiveSmallIntegerField(
        default=AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_INITIATION,
    )
    automatically_unmute_topics_in_muted_streams_policy = models.PositiveSmallIntegerField(
        default=AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_SEND,
    )
    automatically_follow_topics_where_mentioned = models.BooleanField(default=True)

    resolved_topic_notice_auto_read_policy = models.PositiveSmallIntegerField(
        default=ResolvedTopicNoticeAutoReadPolicyEnum.except_followed.value,
        db_default=ResolvedTopicNoticeAutoReadPolicyEnum.except_followed.value,
    )
    RESOLVED_TOPIC_NOTICE_AUTO_READ_POLICY_TYPES = list(ResolvedTopicNoticeAutoReadPolicyEnum)

    # Whether or not the user wants to sync their drafts.
    enable_drafts_synchronization = models.BooleanField(default=True)

    # Privacy settings
    send_stream_typing_notifications = models.BooleanField(default=True)
    send_private_typing_notifications = models.BooleanField(default=True)
    send_read_receipts = models.BooleanField(default=True)
    allow_private_data_export = models.BooleanField(default=False)

    # Whether the user wants to see typing notifications.
    receives_typing_notifications = models.BooleanField(default=True)

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

    # Whether user wants to see AI features in the UI.
    hide_ai_features = models.BooleanField(default=False)

    display_settings_legacy = dict(
        # Don't add anything new to this legacy dict.
        # Instead, see `modern_settings` below.
        color_scheme=int,
        default_language=str,
        web_home_view=str,
        demote_inactive_streams=int,
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
        web_escape_navigates_to_home_view=bool,
        receives_typing_notifications=bool,
        send_private_typing_notifications=bool,
        send_read_receipts=bool,
        send_stream_typing_notifications=bool,
        allow_private_data_export=bool,
        web_mark_read_on_scroll_policy=int,
        web_channel_default_view=int,
        user_list_style=int,
        web_animate_image_previews=str,
        web_stream_unreads_count_display_policy=int,
        web_font_size_px=int,
        web_line_height_percent=int,
        web_navigate_to_sent_message=bool,
        web_suggest_update_timezone=bool,
        hide_ai_features=bool,
        resolved_topic_notice_auto_read_policy=ResolvedTopicNoticeAutoReadPolicyEnum,
        web_left_sidebar_unreads_count_summary=bool,
    )

    modern_notification_settings = dict(
        # Add new notification settings here.
        enable_followed_topic_desktop_notifications=bool,
        enable_followed_topic_email_notifications=bool,
        enable_followed_topic_push_notifications=bool,
        enable_followed_topic_audible_notifications=bool,
        enable_followed_topic_wildcard_mentions_notify=bool,
        automatically_follow_topics_policy=int,
        automatically_unmute_topics_in_muted_streams_policy=int,
        automatically_follow_topics_where_mentioned=bool,
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

    # Settings where security policy may restrict the ability of
    # organization administrators to change this setting for other
    # accounts.
    #
    # Core account fields like name and email address are not part of
    # the property_types framework and thus do not appear here.
    SECURITY_SENSITIVE_USER_SETTINGS = frozenset(
        {
            # Data privacy controls
            "allow_private_data_export",
            "email_address_visibility",
            # Email notification controls
            "enable_digest_emails",
            "enable_login_emails",
            "enable_marketing_emails",
            # Availability/presence privacy controls
            "presence_enabled",
            "send_private_typing_notifications",
            "send_read_receipts",
            "send_stream_typing_notifications",
        }
    )

    class Meta:
        abstract = True

    @staticmethod
    def emojiset_choices() -> list[dict[str, str]]:
        return [
            dict(key=emojiset[0], text=emojiset[1]) for emojiset in UserProfile.EMOJISET_CHOICES
        ]


class RealmUserDefault(UserBaseSettings):
    """This table stores realm-level default values for user preferences
    like notification settings, used when creating a new user account.
    """

    realm = models.OneToOneField("zerver.Realm", on_delete=CASCADE)


class UserProfile(AbstractBaseUser, PermissionsMixin, UserBaseSettings):
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

    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")

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

    realm = models.ForeignKey("zerver.Realm", on_delete=CASCADE)
    # Foreign key to the Recipient object for PERSONAL type messages to this user.
    recipient = models.ForeignKey("zerver.Recipient", null=True, on_delete=models.SET_NULL)

    INACCESSIBLE_USER_NAME = gettext_lazy("Unknown user")
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

    # Maps: user_profile.role -> which email_address_visibility values
    # allow user_profile to see their email address.
    ROLE_TO_ACCESSIBLE_EMAIL_ADDRESS_VISIBILITY_IDS = {
        ROLE_REALM_OWNER: [
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_MODERATORS,
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_MEMBERS,
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
        ],
        ROLE_REALM_ADMINISTRATOR: [
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_MODERATORS,
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_MEMBERS,
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
        ],
        ROLE_MODERATOR: [
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_MODERATORS,
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_MEMBERS,
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
        ],
        ROLE_MEMBER: [
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_MEMBERS,
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
        ],
        ROLE_GUEST: [
            UserBaseSettings.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
        ],
    }

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
    # Users with this flag can change email addresses of users in the realm via the API.
    can_change_user_emails = models.BooleanField(default=False, db_index=True)

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
    # https://docs.djangoproject.com/en/5.0/ref/models/fields/#django.db.models.Field.null.
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
    # This is only used for LDAP-provided avatars; it contains the
    # SHA256 hex digest of most recent raw contents that LDAP provided
    # us, pre-thumbnailing.
    avatar_hash = models.CharField(null=True, max_length=64)

    zoom_token = models.JSONField(default=None, null=True)

    objects = UserManager()

    ROLE_ID_TO_NAME_MAP = {
        ROLE_REALM_OWNER: gettext_lazy("Organization owner"),
        ROLE_REALM_ADMINISTRATOR: gettext_lazy("Organization administrator"),
        ROLE_MODERATOR: gettext_lazy("Moderator"),
        ROLE_MEMBER: gettext_lazy("Member"),
        ROLE_GUEST: gettext_lazy("Guest"),
    }

    # Mapping of role ids to simple string identifiers for the roles,
    # to be used in API contexts such as SCIM provisioning.
    ROLE_ID_TO_API_NAME = {
        ROLE_REALM_OWNER: "owner",
        ROLE_REALM_ADMINISTRATOR: "administrator",
        ROLE_MODERATOR: "moderator",
        ROLE_MEMBER: "member",
        ROLE_GUEST: "guest",
    }
    ROLE_API_NAME_TO_ID = {v: k for k, v in ROLE_ID_TO_API_NAME.items()}

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "realm",
                Upper(F("email")),
                name="zerver_userprofile_realm_id_email_uniq",
            ),
            models.UniqueConstraint(
                "realm",
                Upper(F("delivery_email")),
                name="zerver_userprofile_realm_id_delivery_email_uniq",
            ),
        ]
        indexes = [
            models.Index(Upper("email"), name="upper_userprofile_email_idx"),
        ]

    @override
    def __str__(self) -> str:
        return f"{self.email} {self.realm!r}"

    def get_role_name(self) -> str:
        return str(self.ROLE_ID_TO_NAME_MAP[self.role])

    def profile_data(self) -> ProfileData:
        from zerver.models import CustomProfileFieldValue
        from zerver.models.custom_profile_fields import custom_profile_fields_for_realm

        values = CustomProfileFieldValue.objects.filter(user_profile=self)
        user_data = {
            v.field_id: {"value": v.value, "rendered_value": v.rendered_value} for v in values
        }
        data: ProfileData = []
        for field in custom_profile_fields_for_realm(self.realm_id):
            field_values = user_data.get(field.id, None)
            if field_values:
                value, rendered_value = (
                    field_values.get("value"),
                    field_values.get("rendered_value"),
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
        return self.has_permission("can_manage_billing_group")

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
        return self.is_realm_admin or self.role == UserProfile.ROLE_MODERATOR

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
    def allowed_bot_types(self) -> list[int]:
        allowed_bot_types = []
        if self.has_permission("can_create_bots_group"):
            allowed_bot_types.extend(
                [
                    UserProfile.DEFAULT_BOT,
                    UserProfile.INCOMING_WEBHOOK_BOT,
                    UserProfile.OUTGOING_WEBHOOK_BOT,
                ]
            )
            if settings.EMBEDDED_BOTS_ENABLED:
                allowed_bot_types.append(UserProfile.EMBEDDED_BOT)
        elif self.has_permission("can_create_write_only_bots_group"):
            allowed_bot_types.append(UserProfile.INCOMING_WEBHOOK_BOT)
        return allowed_bot_types

    def email_address_is_realm_public(self) -> bool:
        # Bots always have EMAIL_ADDRESS_VISIBILITY_EVERYONE.
        if self.email_address_visibility == UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE:
            return True
        return False

    def has_permission(self, policy_name: str, realm: Optional["Realm"] = None) -> bool:
        from zerver.lib.user_groups import user_has_permission_for_group_setting
        from zerver.models import Realm

        if policy_name not in Realm.REALM_PERMISSION_GROUP_SETTINGS:
            raise AssertionError("Invalid policy")

        if realm is None:
            # realm is passed by the caller only when we optimize
            # the number of database queries by fetching the group
            # setting fields using select_related.
            realm = self.realm
        allowed_user_group_id = getattr(realm, policy_name).id
        setting_config = Realm.REALM_PERMISSION_GROUP_SETTINGS[policy_name]
        return user_has_permission_for_group_setting(allowed_user_group_id, self, setting_config)

    def can_create_public_streams(self, realm: Optional["Realm"] = None) -> bool:
        return self.has_permission("can_create_public_channel_group", realm)

    def can_create_private_streams(self, realm: Optional["Realm"] = None) -> bool:
        return self.has_permission("can_create_private_channel_group", realm)

    def can_create_web_public_streams(self) -> bool:
        if not self.realm.web_public_streams_enabled():
            return False
        return self.has_permission("can_create_web_public_channel_group")

    def can_manage_default_streams(self) -> bool:
        return self.is_realm_admin

    def can_subscribe_others_to_all_accessible_streams(self) -> bool:
        return self.has_permission("can_add_subscribers_group")

    def can_invite_users_by_email(self, realm: Optional["Realm"] = None) -> bool:
        return self.has_permission("can_invite_users_group", realm)

    def can_create_multiuse_invite_to_realm(self) -> bool:
        return self.has_permission("create_multiuse_invite_group")

    def can_move_messages_between_streams(self) -> bool:
        return self.has_permission("can_move_messages_between_channels_group")

    def can_create_user_groups(self) -> bool:
        return self.has_permission("can_create_groups")

    def can_manage_all_groups(self) -> bool:
        return self.has_permission("can_manage_all_groups")

    def can_move_messages_to_another_topic(self) -> bool:
        return self.has_permission("can_move_messages_between_topics_group")

    def can_resolve_topic(self) -> bool:
        return self.has_permission("can_resolve_topics_group")

    def can_add_custom_emoji(self) -> bool:
        return self.has_permission("can_add_custom_emoji_group")

    def can_delete_any_message(self) -> bool:
        return self.has_permission("can_delete_any_message_group")

    def can_delete_own_message(self) -> bool:
        return self.has_permission("can_delete_own_message_group")

    def can_set_delete_message_policy(self) -> bool:
        return self.is_realm_admin or self.has_permission("can_set_delete_message_policy_group")

    def can_set_topics_policy(self) -> bool:
        return self.is_realm_admin or self.has_permission("can_set_topics_policy_group")

    def can_summarize_topics(self) -> bool:
        return self.has_permission("can_summarize_topics_group")

    def can_access_public_streams(self) -> bool:
        return not (self.is_guest or self.realm.is_zephyr_mirror_realm)

    def major_tos_version(self) -> int:
        if self.tos_version is not None:
            return int(self.tos_version.split(".")[0])
        else:
            return -1

    def format_requester_for_logs(self) -> str:
        return "{}@{}".format(self.id, self.realm.string_id or "root")

    @override
    def set_password(self, password: str | None) -> None:
        if password is None:
            self.set_unusable_password()
            return

        from zproject.backends import check_password_strength

        if not check_password_strength(password):
            raise PasswordTooWeakError

        super().set_password(password)


class PasswordTooWeakError(Exception):
    pass


def remote_user_to_email(remote_user: str) -> str:
    if settings.SSO_APPEND_DOMAIN is not None:
        return Address(username=remote_user, domain=settings.SSO_APPEND_DOMAIN).addr_spec
    return remote_user


# Make sure we flush the UserProfile object from our remote cache
# whenever we save it.
post_save.connect(flush_user_profile, sender=UserProfile)


def base_bulk_get_user_queryset() -> QuerySet[UserProfile]:
    # Base select_related options for UserProfile for general user.
    return UserProfile.objects.select_related("realm")


def base_get_user_queryset() -> QuerySet[UserProfile]:
    """Base select_related options for fetching a single user object.
    In contrast with base_bulk_get_user_queryset, additionally fetches
    fields that are relevant for this user sending a message.
    """
    return UserProfile.objects.select_related("realm", "bot_owner")


@cache_with_key(user_profile_by_id_cache_key, timeout=3600 * 24 * 7)
def get_user_profile_by_id(user_profile_id: int) -> UserProfile:
    return base_get_user_queryset().get(id=user_profile_id)


def base_get_user_narrow_queryset() -> QuerySet[UserProfile]:
    return UserProfile.objects.select_related("realm").only(
        "id",
        "bot_type",
        "is_active",
        "presence_enabled",
        "rate_limits",
        "role",
        "recipient_id",
        "realm__string_id",
        "realm__deactivated",
    )


@cache_with_key(user_profile_narrow_by_id_cache_key, timeout=3600 * 24 * 7)
def get_user_profile_narrow_by_id(user_profile_id: int) -> UserProfile:
    return base_get_user_narrow_queryset().get(id=user_profile_id)


def get_user_profile_by_email(email: str) -> UserProfile:
    """This function is intended to be used for
    manual manage.py shell work; robust code must use get_user or
    get_user_by_delivery_email instead, because Zulip supports
    multiple users with a given (delivery) email address existing on a
    single server (in different realms).
    """
    return UserProfile.objects.select_related("realm").get(delivery_email__iexact=email.strip())


@cache_with_key(user_profile_by_api_key_cache_key, timeout=3600 * 24 * 7)
def maybe_get_user_profile_by_api_key(api_key: str) -> UserProfile | None:
    try:
        return base_get_user_queryset().get(api_key=api_key)
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


def get_user_by_delivery_email(email: str, realm: "Realm") -> UserProfile:
    """Fetches a user given their delivery email.  For use in
    authentication/registration contexts.  Do not use for user-facing
    views (e.g. Zulip API endpoints) as doing so would violate the
    EMAIL_ADDRESS_VISIBILITY_ADMINS security model.  Use get_user in
    those code paths.
    """
    return base_get_user_queryset().get(delivery_email__iexact=email.strip(), realm=realm)


def get_users_by_delivery_email(emails: set[str], realm: "Realm") -> QuerySet[UserProfile]:
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


@cache_with_key(user_profile_by_email_realm_cache_key, timeout=3600 * 24 * 7)
def get_user(email: str, realm: "Realm") -> UserProfile:
    """Fetches the user by its visible-to-other users username (in the
    `email` field).  For use in API contexts; do not use in
    authentication/registration contexts as doing so will break
    authentication in organizations using
    EMAIL_ADDRESS_VISIBILITY_ADMINS.  In those code paths, use
    get_user_by_delivery_email.
    """
    return base_get_user_queryset().get(email__iexact=email.strip(), realm=realm)


def get_active_user(email: str, realm: "Realm") -> UserProfile:
    """Variant of get_user_by_email that excludes deactivated users.
    See get_user docstring for important usage notes."""
    user_profile = get_user(email, realm)
    if not user_profile.is_active:
        raise UserProfile.DoesNotExist
    return user_profile


def get_user_profile_by_id_in_realm(uid: int, realm: "Realm") -> UserProfile:
    return base_bulk_get_user_queryset().get(id=uid, realm=realm)


def get_active_user_profile_by_id_in_realm(uid: int, realm: "Realm") -> UserProfile:
    user_profile = get_user_profile_by_id_in_realm(uid, realm)
    if not user_profile.is_active:
        raise UserProfile.DoesNotExist
    return user_profile


def get_user_including_cross_realm(email: str, realm: "Realm") -> UserProfile:
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
    realm: Optional["Realm"],
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
def get_realm_user_dicts(realm_id: int) -> list[RawUserDict]:
    return list(
        UserProfile.objects.filter(
            realm_id=realm_id,
        ).values(*realm_user_dict_fields)
    )


def get_partial_realm_user_dicts(
    realm_id: int, user_profile: UserProfile | None
) -> list[RawUserDict]:
    """Returns a subset of the users in the realm, guaranteed to
    include the current user as well as all bots in the realm.
    """

    # Currently, we send the minimum set of users permitted by the API.
    user_selection_clause = Q(is_bot=True)
    if user_profile is not None:
        user_selection_clause |= Q(id=user_profile.id)

    return list(
        UserProfile.objects.filter(realm_id=realm_id)
        .filter(
            user_selection_clause,
        )
        .values(*realm_user_dict_fields)
    )


def get_realm_user_dicts_from_ids(realm_id: int, user_ids: list[int]) -> list[RawUserDict]:
    return list(
        UserProfile.objects.filter(
            realm_id=realm_id,
            id__in=user_ids,
        ).values(*realm_user_dict_fields)
    )


@cache_with_key(active_user_ids_cache_key, timeout=3600 * 24 * 7)
def active_user_ids(realm_id: int) -> list[int]:
    query = UserProfile.objects.filter(
        realm_id=realm_id,
        is_active=True,
    ).values_list("id", flat=True)
    return list(query)


@cache_with_key(active_non_guest_user_ids_cache_key, timeout=3600 * 24 * 7)
def active_non_guest_user_ids(realm_id: int) -> list[int]:
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


def bot_owner_user_ids(user_profile: UserProfile) -> set[int]:
    is_private_bot = (
        user_profile.default_sending_stream and user_profile.default_sending_stream.invite_only
    ) or (
        user_profile.default_events_register_stream
        and user_profile.default_events_register_stream.invite_only
    )
    if is_private_bot:
        if user_profile.bot_owner_id is not None:
            return {user_profile.bot_owner_id}
        return set()
    else:
        users = {user.id for user in user_profile.realm.get_human_admin_users()}
        if user_profile.bot_owner_id is not None:
            users.add(user_profile.bot_owner_id)
        return users


def get_source_profile(email: str, realm_id: int) -> UserProfile | None:
    from zerver.models import Realm
    from zerver.models.realms import get_realm_by_id

    try:
        return get_user_by_delivery_email(email, get_realm_by_id(realm_id))
    except (Realm.DoesNotExist, UserProfile.DoesNotExist):
        return None


@cache_with_key(lambda realm: bot_dicts_in_realm_cache_key(realm.id), timeout=3600 * 24 * 7)
def get_bot_dicts_in_realm(realm: "Realm") -> list[dict[str, Any]]:
    return list(UserProfile.objects.filter(realm=realm, is_bot=True).values(*bot_dict_fields))


def is_cross_realm_bot_email(email: str) -> bool:
    return email.lower() in settings.CROSS_REALM_BOT_EMAILS


class ExternalAuthID(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=CASCADE)
    realm = models.ForeignKey("zerver.Realm", on_delete=CASCADE)
    date_created = models.DateTimeField(default=timezone_now)
    # TODO: We might want to add is_active and date_deactivated fields in the future.

    external_auth_method_name = models.TextField(db_index=False)
    external_auth_id = models.TextField(db_index=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "realm",
                    "external_auth_method_name",
                    "external_auth_id",
                ],
                name="zerver_externalauthid_uniq",
            ),
        ]
