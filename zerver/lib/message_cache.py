import copy
import zlib
from datetime import datetime
from email.headerregistry import Address
from typing import Any, Dict, Iterable, List, Optional, TypedDict

import orjson

from zerver.lib.avatar import get_avatar_field, get_avatar_for_inaccessible_user
from zerver.lib.cache import cache_set_many, cache_with_key, to_dict_cache_key, to_dict_cache_key_id
from zerver.lib.display_recipient import bulk_fetch_display_recipients
from zerver.lib.markdown import render_message_markdown, topic_links
from zerver.lib.markdown import version as markdown_version
from zerver.lib.query_helpers import query_for_ids
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import DB_TOPIC_NAME, TOPIC_LINKS, TOPIC_NAME
from zerver.lib.types import DisplayRecipientT, EditHistoryEvent, UserDisplayRecipient
from zerver.models import Message, Reaction, Realm, Recipient, Stream, SubMessage, UserProfile
from zerver.models.realms import get_fake_email_domain


class RawReactionRow(TypedDict):
    emoji_code: str
    emoji_name: str
    message_id: int
    reaction_type: str
    user_profile__email: str
    user_profile__full_name: str
    user_profile_id: int


def sew_messages_and_reactions(
    messages: List[Dict[str, Any]], reactions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Given a iterable of messages and reactions stitch reactions
    into messages.
    """
    # Add all messages with empty reaction item
    for message in messages:
        message["reactions"] = []

    # Convert list of messages into dictionary to make reaction stitching easy
    converted_messages = {message["id"]: message for message in messages}

    for reaction in reactions:
        converted_messages[reaction["message_id"]]["reactions"].append(reaction)

    return list(converted_messages.values())


def sew_messages_and_submessages(
    messages: List[Dict[str, Any]], submessages: List[Dict[str, Any]]
) -> None:
    # This is super similar to sew_messages_and_reactions.
    for message in messages:
        message["submessages"] = []

    message_dict = {message["id"]: message for message in messages}

    for submessage in submessages:
        message_id = submessage["message_id"]
        if message_id in message_dict:
            message = message_dict[message_id]
            message["submessages"].append(submessage)


def extract_message_dict(message_bytes: bytes) -> Dict[str, Any]:
    return orjson.loads(zlib.decompress(message_bytes))


def stringify_message_dict(message_dict: Dict[str, Any]) -> bytes:
    return zlib.compress(orjson.dumps(message_dict))


@cache_with_key(to_dict_cache_key, timeout=3600 * 24)
def message_to_encoded_cache(message: Message, realm_id: Optional[int] = None) -> bytes:
    return MessageDict.messages_to_encoded_cache([message], realm_id)[message.id]


def update_message_cache(
    changed_messages: Iterable[Message], realm_id: Optional[int] = None
) -> List[int]:
    """Updates the message as stored in the to_dict cache (for serving
    messages)."""
    items_for_remote_cache = {}
    message_ids = []
    changed_messages_to_dict = MessageDict.messages_to_encoded_cache(changed_messages, realm_id)
    for msg_id, msg in changed_messages_to_dict.items():
        message_ids.append(msg_id)
        key = to_dict_cache_key_id(msg_id)
        items_for_remote_cache[key] = (msg,)

    cache_set_many(items_for_remote_cache)
    return message_ids


def save_message_rendered_content(message: Message, content: str) -> str:
    rendering_result = render_message_markdown(message, content, realm=message.get_realm())
    rendered_content = None
    if rendering_result is not None:
        rendered_content = rendering_result.rendered_content
    message.rendered_content = rendered_content
    message.rendered_content_version = markdown_version
    message.save_rendered_content()
    return rendered_content


class ReactionDict:
    @staticmethod
    def build_dict_from_raw_db_row(row: RawReactionRow) -> Dict[str, Any]:
        return {
            "emoji_name": row["emoji_name"],
            "emoji_code": row["emoji_code"],
            "reaction_type": row["reaction_type"],
            # TODO: We plan to remove this redundant user dictionary once
            # clients are updated to support accessing use user_id.  See
            # https://github.com/zulip/zulip/pull/14711 for details.
            #
            # When we do that, we can likely update the `.values()` query to
            # not fetch the extra user_profile__* fields from the database
            # as a small performance optimization.
            "user": {
                "email": row["user_profile__email"],
                "id": row["user_profile_id"],
                "full_name": row["user_profile__full_name"],
            },
            "user_id": row["user_profile_id"],
        }


class MessageDict:
    """MessageDict is the core class responsible for marshalling Message
    objects obtained from the database into a format that can be sent
    to clients via the Zulip API, whether via `GET /messages`,
    outgoing webhooks, or other code paths.  There are two core flows through
    which this class is used:

    * For just-sent messages, we construct a single `wide_dict` object
      containing all the data for the message and the related
      UserProfile models (sender_info and recipient_info); this object
      can be stored in queues, caches, etc., and then later turned
      into an API-format JSONable dictionary via finalize_payload.

    * When fetching messages from the database, we fetch their data in
      bulk using messages_for_ids, which makes use of caching, bulk
      fetches that skip the Django ORM, etc., to provide an optimized
      interface for fetching hundreds of thousands of messages from
      the database and then turning them into API-format JSON
      dictionaries.

    """

    @staticmethod
    def wide_dict(message: Message, realm_id: Optional[int] = None) -> Dict[str, Any]:
        """
        The next two lines get the cacheable field related
        to our message object, with the side effect of
        populating the cache.
        """
        encoded_object_bytes = message_to_encoded_cache(message, realm_id)
        obj = extract_message_dict(encoded_object_bytes)

        """
        The steps below are similar to what we do in
        post_process_dicts(), except we don't call finalize_payload(),
        since that step happens later in the queue
        processor.
        """
        MessageDict.bulk_hydrate_sender_info([obj])
        MessageDict.bulk_hydrate_recipient_info([obj])

        return obj

    @staticmethod
    def post_process_dicts(
        objs: List[Dict[str, Any]],
        apply_markdown: bool,
        client_gravatar: bool,
        realm: Realm,
    ) -> None:
        """
        NOTE: This function mutates the objects in
              the `objs` list, rather than making
              shallow copies.  It might be safer to
              make shallow copies here, but performance
              is somewhat important here, as we are
              often fetching hundreds of messages.
        """
        MessageDict.bulk_hydrate_sender_info(objs)
        MessageDict.bulk_hydrate_recipient_info(objs)

        for obj in objs:
            can_access_sender = obj.get("can_access_sender", True)
            MessageDict.finalize_payload(
                obj,
                apply_markdown,
                client_gravatar,
                skip_copy=True,
                can_access_sender=can_access_sender,
                realm_host=realm.host,
            )

    @staticmethod
    def finalize_payload(
        obj: Dict[str, Any],
        apply_markdown: bool,
        client_gravatar: bool,
        keep_rendered_content: bool = False,
        skip_copy: bool = False,
        can_access_sender: bool = True,
        realm_host: str = "",
    ) -> Dict[str, Any]:
        """
        By default, we make a shallow copy of the incoming dict to avoid
        mutation-related bugs.  Code paths that are passing a unique object
        can pass skip_copy=True to avoid this extra work.
        """
        if not skip_copy:
            obj = copy.copy(obj)

        if obj["sender_email_address_visibility"] != UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE:
            # If email address of the sender is only available to administrators,
            # clients cannot compute gravatars, so we force-set it to false.
            # If we plumbed the current user's role, we could allow client_gravatar=True
            # here if the current user's role has access to the target user's email address.
            client_gravatar = False

        if not can_access_sender:
            # Enforce inability to access details of inaccessible
            # users. We should be able to remove the realm_host and
            # can_access_user plumbing to this function if/when we
            # shift the Zulip API to not send these denormalized
            # fields about message senders favor of just sending the
            # sender's user ID.
            obj["sender_full_name"] = str(UserProfile.INACCESSIBLE_USER_NAME)
            sender_id = obj["sender_id"]
            obj["sender_email"] = Address(
                username=f"user{sender_id}", domain=get_fake_email_domain(realm_host)
            ).addr_spec

        MessageDict.set_sender_avatar(obj, client_gravatar, can_access_sender)
        if apply_markdown:
            obj["content_type"] = "text/html"
            obj["content"] = obj["rendered_content"]
        else:
            obj["content_type"] = "text/x-markdown"

        if not keep_rendered_content:
            del obj["rendered_content"]
        del obj["sender_realm_id"]
        del obj["sender_avatar_source"]
        del obj["sender_delivery_email"]
        del obj["sender_avatar_version"]

        del obj["recipient_type"]
        del obj["recipient_type_id"]
        del obj["sender_is_mirror_dummy"]
        del obj["sender_email_address_visibility"]
        if "can_access_sender" in obj:
            del obj["can_access_sender"]
        return obj

    @staticmethod
    def sew_submessages_and_reactions_to_msgs(
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        msg_ids = [msg["id"] for msg in messages]
        submessages = SubMessage.get_raw_db_rows(msg_ids)
        sew_messages_and_submessages(messages, submessages)

        reactions = Reaction.get_raw_db_rows(msg_ids)
        return sew_messages_and_reactions(messages, reactions)

    @staticmethod
    def messages_to_encoded_cache(
        messages: Iterable[Message], realm_id: Optional[int] = None
    ) -> Dict[int, bytes]:
        messages_dict = MessageDict.messages_to_encoded_cache_helper(messages, realm_id)
        encoded_messages = {msg["id"]: stringify_message_dict(msg) for msg in messages_dict}
        return encoded_messages

    @staticmethod
    def messages_to_encoded_cache_helper(
        messages: Iterable[Message], realm_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        # Near duplicate of the build_message_dict + get_raw_db_rows
        # code path that accepts already fetched Message objects
        # rather than message IDs.

        def get_rendering_realm_id(message: Message) -> int:
            # realm_id can differ among users, currently only possible
            # with cross realm bots.
            if realm_id is not None:
                return realm_id
            if message.recipient.type == Recipient.STREAM:
                return Stream.objects.get(id=message.recipient.type_id).realm_id
            return message.realm_id

        message_rows = [
            {
                "id": message.id,
                DB_TOPIC_NAME: message.topic_name(),
                "date_sent": message.date_sent,
                "last_edit_time": message.last_edit_time,
                "edit_history": message.edit_history,
                "content": message.content,
                "rendered_content": message.rendered_content,
                "rendered_content_version": message.rendered_content_version,
                "recipient_id": message.recipient.id,
                "recipient__type": message.recipient.type,
                "recipient__type_id": message.recipient.type_id,
                "rendering_realm_id": get_rendering_realm_id(message),
                "sender_id": message.sender.id,
                "sending_client__name": message.sending_client.name,
                "sender__realm_id": message.sender.realm_id,
            }
            for message in messages
        ]

        MessageDict.sew_submessages_and_reactions_to_msgs(message_rows)
        return [MessageDict.build_dict_from_raw_db_row(row) for row in message_rows]

    @staticmethod
    def ids_to_dict(needed_ids: List[int]) -> List[Dict[str, Any]]:
        # This is a special purpose function optimized for
        # callers like get_messages_backend().
        fields = [
            "id",
            DB_TOPIC_NAME,
            "date_sent",
            "last_edit_time",
            "edit_history",
            "content",
            "rendered_content",
            "rendered_content_version",
            "recipient_id",
            "recipient__type",
            "recipient__type_id",
            "sender_id",
            "sending_client__name",
            "sender__realm_id",
        ]
        # Uses index: zerver_message_pkey
        messages = Message.objects.filter(id__in=needed_ids).values(*fields)
        MessageDict.sew_submessages_and_reactions_to_msgs(messages)
        return [MessageDict.build_dict_from_raw_db_row(row) for row in messages]

    @staticmethod
    def build_dict_from_raw_db_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        row is a row from a .values() call, and it needs to have
        all the relevant fields populated
        """
        return MessageDict.build_message_dict(
            message_id=row["id"],
            last_edit_time=row["last_edit_time"],
            edit_history_json=row["edit_history"],
            content=row["content"],
            topic_name=row[DB_TOPIC_NAME],
            date_sent=row["date_sent"],
            rendered_content=row["rendered_content"],
            rendered_content_version=row["rendered_content_version"],
            sender_id=row["sender_id"],
            sender_realm_id=row["sender__realm_id"],
            sending_client_name=row["sending_client__name"],
            rendering_realm_id=row.get("rendering_realm_id", row["sender__realm_id"]),
            recipient_id=row["recipient_id"],
            recipient_type=row["recipient__type"],
            recipient_type_id=row["recipient__type_id"],
            reactions=row["reactions"],
            submessages=row["submessages"],
        )

    @staticmethod
    def build_message_dict(
        message_id: int,
        last_edit_time: Optional[datetime],
        edit_history_json: Optional[str],
        content: str,
        topic_name: str,
        date_sent: datetime,
        rendered_content: Optional[str],
        rendered_content_version: Optional[int],
        sender_id: int,
        sender_realm_id: int,
        sending_client_name: str,
        rendering_realm_id: int,
        recipient_id: int,
        recipient_type: int,
        recipient_type_id: int,
        reactions: List[RawReactionRow],
        submessages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        obj = dict(
            id=message_id,
            sender_id=sender_id,
            content=content,
            recipient_type_id=recipient_type_id,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            timestamp=datetime_to_timestamp(date_sent),
            client=sending_client_name,
        )

        obj[TOPIC_NAME] = topic_name
        obj["sender_realm_id"] = sender_realm_id

        # Render topic_links with the stream's realm instead of the
        # sender's realm; this is important for messages sent by
        # cross-realm bots like NOTIFICATION_BOT.
        obj[TOPIC_LINKS] = topic_links(rendering_realm_id, topic_name)

        if last_edit_time is not None:
            obj["last_edit_timestamp"] = datetime_to_timestamp(last_edit_time)
            assert edit_history_json is not None
            edit_history: List[EditHistoryEvent] = orjson.loads(edit_history_json)
            obj["edit_history"] = edit_history

        if Message.need_to_render_content(
            rendered_content, rendered_content_version, markdown_version
        ):
            # We really shouldn't be rendering objects in this method, but there is
            # a scenario where we upgrade the version of Markdown and fail to run
            # management commands to re-render historical messages, and then we
            # need to have side effects.  This method is optimized to not need full
            # blown ORM objects, but the Markdown renderer is unfortunately highly
            # coupled to Message, and we also need to persist the new rendered content.
            # If we don't have a message object passed in, we get one here.  The cost
            # of going to the DB here should be overshadowed by the cost of rendering
            # and updating the row.
            # TODO: see #1379 to eliminate Markdown dependencies
            message = Message.objects.select_related("sender").get(id=message_id)

            assert message is not None  # Hint for mypy.
            # It's unfortunate that we need to have side effects on the message
            # in some cases.
            rendered_content = save_message_rendered_content(message, content)

        if rendered_content is not None:
            obj["rendered_content"] = rendered_content
        else:
            obj["rendered_content"] = (
                "<p>[Zulip note: Sorry, we could not understand the formatting of your message]</p>"
            )

        if rendered_content is not None:
            obj["is_me_message"] = Message.is_status_message(content, rendered_content)
        else:
            obj["is_me_message"] = False

        obj["reactions"] = [
            ReactionDict.build_dict_from_raw_db_row(reaction) for reaction in reactions
        ]
        obj["submessages"] = submessages
        return obj

    @staticmethod
    def bulk_hydrate_sender_info(objs: List[Dict[str, Any]]) -> None:
        sender_ids = list({obj["sender_id"] for obj in objs})

        if not sender_ids:
            return

        query = UserProfile.objects.values(
            "id",
            "full_name",
            "delivery_email",
            "email",
            "realm__string_id",
            "avatar_source",
            "avatar_version",
            "is_mirror_dummy",
            "email_address_visibility",
        )

        rows = query_for_ids(query, sender_ids, "zerver_userprofile.id")

        sender_dict = {row["id"]: row for row in rows}

        for obj in objs:
            sender_id = obj["sender_id"]
            user_row = sender_dict[sender_id]
            obj["sender_full_name"] = user_row["full_name"]
            obj["sender_email"] = user_row["email"]
            obj["sender_delivery_email"] = user_row["delivery_email"]
            obj["sender_realm_str"] = user_row["realm__string_id"]
            obj["sender_avatar_source"] = user_row["avatar_source"]
            obj["sender_avatar_version"] = user_row["avatar_version"]
            obj["sender_is_mirror_dummy"] = user_row["is_mirror_dummy"]
            obj["sender_email_address_visibility"] = user_row["email_address_visibility"]

    @staticmethod
    def hydrate_recipient_info(obj: Dict[str, Any], display_recipient: DisplayRecipientT) -> None:
        """
        This method hyrdrates recipient info with things
        like full names and emails of senders.  Eventually
        our clients should be able to hyrdrate these fields
        themselves with info they already have on users.
        """

        recipient_type = obj["recipient_type"]
        recipient_type_id = obj["recipient_type_id"]
        sender_is_mirror_dummy = obj["sender_is_mirror_dummy"]
        sender_email = obj["sender_email"]
        sender_full_name = obj["sender_full_name"]
        sender_id = obj["sender_id"]

        if recipient_type == Recipient.STREAM:
            display_type = "stream"
        elif recipient_type in (Recipient.DIRECT_MESSAGE_GROUP, Recipient.PERSONAL):
            assert not isinstance(display_recipient, str)
            display_type = "private"
            if len(display_recipient) == 1:
                # add the sender in if this isn't a message between
                # someone and themself, preserving ordering
                recip: UserDisplayRecipient = {
                    "email": sender_email,
                    "full_name": sender_full_name,
                    "id": sender_id,
                    "is_mirror_dummy": sender_is_mirror_dummy,
                }
                if recip["email"] < display_recipient[0]["email"]:
                    display_recipient = [recip, display_recipient[0]]
                elif recip["email"] > display_recipient[0]["email"]:
                    display_recipient = [display_recipient[0], recip]
        else:
            raise AssertionError(f"Invalid recipient type {recipient_type}")

        obj["display_recipient"] = display_recipient
        obj["type"] = display_type
        if obj["type"] == "stream":
            obj["stream_id"] = recipient_type_id

    @staticmethod
    def bulk_hydrate_recipient_info(objs: List[Dict[str, Any]]) -> None:
        recipient_tuples = {  # We use set to eliminate duplicate tuples.
            (
                obj["recipient_id"],
                obj["recipient_type"],
                obj["recipient_type_id"],
            )
            for obj in objs
        }
        display_recipients = bulk_fetch_display_recipients(recipient_tuples)

        for obj in objs:
            MessageDict.hydrate_recipient_info(obj, display_recipients[obj["recipient_id"]])

    @staticmethod
    def set_sender_avatar(
        obj: Dict[str, Any], client_gravatar: bool, can_access_sender: bool = True
    ) -> None:
        if not can_access_sender:
            obj["avatar_url"] = get_avatar_for_inaccessible_user()
            return

        sender_id = obj["sender_id"]
        sender_realm_id = obj["sender_realm_id"]
        sender_delivery_email = obj["sender_delivery_email"]
        sender_avatar_source = obj["sender_avatar_source"]
        sender_avatar_version = obj["sender_avatar_version"]

        obj["avatar_url"] = get_avatar_field(
            user_id=sender_id,
            realm_id=sender_realm_id,
            email=sender_delivery_email,
            avatar_source=sender_avatar_source,
            avatar_version=sender_avatar_version,
            medium=False,
            client_gravatar=client_gravatar,
        )
