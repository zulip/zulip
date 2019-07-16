from typing import Any, DefaultDict, Dict, List, Set, Tuple, TypeVar, \
    Union, Optional, Sequence, AbstractSet, Callable, Iterable

from django.db import models
from django.db.models.query import QuerySet
from django.db.models import Manager, Q, Sum, CASCADE
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, UserManager, \
    PermissionsMixin
import django.contrib.auth
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, MinLengthValidator, \
    RegexValidator, validate_email
from zerver.lib.cache import cache_with_key, flush_user_profile, flush_realm, \
    user_profile_by_api_key_cache_key, active_non_guest_user_ids_cache_key, \
    user_profile_by_id_cache_key, user_profile_by_email_cache_key, \
    user_profile_cache_key, generic_bulk_cached_fetch, cache_set, flush_stream, \
    cache_delete, active_user_ids_cache_key, \
    get_stream_cache_key, realm_user_dicts_cache_key, \
    bot_dicts_in_realm_cache_key, realm_user_dict_fields, \
    bot_dict_fields, flush_message, flush_submessage, bot_profile_cache_key, \
    flush_used_upload_space_cache, get_realm_used_upload_space_cache_key, \
    realm_alert_words_cache_key, realm_alert_words_automaton_cache_key
from zerver.lib.utils import make_safe_digest, generate_random_token
from django.db import transaction
from django.utils.timezone import now as timezone_now
from zerver.lib.timestamp import datetime_to_timestamp
from django.db.models.signals import post_save, post_delete
from django.utils.translation import ugettext_lazy as _
from zerver.lib import cache
from zerver.lib.validator import check_int, \
    check_short_string, check_long_string, validate_choice_field, check_date, \
    check_url, check_list
from zerver.lib.types import Validator, ExtendedValidator, \
    ProfileDataElement, ProfileData, RealmUserValidator, \
    ExtendedFieldElement, UserFieldElement, FieldElement, \
    DisplayRecipientT
from zerver.lib.exceptions import JsonableError

from bitfield import BitField
from bitfield.types import BitHandler
from collections import defaultdict
from datetime import timedelta
import re
import sre_constants
import time
import datetime

MAX_TOPIC_NAME_LENGTH = 60
MAX_MESSAGE_LENGTH = 10000
MAX_LANGUAGE_ID_LENGTH: int = 50

STREAM_NAMES = TypeVar('STREAM_NAMES', Sequence[str], AbstractSet[str])

def query_for_ids(query: QuerySet, user_ids: List[int], field: str) -> QuerySet:
    '''
    This function optimizes searches of the form
    `user_profile_id in (1, 2, 3, 4)` by quickly
    building the where clauses.  Profiling shows significant
    speedups over the normal Django-based approach.

    Use this very carefully!  Also, the caller should
    guard against empty lists of user_ids.
    '''
    assert(user_ids)
    value_list = ', '.join(str(int(user_id)) for user_id in user_ids)
    clause = '%s in (%s)' % (field, value_list)
    query = query.extra(
        where=[clause]
    )
    return query

# Doing 1000 remote cache requests to get_display_recipient is quite slow,
# so add a local cache as well as the remote cache cache.
#
# This local cache has a lifetime of just a single request; it is
# cleared inside `flush_per_request_caches` in our middleware.  It
# could be replaced with smarter bulk-fetching logic that deduplicates
# queries for the same recipient; this is just a convenient way to
# write that code.
per_request_display_recipient_cache: Dict[int, DisplayRecipientT] = {}
def get_display_recipient_by_id(recipient_id: int, recipient_type: int,
                                recipient_type_id: Optional[int]) -> DisplayRecipientT:
    """
    returns: an object describing the recipient (using a cache).
    If the type is a stream, the type_id must be an int; a string is returned.
    Otherwise, type_id may be None; an array of recipient dicts is returned.
    """
    # Have to import here, to avoid circular dependency.
    from zerver.lib.display_recipient import get_display_recipient_remote_cache

    if recipient_id not in per_request_display_recipient_cache:
        result = get_display_recipient_remote_cache(recipient_id, recipient_type, recipient_type_id)
        per_request_display_recipient_cache[recipient_id] = result
    return per_request_display_recipient_cache[recipient_id]

def get_display_recipient(recipient: 'Recipient') -> DisplayRecipientT:
    return get_display_recipient_by_id(
        recipient.id,
        recipient.type,
        recipient.type_id
    )

def get_realm_emoji_cache_key(realm: 'Realm') -> str:
    return 'realm_emoji:%s' % (realm.id,)

def get_active_realm_emoji_cache_key(realm: 'Realm') -> str:
    return 'active_realm_emoji:%s' % (realm.id,)

# This simple call-once caching saves ~500us in auth_enabled_helper,
# which is a significant optimization for common_context.  Note that
# these values cannot change in a running production system, but do
# regularly change within unit tests; we address the latter by calling
# clear_supported_auth_backends_cache in our standard tearDown code.
supported_backends: Optional[Set[type]] = None
def supported_auth_backends() -> Set[type]:
    global supported_backends
    # Caching temporarily disabled for debugging
    supported_backends = django.contrib.auth.get_backends()
    assert supported_backends is not None
    return supported_backends

def clear_supported_auth_backends_cache() -> None:
    global supported_backends
    supported_backends = None

class Realm(models.Model):
    MAX_REALM_NAME_LENGTH = 40
    MAX_REALM_SUBDOMAIN_LENGTH = 40
    MAX_GOOGLE_HANGOUTS_DOMAIN_LENGTH = 255  # This is just the maximum domain length by RFC
    INVITES_STANDARD_REALM_DAILY_MAX = 3000
    MESSAGE_VISIBILITY_LIMITED = 10000
    AUTHENTICATION_FLAGS = ['Google', 'Email', 'GitHub', 'LDAP', 'Dev',
                            'RemoteUser', 'AzureAD', 'SAML', 'GitLab']
    SUBDOMAIN_FOR_ROOT_DOMAIN = ''

    # User-visible display name and description used on e.g. the organization homepage
    name: Optional[str] = models.CharField(max_length=MAX_REALM_NAME_LENGTH, null=True)
    description: str = models.TextField(default="")

    # A short, identifier-like name for the organization.  Used in subdomains;
    # e.g. on a server at example.com, an org with string_id `foo` is reached
    # at `foo.example.com`.
    string_id: str = models.CharField(max_length=MAX_REALM_SUBDOMAIN_LENGTH, unique=True)

    date_created: datetime.datetime = models.DateTimeField(default=timezone_now)
    deactivated: bool = models.BooleanField(default=False)

    # See RealmDomain for the domains that apply for a given organization.
    emails_restricted_to_domains: bool = models.BooleanField(default=False)

    invite_required: bool = models.BooleanField(default=True)
    invite_by_admins_only: bool = models.BooleanField(default=False)
    _max_invites: Optional[int] = models.IntegerField(null=True, db_column='max_invites')
    disallow_disposable_email_addresses: bool = models.BooleanField(default=True)
    authentication_methods: BitHandler = BitField(
        flags=AUTHENTICATION_FLAGS, default=2**31 - 1
    )

    # Whether the organization has enabled inline image and URL previews.
    inline_image_preview: bool = models.BooleanField(default=True)
    inline_url_embed_preview: bool = models.BooleanField(default=False)

    # Whether digest emails are enabled for the organization.
    digest_emails_enabled: bool = models.BooleanField(default=False)
    # Day of the week on which the digest is sent (default: Tuesday).
    digest_weekday: int = models.SmallIntegerField(default=1)

    send_welcome_emails: bool = models.BooleanField(default=True)
    message_content_allowed_in_email_notifications: bool = models.BooleanField(default=True)

    mandatory_topics: bool = models.BooleanField(default=False)
    add_emoji_by_admins_only: bool = models.BooleanField(default=False)
    name_changes_disabled: bool = models.BooleanField(default=False)
    email_changes_disabled: bool = models.BooleanField(default=False)
    avatar_changes_disabled: bool = models.BooleanField(default=False)

    POLICY_MEMBERS_ONLY = 1
    POLICY_ADMINS_ONLY = 2
    POLICY_FULL_MEMBERS_ONLY = 3

    COMMON_POLICY_TYPES = [
        POLICY_MEMBERS_ONLY,
        POLICY_ADMINS_ONLY,
        POLICY_FULL_MEMBERS_ONLY,
    ]

    # Who in the organization is allowed to create streams.
    create_stream_policy: int = models.PositiveSmallIntegerField(
        default=POLICY_MEMBERS_ONLY)

    # Who in the organization is allowed to invite other users to streams.
    invite_to_stream_policy: int = models.PositiveSmallIntegerField(
        default=POLICY_MEMBERS_ONLY)

    USER_GROUP_EDIT_POLICY_MEMBERS = 1
    USER_GROUP_EDIT_POLICY_ADMINS = 2
    user_group_edit_policy: int = models.PositiveSmallIntegerField(
        default=USER_GROUP_EDIT_POLICY_MEMBERS)
    USER_GROUP_EDIT_POLICY_TYPES = [
        USER_GROUP_EDIT_POLICY_MEMBERS,
        USER_GROUP_EDIT_POLICY_ADMINS,
    ]

    PRIVATE_MESSAGE_POLICY_UNLIMITED = 1
    PRIVATE_MESSAGE_POLICY_DISABLED = 2
    private_message_policy: int = models.PositiveSmallIntegerField(
        default=PRIVATE_MESSAGE_POLICY_UNLIMITED)
    PRIVATE_MESSAGE_POLICY_TYPES = [
        PRIVATE_MESSAGE_POLICY_UNLIMITED,
        PRIVATE_MESSAGE_POLICY_DISABLED,
    ]

    # Who in the organization has access to users' actual email
    # addresses.  Controls whether the UserProfile.email field is the
    # same as UserProfile.delivery_email, or is instead garbage.
    EMAIL_ADDRESS_VISIBILITY_EVERYONE = 1
    EMAIL_ADDRESS_VISIBILITY_MEMBERS = 2
    EMAIL_ADDRESS_VISIBILITY_ADMINS = 3
    EMAIL_ADDRESS_VISIBILITY_NOBODY = 4
    email_address_visibility: int = models.PositiveSmallIntegerField(
        default=EMAIL_ADDRESS_VISIBILITY_EVERYONE
    )
    EMAIL_ADDRESS_VISIBILITY_TYPES = [
        EMAIL_ADDRESS_VISIBILITY_EVERYONE,
        # The MEMBERS level is not yet implemented on the backend.
        ## EMAIL_ADDRESS_VISIBILITY_MEMBERS,
        EMAIL_ADDRESS_VISIBILITY_ADMINS,
        EMAIL_ADDRESS_VISIBILITY_NOBODY,
    ]

    # Threshold in days for new users to create streams, and potentially take
    # some other actions.
    waiting_period_threshold: int = models.PositiveIntegerField(default=0)

    allow_message_deleting: bool = models.BooleanField(default=False)
    DEFAULT_MESSAGE_CONTENT_DELETE_LIMIT_SECONDS = 600  # if changed, also change in admin.js, setting_org.js
    message_content_delete_limit_seconds: int = models.IntegerField(
        default=DEFAULT_MESSAGE_CONTENT_DELETE_LIMIT_SECONDS
    )

    allow_message_editing: bool = models.BooleanField(default=True)
    DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS = 600  # if changed, also change in admin.js, setting_org.js
    message_content_edit_limit_seconds: int = models.IntegerField(
        default=DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS
    )

    # Whether users have access to message edit history
    allow_edit_history: bool = models.BooleanField(default=True)

    DEFAULT_COMMUNITY_TOPIC_EDITING_LIMIT_SECONDS = 86400
    allow_community_topic_editing: bool = models.BooleanField(default=True)

    # Defaults for new users
    default_twenty_four_hour_time: bool = models.BooleanField(default=False)
    default_language: str = models.CharField(default='en', max_length=MAX_LANGUAGE_ID_LENGTH)

    DEFAULT_NOTIFICATION_STREAM_NAME = 'general'
    INITIAL_PRIVATE_STREAM_NAME = 'core team'
    STREAM_EVENTS_NOTIFICATION_TOPIC = _('stream events')
    notifications_stream: Optional["Stream"] = models.ForeignKey(
        "Stream", related_name="+", null=True, blank=True, on_delete=CASCADE
    )
    signup_notifications_stream: Optional["Stream"] = models.ForeignKey(
        "Stream", related_name="+", null=True, blank=True, on_delete=CASCADE
    )

    RETAIN_MESSAGE_FOREVER = -1
    # For old messages being automatically deleted
    message_retention_days: Optional[int] = models.IntegerField(null=True)

    # When non-null, all but the latest this many messages in the organization
    # are inaccessible to users (but not deleted).
    message_visibility_limit: Optional[int] = models.IntegerField(null=True)

    # Messages older than this message ID in the organization are inaccessible.
    first_visible_message_id: int = models.IntegerField(default=0)

    # Valid org_types are {CORPORATE, COMMUNITY}
    CORPORATE = 1
    COMMUNITY = 2
    org_type: int = models.PositiveSmallIntegerField(default=CORPORATE)

    UPGRADE_TEXT_STANDARD = _("Available on Zulip Standard. Upgrade to access.")
    # plan_type controls various features around resource/feature
    # limitations for a Zulip organization on multi-tenant servers
    # like zulipchat.com.
    SELF_HOSTED = 1
    LIMITED = 2
    STANDARD = 3
    STANDARD_FREE = 4
    plan_type: int = models.PositiveSmallIntegerField(default=SELF_HOSTED)

    # This value is also being used in static/js/settings_bots.bot_creation_policy_values.
    # On updating it here, update it there as well.
    BOT_CREATION_EVERYONE = 1
    BOT_CREATION_LIMIT_GENERIC_BOTS = 2
    BOT_CREATION_ADMINS_ONLY = 3
    bot_creation_policy: int = models.PositiveSmallIntegerField(default=BOT_CREATION_EVERYONE)
    BOT_CREATION_POLICY_TYPES = [
        BOT_CREATION_EVERYONE,
        BOT_CREATION_LIMIT_GENERIC_BOTS,
        BOT_CREATION_ADMINS_ONLY,
    ]

    # See upload_quota_bytes; don't interpret upload_quota_gb directly.
    UPLOAD_QUOTA_LIMITED = 5
    UPLOAD_QUOTA_STANDARD = 50
    upload_quota_gb: Optional[int] = models.IntegerField(null=True)

    VIDEO_CHAT_PROVIDERS = {
        'disabled': {
            'name': "None",
            'id': 0
        },
        'jitsi_meet': {
            'name': "Jitsi Meet",
            'id': 1
        },
        'google_hangouts': {
            'name': "Google Hangouts",
            'id': 2
        },
        'zoom': {
            'name': "Zoom",
            'id': 3
        }
    }
    video_chat_provider = models.PositiveSmallIntegerField(default=VIDEO_CHAT_PROVIDERS['jitsi_meet']['id'])
    google_hangouts_domain = models.TextField(default="")
    zoom_user_id = models.TextField(default="")
    zoom_api_key = models.TextField(default="")
    zoom_api_secret = models.TextField(default="")

    default_code_block_language: Optional[str] = models.TextField(null=True, default=None)

    # Define the types of the various automatically managed properties
    property_types: Dict[str, Union[type, Tuple[type, ...]]] = dict(
        add_emoji_by_admins_only=bool,
        allow_edit_history=bool,
        allow_message_deleting=bool,
        bot_creation_policy=int,
        create_stream_policy=int,
        invite_to_stream_policy=int,
        default_language=str,
        default_twenty_four_hour_time = bool,
        description=str,
        digest_emails_enabled=bool,
        disallow_disposable_email_addresses=bool,
        email_address_visibility=int,
        email_changes_disabled=bool,
        google_hangouts_domain=str,
        zoom_user_id=str,
        zoom_api_key=str,
        zoom_api_secret=str,
        invite_required=bool,
        invite_by_admins_only=bool,
        inline_image_preview=bool,
        inline_url_embed_preview=bool,
        mandatory_topics=bool,
        message_retention_days=(int, type(None)),
        name=str,
        name_changes_disabled=bool,
        avatar_changes_disabled=bool,
        emails_restricted_to_domains=bool,
        send_welcome_emails=bool,
        message_content_allowed_in_email_notifications=bool,
        video_chat_provider=int,
        waiting_period_threshold=int,
        digest_weekday=int,
        private_message_policy=int,
        user_group_edit_policy=int,
        default_code_block_language=(str, type(None)),
    )

    DIGEST_WEEKDAY_VALUES = [0, 1, 2, 3, 4, 5, 6]

    # Icon is the square mobile icon.
    ICON_FROM_GRAVATAR = 'G'
    ICON_UPLOADED = 'U'
    ICON_SOURCES = (
        (ICON_FROM_GRAVATAR, 'Hosted by Gravatar'),
        (ICON_UPLOADED, 'Uploaded by administrator'),
    )
    icon_source: str = models.CharField(
        default=ICON_FROM_GRAVATAR, choices=ICON_SOURCES, max_length=1
    )
    icon_version: int = models.PositiveSmallIntegerField(default=1)

    # Logo is the horizontal logo we show in top-left of webapp navbar UI.
    LOGO_DEFAULT = 'D'
    LOGO_UPLOADED = 'U'
    LOGO_SOURCES = (
        (LOGO_DEFAULT, 'Default to Zulip'),
        (LOGO_UPLOADED, 'Uploaded by administrator'),
    )
    logo_source: str = models.CharField(
        default=LOGO_DEFAULT, choices=LOGO_SOURCES, max_length=1
    )
    logo_version: int = models.PositiveSmallIntegerField(default=1)

    night_logo_source: str = models.CharField(
        default=LOGO_DEFAULT, choices=LOGO_SOURCES, max_length=1
    )
    night_logo_version: int = models.PositiveSmallIntegerField(default=1)

    def authentication_methods_dict(self) -> Dict[str, bool]:
        """Returns the a mapping from authentication flags to their status,
        showing only those authentication flags that are supported on
        the current server (i.e. if EmailAuthBackend is not configured
        on the server, this will not return an entry for "Email")."""
        # This mapping needs to be imported from here due to the cyclic
        # dependency.
        from zproject.backends import AUTH_BACKEND_NAME_MAP

        ret: Dict[str, bool] = {}
        supported_backends = [backend.__class__ for backend in supported_auth_backends()]
        for k, v in self.authentication_methods.iteritems():
            backend = AUTH_BACKEND_NAME_MAP[k]
            if backend in supported_backends:
                ret[k] = v
        return ret

    def __str__(self) -> str:
        return "<Realm: %s %s>" % (self.string_id, self.id)

    @cache_with_key(get_realm_emoji_cache_key, timeout=3600*24*7)
    def get_emoji(self) -> Dict[str, Dict[str, Iterable[str]]]:
        return get_realm_emoji_uncached(self)

    @cache_with_key(get_active_realm_emoji_cache_key, timeout=3600*24*7)
    def get_active_emoji(self) -> Dict[str, Dict[str, Iterable[str]]]:
        return get_active_realm_emoji_uncached(self)

    def get_admin_users_and_bots(self) -> Sequence['UserProfile']:
        """Use this in contexts where we want administrative users as well as
        bots with administrator privileges, like send_event calls for
        notifications to all administrator users.
        """
        # TODO: Change return type to QuerySet[UserProfile]
        return UserProfile.objects.filter(realm=self, is_active=True,
                                          role__in=[UserProfile.ROLE_REALM_ADMINISTRATOR,
                                                    UserProfile.ROLE_REALM_OWNER])

    def get_human_admin_users(self) -> QuerySet:
        """Use this in contexts where we want only human users with
        administrative privileges, like sending an email to all of a
        realm's administrators (bots don't have real email addresses).
        """
        # TODO: Change return type to QuerySet[UserProfile]
        return UserProfile.objects.filter(realm=self, is_bot=False, is_active=True,
                                          role__in=[UserProfile.ROLE_REALM_ADMINISTRATOR,
                                                    UserProfile.ROLE_REALM_OWNER])

    def get_active_users(self) -> Sequence['UserProfile']:
        # TODO: Change return type to QuerySet[UserProfile]
        return UserProfile.objects.filter(realm=self, is_active=True).select_related()

    def get_bot_domain(self) -> str:
        return get_fake_email_domain()

    def get_notifications_stream(self) -> Optional['Stream']:
        if self.notifications_stream is not None and not self.notifications_stream.deactivated:
            return self.notifications_stream
        return None

    def get_signup_notifications_stream(self) -> Optional['Stream']:
        if self.signup_notifications_stream is not None and not self.signup_notifications_stream.deactivated:
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

    @cache_with_key(get_realm_used_upload_space_cache_key, timeout=3600*24*7)
    def currently_used_upload_space_bytes(self) -> int:
        used_space = Attachment.objects.filter(realm=self).aggregate(Sum('size'))['size__sum']
        if used_space is None:
            return 0
        return used_space

    def ensure_not_on_limited_plan(self) -> None:
        if self.plan_type == Realm.LIMITED:
            raise JsonableError(self.UPGRADE_TEXT_STANDARD)

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
        return self.host_for_subdomain(self.subdomain)

    @staticmethod
    def host_for_subdomain(subdomain: str) -> str:
        if subdomain == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
            return settings.EXTERNAL_HOST
        default_host = "%s.%s" % (subdomain, settings.EXTERNAL_HOST)
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

    class Meta:
        permissions = (
            ('administer', "Administer a realm"),
            ('api_super_user', "Can send messages as other users for mirroring"),
        )

