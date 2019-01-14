from typing import Any, DefaultDict, Dict, List, Set, Tuple, TypeVar, \
    Union, Optional, Sequence, AbstractSet, Callable, Iterable
from typing.re import Match

from django.db import models
from django.db.models.query import QuerySet
from django.db.models import Manager, Sum, CASCADE
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, UserManager, \
    PermissionsMixin
import django.contrib.auth
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, MinLengthValidator, \
    RegexValidator
from django.dispatch import receiver
from zerver.lib.cache import cache_with_key, flush_user_profile, flush_realm, \
    user_profile_by_api_key_cache_key, active_non_guest_user_ids_cache_key, \
    user_profile_by_id_cache_key, user_profile_by_email_cache_key, \
    user_profile_cache_key, generic_bulk_cached_fetch, cache_set, flush_stream, \
    display_recipient_cache_key, cache_delete, active_user_ids_cache_key, \
    get_stream_cache_key, realm_user_dicts_cache_key, \
    bot_dicts_in_realm_cache_key, realm_user_dict_fields, \
    bot_dict_fields, flush_message, flush_submessage, bot_profile_cache_key, \
    flush_used_upload_space_cache, get_realm_used_upload_space_cache_key
from zerver.lib.utils import make_safe_digest, generate_random_token
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.contrib.sessions.models import Session
from zerver.lib.timestamp import datetime_to_timestamp
from django.db.models.signals import pre_save, post_save, post_delete
from django.utils.translation import ugettext_lazy as _
from zerver.lib import cache
from zerver.lib.validator import check_int, \
    check_short_string, check_long_string, validate_choice_field, check_date, \
    check_url, check_list
from zerver.lib.name_restrictions import is_disposable_domain
from zerver.lib.types import Validator, ExtendedValidator, \
    ProfileDataElement, ProfileData, FieldTypeData, \
    RealmUserValidator

from bitfield import BitField
from bitfield.types import BitHandler
from collections import defaultdict, OrderedDict
from datetime import timedelta
import pylibmc
import re
import sre_constants
import time
import datetime

MAX_TOPIC_NAME_LENGTH = 60
MAX_MESSAGE_LENGTH = 10000
MAX_LANGUAGE_ID_LENGTH = 50  # type: int

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
per_request_display_recipient_cache = {}  # type: Dict[int, Union[str, List[Dict[str, Any]]]]
def get_display_recipient_by_id(recipient_id: int, recipient_type: int,
                                recipient_type_id: Optional[int]) -> Union[str, List[Dict[str, Any]]]:
    """
    returns: an object describing the recipient (using a cache).
    If the type is a stream, the type_id must be an int; a string is returned.
    Otherwise, type_id may be None; an array of recipient dicts is returned.
    """
    if recipient_id not in per_request_display_recipient_cache:
        result = get_display_recipient_remote_cache(recipient_id, recipient_type, recipient_type_id)
        per_request_display_recipient_cache[recipient_id] = result
    return per_request_display_recipient_cache[recipient_id]

def get_display_recipient(recipient: 'Recipient') -> Union[str, List[Dict[str, Any]]]:
    return get_display_recipient_by_id(
        recipient.id,
        recipient.type,
        recipient.type_id
    )

def flush_per_request_caches() -> None:
    global per_request_display_recipient_cache
    per_request_display_recipient_cache = {}
    global per_request_realm_filters_cache
    per_request_realm_filters_cache = {}

DisplayRecipientCacheT = Union[str, List[Dict[str, Any]]]
@cache_with_key(lambda *args: display_recipient_cache_key(args[0]),
                timeout=3600*24*7)
def get_display_recipient_remote_cache(recipient_id: int, recipient_type: int,
                                       recipient_type_id: Optional[int]) -> DisplayRecipientCacheT:
    """
    returns: an appropriate object describing the recipient.  For a
    stream this will be the stream name as a string.  For a huddle or
    personal, it will be an array of dicts about each recipient.
    """
    if recipient_type == Recipient.STREAM:
        assert recipient_type_id is not None
        stream = Stream.objects.get(id=recipient_type_id)
        return stream.name

    # The main priority for ordering here is being deterministic.
    # Right now, we order by ID, which matches the ordering of user
    # names in the left sidebar.
    user_profile_list = (UserProfile.objects.filter(subscription__recipient_id=recipient_id)
                                            .select_related()
                                            .order_by('id'))
    return [{'email': user_profile.email,
             'full_name': user_profile.full_name,
             'short_name': user_profile.short_name,
             'id': user_profile.id,
             'is_mirror_dummy': user_profile.is_mirror_dummy} for user_profile in user_profile_list]

def get_realm_emoji_cache_key(realm: 'Realm') -> str:
    return u'realm_emoji:%s' % (realm.id,)

def get_active_realm_emoji_cache_key(realm: 'Realm') -> str:
    return u'active_realm_emoji:%s' % (realm.id,)

