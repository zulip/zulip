"""
Import data from DiscordChatExporter JSON exports.

DiscordChatExporter (https://github.com/Tyrrrz/DiscordChatExporter) produces
a directory of JSON files, one per channel, plus a _media/ folder with all
attachments, avatars, and emoji cached locally.  This means no API calls are
needed during import—everything is already on disk.

Usage:
    ./manage.py convert_discord_data <export_dir> --output <output_dir>
    ./manage.py import <subdomain> <output_dir>
"""

import dataclasses
import logging
import os
import re
import shutil
from collections.abc import Iterator
from typing import Any

import orjson
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now

from zerver.data_import.discord_message_conversion import convert_to_zulip_markdown
from zerver.data_import.import_util import (
    SubscriberHandler,
    UploadRecordData,
    ZerverFieldsT,
    build_attachment,
    build_direct_message_group,
    build_direct_message_group_subscriptions,
    build_message,
    build_personal_subscriptions,
    build_realm,
    build_realm_emoji,
    build_recipients,
    build_stream,
    build_stream_subscriptions,
    build_user_profile,
    build_usermessages,
    build_zerver_realm,
    create_converted_data_files,
    get_attachment_path_and_content,
    long_term_idle_helper,
    make_subscriber_map,
)
from zerver.data_import.sequencer import NEXT_ID, IdMapper
from zerver.data_import.user_handler import UserHandler
from zerver.lib.emoji import name_to_codepoint
from zerver.lib.export import do_common_export_processes
from zerver.lib.markdown import IMAGE_EXTENSIONS
from zerver.models import Reaction, RealmEmoji, Recipient, UserProfile

# Message types that carry no user content and should be skipped.
SYSTEM_MESSAGE_TYPES = {
    "GuildMemberJoin",
    "ThreadCreated",
    "ChannelPinnedMessage",
    "RecipientAdd",
    "RecipientRemove",
    "Call",
}

# Channel types representing threads in Discord.
THREAD_CHANNEL_TYPES = {
    "GuildPublicThread",
    "GuildPrivateThread",
}


@dataclasses.dataclass
class DiscordExportMetadata:
    """Lightweight metadata extracted from a single pass over all JSON files.

    Collecting this in one pass avoids holding all parsed JSON in memory.
    """

    discord_users: dict[str, dict[str, Any]]
    channel_info: list[dict[str, Any]]
    thread_topic_map: dict[str, tuple[str, str]]
    dm_participants: dict[str, set[str]]
    custom_emoji: dict[str, dict[str, Any]]
    reply_content_map: dict[str, str]
    guild_name: str
    guild_icon_url: str | None
    channel_id_to_name: dict[str, str]


def discover_export_files(discord_data_dir: str) -> list[str]:
    """Find all JSON channel files in the export directory.

    DiscordChatExporter organises exports inside timestamp-named
    subdirectories.  We walk the entire tree and collect every .json
    file, excluding anything inside _media/.
    """
    json_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(discord_data_dir):
        # Skip _media directory
        dirnames[:] = [d for d in dirnames if d != "_media"]
        json_files.extend(
            os.path.join(dirpath, filename) for filename in filenames if filename.endswith(".json")
        )
    return sorted(json_files)


def parse_channel_file(filepath: str) -> dict[str, Any]:
    """Read and parse a single DiscordChatExporter JSON file."""
    with open(filepath, "rb") as f:
        return orjson.loads(f.read())


def collect_metadata(json_files: list[str]) -> DiscordExportMetadata:
    """Extract all metadata from JSON files in a single pass.

    Each file is parsed, metadata extracted, then the parsed dict is
    discarded.  This keeps peak memory to one file at a time plus the
    lightweight metadata dicts.
    """
    discord_users: dict[str, dict[str, Any]] = {}
    channel_info: list[dict[str, Any]] = []
    thread_topic_map: dict[str, tuple[str, str]] = {}
    dm_participants: dict[str, set[str]] = {}
    custom_emoji: dict[str, dict[str, Any]] = {}
    reply_content_map: dict[str, str] = {}
    guild_name = "Discord Server"
    guild_icon_url: str | None = None
    channel_id_to_name: dict[str, str] = {}

    for filepath in json_files:
        data = parse_channel_file(filepath)
        channel = data["channel"]

        # Collect channel metadata (without messages).
        channel_info.append(channel)

        # Extract guild info.
        guild = data.get("guild")
        if guild:
            if guild.get("name"):
                guild_name = guild["name"]
            if guild.get("iconUrl") and guild_icon_url is None:
                guild_icon_url = guild["iconUrl"]

        # Build channel_id_to_name for guild text/voice channels.
        if channel["type"] in ("GuildTextChat", "GuildVoiceChat"):
            channel_id_to_name[channel["id"]] = channel["name"]

        # Build thread topic map.
        if channel["type"] in THREAD_CHANNEL_TYPES:
            thread_topic_map[channel["id"]] = (channel["categoryId"], channel["name"])

        # Process messages for user, DM, emoji, and reply metadata.
        channel_type = channel["type"]
        is_dm_channel = channel_type in ("DirectMessage", "DirectGroupMessage")
        channel_id = channel["id"]
        if is_dm_channel and channel_id not in dm_participants:
            dm_participants[channel_id] = set()

        for message in data.get("messages", []):
            # Collect users.
            author = message["author"]
            discord_users[author["id"]] = author

            # Collect DM participants.
            if is_dm_channel:
                dm_participants[channel_id].add(author["id"])

            # Collect custom emoji from reactions.
            for reaction in message.get("reactions", []):
                emoji_info = reaction["emoji"]
                if emoji_info.get("id"):
                    emoji_name = emoji_info.get("code") or emoji_info.get("name", "")
                    if emoji_name and emoji_name not in custom_emoji:
                        custom_emoji[emoji_name] = emoji_info

            # Store reply content (message ID → content string only).
            msg_content = message.get("content")
            if msg_content:
                reply_content_map[message["id"]] = msg_content

        del data  # Free memory before next file.

    return DiscordExportMetadata(
        discord_users=discord_users,
        channel_info=channel_info,
        thread_topic_map=thread_topic_map,
        dm_participants=dm_participants,
        custom_emoji=custom_emoji,
        reply_content_map=reply_content_map,
        guild_name=guild_name,
        guild_icon_url=guild_icon_url,
        channel_id_to_name=channel_id_to_name,
    )


