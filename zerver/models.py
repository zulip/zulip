from __future__ import absolute_import
from typing import Any, DefaultDict, Dict, List, Set, Tuple, TypeVar, Text, \
    Union, Optional, Sequence, AbstractSet, Pattern, AnyStr, Callable, Iterable
from typing.re import Match
from zerver.lib.str_utils import NonBinaryStr

from django.db import models
from django.db.models.query import QuerySet
from django.db.models import Manager, CASCADE
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, UserManager, \
    PermissionsMixin
import django.contrib.auth
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, MinLengthValidator, \
    RegexValidator
from django.dispatch import receiver
from zerver.lib.cache import cache_with_key, flush_user_profile, flush_realm, \
    user_profile_by_api_key_cache_key, \
    user_profile_by_id_cache_key, user_profile_by_email_cache_key, \
    user_profile_cache_key, generic_bulk_cached_fetch, cache_set, flush_stream, \
    display_recipient_cache_key, cache_delete, active_user_ids_cache_key, \
    get_stream_cache_key, active_user_dicts_in_realm_cache_key, \
    bot_dicts_in_realm_cache_key, active_user_dict_fields, \
    bot_dict_fields, flush_message, bot_profile_cache_key
from zerver.lib.utils import make_safe_digest, generate_random_token
from zerver.lib.str_utils import ModelReprMixin
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.contrib.sessions.models import Session
from zerver.lib.timestamp import datetime_to_timestamp
from django.db.models.signals import pre_save, post_save, post_delete
from django.utils.translation import ugettext_lazy as _
from zerver.lib import cache
from zerver.lib.validator import check_int, check_float, check_string, \
    check_short_string
from django.utils.encoding import force_text

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
import sys

MAX_SUBJECT_LENGTH = 60
MAX_MESSAGE_LENGTH = 10000
MAX_LANGUAGE_ID_LENGTH = 50  # type: int

STREAM_NAMES = TypeVar('STREAM_NAMES', Sequence[Text], AbstractSet[Text])

def query_for_ids(query, user_ids, field):
    # type: (QuerySet, List[int], str) -> QuerySet
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
per_request_display_recipient_cache = {}  # type: Dict[int, List[Dict[str, Any]]]
def get_display_recipient_by_id(recipient_id, recipient_type, recipient_type_id):
    # type: (int, int, Optional[int]) -> Union[Text, List[Dict[str, Any]]]
    """
    returns: an object describing the recipient (using a cache).
    If the type is a stream, the type_id must be an int; a string is returned.
    Otherwise, type_id may be None; an array of recipient dicts is returned.
    """
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
    # type: (int, int, Optional[int]) -> Union[Text, List[Dict[str, Any]]]
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

def get_realm_emoji_cache_key(realm):
    # type: (Realm) -> Text
    return u'realm_emoji:%s' % (realm.id,)

class Realm(ModelReprMixin, models.Model):
    MAX_REALM_NAME_LENGTH = 40
    MAX_REALM_SUBDOMAIN_LENGTH = 40
    AUTHENTICATION_FLAGS = [u'Google', u'Email', u'GitHub', u'LDAP', u'Dev', u'RemoteUser']

    name = models.CharField(max_length=MAX_REALM_NAME_LENGTH, null=True)  # type: Optional[Text]
    string_id = models.CharField(max_length=MAX_REALM_SUBDOMAIN_LENGTH, unique=True)  # type: Text
    restricted_to_domain = models.BooleanField(default=False)  # type: bool
    invite_required = models.BooleanField(default=True)  # type: bool
    invite_by_admins_only = models.BooleanField(default=False)  # type: bool
    inline_image_preview = models.BooleanField(default=True)  # type: bool
    inline_url_embed_preview = models.BooleanField(default=True)  # type: bool
    create_stream_by_admins_only = models.BooleanField(default=False)  # type: bool
    add_emoji_by_admins_only = models.BooleanField(default=False)  # type: bool
    mandatory_topics = models.BooleanField(default=False)  # type: bool
    show_digest_email = models.BooleanField(default=True)  # type: bool
    name_changes_disabled = models.BooleanField(default=False)  # type: bool
    email_changes_disabled = models.BooleanField(default=False)  # type: bool
    description = models.TextField(null=True)  # type: Optional[Text]

    allow_message_editing = models.BooleanField(default=True)  # type: bool
    DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS = 600  # if changed, also change in admin.js
    message_content_edit_limit_seconds = models.IntegerField(default=DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS)  # type: int
    message_retention_days = models.IntegerField(null=True)  # type: Optional[int]
    allow_edit_history = models.BooleanField(default=True)  # type: bool

    # Valid org_types are {CORPORATE, COMMUNITY}
    CORPORATE = 1
    COMMUNITY = 2
    org_type = models.PositiveSmallIntegerField(default=CORPORATE)  # type: int

    date_created = models.DateTimeField(default=timezone_now)  # type: datetime.datetime
    notifications_stream = models.ForeignKey('Stream', related_name='+', null=True, blank=True, on_delete=CASCADE)  # type: Optional[Stream]
    deactivated = models.BooleanField(default=False)  # type: bool
    default_language = models.CharField(default=u'en', max_length=MAX_LANGUAGE_ID_LENGTH)  # type: Text
    authentication_methods = BitField(flags=AUTHENTICATION_FLAGS,
                                      default=2**31 - 1)  # type: BitHandler
    waiting_period_threshold = models.PositiveIntegerField(default=0)  # type: int

    # Define the types of the various automatically managed properties
    property_types = dict(
        add_emoji_by_admins_only=bool,
        allow_edit_history=bool,
        create_stream_by_admins_only=bool,
        default_language=Text,
        description=Text,
        email_changes_disabled=bool,
        invite_required=bool,
        invite_by_admins_only=bool,
        inline_image_preview=bool,
        inline_url_embed_preview=bool,
        mandatory_topics=bool,
        message_retention_days=(int, type(None)),
        name=Text,
        name_changes_disabled=bool,
        restricted_to_domain=bool,
        waiting_period_threshold=int,
    )  # type: Dict[str, Union[type, Tuple[type, ...]]]

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

        ret = {}  # type: Dict[Text, bool]
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
        # type: () -> Dict[Text, Optional[Dict[str, Iterable[Text]]]]
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
        if self.subdomain not in [None, ""]:
            return "%s.%s" % (self.string_id, external_host)
        return external_host

    def get_notifications_stream(self):
        # type: () -> Optional[Realm]
        if self.notifications_stream is not None and not self.notifications_stream.deactivated:
            return self.notifications_stream
        return None

    @property
    def subdomain(self):
        # type: () -> Optional[Text]
        if settings.REALMS_HAVE_SUBDOMAINS:
            return self.string_id
        return None

    @property
    def uri(self):
        # type: () -> str
        if self.subdomain not in [None, ""]:
            return '%s%s.%s' % (settings.EXTERNAL_URI_SCHEME,
                                self.subdomain, settings.EXTERNAL_HOST)
        return settings.ROOT_DOMAIN_URI

    @property
    def host(self):
        # type: () -> str
        if self.subdomain not in [None, ""]:
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
    # type: (Optional[Realm]) -> bool
    # This realm is completely open to everyone on the internet to
    # join. E-mail addresses do not need to match a realmdomain and
    # an invite from an existing user is not required.
    if realm is None:
        return False
    return not realm.invite_required and not realm.restricted_to_domain