class Realm(models.Model):
    MAX_REALM_NAME_LENGTH = 40
    MAX_REALM_SUBDOMAIN_LENGTH = 40
    MAX_VIDEO_CHAT_PROVIDER_LENGTH = 40
    MAX_GOOGLE_HANGOUTS_DOMAIN_LENGTH = 255  # This is just the maximum domain length by RFC
    INVITES_STANDARD_REALM_DAILY_MAX = 3000
    MESSAGE_VISIBILITY_LIMITED = 10000
    VIDEO_CHAT_PROVIDERS = [u"Jitsi", u"Google Hangouts", u"Zoom"]
    AUTHENTICATION_FLAGS = [u'Google', u'Email', u'GitHub', u'LDAP', u'Dev', u'RemoteUser', u'AzureAD']
    SUBDOMAIN_FOR_ROOT_DOMAIN = ''

    # User-visible display name and description used on e.g. the organization homepage
    name = models.CharField(max_length=MAX_REALM_NAME_LENGTH, null=True)  # type: Optional[str]
    description = models.TextField(default=u"")  # type: str

    # A short, identifier-like name for the organization.  Used in subdomains;
    # e.g. on a server at example.com, an org with string_id `foo` is reached
    # at `foo.example.com`.
    string_id = models.CharField(max_length=MAX_REALM_SUBDOMAIN_LENGTH, unique=True)  # type: str

    date_created = models.DateTimeField(default=timezone_now)  # type: datetime.datetime
    deactivated = models.BooleanField(default=False)  # type: bool

    # See RealmDomain for the domains that apply for a given organization.
    emails_restricted_to_domains = models.BooleanField(default=False)  # type: bool

    invite_required = models.BooleanField(default=True)  # type: bool
    invite_by_admins_only = models.BooleanField(default=False)  # type: bool
    _max_invites = models.IntegerField(null=True, db_column='max_invites')  # type: Optional[int]
    disallow_disposable_email_addresses = models.BooleanField(default=True)  # type: bool
    authentication_methods = BitField(flags=AUTHENTICATION_FLAGS,
                                      default=2**31 - 1)  # type: BitHandler

    # Whether the organization has enabled inline image and URL previews.
    inline_image_preview = models.BooleanField(default=True)  # type: bool
    inline_url_embed_preview = models.BooleanField(default=True)  # type: bool

    # Whether digest emails are enabled for the organization.
    digest_emails_enabled = models.BooleanField(default=True)  # type: bool

    send_welcome_emails = models.BooleanField(default=True)  # type: bool
    message_content_allowed_in_email_notifications = models.BooleanField(default=True)  # type: bool

    mandatory_topics = models.BooleanField(default=False)  # type: bool
    create_stream_by_admins_only = models.BooleanField(default=False)  # type: bool
    add_emoji_by_admins_only = models.BooleanField(default=False)  # type: bool
    name_changes_disabled = models.BooleanField(default=False)  # type: bool
    email_changes_disabled = models.BooleanField(default=False)  # type: bool

    # Who in the organization has access to users' actual email
    # addresses.  Controls whether the UserProfile.email field is the
    # same as UserProfile.delivery_email, or is instead garbage.
    EMAIL_ADDRESS_VISIBILITY_EVERYONE = 1
    EMAIL_ADDRESS_VISIBILITY_MEMBERS = 2
    EMAIL_ADDRESS_VISIBILITY_ADMINS = 3
    email_address_visibility = models.PositiveSmallIntegerField(default=EMAIL_ADDRESS_VISIBILITY_EVERYONE)  # type: int
    EMAIL_ADDRESS_VISIBILITY_TYPES = [
        EMAIL_ADDRESS_VISIBILITY_EVERYONE,
        # The MEMBERS level is not yet implemented on the backend.
        ## EMAIL_ADDRESS_VISIBILITY_MEMBERS,
        EMAIL_ADDRESS_VISIBILITY_ADMINS,
    ]

    # Threshold in days for new users to create streams, and potentially take
    # some other actions.
    waiting_period_threshold = models.PositiveIntegerField(default=0)  # type: int

    allow_message_deleting = models.BooleanField(default=False)  # type: bool
    DEFAULT_MESSAGE_CONTENT_DELETE_LIMIT_SECONDS = 600  # if changed, also change in admin.js, setting_org.js
    message_content_delete_limit_seconds = models.IntegerField(default=DEFAULT_MESSAGE_CONTENT_DELETE_LIMIT_SECONDS)  # type: int

    allow_message_editing = models.BooleanField(default=True)  # type: bool
    DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS = 600  # if changed, also change in admin.js, setting_org.js
    message_content_edit_limit_seconds = models.IntegerField(default=DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS)  # type: int

    # Whether users have access to message edit history
    allow_edit_history = models.BooleanField(default=True)  # type: bool

    DEFAULT_COMMUNITY_TOPIC_EDITING_LIMIT_SECONDS = 86400
    allow_community_topic_editing = models.BooleanField(default=True)  # type: bool

    # Defaults for new users
    default_twenty_four_hour_time = models.BooleanField(default=False)  # type: bool
    default_language = models.CharField(default=u'en', max_length=MAX_LANGUAGE_ID_LENGTH)  # type: str

    DEFAULT_NOTIFICATION_STREAM_NAME = u'announce'
    INITIAL_PRIVATE_STREAM_NAME = u'core team'
    notifications_stream = models.ForeignKey('Stream', related_name='+', null=True, blank=True, on_delete=CASCADE)  # type: Optional[Stream]
    signup_notifications_stream = models.ForeignKey('Stream', related_name='+', null=True, blank=True, on_delete=CASCADE)  # type: Optional[Stream]

    # For old messages being automatically deleted
    message_retention_days = models.IntegerField(null=True)  # type: Optional[int]

    # When non-null, all but the latest this many messages in the organization
    # are inaccessible to users (but not deleted).
    message_visibility_limit = models.IntegerField(null=True)  # type: Optional[int]

    # Messages older than this message ID in the organization are inaccessible.
    first_visible_message_id = models.IntegerField(default=0)  # type: int

    # Valid org_types are {CORPORATE, COMMUNITY}
    CORPORATE = 1
    COMMUNITY = 2
    org_type = models.PositiveSmallIntegerField(default=CORPORATE)  # type: int

    # plan_type controls various features around resource/feature
    # limitations for a Zulip organization on multi-tenant servers
    # like zulipchat.com.
    SELF_HOSTED = 1
    LIMITED = 2
    STANDARD = 3
    STANDARD_FREE = 4
    plan_type = models.PositiveSmallIntegerField(default=SELF_HOSTED)  # type: int

    # This value is also being used in static/js/settings_bots.bot_creation_policy_values.
    # On updating it here, update it there as well.
    BOT_CREATION_EVERYONE = 1
    BOT_CREATION_LIMIT_GENERIC_BOTS = 2
    BOT_CREATION_ADMINS_ONLY = 3
    bot_creation_policy = models.PositiveSmallIntegerField(default=BOT_CREATION_EVERYONE)  # type: int

    # See upload_quota_bytes; don't interpret upload_quota_gb directly.
    UPLOAD_QUOTA_LIMITED = 5
    UPLOAD_QUOTA_STANDARD = 50
    upload_quota_gb = models.IntegerField(null=True)  # type: Optional[int]

    video_chat_provider = models.CharField(default=u"Jitsi", max_length=MAX_VIDEO_CHAT_PROVIDER_LENGTH)
    google_hangouts_domain = models.TextField(default="")
    zoom_user_id = models.TextField(default="")
    zoom_api_key = models.TextField(default="")
    zoom_api_secret = models.TextField(default="")

    # Define the types of the various automatically managed properties
    property_types = dict(
        add_emoji_by_admins_only=bool,
        allow_edit_history=bool,
        allow_message_deleting=bool,
        bot_creation_policy=int,
        create_stream_by_admins_only=bool,
        default_language=str,
        default_twenty_four_hour_time = bool,
        description=str,
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
        emails_restricted_to_domains=bool,
        send_welcome_emails=bool,
        message_content_allowed_in_email_notifications=bool,
        video_chat_provider=str,
        waiting_period_threshold=int,
    )  # type: Dict[str, Union[type, Tuple[type, ...]]]

    # Icon is the square mobile icon.
    ICON_FROM_GRAVATAR = u'G'
    ICON_UPLOADED = u'U'
    ICON_SOURCES = (
        (ICON_FROM_GRAVATAR, 'Hosted by Gravatar'),
        (ICON_UPLOADED, 'Uploaded by administrator'),
    )
    icon_source = models.CharField(default=ICON_FROM_GRAVATAR, choices=ICON_SOURCES,
                                   max_length=1)  # type: str
    icon_version = models.PositiveSmallIntegerField(default=1)  # type: int

    # Logo is the horizonal logo we show in top-left of webapp navbar UI.
    LOGO_DEFAULT = u'D'
    LOGO_UPLOADED = u'U'
    LOGO_SOURCES = (
        (LOGO_DEFAULT, 'Default to Zulip'),
        (LOGO_UPLOADED, 'Uploaded by administrator'),
    )
    logo_source = models.CharField(default=LOGO_DEFAULT, choices=LOGO_SOURCES,
                                   max_length=1)  # type: str
    logo_version = models.PositiveSmallIntegerField(default=1)  # type: int

    night_logo_source = models.CharField(default=LOGO_DEFAULT, choices=LOGO_SOURCES,
                                         max_length=1)  # type: str
    night_logo_version = models.PositiveSmallIntegerField(default=1)  # type: int

    BOT_CREATION_POLICY_TYPES = [
        BOT_CREATION_EVERYONE,
        BOT_CREATION_LIMIT_GENERIC_BOTS,
        BOT_CREATION_ADMINS_ONLY,
    ]

    def authentication_methods_dict(self) -> Dict[str, bool]:
        """Returns the a mapping from authentication flags to their status,
        showing only those authentication flags that are supported on
        the current server (i.e. if EmailAuthBackend is not configured
        on the server, this will not return an entry for "Email")."""
        # This mapping needs to be imported from here due to the cyclic
        # dependency.
        from zproject.backends import AUTH_BACKEND_NAME_MAP

        ret = {}  # type: Dict[str, bool]
        supported_backends = {backend.__class__ for backend in django.contrib.auth.get_backends()}
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

    def get_admin_users(self) -> Sequence['UserProfile']:
        # TODO: Change return type to QuerySet[UserProfile]
        return UserProfile.objects.filter(realm=self, is_realm_admin=True,
                                          is_active=True)

    def get_active_users(self) -> Sequence['UserProfile']:
        # TODO: Change return type to QuerySet[UserProfile]
        return UserProfile.objects.filter(realm=self, is_active=True).select_related()

    def get_bot_domain(self) -> str:
        # Remove the port. Mainly needed for development environment.
        return self.host.split(':')[0]

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
    def max_invites(self, value: int) -> None:
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
    return Realm.objects.filter(string_id=string_id).first()

def name_changes_disabled(realm: Optional[Realm]) -> bool:
    if realm is None:
        return settings.NAME_CHANGES_DISABLED
    return settings.NAME_CHANGES_DISABLED or realm.name_changes_disabled

class RealmDomain(models.Model):
    """For an organization with emails_restricted_to_domains enabled, the list of
    allowed domains"""
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    # should always be stored lowercase
    domain = models.CharField(max_length=80, db_index=True)  # type: str
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

# Is a user with the given email address allowed to be in the given realm?
# (This function does not check whether the user has been invited to the realm.
# So for invite-only realms, this is the test for whether a user can be invited,
# not whether the user can sign up currently.)
def email_allowed_for_realm(email: str, realm: Realm) -> None:
    if not realm.emails_restricted_to_domains:
        if realm.disallow_disposable_email_addresses and \
                is_disposable_domain(email_to_domain(email)):
            raise DisposableEmailError
        return
    elif '+' in email_to_username(email):
        raise EmailContainsPlusError

    domain = email_to_domain(email)
    query = RealmDomain.objects.filter(realm=realm)
    if query.filter(domain=domain).exists():
        return
    else:
        query = query.filter(allow_subdomains=True)
        while len(domain) > 0:
            subdomain, sep, domain = domain.partition('.')
            if query.filter(domain=domain).exists():
                return
    raise DomainNotAllowedForRealmError

def get_realm_domains(realm: Realm) -> List[Dict[str, str]]:
    return list(realm.realmdomain_set.values('domain', 'allow_subdomains'))

