from __future__ import absolute_import
from typing import Any, Dict, List, Set, Tuple, TypeVar, Text, \
    Union, Optional, Sequence, AbstractSet, Pattern, AnyStr
from typing.re import Match
from zerver.lib.str_utils import NonBinaryStr

from django.db import models
from django.db.models.query import QuerySet
from django.db.models import Manager
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, UserManager, \
    PermissionsMixin
import django.contrib.auth
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.dispatch import receiver
from zerver.lib.cache import cache_with_key, flush_user_profile, flush_realm, \
    user_profile_by_id_cache_key, user_profile_by_email_cache_key, \
    generic_bulk_cached_fetch, cache_set, flush_stream, \
    display_recipient_cache_key, cache_delete, \
    get_stream_cache_key, active_user_dicts_in_realm_cache_key, \
    bot_dicts_in_realm_cache_key, active_user_dict_fields, \
    bot_dict_fields, flush_message
from zerver.lib.utils import make_safe_digest, generate_random_token
from zerver.lib.str_utils import ModelReprMixin
from django.db import transaction
from zerver.lib.camo import get_camo_url
from django.utils import timezone
from django.contrib.sessions.models import Session
from zerver.lib.timestamp import datetime_to_timestamp
from django.db.models.signals import pre_save, post_save, post_delete
from django.core.validators import MinLengthValidator, RegexValidator
from django.utils.translation import ugettext_lazy as _
from zerver.lib import cache

from bitfield import BitField
from bitfield.types import BitHandler
from collections import defaultdict
from datetime import timedelta
import pylibmc
import re
import logging
import sre_constants
import time
import datetime

MAX_SUBJECT_LENGTH = 60
MAX_MESSAGE_LENGTH = 10000
MAX_LANGUAGE_ID_LENGTH = 50 # type: int

STREAM_NAMES = TypeVar('STREAM_NAMES', Sequence[Text], AbstractSet[Text])

# Doing 1000 remote cache requests to get_display_recipient is quite slow,
# so add a local cache as well as the remote cache cache.
per_request_display_recipient_cache = {} # type: Dict[int, List[Dict[str, Any]]]
def get_display_recipient_by_id(recipient_id, recipient_type, recipient_type_id):
    # type: (int, int, int) -> Union[Text, List[Dict[str, Any]]]
    if recipient_id not in per_request_display_recipient_cache:
        result = get_display_recipient_remote_cache(recipient_id, recipient_type, recipient_type_id)
        per_request_display_recipient_cache[recipient_id] = result
    return per_request_display_recipient_cache[recipient_id]

def get_display_recipient(recipient):
    # type: (Recipient) -> Union[Text, List[Dict[str, Any]]]
    return get_display_recipient_by_id(
        recipient.id,
        recipient.type,
        recipient.type_id
    )

def flush_per_request_caches():
    # type: () -> None
    global per_request_display_recipient_cache
    per_request_display_recipient_cache = {}
    global per_request_realm_filters_cache
    per_request_realm_filters_cache = {}

@cache_with_key(lambda *args: display_recipient_cache_key(args[0]),
                timeout=3600*24*7)
def get_display_recipient_remote_cache(recipient_id, recipient_type, recipient_type_id):
    # type: (int, int, int) -> Union[Text, List[Dict[str, Any]]]
    """
    returns: an appropriate object describing the recipient.  For a
    stream this will be the stream name as a string.  For a huddle or
    personal, it will be an array of dicts about each recipient.
    """
    if recipient_type == Recipient.STREAM:
        stream = Stream.objects.get(id=recipient_type_id)
        return stream.name

    # We don't really care what the ordering is, just that it's deterministic.
    user_profile_list = (UserProfile.objects.filter(subscription__recipient_id=recipient_id)
                                            .select_related()
                                            .order_by('email'))
    return [{'email': user_profile.email,
             'domain': user_profile.realm.domain,
             'full_name': user_profile.full_name,
             'short_name': user_profile.short_name,
             'id': user_profile.id,
             'is_mirror_dummy': user_profile.is_mirror_dummy} for user_profile in user_profile_list]

def get_realm_emoji_cache_key(realm):
    # type: (Realm) -> Text
    return u'realm_emoji:%s' % (realm.id,)

class Realm(ModelReprMixin, models.Model):
    # domain is a domain in the Internet sense. It must be structured like a
    # valid email domain. We use is to restrict access, identify bots, etc.
    domain = models.CharField(max_length=40, db_index=True, unique=True) # type: Text
    # name is the user-visible identifier for the realm. It has no required
    # structure.
    AUTHENTICATION_FLAGS = [u'Google', u'Email', u'GitHub', u'LDAP', u'Dev', u'RemoteUser']

    name = models.CharField(max_length=40, null=True) # type: Optional[Text]
    string_id = models.CharField(max_length=40, unique=True) # type: Text
    restricted_to_domain = models.BooleanField(default=False) # type: bool
    invite_required = models.BooleanField(default=True) # type: bool
    invite_by_admins_only = models.BooleanField(default=False) # type: bool
    create_stream_by_admins_only = models.BooleanField(default=False) # type: bool
    add_emoji_by_admins_only = models.BooleanField(default=False) # type: bool
    mandatory_topics = models.BooleanField(default=False) # type: bool
    show_digest_email = models.BooleanField(default=True) # type: bool
    name_changes_disabled = models.BooleanField(default=False) # type: bool
    email_changes_disabled = models.BooleanField(default=False) # type: bool

    allow_message_editing = models.BooleanField(default=True) # type: bool
    DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS = 600 # if changed, also change in admin.js
    message_content_edit_limit_seconds = models.IntegerField(default=DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS) # type: int
    message_retention_days = models.IntegerField(null=True) # type: Optional[int]

    # Valid org_types are {CORPORATE, COMMUNITY}
    CORPORATE = 1
    COMMUNITY = 2
    org_type = models.PositiveSmallIntegerField(default=COMMUNITY) # type: int

    date_created = models.DateTimeField(default=timezone.now) # type: datetime.datetime
    notifications_stream = models.ForeignKey('Stream', related_name='+', null=True, blank=True) # type: Optional[Stream]
    deactivated = models.BooleanField(default=False) # type: bool
    default_language = models.CharField(default=u'en', max_length=MAX_LANGUAGE_ID_LENGTH) # type: Text
    authentication_methods = BitField(flags=AUTHENTICATION_FLAGS,
                                      default=2**31 - 1) # type: BitHandler
    waiting_period_threshold = models.PositiveIntegerField(default=0) # type: int

    ICON_FROM_GRAVATAR = u'G'
    ICON_UPLOADED = u'U'
    ICON_SOURCES = (
        (ICON_FROM_GRAVATAR, 'Hosted by Gravatar'),
        (ICON_UPLOADED, 'Uploaded by administrator'),
    )
    icon_source = models.CharField(default=ICON_FROM_GRAVATAR, choices=ICON_SOURCES,
                                   max_length=1)  # type: Text
    icon_version = models.PositiveSmallIntegerField(default=1)  # type: int

    DEFAULT_NOTIFICATION_STREAM_NAME = u'announce'

    def authentication_methods_dict(self):
        # type: () -> Dict[Text, bool]
        """Returns the a mapping from authentication flags to their status,
        showing only those authentication flags that are supported on
        the current server (i.e. if EmailAuthBackend is not configured
        on the server, this will not return an entry for "Email")."""
        # This mapping needs to be imported from here due to the cyclic
        # dependency.
        from zproject.backends import AUTH_BACKEND_NAME_MAP

        ret = {} # type: Dict[Text, bool]
        supported_backends = {backend.__class__ for backend in django.contrib.auth.get_backends()}
        for k, v in self.authentication_methods.iteritems():
            backend = AUTH_BACKEND_NAME_MAP[k]
            if backend in supported_backends:
                ret[k] = v
        return ret

    def __unicode__(self):
        # type: () -> Text
        return u"<Realm: %s %s>" % (self.string_id, self.id)

    @cache_with_key(get_realm_emoji_cache_key, timeout=3600*24*7)
    def get_emoji(self):
        # type: () -> Dict[Text, Optional[Dict[str, Text]]]
        return get_realm_emoji_uncached(self)

    def get_admin_users(self):
        # type: () -> Sequence[UserProfile]
        # TODO: Change return type to QuerySet[UserProfile]
        return UserProfile.objects.filter(realm=self, is_realm_admin=True,
                                          is_active=True).select_related()

    def get_active_users(self):
        # type: () -> Sequence[UserProfile]
        # TODO: Change return type to QuerySet[UserProfile]
        return UserProfile.objects.filter(realm=self, is_active=True).select_related()

    def get_bot_domain(self):
        # type: () -> str
        # Remove the port. Mainly needed for development environment.
        external_host = settings.EXTERNAL_HOST.split(':')[0]
        if settings.REALMS_HAVE_SUBDOMAINS or \
           Realm.objects.filter(deactivated=False) \
                        .exclude(string_id__in=settings.SYSTEM_ONLY_REALMS).count() > 1:
            return "%s.%s" % (self.string_id, external_host)
        return external_host

    @property
    def subdomain(self):
        # type: () -> Optional[Text]
        if settings.REALMS_HAVE_SUBDOMAINS:
            return self.string_id
        return None

    @property
    def uri(self):
        # type: () -> str
        if settings.REALMS_HAVE_SUBDOMAINS and self.subdomain is not None:
            return '%s%s.%s' % (settings.EXTERNAL_URI_SCHEME,
                                self.subdomain, settings.EXTERNAL_HOST)
        return settings.SERVER_URI

    @property
    def host(self):
        # type: () -> str
        if settings.REALMS_HAVE_SUBDOMAINS and self.subdomain is not None:
            return "%s.%s" % (self.subdomain, settings.EXTERNAL_HOST)
        return settings.EXTERNAL_HOST

    @property
    def is_zephyr_mirror_realm(self):
        # type: () -> bool
        return self.string_id == "zephyr"

    @property
    def webathena_enabled(self):
        # type: () -> bool
        return self.is_zephyr_mirror_realm

    @property
    def presence_disabled(self):
        # type: () -> bool
        return self.is_zephyr_mirror_realm

    class Meta(object):
        permissions = (
            ('administer', "Administer a realm"),
            ('api_super_user', "Can send messages as other users for mirroring"),
        )

