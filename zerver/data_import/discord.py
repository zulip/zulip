import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias
from urllib.parse import urljoin

import requests
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    ImportedBotEmail,
    ZerverFieldsT,
    build_realm,
    build_user_profile,
    build_zerver_realm,
    create_converted_data_files,
    data_import_session,
    get_data_file,
    get_domain_name_for_import,
    validate_user_emails_for_import,
)
from zerver.data_import.sequencer import NEXT_ID
from zerver.lib.export import do_common_export_processes
from zerver.lib.string_validation import is_character_printable
from zerver.models.users import UserProfile
from zproject.backends import EMAIL_WITH_ENCODED_DISCORD_ID

DiscordFieldsT: TypeAlias = dict[str, Any]

# Channel types are Discord Chat Exporter's names, not Discord's:
# https://github.com/Tyrrrz/DiscordChatExporter/blob/prime/DiscordChatExporter.Core/Discord/Data/ChannelKind.cs
DISCORD_DIRECT_MESSAGE_CHANNEL_TYPES = frozenset(["DirectTextChat", "DirectGroupTextChat"])

NON_TEXT_DISCORD_CHANNEL_TYPES = frozenset(
    [
        # https://support.discord.com/hc/en-us/articles/115001580171-Channel-Categories-101
        "GuildCategory",
        # https://support.discord.com/hc/en-us/articles/4406046651927-Discord-Student-Hubs-FAQ
        "GuildDirectory",
    ]
)

DISCORD_API_BASE_URL = "https://discord.com/api/v10/"


@dataclass
class DiscordPaginationConfig:
    """Paginated endpoints return at most `limit` items per page. Discord
    doesn't return a cursor for the next page, so we request the items
    after the highest object ID of the previous page. `id_getter` defines
    how to get the object ID from each item in the response.
    """

    limit: int
    id_getter: Callable[[DiscordFieldsT], str]


@dataclass
class DiscordChannel:
    channel: DiscordFieldsT
    messages: list[DiscordFieldsT]


# The response is a JSON object or array, depending on the endpoint.
def get_discord_api_data(
    api_path: str, token: str, pagination: DiscordPaginationConfig | None = None
) -> Any:
    url = urljoin(DISCORD_API_BASE_URL, api_path)
    accumulated_result = []
    params: dict[str, int | str] = {}
    while True:
        if pagination is not None:
            # The number of items in a page/response.
            params["limit"] = pagination.limit

        response = data_import_session.get(
            url, headers={"Authorization": f"Bot {token}"}, params=params
        )

        if response.status_code != requests.codes.ok:
            logging.info("HTTP error: %s, Response: %s", response.status_code, response.text)
            raise Exception("HTTP error accessing the Discord API.")

        result = response.json()
        if pagination is None:
            return result

        accumulated_result.extend(result)
        if len(result) < pagination.limit:
            return accumulated_result

        # Discord's paginated API doesn't use a mechanism like "next" links,
        # instead, the "after" parameter determines where the next page starts.
        # It should be the highest-numbered ID in the current page.
        params["after"] = max((pagination.id_getter(item) for item in result), key=int)


def get_guild_data(guild_id: str, token: str) -> DiscordFieldsT:
    """
    https://docs.discord.com/developers/resources/guild#get-guild
    """
    return get_discord_api_data(f"guilds/{guild_id}", token)


def get_guild_members(guild_id: str, token: str) -> list[DiscordFieldsT]:
    """This requires the bot's Server Members Intent to be enabled.

    https://docs.discord.com/developers/resources/guild#list-guild-members
    """
    pagination = DiscordPaginationConfig(limit=1000, id_getter=lambda member: member["user"]["id"])
    return get_discord_api_data(f"guilds/{guild_id}/members", token, pagination)


def get_zulip_compatible_full_name(discord_names: list[str | None], discord_user_id: str) -> str:
    """Returns the first of discord_names that isn't empty once made
    valid for Zulip. Discord names allow characters that
    check_full_name rejects, so those are replaced with "_" and
    non-printable ones are dropped.

    https://docs.discord.com/developers/resources/user#usernames-and-nicknames
    """
    for discord_name in discord_names:
        if discord_name is None:
            continue

        sanitized_characters = []
        for character in discord_name:
            if character in UserProfile.NAME_INVALID_CHARS:
                sanitized_characters.append("_")
            # Only some non-printable characters are limited by Discord.
            elif is_character_printable(character):
                sanitized_characters.append(character)

        # Same rule as check_full_name: names can't end with e.g. "|15",
        # which looks like the user ID in the syntax for mentioning users.
        sanitized_name = re.sub(r"(\|\d+\s*)+$", "", "".join(sanitized_characters)).strip()
        if sanitized_name:
            return sanitized_name

    return f"Discord user {discord_user_id}"