class RealmEmoji(models.Model):
    author = models.ForeignKey('UserProfile', blank=True, null=True, on_delete=CASCADE)  # type: Optional[UserProfile]
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    name = models.TextField(validators=[
        MinLengthValidator(1),
        # The second part of the regex (negative lookbehind) disallows names
        # ending with one of the punctuation characters.
        RegexValidator(regex=r'^[0-9a-z.\-_]+(?<![.\-_])$',
                       message=_("Invalid characters in emoji name"))])  # type: str

    # The basename of the custom emoji's filename; see PATH_ID_TEMPLATE for the full path.
    file_name = models.TextField(db_index=True, null=True, blank=True)  # type: Optional[str]

    deactivated = models.BooleanField(default=False)  # type: bool

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
    error_msg = _('Invalid filter pattern.  Valid characters are %s.' % (
        '[ a-zA-Z_#=/:+!-]',))

    if not regex.match(str(value)):
        raise ValidationError(error_msg)

    try:
        re.compile(value)
    except sre_constants.error:
        # Regex is invalid
        raise ValidationError(error_msg)

def filter_format_validator(value: str) -> None:
    regex = re.compile(r'^([\.\/:a-zA-Z0-9#_?=-]+%\(([a-zA-Z0-9_-]+)\)s)+[a-zA-Z0-9_-]*$')

    if not regex.match(value):
        raise ValidationError(_('Invalid URL format string.'))

class RealmFilter(models.Model):
    """Realm-specific regular expressions to automatically linkify certain
    strings inside the markdown processor.  See "Custom filters" in the settings UI.
    """
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    pattern = models.TextField(validators=[filter_pattern_validator])  # type: str
    url_format_string = models.TextField(validators=[URLValidator(), filter_format_validator])  # type: str

    class Meta:
        unique_together = ("realm", "pattern")

    def __str__(self) -> str:
        return "<RealmFilter(%s): %s %s>" % (self.realm.string_id, self.pattern, self.url_format_string)

def get_realm_filters_cache_key(realm_id: int) -> str:
    return u'%s:all_realm_filters:%s' % (cache.KEY_PREFIX, realm_id,)

# We have a per-process cache to avoid doing 1000 remote cache queries during page load
per_request_realm_filters_cache = {}  # type: Dict[int, List[Tuple[str, str, int]]]

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
    filters = defaultdict(list)  # type: DefaultDict[int, List[Tuple[str, str, int]]]
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

class UserProfile(AbstractBaseUser, PermissionsMixin):
    USERNAME_FIELD = 'email'
    MAX_NAME_LENGTH = 100
    MIN_NAME_LENGTH = 2
    API_KEY_LENGTH = 32
    NAME_INVALID_CHARS = ['*', '`', '>', '"', '@']

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

    # The display email address, used for Zulip APIs, etc.  This field
    # should never be used for actually emailing someone because it
    # will be invalid for various values of
    # Realm.email_address_visibility; for that, see delivery_email.
    email = models.EmailField(blank=False, db_index=True)  # type: str

    # delivery_email is just used for sending emails.  In almost all
    # organizations, it matches `email`; this field is part of our
    # transition towards supporting organizations where email
    # addresses are not public.
    delivery_email = models.EmailField(blank=False, db_index=True)  # type: str

    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm

    full_name = models.CharField(max_length=MAX_NAME_LENGTH)  # type: str

    # short_name is currently unused.
    short_name = models.CharField(max_length=MAX_NAME_LENGTH)  # type: str

    date_joined = models.DateTimeField(default=timezone_now)  # type: datetime.datetime
    tos_version = models.CharField(null=True, max_length=10)  # type: Optional[str]
    api_key = models.CharField(max_length=API_KEY_LENGTH)  # type: str

    # pointer points to Message.id, NOT UserMessage.id.
    pointer = models.IntegerField()  # type: int

    last_pointer_updater = models.CharField(max_length=64)  # type: str

    # Whether the user has access to server-level administrator pages, like /activity
    is_staff = models.BooleanField(default=False)  # type: bool

    # For a normal user, this is True unless the user or an admin has
    # deactivated their account.  The name comes from Django; this field
    # isn't related to presence or to whether the user has recently used Zulip.
    #
    # See also `long_term_idle`.
    is_active = models.BooleanField(default=True, db_index=True)  # type: bool

    is_realm_admin = models.BooleanField(default=False, db_index=True)  # type: bool
    is_billing_admin = models.BooleanField(default=False, db_index=True)  # type: bool

    # Guest users are limited users without default access to public streams (etc.)
    is_guest = models.BooleanField(default=False, db_index=True)  # type: bool

    is_bot = models.BooleanField(default=False, db_index=True)  # type: bool
    bot_type = models.PositiveSmallIntegerField(null=True, db_index=True)  # type: Optional[int]
    bot_owner = models.ForeignKey('self', null=True, on_delete=models.SET_NULL)  # type: Optional[UserProfile]

    # Whether the user has been "soft-deactivated" due to weeks of inactivity.
    # For these users we avoid doing UserMessage table work, as an optimization
    # for large Zulip organizations with lots of single-visit users.
    long_term_idle = models.BooleanField(default=False, db_index=True)  # type: bool

    # When we last added basic UserMessage rows for a long_term_idle user.
    last_active_message_id = models.IntegerField(null=True)  # type: Optional[int]

    # Mirror dummies are fake (!is_active) users used to provide
    # message senders in our cross-protocol Zephyr<->Zulip content
    # mirroring integration, so that we can display mirrored content
    # like native Zulip messages (with a name + avatar, etc.).
    is_mirror_dummy = models.BooleanField(default=False)  # type: bool

    # API super users are allowed to forge messages as sent by another
    # user; also used for Zephyr/Jabber mirroring.
    is_api_super_user = models.BooleanField(default=False, db_index=True)  # type: bool

    ### Notifications settings. ###

    # Stream notifications.
    enable_stream_desktop_notifications = models.BooleanField(default=False)  # type: bool
    enable_stream_email_notifications = models.BooleanField(default=False)  # type: bool
    enable_stream_push_notifications = models.BooleanField(default=False)  # type: bool
    enable_stream_sounds = models.BooleanField(default=False)  # type: bool
    notification_sound = models.CharField(max_length=20, default='zulip')  # type: str

    # PM + @-mention notifications.
    enable_desktop_notifications = models.BooleanField(default=True)  # type: bool
    pm_content_in_desktop_notifications = models.BooleanField(default=True)  # type: bool
    enable_sounds = models.BooleanField(default=True)  # type: bool
    enable_offline_email_notifications = models.BooleanField(default=True)  # type: bool
    message_content_in_email_notifications = models.BooleanField(default=True)  # type: bool
    enable_offline_push_notifications = models.BooleanField(default=True)  # type: bool
    enable_online_push_notifications = models.BooleanField(default=False)  # type: bool

    enable_digest_emails = models.BooleanField(default=True)  # type: bool
    enable_login_emails = models.BooleanField(default=True)  # type: bool
    realm_name_in_notifications = models.BooleanField(default=False)  # type: bool

    # Words that trigger a mention for this user, formatted as a json-serialized list of strings
    alert_words = models.TextField(default=u'[]')  # type: str

    # Used for rate-limiting certain automated messages generated by bots
    last_reminder = models.DateTimeField(default=None, null=True)  # type: Optional[datetime.datetime]

    # Minutes to wait before warning a bot owner that their bot sent a message
    # to a nonexistent stream
    BOT_OWNER_STREAM_ALERT_WAITPERIOD = 1

    # API rate limits, formatted as a comma-separated list of range:max pairs
    rate_limits = models.CharField(default=u"", max_length=100)  # type: str

    # Hours to wait before sending another email to a user
    EMAIL_REMINDER_WAITPERIOD = 24

    # Default streams for some deprecated/legacy classes of bot users.
    default_sending_stream = models.ForeignKey('zerver.Stream', null=True, related_name='+', on_delete=CASCADE)  # type: Optional[Stream]
    default_events_register_stream = models.ForeignKey('zerver.Stream', null=True, related_name='+', on_delete=CASCADE)  # type: Optional[Stream]
    default_all_public_streams = models.BooleanField(default=False)  # type: bool

    # UI vars
    enter_sends = models.NullBooleanField(default=False)  # type: Optional[bool]
    left_side_userlist = models.BooleanField(default=False)  # type: bool

    # display settings
    twenty_four_hour_time = models.BooleanField(default=False)  # type: bool
    default_language = models.CharField(default=u'en', max_length=MAX_LANGUAGE_ID_LENGTH)  # type: str
    high_contrast_mode = models.BooleanField(default=False)  # type: bool
    night_mode = models.BooleanField(default=False)  # type: bool
    translate_emoticons = models.BooleanField(default=False)  # type: bool
    dense_mode = models.BooleanField(default=True)  # type: bool
    starred_message_counts = models.BooleanField(default=False)  # type: bool

    # A timezone name from the `tzdata` database, as found in pytz.all_timezones.
    #
    # The longest existing name is 32 characters long, so max_length=40 seems
    # like a safe choice.
    #
    # In Django, the convention is to use an empty string instead of NULL/None
    # for text-based fields. For more information, see
    # https://docs.djangoproject.com/en/1.10/ref/models/fields/#django.db.models.Field.null.
    timezone = models.CharField(max_length=40, default=u'')  # type: str

    # Emojisets
    GOOGLE_EMOJISET         = 'google'
    GOOGLE_BLOB_EMOJISET    = 'google-blob'
    TEXT_EMOJISET           = 'text'
    TWITTER_EMOJISET        = 'twitter'
    EMOJISET_CHOICES        = ((GOOGLE_EMOJISET, "Google modern"),
                               (GOOGLE_BLOB_EMOJISET, "Google classic"),
                               (TWITTER_EMOJISET, "Twitter"),
                               (TEXT_EMOJISET, "Plain text"))
    emojiset = models.CharField(default=GOOGLE_BLOB_EMOJISET, choices=EMOJISET_CHOICES, max_length=20)  # type: str

    AVATAR_FROM_GRAVATAR = u'G'
    AVATAR_FROM_USER = u'U'
    AVATAR_SOURCES = (
        (AVATAR_FROM_GRAVATAR, 'Hosted by Gravatar'),
        (AVATAR_FROM_USER, 'Uploaded by user'),
    )
    avatar_source = models.CharField(default=AVATAR_FROM_GRAVATAR, choices=AVATAR_SOURCES, max_length=1)  # type: str
    avatar_version = models.PositiveSmallIntegerField(default=1)  # type: int

    TUTORIAL_WAITING  = u'W'
    TUTORIAL_STARTED  = u'S'
    TUTORIAL_FINISHED = u'F'
    TUTORIAL_STATES   = ((TUTORIAL_WAITING, "Waiting"),
                         (TUTORIAL_STARTED, "Started"),
                         (TUTORIAL_FINISHED, "Finished"))
    tutorial_status = models.CharField(default=TUTORIAL_WAITING, choices=TUTORIAL_STATES, max_length=1)  # type: str

    # Contains serialized JSON of the form:
    #    [("step 1", true), ("step 2", false)]
    # where the second element of each tuple is if the step has been
    # completed.
    onboarding_steps = models.TextField(default=u'[]')  # type: str

    objects = UserManager()  # type: UserManager

    # Define the types of the various automatically managed properties
    property_types = dict(
        default_language=str,
        dense_mode=bool,
        emojiset=str,
        left_side_userlist=bool,
        timezone=str,
        twenty_four_hour_time=bool,
        high_contrast_mode=bool,
        night_mode=bool,
        translate_emoticons=bool,
        starred_message_counts=bool,
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
        enable_stream_sounds=bool,
        message_content_in_email_notifications=bool,
        notification_sound=str,
        pm_content_in_desktop_notifications=bool,
        realm_name_in_notifications=bool,
    )

    class Meta:
        unique_together = (('realm', 'email'),)

    @property
    def profile_data(self) -> ProfileData:
        values = CustomProfileFieldValue.objects.filter(user_profile=self)
        user_data = {v.field_id: {"value": v.value, "rendered_value": v.rendered_value} for v in values}
        data = []  # type: ProfileData
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

            field_data = {}  # type: ProfileDataElement
            for k, v in field.as_dict().items():
                field_data[k] = v
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
    def emojiset_choices() -> Dict[str, str]:
        return OrderedDict((emojiset[0], emojiset[1]) for emojiset in UserProfile.EMOJISET_CHOICES)

    @staticmethod
    def emails_from_ids(user_ids: Sequence[int]) -> Dict[int, str]:
        rows = UserProfile.objects.filter(id__in=user_ids).values('id', 'email')
        return {row['id']: row['email'] for row in rows}

    def can_create_streams(self) -> bool:
        if self.is_realm_admin:
            return True
        if self.realm.create_stream_by_admins_only:
            return False
        if self.is_guest:
            return False

        diff = (timezone_now() - self.date_joined).days
        if diff >= self.realm.waiting_period_threshold:
            return True
        return False

    def can_subscribe_other_users(self) -> bool:
        if self.is_realm_admin:
            return True
        if self.is_guest:
            return False

        diff = (timezone_now() - self.date_joined).days
        if diff >= self.realm.waiting_period_threshold:
            return True
        return False

    def can_access_public_streams(self) -> bool:
        return not (self.is_guest or self.realm.is_zephyr_mirror_realm)

    def can_access_all_realm_members(self) -> bool:
        return not (self.realm.is_zephyr_mirror_realm or self.is_guest)

    def major_tos_version(self) -> int:
        if self.tos_version is not None:
            return int(self.tos_version.split('.')[0])
        else:
            return -1