post_save.connect(flush_realm, sender=Realm)

def get_realm(string_id):
    # type: (Text) -> Realm
    return Realm.objects.filter(string_id=string_id).first()

def completely_open(realm):
    # type: (Realm) -> bool
    # This realm is completely open to everyone on the internet to
    # join. E-mail addresses do not need to match a realmalias and
    # an invite from an existing user is not required.
    if not realm:
        return False
    return not realm.invite_required and not realm.restricted_to_domain

def get_unique_open_realm():
    # type: () -> Optional[Realm]
    """We only return a realm if there is a unique non-system-only realm,
    it is completely open, and there are no subdomains."""
    if settings.REALMS_HAVE_SUBDOMAINS:
        return None
    realms = Realm.objects.filter(deactivated=False)
    # On production installations, the (usually "zulip.com") system
    # realm is an empty realm just used for system bots, so don't
    # include it in this accounting.
    realms = realms.exclude(string_id__in=settings.SYSTEM_ONLY_REALMS)
    if len(realms) != 1:
        return None
    realm = realms[0]
    if realm.invite_required or realm.restricted_to_domain:
        return None
    return realm

def name_changes_disabled(realm):
    # type: (Optional[Realm]) -> bool
    if realm is None:
        return settings.NAME_CHANGES_DISABLED
    return settings.NAME_CHANGES_DISABLED or realm.name_changes_disabled

class RealmAlias(models.Model):
    realm = models.ForeignKey(Realm) # type: Realm
    # should always be stored lowercase
    domain = models.CharField(max_length=80, db_index=True) # type: Text
    allow_subdomains = models.BooleanField(default=False)

    class Meta(object):
        unique_together = ("realm", "domain")

def can_add_alias(domain):
    # type: (Text) -> bool
    if settings.REALMS_HAVE_SUBDOMAINS:
        return True
    if RealmAlias.objects.filter(domain=domain).exists():
        return False
    return True

# These functions should only be used on email addresses that have
# been validated via django.core.validators.validate_email
#
# Note that we need to use some care, since can you have multiple @-signs; e.g.
# "tabbott@test"@zulip.com
# is valid email address
def email_to_username(email):
    # type: (Text) -> Text
    return "@".join(email.split("@")[:-1]).lower()

# Returns the raw domain portion of the desired email address
def email_to_domain(email):
    # type: (Text) -> Text
    return email.split("@")[-1].lower()

class GetRealmByDomainException(Exception):
    pass

def get_realm_by_email_domain(email):
    # type: (Text) -> Optional[Realm]
    if settings.REALMS_HAVE_SUBDOMAINS:
        raise GetRealmByDomainException(
            "Cannot get realm from email domain when settings.REALMS_HAVE_SUBDOMAINS = True")
    domain = email_to_domain(email)
    query = RealmAlias.objects.select_related('realm')
    # Search for the longest match. If found return immediately. Since in case of
    # settings.REALMS_HAVE_SUBDOMAINS=True, we have a unique mapping between the
    # realm and domain so don't worry about `allow_subdomains` being True or False.
    alias = query.filter(domain=domain).first()
    if alias is not None:
        return alias.realm
    else:
        # Since we have not found any match. We will now try matching the parent domain.
        # Filter out the realm domains with `allow_subdomains=False` so that we don't end
        # up matching 'test.zulip.com' wrongly to (realm, 'zulip.com', False).
        query = query.filter(allow_subdomains=True)
        while len(domain) > 0:
            subdomain, sep, domain = domain.partition('.')
            alias = query.filter(domain=domain).first()
            if alias is not None:
                return alias.realm
    return None

# Is a user with the given email address allowed to be in the given realm?
# (This function does not check whether the user has been invited to the realm.
# So for invite-only realms, this is the test for whether a user can be invited,
# not whether the user can sign up currently.)
def email_allowed_for_realm(email, realm):
    # type: (Text, Realm) -> bool
    if not realm.restricted_to_domain:
        return True
    domain = email_to_domain(email)
    query = RealmAlias.objects.filter(realm=realm)
    if query.filter(domain=domain).exists():
        return True
    else:
        query = query.filter(allow_subdomains=True)
        while len(domain) > 0:
            subdomain, sep, domain = domain.partition('.')
            if query.filter(domain=domain).exists():
                return True
    return False

def list_of_domains_for_realm(realm):
    # type: (Realm) -> List[Dict[str, Union[str, bool]]]
    return list(RealmAlias.objects.filter(realm=realm).values('domain', 'allow_subdomains'))