def convert_user_data(
    user_handler: UserHandler,
    user_id_mapper: IdMapper[str],
    discord_users: dict[str, dict[str, Any]],
    realm_id: int,
    domain_name: str,
) -> None:
    """Convert Discord users into Zulip UserProfile records."""
    used_emails: set[str] = set()
    has_owner = False

    for discord_user_id, author in discord_users.items():
        zulip_user_id = user_id_mapper.get(discord_user_id)

        full_name = author.get("nickname") or author["name"]
        short_name = author["name"]

        # Generate a synthetic email, ensuring uniqueness.
        email = f"{short_name}@{domain_name}"
        if email in used_emails:
            email = f"{short_name}_{discord_user_id}@{domain_name}"
        used_emails.add(email)

        is_bot = author.get("isBot", False)

        # The first non-bot user becomes the realm owner, which is
        # required by the import framework for emoji author assignment.
        if not is_bot and not has_owner:
            role = UserProfile.ROLE_REALM_OWNER
            has_owner = True
        else:
            role = UserProfile.ROLE_MEMBER

        avatar_source = "U" if author.get("avatarUrl") else "G"

        user = build_user_profile(
            avatar_source=avatar_source,
            date_joined=int(timezone_now().timestamp()),
            delivery_email=email,
            email=email,
            full_name=full_name,
            id=zulip_user_id,
            is_active=True,
            role=role,
            is_mirror_dummy=False,
            realm_id=realm_id,
            short_name=short_name,
            timezone="UTC",
            is_bot=is_bot,
            bot_type=1 if is_bot else None,
        )
        user_handler.add_user(user)

    user_handler.validate_user_emails()


def convert_channel_data(
    channel_info: list[dict[str, Any]],
    subscriber_handler: SubscriberHandler,
    stream_id_mapper: IdMapper[str],
    user_id_mapper: IdMapper[str],
    realm_id: int,
    all_user_ids: set[int],
) -> list[ZerverFieldsT]:
    """Convert Discord guild text/voice channels to Zulip streams.

    Threads are excluded here—they become topics within their parent stream.
    """
    now = int(timezone_now().timestamp())
    streams: list[ZerverFieldsT] = []
    seen_channel_ids: set[str] = set()

    for channel in channel_info:
        channel_id = channel["id"]
        channel_type = channel["type"]

        # Skip threads, DMs, and group DMs—they are handled separately.
        if channel_type in THREAD_CHANNEL_TYPES:
            continue
        if channel_type in ("DirectMessage", "DirectGroupMessage"):
            continue
        if channel_id in seen_channel_ids:
            continue
        seen_channel_ids.add(channel_id)

        # GuildTextChat and GuildVoiceChat both become streams.
        if channel_type not in ("GuildTextChat", "GuildVoiceChat"):
            continue

        stream_id = stream_id_mapper.get(channel_id)
        stream = build_stream(
            date_created=now,
            realm_id=realm_id,
            name=channel["name"],
            description=channel.get("topic") or "",
            stream_id=stream_id,
            deactivated=False,
            invite_only=False,
        )
        streams.append(stream)

        # Subscribe all users to every stream since Discord exports
        # don't include membership data.  all_user_ids is already a
        # set[int] and SubscriberHandler.get_users() is read-only, so
        # sharing the reference avoids O(users) copies per stream.
        subscriber_handler.set_info(users=all_user_ids, stream_id=stream_id)

    return streams