class UserGroup(models.Model):
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(UserProfile, through='UserGroupMembership')
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    description = models.TextField(default=u'')  # type: str

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
    email = models.EmailField()  # type: str
    referred_by = models.ForeignKey(UserProfile, null=True, on_delete=CASCADE)  # type: Optional[UserProfile]
    streams = models.ManyToManyField('Stream')  # type: Manager
    invited_at = models.DateTimeField(auto_now=True)  # type: datetime.datetime
    realm_creation = models.BooleanField(default=False)
    # Indicates whether the user needs a password.  Users who were
    # created via SSO style auth (e.g. GitHub/Google) generally do not.
    password_required = models.BooleanField(default=True)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_ACTIVE
    status = models.IntegerField(default=0)  # type: int

    realm = models.ForeignKey(Realm, null=True, on_delete=CASCADE)  # type: Optional[Realm]

    # Changes to INVITED_AS should also be reflected in
    # settings_invites.invited_as_values in
    # static/js/settings_invites.js
    INVITE_AS = dict(
        MEMBER = 1,
        REALM_ADMIN = 2,
        GUEST_USER = 3,
    )
    invited_as = models.PositiveSmallIntegerField(default=INVITE_AS['MEMBER'])  # type: int

class MultiuseInvite(models.Model):
    referred_by = models.ForeignKey(UserProfile, on_delete=CASCADE)  # Optional[UserProfile]
    streams = models.ManyToManyField('Stream')  # type: Manager
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    invited_as = models.PositiveSmallIntegerField(default=PreregistrationUser.INVITE_AS['MEMBER'])  # type: int

class EmailChangeStatus(models.Model):
    new_email = models.EmailField()  # type: str
    old_email = models.EmailField()  # type: str
    updated_at = models.DateTimeField(auto_now=True)  # type: datetime.datetime
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_ACTIVE
    status = models.IntegerField(default=0)  # type: int

    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm

class AbstractPushDeviceToken(models.Model):
    APNS = 1
    GCM = 2

    KINDS = (
        (APNS, 'apns'),
        (GCM, 'gcm'),
    )

    kind = models.PositiveSmallIntegerField(choices=KINDS)  # type: int

    # The token is a unique device-specific token that is
    # sent to us from each device:
    #   - APNS token if kind == APNS
    #   - GCM registration id if kind == GCM
    token = models.CharField(max_length=4096, db_index=True)  # type: bytes

    # TODO: last_updated should be renamed date_created, since it is
    # no longer maintained as a last_updated value.
    last_updated = models.DateTimeField(auto_now=True)  # type: datetime.datetime

    # [optional] Contains the app id of the device if it is an iOS device
    ios_app_id = models.TextField(null=True)  # type: Optional[str]

    class Meta:
        abstract = True

class PushDeviceToken(AbstractPushDeviceToken):
    # The user who's device this is
    user = models.ForeignKey(UserProfile, db_index=True, on_delete=CASCADE)  # type: UserProfile

    class Meta:
        unique_together = ("user", "kind", "token")

def generate_email_token_for_stream() -> str:
    return generate_random_token(32)

class Stream(models.Model):
    MAX_NAME_LENGTH = 60
    MAX_DESCRIPTION_LENGTH = 1024

    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)  # type: str
    realm = models.ForeignKey(Realm, db_index=True, on_delete=CASCADE)  # type: Realm
    date_created = models.DateTimeField(default=timezone_now)  # type: datetime.datetime
    deactivated = models.BooleanField(default=False)  # type: bool
    description = models.CharField(max_length=MAX_DESCRIPTION_LENGTH, default=u'')  # type: str
    rendered_description = models.TextField(default=u'')  # type: str

    invite_only = models.NullBooleanField(default=False)  # type: Optional[bool]
    history_public_to_subscribers = models.BooleanField(default=False)  # type: bool

    # Whether this stream's content should be published by the web-public archive features
    is_web_public = models.BooleanField(default=False)  # type: bool

    # Whether only organization administrators can send messages to this stream
    is_announcement_only = models.BooleanField(default=False)  # type: bool

    # The unique thing about Zephyr public streams is that we never list their
    # users.  We may try to generalize this concept later, but for now
    # we just use a concrete field.  (Zephyr public streams aren't exactly like
    # invite-only streams--while both are private in terms of listing users,
    # for Zephyr we don't even list users to stream members, yet membership
    # is more public in the sense that you don't need a Zulip invite to join.
    # This field is populated directly from UserProfile.is_zephyr_mirror_realm,
    # and the reason for denormalizing field is performance.
    is_in_zephyr_realm = models.BooleanField(default=False)  # type: bool

    # Used by the e-mail forwarder. The e-mail RFC specifies a maximum
    # e-mail length of 254, and our max stream length is 30, so we
    # have plenty of room for the token.
    email_token = models.CharField(
        max_length=32, default=generate_email_token_for_stream)  # type: str

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

    # This is stream information that is sent to clients
    def to_dict(self) -> Dict[str, Any]:
        return dict(
            name=self.name,
            stream_id=self.id,
            description=self.description,
            rendered_description=self.rendered_description,
            invite_only=self.invite_only,
            is_announcement_only=self.is_announcement_only,
            history_public_to_subscribers=self.history_public_to_subscribers
        )