class RealmEmoji(ModelReprMixin, models.Model):
    author = models.ForeignKey('UserProfile', blank=True, null=True)
    realm = models.ForeignKey(Realm) # type: Realm
    # Second part of the regex (negative lookbehind) disallows names ending with one of the punctuation characters
    name = models.TextField(validators=[MinLengthValidator(1),
                                        RegexValidator(regex=r'^[0-9a-zA-Z.\-_]+(?<![.\-_])$',
                                                       message=_("Invalid characters in emoji name"))]) # type: Text
    # URLs start having browser compatibility problem below 2000
    # characters, so 1000 seems like a safe limit.
    img_url = models.URLField(max_length=1000) # type: Text

    class Meta(object):
        unique_together = ("realm", "name")

    def __unicode__(self):
        # type: () -> Text
        return u"<RealmEmoji(%s): %s %s>" % (self.realm.string_id, self.name, self.img_url)

def get_realm_emoji_uncached(realm):
    # type: (Realm) -> Dict[Text, Optional[Dict[str, Text]]]
    d = {}
    for row in RealmEmoji.objects.filter(realm=realm).select_related('author'):
        if row.author:
            author = {
                'id': row.author.id,
                'email': row.author.email,
                'full_name': row.author.full_name}
        else:
            author = None
        d[row.name] = dict(source_url=row.img_url,
                           display_url=get_camo_url(row.img_url),
                           author=author)
    return d

def flush_realm_emoji(sender, **kwargs):
    # type: (Any, **Any) -> None
    realm = kwargs['instance'].realm
    cache_set(get_realm_emoji_cache_key(realm),
              get_realm_emoji_uncached(realm),
              timeout=3600*24*7)

post_save.connect(flush_realm_emoji, sender=RealmEmoji)
post_delete.connect(flush_realm_emoji, sender=RealmEmoji)

def filter_pattern_validator(value):
    # type: (Text) -> None
    regex = re.compile(r'(?:[\w\-#]*)(\(\?P<\w+>.+\))')
    error_msg = 'Invalid filter pattern, you must use the following format OPTIONAL_PREFIX(?P<id>.+)'

    if not regex.match(str(value)):
        raise ValidationError(error_msg)

    try:
        re.compile(value)
    except sre_constants.error:
        # Regex is invalid
        raise ValidationError(error_msg)

def filter_format_validator(value):
    # type: (str) -> None
    regex = re.compile(r'^[\.\/:a-zA-Z0-9_-]+%\(([a-zA-Z0-9_-]+)\)s[a-zA-Z0-9_-]*$')

    if not regex.match(value):
        raise ValidationError('URL format string must be in the following format: `https://example.com/%(\w+)s`')

class RealmFilter(models.Model):
    realm = models.ForeignKey(Realm) # type: Realm
    pattern = models.TextField(validators=[filter_pattern_validator]) # type: Text
    url_format_string = models.TextField(validators=[URLValidator, filter_format_validator]) # type: Text

    class Meta(object):
        unique_together = ("realm", "pattern")

    def __unicode__(self):
        # type: () -> Text
        return u"<RealmFilter(%s): %s %s>" % (self.realm.string_id, self.pattern, self.url_format_string)

def get_realm_filters_cache_key(realm_id):
    # type: (int) -> Text
    return u'all_realm_filters:%s' % (realm_id,)

# We have a per-process cache to avoid doing 1000 remote cache queries during page load
per_request_realm_filters_cache = {} # type: Dict[int, List[Tuple[Text, Text, int]]]

def realm_in_local_realm_filters_cache(realm_id):
    # type: (int) -> bool
    return realm_id in per_request_realm_filters_cache

def realm_filters_for_realm(realm_id):
    # type: (int) -> List[Tuple[Text, Text, int]]
    if not realm_in_local_realm_filters_cache(realm_id):
        per_request_realm_filters_cache[realm_id] = realm_filters_for_realm_remote_cache(realm_id)
    return per_request_realm_filters_cache[realm_id]

@cache_with_key(get_realm_filters_cache_key, timeout=3600*24*7)
def realm_filters_for_realm_remote_cache(realm_id):
    # type: (int) -> List[Tuple[Text, Text, int]]
    filters = []
    for realm_filter in RealmFilter.objects.filter(realm_id=realm_id):
        filters.append((realm_filter.pattern, realm_filter.url_format_string, realm_filter.id))

    return filters

def all_realm_filters():
    # type: () -> Dict[int, List[Tuple[Text, Text, int]]]
    filters = defaultdict(list) # type: Dict[int, List[Tuple[Text, Text, int]]]
    for realm_filter in RealmFilter.objects.all():
        filters[realm_filter.realm_id].append((realm_filter.pattern, realm_filter.url_format_string, realm_filter.id))

    return filters

def flush_realm_filter(sender, **kwargs):
    # type: (Any, **Any) -> None
    realm_id = kwargs['instance'].realm_id
    cache_delete(get_realm_filters_cache_key(realm_id))
    try:
        per_request_realm_filters_cache.pop(realm_id)
    except KeyError:
        pass

post_save.connect(flush_realm_filter, sender=RealmFilter)
post_delete.connect(flush_realm_filter, sender=RealmFilter)