def is_public_thread_channel(channel: DiscordFieldsT) -> bool:
    return channel["type"] in ("GuildPublicThread", "GuildNewsThread")


def is_private_thread_channel(channel: DiscordFieldsT) -> bool:
    return channel["type"] == "GuildPrivateThread"


def becomes_zulip_channel(channel: DiscordFieldsT) -> bool:
    channel_type = channel["type"]
    return (
        not is_public_thread_channel(channel)
        and not is_private_thread_channel(channel)
        and channel_type not in DISCORD_DIRECT_MESSAGE_CHANNEL_TYPES
        and channel_type not in NON_TEXT_DISCORD_CHANNEL_TYPES
    )


def group_messages_into_channels(channel_exports: list[DiscordFieldsT]) -> list[DiscordChannel]:
    """Returns the Discord channels that become Zulip channels, each with
    all of its messages.

    Discord Chat Exporter can split a channel across several export
    files, so those are merged. A public thread's messages are merged
    into its parent channel.

    We don't convert private threads, direct messages, or non-text channels.
    """
    discord_channels: dict[str, DiscordChannel] = {}
    thread_exports: list[DiscordFieldsT] = []
    for channel_export in channel_exports:
        channel = channel_export["channel"]
        if is_private_thread_channel(channel):
            logging.warning("Skipping private Discord thread %s.", channel["id"])
        elif is_public_thread_channel(channel):
            thread_exports.append(channel_export)
        elif becomes_zulip_channel(channel):
            discord_channels.setdefault(
                channel["id"], DiscordChannel(channel=channel, messages=[])
            ).messages.extend(channel_export["messages"])

    # The export files are sorted by name, so a thread may come before
    # its parent channel. This is why we record the thread in a separate
    # for loop.
    for thread_export in thread_exports:
        thread = thread_export["channel"]
        parent_channel_id = thread["categoryId"]
        parent = discord_channels.get(parent_channel_id)
        if parent is None:
            logging.warning(
                "Skipping Discord thread %s; its parent channel %s is missing.",
                thread["id"],
                parent_channel_id,
            )
        else:
            parent.messages.extend(thread_export["messages"])

    # Discord message IDs are snowflakes, which sort chronologically.
    for discord_channel in discord_channels.values():
        discord_channel.messages.sort(key=lambda message: int(message["id"]))

    return [discord_channels[channel_id] for channel_id in sorted(discord_channels, key=int)]


def fetch_discord_users(
    guild_id: str, discord_channels: list[DiscordChannel], token: str
) -> dict[str, ZerverFieldsT]:
    """Returns the processed data of the server's current members, plus
    message authors who are no longer members, including deleted accounts,
    as mirror dummies. They're keyed by Discord user ID.

    Names prefer the server-specific nickname, then the display name,
    then the username.
    """
    user_map: dict[str, ZerverFieldsT] = {}

    # https://docs.discord.com/developers/resources/guild#guild-member-object
    for member in get_guild_members(guild_id, token):
        user = member["user"]
        discord_names = [member.get("nick"), user["global_name"], user["username"]]
        user_map[user["id"]] = {
            "full_name": get_zulip_compatible_full_name(discord_names, user["id"]),
            "is_bot": user.get("bot", False),
            "is_mirror_dummy": False,
        }

    for discord_channel in discord_channels:
        for message in discord_channel.messages:
            # Message authors are DiscordChatExporter user objects:
            # https://github.com/Tyrrrz/DiscordChatExporter/blob/prime/DiscordChatExporter.Core/Exporting/JsonMessageWriter.cs
            author = message["author"]
            if author["id"] in user_map:
                continue
            discord_names = [author["nickname"], author["name"]]
            user_map[author["id"]] = {
                "full_name": get_zulip_compatible_full_name(discord_names, author["id"]),
                "is_bot": author["isBot"],
                "is_mirror_dummy": True,
            }

    return user_map


