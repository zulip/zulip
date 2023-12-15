# https://github.com/typeddjango/django-stubs/issues/1698
# mypy: disable-error-code="explicit-override"

import hashlib
import time
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, TypeVar, Union

import orjson
from bitfield import BitField
from bitfield.types import Bit, BitHandler
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models import CASCADE, Exists, F, OuterRef, Q, QuerySet
from django.db.models.functions import Upper
from django.db.models.signals import post_delete, post_save
from django.db.models.sql.compiler import SQLCompiler
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django_stubs_ext import StrPromise, ValuesQuerySet
from typing_extensions import override

from zerver.lib import cache
from zerver.lib.cache import (
    cache_delete,
    cache_with_key,
    flush_message,
    flush_submessage,
    flush_used_upload_space_cache,
    realm_alert_words_automaton_cache_key,
    realm_alert_words_cache_key,
)
from zerver.lib.display_recipient import get_recipient_ids
from zerver.lib.exceptions import RateLimitedError
from zerver.lib.timestamp import datetime_to_timestamp
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
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.groups import GroupGroupMembership as GroupGroupMembership
from zerver.models.groups import UserGroup as UserGroup
from zerver.models.groups import UserGroupMembership as UserGroupMembership
from zerver.models.linkifiers import RealmFilter as RealmFilter
from zerver.models.muted_users import MutedUser as MutedUser
from zerver.models.prereg_users import EmailChangeStatus as EmailChangeStatus
from zerver.models.prereg_users import MultiuseInvite as MultiuseInvite
from zerver.models.prereg_users import PreregistrationRealm as PreregistrationRealm
from zerver.models.prereg_users import PreregistrationUser as PreregistrationUser
from zerver.models.prereg_users import RealmReactivationStatus as RealmReactivationStatus
from zerver.models.push_notifications import AbstractPushDeviceToken as AbstractPushDeviceToken
from zerver.models.push_notifications import PushDeviceToken as PushDeviceToken
from zerver.models.realm_emoji import RealmEmoji as RealmEmoji
from zerver.models.realm_playgrounds import RealmPlayground as RealmPlayground
from zerver.models.realms import Realm as Realm
from zerver.models.realms import RealmAuthenticationMethod as RealmAuthenticationMethod
from zerver.models.realms import RealmDomain as RealmDomain
from zerver.models.recipients import Huddle as Huddle
from zerver.models.recipients import Recipient as Recipient
from zerver.models.streams import DefaultStream as DefaultStream
from zerver.models.streams import DefaultStreamGroup as DefaultStreamGroup
from zerver.models.streams import Stream as Stream
from zerver.models.streams import Subscription as Subscription
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


class Client(models.Model):
    MAX_NAME_LENGTH = 30
    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True, unique=True)

    @override
    def __str__(self) -> str:
        return self.name

    def default_read_by_sender(self) -> bool:
        """Used to determine whether a message was sent by a full Zulip UI
        style client (and thus whether the message should be treated
        as sent by a human and automatically marked as read for the
        sender).  The purpose of this distinction is to ensure that
        message sent to the user by e.g. a Google Calendar integration
        using the user's own API key don't get marked as read
        automatically.
        """
        sending_client = self.name.lower()

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
            or "desktop app" in sending_client
            # Since the vast majority of messages are sent by humans
            # in Zulip, treat test suite messages as such.
            or (sending_client == "test suite" and settings.TEST_SUITE)
        )


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