class UserProfile(ModelReprMixin, AbstractBaseUser, PermissionsMixin):
    DEFAULT_BOT = 1
    """
    Incoming webhook bots are limited to only sending messages via webhooks.
    Thus, it is less of a security risk to expose their API keys to third-party services,
    since they can't be used to read messages.
    """
    INCOMING_WEBHOOK_BOT = 2

    # Fields from models.AbstractUser minus last_name and first_name,
    # which we don't use; email is modified to make it indexed and unique.
    email = models.EmailField(blank=False, db_index=True, unique=True) # type: Text
    is_staff = models.BooleanField(default=False) # type: bool
    is_active = models.BooleanField(default=True, db_index=True) # type: bool
    is_realm_admin = models.BooleanField(default=False, db_index=True) # type: bool
    is_bot = models.BooleanField(default=False, db_index=True) # type: bool
    bot_type = models.PositiveSmallIntegerField(null=True, db_index=True) # type: Optional[int]
    is_api_super_user = models.BooleanField(default=False, db_index=True) # type: bool
    date_joined = models.DateTimeField(default=timezone.now) # type: datetime.datetime
    is_mirror_dummy = models.BooleanField(default=False) # type: bool
    bot_owner = models.ForeignKey('self', null=True, on_delete=models.SET_NULL) # type: Optional[UserProfile]

    USERNAME_FIELD = 'email'
    MAX_NAME_LENGTH = 100
    NAME_INVALID_CHARS = ['*', '`', '>', '"', '@']

    # Our custom site-specific fields
    full_name = models.CharField(max_length=MAX_NAME_LENGTH) # type: Text
    short_name = models.CharField(max_length=MAX_NAME_LENGTH) # type: Text
    # pointer points to Message.id, NOT UserMessage.id.
    pointer = models.IntegerField() # type: int
    last_pointer_updater = models.CharField(max_length=64) # type: Text
    realm = models.ForeignKey(Realm) # type: Realm
    api_key = models.CharField(max_length=32) # type: Text
    tos_version = models.CharField(null=True, max_length=10) # type: Text

    ### Notifications settings. ###

    # Stream notifications.
    enable_stream_desktop_notifications = models.BooleanField(default=False) # type: bool
    enable_stream_sounds = models.BooleanField(default=False) # type: bool

    # PM + @-mention notifications.
    enable_desktop_notifications = models.BooleanField(default=True) # type: bool
    pm_content_in_desktop_notifications = models.BooleanField(default=True)  # type: bool
    enable_sounds = models.BooleanField(default=True) # type: bool
    enable_offline_email_notifications = models.BooleanField(default=True) # type: bool
    enable_offline_push_notifications = models.BooleanField(default=True) # type: bool
    enable_online_push_notifications = models.BooleanField(default=False) # type: bool

    enable_digest_emails = models.BooleanField(default=True) # type: bool

    # Old notification field superseded by existence of stream notification
    # settings.
    default_desktop_notifications = models.BooleanField(default=True) # type: bool

    ###

    last_reminder = models.DateTimeField(default=timezone.now, null=True) # type: Optional[datetime.datetime]
    rate_limits = models.CharField(default=u"", max_length=100) # type: Text # comma-separated list of range:max pairs

    # Default streams
    default_sending_stream = models.ForeignKey('zerver.Stream', null=True, related_name='+') # type: Optional[Stream]
    default_events_register_stream = models.ForeignKey('zerver.Stream', null=True, related_name='+') # type: Optional[Stream]
    default_all_public_streams = models.BooleanField(default=False) # type: bool

    # UI vars
    enter_sends = models.NullBooleanField(default=False) # type: Optional[bool]
    autoscroll_forever = models.BooleanField(default=False) # type: bool
    left_side_userlist = models.BooleanField(default=False) # type: bool
    emoji_alt_code = models.BooleanField(default=False) # type: bool

    # display settings
    twenty_four_hour_time = models.BooleanField(default=False) # type: bool
    default_language = models.CharField(default=u'en', max_length=MAX_LANGUAGE_ID_LENGTH) # type: Text

    # Hours to wait before sending another email to a user
    EMAIL_REMINDER_WAITPERIOD = 24
    # Minutes to wait before warning a bot owner that her bot sent a message
    # to a nonexistent stream
    BOT_OWNER_STREAM_ALERT_WAITPERIOD = 1

    AVATAR_FROM_GRAVATAR = u'G'
    AVATAR_FROM_USER = u'U'
    AVATAR_SOURCES = (
        (AVATAR_FROM_GRAVATAR, 'Hosted by Gravatar'),
        (AVATAR_FROM_USER, 'Uploaded by user'),
    )
    avatar_source = models.CharField(default=AVATAR_FROM_GRAVATAR, choices=AVATAR_SOURCES, max_length=1) # type: Text
    avatar_version = models.PositiveSmallIntegerField(default=1) # type: int

    TUTORIAL_WAITING  = u'W'
    TUTORIAL_STARTED  = u'S'
    TUTORIAL_FINISHED = u'F'
    TUTORIAL_STATES   = ((TUTORIAL_WAITING, "Waiting"),
                         (TUTORIAL_STARTED, "Started"),
                         (TUTORIAL_FINISHED, "Finished"))

    tutorial_status = models.CharField(default=TUTORIAL_WAITING, choices=TUTORIAL_STATES, max_length=1) # type: Text
    # Contains serialized JSON of the form:
    #    [("step 1", true), ("step 2", false)]
    # where the second element of each tuple is if the step has been
    # completed.
    onboarding_steps = models.TextField(default=u'[]') # type: Text

    invites_granted = models.IntegerField(default=0) # type: int
    invites_used = models.IntegerField(default=0) # type: int

    alert_words = models.TextField(default=u'[]') # type: Text # json-serialized list of strings

    # Contains serialized JSON of the form:
    # [["social", "mit"], ["devel", "ios"]]
    muted_topics = models.TextField(default=u'[]') # type: Text

    objects = UserManager() # type: UserManager

    DEFAULT_UPLOADS_QUOTA = 1024*1024*1024

    quota = models.IntegerField(default=DEFAULT_UPLOADS_QUOTA) # type: int

    def can_admin_user(self, target_user):
        # type: (UserProfile) -> bool
        """Returns whether this user has permission to modify target_user"""
        if target_user.bot_owner == self:
            return True
        elif self.is_realm_admin and self.realm == target_user.realm:
            return True
        else:
            return False

    def __unicode__(self):
        # type: () -> Text
        return u"<UserProfile: %s %s>" % (self.email, self.realm)

    @property
    def is_incoming_webhook(self):
        # type: () -> bool
        return self.bot_type == UserProfile.INCOMING_WEBHOOK_BOT

    @staticmethod
    def emails_from_ids(user_ids):
        # type: (Sequence[int]) -> Dict[int, Text]
        rows = UserProfile.objects.filter(id__in=user_ids).values('id', 'email')
        return {row['id']: row['email'] for row in rows}

    def can_create_streams(self):
        # type: () -> bool
        diff = (timezone.now() - self.date_joined).days
        if self.is_realm_admin:
            return True
        elif self.realm.create_stream_by_admins_only:
            return False
        if diff >= self.realm.waiting_period_threshold:
            return True
        return False

    def major_tos_version(self):
        # type: () -> int
        if self.tos_version is not None:
            return int(self.tos_version.split('.')[0])
        else:
            return -1

def receives_offline_notifications(user_profile):
    # type: (UserProfile) -> bool
    return ((user_profile.enable_offline_email_notifications or
             user_profile.enable_offline_push_notifications) and
            not user_profile.is_bot)

def receives_online_notifications(user_profile):
    # type: (UserProfile) -> bool
    return (user_profile.enable_online_push_notifications and
            not user_profile.is_bot)

def remote_user_to_email(remote_user):
    # type: (Text) -> Text
    if settings.SSO_APPEND_DOMAIN is not None:
        remote_user += "@" + settings.SSO_APPEND_DOMAIN
    return remote_user

# Make sure we flush the UserProfile object from our remote cache
# whenever we save it.
post_save.connect(flush_user_profile, sender=UserProfile)

class PreregistrationUser(models.Model):
    email = models.EmailField() # type: Text
    referred_by = models.ForeignKey(UserProfile, null=True) # Optional[UserProfile]
    streams = models.ManyToManyField('Stream') # type: Manager
    invited_at = models.DateTimeField(auto_now=True) # type: datetime.datetime
    realm_creation = models.BooleanField(default=False)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_ACTIVE
    status = models.IntegerField(default=0) # type: int

    realm = models.ForeignKey(Realm, null=True) # type: Optional[Realm]

class EmailChangeStatus(models.Model):
    new_email = models.EmailField() # type: Text
    old_email = models.EmailField() # type: Text
    updated_at = models.DateTimeField(auto_now=True) # type: datetime.datetime
    user_profile = models.ForeignKey(UserProfile) # type: UserProfile

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_ACTIVE
    status = models.IntegerField(default=0) # type: int

    realm = models.ForeignKey(Realm) # type: Realm

class PushDeviceToken(models.Model):
    APNS = 1
    GCM = 2

    KINDS = (
        (APNS, 'apns'),
        (GCM, 'gcm'),
    )

    kind = models.PositiveSmallIntegerField(choices=KINDS) # type: int

    # The token is a unique device-specific token that is
    # sent to us from each device:
    #   - APNS token if kind == APNS
    #   - GCM registration id if kind == GCM
    token = models.CharField(max_length=4096, unique=True) # type: bytes
    last_updated = models.DateTimeField(auto_now=True) # type: datetime.datetime

    # The user who's device this is
    user = models.ForeignKey(UserProfile, db_index=True) # type: UserProfile

    # [optional] Contains the app id of the device if it is an iOS device
    ios_app_id = models.TextField(null=True) # type: Optional[Text]