post_save.connect(flush_realm, sender=Realm)

def get_realm(string_id: str) -> Realm:
    return Realm.objects.get(string_id=string_id)

def name_changes_disabled(realm: Optional[Realm]) -> bool:
    if realm is None:
        return settings.NAME_CHANGES_DISABLED
    return settings.NAME_CHANGES_DISABLED or realm.name_changes_disabled

def avatar_changes_disabled(realm: Realm) -> bool:
    return settings.AVATAR_CHANGES_DISABLED or realm.avatar_changes_disabled

class RealmDomain(models.Model):
    """For an organization with emails_restricted_to_domains enabled, the list of
    allowed domains"""
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    # should always be stored lowercase
    domain: str = models.CharField(max_length=80, db_index=True)
    allow_subdomains = models.BooleanField(default=False)

    class Meta:
        unique_together = ("realm", "domain")

# These functions should only be used on email addresses that have
# been validated via django.core.validators.validate_email
#
# Note that we need to use some care, since can you have multiple @-signs; e.g.
# "tabbott@test"@zulip.com
# is valid email address
def email_to_username(email: str) -> str:
    return "@".join(email.split("@")[:-1]).lower()

# Returns the raw domain portion of the desired email address
def email_to_domain(email: str) -> str:
    return email.split("@")[-1].lower()

class DomainNotAllowedForRealmError(Exception):
    pass

class DisposableEmailError(Exception):
    pass

class EmailContainsPlusError(Exception):
    pass

def get_realm_domains(realm: Realm) -> List[Dict[str, str]]:
    return list(realm.realmdomain_set.values('domain', 'allow_subdomains'))

class RealmEmoji(models.Model):
    author: Optional["UserProfile"] = models.ForeignKey(
        "UserProfile", blank=True, null=True, on_delete=CASCADE
    )
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    name: str = models.TextField(validators=[
        MinLengthValidator(1),
        # The second part of the regex (negative lookbehind) disallows names
        # ending with one of the punctuation characters.
        RegexValidator(regex=r'^[0-9a-z.\-_]+(?<![.\-_])$',
                       message=_("Invalid characters in emoji name"))])

    # The basename of the custom emoji's filename; see PATH_ID_TEMPLATE for the full path.
    file_name: Optional[str] = models.TextField(db_index=True, null=True, blank=True)

    deactivated: bool = models.BooleanField(default=False)

    PATH_ID_TEMPLATE = "{realm_id}/emoji/images/{emoji_file_name}"

    def __str__(self) -> str:
        return "<RealmEmoji(%s): %s %s %s %s>" % (self.realm.string_id,
                                                  self.id,
                                                  self.name,
                                                  self.deactivated,
                                                  self.file_name)

def get_realm_emoji_dicts(realm: Realm,
                          only_active_emojis: bool=False) -> Dict[str, Dict[str, Any]]:
    query = RealmEmoji.objects.filter(realm=realm).select_related('author')
    if only_active_emojis:
        query = query.filter(deactivated=False)
    d = {}
    from zerver.lib.emoji import get_emoji_url

    for realm_emoji in query.all():
        author = None
        if realm_emoji.author:
            author = {
                'id': realm_emoji.author.id,
                'email': realm_emoji.author.email,
                'full_name': realm_emoji.author.full_name}
        emoji_url = get_emoji_url(realm_emoji.file_name, realm_emoji.realm_id)
        d[str(realm_emoji.id)] = dict(id=str(realm_emoji.id),
                                      name=realm_emoji.name,
                                      source_url=emoji_url,
                                      deactivated=realm_emoji.deactivated,
                                      author=author)
    return d

def get_realm_emoji_uncached(realm: Realm) -> Dict[str, Dict[str, Any]]:
    return get_realm_emoji_dicts(realm)

def get_active_realm_emoji_uncached(realm: Realm) -> Dict[str, Dict[str, Any]]:
    realm_emojis = get_realm_emoji_dicts(realm, only_active_emojis=True)
    d = {}
    for emoji_id, emoji_dict in realm_emojis.items():
        d[emoji_dict['name']] = emoji_dict
    return d

def flush_realm_emoji(sender: Any, **kwargs: Any) -> None:
    realm = kwargs['instance'].realm
    cache_set(get_realm_emoji_cache_key(realm),
              get_realm_emoji_uncached(realm),
              timeout=3600*24*7)
    cache_set(get_active_realm_emoji_cache_key(realm),
              get_active_realm_emoji_uncached(realm),
              timeout=3600*24*7)

post_save.connect(flush_realm_emoji, sender=RealmEmoji)
post_delete.connect(flush_realm_emoji, sender=RealmEmoji)

def filter_pattern_validator(value: str) -> None:
    regex = re.compile(r'^(?:(?:[\w\-#_= /:]*|[+]|[!])(\(\?P<\w+>.+\)))+$')
    error_msg = _('Invalid filter pattern.  Valid characters are %s.') % (
        '[ a-zA-Z_#=/:+!-]',)

    if not regex.match(str(value)):
        raise ValidationError(error_msg)

    try:
        re.compile(value)
    except sre_constants.error:
        # Regex is invalid
        raise ValidationError(error_msg)

def filter_format_validator(value: str) -> None:
    regex = re.compile(r'^([\.\/:a-zA-Z0-9#_?=&;-]+%\(([a-zA-Z0-9_-]+)\)s)+[/a-zA-Z0-9#_?=&;-]*$')

    if not regex.match(value):
        raise ValidationError(_('Invalid URL format string.'))

