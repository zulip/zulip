import logging
import os
import re
from dataclasses import dataclass
from typing import Any, TypeAlias
from urllib.parse import SplitResult, urljoin

import requests
from django.conf import settings
from django.utils.timezone import now as timezone_now
from urllib3.util import Retry

from zerver.data_import.import_util import (
    ImportedBotEmail,
    ZerverFieldsT,
    build_realm,
    build_recipient,
    build_stream,
    build_subscription,
    build_user_profile,
    build_zerver_realm,
    create_converted_data_files,
    get_data_file,
    get_unique_truncated_name,
    validate_user_emails_for_import,
)
from zerver.data_import.sequencer import NEXT_ID
from zerver.lib.export import do_common_export_processes
from zerver.lib.message import truncate_content
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.string_validation import is_character_printable
from zerver.models.recipients import Recipient
from zerver.models.streams import Stream
from zerver.models.users import UserProfile
from zproject.backends import EMAIL_WITH_ENCODED_DISCORD_ID

DiscordFieldsT: TypeAlias = dict[str, Any]
DiscordUserIdToZulipUserIdT: TypeAlias = dict[str, int]

# The types listed in *_CHANNEL_TYPES variables are not native from Discord,
# they're from Discord Chat Exporter:
# https://raw.githubusercontent.com/Tyrrrz/DiscordChatExporter/master/DiscordChatExporter.Core/Discord/Data/ChannelKind.cs
DISCORD_PRIVATE_THREAD_CHANNEL_TYPE = "GuildPrivateThread"

DISCORD_PUBLIC_THREAD_CHANNEL_TYPES = frozenset(["GuildPublicThread", "GuildNewsThread"])

DISCORD_DIRECT_MESSAGE_CHANNEL_TYPES = frozenset(["DirectTextChat", "DirectGroupTextChat"])

NON_TEXT_DISCORD_CHANNEL_TYPES = frozenset(
    [
        # An organizational category that contains up to 50 channels
        # https://support.discord.com/hc/en-us/articles/115001580171-Channel-Categories-101
        "GuildCategory",
        # The channel in a hub containing the listed servers.
        # https://support.discord.com/hc/en-us/articles/4406046651927-Discord-Student-Hubs-FAQ
        "GuildDirectory",
    ]
)

DISCORD_ANNOUNCEMENT_CHANNEL_TYPE = "GuildNews"

DISCORD_VOICE_CHANNEL_TYPES = frozenset(["GuildVoiceChat", "GuildStageVoice"])
VOICE_CHANNEL_NAME_PREFIX = "[voice] "

DISCORD_API_BASE_URL = "https://discord.com/api/v10/"

# Retry on 429 (Discord aggressively rate-limits its API) and the common
# transient server errors, like the file-download session in import_util.
_discord_api_session = OutgoingSession(
    role="data_import",
    timeout=60,
    max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]),
)


def get_discord_api_data(api_path: str, token: str) -> Any:
    """Make an authenticated request to the Discord API."""
    # api_path must be relative (no leading slash); see DISCORD_API_BASE_URL.
    url = urljoin(DISCORD_API_BASE_URL, api_path)
    response = _discord_api_session.get(url, headers={"Authorization": f"Bot {token}"})

    if response.status_code != requests.codes.ok:
        logging.info("HTTP error: %s, Response: %s", response.status_code, response.text)
        raise Exception("HTTP error accessing the Discord API.")

    return response.json()


def get_guild_data(guild_id: str, token: str) -> DiscordFieldsT:
    """
    https://docs.discord.com/developers/resources/guild#get-guild
    """
    return get_discord_api_data(f"guilds/{guild_id}", token)


# The "View Channel" permission bit.
# https://docs.discord.com/developers/topics/permissions#permissions-bitwise-permission-flags
DISCORD_VIEW_CHANNEL_PERMISSION = 1 << 10