class AbstractMessage(models.Model):
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # The target of the message is signified by the Recipient object.
    # See the Recipient class for details.
    recipient = models.ForeignKey(Recipient, on_delete=CASCADE)

    # The realm containing the message. Usually this will be the same
    # as the realm of the messages's sender; the exception to that is
    # cross-realm bot users.
    #
    # Important for efficient indexes and sharding in multi-realm servers.
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

    # The raw Markdown-format text (E.g., what the user typed into the compose box).
    content = models.TextField()

    # The HTML rendered content resulting from rendering the content
    # with the Markdown processor.
    rendered_content = models.TextField(null=True)
    # A rarely-incremented version number, theoretically useful for
    # tracking which messages have been already rerendered when making
    # major changes to the markup rendering process.
    rendered_content_version = models.IntegerField(null=True)

    date_sent = models.DateTimeField("date sent", db_index=True)

    # A Client object indicating what type of Zulip client sent this message.
    sending_client = models.ForeignKey(Client, on_delete=CASCADE)

    # The last time the message was modified by message editing or moving.
    last_edit_time = models.DateTimeField(null=True)

    # A JSON-encoded list of objects describing any past edits to this
    # message, oldest first.
    edit_history = models.TextField(null=True)

    # Whether the message contains a (link to) an uploaded file.
    has_attachment = models.BooleanField(default=False, db_index=True)
    # Whether the message contains a visible image element.
    has_image = models.BooleanField(default=False, db_index=True)
    # Whether the message contains a link.
    has_link = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True

    @override
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

    @override
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
                # Used by already_sent_mirrored_message_id, and when
                # determining recent topics (we post-process to merge
                # and show the most recent case)
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

    @override
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

    @override
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
        "stream_wildcard_mentioned",
        "topic_wildcard_mentioned",
        "group_mentioned",
        # These next 2 flags are from features that have since been removed.
        # We've cleared these 2 flags in migration 0486.
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
        "stream_wildcard_mentioned",
        "topic_wildcard_mentioned",
        "group_mentioned",
        "historical",
        # Unused flags can't be edited.
        "force_expand",
        "force_collapse",
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
                | Q(flags__andnz=AbstractUserMessage.flags.stream_wildcard_mentioned.mask),
                name="zerver_usermessage_wildcard_mentioned_message_id",
            ),
            models.Index(
                "user_profile",
                "message",
                condition=Q(
                    flags__andnz=AbstractUserMessage.flags.mentioned.mask
                    | AbstractUserMessage.flags.stream_wildcard_mentioned.mask
                    | AbstractUserMessage.flags.topic_wildcard_mentioned.mask
                    | AbstractUserMessage.flags.group_mentioned.mask
                ),
                name="zerver_usermessage_any_mentioned_message_id",
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

    @override
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

    @staticmethod
    def has_any_mentions(user_profile_id: int, message_id: int) -> bool:
        # The query uses the 'zerver_usermessage_any_mentioned_message_id' index.
        return UserMessage.objects.filter(
            Q(
                flags__andnz=UserMessage.flags.mentioned.mask
                | UserMessage.flags.stream_wildcard_mentioned.mask
                | UserMessage.flags.topic_wildcard_mentioned.mask
                | UserMessage.flags.group_mentioned.mask
            ),
            user_profile_id=user_profile_id,
            message_id=message_id,
        ).exists()


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

    @override
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

    @override
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
    scheduled_messages = models.ManyToManyField("zerver.ScheduledMessage")

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
    delta_weeks_ago = timezone_now() - timedelta(weeks=weeks_ago)

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
    MIN_INTERVAL_LENGTH = timedelta(minutes=15)

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

    @override
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

    @override
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
    read_by_sender = models.BooleanField()
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

    @override
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
    "onboarding_team_to_zulip": ScheduledEmail.WELCOME,
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
    REALM_BILLING_MODALITY_CHANGED = 211
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
    REALM_IMPORTED = 229

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
    CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN = 504

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
    REMOTE_SERVER_DEACTIVATED = 10201
    REMOTE_SERVER_PLAN_TYPE_CHANGED = 10204
    REMOTE_SERVER_DISCOUNT_CHANGED = 10209
    REMOTE_SERVER_SPONSORSHIP_APPROVED = 10210
    REMOTE_SERVER_BILLING_MODALITY_CHANGED = 10211
    REMOTE_SERVER_SPONSORSHIP_PENDING_STATUS_CHANGED = 10213
    REMOTE_SERVER_CREATED = 10215

    # This value is for RemoteRealmAuditLog entries tracking changes to the
    # RemoteRealm model resulting from modified realm information sent to us
    # via send_server_data_to_push_bouncer.
    REMOTE_REALM_VALUE_UPDATED = 20001
    REMOTE_PLAN_TRANSFERRED_SERVER_TO_REALM = 20002
    REMOTE_REALM_LOCALLY_DELETED = 20003

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
        REALM_IMPORTED,
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

    @override
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


class OnboardingStep(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=CASCADE)
    onboarding_step = models.CharField(max_length=30)
    timestamp = models.DateTimeField(default=timezone_now)

    class Meta:
        unique_together = ("user", "onboarding_step")


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