def convert_direct_message_group_data(
    dm_participants: dict[str, set[str]],
    channel_info: list[dict[str, Any]],
    subscriber_handler: SubscriberHandler,
    direct_message_group_id_mapper: IdMapper[frozenset[str]],
    user_id_mapper: IdMapper[str],
) -> list[ZerverFieldsT]:
    """Convert Discord group DMs to Zulip DirectMessageGroup objects."""
    zerver_direct_message_group: list[ZerverFieldsT] = []
    seen_channel_ids: set[str] = set()

    for channel in channel_info:
        if channel["type"] != "DirectGroupMessage":
            continue
        channel_id = channel["id"]
        if channel_id in seen_channel_ids:
            continue
        seen_channel_ids.add(channel_id)

        participant_discord_ids = dm_participants.get(channel_id, set())
        if len(participant_discord_ids) < 2:
            continue

        members_key = frozenset(participant_discord_ids)
        if direct_message_group_id_mapper.has(members_key):
            continue

        group_id = direct_message_group_id_mapper.get(members_key)
        group_dict = build_direct_message_group(group_id, len(participant_discord_ids))
        zerver_direct_message_group.append(group_dict)

        zulip_user_ids = {user_id_mapper.get(uid) for uid in participant_discord_ids}
        subscriber_handler.set_info(
            users=zulip_user_ids,
            direct_message_group_id=group_id,
        )

    return zerver_direct_message_group


def build_recipient_maps(
    zerver_recipient: list[ZerverFieldsT],
) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    """Build lookup dicts from recipient list."""
    stream_id_to_recipient_id: dict[int, int] = {}
    dm_group_id_to_recipient_id: dict[int, int] = {}
    user_id_to_recipient_id: dict[int, int] = {}

    for recipient in zerver_recipient:
        if recipient["type"] == Recipient.STREAM:
            stream_id_to_recipient_id[recipient["type_id"]] = recipient["id"]
        elif recipient["type"] == Recipient.DIRECT_MESSAGE_GROUP:
            dm_group_id_to_recipient_id[recipient["type_id"]] = recipient["id"]
        elif recipient["type"] == Recipient.PERSONAL:
            user_id_to_recipient_id[recipient["type_id"]] = recipient["id"]

    return stream_id_to_recipient_id, dm_group_id_to_recipient_id, user_id_to_recipient_id