def is_private_channel(channel_id: str, guild_id: str, token: str) -> bool:
    """Whether a Discord channel is hidden from the server's @everyone role.

    Discord exports carry no permission data, so we fetch the channel's
    permission overwrites from the API. A channel is private when the
    @everyone role is denied the View Channel permission.
    https://docs.discord.com/developers/resources/channel#channel-object
    """
    channel = get_discord_api_data(f"channels/{channel_id}", token)
    for overwrite in channel["permission_overwrites"]:
        # The "@everyone" role's ID is the guild ID.
        # https://docs.discord.com/developers/topics/permissions#role-object
        if overwrite["type"] == 0 and overwrite["id"] == guild_id:
            return bool(int(overwrite["deny"]) & DISCORD_VIEW_CHANNEL_PERMISSION)
    return False


def discord_user_id_to_zulip_email(discord_user_id: str) -> str:
    """Discord exports don't include user email addresses, so we encode each
    user's Discord ID into a special email address. The Discord
    authentication backend recognizes this scheme and uses it to log the
    imported user in via Discord OAuth; see EMAIL_WITH_ENCODED_DISCORD_ID
    in zproject/backends.py.
    """
    return EMAIL_WITH_ENCODED_DISCORD_ID.format(discord_user_id=discord_user_id)


class DiscordBotEmail:
    @classmethod
    def get_email(cls, author: DiscordFieldsT, domain_name: str) -> str:
        discord_bot_id = author["id"]

        def bot_name_getter(_author: DiscordFieldsT) -> str:
            return get_zulip_compatible_full_name(
                _author["nickname"] or _author["name"], fallback=discord_bot_id
            )

        return ImportedBotEmail.get_email(author, domain_name, discord_bot_id, bot_name_getter)


def get_zulip_compatible_full_name(name: str, fallback: str) -> str:
    """Turn a Discord username or display name into a valid Zulip full name.

    Discord display names allow characters Zulip rejects in names (see
    check_full_name). Each character Zulip disallows
    (UserProfile.NAME_INVALID_CHARS) is replaced with "_", non-printable
    characters are dropped, a trailing "|<number>" (ambiguous with mention
    markup) is removed, and the result is stripped and length-limited. If
    nothing usable remains, fallback is returned.

    https://support.discord.com/hc/en-us/articles/12620128861463-New-Usernames-Display-Names
    """
    sanitized_characters = []
    for character in name:
        # Discord display names allow a much wider range of characters than
        # usernames, so names containing characters that are invalid here may
        # be fairly common.
        if character in UserProfile.NAME_INVALID_CHARS:
            sanitized_characters.append("_")
        elif is_character_printable(character):
            sanitized_characters.append(character)

    sanitized_name = re.sub(r"\|\d+$", "", "".join(sanitized_characters)).strip()
    return sanitized_name or fallback


def is_public_thread_channel(channel: DiscordFieldsT) -> bool:
    return channel["type"] in DISCORD_PUBLIC_THREAD_CHANNEL_TYPES


def is_private_thread_channel(channel: DiscordFieldsT) -> bool:
    return channel["type"] == DISCORD_PRIVATE_THREAD_CHANNEL_TYPE


def is_announcement_channel(channel: DiscordFieldsT) -> bool:
    """
    Discord's "Announcement Channel"; we designate it as the realm's update
    announcements channel.
    https://support.discord.com/hc/en-us/articles/360032008192-Announcement-Channels
    """
    return channel["type"] == DISCORD_ANNOUNCEMENT_CHANNEL_TYPE


def is_voice_channel(channel: DiscordFieldsT) -> bool:
    return channel["type"] in DISCORD_VOICE_CHANNEL_TYPES


def becomes_zulip_channel(channel: DiscordFieldsT) -> bool:
    """Whether a Discord channel export should be converted to a Zulip channel."""
    channel_type = channel["type"]
    return (
        not is_public_thread_channel(channel)
        and not is_private_thread_channel(channel)
        # There are no direct messages in a Discord guild (server). We currently don't
        # support converting direct message exports.
        and channel_type not in DISCORD_DIRECT_MESSAGE_CHANNEL_TYPES
        and channel_type not in NON_TEXT_DISCORD_CHANNEL_TYPES
    )