def convert_users(
    guild: DiscordFieldsT,
    user_map: dict[str, ZerverFieldsT],
    realm: ZerverFieldsT,
    realm_id: int,
    timestamp: float,
    domain_name: str,
) -> dict[str, int]:
    zerver_userprofile: list[ZerverFieldsT] = []
    discord_user_id_to_zulip_user_id: dict[str, int] = {}
    logging.info("######### IMPORTING USERS STARTED #########\n")
    for discord_user_id, user in user_map.items():
        full_name = user["full_name"]
        is_bot = user["is_bot"]
        if is_bot:
            email = ImportedBotEmail.get_email(
                user,
                domain_name,
                bot_id=discord_user_id,
                bot_name_getter=lambda bot: bot["full_name"],
            )
            bot_type = UserProfile.DEFAULT_BOT
        else:
            # Discord exports don't include email addresses. The
            # Discord authentication backend recognizes this encoding,
            # which lets imported users log in with Discord.
            email = EMAIL_WITH_ENCODED_DISCORD_ID.format(discord_user_id=discord_user_id)
            bot_type = None

        # Discord exports don't include roles, so the server owner becomes
        # the realm owner, and everyone else is imported as a member.
        if discord_user_id == guild["owner_id"]:
            role = UserProfile.ROLE_REALM_OWNER
        else:
            role = UserProfile.ROLE_MEMBER

        is_mirror_dummy = user["is_mirror_dummy"]

        zulip_user_id = NEXT_ID("user")
        zerver_userprofile.append(
            build_user_profile(
                avatar_source=UserProfile.DEFAULT_AVATAR_SOURCE,
                date_joined=timestamp,
                delivery_email=email,
                email=email,
                full_name=full_name,
                id=zulip_user_id,
                is_active=not is_mirror_dummy,
                role=role,
                is_mirror_dummy=is_mirror_dummy,
                realm_id=realm_id,
                short_name=full_name,
                timezone="UTC",
                is_bot=is_bot,
                bot_type=bot_type,
            )
        )
        discord_user_id_to_zulip_user_id[discord_user_id] = zulip_user_id
        logging.info("%s: %s -> %s", discord_user_id, full_name, email)

    validate_user_emails_for_import([user["delivery_email"] for user in zerver_userprofile])
    realm["zerver_userprofile"] = zerver_userprofile
    logging.info("######### IMPORTING USERS FINISHED #########\n")
    return discord_user_id_to_zulip_user_id


def do_convert_directory(discord_data_dir: str, output_dir: str, token: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    if os.listdir(output_dir):  # nocoverage
        raise Exception("Output directory should be empty!")

    channels_dir = os.path.join(discord_data_dir, "channels")
    if not os.path.isdir(channels_dir):
        raise ValueError(
            "Import does not have the layout we expect! Export every channel data "
            "in a 'channels' directory."
        )
    channel_exports = [
        get_data_file(os.path.join(channels_dir, file_name))
        for file_name in sorted(os.listdir(channels_dir))
        if file_name.endswith(".json")
    ]

    guild_ids = {
        channel_export["guild"]["id"]
        for channel_export in channel_exports
        if becomes_zulip_channel(channel_export["channel"])
    }
    if len(guild_ids) != 1:
        raise ValueError("The export must contain the channels of exactly one Discord server.")
    [guild_id] = guild_ids
    guild = get_guild_data(guild_id, token)

    realm_id = 0
    domain_name = get_domain_name_for_import()
    timestamp = timezone_now().timestamp()
    zerver_realm = build_zerver_realm(realm_id, "", timestamp, "Discord")
    realm = build_realm(zerver_realm, realm_id, domain_name, import_source="discord")
    realm["zerver_stream"] = []
    realm["zerver_defaultstream"] = []
    realm["zerver_recipient"] = []
    realm["zerver_subscription"] = []

    discord_channels = group_messages_into_channels(channel_exports)
    user_map = fetch_discord_users(guild["id"], discord_channels, token)
    convert_users(
        guild=guild,
        user_map=user_map,
        realm=realm,
        realm_id=realm_id,
        timestamp=timestamp,
        domain_name=domain_name,
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