post_save.connect(flush_stream, sender=Stream)
post_delete.connect(flush_stream, sender=Stream)

# The Recipient table is used to map Messages to the set of users who
# received the message.  It is implemented as a set of triples (id,
# type_id, type). We have 3 types of recipients: Huddles (for group
# private messages), UserProfiles (for 1:1 private messages), and
# Streams. The recipient table maps a globally unique recipient id
# (used by the Message table) to the type-specific unique id (the
# stream id, user_profile id, or huddle id).
class Recipient(models.Model):
    type_id = models.IntegerField(db_index=True)  # type: int
    type = models.PositiveSmallIntegerField(db_index=True)  # type: int
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

class MutedTopic(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    topic_name = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)

    class Meta:
        unique_together = ('user_profile', 'stream', 'topic_name')

    def __str__(self) -> str:
        return "<MutedTopic: (%s, %s, %s)>" % (self.user_profile.email, self.stream.name, self.topic_name)

class Client(models.Model):
    name = models.CharField(max_length=30, db_index=True, unique=True)  # type: str

    def __str__(self) -> str:
        return "<Client: %s>" % (self.name,)

get_client_cache = {}  # type: Dict[str, Client]
def get_client(name: str) -> Client:
    # Accessing KEY_PREFIX through the module is necessary
    # because we need the updated value of the variable.
    cache_name = cache.KEY_PREFIX + name
    if cache_name not in get_client_cache:
        result = get_client_remote_cache(name)
        get_client_cache[cache_name] = result
    return get_client_cache[cache_name]

def get_client_cache_key(name: str) -> str:
    return u'get_client:%s' % (make_safe_digest(name),)

@cache_with_key(get_client_cache_key, timeout=3600*24*7)
def get_client_remote_cache(name: str) -> Client:
    (client, _) = Client.objects.get_or_create(name=name)
    return client

@cache_with_key(get_stream_cache_key, timeout=3600*24*7)
def get_realm_stream(stream_name: str, realm_id: int) -> Stream:
    return Stream.objects.select_related("realm").get(
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
        # Stream.objects.select_related("realm").filter(name__iexact__in=stream_names,
        #                                               realm_id=realm_id)
        #
        # But chaining __in and __iexact doesn't work with Django's
        # ORM, so we have the following hack to construct the relevant where clause
        if len(stream_names) == 0:
            return []
        upper_list = ", ".join(["UPPER(%s)"] * len(stream_names))
        where_clause = "UPPER(zerver_stream.name::text) IN (%s)" % (upper_list,)
        return get_active_streams(realm.id).select_related("realm").extra(
            where=[where_clause],
            params=stream_names)

    return generic_bulk_cached_fetch(lambda stream_name: get_stream_cache_key(stream_name, realm.id),
                                     fetch_streams_by_name,
                                     [stream_name.lower() for stream_name in stream_names],
                                     id_fetcher=lambda stream: stream.name.lower())

def get_recipient_cache_key(type: int, type_id: int) -> str:
    return u"%s:get_recipient:%s:%s" % (cache.KEY_PREFIX, type, type_id,)

@cache_with_key(get_recipient_cache_key, timeout=3600*24*7)
def get_recipient(type: int, type_id: int) -> Recipient:
    return Recipient.objects.get(type_id=type_id, type=type)

def get_stream_recipient(stream_id: int) -> Recipient:
    return get_recipient(Recipient.STREAM, stream_id)

def get_personal_recipient(user_profile_id: int) -> Recipient:
    return get_recipient(Recipient.PERSONAL, user_profile_id)

def get_huddle_recipient(user_profile_ids: Set[int]) -> Recipient:

    # The caller should ensure that user_profile_ids includes
    # the sender.  Note that get_huddle hits the cache, and then
    # we hit another cache to get the recipient.  We may want to
    # unify our caching strategy here.
    huddle = get_huddle(list(user_profile_ids))
    return get_recipient(Recipient.HUDDLE, huddle.id)

def get_huddle_user_ids(recipient: Recipient) -> List[int]:
    assert(recipient.type == Recipient.HUDDLE)

    return Subscription.objects.filter(
        recipient=recipient,
        active=True,
    ).order_by('user_profile_id').values_list('user_profile_id', flat=True)

def bulk_get_recipients(type: int, type_ids: List[int]) -> Dict[int, Any]:
    def cache_key_function(type_id: int) -> str:
        return get_recipient_cache_key(type, type_id)

    def query_function(type_ids: List[int]) -> Sequence[Recipient]:
        # TODO: Change return type to QuerySet[Recipient]
        return Recipient.objects.filter(type=type, type_id__in=type_ids)

    return generic_bulk_cached_fetch(cache_key_function, query_function, type_ids,
                                     id_fetcher=lambda recipient: recipient.type_id)

def get_stream_recipients(stream_ids: List[int]) -> List[Recipient]:

    '''
    We could call bulk_get_recipients(...).values() here, but it actually
    leads to an extra query in test mode.
    '''
    return Recipient.objects.filter(
        type=Recipient.STREAM,
        type_id__in=stream_ids,
    )

class AbstractMessage(models.Model):
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)  # type: Recipient

    # The message's topic.
    #
    # Early versions of Zulip called this concept a "subject", as in an email
    # "subject line", before changing to "topic" in 2013 (commit dac5a46fa).
    # UI and user documentation now consistently say "topic".  New APIs and
    # new code should generally also say "topic".
    #
    # See also the `topic_name` method on `Message`.
    subject = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH, db_index=True)  # type: str

    content = models.TextField()  # type: str
    rendered_content = models.TextField(null=True)  # type: Optional[str]
    rendered_content_version = models.IntegerField(null=True)  # type: Optional[int]

    pub_date = models.DateTimeField('date published', db_index=True)  # type: datetime.datetime
    sending_client = models.ForeignKey(Client, on_delete=CASCADE)  # type: Client

    last_edit_time = models.DateTimeField(null=True)  # type: Optional[datetime.datetime]

    # A JSON-encoded list of objects describing any past edits to this
    # message, oldest first.
    edit_history = models.TextField(null=True)  # type: Optional[str]

    has_attachment = models.BooleanField(default=False, db_index=True)  # type: bool
    has_image = models.BooleanField(default=False, db_index=True)  # type: bool
    has_link = models.BooleanField(default=False, db_index=True)  # type: bool

    class Meta:
        abstract = True

    def __str__(self) -> str:
        display_recipient = get_display_recipient(self.recipient)
        return "<%s: %s / %s / %s>" % (self.__class__.__name__, display_recipient,
                                       self.subject, self.sender)


class ArchivedMessage(AbstractMessage):
    """Used as a temporary holding place for deleted messages before they
    are permanently deleted.  This is an important part of a robust
    'message retention' feature.
    """
    archive_timestamp = models.DateTimeField(default=timezone_now, db_index=True)  # type: datetime.datetime


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
        type onto Message, either explicity (message.type)
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
            timestamp         = datetime_to_timestamp(self.pub_date))

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
    def content_has_attachment(content: str) -> Match:
        return re.search(r'[/\-]user[\-_]uploads[/\.-]', content)

    @staticmethod
    def content_has_image(content: str) -> bool:
        return bool(re.search(r'[/\-]user[\-_]uploads[/\.-]\S+\.(bmp|gif|jpg|jpeg|png|webp)',
                              content, re.IGNORECASE))

    @staticmethod
    def content_has_link(content: str) -> bool:
        return ('http://' in content or
                'https://' in content or
                '/user_uploads' in content or
                (settings.ENABLE_FILE_LINKS and 'file:///' in content) or
                'bitcoin:' in content)

    @staticmethod
    def is_status_message(content: str, rendered_content: str) -> bool:
        """
        Returns True if content and rendered_content are from 'me_message'
        """
        if content.startswith('/me ') and '\n' not in content:
            if rendered_content.startswith('<p>') and rendered_content.endswith('</p>'):
                return True
        return False

    def update_calculated_fields(self) -> None:
        # TODO: rendered_content could also be considered a calculated field
        content = self.content
        self.has_attachment = bool(Message.content_has_attachment(content))
        self.has_image = bool(Message.content_has_image(content))
        self.has_link = bool(Message.content_has_link(content))

@receiver(pre_save, sender=Message)
def pre_save_message(sender: Any, **kwargs: Any) -> None:
    if kwargs['update_fields'] is None or "content" in kwargs['update_fields']:
        message = kwargs['instance']
        message.update_calculated_fields()

