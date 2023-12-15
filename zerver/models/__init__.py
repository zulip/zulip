from typing import Any, Callable, Dict, List, Tuple, TypeVar, Union

import orjson
from django.core.exceptions import ValidationError
from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models import CASCADE, QuerySet
from django.db.models.signals import post_delete, post_save
from django.db.models.sql.compiler import SQLCompiler
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django_stubs_ext import StrPromise, ValuesQuerySet
from typing_extensions import override

from zerver.lib.cache import (
    cache_delete,
    realm_alert_words_automaton_cache_key,
    realm_alert_words_cache_key,
)
from zerver.lib.types import (
    ExtendedFieldElement,
    ExtendedValidator,
    FieldElement,
    ProfileDataElementBase,
    ProfileDataElementValue,
    RealmUserValidator,
    UserFieldElement,
    Validator,
)
from zerver.lib.validator import (
    check_date,
    check_int,
    check_list,
    check_long_string,
    check_short_string,
    check_url,
    validate_select_field,
)
from zerver.models.clients import Client as Client
from zerver.models.drafts import Draft as Draft
from zerver.models.groups import GroupGroupMembership as GroupGroupMembership
from zerver.models.groups import UserGroup as UserGroup
from zerver.models.groups import UserGroupMembership as UserGroupMembership
from zerver.models.linkifiers import RealmFilter as RealmFilter
from zerver.models.messages import AbstractAttachment as AbstractAttachment
from zerver.models.messages import AbstractEmoji as AbstractEmoji
from zerver.models.messages import AbstractMessage as AbstractMessage
from zerver.models.messages import AbstractReaction as AbstractReaction
from zerver.models.messages import AbstractSubMessage as AbstractSubMessage
from zerver.models.messages import AbstractUserMessage as AbstractUserMessage
from zerver.models.messages import ArchivedAttachment as ArchivedAttachment
from zerver.models.messages import ArchivedMessage as ArchivedMessage
from zerver.models.messages import ArchivedReaction as ArchivedReaction
from zerver.models.messages import ArchivedSubMessage as ArchivedSubMessage
from zerver.models.messages import ArchivedUserMessage as ArchivedUserMessage
from zerver.models.messages import ArchiveTransaction as ArchiveTransaction
from zerver.models.messages import Attachment as Attachment
from zerver.models.messages import Message as Message
from zerver.models.messages import Reaction as Reaction
from zerver.models.messages import SubMessage as SubMessage
from zerver.models.messages import UserMessage as UserMessage
from zerver.models.muted_users import MutedUser as MutedUser
from zerver.models.onboarding_steps import OnboardingStep as OnboardingStep
from zerver.models.prereg_users import EmailChangeStatus as EmailChangeStatus
from zerver.models.prereg_users import MultiuseInvite as MultiuseInvite
from zerver.models.prereg_users import PreregistrationRealm as PreregistrationRealm
from zerver.models.prereg_users import PreregistrationUser as PreregistrationUser
from zerver.models.prereg_users import RealmReactivationStatus as RealmReactivationStatus
from zerver.models.presence import UserPresence as UserPresence
from zerver.models.presence import UserStatus as UserStatus
from zerver.models.push_notifications import AbstractPushDeviceToken as AbstractPushDeviceToken
from zerver.models.push_notifications import PushDeviceToken as PushDeviceToken
from zerver.models.realm_audit_logs import AbstractRealmAuditLog as AbstractRealmAuditLog
from zerver.models.realm_audit_logs import RealmAuditLog as RealmAuditLog
from zerver.models.realm_emoji import RealmEmoji as RealmEmoji
from zerver.models.realm_playgrounds import RealmPlayground as RealmPlayground
from zerver.models.realms import Realm as Realm
from zerver.models.realms import RealmAuthenticationMethod as RealmAuthenticationMethod
from zerver.models.realms import RealmDomain as RealmDomain
from zerver.models.recipients import Huddle as Huddle
from zerver.models.recipients import Recipient as Recipient
from zerver.models.scheduled_jobs import AbstractScheduledJob as AbstractScheduledJob
from zerver.models.scheduled_jobs import MissedMessageEmailAddress as MissedMessageEmailAddress
from zerver.models.scheduled_jobs import ScheduledEmail as ScheduledEmail
from zerver.models.scheduled_jobs import ScheduledMessage as ScheduledMessage
from zerver.models.scheduled_jobs import (
    ScheduledMessageNotificationEmail as ScheduledMessageNotificationEmail,
)
from zerver.models.streams import DefaultStream as DefaultStream
from zerver.models.streams import DefaultStreamGroup as DefaultStreamGroup
from zerver.models.streams import Stream as Stream
from zerver.models.streams import Subscription as Subscription
from zerver.models.user_activity import UserActivity as UserActivity
from zerver.models.user_activity import UserActivityInterval as UserActivityInterval
from zerver.models.user_topics import UserTopic as UserTopic
from zerver.models.users import RealmUserDefault as RealmUserDefault
from zerver.models.users import UserBaseSettings as UserBaseSettings
from zerver.models.users import UserProfile as UserProfile
from zerver.models.users import get_user_profile_by_id_in_realm


@models.Field.register_lookup
class AndZero(models.Lookup[int]):
    lookup_name = "andz"

    @override
    def as_sql(
        self, compiler: SQLCompiler, connection: BaseDatabaseWrapper
    ) -> Tuple[str, List[Union[str, int]]]:  # nocoverage # currently only used in migrations
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f"{lhs} & {rhs} = 0", lhs_params + rhs_params


@models.Field.register_lookup
class AndNonZero(models.Lookup[int]):
    lookup_name = "andnz"

    @override
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

    @override
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

    @override
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
