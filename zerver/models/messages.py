# https://github.com/typeddjango/django-stubs/issues/1698
# mypy: disable-error-code="explicit-override"

import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

from bitfield import BitField
from bitfield.types import Bit, BitHandler
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import CASCADE, F, Q, QuerySet
from django.db.models.functions import Upper
from django.db.models.signals import post_delete, post_save
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext_lazy
from typing_extensions import override

from zerver.lib.cache import flush_message, flush_submessage, flush_used_upload_space_cache
from zerver.models.clients import Client
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.realms import Realm
from zerver.models.recipients import Recipient
from zerver.models.users import UserProfile


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
    API_RECIPIENT_TYPES = ["direct", "private", "stream", "channel"]

    search_tsvector = SearchVectorField(null=True)

    DEFAULT_SELECT_RELATED = ["sender", "realm", "recipient", "sending_client"]

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

    @override
    def __str__(self) -> str:
        return f"{self.user_profile.email} / {self.message.id} / {self.emoji_name}"

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
        """This `SELECT FOR UPDATE OF zerver_usermessage` query ensures
        consistent ordering on the row locks acquired by a bulk update
        operation to modify message flags using bitand/bitor.

        This consistent ordering is important to prevent deadlocks when
        2 or more bulk updates to the same rows in the UserMessage table
        race against each other (For example, if a client submits
        simultaneous duplicate API requests to mark a certain set of
        messages as read).

        """
        return UserMessage.objects.select_for_update(of=("self",)).order_by("message_id")

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
        return UserMessage.objects.get(user_profile=user_profile, message_id=message_id)
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