def get_context_for_message(message: Message) -> Sequence[Message]:
    # TODO: Change return type to QuerySet[Message]
    return Message.objects.filter(
        recipient_id=message.recipient_id,
        subject=message.subject,
        id__lt=message.id,
        pub_date__gt=message.pub_date - timedelta(minutes=15),
    ).order_by('-id')[:10]

post_save.connect(flush_message, sender=Message)

class SubMessage(models.Model):
    # We can send little text messages that are associated with a regular
    # Zulip message.  These can be used for experimental widgets like embedded
    # games, surveys, mini threads, etc.  These are designed to be pretty
    # generic in purpose.

    message = models.ForeignKey(Message, on_delete=CASCADE)  # type: Message
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    msg_type = models.TextField()
    content = models.TextField()

    @staticmethod
    def get_raw_db_rows(needed_ids: List[int]) -> List[Dict[str, Any]]:
        fields = ['id', 'message_id', 'sender_id', 'msg_type', 'content']
        query = SubMessage.objects.filter(message_id__in=needed_ids).values(*fields)
        query = query.order_by('message_id', 'id')
        return list(query)

post_save.connect(flush_submessage, sender=SubMessage)

class Reaction(models.Model):
    """For emoji reactions to messages (and potentially future reaction types).

    Emoji are surprisingly complicated to implement correctly.  For details
    on how this subsystem works, see:
      https://zulip.readthedocs.io/en/latest/subsystems/emoji.html
    """
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    message = models.ForeignKey(Message, on_delete=CASCADE)  # type: Message

    # The user-facing name for an emoji reaction.  With emoji aliases,
    # there may be multiple accepted names for a given emoji; this
    # field encodes which one the user selected.
    emoji_name = models.TextField()  # type: str

    UNICODE_EMOJI       = u'unicode_emoji'
    REALM_EMOJI         = u'realm_emoji'
    ZULIP_EXTRA_EMOJI   = u'zulip_extra_emoji'
    REACTION_TYPES      = ((UNICODE_EMOJI, _("Unicode emoji")),
                           (REALM_EMOJI, _("Custom emoji")),
                           (ZULIP_EXTRA_EMOJI, _("Zulip extra emoji")))
    reaction_type = models.CharField(default=UNICODE_EMOJI, choices=REACTION_TYPES, max_length=30)  # type: str

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
    emoji_code = models.TextField()  # type: str

    class Meta:
        unique_together = ("user_profile", "message", "emoji_name")

    @staticmethod
    def get_raw_db_rows(needed_ids: List[int]) -> List[Dict[str, Any]]:
        fields = ['message_id', 'emoji_name', 'emoji_code', 'reaction_type',
                  'user_profile__email', 'user_profile__id', 'user_profile__full_name']
        return Reaction.objects.filter(message_id__in=needed_ids).values(*fields)

    def __str__(self) -> str:
        return "%s / %s / %s" % (self.user_profile.email, self.message.id, self.emoji_name)

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
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    ALL_FLAGS = ['read', 'starred', 'collapsed', 'mentioned', 'wildcard_mentioned',
                 'summarize_in_home', 'summarize_in_stream', 'force_expand', 'force_collapse',
                 'has_alert_word', "historical", "is_private", "active_mobile_push_notification"]
    # Certain flags are used only for internal accounting within the
    # Zulip backend, and don't make sense to expose to the API.  A
    # good example is is_private, which is just a denormalization of
    # message.recipient_type for database query performance.
    NON_API_FLAGS = {"is_private", "active_mobile_push_notification"}
    flags = BitField(flags=ALL_FLAGS, default=0)  # type: BitHandler

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
    message = models.ForeignKey(Message, on_delete=CASCADE)  # type: Message

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
    message = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)  # type: Message
    archive_timestamp = models.DateTimeField(default=timezone_now, db_index=True)  # type: datetime.datetime


class AbstractAttachment(models.Model):
    file_name = models.TextField(db_index=True)  # type: str

    # path_id is a storage location agnostic representation of the path of the file.
    # If the path of a file is http://localhost:9991/user_uploads/a/b/abc/temp_file.py
    # then its path_id will be a/b/abc/temp_file.py.
    path_id = models.TextField(db_index=True, unique=True)  # type: str
    owner = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    realm = models.ForeignKey(Realm, blank=True, null=True, on_delete=CASCADE)  # type: Optional[Realm]

    create_time = models.DateTimeField(default=timezone_now,
                                       db_index=True)  # type: datetime.datetime
    size = models.IntegerField(null=True)  # type: Optional[int]

    # Whether this attachment has been posted to a public stream, and
    # thus should be available to all non-guest users in the
    # organization (even if they weren't a recipient of a message
    # linking to it).  This lets us avoid looking up the corresponding
    # messages/streams to check permissions before serving these files.
    is_realm_public = models.BooleanField(default=False)  # type: bool

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return "<%s: %s>" % (self.__class__.__name__, self.file_name,)


class ArchivedAttachment(AbstractAttachment):
    """Used as a temporary holding place for deleted Attachment objects
    before they are permanently deleted.  This is an important part of
    a robust 'message retention' feature.
    """
    archive_timestamp = models.DateTimeField(default=timezone_now, db_index=True)  # type: datetime.datetime
    messages = models.ManyToManyField(ArchivedMessage)  # type: Manager


class Attachment(AbstractAttachment):
    messages = models.ManyToManyField(Message)  # type: Manager

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
                'name': time.mktime(m.pub_date.timetuple()) * 1000
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
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)  # type: Recipient

    # Whether the user has since unsubscribed.  We mark Subscription
    # objects as inactive, rather than deleting them, when a user
    # unsubscribes, so we can preseve user customizations like
    # notification settings, stream color, etc., if the user later
    # resubscribes.
    active = models.BooleanField(default=True)  # type: bool

    # Whether the stream is muted.  TODO: Remove to !muted.
    in_home_view = models.NullBooleanField(default=True)  # type: Optional[bool]

    DEFAULT_STREAM_COLOR = u"#c2c2c2"
    color = models.CharField(max_length=10, default=DEFAULT_STREAM_COLOR)  # type: str
    pin_to_top = models.BooleanField(default=False)  # type: bool

    desktop_notifications = models.BooleanField(default=True)  # type: bool
    audible_notifications = models.BooleanField(default=True)  # type: bool
    push_notifications = models.BooleanField(default=False)  # type: bool
    email_notifications = models.BooleanField(default=False)  # type: bool

    class Meta:
        unique_together = ("user_profile", "recipient")

    def __str__(self) -> str:
        return "<Subscription: %s -> %s>" % (self.user_profile, self.recipient)

@cache_with_key(user_profile_by_id_cache_key, timeout=3600*24*7)
def get_user_profile_by_id(uid: int) -> UserProfile:
    return UserProfile.objects.select_related().get(id=uid)

@cache_with_key(user_profile_by_email_cache_key, timeout=3600*24*7)
def get_user_profile_by_email(email: str) -> UserProfile:
    return UserProfile.objects.select_related().get(delivery_email__iexact=email.strip())

@cache_with_key(user_profile_by_api_key_cache_key, timeout=3600*24*7)
def get_user_profile_by_api_key(api_key: str) -> UserProfile:
    return UserProfile.objects.select_related().get(api_key=api_key)

def get_user_by_delivery_email(email: str, realm: Realm) -> UserProfile:
    # Fetches users by delivery_email for use in
    # authentication/registration contexts. Do not use for user-facing
    # views (e.g. Zulip API endpoints); for that, you want get_user.
    return UserProfile.objects.select_related().get(delivery_email__iexact=email.strip(), realm=realm)

@cache_with_key(user_profile_cache_key, timeout=3600*24*7)
def get_user(email: str, realm: Realm) -> UserProfile:
    # Fetches the user by its visible-to-other users username (in the
    # `email` field).  For use in API contexts; do not use in
    # authentication/registration contexts; for that, you need to use
    # get_user_by_delivery_email.
    return UserProfile.objects.select_related().get(email__iexact=email.strip(), realm=realm)

def get_active_user_by_delivery_email(email: str, realm: Realm) -> UserProfile:
    user_profile = get_user_by_delivery_email(email, realm)
    if not user_profile.is_active:
        raise UserProfile.DoesNotExist()
    return user_profile

def get_active_user(email: str, realm: Realm) -> UserProfile:
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
        realm: Realm
) -> UserProfile:
    user_profile = get_user_profile_by_id(uid)
    if user_profile.realm == realm:
        return user_profile

    # Note: This doesn't validate whether the `realm` passed in is
    # None/invalid for the CROSS_REALM_BOT_EMAILS case.
    if user_profile.email in settings.CROSS_REALM_BOT_EMAILS:
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
        is_active=True,
        is_guest=False,
    ).values_list('id', flat=True)
    return list(query)