def generate_email_token_for_stream():
    # type: () -> Text
    return generate_random_token(32)

class Stream(ModelReprMixin, models.Model):
    MAX_NAME_LENGTH = 60
    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True) # type: Text
    realm = models.ForeignKey(Realm, db_index=True) # type: Realm
    invite_only = models.NullBooleanField(default=False) # type: Optional[bool]
    # Used by the e-mail forwarder. The e-mail RFC specifies a maximum
    # e-mail length of 254, and our max stream length is 30, so we
    # have plenty of room for the token.
    email_token = models.CharField(
        max_length=32, default=generate_email_token_for_stream) # type: Text
    description = models.CharField(max_length=1024, default=u'') # type: Text

    date_created = models.DateTimeField(default=timezone.now) # type: datetime.datetime
    deactivated = models.BooleanField(default=False) # type: bool

    def __unicode__(self):
        # type: () -> Text
        return u"<Stream: %s>" % (self.name,)

    def is_public(self):
        # type: () -> bool
        # All streams are private in Zephyr mirroring realms.
        return not self.invite_only and not self.realm.is_zephyr_mirror_realm

    class Meta(object):
        unique_together = ("name", "realm")

    def num_subscribers(self):
        # type: () -> int
        return Subscription.objects.filter(
            recipient__type=Recipient.STREAM,
            recipient__type_id=self.id,
            user_profile__is_active=True,
            active=True
        ).count()

    # This is stream information that is sent to clients
    def to_dict(self):
        # type: () -> Dict[str, Any]
        return dict(name=self.name,
                    stream_id=self.id,
                    description=self.description,
                    invite_only=self.invite_only)

post_save.connect(flush_stream, sender=Stream)
post_delete.connect(flush_stream, sender=Stream)

# The Recipient table is used to map Messages to the set of users who
# received the message.  It is implemented as a set of triples (id,
# type_id, type). We have 3 types of recipients: Huddles (for group
# private messages), UserProfiles (for 1:1 private messages), and
# Streams. The recipient table maps a globally unique recipient id
# (used by the Message table) to the type-specific unique id (the
# stream id, user_profile id, or huddle id).
class Recipient(ModelReprMixin, models.Model):
    type_id = models.IntegerField(db_index=True) # type: int
    type = models.PositiveSmallIntegerField(db_index=True) # type: int
    # Valid types are {personal, stream, huddle}
    PERSONAL = 1
    STREAM = 2
    HUDDLE = 3

    class Meta(object):
        unique_together = ("type", "type_id")

    # N.B. If we used Django's choice=... we would get this for free (kinda)
    _type_names = {
        PERSONAL: 'personal',
        STREAM: 'stream',
        HUDDLE: 'huddle'}

    def type_name(self):
        # type: () -> str
        # Raises KeyError if invalid
        return self._type_names[self.type]

    def __unicode__(self):
        # type: () -> Text
        display_recipient = get_display_recipient(self)
        return u"<Recipient: %s (%d, %s)>" % (display_recipient, self.type_id, self.type)

class Client(ModelReprMixin, models.Model):
    name = models.CharField(max_length=30, db_index=True, unique=True) # type: Text

    def __unicode__(self):
        # type: () -> Text
        return u"<Client: %s>" % (self.name,)

get_client_cache = {} # type: Dict[Text, Client]
def get_client(name):
    # type: (Text) -> Client
    # Accessing KEY_PREFIX through the module is necessary
    # because we need the updated value of the variable.
    cache_name = cache.KEY_PREFIX + name
    if cache_name not in get_client_cache:
        result = get_client_remote_cache(name)
        get_client_cache[cache_name] = result
    return get_client_cache[cache_name]

def get_client_cache_key(name):
    # type: (Text) -> Text
    return u'get_client:%s' % (make_safe_digest(name),)

@cache_with_key(get_client_cache_key, timeout=3600*24*7)
def get_client_remote_cache(name):
    # type: (Text) -> Client
    (client, _) = Client.objects.get_or_create(name=name)
    return client

# get_stream_backend takes either a realm id or a realm
@cache_with_key(get_stream_cache_key, timeout=3600*24*7)
def get_stream_backend(stream_name, realm):
    # type: (Text, Realm) -> Stream
    return Stream.objects.select_related("realm").get(
        name__iexact=stream_name.strip(), realm_id=realm.id)

def get_active_streams(realm):
    # type: (Realm) -> QuerySet
    """
    Return all streams (including invite-only streams) that have not been deactivated.
    """
    return Stream.objects.filter(realm=realm, deactivated=False)

def get_stream(stream_name, realm):
    # type: (Text, Realm) -> Optional[Stream]
    try:
        return get_stream_backend(stream_name, realm)
    except Stream.DoesNotExist:
        return None

def bulk_get_streams(realm, stream_names):
    # type: (Realm, STREAM_NAMES) -> Dict[Text, Any]

    def fetch_streams_by_name(stream_names):
        # type: (List[Text]) -> Sequence[Stream]
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

    return generic_bulk_cached_fetch(lambda stream_name: get_stream_cache_key(stream_name, realm),
                                     fetch_streams_by_name,
                                     [stream_name.lower() for stream_name in stream_names],
                                     id_fetcher=lambda stream: stream.name.lower())

def get_recipient_cache_key(type, type_id):
    # type: (int, int) -> Text
    return u"get_recipient:%s:%s" % (type, type_id,)

@cache_with_key(get_recipient_cache_key, timeout=3600*24*7)
def get_recipient(type, type_id):
    # type: (int, int) -> Recipient
    return Recipient.objects.get(type_id=type_id, type=type)

def bulk_get_recipients(type, type_ids):
    # type: (int, List[int]) -> Dict[int, Any]
    def cache_key_function(type_id):
        # type: (int) -> Text
        return get_recipient_cache_key(type, type_id)

    def query_function(type_ids):
        # type: (List[int]) -> Sequence[Recipient]
        # TODO: Change return type to QuerySet[Recipient]
        return Recipient.objects.filter(type=type, type_id__in=type_ids)

    return generic_bulk_cached_fetch(cache_key_function, query_function, type_ids,
                                     id_fetcher=lambda recipient: recipient.type_id)


def sew_messages_and_reactions(messages, reactions):
    # type: (List[Dict[str, Any]], List[Dict[str, Any]]) -> List[Dict[str, Any]]
    """Given a iterable of messages and reactions stitch reactions
    into messages.
    """
    # Add all messages with empty reaction item
    for message in messages:
        message['reactions'] = []

    # Convert list of messages into dictionary to make reaction stitching easy
    converted_messages = {message['id']: message for message in messages}

    for reaction in reactions:
        converted_messages[reaction['message_id']]['reactions'].append(
            reaction)

    return list(converted_messages.values())