class RealmFilter(models.Model):
    """Realm-specific regular expressions to automatically linkify certain
    strings inside the markdown processor.  See "Custom filters" in the settings UI.
    """
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    pattern: str = models.TextField(validators=[filter_pattern_validator])
    url_format_string: str = models.TextField(validators=[URLValidator(), filter_format_validator])

    class Meta:
        unique_together = ("realm", "pattern")

    def __str__(self) -> str:
        return "<RealmFilter(%s): %s %s>" % (self.realm.string_id, self.pattern, self.url_format_string)

def get_realm_filters_cache_key(realm_id: int) -> str:
    return '%s:all_realm_filters:%s' % (cache.KEY_PREFIX, realm_id,)

# We have a per-process cache to avoid doing 1000 remote cache queries during page load
per_request_realm_filters_cache: Dict[int, List[Tuple[str, str, int]]] = {}

def realm_in_local_realm_filters_cache(realm_id: int) -> bool:
    return realm_id in per_request_realm_filters_cache

def realm_filters_for_realm(realm_id: int) -> List[Tuple[str, str, int]]:
    if not realm_in_local_realm_filters_cache(realm_id):
        per_request_realm_filters_cache[realm_id] = realm_filters_for_realm_remote_cache(realm_id)
    return per_request_realm_filters_cache[realm_id]

@cache_with_key(get_realm_filters_cache_key, timeout=3600*24*7)
def realm_filters_for_realm_remote_cache(realm_id: int) -> List[Tuple[str, str, int]]:
    filters = []
    for realm_filter in RealmFilter.objects.filter(realm_id=realm_id):
        filters.append((realm_filter.pattern, realm_filter.url_format_string, realm_filter.id))

    return filters

def all_realm_filters() -> Dict[int, List[Tuple[str, str, int]]]:
    filters: DefaultDict[int, List[Tuple[str, str, int]]] = defaultdict(list)
    for realm_filter in RealmFilter.objects.all():
        filters[realm_filter.realm_id].append((realm_filter.pattern,
                                               realm_filter.url_format_string,
                                               realm_filter.id))

    return filters

def flush_realm_filter(sender: Any, **kwargs: Any) -> None:
    realm_id = kwargs['instance'].realm_id
    cache_delete(get_realm_filters_cache_key(realm_id))
    try:
        per_request_realm_filters_cache.pop(realm_id)
    except KeyError:
        pass

post_save.connect(flush_realm_filter, sender=RealmFilter)
post_delete.connect(flush_realm_filter, sender=RealmFilter)

def flush_per_request_caches() -> None:
    global per_request_display_recipient_cache
    per_request_display_recipient_cache = {}
    global per_request_realm_filters_cache
    per_request_realm_filters_cache = {}

# The Recipient table is used to map Messages to the set of users who
# received the message.  It is implemented as a set of triples (id,
# type_id, type). We have 3 types of recipients: Huddles (for group
# private messages), UserProfiles (for 1:1 private messages), and
# Streams. The recipient table maps a globally unique recipient id
# (used by the Message table) to the type-specific unique id (the
# stream id, user_profile id, or huddle id).
class Recipient(models.Model):
    type_id: int = models.IntegerField(db_index=True)
    type: int = models.PositiveSmallIntegerField(db_index=True)
    # Valid types are {personal, stream, huddle}
    PERSONAL = 1
    STREAM = 2
    HUDDLE = 3

    class Meta:
        unique_together = ("type", "type_id")

    # N.B. If we used Django's choice=... we would get this for free (kinda)
    _type_names = {
        PERSONAL: 'personal',
        STREAM: 'stream',
        HUDDLE: 'huddle'}

    def type_name(self) -> str:
        # Raises KeyError if invalid
        return self._type_names[self.type]

    def __str__(self) -> str:
        display_recipient = get_display_recipient(self)
        return "<Recipient: %s (%d, %s)>" % (display_recipient, self.type_id, self.type)