@dataclass
class DiscordChannel:
    """A Discord channel can be an actual channel, thread, or direct message group.
    https://docs.discord.com/developers/resources/channel
    """

    channel: DiscordFieldsT
    messages: list[DiscordFieldsT]
    invite_only: bool


def group_messages_into_channels(
    channel_exports: list[DiscordFieldsT],
    guild_id: str,
    token: str,
) -> list[DiscordChannel]:
    """Determine which Discord channels become Zulip channels and which
    messages belong to each.

    A channel's messages can be split across several export files (Discord Chat
    Exporter partitions large channels), so exports that share a channel ID are
    merged into one Zulip channel.

    A thread's messages are merged into its parent channel (identified by the
    thread's categoryId); a thread whose parent isn't a converted channel is
    dropped. Direct messages and non-text channels are skipped.

    All private threads are dropped, since we don't have a clean way of
    converting them.
    """
    # Collect channels in a first pass and merge threads in a second, because
    # the export's channel files are sorted by name with no guarantee that a
    # thread's parent channel is seen before the thread.
    discord_channels: dict[str, DiscordChannel] = {}
    thread_exports: list[DiscordFieldsT] = []
    for channel_export in channel_exports:
        channel = channel_export["channel"]
        if is_private_thread_channel(channel):
            # We currently don't convert private threads.
            logging.warning(
                "Skipping private Discord thread %s.",
                channel["id"],
            )
            continue
        elif is_public_thread_channel(channel):
            thread_exports.append(channel_export)
        elif becomes_zulip_channel(channel):
            existing_channel = discord_channels.get(channel["id"])
            if existing_channel is None:
                discord_channels[channel["id"]] = DiscordChannel(
                    channel=channel,
                    messages=list(channel_export["messages"]),
                    invite_only=is_private_channel(channel["id"], guild_id, token),
                )
            else:
                # Another partition of a channel we've already seen; merge in
                # its messages without re-checking privacy.
                existing_channel.messages.extend(channel_export["messages"])

    for thread_export in thread_exports:
        thread = thread_export["channel"]
        parent_channel_id = thread["categoryId"]
        parent = discord_channels.get(parent_channel_id)
        if parent is None:
            # The thread's parent isn't a converted channel, so there's nowhere
            # to merge it. This doesn't normally happen if at all.
            logging.warning(
                "Skipping Discord thread %s; its parent channel %s is missing.",
                thread["id"],
                parent_channel_id,
            )
        else:
            parent.messages.extend(thread_export["messages"])

    # Discord message IDs are snowflakes that encode their creation time, so
    # sorting by ID orders a channel's merged messages chronologically.
    for discord_channel in discord_channels.values():
        discord_channel.messages.sort(key=lambda message: int(message["id"]))

    # Return in a deterministic order for stable object IDs across conversions.
    return [discord_channels[channel_id] for channel_id in sorted(discord_channels)]


DISCORD_CHANNELS_DIR_NAME = "channels"


def get_discord_channel_export_file_paths(discord_data_dir: str) -> list[str]:
    channels_dir = os.path.join(discord_data_dir, DISCORD_CHANNELS_DIR_NAME)
    if not os.path.isdir(channels_dir):
        return []
    return sorted(
        os.path.join(channels_dir, file_name)
        for file_name in os.listdir(channels_dir)
        if file_name.endswith(".json")
    )