def get_source_profile(email: str, string_id: str) -> Optional[UserProfile]:
    realm = get_realm(string_id)

    if realm is None:
        return None

    try:
        return get_user_by_delivery_email(email, realm)
    except UserProfile.DoesNotExist:
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
    huddle_hash = models.CharField(max_length=40, db_index=True, unique=True)  # type: str

def get_huddle_hash(id_list: List[int]) -> str:
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    return make_safe_digest(hash_key)

def huddle_hash_cache_key(huddle_hash: str) -> str:
    return u"huddle_by_hash:%s" % (huddle_hash,)

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
            subs_to_create = [Subscription(recipient=recipient,
                                           user_profile_id=user_profile_id)
                              for user_profile_id in id_list]
            Subscription.objects.bulk_create(subs_to_create)
        return huddle

def clear_database() -> None:  # nocoverage # Only used in populate_db
    pylibmc.Client(['127.0.0.1']).flush_all()
    model = None  # type: Any
    for model in [Message, Stream, UserProfile, Recipient,
                  Realm, Subscription, Huddle, UserMessage, Client,
                  DefaultStream]:
        model.objects.all().delete()
    Session.objects.all().delete()

class UserActivity(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    client = models.ForeignKey(Client, on_delete=CASCADE)  # type: Client
    query = models.CharField(max_length=50, db_index=True)  # type: str

    count = models.IntegerField()  # type: int
    last_visit = models.DateTimeField('last visit')  # type: datetime.datetime

    class Meta:
        unique_together = ("user_profile", "client", "query")

class UserActivityInterval(models.Model):
    MIN_INTERVAL_LENGTH = datetime.timedelta(minutes=15)

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    start = models.DateTimeField('start time', db_index=True)  # type: datetime.datetime
    end = models.DateTimeField('end time', db_index=True)  # type: datetime.datetime


class UserPresence(models.Model):
    """A record from the last time we heard from a given user on a given client.

    This is a tricky subsystem, because it is highly optimized.  See the docs:
      https://zulip.readthedocs.io/en/latest/subsystems/presence.html
    """
    class Meta:
        unique_together = ("user_profile", "client")

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    client = models.ForeignKey(Client, on_delete=CASCADE)  # type: Client

    # The time we heard this update from the client.
    timestamp = models.DateTimeField('presence changed')  # type: datetime.datetime

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
    status = models.PositiveSmallIntegerField(default=ACTIVE)  # type: int

    @staticmethod
    def status_to_string(status: int) -> str:
        if status == UserPresence.ACTIVE:
            return 'active'
        elif status == UserPresence.IDLE:
            return 'idle'
        else:  # nocoverage # TODO: Add a presence test to cover this.
            raise ValueError('Unknown status: %s' % (status,))

    @staticmethod
    def get_status_dict_by_user(user_profile: UserProfile) -> Dict[str, Dict[str, Any]]:
        query = UserPresence.objects.filter(user_profile=user_profile).values(
            'client__name',
            'status',
            'timestamp',
            'user_profile__email',
            'user_profile__id',
            'user_profile__enable_offline_push_notifications',
        )
        presence_rows = list(query)

        mobile_user_ids = set()  # type: Set[int]
        if PushDeviceToken.objects.filter(user=user_profile).exists():  # nocoverage
            # TODO: Add a test, though this is low priority, since we don't use mobile_user_ids yet.
            mobile_user_ids.add(user_profile.id)

        return UserPresence.get_status_dicts_for_rows(presence_rows, mobile_user_ids)

    @staticmethod
    def get_status_dict_by_realm(realm_id: int) -> Dict[str, Dict[str, Any]]:
        user_profile_ids = UserProfile.objects.filter(
            realm_id=realm_id,
            is_active=True,
            is_bot=False
        ).order_by('id').values_list('id', flat=True)

        user_profile_ids = list(user_profile_ids)
        if not user_profile_ids:  # nocoverage
            # This conditional is necessary because query_for_ids
            # throws an exception if passed an empty list.
            #
            # It's not clear this condition is actually possible,
            # though, because it shouldn't be possible to end up with
            # a realm with 0 active users.
            return {}

        two_weeks_ago = timezone_now() - datetime.timedelta(weeks=2)
        query = UserPresence.objects.filter(
            timestamp__gte=two_weeks_ago
        ).values(
            'client__name',
            'status',
            'timestamp',
            'user_profile__email',
            'user_profile__id',
            'user_profile__enable_offline_push_notifications',
        )

        query = query_for_ids(
            query=query,
            user_ids=user_profile_ids,
            field='user_profile_id'
        )
        presence_rows = list(query)

        mobile_query = PushDeviceToken.objects.distinct(
            'user_id'
        ).values_list(
            'user_id',
            flat=True
        )

        mobile_query = query_for_ids(
            query=mobile_query,
            user_ids=user_profile_ids,
            field='user_id'
        )
        mobile_user_ids = set(mobile_query)

        return UserPresence.get_status_dicts_for_rows(presence_rows, mobile_user_ids)

    @staticmethod
    def get_status_dicts_for_rows(presence_rows: List[Dict[str, Any]],
                                  mobile_user_ids: Set[int]) -> Dict[str, Dict[str, Any]]:

        info_row_dct = defaultdict(list)  # type: DefaultDict[str, List[Dict[str, Any]]]
        for row in presence_rows:
            email = row['user_profile__email']
            client_name = row['client__name']
            status = UserPresence.status_to_string(row['status'])
            dt = row['timestamp']
            timestamp = datetime_to_timestamp(dt)
            push_enabled = row['user_profile__enable_offline_push_notifications']
            has_push_devices = row['user_profile__id'] in mobile_user_ids
            pushable = (push_enabled and has_push_devices)

            info = dict(
                client=client_name,
                status=status,
                dt=dt,
                timestamp=timestamp,
                pushable=pushable,
            )

            info_row_dct[email].append(info)

        user_statuses = dict()  # type: Dict[str, Dict[str, Any]]

        for email, info_rows in info_row_dct.items():
            # Note that datetime values have sub-second granularity, which is
            # mostly important for avoiding test flakes, but it's also technically
            # more precise for real users.
            by_time = lambda row: row['dt']
            most_recent_info = max(info_rows, key=by_time)

            # We don't send datetime values to the client.
            for r in info_rows:
                del r['dt']

            client_dict = {info['client']: info for info in info_rows}
            user_statuses[email] = client_dict

            # The word "aggegrated" here is possibly misleading.
            # It's really just the most recent client's info.
            user_statuses[email]['aggregated'] = dict(
                client=most_recent_info['client'],
                status=most_recent_info['status'],
                timestamp=most_recent_info['timestamp'],
            )

        return user_statuses

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
            status_val = UserPresence.ACTIVE  # type: Optional[int] # See https://github.com/python/mypy/issues/2611
        elif status == 'idle':
            status_val = UserPresence.IDLE
        else:
            status_val = None

        return status_val

class UserStatus(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=CASCADE)  # type: UserProfile

    timestamp = models.DateTimeField()  # type: datetime.datetime
    client = models.ForeignKey(Client, on_delete=CASCADE)  # type: Client

    NORMAL = 0
    AWAY = 1

    status = models.PositiveSmallIntegerField(default=NORMAL)  # type: int
    status_text = models.CharField(max_length=255, default='')  # type: str

class DefaultStream(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    stream = models.ForeignKey(Stream, on_delete=CASCADE)  # type: Stream

    class Meta:
        unique_together = ("realm", "stream")

class DefaultStreamGroup(models.Model):
    MAX_NAME_LENGTH = 60
    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)  # type: str
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    streams = models.ManyToManyField('Stream')  # type: Manager
    description = models.CharField(max_length=1024, default=u'')  # type: str

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
    scheduled_timestamp = models.DateTimeField(db_index=True)  # type: datetime.datetime
    # JSON representation of arguments to consumer
    data = models.TextField()  # type: str
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm

    class Meta:
        abstract = True

class ScheduledEmail(AbstractScheduledJob):
    # Exactly one of user or address should be set. These are used to
    # filter the set of ScheduledEmails.
    user = models.ForeignKey(UserProfile, null=True, on_delete=CASCADE)  # type: Optional[UserProfile]
    # Just the address part of a full "name <address>" email address
    address = models.EmailField(null=True, db_index=True)  # type: Optional[str]

    # Valid types are below
    WELCOME = 1
    DIGEST = 2
    INVITATION_REMINDER = 3
    type = models.PositiveSmallIntegerField()  # type: int

    def __str__(self) -> str:
        return "<ScheduledEmail: %s %s %s>" % (self.type, self.user or self.address,
                                               self.scheduled_timestamp)

class ScheduledMessage(models.Model):
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)  # type: Recipient
    subject = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH)  # type: str
    content = models.TextField()  # type: str
    sending_client = models.ForeignKey(Client, on_delete=CASCADE)  # type: Client
    stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)  # type: Optional[Stream]
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    scheduled_timestamp = models.DateTimeField(db_index=True)  # type: datetime.datetime
    delivered = models.BooleanField(default=False)  # type: bool

    SEND_LATER = 1
    REMIND = 2

    DELIVERY_TYPES = (
        (SEND_LATER, 'send_later'),
        (REMIND, 'remind'),
    )

    delivery_type = models.PositiveSmallIntegerField(choices=DELIVERY_TYPES,
                                                     default=SEND_LATER)  # type: int

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