class UserProfile(AbstractBaseUser, PermissionsMixin):
    USERNAME_FIELD = 'email'
    MAX_NAME_LENGTH = 100
    MIN_NAME_LENGTH = 2
    API_KEY_LENGTH = 32
    NAME_INVALID_CHARS = ['*', '`', "\\", '>', '"', '@']

    DEFAULT_BOT = 1
    """
    Incoming webhook bots are limited to only sending messages via webhooks.
    Thus, it is less of a security risk to expose their API keys to third-party services,
    since they can't be used to read messages.
    """
    INCOMING_WEBHOOK_BOT = 2
    # This value is also being used in static/js/settings_bots.js.
    # On updating it here, update it there as well.
    OUTGOING_WEBHOOK_BOT = 3
    """
    Embedded bots run within the Zulip server itself; events are added to the
    embedded_bots queue and then handled by a QueueProcessingWorker.
    """
    EMBEDDED_BOT = 4

    BOT_TYPES = {
        DEFAULT_BOT: 'Generic bot',
        INCOMING_WEBHOOK_BOT: 'Incoming webhook',
        OUTGOING_WEBHOOK_BOT: 'Outgoing webhook',
        EMBEDDED_BOT: 'Embedded bot',
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
    # Both fields are unique within a realm (in a case-insensitive fashion).
    delivery_email: str = models.EmailField(blank=False, db_index=True)
    email: str = models.EmailField(blank=False, db_index=True)

    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    # Foreign key to the Recipient object for PERSONAL type messages to this user.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)

    # The user's name.  We prefer the model of a full_name and
    # short_name over first+last because cultures vary on how many
    # names one has, whether the family name is first or last, etc.
    # It also allows organizations to encode a bit of non-name data in
    # the "name" attribute if desired, like gender pronouns,
    # graduation year, etc.  The short_name attribute is currently not
    # used anywhere, but the intent is that it would be used as the
    # shorter familiar name for addressing the user in the UI.
    full_name: str = models.CharField(max_length=MAX_NAME_LENGTH)
    short_name: str = models.CharField(max_length=MAX_NAME_LENGTH)

    date_joined: datetime.datetime = models.DateTimeField(default=timezone_now)
    tos_version: Optional[str] = models.CharField(null=True, max_length=10)
    api_key: str = models.CharField(max_length=API_KEY_LENGTH)

    # pointer points to Message.id, NOT UserMessage.id.
    pointer: int = models.IntegerField()

    # Whether the user has access to server-level administrator pages, like /activity
    is_staff: bool = models.BooleanField(default=False)

    # For a normal user, this is True unless the user or an admin has
    # deactivated their account.  The name comes from Django; this field
    # isn't related to presence or to whether the user has recently used Zulip.
    #
    # See also `long_term_idle`.
    is_active: bool = models.BooleanField(default=True, db_index=True)

    is_billing_admin: bool = models.BooleanField(default=False, db_index=True)

    is_bot: bool = models.BooleanField(default=False, db_index=True)
    bot_type: Optional[int] = models.PositiveSmallIntegerField(null=True, db_index=True)
    bot_owner: Optional["UserProfile"] = models.ForeignKey('self', null=True, on_delete=models.SET_NULL)

    # Each role has a superset of the permissions of the next higher
    # numbered role.  When adding new roles, leave enough space for
    # future roles to be inserted between currently adjacent
    # roles. These constants appear in RealmAuditLog.extra_data, so
    # changes to them will require a migration of RealmAuditLog.
    ROLE_REALM_OWNER = 100
    ROLE_REALM_ADMINISTRATOR = 200
    # ROLE_MODERATOR = 300
    ROLE_MEMBER = 400
    ROLE_GUEST = 600
    role: int = models.PositiveSmallIntegerField(default=ROLE_MEMBER, db_index=True)

    # Whether the user has been "soft-deactivated" due to weeks of inactivity.
    # For these users we avoid doing UserMessage table work, as an optimization
    # for large Zulip organizations with lots of single-visit users.
    long_term_idle: bool = models.BooleanField(default=False, db_index=True)

    # When we last added basic UserMessage rows for a long_term_idle user.
    last_active_message_id: Optional[int] = models.IntegerField(null=True)

    # Mirror dummies are fake (!is_active) users used to provide
    # message senders in our cross-protocol Zephyr<->Zulip content
    # mirroring integration, so that we can display mirrored content
    # like native Zulip messages (with a name + avatar, etc.).
    is_mirror_dummy: bool = models.BooleanField(default=False)

    # API super users are allowed to forge messages as sent by another
    # user and to send to private streams; also used for Zephyr/Jabber mirroring.
    is_api_super_user: bool = models.BooleanField(default=False, db_index=True)

    ### Notifications settings. ###

    # Stream notifications.
    enable_stream_desktop_notifications: bool = models.BooleanField(default=False)
    enable_stream_email_notifications: bool = models.BooleanField(default=False)
    enable_stream_push_notifications: bool = models.BooleanField(default=False)
    enable_stream_audible_notifications: bool = models.BooleanField(default=False)
    notification_sound: str = models.CharField(max_length=20, default='zulip')
    wildcard_mentions_notify: bool = models.BooleanField(default=True)

    # PM + @-mention notifications.
    enable_desktop_notifications: bool = models.BooleanField(default=True)
    pm_content_in_desktop_notifications: bool = models.BooleanField(default=True)
    enable_sounds: bool = models.BooleanField(default=True)
    enable_offline_email_notifications: bool = models.BooleanField(default=True)
    message_content_in_email_notifications: bool = models.BooleanField(default=True)
    enable_offline_push_notifications: bool = models.BooleanField(default=True)
    enable_online_push_notifications: bool = models.BooleanField(default=True)

    DESKTOP_ICON_COUNT_DISPLAY_MESSAGES = 1
    DESKTOP_ICON_COUNT_DISPLAY_NOTIFIABLE = 2
    DESKTOP_ICON_COUNT_DISPLAY_NONE = 3
    desktop_icon_count_display: int = models.PositiveSmallIntegerField(
        default=DESKTOP_ICON_COUNT_DISPLAY_MESSAGES)

    enable_digest_emails: bool = models.BooleanField(default=True)
    enable_login_emails: bool = models.BooleanField(default=True)
    realm_name_in_notifications: bool = models.BooleanField(default=False)
    presence_enabled: bool = models.BooleanField(default=True)

    # Used for rate-limiting certain automated messages generated by bots
    last_reminder: Optional[datetime.datetime] = models.DateTimeField(default=None, null=True)

    # Minutes to wait before warning a bot owner that their bot sent a message
    # to a nonexistent stream
    BOT_OWNER_STREAM_ALERT_WAITPERIOD = 1

    # API rate limits, formatted as a comma-separated list of range:max pairs
    rate_limits: str = models.CharField(default="", max_length=100)

    # Hours to wait before sending another email to a user
    EMAIL_REMINDER_WAITPERIOD = 24

    # Default streams for some deprecated/legacy classes of bot users.
    default_sending_stream: Optional["Stream"] = models.ForeignKey(
        "zerver.Stream", null=True, related_name="+", on_delete=CASCADE
    )
    default_events_register_stream: Optional["Stream"] = models.ForeignKey(
        "zerver.Stream", null=True, related_name="+", on_delete=CASCADE
    )
    default_all_public_streams: bool = models.BooleanField(default=False)

    # UI vars
    enter_sends: Optional[bool] = models.BooleanField(null=True, default=False)
    left_side_userlist: bool = models.BooleanField(default=False)

    # display settings
    default_language: str = models.CharField(default='en', max_length=MAX_LANGUAGE_ID_LENGTH)
    dense_mode: bool = models.BooleanField(default=True)
    fluid_layout_width: bool = models.BooleanField(default=False)
    high_contrast_mode: bool = models.BooleanField(default=False)
    night_mode: bool = models.BooleanField(default=False)
    translate_emoticons: bool = models.BooleanField(default=False)
    twenty_four_hour_time: bool = models.BooleanField(default=False)
    starred_message_counts: bool = models.BooleanField(default=False)

    # UI setting controlling Zulip's behavior of demoting in the sort
    # order and graying out streams with no recent traffic.  The
    # default behavior, automatic, enables this behavior once a user
    # is subscribed to 30+ streams in the webapp.
    DEMOTE_STREAMS_AUTOMATIC = 1
    DEMOTE_STREAMS_ALWAYS = 2
    DEMOTE_STREAMS_NEVER = 3
    DEMOTE_STREAMS_CHOICES = [
        DEMOTE_STREAMS_AUTOMATIC,
        DEMOTE_STREAMS_ALWAYS,
        DEMOTE_STREAMS_NEVER
    ]
    demote_inactive_streams = models.PositiveSmallIntegerField(default=DEMOTE_STREAMS_AUTOMATIC)

    # A timezone name from the `tzdata` database, as found in pytz.all_timezones.
    #
    # The longest existing name is 32 characters long, so max_length=40 seems
    # like a safe choice.
    #
    # In Django, the convention is to use an empty string instead of NULL/None
    # for text-based fields. For more information, see
    # https://docs.djangoproject.com/en/1.10/ref/models/fields/#django.db.models.Field.null.
    timezone: str = models.CharField(max_length=40, default='')

    # user list sidebar
    BUDDY_LIST_MODE_ALL_USERS = 1
    BUDDY_LIST_MODE_STREAM_OR_PM_RECIPIENTS = 2
    BUDDY_LIST_MODE_CHOICES = [
        BUDDY_LIST_MODE_ALL_USERS,
        BUDDY_LIST_MODE_STREAM_OR_PM_RECIPIENTS
    ]
    buddy_list_mode = models.PositiveSmallIntegerField(default=BUDDY_LIST_MODE_ALL_USERS)

    # Emojisets
    GOOGLE_EMOJISET         = 'google'
    GOOGLE_BLOB_EMOJISET    = 'google-blob'
    TEXT_EMOJISET           = 'text'
    TWITTER_EMOJISET        = 'twitter'
    EMOJISET_CHOICES        = ((GOOGLE_EMOJISET, "Google modern"),
                               (GOOGLE_BLOB_EMOJISET, "Google classic"),
                               (TWITTER_EMOJISET, "Twitter"),
                               (TEXT_EMOJISET, "Plain text"))
    emojiset: str = models.CharField(default=GOOGLE_BLOB_EMOJISET, choices=EMOJISET_CHOICES, max_length=20)

    AVATAR_FROM_GRAVATAR = 'G'
    AVATAR_FROM_USER = 'U'
    AVATAR_SOURCES = (
        (AVATAR_FROM_GRAVATAR, 'Hosted by Gravatar'),
        (AVATAR_FROM_USER, 'Uploaded by user'),
    )
    avatar_source: str = models.CharField(default=AVATAR_FROM_GRAVATAR, choices=AVATAR_SOURCES, max_length=1)
    avatar_version: int = models.PositiveSmallIntegerField(default=1)
    avatar_hash: Optional[str] = models.CharField(null=True, max_length=64)

    TUTORIAL_WAITING  = 'W'
    TUTORIAL_STARTED  = 'S'
    TUTORIAL_FINISHED = 'F'
    TUTORIAL_STATES   = ((TUTORIAL_WAITING, "Waiting"),
                         (TUTORIAL_STARTED, "Started"),
                         (TUTORIAL_FINISHED, "Finished"))
    tutorial_status: str = models.CharField(default=TUTORIAL_WAITING, choices=TUTORIAL_STATES, max_length=1)

    # Contains serialized JSON of the form:
    #    [("step 1", true), ("step 2", false)]
    # where the second element of each tuple is if the step has been
    # completed.
    onboarding_steps: str = models.TextField(default='[]')

    objects: UserManager = UserManager()

    # Define the types of the various automatically managed properties
    property_types = dict(
        buddy_list_mode=int,
        default_language=str,
        demote_inactive_streams=int,
        dense_mode=bool,
        emojiset=str,
        fluid_layout_width=bool,
        high_contrast_mode=bool,
        left_side_userlist=bool,
        night_mode=bool,
        starred_message_counts=bool,
        timezone=str,
        translate_emoticons=bool,
        twenty_four_hour_time=bool,
    )

    notification_setting_types = dict(
        enable_desktop_notifications=bool,
        enable_digest_emails=bool,
        enable_login_emails=bool,
        enable_offline_email_notifications=bool,
        enable_offline_push_notifications=bool,
        enable_online_push_notifications=bool,
        enable_sounds=bool,
        enable_stream_desktop_notifications=bool,
        enable_stream_email_notifications=bool,
        enable_stream_push_notifications=bool,
        enable_stream_audible_notifications=bool,
        wildcard_mentions_notify=bool,
        message_content_in_email_notifications=bool,
        notification_sound=str,
        pm_content_in_desktop_notifications=bool,
        desktop_icon_count_display=int,
        realm_name_in_notifications=bool,
        presence_enabled=bool,
    )

    class Meta:
        unique_together = (('realm', 'email'),)

    @property
    def profile_data(self) -> ProfileData:
        values = CustomProfileFieldValue.objects.filter(user_profile=self)
        user_data = {v.field_id: {"value": v.value, "rendered_value": v.rendered_value} for v in values}
        data: ProfileData = []
        for field in custom_profile_fields_for_realm(self.realm_id):
            field_values = user_data.get(field.id, None)
            if field_values:
                value, rendered_value = field_values.get("value"), field_values.get("rendered_value")
            else:
                value, rendered_value = None, None
            field_type = field.field_type
            if value is not None:
                converter = field.FIELD_CONVERTERS[field_type]
                value = converter(value)

            field_data = field.as_dict()
            field_data['value'] = value
            field_data['rendered_value'] = rendered_value
            data.append(field_data)

        return data

    def can_admin_user(self, target_user: 'UserProfile') -> bool:
        """Returns whether this user has permission to modify target_user"""
        if target_user.bot_owner == self:
            return True
        elif self.is_realm_admin and self.realm == target_user.realm:
            return True
        else:
            return False

    def __str__(self) -> str:
        return "<UserProfile: %s %s>" % (self.email, self.realm)

    @property
    def is_new_member(self) -> bool:
        diff = (timezone_now() - self.date_joined).days
        if diff < self.realm.waiting_period_threshold:
            return True
        return False

    @property
    def is_realm_admin(self) -> bool:
        return self.role == UserProfile.ROLE_REALM_ADMINISTRATOR or \
            self.role == UserProfile.ROLE_REALM_OWNER

    @is_realm_admin.setter
    def is_realm_admin(self, value: bool) -> None:
        if value:
            self.role = UserProfile.ROLE_REALM_ADMINISTRATOR
        elif self.role == UserProfile.ROLE_REALM_ADMINISTRATOR:
            # We need to be careful to not accidentally change
            # ROLE_GUEST to ROLE_MEMBER here.
            self.role = UserProfile.ROLE_MEMBER

    @property
    def is_realm_owner(self) -> bool:
        return self.role == UserProfile.ROLE_REALM_OWNER

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
    def is_incoming_webhook(self) -> bool:
        return self.bot_type == UserProfile.INCOMING_WEBHOOK_BOT

    @property
    def allowed_bot_types(self) -> List[int]:
        allowed_bot_types = []
        if self.is_realm_admin or \
                not self.realm.bot_creation_policy == Realm.BOT_CREATION_LIMIT_GENERIC_BOTS:
            allowed_bot_types.append(UserProfile.DEFAULT_BOT)
        allowed_bot_types += [
            UserProfile.INCOMING_WEBHOOK_BOT,
            UserProfile.OUTGOING_WEBHOOK_BOT,
        ]
        if settings.EMBEDDED_BOTS_ENABLED:
            allowed_bot_types.append(UserProfile.EMBEDDED_BOT)
        return allowed_bot_types

    @staticmethod
    def emojiset_choices() -> List[Dict[str, str]]:
        return [dict(key=emojiset[0], text=emojiset[1]) for emojiset in UserProfile.EMOJISET_CHOICES]

    @staticmethod
    def emails_from_ids(user_ids: Sequence[int]) -> Dict[int, str]:
        rows = UserProfile.objects.filter(id__in=user_ids).values('id', 'email')
        return {row['id']: row['email'] for row in rows}

    def email_address_is_realm_public(self) -> bool:
        if self.realm.email_address_visibility == Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE:
            return True
        if self.is_bot:
            return True
        return False

    def has_permission(self, policy_name: str) -> bool:
        if policy_name not in ['create_stream_policy', 'invite_to_stream_policy']:
            raise AssertionError("Invalid policy")

        if self.is_realm_admin:
            return True

        policy_value = getattr(self.realm, policy_name)
        if policy_value == Realm.POLICY_ADMINS_ONLY:
            return False

        if self.is_guest:
            return False

        if policy_value == Realm.POLICY_MEMBERS_ONLY:
            return True
        return not self.is_new_member

    def can_create_streams(self) -> bool:
        return self.has_permission('create_stream_policy')

    def can_subscribe_other_users(self) -> bool:
        return self.has_permission('invite_to_stream_policy')

    def can_access_public_streams(self) -> bool:
        return not (self.is_guest or self.realm.is_zephyr_mirror_realm)

    def can_access_all_realm_members(self) -> bool:
        return not (self.realm.is_zephyr_mirror_realm or self.is_guest)

    def major_tos_version(self) -> int:
        if self.tos_version is not None:
            return int(self.tos_version.split('.')[0])
        else:
            return -1

    def format_requestor_for_logs(self) -> str:
        return "{}@{}".format(self.id, self.realm.string_id or 'root')

    def set_password(self, password: Optional[str]) -> None:
        if password is None:
            self.set_unusable_password()
            return

        from zproject.backends import check_password_strength
        if not check_password_strength(password):
            raise PasswordTooWeakError

        super().set_password(password)

class PasswordTooWeakError(Exception):
    pass

class UserGroup(models.Model):
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(UserProfile, through='UserGroupMembership')
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    description: str = models.TextField(default='')

    class Meta:
        unique_together = (('realm', 'name'),)

class UserGroupMembership(models.Model):
    user_group = models.ForeignKey(UserGroup, on_delete=CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)

    class Meta:
        unique_together = (('user_group', 'user_profile'),)

def receives_offline_push_notifications(user_profile: UserProfile) -> bool:
    return (user_profile.enable_offline_push_notifications and
            not user_profile.is_bot)

def receives_offline_email_notifications(user_profile: UserProfile) -> bool:
    return (user_profile.enable_offline_email_notifications and
            not user_profile.is_bot)

def receives_online_notifications(user_profile: UserProfile) -> bool:
    return (user_profile.enable_online_push_notifications and
            not user_profile.is_bot)

def receives_stream_notifications(user_profile: UserProfile) -> bool:
    return (user_profile.enable_stream_push_notifications and
            not user_profile.is_bot)

def remote_user_to_email(remote_user: str) -> str:
    if settings.SSO_APPEND_DOMAIN is not None:
        remote_user += "@" + settings.SSO_APPEND_DOMAIN
    return remote_user

# Make sure we flush the UserProfile object from our remote cache
# whenever we save it.
post_save.connect(flush_user_profile, sender=UserProfile)

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

    email: str = models.EmailField()

    # If the pre-registration process provides a suggested full name for this user,
    # store it here to use it to prepopulate the Full Name field in the registration form:
    full_name: Optional[str] = models.CharField(max_length=UserProfile.MAX_NAME_LENGTH, null=True)
    full_name_validated = models.BooleanField(default=False)
    referred_by: Optional[UserProfile] = models.ForeignKey(UserProfile, null=True, on_delete=CASCADE)
    streams: Manager = models.ManyToManyField('Stream')
    invited_at: datetime.datetime = models.DateTimeField(auto_now=True)
    realm_creation = models.BooleanField(default=False)
    # Indicates whether the user needs a password.  Users who were
    # created via SSO style auth (e.g. GitHub/Google) generally do not.
    password_required = models.BooleanField(default=True)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_ACTIVE
    status: int = models.IntegerField(default=0)

    # The realm should only ever be None for PreregistrationUser
    # objects created as part of realm creation.
    realm: Optional[Realm] = models.ForeignKey(Realm, null=True, on_delete=CASCADE)

    # Changes to INVITED_AS should also be reflected in
    # settings_invites.invited_as_values in
    # static/js/settings_invites.js
    INVITE_AS = dict(
        MEMBER = 1,
        REALM_ADMIN = 2,
        GUEST_USER = 3,
    )
    invited_as: int = models.PositiveSmallIntegerField(default=INVITE_AS['MEMBER'])

class MultiuseInvite(models.Model):
    referred_by = models.ForeignKey(UserProfile, on_delete=CASCADE)  # Optional[UserProfile]
    streams: Manager = models.ManyToManyField('Stream')
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    invited_as: int = models.PositiveSmallIntegerField(default=PreregistrationUser.INVITE_AS['MEMBER'])

class EmailChangeStatus(models.Model):
    new_email: str = models.EmailField()
    old_email: str = models.EmailField()
    updated_at: datetime.datetime = models.DateTimeField(auto_now=True)
    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_ACTIVE
    status: int = models.IntegerField(default=0)

    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)

class AbstractPushDeviceToken(models.Model):
    APNS = 1
    GCM = 2

    KINDS = (
        (APNS, 'apns'),
        (GCM, 'gcm'),
    )

    kind: int = models.PositiveSmallIntegerField(choices=KINDS)

    # The token is a unique device-specific token that is
    # sent to us from each device:
    #   - APNS token if kind == APNS
    #   - GCM registration id if kind == GCM
    token: str = models.CharField(max_length=4096, db_index=True)

    # TODO: last_updated should be renamed date_created, since it is
    # no longer maintained as a last_updated value.
    last_updated: datetime.datetime = models.DateTimeField(auto_now=True)

    # [optional] Contains the app id of the device if it is an iOS device
    ios_app_id: Optional[str] = models.TextField(null=True)

    class Meta:
        abstract = True

class PushDeviceToken(AbstractPushDeviceToken):
    # The user who's device this is
    user: UserProfile = models.ForeignKey(UserProfile, db_index=True, on_delete=CASCADE)

    class Meta:
        unique_together = ("user", "kind", "token")

def generate_email_token_for_stream() -> str:
    return generate_random_token(32)