def convert_users(
    discord_channels: list[DiscordChannel],
    realm: dict[str, Any],
    realm_id: int,
    timestamp: int,
    guild: DiscordFieldsT,
    domain_name: str,
) -> DiscordUserIdToZulipUserIdT:
    """Discord exports have no standalone member list, so users are
    discovered from the authors of the messages in each channel.

    Discord exports also don't include role or ownership data. Zulip
    requires a realm owner, so the caller fetches the guild via the Discord
    API and passes it as guild; its owner_id becomes the realm owner and
    everyone else is imported as a member. The guild's roles also identify
    which authors are bots, via each role's tags.bot_id.
    """
    zerver_userprofile: list[ZerverFieldsT] = []
    discord_user_id_to_zulip_user_id: DiscordUserIdToZulipUserIdT = {}
    found_emails: dict[str, int] = {}
    has_owner = False

    owner_discord_user_id = guild["owner_id"]
    guild_roles = guild["roles"]
    bot_discord_user_ids: set[str] = {
        bot_id for role in guild_roles if (bot_id := role.get("tags", {}).get("bot_id"))
    }

    logging.info("######### IMPORTING USERS STARTED #########\n")
    for discord_channel in discord_channels:
        for message in discord_channel.messages:
            author = message["author"]
            discord_user_id: str = author["id"]
            if discord_user_id in discord_user_id_to_zulip_user_id:
                continue

            # Prefer the server-specific nickname over the global username
            # as the Zulip full name when one is set.
            # TODO: Convert avatars, and users who only appear in mentions
            # or reactions.
            full_name = get_zulip_compatible_full_name(
                author["nickname"] or author["name"], fallback=discord_user_id
            )

            is_bot = discord_user_id in bot_discord_user_ids
            if is_bot:
                email = DiscordBotEmail.get_email(author, domain_name)
            else:
                email = discord_user_id_to_zulip_email(discord_user_id)

            # We assume the owner has at least sent one message to avoid
            # doing another API call to get their data.
            if discord_user_id == owner_discord_user_id:
                user_role = UserProfile.ROLE_REALM_OWNER
                has_owner = True
            else:
                user_role = UserProfile.ROLE_MEMBER

            zulip_user_id = NEXT_ID("user")
            found_emails[email] = zulip_user_id
            user_profile_dict = build_user_profile(
                avatar_source=UserProfile.DEFAULT_AVATAR_SOURCE,
                date_joined=timestamp,
                delivery_email=email,
                email=email,
                full_name=full_name,
                id=zulip_user_id,
                is_active=True,
                role=user_role,
                is_mirror_dummy=False,
                realm_id=realm_id,
                short_name=full_name,
                timezone="UTC",
                is_bot=is_bot,
                bot_type=UserProfile.DEFAULT_BOT if is_bot else None,
            )
            user_profile_dict["realm"] = realm_id
            zerver_userprofile.append(user_profile_dict)
            discord_user_id_to_zulip_user_id[discord_user_id] = zulip_user_id

            logging.info("%s: %s -> %s", discord_user_id, full_name, email)

    assert has_owner, (
        f"The Discord server owner (user ID {owner_discord_user_id}) did not send "
        "any messages in the export, so no realm owner could be assigned."
    )

    validate_user_emails_for_import(list(found_emails))
    realm["zerver_userprofile"] = zerver_userprofile
    logging.info("######### IMPORTING USERS FINISHED #########\n")
    return discord_user_id_to_zulip_user_id