def get_unique_non_system_realm():
    # type: () -> Optional[Realm]
    realms = Realm.objects.filter(deactivated=False)
    # On production installations, the (usually "zulip.com") system
    # realm is an empty realm just used for system bots, so don't
    # include it in this accounting.
    realms = realms.exclude(string_id__in=settings.SYSTEM_ONLY_REALMS)
    if len(realms) != 1:
        return None
    return realms[0]

def get_unique_open_realm():
    # type: () -> Optional[Realm]
    """We only return a realm if there is a unique non-system-only realm,
    it is completely open, and there are no subdomains."""
    if settings.REALMS_HAVE_SUBDOMAINS:
        return None
    realm = get_unique_non_system_realm()
    if realm is None:
        return None
    if realm.invite_required or realm.restricted_to_domain:
        return None
    return realm

def name_changes_disabled(realm):
    # type: (Optional[Realm]) -> bool
    if realm is None:
        return settings.NAME_CHANGES_DISABLED
    return settings.NAME_CHANGES_DISABLED or realm.name_changes_disabled

class RealmDomain(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    # should always be stored lowercase
    domain = models.CharField(max_length=80, db_index=True)  # type: Text
    allow_subdomains = models.BooleanField(default=False)

    class Meta(object):
        unique_together = ("realm", "domain")

def can_add_realm_domain(domain):
    # type: (Text) -> bool
    if settings.REALMS_HAVE_SUBDOMAINS:
        return True
    if RealmDomain.objects.filter(domain=domain).exists():
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
    query = RealmDomain.objects.select_related('realm')
    # Search for the longest match. If found return immediately. Since in case of
    # settings.REALMS_HAVE_SUBDOMAINS=True, we have a unique mapping between the
    # realm and domain so don't worry about `allow_subdomains` being True or False.
    realm_domain = query.filter(domain=domain).first()
    if realm_domain is not None:
        return realm_domain.realm
    else:
        # Since we have not found any match. We will now try matching the parent domain.
        # Filter out the realm domains with `allow_subdomains=False` so that we don't end
        # up matching 'test.zulip.com' wrongly to (realm, 'zulip.com', False).
        query = query.filter(allow_subdomains=True)
        while len(domain) > 0:
            subdomain, sep, domain = domain.partition('.')
            realm_domain = query.filter(domain=domain).first()
            if realm_domain is not None:
                return realm_domain.realm
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
    query = RealmDomain.objects.filter(realm=realm)
    if query.filter(domain=domain).exists():
        return True
    else:
        query = query.filter(allow_subdomains=True)
        while len(domain) > 0:
            subdomain, sep, domain = domain.partition('.')
            if query.filter(domain=domain).exists():
                return True
    return False

def get_realm_domains(realm):
    # type: (Realm) -> List[Dict[str, Text]]
    return list(realm.realmdomain_set.values('domain', 'allow_subdomains'))

class RealmEmoji(ModelReprMixin, models.Model):
    author = models.ForeignKey('UserProfile', blank=True, null=True, on_delete=CASCADE)
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    # Second part of the regex (negative lookbehind) disallows names ending with one of the punctuation characters
    name = models.TextField(validators=[MinLengthValidator(1),
                                        RegexValidator(regex=r'^[0-9a-z.\-_]+(?<![.\-_])$',
                                                       message=_("Invalid characters in emoji name"))])  # type: Text
    file_name = models.TextField(db_index=True, null=True)  # type: Optional[Text]
    deactivated = models.BooleanField(default=False)  # type: bool

    PATH_ID_TEMPLATE = "{realm_id}/emoji/{emoji_file_name}"

    class Meta(object):
        unique_together = ("realm", "name")

    def __unicode__(self):
        # type: () -> Text
        return u"<RealmEmoji(%s): %s %s>" % (self.realm.string_id, self.name, self.file_name)

def get_realm_emoji_uncached(realm):
    # type: (Realm) -> Dict[Text, Dict[str, Any]]
    d = {}
    from zerver.lib.emoji import get_emoji_url
    for row in RealmEmoji.objects.filter(realm=realm).select_related('author'):
        author = None
        if row.author:
            author = {
                'id': row.author.id,
                'email': row.author.email,
                'full_name': row.author.full_name}
        d[row.name] = dict(source_url=get_emoji_url(row.file_name, row.realm_id),
                           deactivated=row.deactivated,
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
    regex = re.compile(r'^[\.\/:a-zA-Z0-9_?=-]+%\(([a-zA-Z0-9_-]+)\)s[a-zA-Z0-9_-]*$')

    if not regex.match(value):
        raise ValidationError('URL format string must be in the following format: `https://example.com/%(\w+)s`')

class RealmFilter(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    pattern = models.TextField(validators=[filter_pattern_validator])  # type: Text
    url_format_string = models.TextField(validators=[URLValidator(), filter_format_validator])  # type: Text

    class Meta(object):
        unique_together = ("realm", "pattern")

    def __unicode__(self):
        # type: () -> Text
        return u"<RealmFilter(%s): %s %s>" % (self.realm.string_id, self.pattern, self.url_format_string)

def get_realm_filters_cache_key(realm_id):
    # type: (int) -> Text
    return u'all_realm_filters:%s' % (realm_id,)

# We have a per-process cache to avoid doing 1000 remote cache queries during page load
per_request_realm_filters_cache = {}  # type: Dict[int, List[Tuple[Text, Text, int]]]

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
    filters = defaultdict(list)  # type: DefaultDict[int, List[Tuple[Text, Text, int]]]
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
    # This value is also being used in static/js/settings_bots.js. On updating it here, update it there as well.
    OUTGOING_WEBHOOK_BOT = 3
    """
    Embedded bots run within the Zulip server itself; events are added to the
    embedded_bots queue and then handled by a QueueProcessingWorker.
    """
    EMBEDDED_BOT = 4

    # For now, don't allow creating other bot types via the UI
    ALLOWED_BOT_TYPES = [
        DEFAULT_BOT,
        INCOMING_WEBHOOK_BOT,
        OUTGOING_WEBHOOK_BOT,
    ]

    SERVICE_BOT_TYPES = [
        OUTGOING_WEBHOOK_BOT,
        EMBEDDED_BOT
    ]

    # Fields from models.AbstractUser minus last_name and first_name,
    # which we don't use; email is modified to make it indexed and unique.
    email = models.EmailField(blank=False, db_index=True, unique=True)  # type: Text
    is_staff = models.BooleanField(default=False)  # type: bool
    is_active = models.BooleanField(default=True, db_index=True)  # type: bool
    is_realm_admin = models.BooleanField(default=False, db_index=True)  # type: bool
    is_bot = models.BooleanField(default=False, db_index=True)  # type: bool
    bot_type = models.PositiveSmallIntegerField(null=True, db_index=True)  # type: Optional[int]
    is_api_super_user = models.BooleanField(default=False, db_index=True)  # type: bool
    date_joined = models.DateTimeField(default=timezone_now)  # type: datetime.datetime
    is_mirror_dummy = models.BooleanField(default=False)  # type: bool
    bot_owner = models.ForeignKey('self', null=True, on_delete=models.SET_NULL)  # type: Optional[UserProfile]
    long_term_idle = models.BooleanField(default=False, db_index=True)  # type: bool

    USERNAME_FIELD = 'email'
    MAX_NAME_LENGTH = 100
    MIN_NAME_LENGTH = 3
    API_KEY_LENGTH = 32
    NAME_INVALID_CHARS = ['*', '`', '>', '"', '@']

    # Our custom site-specific fields
    full_name = models.CharField(max_length=MAX_NAME_LENGTH)  # type: Text
    short_name = models.CharField(max_length=MAX_NAME_LENGTH)  # type: Text
    # pointer points to Message.id, NOT UserMessage.id.
    pointer = models.IntegerField()  # type: int
    last_pointer_updater = models.CharField(max_length=64)  # type: Text
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    api_key = models.CharField(max_length=API_KEY_LENGTH)  # type: Text
    tos_version = models.CharField(null=True, max_length=10)  # type: Optional[Text]
    last_active_message_id = models.IntegerField(null=True)  # type: int

    ### Notifications settings. ###

    # Stream notifications.
    enable_stream_desktop_notifications = models.BooleanField(default=False)  # type: bool
    enable_stream_push_notifications = models.BooleanField(default=False)  # type: bool
    enable_stream_sounds = models.BooleanField(default=False)  # type: bool

    # PM + @-mention notifications.
    enable_desktop_notifications = models.BooleanField(default=True)  # type: bool
    pm_content_in_desktop_notifications = models.BooleanField(default=True)  # type: bool
    enable_sounds = models.BooleanField(default=True)  # type: bool
    enable_offline_email_notifications = models.BooleanField(default=True)  # type: bool
    enable_offline_push_notifications = models.BooleanField(default=True)  # type: bool
    enable_online_push_notifications = models.BooleanField(default=False)  # type: bool

    enable_digest_emails = models.BooleanField(default=True)  # type: bool

    # Old notification field superseded by existence of stream notification
    # settings.
    default_desktop_notifications = models.BooleanField(default=True)  # type: bool

    ###

    last_reminder = models.DateTimeField(default=timezone_now, null=True)  # type: Optional[datetime.datetime]
    rate_limits = models.CharField(default=u"", max_length=100)  # type: Text # comma-separated list of range:max pairs

    # Default streams
    default_sending_stream = models.ForeignKey('zerver.Stream', null=True, related_name='+', on_delete=CASCADE)  # type: Optional[Stream]
    default_events_register_stream = models.ForeignKey('zerver.Stream', null=True, related_name='+', on_delete=CASCADE)  # type: Optional[Stream]
    default_all_public_streams = models.BooleanField(default=False)  # type: bool

    # UI vars
    enter_sends = models.NullBooleanField(default=False)  # type: Optional[bool]
    autoscroll_forever = models.BooleanField(default=False)  # type: bool
    left_side_userlist = models.BooleanField(default=False)  # type: bool
    emoji_alt_code = models.BooleanField(default=False)  # type: bool

    # display settings
    twenty_four_hour_time = models.BooleanField(default=False)  # type: bool
    default_language = models.CharField(default=u'en', max_length=MAX_LANGUAGE_ID_LENGTH)  # type: Text
    high_contrast_mode = models.BooleanField(default=False)  # type: bool

    # Hours to wait before sending another email to a user
    EMAIL_REMINDER_WAITPERIOD = 24
    # Minutes to wait before warning a bot owner that their bot sent a message
    # to a nonexistent stream
    BOT_OWNER_STREAM_ALERT_WAITPERIOD = 1

    AVATAR_FROM_GRAVATAR = u'G'
    AVATAR_FROM_USER = u'U'
    AVATAR_SOURCES = (
        (AVATAR_FROM_GRAVATAR, 'Hosted by Gravatar'),
        (AVATAR_FROM_USER, 'Uploaded by user'),
    )
    avatar_source = models.CharField(default=AVATAR_FROM_GRAVATAR, choices=AVATAR_SOURCES, max_length=1)  # type: Text
    avatar_version = models.PositiveSmallIntegerField(default=1)  # type: int

    TUTORIAL_WAITING  = u'W'
    TUTORIAL_STARTED  = u'S'
    TUTORIAL_FINISHED = u'F'
    TUTORIAL_STATES   = ((TUTORIAL_WAITING, "Waiting"),
                         (TUTORIAL_STARTED, "Started"),
                         (TUTORIAL_FINISHED, "Finished"))

    tutorial_status = models.CharField(default=TUTORIAL_WAITING, choices=TUTORIAL_STATES, max_length=1)  # type: Text
    # Contains serialized JSON of the form:
    #    [("step 1", true), ("step 2", false)]
    # where the second element of each tuple is if the step has been
    # completed.
    onboarding_steps = models.TextField(default=u'[]')  # type: Text

    alert_words = models.TextField(default=u'[]')  # type: Text # json-serialized list of strings

    objects = UserManager()  # type: UserManager

    DEFAULT_UPLOADS_QUOTA = 1024*1024*1024

    quota = models.IntegerField(default=DEFAULT_UPLOADS_QUOTA)  # type: int
    # The maximum length of a timezone in pytz.all_timezones is 32.
    # Setting max_length=40 is a safe choice.
    # In Django, the convention is to use empty string instead of Null
    # for text based fields. For more information, see
    # https://docs.djangoproject.com/en/1.10/ref/models/fields/#django.db.models.Field.null.
    timezone = models.CharField(max_length=40, default=u'')  # type: Text

    # Emojisets
    APPLE_EMOJISET      = u'apple'
    EMOJIONE_EMOJISET   = u'emojione'
    GOOGLE_EMOJISET     = u'google'
    TWITTER_EMOJISET    = u'twitter'
    EMOJISET_CHOICES    = ((APPLE_EMOJISET, _("Apple style")),
                           (EMOJIONE_EMOJISET, _("Emoji One style")),
                           (GOOGLE_EMOJISET, _("Google style")),
                           (TWITTER_EMOJISET, _("Twitter style")))
    emojiset = models.CharField(default=GOOGLE_EMOJISET, choices=EMOJISET_CHOICES, max_length=20)  # type: Text

    # Define the types of the various automatically managed properties
    property_types = dict(
        default_language=Text,
        emoji_alt_code=bool,
        emojiset=Text,
        left_side_userlist=bool,
        timezone=Text,
        twenty_four_hour_time=bool,
        high_contrast_mode=bool,
    )

    notification_setting_types = dict(
        enable_desktop_notifications=bool,
        enable_digest_emails=bool,
        enable_offline_email_notifications=bool,
        enable_offline_push_notifications=bool,
        enable_online_push_notifications=bool,
        enable_sounds=bool,
        enable_stream_desktop_notifications=bool,
        enable_stream_push_notifications=bool,
        enable_stream_sounds=bool,
        pm_content_in_desktop_notifications=bool,
    )

    @property
    def profile_data(self):
        # type: () -> List[Dict[str, Union[int, float, Text]]]
        values = CustomProfileFieldValue.objects.filter(user_profile=self)
        user_data = {v.field_id: v.value for v in values}
        data = []  # type: List[Dict[str, Union[int, float, Text]]]
        for field in custom_profile_fields_for_realm(self.realm_id):
            value = user_data.get(field.id, None)
            field_type = field.field_type
            if value is not None:
                converter = field.FIELD_CONVERTERS[field_type]
                value = converter(value)

            field_data = {}  # type: Dict[str, Union[int, float, Text]]
            for k, v in field.as_dict().items():
                field_data[k] = v
            field_data['value'] = value
            data.append(field_data)

        return data

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

    @property
    def is_outgoing_webhook_bot(self):
        # type: () -> bool
        return self.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT

    @property
    def is_embedded_bot(self):
        # type: () -> bool
        return self.bot_type == UserProfile.EMBEDDED_BOT

    @property
    def is_service_bot(self):
        # type: () -> bool
        return self.is_bot and self.bot_type in UserProfile.SERVICE_BOT_TYPES

    @staticmethod
    def emojiset_choices():
        # type: () -> Dict[Text, Text]
        return {emojiset[0]: force_text(emojiset[1]) for emojiset in UserProfile.EMOJISET_CHOICES}

    @staticmethod
    def emails_from_ids(user_ids):
        # type: (Sequence[int]) -> Dict[int, Text]
        rows = UserProfile.objects.filter(id__in=user_ids).values('id', 'email')
        return {row['id']: row['email'] for row in rows}

    def can_create_streams(self):
        # type: () -> bool
        diff = (timezone_now() - self.date_joined).days
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

def receives_stream_notifications(user_profile):
    # type: (UserProfile) -> bool
    return (user_profile.enable_stream_push_notifications and
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
    email = models.EmailField()  # type: Text
    referred_by = models.ForeignKey(UserProfile, null=True, on_delete=CASCADE)  # Optional[UserProfile]
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

class MultiuseInvite(models.Model):
    referred_by = models.ForeignKey(UserProfile, on_delete=CASCADE)  # Optional[UserProfile]
    streams = models.ManyToManyField('Stream')  # type: Manager
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm

class EmailChangeStatus(models.Model):
    new_email = models.EmailField()  # type: Text
    old_email = models.EmailField()  # type: Text
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
    token = models.CharField(max_length=4096, unique=True)  # type: bytes
    last_updated = models.DateTimeField(auto_now=True)  # type: datetime.datetime

    # [optional] Contains the app id of the device if it is an iOS device
    ios_app_id = models.TextField(null=True)  # type: Optional[Text]

    class Meta(object):
        abstract = True

class PushDeviceToken(AbstractPushDeviceToken):
    # The user who's device this is
    user = models.ForeignKey(UserProfile, db_index=True, on_delete=CASCADE)  # type: UserProfile

def generate_email_token_for_stream():
    # type: () -> str
    return generate_random_token(32)

class Stream(ModelReprMixin, models.Model):
    MAX_NAME_LENGTH = 60
    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)  # type: Text
    realm = models.ForeignKey(Realm, db_index=True, on_delete=CASCADE)  # type: Realm
    invite_only = models.NullBooleanField(default=False)  # type: Optional[bool]
    # Used by the e-mail forwarder. The e-mail RFC specifies a maximum
    # e-mail length of 254, and our max stream length is 30, so we
    # have plenty of room for the token.
    email_token = models.CharField(
        max_length=32, default=generate_email_token_for_stream)  # type: str
    description = models.CharField(max_length=1024, default=u'')  # type: Text

    date_created = models.DateTimeField(default=timezone_now)  # type: datetime.datetime
    deactivated = models.BooleanField(default=False)  # type: bool

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
    type_id = models.IntegerField(db_index=True)  # type: int
    type = models.PositiveSmallIntegerField(db_index=True)  # type: int
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

class MutedTopic(ModelReprMixin, models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    stream = models.ForeignKey(Stream, on_delete=CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    topic_name = models.CharField(max_length=MAX_SUBJECT_LENGTH)

    class Meta(object):
        unique_together = ('user_profile', 'stream', 'topic_name')

    def __unicode__(self):
        # type: () -> Text
        return u"<MutedTopic: (%s, %s, %s)>" % (self.user_profile.email, self.stream.name, self.topic_name)

class Client(ModelReprMixin, models.Model):
    name = models.CharField(max_length=30, db_index=True, unique=True)  # type: Text

    def __unicode__(self):
        # type: () -> Text
        return u"<Client: %s>" % (self.name,)

get_client_cache = {}  # type: Dict[Text, Client]
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
def get_stream_backend(stream_name, realm_id):
    # type: (Text, int) -> Stream
    return Stream.objects.select_related("realm").get(
        name__iexact=stream_name.strip(), realm_id=realm_id)

def stream_name_in_use(stream_name, realm_id):
    # type: (Text, int) -> bool
    return Stream.objects.filter(
        name__iexact=stream_name.strip(),
        realm_id=realm_id
    ).exists()

def get_active_streams(realm):
    # type: (Optional[Realm]) -> QuerySet
    """
    Return all streams (including invite-only streams) that have not been deactivated.
    """
    return Stream.objects.filter(realm=realm, deactivated=False)

def get_stream(stream_name, realm):
    # type: (Text, Realm) -> Stream
    return get_stream_backend(stream_name, realm.id)

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

    return generic_bulk_cached_fetch(lambda stream_name: get_stream_cache_key(stream_name, realm.id),
                                     fetch_streams_by_name,
                                     [stream_name.lower() for stream_name in stream_names],
                                     id_fetcher=lambda stream: stream.name.lower())

def get_recipient_cache_key(type, type_id):
    # type: (int, int) -> Text
    return u"%s:get_recipient:%s:%s" % (cache.KEY_PREFIX, type, type_id,)

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


class AbstractMessage(ModelReprMixin, models.Model):
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)  # type: Recipient
    subject = models.CharField(max_length=MAX_SUBJECT_LENGTH, db_index=True)  # type: Text
    content = models.TextField()  # type: Text
    rendered_content = models.TextField(null=True)  # type: Optional[Text]
    rendered_content_version = models.IntegerField(null=True)  # type: Optional[int]
    pub_date = models.DateTimeField('date published', db_index=True)  # type: datetime.datetime
    sending_client = models.ForeignKey(Client, on_delete=CASCADE)  # type: Client
    last_edit_time = models.DateTimeField(null=True)  # type: Optional[datetime.datetime]
    edit_history = models.TextField(null=True)  # type: Optional[Text]
    has_attachment = models.BooleanField(default=False, db_index=True)  # type: bool
    has_image = models.BooleanField(default=False, db_index=True)  # type: bool
    has_link = models.BooleanField(default=False, db_index=True)  # type: bool

    class Meta(object):
        abstract = True

    def __unicode__(self):
        # type: () -> Text
        display_recipient = get_display_recipient(self.recipient)
        return u"<%s: %s / %s / %r>" % (self.__class__.__name__, display_recipient,
                                        self.subject, self.sender)


class ArchivedMessage(AbstractMessage):
    archive_timestamp = models.DateTimeField(default=timezone_now, db_index=True)  # type: datetime.datetime


class Message(AbstractMessage):

    def topic_name(self):
        # type: () -> Text
        """
        Please start using this helper to facilitate an
        eventual switch over to a separate topic table.
        """
        return self.subject

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
            sender_realm_str  = self.sender.realm.string_id,
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
        # callers like get_messages_backend().
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
            'sender__realm__string_id',
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
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    message = models.ForeignKey(Message, on_delete=CASCADE)  # type: Message
    emoji_name = models.TextField()  # type: Text
    emoji_code = models.TextField()  # type: Text

    UNICODE_EMOJI       = u'unicode_emoji'
    REALM_EMOJI         = u'realm_emoji'
    ZULIP_EXTRA_EMOJI   = u'zulip_extra_emoji'
    REACTION_TYPES      = ((UNICODE_EMOJI, _("Unicode emoji")),
                           (REALM_EMOJI, _("Realm emoji")),
                           (ZULIP_EXTRA_EMOJI, _("Zulip extra emoji")))

    reaction_type = models.CharField(default=UNICODE_EMOJI, choices=REACTION_TYPES, max_length=30)  # type: Text

    class Meta(object):
        unique_together = ("user_profile", "message", "emoji_name")

    @staticmethod
    def get_raw_db_rows(needed_ids):
        # type: (List[int]) -> List[Dict[str, Any]]
        fields = ['message_id', 'emoji_name', 'emoji_code', 'reaction_type',
                  'user_profile__email', 'user_profile__id', 'user_profile__full_name']
        return Reaction.objects.filter(message_id__in=needed_ids).values(*fields)

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
class AbstractUserMessage(ModelReprMixin, models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    # WARNING: We removed the previously-final flag,
    # is_me_message, without clearing any values it might have had in
    # the database.  So when we next add a flag, you need to do a
    # migration to set it to 0 first
    ALL_FLAGS = ['read', 'starred', 'collapsed', 'mentioned', 'wildcard_mentioned',
                 'summarize_in_home', 'summarize_in_stream', 'force_expand', 'force_collapse',
                 'has_alert_word', "historical"]
    flags = BitField(flags=ALL_FLAGS, default=0)  # type: BitHandler

    class Meta(object):
        abstract = True
        unique_together = ("user_profile", "message")

    @staticmethod
    def where_unread():
        # type: () -> str
        # Use this for Django ORM queries where we are getting lots
        # of rows.  This custom SQL plays nice with our partial indexes.
        # Grep the code for example usage.
        return 'flags & 1 = 0'

    def flags_list(self):
        # type: () -> List[str]
        flags = int(self.flags)
        return self.flags_list_for_flags(flags)

    @staticmethod
    def flags_list_for_flags(flags):
        # type: (int) -> List[str]
        '''
        This function is highly optimized, because it actually slows down
        sending messages in a naive implementation.
        '''
        names = AbstractUserMessage.ALL_FLAGS
        return [
            names[i]
            for i in range(len(names))
            if flags & (2 ** i)
        ]

    def __unicode__(self):
        # type: () -> Text
        display_recipient = get_display_recipient(self.message.recipient)
        return u"<%s: %s / %s (%s)>" % (self.__class__.__name__, display_recipient,
                                        self.user_profile.email, self.flags_list())


class ArchivedUserMessage(AbstractUserMessage):
    message = models.ForeignKey(ArchivedMessage, on_delete=CASCADE)  # type: Message
    archive_timestamp = models.DateTimeField(default=timezone_now, db_index=True)  # type: datetime.datetime


class UserMessage(AbstractUserMessage):
    message = models.ForeignKey(Message, on_delete=CASCADE)  # type: Message


def parse_usermessage_flags(val):
    # type: (int) -> List[str]
    flags = []
    mask = 1
    for flag in UserMessage.ALL_FLAGS:
        if val & mask:
            flags.append(flag)
        mask <<= 1
    return flags


class AbstractAttachment(ModelReprMixin, models.Model):
    file_name = models.TextField(db_index=True)  # type: Text
    # path_id is a storage location agnostic representation of the path of the file.
    # If the path of a file is http://localhost:9991/user_uploads/a/b/abc/temp_file.py
    # then its path_id will be a/b/abc/temp_file.py.
    path_id = models.TextField(db_index=True, unique=True)  # type: Text
    owner = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    realm = models.ForeignKey(Realm, blank=True, null=True, on_delete=CASCADE)  # type: Optional[Realm]
    is_realm_public = models.BooleanField(default=False)  # type: bool
    create_time = models.DateTimeField(default=timezone_now,
                                       db_index=True)  # type: datetime.datetime
    size = models.IntegerField(null=True)  # type: Optional[int]

    class Meta(object):
        abstract = True

    def __unicode__(self):
        # type: () -> Text
        return u"<%s: %s>" % (self.__class__.__name__, self.file_name,)


class ArchivedAttachment(AbstractAttachment):
    archive_timestamp = models.DateTimeField(default=timezone_now, db_index=True)  # type: datetime.datetime
    messages = models.ManyToManyField(ArchivedMessage)  # type: Manager


class Attachment(AbstractAttachment):
    messages = models.ManyToManyField(Message)  # type: Manager

    def is_claimed(self):
        # type: () -> bool
        return self.messages.count() > 0

    def to_dict(self):
        # type: () -> Dict[str, Any]
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

def validate_attachment_request(user_profile, path_id):
    # type: (UserProfile, Text) -> Optional[bool]
    try:
        attachment = Attachment.objects.get(path_id=path_id)
        messages = attachment.messages.all()

        if user_profile == attachment.owner:
            # If you own the file, you can access it.
            return True
        elif attachment.is_realm_public and attachment.realm == user_profile.realm:
            # Any user in the realm can access realm-public files
            return True
        elif UserMessage.objects.filter(user_profile=user_profile, message__in=messages).exists():
            # If it was sent in a private message or private stream
            # message, then anyone who received that message can access it.
            return True
        else:
            return False
    except Attachment.DoesNotExist:
        return None

def get_old_unclaimed_attachments(weeks_ago):
    # type: (int) -> Sequence[Attachment]
    # TODO: Change return type to QuerySet[Attachment]
    delta_weeks_ago = timezone_now() - datetime.timedelta(weeks=weeks_ago)
    old_attachments = Attachment.objects.filter(messages=None, create_time__lt=delta_weeks_ago)
    return old_attachments

class Subscription(ModelReprMixin, models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)  # type: Recipient
    active = models.BooleanField(default=True)  # type: bool
    in_home_view = models.NullBooleanField(default=True)  # type: Optional[bool]

    DEFAULT_STREAM_COLOR = u"#c2c2c2"
    color = models.CharField(max_length=10, default=DEFAULT_STREAM_COLOR)  # type: Text
    pin_to_top = models.BooleanField(default=False)  # type: bool

    desktop_notifications = models.BooleanField(default=True)  # type: bool
    audible_notifications = models.BooleanField(default=True)  # type: bool
    push_notifications = models.BooleanField(default=False)  # type: bool

    # Combination desktop + audible notifications superseded by the
    # above.
    notifications = models.BooleanField(default=False)  # type: bool

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

@cache_with_key(user_profile_by_api_key_cache_key, timeout=3600*24*7)
def get_user_profile_by_api_key(api_key):
    # type: (Text) -> UserProfile
    return UserProfile.objects.select_related().get(api_key=api_key)

@cache_with_key(user_profile_cache_key, timeout=3600*24*7)
def get_user(email, realm):
    # type: (Text, Realm) -> UserProfile
    return UserProfile.objects.select_related().get(email__iexact=email.strip(), realm=realm)

def get_user_including_cross_realm(email, realm=None):
    # type: (Text, Optional[Realm]) -> UserProfile
    if email in get_cross_realm_emails():
        return get_system_bot(email)
    assert realm is not None
    return get_user(email, realm)

@cache_with_key(bot_profile_cache_key, timeout=3600*24*7)
def get_system_bot(email):
    # type: (Text) -> UserProfile
    return UserProfile.objects.select_related().get(email__iexact=email.strip())

@cache_with_key(active_user_dicts_in_realm_cache_key, timeout=3600*24*7)
def get_active_user_dicts_in_realm(realm_id):
    # type: (int) -> List[Dict[str, Any]]
    return UserProfile.objects.filter(
        realm_id=realm_id,
        is_active=True
    ).values(*active_user_dict_fields)

@cache_with_key(active_user_ids_cache_key, timeout=3600*24*7)
def active_user_ids(realm_id):
    # type: (int) -> List[int]
    query = UserProfile.objects.filter(
        realm_id=realm_id,
        is_active=True
    ).values_list('id', flat=True)
    return list(query)

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
    from zerver.lib.avatar import avatar_url_from_dict

    return [{'email': botdict['email'],
             'user_id': botdict['id'],
             'full_name': botdict['full_name'],
             'bot_type': botdict['bot_type'],
             'is_active': botdict['is_active'],
             'api_key': botdict['api_key'],
             'default_sending_stream': botdict['default_sending_stream__name'],
             'default_events_register_stream': botdict['default_events_register_stream__name'],
             'default_all_public_streams': botdict['default_all_public_streams'],
             'owner': botdict['bot_owner__email'],
             'avatar_url': avatar_url_from_dict(botdict),
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
    huddle_hash = models.CharField(max_length=40, db_index=True, unique=True)  # type: Text

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
                                           user_profile_id=user_profile_id)
                              for user_profile_id in id_list]
            Subscription.objects.bulk_create(subs_to_create)
        return huddle

def clear_database():
    # type: () -> None
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
    query = models.CharField(max_length=50, db_index=True)  # type: Text

    count = models.IntegerField()  # type: int
    last_visit = models.DateTimeField('last visit')  # type: datetime.datetime

    class Meta(object):
        unique_together = ("user_profile", "client", "query")

class UserActivityInterval(models.Model):
    MIN_INTERVAL_LENGTH = datetime.timedelta(minutes=15)

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    start = models.DateTimeField('start time', db_index=True)  # type: datetime.datetime
    end = models.DateTimeField('end time', db_index=True)  # type: datetime.datetime


class UserPresence(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    client = models.ForeignKey(Client, on_delete=CASCADE)  # type: Client

    # Valid statuses
    ACTIVE = 1
    IDLE = 2

    timestamp = models.DateTimeField('presence changed')  # type: datetime.datetime
    status = models.PositiveSmallIntegerField(default=ACTIVE)  # type: int

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
        # type: (UserProfile) -> Dict[Text, Dict[Any, Any]]
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
        if PushDeviceToken.objects.filter(user=user_profile).exists():
            mobile_user_ids.add(user_profile.id)

        return UserPresence.get_status_dicts_for_rows(presence_rows, mobile_user_ids)

    @staticmethod
    def get_status_dict_by_realm(realm_id):
        # type: (int) -> Dict[Text, Dict[Any, Any]]
        user_profile_ids = UserProfile.objects.filter(
            realm_id=realm_id,
            is_active=True,
            is_bot=False
        ).order_by('id').values_list('id', flat=True)

        user_profile_ids = list(user_profile_ids)

        if not user_profile_ids:
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
    def get_status_dicts_for_rows(presence_rows, mobile_user_ids):
        # type: (List[Dict[str, Any]], Set[int]) -> Dict[Text, Dict[Any, Any]]

        info_row_dct = defaultdict(list)  # type: DefaultDict[Text, List[Dict[str, Any]]]
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
    def to_presence_dict(client_name, status, dt, push_enabled=False,
                         has_push_devices=False):
        # type: (Text, int, datetime.datetime, bool, bool) -> Dict[str, Any]
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
            status_val = UserPresence.ACTIVE  # type: Optional[int] # See https://github.com/python/mypy/issues/2611
        elif status == 'idle':
            status_val = UserPresence.IDLE
        else:
            status_val = None

        return status_val

    class Meta(object):
        unique_together = ("user_profile", "client")

class DefaultStream(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    stream = models.ForeignKey(Stream, on_delete=CASCADE)  # type: Stream

    class Meta(object):
        unique_together = ("realm", "stream")

class AbstractScheduledJob(models.Model):
    scheduled_timestamp = models.DateTimeField(db_index=True)  # type: datetime.datetime
    # JSON representation of arguments to consumer
    data = models.TextField()  # type: Text

    class Meta(object):
        abstract = True

class ScheduledEmail(AbstractScheduledJob):
    # Exactly one of user or address should be set. These are used to
    # filter the set of ScheduledEmails.
    user = models.ForeignKey(UserProfile, null=True, on_delete=CASCADE)  # type: UserProfile
    # Just the address part of a full "name <address>" email address
    address = models.EmailField(null=True, db_index=True)  # type: Text

    # Valid types are below
    WELCOME = 1
    DIGEST = 2
    INVITATION_REMINDER = 3
    type = models.PositiveSmallIntegerField()  # type: int

    def __str__(self):
        # type: () -> Text
        return u"<ScheduledEmail: %s %s %s>" % (self.type, self.user or self.address,
                                                self.scheduled_timestamp)

EMAIL_TYPES = {
    'followup_day1': ScheduledEmail.WELCOME,
    'followup_day2': ScheduledEmail.WELCOME,
    'digest': ScheduledEmail.DIGEST,
    'invitation_reminder': ScheduledEmail.INVITATION_REMINDER,
}

class RealmAuditLog(ModelReprMixin, models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    acting_user = models.ForeignKey(UserProfile, null=True, related_name='+', on_delete=CASCADE)  # type: Optional[UserProfile]
    modified_user = models.ForeignKey(UserProfile, null=True, related_name='+', on_delete=CASCADE)  # type: Optional[UserProfile]
    modified_stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)  # type: Optional[Stream]
    event_last_message_id = models.IntegerField(null=True)  # type: Optional[int]
    event_type = models.CharField(max_length=40)  # type: Text
    event_time = models.DateTimeField(db_index=True)  # type: datetime.datetime
    # If True, event_time is an overestimate of the true time. Can be used
    # by migrations when introducing a new event_type.
    backfilled = models.BooleanField(default=False)  # type: bool
    extra_data = models.TextField(null=True)  # type: Optional[Text]

    def __unicode__(self):
        # type: () -> str
        if self.modified_user is not None:
            return u"<RealmAuditLog: %s %s %s>" % (self.modified_user, self.event_type, self.event_time)
        if self.modified_stream is not None:
            return u"<RealmAuditLog: %s %s %s>" % (self.modified_stream, self.event_type, self.event_time)
        return "<RealmAuditLog: %s %s %s>" % (self.realm, self.event_type, self.event_time)

class UserHotspot(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    hotspot = models.CharField(max_length=30)  # type: Text
    timestamp = models.DateTimeField(default=timezone_now)  # type: datetime.datetime

    class Meta(object):
        unique_together = ("user", "hotspot")

class CustomProfileField(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # type: Realm
    name = models.CharField(max_length=100)  # type: Text

    INTEGER = 1
    FLOAT = 2
    SHORT_TEXT = 3
    LONG_TEXT = 4

    FIELD_TYPE_DATA = [
        # Type, Name, Validator, Converter
        (INTEGER, u'Integer', check_int, int),
        (FLOAT, u'Float', check_float, float),
        (SHORT_TEXT, u'Short Text', check_short_string, str),
        (LONG_TEXT, u'Long Text', check_string, str),
    ]  # type: List[Tuple[int, Text, Callable[[str, Any], str], Callable[[Any], Any]]]

    FIELD_VALIDATORS = {item[0]: item[2] for item in FIELD_TYPE_DATA}  # type: Dict[int, Callable[[str, Any], str]]
    FIELD_CONVERTERS = {item[0]: item[3] for item in FIELD_TYPE_DATA}  # type: Dict[int, Callable[[Any], Any]]
    FIELD_TYPE_CHOICES = [(item[0], item[1]) for item in FIELD_TYPE_DATA]  # type: List[Tuple[int, Text]]

    field_type = models.PositiveSmallIntegerField(choices=FIELD_TYPE_CHOICES,
                                                  default=SHORT_TEXT)  # type: int

    class Meta(object):
        unique_together = ('realm', 'name')

    def as_dict(self):
        # type: () -> Dict[str, Union[int, Text]]
        return {
            'id': self.id,
            'name': self.name,
            'type': self.field_type,
        }

def custom_profile_fields_for_realm(realm_id):
    # type: (int) -> List[CustomProfileField]
    return CustomProfileField.objects.filter(realm=realm_id).order_by('name')

class CustomProfileFieldValue(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    field = models.ForeignKey(CustomProfileField, on_delete=CASCADE)  # type: CustomProfileField
    value = models.TextField()  # type: Text

    class Meta(object):
        unique_together = ('user_profile', 'field')

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
    name = models.CharField(max_length=UserProfile.MAX_NAME_LENGTH)  # type: Text
    # Bot user corresponding to the Service.  The bot_type of this user
    # deterines the type of service.  If non-bot services are added later,
    # user_profile can also represent the owner of the Service.
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)  # type: UserProfile
    base_url = models.TextField()  # type: Text
    token = models.TextField()  # type: Text
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
    }  # type: Dict[int, Text]

    def interface_name(self):
        # type: () -> Text
        # Raises KeyError if invalid
        return self._interfaces[self.interface]


def get_realm_outgoing_webhook_services_name(realm):
    # type: (Realm) -> List[Any]
    return list(Service.objects.filter(user_profile__realm=realm, user_profile__is_bot=True,
                                       user_profile__bot_type=UserProfile.OUTGOING_WEBHOOK_BOT).values('name'))

def get_bot_services(user_profile_id):
    # type: (str) -> List[Service]
    return list(Service.objects.filter(user_profile__id=user_profile_id))

def get_service_profile(user_profile_id, service_name):
    # type: (str, str) -> Service
    return Service.objects.get(user_profile__id=user_profile_id, name=service_name)