class Stream(models.Model):
    MAX_NAME_LENGTH = 60
    MAX_DESCRIPTION_LENGTH = 1024

    name: str = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)
    realm: Realm = models.ForeignKey(Realm, db_index=True, on_delete=CASCADE)
    date_created: datetime.datetime = models.DateTimeField(default=timezone_now)
    deactivated: bool = models.BooleanField(default=False)
    description: str = models.CharField(max_length=MAX_DESCRIPTION_LENGTH, default='')
    rendered_description: str = models.TextField(default='')

    # Foreign key to the Recipient object for STREAM type messages to this stream.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)

    invite_only: Optional[bool] = models.BooleanField(null=True, default=False)
    history_public_to_subscribers: bool = models.BooleanField(default=False)

    # Whether this stream's content should be published by the web-public archive features
    is_web_public: bool = models.BooleanField(default=False)

    STREAM_POST_POLICY_EVERYONE = 1
    STREAM_POST_POLICY_ADMINS = 2
    STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS = 3
    # TODO: Implement policy to restrict posting to a user group or admins.

    # Who in the organization has permission to send messages to this stream.
    stream_post_policy: int = models.PositiveSmallIntegerField(default=STREAM_POST_POLICY_EVERYONE)
    STREAM_POST_POLICY_TYPES = [
        STREAM_POST_POLICY_EVERYONE,
        STREAM_POST_POLICY_ADMINS,
        STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS,
    ]

    # The unique thing about Zephyr public streams is that we never list their
    # users.  We may try to generalize this concept later, but for now
    # we just use a concrete field.  (Zephyr public streams aren't exactly like
    # invite-only streams--while both are private in terms of listing users,
    # for Zephyr we don't even list users to stream members, yet membership
    # is more public in the sense that you don't need a Zulip invite to join.
    # This field is populated directly from UserProfile.is_zephyr_mirror_realm,
    # and the reason for denormalizing field is performance.
    is_in_zephyr_realm: bool = models.BooleanField(default=False)

    # Used by the e-mail forwarder. The e-mail RFC specifies a maximum
    # e-mail length of 254, and our max stream length is 30, so we
    # have plenty of room for the token.
    email_token: str = models.CharField(
        max_length=32, default=generate_email_token_for_stream, unique=True
    )

    # For old messages being automatically deleted.
    # Value NULL means "use retention policy of the realm".
    # Value -1 means "disable retention policy for this stream unconditionally".
    # Non-negative values have the natural meaning of "archive messages older than <value> days".
    message_retention_days: Optional[int] = models.IntegerField(null=True, default=None)

    # The very first message ID in the stream.  Used to help clients
    # determine whether they might need to display "more topics" for a
    # stream based on what messages they have cached.
    first_message_id: Optional[int] = models.IntegerField(null=True, db_index=True)

    def __str__(self) -> str:
        return "<Stream: %s>" % (self.name,)

    def is_public(self) -> bool:
        # All streams are private in Zephyr mirroring realms.
        return not self.invite_only and not self.is_in_zephyr_realm

    def is_history_realm_public(self) -> bool:
        return self.is_public()

    def is_history_public_to_subscribers(self) -> bool:
        return self.history_public_to_subscribers

    class Meta:
        unique_together = ("name", "realm")

    # Stream fields included whenever a Stream object is provided to
    # Zulip clients via the API.  A few details worth noting:
    # * "id" is represented as "stream_id" in most API interfaces.
    # * "email_token" is not realm-public and thus is not included here.
    # * is_in_zephyr_realm is a backend-only optimization.
    # * "deactivated" streams are filtered from the API entirely.
    # * "realm" and "recipient" are not exposed to clients via the API.
    # * "date_created" should probably be added here, as it's useful information
    #   to subscribers and is needed to compute is_old_stream.
    # * message_retention_days should be added here once the feature is
    #   complete.
    API_FIELDS = [
        "name",
        "id",
        "description",
        "rendered_description",
        "invite_only",
        "is_web_public",
        "stream_post_policy",
        "history_public_to_subscribers",
        "first_message_id",
    ]

    @staticmethod
    def get_client_data(query: QuerySet) -> List[Dict[str, Any]]:
        query = query.only(*Stream.API_FIELDS)
        return [row.to_dict() for row in query]

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for field_name in self.API_FIELDS:
            if field_name == "id":
                result['stream_id'] = self.id
                continue
            result[field_name] = getattr(self, field_name)
        result['is_announcement_only'] = self.stream_post_policy == Stream.STREAM_POST_POLICY_ADMINS
        return result

post_save.connect(flush_stream, sender=Stream)
post_delete.connect(flush_stream, sender=Stream)

class MutedTopic(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    topic_name = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)
    # The default value for date_muted is a few weeks before tracking
    # of when topics were muted was first introduced.  It's designed
    # to be obviously incorrect so that users can tell it's backfilled data.
    date_muted = models.DateTimeField(default=datetime.datetime(2020, 1, 1, 0, 0, 0, 0))

    class Meta:
        unique_together = ('user_profile', 'stream', 'topic_name')

    def __str__(self) -> str:
        return ("<MutedTopic: (%s, %s, %s, %s)>" % (self.user_profile.email,
                                                    self.stream.name,
                                                    self.topic_name,
                                                    self.date_muted))

class Client(models.Model):
    name: str = models.CharField(max_length=30, db_index=True, unique=True)

    def __str__(self) -> str:
        return "<Client: %s>" % (self.name,)

get_client_cache: Dict[str, Client] = {}
def get_client(name: str) -> Client:
    # Accessing KEY_PREFIX through the module is necessary
    # because we need the updated value of the variable.
    cache_name = cache.KEY_PREFIX + name
    if cache_name not in get_client_cache:
        result = get_client_remote_cache(name)
        get_client_cache[cache_name] = result
    return get_client_cache[cache_name]

def get_client_cache_key(name: str) -> str:
    return 'get_client:%s' % (make_safe_digest(name),)

@cache_with_key(get_client_cache_key, timeout=3600*24*7)
def get_client_remote_cache(name: str) -> Client:
    (client, _) = Client.objects.get_or_create(name=name)
    return client

@cache_with_key(get_stream_cache_key, timeout=3600*24*7)
def get_realm_stream(stream_name: str, realm_id: int) -> Stream:
    return Stream.objects.select_related().get(
        name__iexact=stream_name.strip(), realm_id=realm_id)

def stream_name_in_use(stream_name: str, realm_id: int) -> bool:
    return Stream.objects.filter(
        name__iexact=stream_name.strip(),
        realm_id=realm_id
    ).exists()

def get_active_streams(realm: Optional[Realm]) -> QuerySet:
    # TODO: Change return type to QuerySet[Stream]
    # NOTE: Return value is used as a QuerySet, so cannot currently be Sequence[QuerySet]
    """
    Return all streams (including invite-only streams) that have not been deactivated.
    """
    return Stream.objects.filter(realm=realm, deactivated=False)

def get_stream(stream_name: str, realm: Realm) -> Stream:
    '''
    Callers that don't have a Realm object already available should use
    get_realm_stream directly, to avoid unnecessarily fetching the
    Realm object.
    '''
    return get_realm_stream(stream_name, realm.id)

def get_stream_by_id_in_realm(stream_id: int, realm: Realm) -> Stream:
    return Stream.objects.select_related().get(id=stream_id, realm=realm)

def bulk_get_streams(realm: Realm, stream_names: STREAM_NAMES) -> Dict[str, Any]:

    def fetch_streams_by_name(stream_names: List[str]) -> Sequence[Stream]:
        #
        # This should be just
        #
        # Stream.objects.select_related().filter(name__iexact__in=stream_names,
        #                                        realm_id=realm_id)
        #
        # But chaining __in and __iexact doesn't work with Django's
        # ORM, so we have the following hack to construct the relevant where clause
        upper_list = ", ".join(["UPPER(%s)"] * len(stream_names))
        where_clause = "UPPER(zerver_stream.name::text) IN (%s)" % (upper_list,)
        return get_active_streams(realm.id).select_related().extra(
            where=[where_clause],
            params=stream_names)

    def stream_name_to_cache_key(stream_name: str) -> str:
        return get_stream_cache_key(stream_name, realm.id)

    def stream_to_lower_name(stream: Stream) -> str:
        return stream.name.lower()

    return generic_bulk_cached_fetch(stream_name_to_cache_key,
                                     fetch_streams_by_name,
                                     [stream_name.lower() for stream_name in stream_names],
                                     id_fetcher=stream_to_lower_name)

def get_huddle_recipient(user_profile_ids: Set[int]) -> Recipient:

    # The caller should ensure that user_profile_ids includes
    # the sender.  Note that get_huddle hits the cache, and then
    # we hit another cache to get the recipient.  We may want to
    # unify our caching strategy here.
    huddle = get_huddle(list(user_profile_ids))
    return huddle.recipient

def get_huddle_user_ids(recipient: Recipient) -> List[int]:
    assert(recipient.type == Recipient.HUDDLE)

    return Subscription.objects.filter(
        recipient=recipient
    ).order_by('user_profile_id').values_list('user_profile_id', flat=True)

def bulk_get_huddle_user_ids(recipients: List[Recipient]) -> Dict[int, List[int]]:
    """
    Takes a list of huddle-type recipients, returns a dict
    mapping recipient id to list of user ids in the huddle.
    """
    assert all(recipient.type == Recipient.HUDDLE for recipient in recipients)
    if not recipients:
        return {}

    subscriptions = Subscription.objects.filter(
        recipient__in=recipients
    ).order_by('user_profile_id')

    result_dict: Dict[int, List[int]] = {}
    for recipient in recipients:
        result_dict[recipient.id] = [subscription.user_profile_id
                                     for subscription in subscriptions
                                     if subscription.recipient_id == recipient.id]

    return result_dict

class AbstractMessage(models.Model):
    sender: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    recipient: Recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    # The message's topic.
    #
    # Early versions of Zulip called this concept a "subject", as in an email
    # "subject line", before changing to "topic" in 2013 (commit dac5a46fa).
    # UI and user documentation now consistently say "topic".  New APIs and
    # new code should generally also say "topic".
    #
    # See also the `topic_name` method on `Message`.
    subject: str = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH, db_index=True)

    content: str = models.TextField()
    rendered_content: Optional[str] = models.TextField(null=True)
    rendered_content_version: Optional[int] = models.IntegerField(null=True)

    date_sent: datetime.datetime = models.DateTimeField('date sent', db_index=True)
    sending_client: Client = models.ForeignKey(Client, on_delete=CASCADE)

    last_edit_time: Optional[datetime.datetime] = models.DateTimeField(null=True)

    # A JSON-encoded list of objects describing any past edits to this
    # message, oldest first.
    edit_history: Optional[str] = models.TextField(null=True)

    has_attachment: bool = models.BooleanField(default=False, db_index=True)
    has_image: bool = models.BooleanField(default=False, db_index=True)
    has_link: bool = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        display_recipient = get_display_recipient(self.recipient)
        return "<%s: %s / %s / %s>" % (self.__class__.__name__, display_recipient,
                                       self.subject, self.sender)

class ArchiveTransaction(models.Model):
    timestamp: datetime.datetime = models.DateTimeField(default=timezone_now, db_index=True)
    # Marks if the data archived in this transaction has been restored:
    restored: bool = models.BooleanField(default=False, db_index=True)

    type: int = models.PositiveSmallIntegerField(db_index=True)
    # Valid types:
    RETENTION_POLICY_BASED = 1  # Archiving was executed due to automated retention policies
    MANUAL = 2  # Archiving was run manually, via move_messages_to_archive function

    # ForeignKey to the realm with which objects archived in this transaction are associated.
    # If type is set to MANUAL, this should be null.
    realm: Optional[Realm] = models.ForeignKey(Realm, null=True, on_delete=CASCADE)

    def __str__(self) -> str:
        return "ArchiveTransaction id: {id}, type: {type}, realm: {realm}, timestamp: {timestamp}".format(
            id=self.id,
            type="MANUAL" if self.type == self.MANUAL else "RETENTION_POLICY_BASED",
            realm=self.realm.string_id if self.realm else None,
            timestamp=self.timestamp
        )

class ArchivedMessage(AbstractMessage):
    """Used as a temporary holding place for deleted messages before they
    are permanently deleted.  This is an important part of a robust
    'message retention' feature.
    """
    archive_transaction: ArchiveTransaction = models.ForeignKey(ArchiveTransaction, on_delete=CASCADE)

class Message(AbstractMessage):

    def topic_name(self) -> str:
        """
        Please start using this helper to facilitate an
        eventual switch over to a separate topic table.
        """
        return self.subject

    def set_topic_name(self, topic_name: str) -> None:
        self.subject = topic_name

    def is_stream_message(self) -> bool:
        '''
        Find out whether a message is a stream message by
        looking up its recipient.type.  TODO: Make this
        an easier operation by denormalizing the message
        type onto Message, either explicitly (message.type)
        or implicitly (message.stream_id is not None).
        '''
        return self.recipient.type == Recipient.STREAM

    def get_realm(self) -> Realm:
        return self.sender.realm

    def save_rendered_content(self) -> None:
        self.save(update_fields=["rendered_content", "rendered_content_version"])

    @staticmethod
    def need_to_render_content(rendered_content: Optional[str],
                               rendered_content_version: Optional[int],
                               bugdown_version: int) -> bool:
        return (rendered_content is None or
                rendered_content_version is None or
                rendered_content_version < bugdown_version)

    def to_log_dict(self) -> Dict[str, Any]:
        return dict(
            id                = self.id,
            sender_id         = self.sender.id,
            sender_email      = self.sender.email,
            sender_realm_str  = self.sender.realm.string_id,
            sender_full_name  = self.sender.full_name,
            sender_short_name = self.sender.short_name,
            sending_client    = self.sending_client.name,
            type              = self.recipient.type_name(),
            recipient         = get_display_recipient(self.recipient),
            subject           = self.topic_name(),
            content           = self.content,
            timestamp         = datetime_to_timestamp(self.date_sent))

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

        return (sending_client in ('zulipandroid', 'zulipios', 'zulipdesktop',
                                   'zulipmobile', 'zulipelectron', 'zulipterminal', 'snipe',
                                   'website', 'ios', 'android')) or (
                                       'desktop app' in sending_client)

    @staticmethod
    def is_status_message(content: str, rendered_content: str) -> bool:
        """
        "status messages" start with /me and have special rendering:
            /me loves chocolate -> Full Name loves chocolate
        """
        if content.startswith('/me '):
            return True
        return False