class Message(ModelReprMixin, models.Model):
    sender = models.ForeignKey(UserProfile) # type: UserProfile
    recipient = models.ForeignKey(Recipient) # type: Recipient
    subject = models.CharField(max_length=MAX_SUBJECT_LENGTH, db_index=True) # type: Text
    content = models.TextField() # type: Text
    rendered_content = models.TextField(null=True) # type: Optional[Text]
    rendered_content_version = models.IntegerField(null=True) # type: Optional[int]
    pub_date = models.DateTimeField('date published', db_index=True) # type: datetime.datetime
    sending_client = models.ForeignKey(Client) # type: Client
    last_edit_time = models.DateTimeField(null=True) # type: Optional[datetime.datetime]
    edit_history = models.TextField(null=True) # type: Optional[Text]
    has_attachment = models.BooleanField(default=False, db_index=True) # type: bool
    has_image = models.BooleanField(default=False, db_index=True) # type: bool
    has_link = models.BooleanField(default=False, db_index=True) # type: bool

    def topic_name(self):
        # type: () -> Text
        """
        Please start using this helper to facilitate an
        eventual switch over to a separate topic table.
        """
        return self.subject

    def __unicode__(self):
        # type: () -> Text
        display_recipient = get_display_recipient(self.recipient)
        return u"<Message: %s / %s / %r>" % (display_recipient, self.subject, self.sender)

    def get_realm(self):
        # type: () -> Realm
        return self.sender.realm

    def save_rendered_content(self):
        # type: () -> None
        self.save(update_fields=["rendered_content", "rendered_content_version"])

    @staticmethod
    def need_to_render_content(rendered_content, rendered_content_version, bugdown_version):
        # type: (Optional[Text], Optional[int], int) -> bool
        return (rendered_content is None or
                rendered_content_version is None or
                rendered_content_version < bugdown_version)

    def to_log_dict(self):
        # type: () -> Dict[str, Any]
        return dict(
            id                = self.id,
            sender_id         = self.sender.id,
            sender_email      = self.sender.email,
            sender_domain     = self.sender.realm.domain,
            sender_full_name  = self.sender.full_name,
            sender_short_name = self.sender.short_name,
            sending_client    = self.sending_client.name,
            type              = self.recipient.type_name(),
            recipient         = get_display_recipient(self.recipient),
            subject           = self.topic_name(),
            content           = self.content,
            timestamp         = datetime_to_timestamp(self.pub_date))

    @staticmethod
    def get_raw_db_rows(needed_ids):
        # type: (List[int]) -> List[Dict[str, Any]]
        # This is a special purpose function optimized for
        # callers like get_old_messages_backend().
        fields = [
            'id',
            'subject',
            'pub_date',
            'last_edit_time',
            'edit_history',
            'content',
            'rendered_content',
            'rendered_content_version',
            'recipient_id',
            'recipient__type',
            'recipient__type_id',
            'sender_id',
            'sending_client__name',
            'sender__email',
            'sender__full_name',
            'sender__short_name',
            'sender__realm__id',
            'sender__realm__domain',
            'sender__avatar_source',
            'sender__avatar_version',
            'sender__is_mirror_dummy',
        ]
        messages = Message.objects.filter(id__in=needed_ids).values(*fields)
        """Adding one-many or Many-Many relationship in values results in N X
        results.

        Link: https://docs.djangoproject.com/en/1.8/ref/models/querysets/#values
        """
        reactions = Reaction.get_raw_db_rows(needed_ids)
        return sew_messages_and_reactions(messages, reactions)

    def sent_by_human(self):
        # type: () -> bool
        sending_client = self.sending_client.name.lower()

        return (sending_client in ('zulipandroid', 'zulipios', 'zulipdesktop',
                                   'zulipmobile', 'zulipelectron', 'snipe',
                                   'website', 'ios', 'android')) or (
                                       'desktop app' in sending_client)

    @staticmethod
    def content_has_attachment(content):
        # type: (Text) -> Match
        return re.search(r'[/\-]user[\-_]uploads[/\.-]', content)

    @staticmethod
    def content_has_image(content):
        # type: (Text) -> bool
        return bool(re.search(r'[/\-]user[\-_]uploads[/\.-]\S+\.(bmp|gif|jpg|jpeg|png|webp)', content, re.IGNORECASE))

    @staticmethod
    def content_has_link(content):
        # type: (Text) -> bool
        return ('http://' in content or
                'https://' in content or
                '/user_uploads' in content or
                (settings.ENABLE_FILE_LINKS and 'file:///' in content))

    @staticmethod
    def is_status_message(content, rendered_content):
        # type: (Text, Text) -> bool
        """
        Returns True if content and rendered_content are from 'me_message'
        """
        if content.startswith('/me ') and '\n' not in content:
            if rendered_content.startswith('<p>') and rendered_content.endswith('</p>'):
                return True
        return False

    def update_calculated_fields(self):
        # type: () -> None
        # TODO: rendered_content could also be considered a calculated field
        content = self.content
        self.has_attachment = bool(Message.content_has_attachment(content))
        self.has_image = bool(Message.content_has_image(content))
        self.has_link = bool(Message.content_has_link(content))

@receiver(pre_save, sender=Message)
def pre_save_message(sender, **kwargs):
    # type: (Any, **Any) -> None
    if kwargs['update_fields'] is None or "content" in kwargs['update_fields']:
        message = kwargs['instance']
        message.update_calculated_fields()

def get_context_for_message(message):
    # type: (Message) -> QuerySet[Message]
    # TODO: Change return type to QuerySet[Message]
    return Message.objects.filter(
        recipient_id=message.recipient_id,
        subject=message.subject,
        id__lt=message.id,
        pub_date__gt=message.pub_date - timedelta(minutes=15),
    ).order_by('-id')[:10]

post_save.connect(flush_message, sender=Message)

class Reaction(ModelReprMixin, models.Model):
    user_profile = models.ForeignKey(UserProfile) # type: UserProfile
    message = models.ForeignKey(Message) # type: Message
    emoji_name = models.TextField() # type: Text

    class Meta(object):
        unique_together = ("user_profile", "message", "emoji_name")

    @staticmethod
    def get_raw_db_rows(needed_ids):
        # type: (List[int]) -> List[Dict[str, Any]]
        fields = ['message_id', 'emoji_name', 'user_profile__email',
                  'user_profile__id', 'user_profile__full_name']
        return Reaction.objects.filter(message_id__in=needed_ids).values(*fields)

# Whenever a message is sent, for each user current subscribed to the
# corresponding Recipient object, we add a row to the UserMessage
# table, which has has columns (id, user profile id, message id,
# flags) indicating which messages each user has received.  This table
# allows us to quickly query any user's last 1000 messages to generate
# the home view.
#
# Additionally, the flags field stores metadata like whether the user
# has read the message, starred the message, collapsed or was
# mentioned the message, etc.
#
# UserMessage is the largest table in a Zulip installation, even
# though each row is only 4 integers.
class UserMessage(ModelReprMixin, models.Model):
    user_profile = models.ForeignKey(UserProfile) # type: UserProfile
    message = models.ForeignKey(Message) # type: Message
    # We're not using the archived field for now, but create it anyway
    # since this table will be an unpleasant one to do schema changes
    # on later
    ALL_FLAGS = ['read', 'starred', 'collapsed', 'mentioned', 'wildcard_mentioned',
                 'summarize_in_home', 'summarize_in_stream', 'force_expand', 'force_collapse',
                 'has_alert_word', "historical", 'is_me_message']
    flags = BitField(flags=ALL_FLAGS, default=0) # type: BitHandler

    class Meta(object):
        unique_together = ("user_profile", "message")

    def __unicode__(self):
        # type: () -> Text
        display_recipient = get_display_recipient(self.message.recipient)
        return u"<UserMessage: %s / %s (%s)>" % (display_recipient, self.user_profile.email, self.flags_list())

    def flags_list(self):
        # type: () -> List[str]
        return [flag for flag in self.flags.keys() if getattr(self.flags, flag).is_set]