def convert_channels(
    discord_channels: list[DiscordChannel],
    discord_user_id_to_zulip_user_id: DiscordUserIdToZulipUserIdT,
    realm: dict[str, Any],
    realm_id: int,
    timestamp: float,
) -> None:
    channel_name_counts: dict[str, int] = {}
    logging.info("######### IMPORTING CHANNELS STARTED #########\n")
    for discord_channel in discord_channels:
        channel = discord_channel.channel
        zulip_channel_id = NEXT_ID("channel")
        recipient_id = NEXT_ID("recipient")

        channel_name = channel["name"]
        if is_voice_channel(channel):
            # Discord voice channels can also carry text chat, which we import.
            # Their Zulip channel names get this prefix so they don't collide
            # with a same-named text channel, since Zulip channel names must
            # be unique case-insensitively.
            channel_name = VOICE_CHANNEL_NAME_PREFIX + channel_name

        description = (
            truncate_content(channel["topic"], Stream.MAX_DESCRIPTION_LENGTH, "…")
            if channel["topic"]
            else ""
        )

        zulip_channel = build_stream(
            # Discord's export doesn't include the channel's creation date.
            date_created=timestamp,
            realm_id=realm_id,
            name=get_unique_truncated_name(
                channel_name, Stream.MAX_NAME_LENGTH, channel_name_counts
            ),
            description=description,
            stream_id=zulip_channel_id,
            invite_only=discord_channel.invite_only,
        )
        realm["zerver_stream"].append(zulip_channel)

        if (
            is_announcement_channel(channel)
            and realm["zerver_realm"][0]["zulip_update_announcements_stream"] is None
        ):
            # Map a Discord announcement channel to Zulip's update announcements
            # channel. There can be several Discord announcement channels, so
            # we only convert the first one we encounter.
            realm["zerver_realm"][0]["zulip_update_announcements_stream"] = zulip_channel_id
            logging.info(
                "Using the channel '%s' as the update announcements channel.", channel["name"]
            )

        recipient = build_recipient(zulip_channel_id, recipient_id, Recipient.STREAM)
        realm["zerver_recipient"].append(recipient)

        # Discord exports don't list channel members, so we subscribe the
        # users who sent messages in the channel.
        subscriber_zulip_user_ids = {
            discord_user_id_to_zulip_user_id[message["author"]["id"]]
            for message in discord_channel.messages
        }
        for zulip_user_id in sorted(subscriber_zulip_user_ids):
            subscription = build_subscription(
                recipient_id=recipient_id,
                user_id=zulip_user_id,
                subscription_id=NEXT_ID("subscription"),
            )
            realm["zerver_subscription"].append(subscription)

    logging.info("######### IMPORTING CHANNELS FINISHED #########\n")


def do_convert_directory(discord_data_dir: str, output_dir: str, token: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    if os.listdir(output_dir):  # nocoverage
        raise Exception("Output directory should be empty!")

    channel_export_file_paths = get_discord_channel_export_file_paths(discord_data_dir)
    if not channel_export_file_paths:
        raise ValueError(
            "Import does not have the layout we expect! Export every channel data "
            "in a 'channels' directory."
        )
    channel_exports = [get_data_file(path) for path in channel_export_file_paths]

    # Every channel export records the same server, so any of them tells us
    # which guild to look up the owner for.
    guild_id = channel_exports[0]["guild"]["id"]
    guild = get_guild_data(guild_id, token)

    realm_id = 0
    domain_name = SplitResult("", settings.EXTERNAL_HOST, "", "", "").hostname
    assert isinstance(domain_name, str)

    NOW = float(timezone_now().timestamp())
    zerver_realm: list[ZerverFieldsT] = build_zerver_realm(realm_id, "", NOW, "Discord")
    realm = build_realm(zerver_realm, realm_id, domain_name, import_source="discord")
    realm["zerver_stream"] = []
    realm["zerver_defaultstream"] = []
    realm["zerver_recipient"] = []
    realm["zerver_subscription"] = []

    discord_channels = group_messages_into_channels(channel_exports, guild_id, token)

    discord_user_id_to_zulip_user_id = convert_users(
        discord_channels=discord_channels,
        realm=realm,
        realm_id=realm_id,
        timestamp=int(NOW),
        guild=guild,
        domain_name=domain_name,
    )

    convert_channels(
        discord_channels=discord_channels,
        discord_user_id_to_zulip_user_id=discord_user_id_to_zulip_user_id,
        realm=realm,
        realm_id=realm_id,
        timestamp=NOW,
    )

    create_converted_data_files(realm, output_dir, "/realm.json")
    create_converted_data_files([], output_dir, "/uploads/records.json")
    create_converted_data_files({"zerver_attachment": []}, output_dir, "/attachment.json")
    create_converted_data_files([], output_dir, "/emoji/records.json")
    create_converted_data_files([], output_dir, "/avatars/records.json")
    create_converted_data_files([], output_dir, "/realm_icons/records.json")
    do_common_export_processes(output_dir)

    logging.info("######### DATA CONVERSION FINISHED #########\n")
    logging.info("Zulip data dump created at %s", output_dir)