def get_context_for_message(message: Message) -> Sequence[Message]:
    # TODO: Change return type to QuerySet[Message]
    return Message.objects.filter(
        recipient_id=message.recipient_id,
        subject=message.subject,
        id__lt=message.id,
        date_sent__gt=message.date_sent - timedelta(minutes=15),
    ).order_by('-id')[:10]

post_save.connect(flush_message, sender=Message)

class AbstractSubMessage(models.Model):
    # We can send little text messages that are associated with a regular
    # Zulip message.  These can be used for experimental widgets like embedded
    # games, surveys, mini threads, etc.  These are designed to be pretty
    # generic in purpose.

    sender: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    msg_type = models.TextField()
    content = models.TextField()

    class Meta:
        abstract = True

class SubMessage(AbstractSubMessage):
    message: Message = models.ForeignKey(Message, on_delete=CASCADE)

    @staticmethod
    def get_raw_db_rows(needed_ids: List[int]) -> List[Dict[str, Any]]:
        fields = ['id', 'message_id', 'sender_id', 'msg_type', 'content']
        query = SubMessage.objects.filter(message_id__in=needed_ids).values(*fields)
        query = query.order_by('message_id', 'id')
        return list(query)

class ArchivedSubMessage(AbstractSubMessage):
    message: ArchivedMessage = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)

post_save.connect(flush_submessage, sender=SubMessage)

class AbstractReaction(models.Model):
    """For emoji reactions to messages (and potentially future reaction types).

    Emoji are surprisingly complicated to implement correctly.  For details
    on how this subsystem works, see:
      https://zulip.readthedocs.io/en/latest/subsystems/emoji.html
    """
    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # The user-facing name for an emoji reaction.  With emoji aliases,
    # there may be multiple accepted names for a given emoji; this
    # field encodes which one the user selected.
    emoji_name: str = models.TextField()

    UNICODE_EMOJI       = 'unicode_emoji'
    REALM_EMOJI         = 'realm_emoji'
    ZULIP_EXTRA_EMOJI   = 'zulip_extra_emoji'
    REACTION_TYPES      = ((UNICODE_EMOJI, _("Unicode emoji")),
                           (REALM_EMOJI, _("Custom emoji")),
                           (ZULIP_EXTRA_EMOJI, _("Zulip extra emoji")))
    reaction_type: str = models.CharField(default=UNICODE_EMOJI, choices=REACTION_TYPES, max_length=30)

    # A string that uniquely identifies a particular emoji.  The format varies
    # by type:
    #
    # * For Unicode emoji, a dash-separated hex encoding of the sequence of
    #   Unicode codepoints that define this emoji in the Unicode
    #   specification.  For examples, see "non_qualified" or "unified" in the
    #   following data, with "non_qualified" taking precedence when both present:
    #     https://raw.githubusercontent.com/iamcal/emoji-data/master/emoji_pretty.json
    #
    # * For realm emoji (aka user uploaded custom emoji), the ID
    #   (in ASCII decimal) of the RealmEmoji object.
    #
    # * For "Zulip extra emoji" (like :zulip:), the filename of the emoji.
    emoji_code: str = models.TextField()

    class Meta:
        abstract = True
        unique_together = ("user_profile", "message", "emoji_name")

class Reaction(AbstractReaction):
    message: Message = models.ForeignKey(Message, on_delete=CASCADE)

    @staticmethod
    def get_raw_db_rows(needed_ids: List[int]) -> List[Dict[str, Any]]:
        fields = ['message_id', 'emoji_name', 'emoji_code', 'reaction_type',
                  'user_profile__email', 'user_profile__id', 'user_profile__full_name']
        return Reaction.objects.filter(message_id__in=needed_ids).values(*fields)

    def __str__(self) -> str:
        return "%s / %s / %s" % (self.user_profile.email, self.message.id, self.emoji_name)

class ArchivedReaction(AbstractReaction):
    message: ArchivedMessage = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)

# Whenever a message is sent, for each user subscribed to the
# corresponding Recipient object, we add a row to the UserMessage
# table indicating that that user received that message.  This table
# allows us to quickly query any user's last 1000 messages to generate
# the home view.
#
# Additionally, the flags field stores metadata like whether the user
# has read the message, starred or collapsed the message, was
# mentioned in the message, etc.
#
# UserMessage is the largest table in a Zulip installation, even
# though each row is only 4 integers.
class AbstractUserMessage(models.Model):
    id: int = models.BigAutoField(primary_key=True)

    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    # The order here is important!  It's the order of fields in the bitfield.
    ALL_FLAGS = [
        'read',
        'starred',
        'collapsed',
        'mentioned',
        'wildcard_mentioned',
        # These next 4 flags are from features that have since been removed.
        'summarize_in_home',
        'summarize_in_stream',
        'force_expand',
        'force_collapse',
        # Whether the message contains any of the user's alert words.
        'has_alert_word',
        # The historical flag is used to mark messages which the user
        # did not receive when they were sent, but later added to
        # their history via e.g. starring the message.  This is
        # important accounting for the "Subscribed to stream" dividers.
        'historical',
        # Whether the message is a private message; this flag is a
        # denormalization of message.recipient.type to support an
        # efficient index on UserMessage for a user's private messages.
        'is_private',
        # Whether we've sent a push notification to the user's mobile
        # devices for this message that has not been revoked.
        'active_mobile_push_notification',
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
    def where_unread() -> str:
        # Use this for Django ORM queries to access unread message.
        # This custom SQL plays nice with our partial indexes.  Grep
        # the code for example usage.
        return 'flags & 1 = 0'

    @staticmethod
    def where_starred() -> str:
        # Use this for Django ORM queries to access starred messages.
        # This custom SQL plays nice with our partial indexes.  Grep
        # the code for example usage.
        #
        # The key detail is that e.g.
        #   UserMessage.objects.filter(user_profile=user_profile, flags=UserMessage.flags.starred)
        # will generate a query involving `flags & 2 = 2`, which doesn't match our index.
        return 'flags & 2 <> 0'

    @staticmethod
    def where_active_push_notification() -> str:
        # See where_starred for documentation.
        return 'flags & 4096 <> 0'

    def flags_list(self) -> List[str]:
        flags = int(self.flags)
        return self.flags_list_for_flags(flags)

    @staticmethod
    def flags_list_for_flags(val: int) -> List[str]:
        '''
        This function is highly optimized, because it actually slows down
        sending messages in a naive implementation.
        '''
        flags = []
        mask = 1
        for flag in UserMessage.ALL_FLAGS:
            if (val & mask) and flag not in AbstractUserMessage.NON_API_FLAGS:
                flags.append(flag)
            mask <<= 1
        return flags

    def __str__(self) -> str:
        display_recipient = get_display_recipient(self.message.recipient)
        return "<%s: %s / %s (%s)>" % (self.__class__.__name__, display_recipient,
                                       self.user_profile.email, self.flags_list())


class UserMessage(AbstractUserMessage):
    message: Message = models.ForeignKey(Message, on_delete=CASCADE)

def get_usermessage_by_message_id(user_profile: UserProfile, message_id: int) -> Optional[UserMessage]:
    try:
        return UserMessage.objects.select_related().get(user_profile=user_profile,
                                                        message__id=message_id)
    except UserMessage.DoesNotExist:
        return None

class ArchivedUserMessage(AbstractUserMessage):
    """Used as a temporary holding place for deleted UserMessages objects
    before they are permanently deleted.  This is an important part of
    a robust 'message retention' feature.
    """
    message: Message = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)

class AbstractAttachment(models.Model):
    file_name: str = models.TextField(db_index=True)

    # path_id is a storage location agnostic representation of the path of the file.
    # If the path of a file is http://localhost:9991/user_uploads/a/b/abc/temp_file.py
    # then its path_id will be a/b/abc/temp_file.py.
    path_id: str = models.TextField(db_index=True, unique=True)
    owner: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    realm: Optional[Realm] = models.ForeignKey(Realm, blank=True, null=True, on_delete=CASCADE)

    create_time: datetime.datetime = models.DateTimeField(
        default=timezone_now, db_index=True
    )
    size: Optional[int] = models.IntegerField(null=True)

    # Whether this attachment has been posted to a public stream, and
    # thus should be available to all non-guest users in the
    # organization (even if they weren't a recipient of a message
    # linking to it).  This lets us avoid looking up the corresponding
    # messages/streams to check permissions before serving these files.
    is_realm_public: bool = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return "<%s: %s>" % (self.__class__.__name__, self.file_name,)


class ArchivedAttachment(AbstractAttachment):
    """Used as a temporary holding place for deleted Attachment objects
    before they are permanently deleted.  This is an important part of
    a robust 'message retention' feature.
    """
    messages: Manager = models.ManyToManyField(ArchivedMessage)

class Attachment(AbstractAttachment):
    messages: Manager = models.ManyToManyField(Message)

    def is_claimed(self) -> bool:
        return self.messages.count() > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.file_name,
            'path_id': self.path_id,
            'size': self.size,
            # convert to JavaScript-style UNIX timestamp so we can take
            # advantage of client timezones.
            'create_time': time.mktime(self.create_time.timetuple()) * 1000,
            'messages': [{
                'id': m.id,
                'name': time.mktime(m.date_sent.timetuple()) * 1000
            } for m in self.messages.all()]
        }

post_save.connect(flush_used_upload_space_cache, sender=Attachment)
post_delete.connect(flush_used_upload_space_cache, sender=Attachment)

def validate_attachment_request(user_profile: UserProfile, path_id: str) -> Optional[bool]:
    try:
        attachment = Attachment.objects.get(path_id=path_id)
    except Attachment.DoesNotExist:
        return None

    if user_profile == attachment.owner:
        # If you own the file, you can access it.
        return True
    if (attachment.is_realm_public and attachment.realm == user_profile.realm and
            user_profile.can_access_public_streams()):
        # Any user in the realm can access realm-public files
        return True

    messages = attachment.messages.all()
    if UserMessage.objects.filter(user_profile=user_profile, message__in=messages).exists():
        # If it was sent in a private message or private stream
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
        recipient__in=[m.recipient_id for m in messages]).values_list("recipient__type_id", flat=True)
    if len(relevant_stream_ids) == 0:
        return False

    return Stream.objects.filter(id__in=relevant_stream_ids,
                                 history_public_to_subscribers=True).exists()

def get_old_unclaimed_attachments(weeks_ago: int) -> Sequence[Attachment]:
    # TODO: Change return type to QuerySet[Attachment]
    delta_weeks_ago = timezone_now() - datetime.timedelta(weeks=weeks_ago)
    old_attachments = Attachment.objects.filter(messages=None, create_time__lt=delta_weeks_ago)
    return old_attachments

class Subscription(models.Model):
    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    recipient: Recipient = models.ForeignKey(Recipient, on_delete=CASCADE)

    # Whether the user has since unsubscribed.  We mark Subscription
    # objects as inactive, rather than deleting them, when a user
    # unsubscribes, so we can preserve user customizations like
    # notification settings, stream color, etc., if the user later
    # resubscribes.
    active: bool = models.BooleanField(default=True)

    # Whether this user had muted this stream.
    is_muted: Optional[bool] = models.BooleanField(null=True, default=False)

    DEFAULT_STREAM_COLOR = "#c2c2c2"
    color: str = models.CharField(max_length=10, default=DEFAULT_STREAM_COLOR)
    pin_to_top: bool = models.BooleanField(default=False)

    # These fields are stream-level overrides for the user's default
    # configuration for notification, configured in UserProfile.  The
    # default, None, means we just inherit the user-level default.
    desktop_notifications: Optional[bool] = models.BooleanField(null=True, default=None)
    audible_notifications: Optional[bool] = models.BooleanField(null=True, default=None)
    push_notifications: Optional[bool] = models.BooleanField(null=True, default=None)
    email_notifications: Optional[bool] = models.BooleanField(null=True, default=None)
    wildcard_mentions_notify: Optional[bool] = models.BooleanField(null=True, default=None)

    class Meta:
        unique_together = ("user_profile", "recipient")

    def __str__(self) -> str:
        return "<Subscription: %s -> %s>" % (self.user_profile, self.recipient)

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
        "active",
        "color",
        "is_muted",
        "pin_to_top",
        "audible_notifications",
        "desktop_notifications",
        "email_notifications",
        "push_notifications",
        "wildcard_mentions_notify",
    ]

@cache_with_key(user_profile_by_id_cache_key, timeout=3600*24*7)
def get_user_profile_by_id(uid: int) -> UserProfile:
    return UserProfile.objects.select_related().get(id=uid)

@cache_with_key(user_profile_by_email_cache_key, timeout=3600*24*7)
def get_user_profile_by_email(email: str) -> UserProfile:
    """This function is intended to be used by our unit tests and for
    manual manage.py shell work; robust code must use get_user or
    get_user_by_delivery_email instead, because Zulip supports
    multiple users with a given (delivery) email address existing on a
    single server (in different realms).
    """
    return UserProfile.objects.select_related().get(delivery_email__iexact=email.strip())

@cache_with_key(user_profile_by_api_key_cache_key, timeout=3600*24*7)
def maybe_get_user_profile_by_api_key(api_key: str) -> Optional[UserProfile]:
    try:
        return UserProfile.objects.select_related().get(api_key=api_key)
    except UserProfile.DoesNotExist:
        # We will cache failed lookups with None.  The
        # use case here is that broken API clients may
        # continually ask for the same wrong API key, and
        # we want to handle that as quickly as possible.
        return None