def parse_usermessage_flags(val):
    # type: (int) -> List[str]
    flags = []
    mask = 1
    for flag in UserMessage.ALL_FLAGS:
        if val & mask:
            flags.append(flag)
        mask <<= 1
    return flags

class Attachment(ModelReprMixin, models.Model):
    file_name = models.TextField(db_index=True) # type: Text
    # path_id is a storage location agnostic representation of the path of the file.
    # If the path of a file is http://localhost:9991/user_uploads/a/b/abc/temp_file.py
    # then its path_id will be a/b/abc/temp_file.py.
    path_id = models.TextField(db_index=True) # type: Text
    owner = models.ForeignKey(UserProfile) # type: UserProfile
    realm = models.ForeignKey(Realm, blank=True, null=True) # type: Realm
    is_realm_public = models.BooleanField(default=False) # type: bool
    messages = models.ManyToManyField(Message) # type: Manager
    create_time = models.DateTimeField(default=timezone.now, db_index=True) # type: datetime.datetime
    size = models.IntegerField(null=True) # type: int

    def __unicode__(self):
        # type: () -> Text
        return u"<Attachment: %s>" % (self.file_name,)

    def is_claimed(self):
        # type: () -> bool
        return self.messages.count() > 0

    def to_dict(self):
        # type: () -> Dict[str, Any]
        return {
            'id': self.id,
            'name': self.file_name,
            'path_id': self.path_id,
            'messages': [{
                'id': m.id,
                # convert to JavaScript-style UNIX timestamp so we can take
                # advantage of client timezones.
                'name': time.mktime(m.pub_date.timetuple()) * 1000
            } for m in self.messages.all()]
        }

def get_old_unclaimed_attachments(weeks_ago):
    # type: (int) -> Sequence[Attachment]
    # TODO: Change return type to QuerySet[Attachment]
    delta_weeks_ago = timezone.now() - datetime.timedelta(weeks=weeks_ago)
    old_attachments = Attachment.objects.filter(messages=None, create_time__lt=delta_weeks_ago)
    return old_attachments

class Subscription(ModelReprMixin, models.Model):
    user_profile = models.ForeignKey(UserProfile) # type: UserProfile
    recipient = models.ForeignKey(Recipient) # type: Recipient
    active = models.BooleanField(default=True) # type: bool
    in_home_view = models.NullBooleanField(default=True) # type: Optional[bool]

    DEFAULT_STREAM_COLOR = u"#c2c2c2"
    color = models.CharField(max_length=10, default=DEFAULT_STREAM_COLOR) # type: Text
    pin_to_top = models.BooleanField(default=False) # type: bool

    desktop_notifications = models.BooleanField(default=True) # type: bool
    audible_notifications = models.BooleanField(default=True) # type: bool

    # Combination desktop + audible notifications superseded by the
    # above.
    notifications = models.BooleanField(default=False) # type: bool

    class Meta(object):
        unique_together = ("user_profile", "recipient")

    def __unicode__(self):
        # type: () -> Text
        return u"<Subscription: %r -> %s>" % (self.user_profile, self.recipient)

@cache_with_key(user_profile_by_id_cache_key, timeout=3600*24*7)
def get_user_profile_by_id(uid):
    # type: (int) -> UserProfile
    return UserProfile.objects.select_related().get(id=uid)

@cache_with_key(user_profile_by_email_cache_key, timeout=3600*24*7)
def get_user_profile_by_email(email):
    # type: (Text) -> UserProfile
    return UserProfile.objects.select_related().get(email__iexact=email.strip())

@cache_with_key(active_user_dicts_in_realm_cache_key, timeout=3600*24*7)
def get_active_user_dicts_in_realm(realm):
    # type: (Realm) -> List[Dict[str, Any]]
    return UserProfile.objects.filter(realm=realm, is_active=True) \
                              .values(*active_user_dict_fields)

@cache_with_key(bot_dicts_in_realm_cache_key, timeout=3600*24*7)
def get_bot_dicts_in_realm(realm):
    # type: (Realm) -> List[Dict[str, Any]]
    return UserProfile.objects.filter(realm=realm, is_bot=True).values(*bot_dict_fields)

def get_owned_bot_dicts(user_profile, include_all_realm_bots_if_admin=True):
    # type: (UserProfile, bool) -> List[Dict[str, Any]]
    if user_profile.is_realm_admin and include_all_realm_bots_if_admin:
        result = get_bot_dicts_in_realm(user_profile.realm)
    else:
        result = UserProfile.objects.filter(realm=user_profile.realm, is_bot=True,
                                            bot_owner=user_profile).values(*bot_dict_fields)
    # TODO: Remove this import cycle
    from zerver.lib.avatar import get_avatar_url

    return [{'email': botdict['email'],
             'user_id': botdict['id'],
             'full_name': botdict['full_name'],
             'is_active': botdict['is_active'],
             'api_key': botdict['api_key'],
             'default_sending_stream': botdict['default_sending_stream__name'],
             'default_events_register_stream': botdict['default_events_register_stream__name'],
             'default_all_public_streams': botdict['default_all_public_streams'],
             'owner': botdict['bot_owner__email'],
             'avatar_url': get_avatar_url(botdict['avatar_source'], botdict['email'],
                                          botdict['avatar_version']),
             }
            for botdict in result]

def get_prereg_user_by_email(email):
    # type: (Text) -> PreregistrationUser
    # A user can be invited many times, so only return the result of the latest
    # invite.
    return PreregistrationUser.objects.filter(email__iexact=email.strip()).latest("invited_at")

def get_cross_realm_emails():
    # type: () -> Set[Text]
    return set(settings.CROSS_REALM_BOT_EMAILS)

# The Huddle class represents a group of individuals who have had a
# Group Private Message conversation together.  The actual membership
# of the Huddle is stored in the Subscription table just like with
# Streams, and a hash of that list is stored in the huddle_hash field
# below, to support efficiently mapping from a set of users to the
# corresponding Huddle object.
class Huddle(models.Model):
    # TODO: We should consider whether using
    # CommaSeparatedIntegerField would be better.
    huddle_hash = models.CharField(max_length=40, db_index=True, unique=True) # type: Text

def get_huddle_hash(id_list):
    # type: (List[int]) -> Text
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    return make_safe_digest(hash_key)

def huddle_hash_cache_key(huddle_hash):
    # type: (Text) -> Text
    return u"huddle_by_hash:%s" % (huddle_hash,)

def get_huddle(id_list):
    # type: (List[int]) -> Huddle
    huddle_hash = get_huddle_hash(id_list)
    return get_huddle_backend(huddle_hash, id_list)

@cache_with_key(lambda huddle_hash, id_list: huddle_hash_cache_key(huddle_hash), timeout=3600*24*7)
def get_huddle_backend(huddle_hash, id_list):
    # type: (Text, List[int]) -> Huddle
    with transaction.atomic():
        (huddle, created) = Huddle.objects.get_or_create(huddle_hash=huddle_hash)
        if created:
            recipient = Recipient.objects.create(type_id=huddle.id,
                                                 type=Recipient.HUDDLE)
            subs_to_create = [Subscription(recipient=recipient,
                                           user_profile=get_user_profile_by_id(user_profile_id))
                              for user_profile_id in id_list]
            Subscription.objects.bulk_create(subs_to_create)
        return huddle