class RealmAuditLog(models.Model):
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
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    acting_user = models.ForeignKey(UserProfile, null=True, related_name='+', on_delete=CASCADE)  # type: Optional[UserProfile]
    modified_user = models.ForeignKey(UserProfile, null=True, related_name='+', on_delete=CASCADE)  # type: Optional[UserProfile]
    modified_stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)  # type: Optional[Stream]
    event_last_message_id = models.IntegerField(null=True)  # type: Optional[int]

    event_time = models.DateTimeField(db_index=True)  # type: datetime.datetime
    # If True, event_time is an overestimate of the true time. Can be used
    # by migrations when introducing a new event_type.
    backfilled = models.BooleanField(default=False)  # type: bool
    extra_data = models.TextField(null=True)  # type: Optional[str]

    STRIPE_CUSTOMER_CREATED = 'stripe_customer_created'
    STRIPE_CARD_CHANGED = 'stripe_card_changed'
    STRIPE_PLAN_CHANGED = 'stripe_plan_changed'
    STRIPE_PLAN_QUANTITY_RESET = 'stripe_plan_quantity_reset'

    CUSTOMER_CREATED = 'customer_created'
    CUSTOMER_PLAN_CREATED = 'customer_plan_created'

    USER_CREATED = 'user_created'
    USER_ACTIVATED = 'user_activated'
    USER_DEACTIVATED = 'user_deactivated'
    USER_REACTIVATED = 'user_reactivated'
    USER_SOFT_ACTIVATED = 'user_soft_activated'
    USER_SOFT_DEACTIVATED = 'user_soft_deactivated'
    USER_PASSWORD_CHANGED = 'user_password_changed'
    USER_AVATAR_SOURCE_CHANGED = 'user_avatar_source_changed'
    USER_FULL_NAME_CHANGED = 'user_full_name_changed'
    USER_EMAIL_CHANGED = 'user_email_changed'
    USER_TOS_VERSION_CHANGED = 'user_tos_version_changed'
    USER_API_KEY_CHANGED = 'user_api_key_changed'
    USER_BOT_OWNER_CHANGED = 'user_bot_owner_changed'

    REALM_DEACTIVATED = 'realm_deactivated'
    REALM_REACTIVATED = 'realm_reactivated'
    REALM_SCRUBBED = 'realm_scrubbed'
    REALM_PLAN_TYPE_CHANGED = 'realm_plan_type_changed'
    REALM_LOGO_CHANGED = 'realm_logo_changed'

    SUBSCRIPTION_CREATED = 'subscription_created'
    SUBSCRIPTION_ACTIVATED = 'subscription_activated'
    SUBSCRIPTION_DEACTIVATED = 'subscription_deactivated'

    event_type = models.CharField(max_length=40)  # type: str

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
    user = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    hotspot = models.CharField(max_length=30)  # type: str
    timestamp = models.DateTimeField(default=timezone_now)  # type: datetime.datetime

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

    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    name = models.CharField(max_length=NAME_MAX_LENGTH)  # type: str
    hint = models.CharField(max_length=HINT_MAX_LENGTH, default='', null=True)  # type: Optional[str]
    order = models.IntegerField(default=0)  # type: int

    SHORT_TEXT = 1
    LONG_TEXT = 2
    CHOICE = 3
    DATE = 4
    URL = 5
    USER = 6

    # These are the fields whose validators require more than var_name
    # and value argument. i.e. CHOICE require field_data, USER require
    # realm as argument.
    CHOICE_FIELD_TYPE_DATA = [
        (CHOICE, str(_('List of options')), validate_choice_field, str, "CHOICE"),
    ]  # type: FieldTypeData
    USER_FIELD_TYPE_DATA = [
        (USER, str(_('Person picker')), check_valid_user_ids, eval, "USER"),
    ]  # type: FieldTypeData

    CHOICE_FIELD_VALIDATORS = {
        item[0]: item[2] for item in CHOICE_FIELD_TYPE_DATA
    }  # type: Dict[int, ExtendedValidator]
    USER_FIELD_VALIDATORS = {
        item[0]: item[2] for item in USER_FIELD_TYPE_DATA
    }  # type: Dict[int, RealmUserValidator]

    FIELD_TYPE_DATA = [
        # Type, Display Name, Validator, Converter, Keyword
        (SHORT_TEXT, str(_('Short text')), check_short_string, str, "SHORT_TEXT"),
        (LONG_TEXT, str(_('Long text')), check_long_string, str, "LONG_TEXT"),
        (DATE, str(_('Date picker')), check_date, str, "DATE"),
        (URL, str(_('Link')), check_url, str, "URL"),
    ]  # type: FieldTypeData

    ALL_FIELD_TYPES = FIELD_TYPE_DATA + CHOICE_FIELD_TYPE_DATA + USER_FIELD_TYPE_DATA

    FIELD_VALIDATORS = {item[0]: item[2] for item in FIELD_TYPE_DATA}  # type: Dict[int, Validator]
    FIELD_CONVERTERS = {item[0]: item[3] for item in ALL_FIELD_TYPES}  # type: Dict[int, Callable[[Any], Any]]
    FIELD_TYPE_CHOICES = [(item[0], item[1]) for item in ALL_FIELD_TYPES]  # type: List[Tuple[int, str]]
    FIELD_TYPE_CHOICES_DICT = {
        item[4]: {"id": item[0], "name": item[1]} for item in ALL_FIELD_TYPES
    }  # type: Dict[str, Dict[str, Union[str, int]]]

    field_type = models.PositiveSmallIntegerField(choices=FIELD_TYPE_CHOICES,
                                                  default=SHORT_TEXT)  # type: int

    # A JSON blob of any additional data needed to define the field beyond
    # type/name/hint.
    #
    # The format depends on the type.  Field types SHORT_TEXT, LONG_TEXT,
    # DATE, URL, and USER leave this null.  Fields of type CHOICE store the
    # choices' descriptions.
    #
    # Note: There is no performance overhead of using TextField in PostgreSQL.
    # See https://www.postgresql.org/docs/9.0/static/datatype-character.html
    field_data = models.TextField(default='', null=True)  # type: Optional[str]

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
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    field = models.ForeignKey(CustomProfileField, on_delete=CASCADE)  # type: CustomProfileField
    value = models.TextField()  # type: str
    rendered_value = models.TextField(null=True, default=None)  # type: Optional[str]

    class Meta:
        unique_together = ('user_profile', 'field')

    def __str__(self) -> str:
        return "<CustomProfileFieldValue: %s %s %s>" % (self.user_profile, self.field, self.value)

# Interfaces for services
# They provide additional functionality like parsing message to obtain query url, data to be sent to url,
# and parsing the response.
GENERIC_INTERFACE = u'GenericService'
SLACK_INTERFACE = u'SlackOutgoingWebhookService'

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
    name = models.CharField(max_length=UserProfile.MAX_NAME_LENGTH)  # type: str
    # Bot user corresponding to the Service.  The bot_type of this user
    # deterines the type of service.  If non-bot services are added later,
    # user_profile can also represent the owner of the Service.
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    base_url = models.TextField()  # type: str
    token = models.TextField()  # type: str
    # Interface / API version of the service.
    interface = models.PositiveSmallIntegerField(default=1)  # type: int

    # Valid interfaces are {generic, zulip_bot_service, slack}
    GENERIC = 1
    SLACK = 2

    ALLOWED_INTERFACE_TYPES = [
        GENERIC,
        SLACK,
    ]
    # N.B. If we used Django's choice=... we would get this for free (kinda)
    _interfaces = {
        GENERIC: GENERIC_INTERFACE,
        SLACK: SLACK_INTERFACE,
    }  # type: Dict[int, str]

    def interface_name(self) -> str:
        # Raises KeyError if invalid
        return self._interfaces[self.interface]


def get_bot_services(user_profile_id: str) -> List[Service]:
    return list(Service.objects.filter(user_profile__id=user_profile_id))

def get_service_profile(user_profile_id: str, service_name: str) -> Service:
    return Service.objects.get(user_profile__id=user_profile_id, name=service_name)


class BotStorageData(models.Model):
    bot_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    key = models.TextField(db_index=True)  # type: str
    value = models.TextField()  # type: str

    class Meta:
        unique_together = ("bot_profile", "key")

class BotConfigData(models.Model):
    bot_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    key = models.TextField(db_index=True)  # type: str
    value = models.TextField()  # type: str

    class Meta(object):
        unique_together = ("bot_profile", "key")