def build_user_id_to_fullname(
    discord_users: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Build Discord user ID -> full name map for mention conversion."""
    return {uid: author.get("nickname") or author["name"] for uid, author in discord_users.items()}


def get_message_recipient_id(
    channel: dict[str, Any],
    message: dict[str, Any],
    stream_id_mapper: IdMapper[str],
    user_id_mapper: IdMapper[str],
    direct_message_group_id_mapper: IdMapper[frozenset[str]],
    dm_participants: dict[str, set[str]],
    thread_topic_map: dict[str, tuple[str, str]],
    stream_id_to_recipient_id: dict[int, int],
    dm_group_id_to_recipient_id: dict[int, int],
    user_id_to_recipient_id: dict[int, int],
) -> tuple[int, bool, str]:
    """Determine the Zulip recipient_id and topic for a Discord message.

    Returns (recipient_id, is_direct_message_type, topic_name).
    """
    channel_id = channel["id"]
    channel_type = channel["type"]

    if channel_type in THREAD_CHANNEL_TYPES:
        parent_channel_id, thread_name = thread_topic_map[channel_id]
        stream_id = stream_id_mapper.get(parent_channel_id)
        recipient_id = stream_id_to_recipient_id[stream_id]
        return recipient_id, False, thread_name

    if channel_type in ("GuildTextChat", "GuildVoiceChat"):
        stream_id = stream_id_mapper.get(channel_id)
        recipient_id = stream_id_to_recipient_id[stream_id]
        return recipient_id, False, "imported from Discord"

    if channel_type == "DirectGroupMessage":
        participant_ids = dm_participants.get(channel_id, set())
        members_key = frozenset(participant_ids)
        group_id = direct_message_group_id_mapper.get(members_key)
        recipient_id = dm_group_id_to_recipient_id[group_id]
        return recipient_id, True, ""

    if channel_type == "DirectMessage":
        # For 1:1 DMs, route to the *other* user's personal recipient.
        sender_id = message["author"]["id"]
        participant_ids = dm_participants.get(channel_id, set())
        other_ids = participant_ids - {sender_id}
        if other_ids:
            other_discord_id = next(iter(other_ids))
        else:
            # Self-DM edge case.
            other_discord_id = sender_id
        other_zulip_id = user_id_mapper.get(other_discord_id)
        recipient_id = user_id_to_recipient_id[other_zulip_id]
        return recipient_id, True, ""

    raise AssertionError(f"Unexpected channel type: {channel_type}")


def build_discord_reactions(
    reactions: list[dict[str, Any]],
    message_id: int,
    user_id_mapper: IdMapper[str],
    total_reactions: list[ZerverFieldsT],
    zerver_realmemoji: list[ZerverFieldsT],
) -> None:
    """Convert Discord reactions to Zulip Reaction records."""
    realmemoji_map: dict[str, int] = {}
    for emoji in zerver_realmemoji:
        realmemoji_map[emoji["name"]] = emoji["id"]

    for reaction_data in reactions:
        emoji_info = reaction_data["emoji"]
        emoji_name = emoji_info.get("code") or emoji_info.get("name", "")

        # Determine reaction type.
        if emoji_info.get("id"):
            # Custom emoji
            if emoji_name in realmemoji_map:
                emoji_code = str(realmemoji_map[emoji_name])
                reaction_type = Reaction.REALM_EMOJI
            else:
                continue
        elif emoji_name in name_to_codepoint:
            emoji_code = name_to_codepoint[emoji_name]
            reaction_type = Reaction.UNICODE_EMOJI
        else:
            continue

        for user in reaction_data.get("users", []):
            discord_user_id = user["id"]
            if not user_id_mapper.has(discord_user_id):
                continue

            reaction_id = NEXT_ID("reaction")
            reaction = Reaction(
                id=reaction_id,
                emoji_code=emoji_code,
                emoji_name=emoji_name,
                reaction_type=reaction_type,
            )
            reaction_dict = model_to_dict(reaction, exclude=["message", "user_profile"])
            reaction_dict["message"] = message_id
            reaction_dict["user_profile"] = user_id_mapper.get(discord_user_id)
            total_reactions.append(reaction_dict)


def process_discord_attachments(
    attachments: list[dict[str, Any]],
    realm_id: int,
    message_id: int,
    user_id: int,
    discord_data_dir: str,
    output_dir: str,
    zerver_attachment: list[ZerverFieldsT],
    uploads_list: list[UploadRecordData],
) -> tuple[str, bool]:
    """Copy local attachment files and create Zulip attachment records.

    Returns (attachment_markdown, has_image).
    """
    has_image = False
    markdown_links: list[str] = []

    for attachment in attachments:
        file_name = attachment["fileName"]
        local_url = attachment["url"]

        # Resolve the local path relative to the export directory.
        attachment_full_path = os.path.join(discord_data_dir, local_url)
        if not os.path.exists(attachment_full_path):
            logging.warning("Attachment file not found: %s", attachment_full_path)
            continue

        file_ext = f".{file_name.split('.')[-1]}" if "." in file_name else ""
        if file_ext.lower() in IMAGE_EXTENSIONS:
            has_image = True

        attachment_data = get_attachment_path_and_content(
            link_name=file_name, filename=file_name, realm_id=realm_id
        )
        markdown_links.append(attachment_data.markdown_link)

        file_size = os.path.getsize(attachment_full_path)
        file_mtime = os.path.getmtime(attachment_full_path)

        fileinfo: ZerverFieldsT = {
            "name": file_name,
            "size": file_size,
            "created": file_mtime,
        }

        uploads_list.append(
            UploadRecordData(
                content_type=None,
                last_modified=file_mtime,
                path=attachment_data.path_id,
                realm_id=realm_id,
                s3_path=attachment_data.path_id,
                size=file_size,
                user_profile_id=user_id,
            )
        )

        build_attachment(
            realm_id=realm_id,
            message_ids={message_id},
            user_id=user_id,
            fileinfo=fileinfo,
            s3_path=attachment_data.path_id,
            zerver_attachment=zerver_attachment,
        )

        attachment_out_path = os.path.join(output_dir, "uploads", attachment_data.path_id)
        os.makedirs(os.path.dirname(attachment_out_path), exist_ok=True)
        shutil.copyfile(attachment_full_path, attachment_out_path)

    content = "\n".join(markdown_links)
    return content, has_image


def find_replied_message_content(
    message: dict[str, Any],
    reply_content_map: dict[str, str],
) -> str | None:
    """For Reply messages, find the original message content for quoting."""
    reference = message.get("reference")
    if reference is None:
        return None
    ref_message_id = reference.get("messageId")
    if ref_message_id and ref_message_id in reply_content_map:
        return reply_content_map[ref_message_id]
    return None


def process_message_batch(
    realm_id: int,
    raw_messages: list[dict[str, Any]],
    subscriber_map: dict[int, set[int]],
    is_pm_data: bool,
    output_dir: str,
    total_reactions: list[ZerverFieldsT],
    user_id_mapper: IdMapper[str],
    zerver_realmemoji: list[ZerverFieldsT],
    uploads_list: list[UploadRecordData],
    zerver_attachment: list[ZerverFieldsT],
    discord_data_dir: str,
    user_id_to_fullname: dict[str, str],
    user_id_to_zulip_id: dict[str, int],
    channel_id_to_name: dict[str, str],
    long_term_idle: set[int],
) -> None:
    """Process a batch of messages and write to a messages-NNNNNN.json file."""
    mention_map: dict[int, set[int]] = {}
    zerver_message: list[ZerverFieldsT] = []

    for raw_msg in raw_messages:
        message_id = NEXT_ID("message")
        content = raw_msg["content"]

        # For Reply messages, prepend quoted original content.
        if raw_msg["is_reply"]:
            original_content = raw_msg.get("original_content")
            if original_content:
                content = f"> {original_content}\n\n{content}"

        # Convert Discord markdown to Zulip markdown.
        content, mentioned_user_ids, has_link = convert_to_zulip_markdown(
            content,
            user_id_to_fullname,
            user_id_to_zulip_id,
            channel_id_to_name,
        )

        mention_map[message_id] = mentioned_user_ids

        has_attachment = False
        has_image = False
        if raw_msg["attachments"]:
            has_attachment = True
            has_link = True
            attachment_markdown, has_image = process_discord_attachments(
                attachments=raw_msg["attachments"],
                realm_id=realm_id,
                message_id=message_id,
                user_id=raw_msg["sender_id"],
                discord_data_dir=discord_data_dir,
                output_dir=output_dir,
                zerver_attachment=zerver_attachment,
                uploads_list=uploads_list,
            )
            if attachment_markdown:
                content += "\n" + attachment_markdown

        message = build_message(
            content=content,
            message_id=message_id,
            date_sent=raw_msg["date_sent"],
            recipient_id=raw_msg["recipient_id"],
            realm_id=realm_id,
            rendered_content=None,
            topic_name=raw_msg["topic_name"],
            user_id=raw_msg["sender_id"],
            is_channel_message=not raw_msg["is_dm"],
            has_image=has_image,
            has_link=has_link,
            has_attachment=has_attachment,
            is_direct_message_type=raw_msg["is_dm"],
        )
        zerver_message.append(message)

        build_discord_reactions(
            reactions=raw_msg["reactions"],
            message_id=message_id,
            user_id_mapper=user_id_mapper,
            total_reactions=total_reactions,
            zerver_realmemoji=zerver_realmemoji,
        )

    zerver_usermessage: list[ZerverFieldsT] = []
    for message in zerver_message:
        build_usermessages(
            zerver_usermessage=zerver_usermessage,
            subscriber_map=subscriber_map,
            recipient_id=message["recipient"],
            mentioned_user_ids=list(mention_map[message["id"]]),
            message_id=message["id"],
            is_private=is_pm_data,
            long_term_idle=long_term_idle,
        )

    message_json = dict(
        zerver_message=zerver_message,
        zerver_usermessage=zerver_usermessage,
    )

    dump_file_id = NEXT_ID("dump_file_id" + str(realm_id))
    message_file = f"/messages-{dump_file_id:06}.json"
    create_converted_data_files(message_json, output_dir, message_file)


def parse_discord_timestamp(timestamp_str: str) -> float:
    """Parse an ISO 8601 timestamp string to a Unix timestamp float."""
    from datetime import datetime

    # Handle both formats: with timezone offset and with Z suffix
    timestamp_str = timestamp_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(timestamp_str)
    return dt.timestamp()


def write_message_data(
    realm_id: int,
    json_files: list[str],
    reply_content_map: dict[str, str],
    stream_id_mapper: IdMapper[str],
    user_id_mapper: IdMapper[str],
    direct_message_group_id_mapper: IdMapper[frozenset[str]],
    dm_participants: dict[str, set[str]],
    thread_topic_map: dict[str, tuple[str, str]],
    stream_id_to_recipient_id: dict[int, int],
    dm_group_id_to_recipient_id: dict[int, int],
    user_id_to_recipient_id: dict[int, int],
    subscriber_map: dict[int, set[int]],
    output_dir: str,
    total_reactions: list[ZerverFieldsT],
    zerver_realmemoji: list[ZerverFieldsT],
    uploads_list: list[UploadRecordData],
    zerver_attachment: list[ZerverFieldsT],
    discord_data_dir: str,
    discord_users: dict[str, dict[str, Any]],
    channel_id_to_name: dict[str, str],
    long_term_idle: set[int],
) -> None:
    """Convert all messages and write message JSON files.

    Re-reads each JSON file one at a time to avoid holding all parsed
    data in memory.  Batches are flushed when they reach chunk_size.
    """
    user_id_to_fullname = build_user_id_to_fullname(discord_users)
    user_id_to_zulip_id: dict[str, int] = {uid: user_id_mapper.get(uid) for uid in discord_users}

    chunk_size = 1000
    channel_raw_messages: list[dict[str, Any]] = []
    dm_raw_messages: list[dict[str, Any]] = []

    def flush_channel_messages() -> None:
        nonlocal channel_raw_messages
        if channel_raw_messages:
            process_message_batch(
                realm_id=realm_id,
                raw_messages=channel_raw_messages,
                subscriber_map=subscriber_map,
                is_pm_data=False,
                output_dir=output_dir,
                total_reactions=total_reactions,
                user_id_mapper=user_id_mapper,
                zerver_realmemoji=zerver_realmemoji,
                uploads_list=uploads_list,
                zerver_attachment=zerver_attachment,
                discord_data_dir=discord_data_dir,
                user_id_to_fullname=user_id_to_fullname,
                user_id_to_zulip_id=user_id_to_zulip_id,
                channel_id_to_name=channel_id_to_name,
                long_term_idle=long_term_idle,
            )
            channel_raw_messages = []

    def flush_dm_messages() -> None:
        nonlocal dm_raw_messages
        if dm_raw_messages:
            process_message_batch(
                realm_id=realm_id,
                raw_messages=dm_raw_messages,
                subscriber_map=subscriber_map,
                is_pm_data=True,
                output_dir=output_dir,
                total_reactions=total_reactions,
                user_id_mapper=user_id_mapper,
                zerver_realmemoji=zerver_realmemoji,
                uploads_list=uploads_list,
                zerver_attachment=zerver_attachment,
                discord_data_dir=discord_data_dir,
                user_id_to_fullname=user_id_to_fullname,
                user_id_to_zulip_id=user_id_to_zulip_id,
                channel_id_to_name=channel_id_to_name,
                long_term_idle=long_term_idle,
            )
            dm_raw_messages = []

    for filepath in json_files:
        data = parse_channel_file(filepath)
        channel = data["channel"]
        for message in data.get("messages", []):
            if message["type"] in SYSTEM_MESSAGE_TYPES:
                continue

            sender_discord_id = message["author"]["id"]
            if not user_id_mapper.has(sender_discord_id):
                continue
            sender_id = user_id_mapper.get(sender_discord_id)

            recipient_id, is_dm, topic_name = get_message_recipient_id(
                channel=channel,
                message=message,
                stream_id_mapper=stream_id_mapper,
                user_id_mapper=user_id_mapper,
                direct_message_group_id_mapper=direct_message_group_id_mapper,
                dm_participants=dm_participants,
                thread_topic_map=thread_topic_map,
                stream_id_to_recipient_id=stream_id_to_recipient_id,
                dm_group_id_to_recipient_id=dm_group_id_to_recipient_id,
                user_id_to_recipient_id=user_id_to_recipient_id,
            )

            is_reply = message["type"] == "Reply"
            original_content = None
            if is_reply:
                original_content = find_replied_message_content(message, reply_content_map)

            raw_msg: dict[str, Any] = {
                "sender_id": sender_id,
                "content": message.get("content", ""),
                "date_sent": parse_discord_timestamp(message["timestamp"]),
                "recipient_id": recipient_id,
                "topic_name": topic_name,
                "is_dm": is_dm,
                "is_reply": is_reply,
                "original_content": original_content,
                "attachments": message.get("attachments", []),
                "reactions": message.get("reactions", []),
            }

            if is_dm:
                dm_raw_messages.append(raw_msg)
                if len(dm_raw_messages) >= chunk_size:
                    flush_dm_messages()
            else:
                channel_raw_messages.append(raw_msg)
                if len(channel_raw_messages) >= chunk_size:
                    flush_channel_messages()

        del data  # Free memory before next file.

    # Flush remaining messages.
    flush_channel_messages()
    flush_dm_messages()


def write_emoticon_data(
    realm_id: int,
    custom_emoji_data: dict[str, dict[str, Any]],
    discord_data_dir: str,
    output_dir: str,
) -> list[ZerverFieldsT]:
    """Process custom emoji and write emoji records."""
    logging.info("Starting to process custom emoji")

    emoji_folder = os.path.join(output_dir, "emoji")
    os.makedirs(emoji_folder, exist_ok=True)

    emoji_records: list[ZerverFieldsT] = []
    zerver_realmemoji: list[ZerverFieldsT] = []

    for emoji_name, emoji_info in custom_emoji_data.items():
        image_url = emoji_info.get("imageUrl", "")
        if not image_url:
            continue

        source_path = os.path.join(discord_data_dir, image_url)
        if not os.path.exists(source_path):
            logging.warning("Emoji file not found: %s", source_path)
            continue

        emoji_id = NEXT_ID("realmemoji")
        target_fn = emoji_name
        target_sub_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=realm_id,
            emoji_file_name=target_fn,
        )
        target_path = os.path.join(emoji_folder, target_sub_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copyfile(os.path.abspath(source_path), os.path.abspath(target_path))

        emoji_records.append(
            dict(
                path=os.path.abspath(target_path),
                s3_path=os.path.abspath(target_path),
                file_name=target_fn,
                realm_id=realm_id,
                name=emoji_name,
            )
        )

        zerver_realmemoji.append(
            build_realm_emoji(
                realm_id=realm_id,
                name=emoji_name,
                id=emoji_id,
                file_name=target_fn,
            )
        )

    create_converted_data_files(emoji_records, output_dir, "/emoji/records.json")
    logging.info("Done processing custom emoji")
    return zerver_realmemoji


def process_avatars(
    discord_users: dict[str, dict[str, Any]],
    user_id_mapper: IdMapper[str],
    realm_id: int,
    discord_data_dir: str,
    output_dir: str,
) -> list[ZerverFieldsT]:
    """Copy avatar files from _media/ to the avatars output directory.

    Unlike Slack, we don't need to download anything—DiscordChatExporter
    already cached all avatars locally.
    """
    from zerver.lib.avatar_hash import user_avatar_base_path_from_ids

    logging.info("Processing avatars")
    avatar_dir = os.path.join(output_dir, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)

    avatar_records: list[ZerverFieldsT] = []

    for discord_user_id, author in discord_users.items():
        avatar_url = author.get("avatarUrl")
        if not avatar_url:
            continue

        avatar_source_path = os.path.join(discord_data_dir, avatar_url)
        if not os.path.exists(avatar_source_path):
            continue

        zulip_user_id = user_id_mapper.get(discord_user_id)
        avatar_hash = user_avatar_base_path_from_ids(zulip_user_id, 1, realm_id)

        image_path = f"{avatar_hash}.png"
        original_image_path = f"{avatar_hash}.original"

        target_image = os.path.join(avatar_dir, image_path)
        target_original = os.path.join(avatar_dir, original_image_path)

        os.makedirs(os.path.dirname(target_image), exist_ok=True)
        shutil.copyfile(avatar_source_path, target_image)
        shutil.copyfile(avatar_source_path, target_original)

        avatar_record = dict(
            path=image_path,
            realm_id=realm_id,
            content_type="image/png",
            avatar_version=1,
            user_profile_id=zulip_user_id,
            last_modified=int(timezone_now().timestamp()),
            s3_path=image_path,
            size=os.path.getsize(avatar_source_path),
        )
        avatar_records.append(avatar_record)

        avatar_original_record = dict(
            path=original_image_path,
            realm_id=realm_id,
            content_type="image/png",
            avatar_version=1,
            user_profile_id=zulip_user_id,
            last_modified=int(timezone_now().timestamp()),
            s3_path=original_image_path,
            size=os.path.getsize(avatar_source_path),
        )
        avatar_records.append(avatar_original_record)

    create_converted_data_files(avatar_records, output_dir, "/avatars/records.json")
    logging.info("Done processing avatars")
    return avatar_records


def process_realm_icon(
    guild_icon_url: str | None,
    realm_id: int,
    discord_data_dir: str,
    output_dir: str,
) -> None:
    """Copy the Discord server icon to the realm icon location."""
    if guild_icon_url is None:
        return

    icon_source = os.path.join(discord_data_dir, guild_icon_url)
    if not os.path.exists(icon_source):
        return

    icon_dir = os.path.join(output_dir, "realm_icons")
    icon_relative_path = os.path.join(str(realm_id), "icon.original")
    icon_dest = os.path.join(icon_dir, icon_relative_path)
    os.makedirs(os.path.dirname(icon_dest), exist_ok=True)
    shutil.copyfile(icon_source, icon_dest)

    records = [
        dict(
            realm_id=realm_id,
            path=icon_relative_path,
            s3_path=icon_relative_path,
        )
    ]
    create_converted_data_files(records, icon_dir, "/records.json")


def discord_message_iterator(json_files: list[str]) -> Iterator[dict[str, Any]]:
    """Yield all non-system messages across all JSON files.

    Re-reads each file one at a time for the long_term_idle_helper scan,
    keeping peak memory to a single file at a time.
    """
    for filepath in json_files:
        data = parse_channel_file(filepath)
        for message in data.get("messages", []):
            if message["type"] not in SYSTEM_MESSAGE_TYPES:
                yield message
        del data


def do_convert_data(discord_data_dir: str, output_dir: str) -> None:
    """Main entry point: convert DiscordChatExporter data to Zulip format."""
    os.makedirs(output_dir, exist_ok=True)
    if os.listdir(output_dir):
        raise Exception("Output directory should be empty!")

    realm_id = NEXT_ID("realm_id")
    domain_name = settings.EXTERNAL_HOST

    json_files = discover_export_files(discord_data_dir)
    if not json_files:
        raise Exception(f"No JSON files found in {discord_data_dir}")

    metadata = collect_metadata(json_files)
    print("Converting data for", metadata.guild_name)

    NOW = float(timezone_now().timestamp())
    realm_subdomain = re.sub(r"[^a-z0-9-]", "", metadata.guild_name.lower().replace(" ", "-"))[:40]
    if not realm_subdomain:
        realm_subdomain = "discord"
    zerver_realm = build_zerver_realm(realm_id, realm_subdomain, NOW, "Discord")
    realm = build_realm(zerver_realm, realm_id, domain_name, import_source="discord")
    realm["zerver_defaultstream"] = []

    user_handler = UserHandler()
    user_id_mapper = IdMapper[str]()
    convert_user_data(
        user_handler=user_handler,
        user_id_mapper=user_id_mapper,
        discord_users=metadata.discord_users,
        realm_id=realm_id,
        domain_name=domain_name,
    )

    all_user_ids = {user["id"] for user in user_handler.get_all_users()}

    subscriber_handler = SubscriberHandler()
    stream_id_mapper = IdMapper[str]()
    zerver_stream = convert_channel_data(
        channel_info=metadata.channel_info,
        subscriber_handler=subscriber_handler,
        stream_id_mapper=stream_id_mapper,
        user_id_mapper=user_id_mapper,
        realm_id=realm_id,
        all_user_ids=all_user_ids,
    )
    realm["zerver_stream"] = zerver_stream

    direct_message_group_id_mapper = IdMapper[frozenset[str]]()
    zerver_direct_message_group = convert_direct_message_group_data(
        dm_participants=metadata.dm_participants,
        channel_info=metadata.channel_info,
        subscriber_handler=subscriber_handler,
        direct_message_group_id_mapper=direct_message_group_id_mapper,
        user_id_mapper=user_id_mapper,
    )
    realm["zerver_huddle"] = zerver_direct_message_group

    all_users = user_handler.get_all_users()
    zerver_recipient = build_recipients(
        zerver_userprofile=all_users,
        zerver_stream=zerver_stream,
        zerver_direct_message_group=zerver_direct_message_group,
    )
    realm["zerver_recipient"] = zerver_recipient

    stream_subscriptions = build_stream_subscriptions(
        get_users=subscriber_handler.get_users,
        zerver_recipient=zerver_recipient,
        zerver_stream=zerver_stream,
    )
    dm_group_subscriptions = build_direct_message_group_subscriptions(
        get_users=subscriber_handler.get_users,
        zerver_recipient=zerver_recipient,
        zerver_direct_message_group=zerver_direct_message_group,
    )
    personal_subscriptions = build_personal_subscriptions(
        zerver_recipient=zerver_recipient,
    )
    zerver_subscription = personal_subscriptions + stream_subscriptions + dm_group_subscriptions
    realm["zerver_subscription"] = zerver_subscription

    zerver_realmemoji = write_emoticon_data(
        realm_id=realm_id,
        custom_emoji_data=metadata.custom_emoji,
        discord_data_dir=discord_data_dir,
        output_dir=output_dir,
    )
    realm["zerver_realmemoji"] = zerver_realmemoji

    subscriber_map = make_subscriber_map(zerver_subscription=zerver_subscription)

    long_term_idle = long_term_idle_helper(
        message_iterator=discord_message_iterator(json_files),
        user_from_message=lambda msg: msg["author"]["id"],
        timestamp_from_message=lambda msg: parse_discord_timestamp(msg["timestamp"]),
        zulip_user_id_from_user=user_id_mapper.get,
        all_user_ids_iterator=iter(metadata.discord_users.keys()),
        zerver_userprofile=user_handler.get_all_users(),
    )

    total_reactions: list[ZerverFieldsT] = []
    uploads_list: list[UploadRecordData] = []
    zerver_attachment: list[ZerverFieldsT] = []

    (
        stream_id_to_recipient_id,
        dm_group_id_to_recipient_id,
        user_id_to_recipient_id,
    ) = build_recipient_maps(zerver_recipient)

    write_message_data(
        realm_id=realm_id,
        json_files=json_files,
        reply_content_map=metadata.reply_content_map,
        stream_id_mapper=stream_id_mapper,
        user_id_mapper=user_id_mapper,
        direct_message_group_id_mapper=direct_message_group_id_mapper,
        dm_participants=metadata.dm_participants,
        thread_topic_map=metadata.thread_topic_map,
        stream_id_to_recipient_id=stream_id_to_recipient_id,
        dm_group_id_to_recipient_id=dm_group_id_to_recipient_id,
        user_id_to_recipient_id=user_id_to_recipient_id,
        subscriber_map=subscriber_map,
        output_dir=output_dir,
        total_reactions=total_reactions,
        zerver_realmemoji=zerver_realmemoji,
        uploads_list=uploads_list,
        zerver_attachment=zerver_attachment,
        discord_data_dir=discord_data_dir,
        discord_users=metadata.discord_users,
        channel_id_to_name=metadata.channel_id_to_name,
        long_term_idle=long_term_idle,
    )

    realm["zerver_reaction"] = total_reactions
    realm["zerver_userprofile"] = user_handler.get_all_users()
    realm["sort_by_date"] = True

    process_avatars(
        discord_users=metadata.discord_users,
        user_id_mapper=user_id_mapper,
        realm_id=realm_id,
        discord_data_dir=discord_data_dir,
        output_dir=output_dir,
    )

    process_realm_icon(metadata.guild_icon_url, realm_id, discord_data_dir, output_dir)

    create_converted_data_files(realm, output_dir, "/realm.json")

    attachment: dict[str, list[Any]] = {"zerver_attachment": zerver_attachment}
    create_converted_data_files(attachment, output_dir, "/attachment.json")
    create_converted_data_files(uploads_list, output_dir, "/uploads/records.json")

    do_common_export_processes(output_dir)