def clear_database():
    # type: () -> None
    pylibmc.Client(['127.0.0.1']).flush_all()
    model = None # type: Any
    for model in [Message, Stream, UserProfile, Recipient,
                  Realm, Subscription, Huddle, UserMessage, Client,
                  DefaultStream]:
        model.objects.all().delete()
    Session.objects.all().delete()

class UserActivity(models.Model):
    user_profile = models.ForeignKey(UserProfile) # type: UserProfile
    client = models.ForeignKey(Client) # type: Client
    query = models.CharField(max_length=50, db_index=True) # type: Text

    count = models.IntegerField() # type: int
    last_visit = models.DateTimeField('last visit') # type: datetime.datetime

    class Meta(object):
        unique_together = ("user_profile", "client", "query")

class UserActivityInterval(models.Model):
    user_profile = models.ForeignKey(UserProfile) # type: UserProfile
    start = models.DateTimeField('start time', db_index=True) # type: datetime.datetime
    end = models.DateTimeField('end time', db_index=True) # type: datetime.datetime

class UserPresence(models.Model):
    user_profile = models.ForeignKey(UserProfile) # type: UserProfile
    client = models.ForeignKey(Client) # type: Client

    # Valid statuses
    ACTIVE = 1
    IDLE = 2

    timestamp = models.DateTimeField('presence changed') # type: datetime.datetime
    status = models.PositiveSmallIntegerField(default=ACTIVE) # type: int

    @staticmethod
    def status_to_string(status):
        # type: (int) -> str
        if status == UserPresence.ACTIVE:
            return 'active'
        elif status == UserPresence.IDLE:
            return 'idle'
        else:
            raise ValueError('Unknown status: %s' % (status,))

    @staticmethod
    def get_status_dict_by_user(user_profile):
        # type: (UserProfile) -> defaultdict[Any, Dict[Any, Any]]
        query = UserPresence.objects.filter(user_profile=user_profile).values(
            'client__name',
            'status',
            'timestamp',
            'user_profile__email',
            'user_profile__id',
            'user_profile__enable_offline_push_notifications',
            'user_profile__is_mirror_dummy',
        )

        if PushDeviceToken.objects.filter(user=user_profile).exists():
            mobile_user_ids = [user_profile.id]  # type: List[int]
        else:
            mobile_user_ids = []

        return UserPresence.get_status_dicts_for_query(query, mobile_user_ids)

    @staticmethod
    def get_status_dict_by_realm(realm_id):
        # type: (int) -> defaultdict[Any, Dict[Any, Any]]
        query = UserPresence.objects.filter(
            user_profile__realm_id=realm_id,
            user_profile__is_active=True,
            user_profile__is_bot=False
        ).values(
            'client__name',
            'status',
            'timestamp',
            'user_profile__email',
            'user_profile__id',
            'user_profile__enable_offline_push_notifications',
            'user_profile__is_mirror_dummy',
        )

        mobile_user_ids = [row['user'] for row in PushDeviceToken.objects.filter(
            user__realm_id=1,
            user__is_active=True,
            user__is_bot=False,
        ).distinct("user").values("user")]

        return UserPresence.get_status_dicts_for_query(query, mobile_user_ids)

    @staticmethod
    def get_status_dicts_for_query(query, mobile_user_ids):
        # type: (QuerySet, List[int]) -> defaultdict[Any, Dict[Any, Any]]
        user_statuses = defaultdict(dict) # type: defaultdict[Any, Dict[Any, Any]]
        # Order of query is important to get a latest status as aggregated status.
        for row in query.order_by("user_profile__id", "-timestamp"):
            info = UserPresence.to_presence_dict(
                row['client__name'],
                row['status'],
                row['timestamp'],
                push_enabled=row['user_profile__enable_offline_push_notifications'],
                has_push_devices=row['user_profile__id'] in mobile_user_ids,
                is_mirror_dummy=row['user_profile__is_mirror_dummy'],
            )
            if not user_statuses.get(row['user_profile__email']):
                # Applying the latest status as aggregated status for user.
                user_statuses[row['user_profile__email']]['aggregated'] = {
                    'status': info['status'],
                    'timestamp': info['timestamp']
                }
            user_statuses[row['user_profile__email']][row['client__name']] = info
        return user_statuses

    @staticmethod
    def to_presence_dict(client_name, status, dt, push_enabled=None,
                         has_push_devices=None, is_mirror_dummy=None):
        # type: (Text, int, datetime.datetime, Optional[bool], Optional[bool], Optional[bool]) -> Dict[str, Any]
        presence_val = UserPresence.status_to_string(status)

        timestamp = datetime_to_timestamp(dt)
        return dict(
            client=client_name,
            status=presence_val,
            timestamp=timestamp,
            pushable=(push_enabled and has_push_devices),
        )

    def to_dict(self):
        # type: () -> Dict[str, Any]
        return UserPresence.to_presence_dict(
            self.client.name,
            self.status,
            self.timestamp
        )

    @staticmethod
    def status_from_string(status):
        # type: (NonBinaryStr) -> Optional[int]
        if status == 'active':
            status_val = UserPresence.ACTIVE
        elif status == 'idle':
            status_val = UserPresence.IDLE
        else:
            status_val = None

        return status_val

    class Meta(object):
        unique_together = ("user_profile", "client")

class DefaultStream(models.Model):
    realm = models.ForeignKey(Realm) # type: Realm
    stream = models.ForeignKey(Stream) # type: Stream

    class Meta(object):
        unique_together = ("realm", "stream")

class Referral(models.Model):
    user_profile = models.ForeignKey(UserProfile) # type: UserProfile
    email = models.EmailField(blank=False, null=False) # type: Text
    timestamp = models.DateTimeField(auto_now_add=True, null=False) # type: datetime.datetime

# This table only gets used on Zulip Voyager instances
# For reasons of deliverability (and sending from multiple email addresses),
# we will still send from mandrill when we send things from the (staging.)zulip.com install
class ScheduledJob(models.Model):
    scheduled_timestamp = models.DateTimeField(auto_now_add=False, null=False) # type: datetime.datetime
    type = models.PositiveSmallIntegerField() # type: int
    # Valid types are {email}
    # for EMAIL, filter_string is recipient_email
    EMAIL = 1

    # JSON representation of the job's data. Be careful, as we are not relying on Django to do validation
    data = models.TextField() # type: Text
    # Kind if like a ForeignKey, but table is determined by type.
    filter_id = models.IntegerField(null=True) # type: Optional[int]
    filter_string = models.CharField(max_length=100) # type: Text

class RealmAuditLog(models.Model):
    realm = models.ForeignKey(Realm) # type: Realm
    acting_user = models.ForeignKey(UserProfile, null=True, related_name='+') # type: Optional[UserProfile]
    modified_user = models.ForeignKey(UserProfile, null=True, related_name='+') # type: Optional[UserProfile]
    modified_stream = models.ForeignKey(Stream, null=True) # type: Optional[Stream]
    event_type = models.CharField(max_length=40) # type: Text
    event_time = models.DateTimeField() # type: datetime.datetime
    backfilled = models.BooleanField(default=False) # type: bool