def get_user_profile_by_api_key(api_key: str) -> UserProfile:
    user_profile = maybe_get_user_profile_by_api_key(api_key)
    if user_profile is None:
        raise UserProfile.DoesNotExist()

    return user_profile

def get_user_by_delivery_email(email: str, realm: Realm) -> UserProfile:
    """Fetches a user given their delivery email.  For use in
    authentication/registration contexts.  Do not use for user-facing
    views (e.g. Zulip API endpoints) as doing so would violate the
    EMAIL_ADDRESS_VISIBILITY_ADMINS security model.  Use get_user in
    those code paths.
    """
    return UserProfile.objects.select_related().get(
        delivery_email__iexact=email.strip(), realm=realm)

def get_users_by_delivery_email(emails: Set[str], realm: Realm) -> QuerySet:
    """This is similar to get_users_by_delivery_email, and
    it has the same security caveats.  It gets multiple
    users and returns a QuerySet, since most callers
    will only need two or three fields.

    If you are using this to get large UserProfile objects, you are
    probably making a mistake, but if you must,
    then use `select_related`.
    """

    '''
    Django doesn't support delivery_email__iexact__in, so
    we simply OR all the filters that we'd do for the
    one-email case.
    '''
    email_filter = Q()
    for email in emails:
        email_filter |= Q(delivery_email__iexact=email.strip())

    return UserProfile.objects.filter(realm=realm).filter(email_filter)

@cache_with_key(user_profile_cache_key, timeout=3600*24*7)
def get_user(email: str, realm: Realm) -> UserProfile:
    """Fetches the user by its visible-to-other users username (in the
    `email` field).  For use in API contexts; do not use in
    authentication/registration contexts as doing so will break
    authentication in organizations using
    EMAIL_ADDRESS_VISIBILITY_ADMINS.  In those code paths, use
    get_user_by_delivery_email.
    """
    return UserProfile.objects.select_related().get(email__iexact=email.strip(), realm=realm)

def get_active_user(email: str, realm: Realm) -> UserProfile:
    """Variant of get_user_by_email that excludes deactivated users.
    See get_user docstring for important usage notes."""
    user_profile = get_user(email, realm)
    if not user_profile.is_active:
        raise UserProfile.DoesNotExist()
    return user_profile

def get_user_profile_by_id_in_realm(uid: int, realm: Realm) -> UserProfile:
    return UserProfile.objects.select_related().get(id=uid, realm=realm)

def get_user_including_cross_realm(email: str, realm: Optional[Realm]=None) -> UserProfile:
    if is_cross_realm_bot_email(email):
        return get_system_bot(email)
    assert realm is not None
    return get_user(email, realm)

@cache_with_key(bot_profile_cache_key, timeout=3600*24*7)
def get_system_bot(email: str) -> UserProfile:
    return UserProfile.objects.select_related().get(email__iexact=email.strip())

def get_user_by_id_in_realm_including_cross_realm(
        uid: int,
        realm: Optional[Realm]
) -> UserProfile:
    user_profile = get_user_profile_by_id(uid)
    if user_profile.realm == realm:
        return user_profile

    # Note: This doesn't validate whether the `realm` passed in is
    # None/invalid for the CROSS_REALM_BOT_EMAILS case.
    if user_profile.delivery_email in settings.CROSS_REALM_BOT_EMAILS:
        return user_profile

    raise UserProfile.DoesNotExist()

@cache_with_key(realm_user_dicts_cache_key, timeout=3600*24*7)
def get_realm_user_dicts(realm_id: int) -> List[Dict[str, Any]]:
    return UserProfile.objects.filter(
        realm_id=realm_id,
    ).values(*realm_user_dict_fields)

@cache_with_key(active_user_ids_cache_key, timeout=3600*24*7)
def active_user_ids(realm_id: int) -> List[int]:
    query = UserProfile.objects.filter(
        realm_id=realm_id,
        is_active=True
    ).values_list('id', flat=True)
    return list(query)

@cache_with_key(active_non_guest_user_ids_cache_key, timeout=3600*24*7)
def active_non_guest_user_ids(realm_id: int) -> List[int]:
    query = UserProfile.objects.filter(
        realm_id=realm_id,
        is_active=True
    ).exclude(
        role=UserProfile.ROLE_GUEST
    ).values_list('id', flat=True)
    return list(query)

def get_source_profile(email: str, string_id: str) -> Optional[UserProfile]:
    try:
        return get_user_by_delivery_email(email, get_realm(string_id))
    except (Realm.DoesNotExist, UserProfile.DoesNotExist):
        return None

@cache_with_key(bot_dicts_in_realm_cache_key, timeout=3600*24*7)
def get_bot_dicts_in_realm(realm: Realm) -> List[Dict[str, Any]]:
    return UserProfile.objects.filter(realm=realm, is_bot=True).values(*bot_dict_fields)

def is_cross_realm_bot_email(email: str) -> bool:
    return email.lower() in settings.CROSS_REALM_BOT_EMAILS

# The Huddle class represents a group of individuals who have had a
# Group Private Message conversation together.  The actual membership
# of the Huddle is stored in the Subscription table just like with
# Streams, and a hash of that list is stored in the huddle_hash field
# below, to support efficiently mapping from a set of users to the
# corresponding Huddle object.
class Huddle(models.Model):
    # TODO: We should consider whether using
    # CommaSeparatedIntegerField would be better.
    huddle_hash: str = models.CharField(max_length=40, db_index=True, unique=True)
    # Foreign key to the Recipient object for this Huddle.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)

def get_huddle_hash(id_list: List[int]) -> str:
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    return make_safe_digest(hash_key)

def huddle_hash_cache_key(huddle_hash: str) -> str:
    return "huddle_by_hash:%s" % (huddle_hash,)

def get_huddle(id_list: List[int]) -> Huddle:
    huddle_hash = get_huddle_hash(id_list)
    return get_huddle_backend(huddle_hash, id_list)

@cache_with_key(lambda huddle_hash, id_list: huddle_hash_cache_key(huddle_hash), timeout=3600*24*7)
def get_huddle_backend(huddle_hash: str, id_list: List[int]) -> Huddle:
    with transaction.atomic():
        (huddle, created) = Huddle.objects.get_or_create(huddle_hash=huddle_hash)
        if created:
            recipient = Recipient.objects.create(type_id=huddle.id,
                                                 type=Recipient.HUDDLE)
            huddle.recipient = recipient
            huddle.save(update_fields=["recipient"])
            subs_to_create = [Subscription(recipient=recipient,
                                           user_profile_id=user_profile_id)
                              for user_profile_id in id_list]
            Subscription.objects.bulk_create(subs_to_create)
        return huddle

class UserActivity(models.Model):
    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    client: Client = models.ForeignKey(Client, on_delete=CASCADE)
    query: str = models.CharField(max_length=50, db_index=True)

    count: int = models.IntegerField()
    last_visit: datetime.datetime = models.DateTimeField('last visit')

    class Meta:
        unique_together = ("user_profile", "client", "query")

class UserActivityInterval(models.Model):
    MIN_INTERVAL_LENGTH = datetime.timedelta(minutes=15)

    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    start: datetime.datetime = models.DateTimeField('start time', db_index=True)
    end: datetime.datetime = models.DateTimeField('end time', db_index=True)


class UserPresence(models.Model):
    """A record from the last time we heard from a given user on a given client.

    This is a tricky subsystem, because it is highly optimized.  See the docs:
      https://zulip.readthedocs.io/en/latest/subsystems/presence.html
    """
    class Meta:
        unique_together = ("user_profile", "client")
        index_together = [
            ("realm", "timestamp")
        ]

    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    client: Client = models.ForeignKey(Client, on_delete=CASCADE)

    # The time we heard this update from the client.
    timestamp: datetime.datetime = models.DateTimeField('presence changed')

    # The user was actively using this Zulip client as of `timestamp` (i.e.,
    # they had interacted with the client recently).  When the timestamp is
    # itself recent, this is the green "active" status in the webapp.
    ACTIVE = 1

    # There had been no user activity (keyboard/mouse/etc.) on this client
    # recently.  So the client was online at the specified time, but it
    # could be the user's desktop which they were away from.  Displayed as
    # orange/idle if the timestamp is current.
    IDLE = 2

    # Information from the client about the user's recent interaction with
    # that client, as of `timestamp`.  Possible values above.
    #
    # There is no "inactive" status, because that is encoded by the
    # timestamp being old.
    status: int = models.PositiveSmallIntegerField(default=ACTIVE)

    @staticmethod
    def status_to_string(status: int) -> str:
        if status == UserPresence.ACTIVE:
            return 'active'
        elif status == UserPresence.IDLE:
            return 'idle'
        else:  # nocoverage # TODO: Add a presence test to cover this.
            raise ValueError('Unknown status: %s' % (status,))

    @staticmethod
    def to_presence_dict(client_name: str, status: int, dt: datetime.datetime, push_enabled: bool=False,
                         has_push_devices: bool=False) -> Dict[str, Any]:
        presence_val = UserPresence.status_to_string(status)

        timestamp = datetime_to_timestamp(dt)
        return dict(
            client=client_name,
            status=presence_val,
            timestamp=timestamp,
            pushable=(push_enabled and has_push_devices),
        )

    def to_dict(self) -> Dict[str, Any]:
        return UserPresence.to_presence_dict(
            self.client.name,
            self.status,
            self.timestamp
        )

    @staticmethod
    def status_from_string(status: str) -> Optional[int]:
        if status == 'active':
            status_val: Optional[int] = UserPresence.ACTIVE  # See https://github.com/python/mypy/issues/2611
        elif status == 'idle':
            status_val = UserPresence.IDLE
        else:
            status_val = None

        return status_val

class UserStatus(models.Model):
    user_profile: UserProfile = models.OneToOneField(UserProfile, on_delete=CASCADE)

    timestamp: datetime.datetime = models.DateTimeField()
    client: Client = models.ForeignKey(Client, on_delete=CASCADE)

    NORMAL = 0
    AWAY = 1

    status: int = models.PositiveSmallIntegerField(default=NORMAL)
    status_text: str = models.CharField(max_length=255, default='')

class DefaultStream(models.Model):
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    stream: Stream = models.ForeignKey(Stream, on_delete=CASCADE)

    class Meta:
        unique_together = ("realm", "stream")

class DefaultStreamGroup(models.Model):
    MAX_NAME_LENGTH = 60
    name: str = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    streams: Manager = models.ManyToManyField('Stream')
    description: str = models.CharField(max_length=1024, default='')

    class Meta:
        unique_together = ("realm", "name")

    def to_dict(self) -> Dict[str, Any]:
        return dict(name=self.name,
                    id=self.id,
                    description=self.description,
                    streams=[stream.to_dict() for stream in self.streams.all()])

def get_default_stream_groups(realm: Realm) -> List[DefaultStreamGroup]:
    return DefaultStreamGroup.objects.filter(realm=realm)

class AbstractScheduledJob(models.Model):
    scheduled_timestamp: datetime.datetime = models.DateTimeField(db_index=True)
    # JSON representation of arguments to consumer
    data: str = models.TextField()
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)

    class Meta:
        abstract = True

class ScheduledEmail(AbstractScheduledJob):
    # Exactly one of users or address should be set. These are
    # duplicate values, used to efficiently filter the set of
    # ScheduledEmails for use in clear_scheduled_emails; the
    # recipients used for actually sending messages are stored in the
    # data field of AbstractScheduledJob.
    users: Manager = models.ManyToManyField(UserProfile)
    # Just the address part of a full "name <address>" email address
    address: Optional[str] = models.EmailField(null=True, db_index=True)

    # Valid types are below
    WELCOME = 1
    DIGEST = 2
    INVITATION_REMINDER = 3
    type: int = models.PositiveSmallIntegerField()

    def __str__(self) -> str:
        return "<ScheduledEmail: %s %s %s>" % (self.type,
                                               self.address or list(self.users.all()),
                                               self.scheduled_timestamp)

class MissedMessageEmailAddress(models.Model):
    EXPIRY_SECONDS = 60 * 60 * 24 * 5
    ALLOWED_USES = 1

    message: Message = models.ForeignKey(Message, on_delete=CASCADE)
    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    email_token: str = models.CharField(max_length=34, unique=True, db_index=True)

    # Timestamp of when the missed message address generated.
    # The address is valid until timestamp + EXPIRY_SECONDS.
    timestamp: datetime.datetime = models.DateTimeField(db_index=True, default=timezone_now)
    times_used: int = models.PositiveIntegerField(default=0, db_index=True)

    def __str__(self) -> str:
        return settings.EMAIL_GATEWAY_PATTERN % (self.email_token,)

    def is_usable(self) -> bool:
        not_expired = timezone_now() <= self.timestamp + timedelta(seconds=self.EXPIRY_SECONDS)
        has_uses_left = self.times_used < self.ALLOWED_USES
        return has_uses_left and not_expired

    def increment_times_used(self) -> None:
        self.times_used += 1
        self.save(update_fields=["times_used"])

class ScheduledMessage(models.Model):
    sender: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    recipient: Recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    subject: str = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)
    content: str = models.TextField()
    sending_client: Client = models.ForeignKey(Client, on_delete=CASCADE)
    stream: Optional[Stream] = models.ForeignKey(Stream, null=True, on_delete=CASCADE)
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    scheduled_timestamp: datetime.datetime = models.DateTimeField(db_index=True)
    delivered: bool = models.BooleanField(default=False)

    SEND_LATER = 1
    REMIND = 2

    DELIVERY_TYPES = (
        (SEND_LATER, 'send_later'),
        (REMIND, 'remind'),
    )

    delivery_type: int = models.PositiveSmallIntegerField(
        choices=DELIVERY_TYPES, default=SEND_LATER
    )

    def topic_name(self) -> str:
        return self.subject

    def set_topic_name(self, topic_name: str) -> None:
        self.subject = topic_name

    def __str__(self) -> str:
        display_recipient = get_display_recipient(self.recipient)
        return "<ScheduledMessage: %s %s %s %s>" % (display_recipient,
                                                    self.subject, self.sender,
                                                    self.scheduled_timestamp)

EMAIL_TYPES = {
    'followup_day1': ScheduledEmail.WELCOME,
    'followup_day2': ScheduledEmail.WELCOME,
    'digest': ScheduledEmail.DIGEST,
    'invitation_reminder': ScheduledEmail.INVITATION_REMINDER,
}

class AbstractRealmAuditLog(models.Model):
    """Defines fields common to RealmAuditLog and RemoteRealmAuditLog."""
    event_time: datetime.datetime = models.DateTimeField(db_index=True)
    # If True, event_time is an overestimate of the true time. Can be used
    # by migrations when introducing a new event_type.
    backfilled: bool = models.BooleanField(default=False)

    # Keys within extra_data, when extra_data is a json dict. Keys are strings because
    # json keys must always be strings.
    OLD_VALUE = '1'
    NEW_VALUE = '2'
    ROLE_COUNT = '10'
    ROLE_COUNT_HUMANS = '11'
    ROLE_COUNT_BOTS = '12'

    extra_data: Optional[str] = models.TextField(null=True)

    # Event types
    USER_CREATED = 101
    USER_ACTIVATED = 102
    USER_DEACTIVATED = 103
    USER_REACTIVATED = 104
    USER_ROLE_CHANGED = 105

    USER_SOFT_ACTIVATED = 120
    USER_SOFT_DEACTIVATED = 121
    USER_PASSWORD_CHANGED = 122
    USER_AVATAR_SOURCE_CHANGED = 123
    USER_FULL_NAME_CHANGED = 124
    USER_EMAIL_CHANGED = 125
    USER_TOS_VERSION_CHANGED = 126
    USER_API_KEY_CHANGED = 127
    USER_BOT_OWNER_CHANGED = 128

    REALM_DEACTIVATED = 201
    REALM_REACTIVATED = 202
    REALM_SCRUBBED = 203
    REALM_PLAN_TYPE_CHANGED = 204
    REALM_LOGO_CHANGED = 205
    REALM_EXPORTED = 206

    SUBSCRIPTION_CREATED = 301
    SUBSCRIPTION_ACTIVATED = 302
    SUBSCRIPTION_DEACTIVATED = 303

    STRIPE_CUSTOMER_CREATED = 401
    STRIPE_CARD_CHANGED = 402
    STRIPE_PLAN_CHANGED = 403
    STRIPE_PLAN_QUANTITY_RESET = 404

    CUSTOMER_CREATED = 501
    CUSTOMER_PLAN_CREATED = 502

    event_type: int = models.PositiveSmallIntegerField()

    # event_types synced from on-prem installations to zulipchat.com when
    # billing for mobile push notifications is enabled.  Every billing
    # event_type should have ROLE_COUNT populated in extra_data.
    SYNCED_BILLING_EVENTS = [
        USER_CREATED, USER_ACTIVATED, USER_DEACTIVATED, USER_REACTIVATED, USER_ROLE_CHANGED,
        REALM_DEACTIVATED, REALM_REACTIVATED]

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

    For example:
    * When a user subscribes another user to a stream, modified_user,
      acting_user, and modified_stream will all be present and different.
    * When an administrator changes an organization's realm icon,
      acting_user is that administrator and both modified_user and
      modified_stream will be None.
    """
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    acting_user: Optional[UserProfile] = models.ForeignKey(
        UserProfile, null=True, related_name="+", on_delete=CASCADE
    )
    modified_user: Optional[UserProfile] = models.ForeignKey(
        UserProfile, null=True, related_name="+", on_delete=CASCADE
    )
    modified_stream: Optional[Stream] = models.ForeignKey(
        Stream, null=True, on_delete=CASCADE
    )
    event_last_message_id: Optional[int] = models.IntegerField(null=True)

    def __str__(self) -> str:
        if self.modified_user is not None:
            return "<RealmAuditLog: %s %s %s %s>" % (
                self.modified_user, self.event_type, self.event_time, self.id)
        if self.modified_stream is not None:
            return "<RealmAuditLog: %s %s %s %s>" % (
                self.modified_stream, self.event_type, self.event_time, self.id)
        return "<RealmAuditLog: %s %s %s %s>" % (
            self.realm, self.event_type, self.event_time, self.id)

class UserHotspot(models.Model):
    user: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    hotspot: str = models.CharField(max_length=30)
    timestamp: datetime.datetime = models.DateTimeField(default=timezone_now)

    class Meta:
        unique_together = ("user", "hotspot")

def check_valid_user_ids(realm_id: int, user_ids: List[int],
                         allow_deactivated: bool=False) -> Optional[str]:
    error = check_list(check_int)("User IDs", user_ids)
    if error:
        return error
    realm = Realm.objects.get(id=realm_id)
    for user_id in user_ids:
        # TODO: Structurally, we should be doing a bulk fetch query to
        # get the users here, not doing these in a loop.  But because
        # this is a rarely used feature and likely to never have more
        # than a handful of users, it's probably mostly OK.
        try:
            user_profile = get_user_profile_by_id_in_realm(user_id, realm)
        except UserProfile.DoesNotExist:
            return _('Invalid user ID: %d') % (user_id)

        if not allow_deactivated:
            if not user_profile.is_active:
                return _('User with ID %d is deactivated') % (user_id)

        if (user_profile.is_bot):
            return _('User with ID %d is a bot') % (user_id)

    return None

class CustomProfileField(models.Model):
    """Defines a form field for the per-realm custom profile fields feature.

    See CustomProfileFieldValue for an individual user's values for one of
    these fields.
    """
    HINT_MAX_LENGTH = 80
    NAME_MAX_LENGTH = 40

    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    name: str = models.CharField(max_length=NAME_MAX_LENGTH)
    hint: Optional[str] = models.CharField(max_length=HINT_MAX_LENGTH, default='', null=True)
    order: int = models.IntegerField(default=0)

    SHORT_TEXT = 1
    LONG_TEXT = 2
    CHOICE = 3
    DATE = 4
    URL = 5
    USER = 6
    EXTERNAL_ACCOUNT = 7

    # These are the fields whose validators require more than var_name
    # and value argument. i.e. CHOICE require field_data, USER require
    # realm as argument.
    CHOICE_FIELD_TYPE_DATA: List[ExtendedFieldElement] = [
        (CHOICE, str(_('List of options')), validate_choice_field, str, "CHOICE"),
    ]
    USER_FIELD_TYPE_DATA: List[UserFieldElement] = [
        (USER, str(_('Person picker')), check_valid_user_ids, eval, "USER"),
    ]

    CHOICE_FIELD_VALIDATORS: Dict[int, ExtendedValidator] = {
        item[0]: item[2] for item in CHOICE_FIELD_TYPE_DATA
    }
    USER_FIELD_VALIDATORS: Dict[int, RealmUserValidator] = {
        item[0]: item[2] for item in USER_FIELD_TYPE_DATA
    }

    FIELD_TYPE_DATA: List[FieldElement] = [
        # Type, Display Name, Validator, Converter, Keyword
        (SHORT_TEXT, str(_('Short text')), check_short_string, str, "SHORT_TEXT"),
        (LONG_TEXT, str(_('Long text')), check_long_string, str, "LONG_TEXT"),
        (DATE, str(_('Date picker')), check_date, str, "DATE"),
        (URL, str(_('Link')), check_url, str, "URL"),
        (EXTERNAL_ACCOUNT, str(_('External account')), check_short_string, str, "EXTERNAL_ACCOUNT"),
    ]

    ALL_FIELD_TYPES = [*FIELD_TYPE_DATA, *CHOICE_FIELD_TYPE_DATA, *USER_FIELD_TYPE_DATA]

    FIELD_VALIDATORS: Dict[int, Validator] = {item[0]: item[2] for item in FIELD_TYPE_DATA}
    FIELD_CONVERTERS: Dict[int, Callable[[Any], Any]] = {item[0]: item[3] for item in ALL_FIELD_TYPES}
    FIELD_TYPE_CHOICES: List[Tuple[int, str]] = [(item[0], item[1]) for item in ALL_FIELD_TYPES]
    FIELD_TYPE_CHOICES_DICT: Dict[str, Dict[str, Union[str, int]]] = {
        item[4]: {"id": item[0], "name": item[1]} for item in ALL_FIELD_TYPES
    }

    field_type: int = models.PositiveSmallIntegerField(
        choices=FIELD_TYPE_CHOICES, default=SHORT_TEXT
    )

    # A JSON blob of any additional data needed to define the field beyond
    # type/name/hint.
    #
    # The format depends on the type.  Field types SHORT_TEXT, LONG_TEXT,
    # DATE, URL, and USER leave this null.  Fields of type CHOICE store the
    # choices' descriptions.
    #
    # Note: There is no performance overhead of using TextField in PostgreSQL.
    # See https://www.postgresql.org/docs/9.0/static/datatype-character.html
    field_data: Optional[str] = models.TextField(default='', null=True)

    class Meta:
        unique_together = ('realm', 'name')

    def as_dict(self) -> ProfileDataElement:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.field_type,
            'hint': self.hint,
            'field_data': self.field_data,
            'order': self.order,
        }

    def is_renderable(self) -> bool:
        if self.field_type in [CustomProfileField.SHORT_TEXT, CustomProfileField.LONG_TEXT]:
            return True
        return False

    def __str__(self) -> str:
        return "<CustomProfileField: %s %s %s %d>" % (self.realm, self.name, self.field_type, self.order)

def custom_profile_fields_for_realm(realm_id: int) -> List[CustomProfileField]:
    return CustomProfileField.objects.filter(realm=realm_id).order_by('order')

class CustomProfileFieldValue(models.Model):
    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    field: CustomProfileField = models.ForeignKey(CustomProfileField, on_delete=CASCADE)
    value: str = models.TextField()
    rendered_value: Optional[str] = models.TextField(null=True, default=None)

    class Meta:
        unique_together = ('user_profile', 'field')

    def __str__(self) -> str:
        return "<CustomProfileFieldValue: %s %s %s>" % (self.user_profile, self.field, self.value)

# Interfaces for services
# They provide additional functionality like parsing message to obtain query url, data to be sent to url,
# and parsing the response.
GENERIC_INTERFACE = 'GenericService'
SLACK_INTERFACE = 'SlackOutgoingWebhookService'

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
    name: str = models.CharField(max_length=UserProfile.MAX_NAME_LENGTH)
    # Bot user corresponding to the Service.  The bot_type of this user
    # deterines the type of service.  If non-bot services are added later,
    # user_profile can also represent the owner of the Service.
    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    base_url: str = models.TextField()
    token: str = models.TextField()
    # Interface / API version of the service.
    interface: int = models.PositiveSmallIntegerField(default=1)

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


def get_bot_services(user_profile_id: str) -> List[Service]:
    return list(Service.objects.filter(user_profile__id=user_profile_id))

def get_service_profile(user_profile_id: str, service_name: str) -> Service:
    return Service.objects.get(user_profile__id=user_profile_id, name=service_name)


class BotStorageData(models.Model):
    bot_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    key: str = models.TextField(db_index=True)
    value: str = models.TextField()

    class Meta:
        unique_together = ("bot_profile", "key")

class BotConfigData(models.Model):
    bot_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    key: str = models.TextField(db_index=True)
    value: str = models.TextField()

    class Meta:
        unique_together = ("bot_profile", "key")

class InvalidFakeEmailDomain(Exception):
    pass

def get_fake_email_domain() -> str:
    try:
        # Check that the fake email domain can be used to form valid email addresses.
        validate_email("bot@" + settings.FAKE_EMAIL_DOMAIN)
    except ValidationError:
        raise InvalidFakeEmailDomain(settings.FAKE_EMAIL_DOMAIN + ' is not a valid domain.')

    return settings.FAKE_EMAIL_DOMAIN

class AlertWord(models.Model):
    # Realm isn't necessary, but it's a nice denormalization.  Users
    # never move to another realm, so it's static, and having Realm
    # here optimizes the main query on this table, which is fetching
    # all the alert words in a realm.
    realm: Realm = models.ForeignKey(Realm, db_index=True, on_delete=CASCADE)
    user_profile: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    # Case-insensitive name for the alert word.
    word: str = models.TextField()

    class Meta:
        unique_together = ("user_profile", "word")

def flush_realm_alert_words(realm: Realm) -> None:
    cache_delete(realm_alert_words_cache_key(realm))
    cache_delete(realm_alert_words_automaton_cache_key(realm))

def flush_alert_word(sender: Any, **kwargs: Any) -> None:
    realm = kwargs['instance'].realm
    flush_realm_alert_words(realm)

post_save.connect(flush_alert_word, sender=AlertWord)
post_delete.connect(flush_alert_word, sender=AlertWord)
