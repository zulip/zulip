import itertools
import logging
import os
import posixpath
import random
import re
import secrets
import shutil
import time
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timezone
from email.headerregistry import Address
from typing import Any, TypeAlias
from urllib.parse import SplitResult, urlsplit

import orjson
import requests
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    ZerverFieldsT,
    build_attachment,
    build_avatar,
    build_defaultstream,
    build_direct_message_group,
    build_message,
    build_realm,
    build_recipient,
    build_stream,
    build_subscription,
    build_usermessages,
    build_zerver_realm,
    create_converted_data_files,
    long_term_idle_helper,
    make_subscriber_map,
    process_avatars,
    process_emojis,
    process_uploads,
    validate_user_emails_for_import,
)
from zerver.data_import.sequencer import NEXT_ID
from zerver.data_import.slack_message_conversion import (
    convert_to_zulip_markdown,
    get_user_full_name,
    process_slack_block_and_attachment,
)
from zerver.lib.emoji import codepoint_to_name, get_emoji_file_name
from zerver.lib.exceptions import SlackImportInvalidFileError
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE, do_common_export_processes
from zerver.lib.message import truncate_content
from zerver.lib.mime_types import guess_type
from zerver.lib.storage import static_path
from zerver.lib.thumbnail import THUMBNAIL_ACCEPT_IMAGE_TYPES, resize_realm_icon
from zerver.lib.upload import sanitize_name
from zerver.models import (
    CustomProfileField,
    CustomProfileFieldValue,
    Reaction,
    Realm,
    RealmEmoji,
    Recipient,
    UserProfile,
)
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH

SlackToZulipUserIDT: TypeAlias = dict[str, int]
AddedChannelsT: TypeAlias = dict[str, tuple[str, int]]
AddedMPIMsT: TypeAlias = dict[str, tuple[str, int]]
DMMembersT: TypeAlias = dict[str, tuple[str, str]]
SlackToZulipRecipientT: TypeAlias = dict[str, int]

# We can look up unicode codepoints for Slack emoji using iamcal emoji
# data. https://emojipedia.org/slack/, documents Slack's emoji names
# are derived from https://github.com/iamcal/emoji-data; this seems
# likely to remain true since Cal is a Slack's cofounder.
emoji_data_file_path = static_path("generated/emoji/emoji-datasource-google-emoji.json")
with open(emoji_data_file_path, "rb") as emoji_data_file:
    emoji_data = orjson.loads(emoji_data_file.read())


def get_emoji_code(emoji_dict: dict[str, Any]) -> str:
    # This function is identical with the function with the same name at
    # tools/setup/emoji/emoji_setup_utils.py.
    # This function is unlikely to be changed, unless iamcal changes their data
    # structure.
    emoji_code = emoji_dict.get("non_qualified") or emoji_dict["unified"]
    return emoji_code.lower()


# Build the translation dict from Slack emoji name to codepoint.
slack_emoji_name_to_codepoint: dict[str, str] = {}
for emoji_dict in emoji_data:
    short_name = emoji_dict["short_name"]
    emoji_code = get_emoji_code(emoji_dict)
    slack_emoji_name_to_codepoint[short_name] = emoji_code
    for sn in emoji_dict["short_names"]:
        if sn != short_name:
            slack_emoji_name_to_codepoint[sn] = emoji_code


class SlackBotEmail:
    duplicate_email_count: dict[str, int] = {}
    # Mapping of `bot_id` to final email assigned to the bot.
    assigned_email: dict[str, str] = {}

    @classmethod
    def get_email(cls, user_profile: ZerverFieldsT, domain_name: str) -> str:
        slack_bot_id = user_profile["bot_id"]
        if slack_bot_id in cls.assigned_email:
            return cls.assigned_email[slack_bot_id]

        if "real_name_normalized" in user_profile:
            slack_bot_name = user_profile["real_name_normalized"]
        elif "first_name" in user_profile:
            slack_bot_name = user_profile["first_name"]
        else:
            raise AssertionError("Could not identify bot type")

        email = Address(
            username=slack_bot_name.replace("Bot", "").replace(" ", "").lower() + "-bot",
            domain=domain_name,
        ).addr_spec

        if email in cls.duplicate_email_count:
            cls.duplicate_email_count[email] += 1
            address = Address(addr_spec=email)
            email_username = address.username + "-" + str(cls.duplicate_email_count[email])
            email = Address(username=email_username, domain=address.domain).addr_spec
        else:
            cls.duplicate_email_count[email] = 1

        cls.assigned_email[slack_bot_id] = email
        return email


def rm_tree(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)


def slack_workspace_to_realm(
    domain_name: str,
    realm_id: int,
    user_list: list[ZerverFieldsT],
    realm_subdomain: str,
    slack_data_dir: str,
    custom_emoji_list: ZerverFieldsT,
) -> tuple[
    ZerverFieldsT,
    SlackToZulipUserIDT,
    SlackToZulipRecipientT,
    AddedChannelsT,
    AddedMPIMsT,
    DMMembersT,
    list[ZerverFieldsT],
    ZerverFieldsT,
]:
    """
    Returns:
    1. realm, converted realm data
    2. slack_user_id_to_zulip_user_id, which is a dictionary to map from Slack user id to Zulip user id
    3. slack_recipient_name_to_zulip_recipient_id, which is a dictionary to map from Slack recipient
       name(channel names, mpim names, usernames, etc) to Zulip recipient id
    4. added_channels, which is a dictionary to map from channel name to channel id, Zulip stream_id
    5. added_mpims, which is a dictionary to map from MPIM name to MPIM id, Zulip direct_message_group_id
    6. dm_members, which is a dictionary to map from DM id to tuple of DM participants.
    7. avatars, which is list to map avatars to Zulip avatar records.json
    8. emoji_url_map, which is maps emoji name to its Slack URL
    """
    NOW = float(timezone_now().timestamp())

    zerver_realm: list[ZerverFieldsT] = build_zerver_realm(realm_id, realm_subdomain, NOW, "Slack")
    realm = build_realm(zerver_realm, realm_id, domain_name, import_source="slack")

    (
        zerver_userprofile,
        avatars,
        slack_user_id_to_zulip_user_id,
        zerver_customprofilefield,
        zerver_customprofilefield_value,
    ) = users_to_zerver_userprofile(slack_data_dir, user_list, realm_id, int(NOW), domain_name)
    (
        realm,
        added_channels,
        added_mpims,
        dm_members,
        slack_recipient_name_to_zulip_recipient_id,
    ) = channels_to_zerver_stream(
        slack_data_dir, realm_id, realm, slack_user_id_to_zulip_user_id, zerver_userprofile
    )

    zerver_realmemoji, emoji_url_map = build_realmemoji(custom_emoji_list, realm_id)
    realm["zerver_realmemoji"] = zerver_realmemoji

    # See https://zulip.com/help/set-default-channels-for-new-users
    # for documentation on zerver_defaultstream
    realm["zerver_userprofile"] = zerver_userprofile

    realm["zerver_customprofilefield"] = zerver_customprofilefield
    realm["zerver_customprofilefieldvalue"] = zerver_customprofilefield_value

    return (
        realm,
        slack_user_id_to_zulip_user_id,
        slack_recipient_name_to_zulip_recipient_id,
        added_channels,
        added_mpims,
        dm_members,
        avatars,
        emoji_url_map,
    )


def build_realmemoji(
    custom_emoji_list: ZerverFieldsT, realm_id: int
) -> tuple[list[ZerverFieldsT], ZerverFieldsT]:
    zerver_realmemoji = []
    emoji_url_map = {}
    emoji_id = 0
    for emoji_name, url in custom_emoji_list.items():
        split_url = urlsplit(url)
        if split_url.hostname == "emoji.slack-edge.com":
            # Some of the emojis we get from the API have invalid links
            # this is to prevent errors related to them
            content_type = guess_type(posixpath.basename(split_url.path))[0]
            assert content_type is not None
            realmemoji = RealmEmoji(
                name=emoji_name,
                id=emoji_id,
                file_name=get_emoji_file_name(content_type, emoji_id),
                deactivated=False,
            )

            realmemoji_dict = model_to_dict(realmemoji, exclude=["realm", "author"])
            realmemoji_dict["author"] = None
            realmemoji_dict["realm"] = realm_id

            emoji_url_map[emoji_name] = url
            zerver_realmemoji.append(realmemoji_dict)
            emoji_id += 1
    return zerver_realmemoji, emoji_url_map


def users_to_zerver_userprofile(
    slack_data_dir: str, users: list[ZerverFieldsT], realm_id: int, timestamp: Any, domain_name: str
) -> tuple[
    list[ZerverFieldsT],
    list[ZerverFieldsT],
    SlackToZulipUserIDT,
    list[ZerverFieldsT],
    list[ZerverFieldsT],
]:
    """
    Returns:
    1. zerver_userprofile, which is a list of user profile
    2. avatar_list, which is list to map avatars to Zulip avatar records.json
    3. slack_user_id_to_zulip_user_id, which is a dictionary to map from Slack user ID to Zulip
       user id
    4. zerver_customprofilefield, which is a list of all custom profile fields
    5. zerver_customprofilefield_values, which is a list of user profile fields
    """
    logging.info("######### IMPORTING USERS STARTED #########\n")
    zerver_userprofile = []
    zerver_customprofilefield: list[ZerverFieldsT] = []
    zerver_customprofilefield_values: list[ZerverFieldsT] = []
    avatar_list: list[ZerverFieldsT] = []
    slack_user_id_to_zulip_user_id = {}

    # The user data we get from the Slack API does not contain custom profile data
    # Hence we get it from the Slack zip file
    slack_data_file_user_list = get_data_file(slack_data_dir + "/users.json")

    slack_user_id_to_custom_profile_fields: ZerverFieldsT = {}
    slack_custom_field_name_to_zulip_custom_field_id: ZerverFieldsT = {}

    for user in slack_data_file_user_list:
        process_slack_custom_fields(user, slack_user_id_to_custom_profile_fields)

    # We have only one primary owner in Slack, see link
    # https://get.slack.help/hc/en-us/articles/201912948-Owners-and-Administrators
    # This is to import the primary owner first from all the users
    user_id_count = custom_profile_field_value_id_count = custom_profile_field_id_count = 0
    primary_owner_id = user_id_count
    user_id_count += 1

    found_emails: dict[str, int] = {}
    for user in users:
        slack_user_id = user["id"]

        if user.get("is_primary_owner", False):
            user_id = primary_owner_id
        else:
            user_id = user_id_count

        email = get_user_email(user, domain_name)
        if email.lower() in found_emails:
            slack_user_id_to_zulip_user_id[slack_user_id] = found_emails[email.lower()]
            logging.info("%s: %s MERGED", slack_user_id, email)
            continue
        found_emails[email.lower()] = user_id

        # ref: https://zulip.com/help/change-your-profile-picture
        avatar_source, avatar_url = build_avatar_url(slack_user_id, user)
        if avatar_source == UserProfile.AVATAR_FROM_USER:
            build_avatar(user_id, realm_id, email, avatar_url, timestamp, avatar_list)
        role = UserProfile.ROLE_MEMBER
        if get_owner(user):
            role = UserProfile.ROLE_REALM_OWNER
        elif get_admin(user):
            role = UserProfile.ROLE_REALM_ADMINISTRATOR
        if get_guest(user):
            role = UserProfile.ROLE_GUEST
        timezone = get_user_timezone(user)

        if slack_user_id in slack_user_id_to_custom_profile_fields:
            (
                slack_custom_field_name_to_zulip_custom_field_id,
                custom_profile_field_id_count,
            ) = build_customprofile_field(
                zerver_customprofilefield,
                slack_user_id_to_custom_profile_fields[slack_user_id],
                custom_profile_field_id_count,
                realm_id,
                slack_custom_field_name_to_zulip_custom_field_id,
            )
            custom_profile_field_value_id_count = build_customprofilefields_values(
                slack_custom_field_name_to_zulip_custom_field_id,
                slack_user_id_to_custom_profile_fields[slack_user_id],
                user_id,
                custom_profile_field_value_id_count,
                zerver_customprofilefield_values,
            )

        if is_slackbot(user):
            is_bot = True
        else:
            is_bot = user.get("is_bot", False)
        if is_bot:
            bot_type = 1
        else:
            bot_type = None

        userprofile = UserProfile(
            full_name=get_user_full_name(user),
            is_active=not user.get("deleted", False) and not user["is_mirror_dummy"],
            is_mirror_dummy=user["is_mirror_dummy"],
            id=user_id,
            email=email,
            delivery_email=email,
            avatar_source=avatar_source,
            is_bot=is_bot,
            role=role,
            bot_type=bot_type,
            date_joined=timestamp,
            timezone=timezone,
            last_login=timestamp,
        )
        userprofile_dict = model_to_dict(userprofile)
        # Set realm id separately as the corresponding realm is not yet a Realm model instance
        userprofile_dict["realm"] = realm_id

        zerver_userprofile.append(userprofile_dict)
        slack_user_id_to_zulip_user_id[slack_user_id] = user_id
        if not user.get("is_primary_owner", False):
            user_id_count += 1

        logging.info("%s: %s -> %s", slack_user_id, user["name"], userprofile_dict["email"])

    validate_user_emails_for_import(list(found_emails))
    process_customprofilefields(zerver_customprofilefield, zerver_customprofilefield_values)
    logging.info("######### IMPORTING USERS FINISHED #########\n")
    return (
        zerver_userprofile,
        avatar_list,
        slack_user_id_to_zulip_user_id,
        zerver_customprofilefield,
        zerver_customprofilefield_values,
    )


def build_customprofile_field(
    customprofile_field: list[ZerverFieldsT],
    fields: ZerverFieldsT,
    custom_profile_field_id: int,
    realm_id: int,
    slack_custom_field_name_to_zulip_custom_field_id: ZerverFieldsT,
) -> tuple[ZerverFieldsT, int]:
    # The name of the custom profile field is not provided in the Slack data
    # Hash keys of the fields are provided
    # Reference: https://api.slack.com/methods/users.profile.set
    for field in fields:
        if field not in slack_custom_field_name_to_zulip_custom_field_id:
            slack_custom_fields = ["phone", "skype"]
            if field in slack_custom_fields:
                field_name = field
            else:
                field_name = f"Slack custom field {custom_profile_field_id + 1}"
            customprofilefield = CustomProfileField(
                id=custom_profile_field_id,
                name=field_name,
                field_type=1,  # For now this is defaulted to 'SHORT_TEXT'
                # Processing is done in the function 'process_customprofilefields'
            )

            customprofilefield_dict = model_to_dict(customprofilefield, exclude=["realm"])
            customprofilefield_dict["realm"] = realm_id

            slack_custom_field_name_to_zulip_custom_field_id[field] = custom_profile_field_id
            custom_profile_field_id += 1
            customprofile_field.append(customprofilefield_dict)
    return slack_custom_field_name_to_zulip_custom_field_id, custom_profile_field_id


def process_slack_custom_fields(
    user: ZerverFieldsT, slack_user_id_to_custom_profile_fields: ZerverFieldsT
) -> None:
    slack_user_id_to_custom_profile_fields[user["id"]] = {}
    if user["profile"].get("fields"):
        slack_user_id_to_custom_profile_fields[user["id"]] = user["profile"]["fields"]

    slack_custom_fields = ["phone", "skype"]
    for field in slack_custom_fields:
        if field in user["profile"]:
            slack_user_id_to_custom_profile_fields[user["id"]][field] = {
                "value": user["profile"][field]
            }


def build_customprofilefields_values(
    slack_custom_field_name_to_zulip_custom_field_id: ZerverFieldsT,
    fields: ZerverFieldsT,
    user_id: int,
    custom_field_id: int,
    custom_field_values: list[ZerverFieldsT],
) -> int:
    for field, value in fields.items():
        if value["value"] == "":
            continue
        custom_field_value = CustomProfileFieldValue(id=custom_field_id, value=value["value"])

        custom_field_value_dict = model_to_dict(
            custom_field_value, exclude=["user_profile", "field"]
        )
        custom_field_value_dict["user_profile"] = user_id
        custom_field_value_dict["field"] = slack_custom_field_name_to_zulip_custom_field_id[field]

        custom_field_values.append(custom_field_value_dict)
        custom_field_id += 1
    return custom_field_id


def process_customprofilefields(
    customprofilefield: list[ZerverFieldsT], customprofilefield_value: list[ZerverFieldsT]
) -> None:
    for field in customprofilefield:
        for field_value in customprofilefield_value:
            if field_value["field"] == field["id"] and len(field_value["value"]) > 50:
                field["field_type"] = 2  # corresponding to Long text
                break


def is_slackbot(user: ZerverFieldsT) -> bool:
    return get_user_full_name(user).lower() == "slackbot"


def get_user_email(user: ZerverFieldsT, domain_name: str) -> str:
    if "email" in user["profile"]:
        return user["profile"]["email"]
    if user["is_mirror_dummy"]:
        return Address(username=user["name"], domain=f"{user['team_domain']}.slack.com").addr_spec
    if "bot_id" in user["profile"]:
        return SlackBotEmail.get_email(user["profile"], domain_name)
    if is_slackbot(user):
        return Address(username="imported-slackbot-bot", domain=domain_name).addr_spec
    raise AssertionError(f"Could not find email address for Slack user {user}")


def build_avatar_url(slack_user_id: str, user: ZerverFieldsT) -> tuple[str, str]:
    avatar_url: str = ""
    avatar_source = UserProfile.AVATAR_FROM_GRAVATAR
    if user["profile"].get("avatar_hash"):
        # Process avatar image for a typical Slack user.
        team_id = user["team_id"]
        avatar_hash = user["profile"]["avatar_hash"]
        avatar_url = f"https://ca.slack-edge.com/{team_id}-{slack_user_id}-{avatar_hash}"
        avatar_source = UserProfile.AVATAR_FROM_USER
    elif user.get("is_integration_bot") and "image_72" in user["profile"]:
        # Unlike other Slack user types, Slacks integration bot avatar URL ends with
        # a file type extension (.png, in this case).
        # e.g https://avatars.slack-edge.com/2024-05-01/7218497908_deb94eac4c_512.png
        avatar_url = user["profile"]["image_72"]
        content_type = guess_type(avatar_url)[0]
        if content_type not in THUMBNAIL_ACCEPT_IMAGE_TYPES:
            logging.info(
                "Unsupported avatar type (%s) for user -> %s\n", content_type, user.get("name")
            )
            avatar_source = UserProfile.AVATAR_FROM_GRAVATAR
        else:
            avatar_source = UserProfile.AVATAR_FROM_USER
    else:
        logging.info("Failed to process avatar for user -> %s\n", user.get("name"))
    return avatar_source, avatar_url


def get_owner(user: ZerverFieldsT) -> bool:
    owner = user.get("is_owner", False)
    primary_owner = user.get("is_primary_owner", False)

    return primary_owner or owner


def get_admin(user: ZerverFieldsT) -> bool:
    admin = user.get("is_admin", False)
    return admin


def get_guest(user: ZerverFieldsT) -> bool:
    restricted_user = user.get("is_restricted", False)
    ultra_restricted_user = user.get("is_ultra_restricted", False)

    # Slack's Single channel and multi channel guests both have
    # is_restricted set to True.  So assuming Slack doesn't change their
    # data model, it would also be correct to just check whether
    # is_restricted is set to True.
    return restricted_user or ultra_restricted_user


def get_user_timezone(user: ZerverFieldsT) -> str:
    _default_timezone = "America/New_York"
    timezone = user.get("tz", _default_timezone)
    if timezone is None or "/" not in timezone:
        timezone = _default_timezone
    return timezone


SLACK_DEFAULT_ANNOUNCEMENTS_CHANNEL_NAME = "general"


def channels_to_zerver_stream(
    slack_data_dir: str,
    realm_id: int,
    realm: dict[str, Any],
    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
    zerver_userprofile: list[ZerverFieldsT],
) -> tuple[
    dict[str, list[ZerverFieldsT]], AddedChannelsT, AddedMPIMsT, DMMembersT, SlackToZulipRecipientT
]:
    """
    Returns:
    1. realm, converted realm data
    2. added_channels, which is a dictionary to map from channel name to channel id, Zulip stream_id
    3. added_mpims, which is a dictionary to map from MPIM(multiparty IM) name to MPIM id, Zulip
       direct_message_group_id
    4. dm_members, which is a dictionary to map from DM id to tuple of DM participants.
    5. slack_recipient_name_to_zulip_recipient_id, which is a dictionary to map from Slack recipient
       name(channel names, mpim names, usernames etc) to Zulip recipient_id
    """
    logging.info("######### IMPORTING CHANNELS STARTED #########\n")

    zerver_realm = realm["zerver_realm"]

    added_channels = {}
    added_mpims = {}
    dm_members = {}
    slack_recipient_name_to_zulip_recipient_id = {}

    realm["zerver_stream"] = []
    realm["zerver_huddle"] = []
    realm["zerver_subscription"] = []
    realm["zerver_recipient"] = []
    realm["zerver_defaultstream"] = []

    subscription_id_count = recipient_id_count = 0
    stream_id_count = defaultstream_id = 0
    direct_message_group_id_count = 0

    def process_channels(channels: list[dict[str, Any]], invite_only: bool = False) -> None:
        nonlocal stream_id_count, recipient_id_count, defaultstream_id, subscription_id_count

        for channel in channels:
            # map Slack's topic and purpose content into Zulip's stream description.
            # WARN This mapping is lossy since the topic.creator, topic.last_set,
            # purpose.creator, purpose.last_set fields are not preserved.
            description = channel["purpose"]["value"]
            stream_id = stream_id_count
            recipient_id = recipient_id_count

            stream = build_stream(
                float(channel["created"]),
                realm_id,
                channel["name"],
                description,
                stream_id,
                channel["is_archived"],
                invite_only,
            )
            realm["zerver_stream"].append(stream)

            slack_default_channels = ["general", "random"]
            if channel["name"] in slack_default_channels and not stream["deactivated"]:
                defaultstream = build_defaultstream(realm_id, stream_id, defaultstream_id)
                realm["zerver_defaultstream"].append(defaultstream)
                defaultstream_id += 1

            added_channels[stream["name"]] = (channel["id"], stream_id)

            recipient = build_recipient(stream_id, recipient_id, Recipient.STREAM)
            realm["zerver_recipient"].append(recipient)
            slack_recipient_name_to_zulip_recipient_id[stream["name"]] = recipient_id

            subscription_id_count = get_subscription(
                channel["members"],
                realm["zerver_subscription"],
                recipient_id,
                slack_user_id_to_zulip_user_id,
                subscription_id_count,
            )

            stream_id_count += 1
            recipient_id_count += 1
            logging.info("%s -> created", channel["name"])

            if channel["name"] == SLACK_DEFAULT_ANNOUNCEMENTS_CHANNEL_NAME:
                zerver_realm[0]["new_stream_announcements_stream"] = stream["id"]
                zerver_realm[0]["zulip_update_announcements_stream"] = stream["id"]
                logging.info(
                    "Using the channel %s as default announcements channel.", channel["name"]
                )

            # TODO map Slack's pins to Zulip's stars
            # There is the security model that Slack's pins are known to the team owner
            # as evident from where it is stored at (channels)
            # "pins": [
            #         {
            #             "id": "1444755381.000003",
            #             "type": "C",
            #             "user": "U061A5N1G",
            #             "owner": "U061A5N1G",
            #             "created": "1444755463"
            #         }
            #         ],

    public_channels = get_data_file(slack_data_dir + "/channels.json")
    process_channels(public_channels)

    try:
        private_channels = get_data_file(slack_data_dir + "/groups.json")
    except FileNotFoundError:
        private_channels = []
    process_channels(private_channels, True)

    # mpim is the Slack equivalent of direct message group.
    def process_mpims(mpims: list[dict[str, Any]]) -> None:
        nonlocal direct_message_group_id_count, recipient_id_count, subscription_id_count

        for mpim in mpims:
            direct_message_group = build_direct_message_group(
                direct_message_group_id_count, len(mpim["members"])
            )
            realm["zerver_huddle"].append(direct_message_group)

            added_mpims[mpim["name"]] = (mpim["id"], direct_message_group_id_count)

            recipient = build_recipient(
                direct_message_group_id_count, recipient_id_count, Recipient.DIRECT_MESSAGE_GROUP
            )
            realm["zerver_recipient"].append(recipient)
            slack_recipient_name_to_zulip_recipient_id[mpim["name"]] = recipient_id_count

            subscription_id_count = get_subscription(
                mpim["members"],
                realm["zerver_subscription"],
                recipient_id_count,
                slack_user_id_to_zulip_user_id,
                subscription_id_count,
            )

            direct_message_group_id_count += 1
            recipient_id_count += 1
            logging.info("%s -> created", mpim["name"])

    try:
        mpims = get_data_file(slack_data_dir + "/mpims.json")
    except FileNotFoundError:
        mpims = []
    process_mpims(mpims)

    # This may have duplicated zulip user_ids, since we merge multiple
    # Slack same-email shared-channel users into one Zulip dummy user
    zulip_user_to_recipient: dict[int, int] = {}
    for slack_user_id, zulip_user_id in slack_user_id_to_zulip_user_id.items():
        if zulip_user_id in zulip_user_to_recipient:
            slack_recipient_name_to_zulip_recipient_id[slack_user_id] = zulip_user_to_recipient[
                zulip_user_id
            ]
            continue
        recipient = build_recipient(zulip_user_id, recipient_id_count, Recipient.PERSONAL)
        slack_recipient_name_to_zulip_recipient_id[slack_user_id] = recipient_id_count
        zulip_user_to_recipient[zulip_user_id] = recipient_id_count
        sub = build_subscription(recipient_id_count, zulip_user_id, subscription_id_count)
        realm["zerver_recipient"].append(recipient)
        realm["zerver_subscription"].append(sub)
        recipient_id_count += 1
        subscription_id_count += 1

    def process_dms(dms: list[dict[str, Any]]) -> None:
        for dm in dms:
            user_a = dm["members"][0]
            user_b = dm["members"][1]
            dm_members[dm["id"]] = (user_a, user_b)

    try:
        dms = get_data_file(slack_data_dir + "/dms.json")
    except FileNotFoundError:
        dms = []
    process_dms(dms)

    logging.info("######### IMPORTING STREAMS FINISHED #########\n")
    return (
        realm,
        added_channels,
        added_mpims,
        dm_members,
        slack_recipient_name_to_zulip_recipient_id,
    )


def get_subscription(
    channel_members: list[str],
    zerver_subscription: list[ZerverFieldsT],
    recipient_id: int,
    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
    subscription_id: int,
) -> int:
    processed_zulip_user_ids = set()
    for slack_user_id in channel_members:
        zulip_user_id = slack_user_id_to_zulip_user_id[slack_user_id]
        if zulip_user_id in processed_zulip_user_ids:
            # Multiple slack user ids can map to the same Zulip user id,
            # due to merging of accounts which share the same email address.
            # We don't want to create duplicate subscriptions for a user,
            # so if we've already seen this zulip_user_id, we skip ahead.
            continue

        processed_zulip_user_ids.add(zulip_user_id)
        sub = build_subscription(recipient_id, zulip_user_id, subscription_id)
        zerver_subscription.append(sub)
        subscription_id += 1
    return subscription_id


def process_long_term_idle_users(
    slack_data_dir: str,
    users: list[ZerverFieldsT],
    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
    added_channels: AddedChannelsT,
    added_mpims: AddedMPIMsT,
    dm_members: DMMembersT,
    zerver_userprofile: list[ZerverFieldsT],
) -> set[int]:
    return long_term_idle_helper(
        get_messages_iterator(slack_data_dir, added_channels, added_mpims, dm_members),
        get_message_sending_user,
        get_timestamp_from_message,
        lambda id: slack_user_id_to_zulip_user_id[id],
        iter(user["id"] for user in users),
        zerver_userprofile,
    )


def convert_slack_workspace_messages(
    slack_data_dir: str,
    users: list[ZerverFieldsT],
    realm_id: int,
    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
    slack_recipient_name_to_zulip_recipient_id: SlackToZulipRecipientT,
    added_channels: AddedChannelsT,
    added_mpims: AddedMPIMsT,
    dm_members: DMMembersT,
    realm: ZerverFieldsT,
    zerver_userprofile: list[ZerverFieldsT],
    zerver_realmemoji: list[ZerverFieldsT],
    domain_name: str,
    output_dir: str,
    convert_slack_threads: bool,
    chunk_size: int = MESSAGE_BATCH_CHUNK_SIZE,
) -> tuple[list[ZerverFieldsT], list[ZerverFieldsT], list[ZerverFieldsT]]:
    """
    Returns:
    1. reactions, which is a list of the reactions
    2. uploads, which is a list of uploads to be mapped in uploads records.json
    3. attachment, which is a list of the attachments
    """

    long_term_idle = process_long_term_idle_users(
        slack_data_dir,
        users,
        slack_user_id_to_zulip_user_id,
        added_channels,
        added_mpims,
        dm_members,
        zerver_userprofile,
    )

    all_messages = get_messages_iterator(slack_data_dir, added_channels, added_mpims, dm_members)
    logging.info("######### IMPORTING MESSAGES STARTED #########\n")

    total_reactions: list[ZerverFieldsT] = []
    total_attachments: list[ZerverFieldsT] = []
    total_uploads: list[ZerverFieldsT] = []

    dump_file_id = 1

    subscriber_map = make_subscriber_map(
        zerver_subscription=realm["zerver_subscription"],
    )

    while message_data := list(itertools.islice(all_messages, chunk_size)):
        (
            zerver_message,
            zerver_usermessage,
            attachment,
            uploads,
            reactions,
        ) = channel_message_to_zerver_message(
            realm_id,
            users,
            slack_user_id_to_zulip_user_id,
            slack_recipient_name_to_zulip_recipient_id,
            message_data,
            zerver_realmemoji,
            subscriber_map,
            added_channels,
            dm_members,
            domain_name,
            long_term_idle,
            convert_slack_threads,
        )

        message_json = dict(zerver_message=zerver_message, zerver_usermessage=zerver_usermessage)

        message_file = f"/messages-{dump_file_id:06}.json"
        logging.info("Writing messages to %s\n", output_dir + message_file)
        create_converted_data_files(message_json, output_dir, message_file)

        total_reactions += reactions
        total_attachments += attachment
        total_uploads += uploads

        dump_file_id += 1

    logging.info("######### IMPORTING MESSAGES FINISHED #########\n")
    return total_reactions, total_uploads, total_attachments


def get_messages_iterator(
    slack_data_dir: str,
    added_channels: dict[str, Any],
    added_mpims: AddedMPIMsT,
    dm_members: DMMembersT,
) -> Iterator[ZerverFieldsT]:
    """This function is an iterator that returns all the messages across
    all Slack channels, in order by timestamp.  It's important to
    not read all the messages into memory at once, because for
    large imports that can OOM kill."""

    dir_names = [*added_channels, *added_mpims, *dm_members]
    all_json_names: dict[str, list[str]] = defaultdict(list)
    for dir_name in dir_names:
        dir_path = os.path.join(slack_data_dir, dir_name)
        json_names = os.listdir(dir_path)
        for json_name in json_names:
            if json_name.endswith(".json"):
                all_json_names[json_name].append(dir_path)

    # Sort json_name by date
    for json_name in sorted(all_json_names.keys()):
        messages_for_one_day: list[ZerverFieldsT] = []
        for dir_path in all_json_names[json_name]:
            message_dir = os.path.join(dir_path, json_name)
            dir_name = os.path.basename(dir_path)
            messages = []
            for message in get_data_file(message_dir):
                if message.get("user") == "U00":
                    # Skip messages involving the "U00" user,
                    # which is apparently used in some channel rename
                    # messages.  It's likely just the result of some
                    # bug in Slack's export system.  Arguably we could
                    # change this to point to slackbot instead, but
                    # skipping those messages is simpler.
                    continue
                if message.get("mimetype") == "application/vnd.slack-docs":
                    # This is a Slack "Post" which is HTML-formatted,
                    # and we don't have a clean way to import at the
                    # moment.  We skip them on import.
                    continue
                if dir_name in added_channels:
                    message["channel_name"] = dir_name
                elif dir_name in added_mpims:
                    message["mpim_name"] = dir_name
                elif dir_name in dm_members:
                    message["pm_name"] = dir_name
                messages.append(message)
            messages_for_one_day += messages

        # we sort the messages according to the timestamp to show messages with
        # the proper date order
        yield from sorted(messages_for_one_day, key=get_timestamp_from_message)


def get_parent_user_id_from_thread_message(thread_message: ZerverFieldsT, subtype: str) -> str:
    """
    This retrieves the user id of the sender of the original thread
    message.
    """
    if subtype == "thread_broadcast":
        return thread_message["root"]["user"]
    elif thread_message["thread_ts"] == thread_message["ts"]:
        # This is the original thread message
        return thread_message["user"]
    else:
        return thread_message["parent_user_id"]


def get_zulip_thread_topic_name(
    message_content: str, thread_ts: datetime, thread_counter: dict[str, int]
) -> str:
    """
    The topic name format is date + message snippet + counter.

    e.g "2024-05-22 Hello this is a long message that will be c… (1)"
    """
    thread_date = thread_ts.strftime(r"%Y-%m-%d")

    # Truncate
    truncated_zulip_topic_name = truncate_content(
        f"{thread_date} {message_content}".strip(), MAX_TOPIC_NAME_LENGTH, "…"
    )
    collision = thread_counter[truncated_zulip_topic_name]
    thread_counter[truncated_zulip_topic_name] += 1
    count = (f" ({collision + 1})") if collision > 0 else ""

    # Important: The count is at the end, after …, so we need to
    # subtract its length when doing truncation.
    final_topic_name = (
        truncate_content(
            f"{thread_date} {message_content}".strip(), MAX_TOPIC_NAME_LENGTH - len(f"{count}"), "…"
        )
        + f"{count}"
    )
    return final_topic_name


def channel_message_to_zerver_message(
    realm_id: int,
    users: list[ZerverFieldsT],
    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
    slack_recipient_name_to_zulip_recipient_id: SlackToZulipRecipientT,
    all_messages: list[ZerverFieldsT],
    zerver_realmemoji: list[ZerverFieldsT],
    subscriber_map: dict[int, set[int]],
    added_channels: AddedChannelsT,
    dm_members: DMMembersT,
    domain_name: str,
    long_term_idle: set[int],
    convert_slack_threads: bool,
) -> tuple[
    list[ZerverFieldsT],
    list[ZerverFieldsT],
    list[ZerverFieldsT],
    list[ZerverFieldsT],
    list[ZerverFieldsT],
]:
    """
    Returns:
    1. zerver_message, which is a list of the messages
    2. zerver_usermessage, which is a list of the usermessages
    3. zerver_attachment, which is a list of the attachments
    4. uploads_list, which is a list of uploads to be mapped in uploads records.json
    5. reaction_list, which is a list of all user reactions
    """
    zerver_message = []
    zerver_usermessage: list[ZerverFieldsT] = []
    uploads_list: list[ZerverFieldsT] = []
    zerver_attachment: list[ZerverFieldsT] = []
    reaction_list: list[ZerverFieldsT] = []

    total_user_messages = 0
    total_skipped_user_messages = 0
    thread_counter: dict[str, int] = defaultdict(int)
    thread_map: dict[str, str] = {}
    for message in all_messages:
        slack_user_id = get_message_sending_user(message)
        if not slack_user_id:
            # Ignore messages without slack_user_id
            # These are Sometimes produced by Slack
            continue

        subtype = message.get("subtype", False)
        if subtype in [
            # Zulip doesn't have a pinned_item concept
            "pinned_item",
            "unpinned_item",
            # Slack's channel join/leave notices are spammy
            "channel_join",
            "channel_leave",
            "channel_name",
        ]:
            continue

        formatted_block = process_slack_block_and_attachment(message)

        # Leave it as is if formatted_block is an empty string, it's likely
        # one of the unhandled_types.
        if formatted_block != "":
            # For most cases, the value of message["text"] will be just an
            # empty string.
            message["text"] = formatted_block

        try:
            content, mentioned_user_ids, has_link = convert_to_zulip_markdown(
                message["text"], users, added_channels, slack_user_id_to_zulip_user_id
            )
        except Exception:
            print("Slack message unexpectedly missing text representation:")
            print(orjson.dumps(message, option=orjson.OPT_INDENT_2).decode())
            continue
        rendered_content = None

        if "channel_name" in message:
            is_direct_message_type = False
            recipient_id = slack_recipient_name_to_zulip_recipient_id[message["channel_name"]]
        elif "mpim_name" in message:
            is_direct_message_type = True
            recipient_id = slack_recipient_name_to_zulip_recipient_id[message["mpim_name"]]
        elif "pm_name" in message:
            is_direct_message_type = True
            sender = get_message_sending_user(message)
            members = dm_members[message["pm_name"]]
            if sender == members[0]:
                recipient_id = slack_recipient_name_to_zulip_recipient_id[members[1]]
                sender_recipient_id = slack_recipient_name_to_zulip_recipient_id[members[0]]
            else:
                recipient_id = slack_recipient_name_to_zulip_recipient_id[members[0]]
                sender_recipient_id = slack_recipient_name_to_zulip_recipient_id[members[1]]

        message_id = NEXT_ID("message")

        if "reactions" in message:
            build_reactions(
                reaction_list,
                message["reactions"],
                slack_user_id_to_zulip_user_id,
                message_id,
                zerver_realmemoji,
            )

        # Process different subtypes of slack messages

        # Subtypes which have only the action in the message should
        # be rendered with '/me' in the content initially
        # For example "sh_room_created" has the message 'started a call'
        # which should be displayed as '/me started a call'
        if subtype in ["bot_add", "sh_room_created", "me_message"]:
            content = f"/me {content}"
        if subtype == "file_comment":
            # The file_comment message type only indicates the
            # responsible user in a subfield.
            message["user"] = message["comment"]["user"]

        file_info = process_message_files(
            message=message,
            domain_name=domain_name,
            realm_id=realm_id,
            message_id=message_id,
            slack_user_id=slack_user_id,
            users=users,
            slack_user_id_to_zulip_user_id=slack_user_id_to_zulip_user_id,
            zerver_attachment=zerver_attachment,
            uploads_list=uploads_list,
        )

        content = "\n".join([part for part in [content, file_info["content"]] if part != ""])
        has_link = has_link or file_info["has_link"]

        has_attachment = file_info["has_attachment"]
        has_image = file_info["has_image"]

        # Slack's unthreaded messages go into a single topic, while
        # threads each generate a unique topic labeled by the date,
        # a snippet of the original message and a counter if there
        # are any thread with the same topic name
        topic_name = "imported from Slack"
        if convert_slack_threads and not is_direct_message_type and "thread_ts" in message:
            thread_ts = datetime.fromtimestamp(float(message["thread_ts"]), tz=timezone.utc)
            thread_ts_str = thread_ts.strftime(r"%Y/%m/%d %H:%M:%S")
            parent_user_id = get_parent_user_id_from_thread_message(message, subtype)
            thread_key = f"{thread_ts_str}-{parent_user_id}"

            if thread_key in thread_map:
                topic_name = thread_map[thread_key]
            else:
                topic_name = get_zulip_thread_topic_name(content, thread_ts, thread_counter)
                thread_map[thread_key] = topic_name

        if is_direct_message_type:
            topic_name = ""

        zulip_message = build_message(
            topic_name=topic_name,
            date_sent=get_timestamp_from_message(message),
            message_id=message_id,
            content=content,
            rendered_content=rendered_content,
            user_id=slack_user_id_to_zulip_user_id[slack_user_id],
            recipient_id=recipient_id,
            realm_id=realm_id,
            is_channel_message=not is_direct_message_type,
            has_image=has_image,
            has_link=has_link,
            has_attachment=has_attachment,
            is_direct_message_type=is_direct_message_type,
        )
        zerver_message.append(zulip_message)

        (num_created, num_skipped) = build_usermessages(
            zerver_usermessage=zerver_usermessage,
            subscriber_map=subscriber_map,
            recipient_id=recipient_id,
            mentioned_user_ids=mentioned_user_ids,
            message_id=message_id,
            is_private=is_direct_message_type,
            long_term_idle=long_term_idle,
        )
        total_user_messages += num_created
        total_skipped_user_messages += num_skipped

        if "pm_name" in message and recipient_id != sender_recipient_id:
            (num_created, num_skipped) = build_usermessages(
                zerver_usermessage=zerver_usermessage,
                subscriber_map=subscriber_map,
                recipient_id=sender_recipient_id,
                mentioned_user_ids=mentioned_user_ids,
                message_id=message_id,
                is_private=is_direct_message_type,
                long_term_idle=long_term_idle,
            )
            total_user_messages += num_created
            total_skipped_user_messages += num_skipped

    logging.debug(
        "Created %s UserMessages; deferred %s due to long-term idle",
        total_user_messages,
        total_skipped_user_messages,
    )
    return zerver_message, zerver_usermessage, zerver_attachment, uploads_list, reaction_list


def process_message_files(
    message: ZerverFieldsT,
    domain_name: str,
    realm_id: int,
    message_id: int,
    slack_user_id: str,
    users: list[ZerverFieldsT],
    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
    zerver_attachment: list[ZerverFieldsT],
    uploads_list: list[ZerverFieldsT],
) -> dict[str, Any]:
    has_attachment = False
    has_image = False
    has_link = False

    files = message.get("files", [])

    subtype = message.get("subtype")

    if subtype == "file_share":
        # In Slack messages, uploads can either have the subtype as 'file_share' or
        # have the upload information in 'files' keyword
        files = [message["file"]]

    markdown_links = []

    for fileinfo in files:
        if fileinfo.get("mode", "") in ["tombstone", "hidden_by_limit"]:
            # Slack sometimes includes tombstone mode files with no
            # real data on the actual file (presumably in cases where
            # the file was deleted). hidden_by_limit mode is for files
            # that are hidden because of 10k cap in free plan.
            continue

        if fileinfo.get("file_access", "") in ["access_denied", "file_not_found"]:
            # Slack sometimes includes file stubs for files it declares
            # inaccessible and does not further reference.
            continue

        url = fileinfo["url_private"]
        split_url = urlsplit(url)

        if split_url.hostname == "files.slack.com":
            # For attachments with Slack download link
            has_attachment = True
            has_link = True
            has_image = "image" in fileinfo["mimetype"]

            file_user = [
                iterate_user for iterate_user in users if message["user"] == iterate_user["id"]
            ]
            file_user_email = get_user_email(file_user[0], domain_name)

            s3_path, content_for_link = get_attachment_path_and_content(fileinfo, realm_id)
            markdown_links.append(content_for_link)

            build_uploads(
                slack_user_id_to_zulip_user_id[slack_user_id],
                realm_id,
                file_user_email,
                fileinfo,
                s3_path,
                uploads_list,
            )

            build_attachment(
                realm_id,
                {message_id},
                slack_user_id_to_zulip_user_id[slack_user_id],
                fileinfo,
                s3_path,
                zerver_attachment,
            )
        else:
            # For attachments with link not from Slack
            # Example: Google drive integration
            has_link = True
            if "title" in fileinfo:
                file_name = fileinfo["title"]
            else:
                file_name = fileinfo["name"]
            markdown_links.append("[{}]({})".format(file_name, fileinfo["url_private"]))

    content = "\n".join(markdown_links)

    return dict(
        content=content,
        has_attachment=has_attachment,
        has_image=has_image,
        has_link=has_link,
    )


def get_attachment_path_and_content(fileinfo: ZerverFieldsT, realm_id: int) -> tuple[str, str]:
    # Should be kept in sync with its equivalent in zerver/lib/uploads in the function
    # 'upload_message_attachment'
    s3_path = "/".join(
        [
            str(realm_id),
            format(random.randint(0, 255), "x"),
            secrets.token_urlsafe(18),
            sanitize_name(fileinfo["name"]),
        ]
    )
    attachment_path = f"/user_uploads/{s3_path}"
    content = "[{}]({})".format(fileinfo["title"], attachment_path)

    return s3_path, content


def build_reactions(
    reaction_list: list[ZerverFieldsT],
    reactions: list[ZerverFieldsT],
    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
    message_id: int,
    zerver_realmemoji: list[ZerverFieldsT],
) -> None:
    realmemoji = {}
    for realm_emoji in zerver_realmemoji:
        realmemoji[realm_emoji["name"]] = realm_emoji["id"]

    # Slack's data exports use encode skin tone variants on emoji
    # reactions like this: `clap::skin-tone-2`. For now, we only
    # use the name of the base emoji, since Zulip's emoji
    # reactions system doesn't yet support skin tone modifiers.
    # We need to merge and dedup reactions, as someone may have
    # reacted to `clap::skin-tone-1` and `clap::skin-tone-2`, etc.
    merged_reactions = defaultdict(set)
    for slack_reaction in reactions:
        emoji_name = slack_reaction["name"].split("::", maxsplit=1)[0]
        merged_reactions[emoji_name].update(slack_reaction["users"])
    reactions = [{"name": k, "users": v, "count": len(v)} for k, v in merged_reactions.items()]

    processed_reactions: set[tuple[int, int, str, str]] = set()
    # For the Unicode emoji codes, we use equivalent of
    # function 'get_emoji_data' in 'zerver/lib/emoji' here
    for slack_reaction in reactions:
        emoji_name = slack_reaction["name"]
        if emoji_name in slack_emoji_name_to_codepoint:
            emoji_code = slack_emoji_name_to_codepoint[emoji_name]
            try:
                zulip_emoji_name = codepoint_to_name[emoji_code]
            except KeyError:
                print(f"WARN: Emoji found in iamcal but not Zulip: {emoji_name}")
                continue
            # Convert Slack emoji name to Zulip emoji name.
            emoji_name = zulip_emoji_name
            reaction_type = Reaction.UNICODE_EMOJI
        elif emoji_name in realmemoji:
            emoji_code = realmemoji[emoji_name]
            reaction_type = Reaction.REALM_EMOJI
        else:
            print(f"WARN: Emoji not found in iamcal: {emoji_name}")
            continue

        for slack_user_id in slack_reaction["users"]:
            if slack_user_id not in slack_user_id_to_zulip_user_id:
                # Deleted users still have reaction references but no profile, so we skip
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
            zulip_user_id = slack_user_id_to_zulip_user_id[slack_user_id]
            reaction_dict["user_profile"] = zulip_user_id

            reaction_tuple = (zulip_user_id, message_id, reaction_type, emoji_code)
            if reaction_tuple in processed_reactions:
                # Due to possible merging of Slack accounts into a single Zulip account,
                # we need to ensure reactions don't get duplicated, violating the unique
                # constraint on the (user_profile_id, message_id, reaction_type, emoji_code)
                # index.
                continue
            processed_reactions.add(reaction_tuple)

            reaction_list.append(reaction_dict)


def build_uploads(
    user_id: int,
    realm_id: int,
    email: str,
    fileinfo: ZerverFieldsT,
    s3_path: str,
    uploads_list: list[ZerverFieldsT],
) -> None:
    upload = dict(
        path=fileinfo["url_private"],  # Save Slack's URL here, which is used later while processing
        realm_id=realm_id,
        content_type=None,
        user_profile_id=user_id,
        last_modified=fileinfo["timestamp"],
        user_profile_email=email,
        s3_path=s3_path,
        size=fileinfo["size"],
    )
    uploads_list.append(upload)


def get_message_sending_user(message: ZerverFieldsT) -> str | None:
    if "user" in message:
        return message["user"]
    if message.get("file"):
        return message["file"].get("user")
    if message.get("bot_id"):
        return message.get("bot_id")
    return None


def get_timestamp_from_message(message: ZerverFieldsT) -> float:
    return float(message["ts"])


def is_integration_bot_message(message: ZerverFieldsT) -> bool:
    return message.get("subtype") == "bot_message" and "user" not in message and "bot_id" in message


def convert_bot_info_to_slack_user(bot_info: dict[str, Any]) -> ZerverFieldsT:
    # We use "image_72," an icon-sized 72x72 pixel image, for the Slack integration
    # bots avatar because it is the best available option. As a consequence, this
    # will make the avatar appear blurry in places where a medium-sized avatar
    # (500x500px) is expected, such as in the user profile menu.

    bot_user = {
        "id": bot_info["id"],
        "name": bot_info["name"],
        "deleted": bot_info["deleted"],
        "is_mirror_dummy": False,
        "real_name": bot_info["name"],
        "is_integration_bot": True,
        "profile": {
            "bot_id": bot_info["id"],
            "first_name": bot_info["name"],
        },
    }
    if "image_72" in bot_info["icons"]:
        # Otherwise, gravatar will be used.
        bot_user["profile"]["image_72"] = bot_info["icons"]["image_72"]

    return bot_user


def make_deleted_placeholder(bot_id: str) -> ZerverFieldsT:
    name = f"Deleted Slack Bot {bot_id}"
    bot_user = {
        "id": bot_id,
        "name": name,
        "deleted": True,
        "is_mirror_dummy": False,
        "real_name": name,
        "is_integration_bot": True,
        "profile": {
            # Intentionally skip image_72. Gravatar should be used.
            "bot_id": bot_id,
            "first_name": name,
        },
    }
    return bot_user


def fetch_shared_channel_users(
    user_list: list[ZerverFieldsT], slack_data_dir: str, token: str
) -> None:
    normal_user_ids = set()
    mirror_dummy_user_ids = set()
    added_channels = {}
    integration_bot_users: list[str] = []
    team_id_to_domain: dict[str, str] = {}
    for user in user_list:
        user["is_mirror_dummy"] = False
        normal_user_ids.add(user["id"])

    public_channels = get_data_file(slack_data_dir + "/channels.json")
    try:
        private_channels = get_data_file(slack_data_dir + "/groups.json")
    except FileNotFoundError:
        private_channels = []
    try:
        direct_message_groups = get_data_file(slack_data_dir + "/mpims.json")
    except FileNotFoundError:
        direct_message_groups = []
    for channel in public_channels + private_channels + direct_message_groups:
        added_channels[channel["name"]] = True
        for user_id in channel["members"]:
            if user_id not in normal_user_ids:
                mirror_dummy_user_ids.add(user_id)
    if os.path.exists(slack_data_dir + "/dms.json"):
        dms = get_data_file(slack_data_dir + "/dms.json")
        for dm_data in dms:
            for user_id in dm_data["members"]:
                if user_id not in normal_user_ids:
                    mirror_dummy_user_ids.add(user_id)

    all_messages = get_messages_iterator(slack_data_dir, added_channels, {}, {})
    for message in all_messages:
        if is_integration_bot_message(message):
            # This message is likely from an integration bot. Since Slack's integration
            # bots doesn't have user profiles, we need to artificially create users for
            # them to convert their messages.
            bot_id = message["bot_id"]
            if bot_id in integration_bot_users:
                continue
            try:
                bot_info = get_slack_api_data(
                    "https://slack.com/api/bots.info", "bot", token=token, bot=bot_id
                )
            except SlackBotNotFoundError:
                logging.info("Bot %s not found, creating a deleted placeholder", bot_id)
                bot_user = make_deleted_placeholder(bot_id)
            else:
                bot_user = convert_bot_info_to_slack_user(bot_info)

            user_list.append(bot_user)
            integration_bot_users.append(bot_id)
        else:
            user_id = get_message_sending_user(message)
            if user_id is None or user_id in normal_user_ids:
                continue
            mirror_dummy_user_ids.add(user_id)

    # Fetch data on the mirror_dummy_user_ids from the Slack API (it's
    # not included in the data export file).
    for user_id in mirror_dummy_user_ids:
        user = get_slack_api_data(
            "https://slack.com/api/users.info", "user", token=token, user=user_id
        )
        team_id = user["team_id"]
        if team_id not in team_id_to_domain:
            team = get_slack_api_data(
                "https://slack.com/api/team.info", "team", token=token, team=team_id
            )
            team_id_to_domain[team_id] = team["domain"]
        user["team_domain"] = team_id_to_domain[team_id]
        user["is_mirror_dummy"] = True
        user_list.append(user)


def fetch_team_icons(
    zerver_realm: dict[str, Any], team_info_dict: dict[str, Any], output_dir: str
) -> list[dict[str, Any]]:
    records = []

    team_icons_dict = team_info_dict["icon"]
    if team_icons_dict.get("image_default", False):
        return []

    icon_url = (
        team_icons_dict.get("image_original", None)
        or team_icons_dict.get("image_230", None)
        or team_icons_dict.get("image_132", None)
        or team_icons_dict.get("image_102", None)
    )
    if icon_url is None:
        return []

    response = requests.get(icon_url, stream=True)
    response_raw = response.raw

    realm_id = zerver_realm["id"]
    os.makedirs(os.path.join(output_dir, str(realm_id)), exist_ok=True)

    original_icon_output_path = os.path.join(output_dir, str(realm_id), "icon.original")
    with open(original_icon_output_path, "wb") as output_file:
        shutil.copyfileobj(response_raw, output_file)
    records.append(
        {
            "realm_id": realm_id,
            "path": os.path.join(str(realm_id), "icon.original"),
            "s3_path": os.path.join(str(realm_id), "icon.original"),
            "content_type": response.headers["Content-Type"],
        }
    )

    resized_icon_output_path = os.path.join(output_dir, str(realm_id), "icon.png")
    with (
        open(resized_icon_output_path, "wb") as output_file,
        open(original_icon_output_path, "rb") as original_file,
    ):
        resized_data = resize_realm_icon(original_file.read())
        output_file.write(resized_data)
    records.append(
        {
            "realm_id": realm_id,
            "path": os.path.join(str(realm_id), "icon.png"),
            "s3_path": os.path.join(str(realm_id), "icon.png"),
            "content_type": "image/png",
        }
    )

    zerver_realm["icon_source"] = Realm.ICON_UPLOADED

    return records


def do_convert_zipfile(
    original_path: str,
    output_dir: str,
    token: str,
    threads: int = 6,
    convert_slack_threads: bool = False,
) -> None:
    assert original_path.endswith(".zip")
    slack_data_dir = original_path.removesuffix(".zip")
    try:
        os.makedirs(slack_data_dir, exist_ok=True)

        with zipfile.ZipFile(original_path) as zipObj:
            total_size = 0
            for fileinfo in zipObj.infolist():
                # Slack's export doesn't set the UTF-8 flag on each
                # filename entry, despite encoding them as such, so
                # zipfile mojibake's the output.  Explicitly re-interpret
                # it as UTF-8 misdecoded as cp437, the default.
                fileinfo.flag_bits |= 0x800
                fileinfo.filename = fileinfo.filename.encode("cp437").decode("utf-8")
                zipObj.NameToInfo[fileinfo.filename] = fileinfo

                # The only files we expect to find in a Slack export are .json files:
                #   something.json
                #   channelname/
                #   channelname/2024-01-02.json
                #
                # Canvases may also appear in exports, either in their own
                # top-level directories, or as `canvas_in_the_conversation.json`
                # files in channel directories.  We do not parse these currently.
                if not re.match(r"[^/]+(\.json|/([^/]+\.json)?)$", fileinfo.filename):
                    raise SlackImportInvalidFileError(
                        "Uploaded zip file is not a valid Slack export."
                    )

                # file_size is the uncompressed size of the file
                total_size += fileinfo.file_size

            # Based on historical Slack exports, anything that is more
            # than a 10x size magnification is suspect, particularly
            # if it results in over 1GB.
            if total_size > 1024 * 1024 * 1024 and total_size > 10 * os.path.getsize(original_path):
                raise SlackImportInvalidFileError("Uploaded zip file is not a valid Slack export.")

            zipObj.extractall(slack_data_dir)

        do_convert_directory(slack_data_dir, output_dir, token, threads, convert_slack_threads)
    finally:
        # Always clean up the uncompressed directory
        rm_tree(slack_data_dir)


SLACK_IMPORT_TOKEN_SCOPES = {"emoji:read", "users:read", "users:read.email", "team:read"}


def do_convert_directory(
    slack_data_dir: str,
    output_dir: str,
    token: str,
    threads: int = 6,
    convert_slack_threads: bool = False,
) -> None:
    check_token_access(token, SLACK_IMPORT_TOKEN_SCOPES)

    os.makedirs(output_dir, exist_ok=True)
    if os.listdir(output_dir):
        raise Exception("Output directory should be empty!")

    if not os.path.isfile(os.path.join(slack_data_dir, "channels.json")):
        raise ValueError("Import does not have the layout we expect from a Slack export!")

    # We get the user data from the legacy token method of Slack API, which is depreciated
    # but we use it as the user email data is provided only in this method.
    # Fetching from this endpoint requires using pagination, as only a subset
    # of the users might be returned in any single request.
    # We use the limit value of 200, as that's suggested in Slack's documentation for this
    # endpoint.
    user_list = get_slack_api_data(
        "https://slack.com/api/users.list", "members", token=token, pagination_limit=200
    )
    fetch_shared_channel_users(user_list, slack_data_dir, token)

    custom_emoji_list = get_slack_api_data("https://slack.com/api/emoji.list", "emoji", token=token)

    # Subdomain is set by the user while running the import command
    realm_subdomain = ""
    realm_id = 0
    domain_name = SplitResult("", settings.EXTERNAL_HOST, "", "", "").hostname
    assert isinstance(domain_name, str)

    (
        realm,
        slack_user_id_to_zulip_user_id,
        slack_recipient_name_to_zulip_recipient_id,
        added_channels,
        added_mpims,
        dm_members,
        avatar_list,
        emoji_url_map,
    ) = slack_workspace_to_realm(
        domain_name, realm_id, user_list, realm_subdomain, slack_data_dir, custom_emoji_list
    )

    reactions, uploads_list, zerver_attachment = convert_slack_workspace_messages(
        slack_data_dir,
        user_list,
        realm_id,
        slack_user_id_to_zulip_user_id,
        slack_recipient_name_to_zulip_recipient_id,
        added_channels,
        added_mpims,
        dm_members,
        realm,
        realm["zerver_userprofile"],
        realm["zerver_realmemoji"],
        domain_name,
        output_dir,
        convert_slack_threads,
    )

    # Move zerver_reactions to realm.json file
    realm["zerver_reaction"] = reactions

    emoji_folder = os.path.join(output_dir, "emoji")
    os.makedirs(emoji_folder, exist_ok=True)
    emoji_records = process_emojis(realm["zerver_realmemoji"], emoji_folder, emoji_url_map, threads)

    avatar_folder = os.path.join(output_dir, "avatars")
    avatar_realm_folder = os.path.join(avatar_folder, str(realm_id))
    os.makedirs(avatar_realm_folder, exist_ok=True)
    avatar_records = process_avatars(
        avatar_list, avatar_folder, realm_id, threads, size_url_suffix="-512"
    )

    uploads_folder = os.path.join(output_dir, "uploads")
    os.makedirs(os.path.join(uploads_folder, str(realm_id)), exist_ok=True)
    uploads_records = process_uploads(uploads_list, uploads_folder, threads)
    attachment = {"zerver_attachment": zerver_attachment}

    team_info_dict = get_slack_api_data("https://slack.com/api/team.info", "team", token=token)
    realm_icons_folder = os.path.join(output_dir, "realm_icons")
    realm_icon_records = fetch_team_icons(
        realm["zerver_realm"][0], team_info_dict, realm_icons_folder
    )

    create_converted_data_files(realm, output_dir, "/realm.json")
    create_converted_data_files(emoji_records, output_dir, "/emoji/records.json")
    create_converted_data_files(avatar_records, output_dir, "/avatars/records.json")
    create_converted_data_files(uploads_records, output_dir, "/uploads/records.json")
    create_converted_data_files(attachment, output_dir, "/attachment.json")
    create_converted_data_files(realm_icon_records, output_dir, "/realm_icons/records.json")
    do_common_export_processes(output_dir)

    logging.info("######### DATA CONVERSION FINISHED #########\n")
    logging.info("Zulip data dump created at %s", output_dir)


def get_data_file(path: str) -> Any:
    with open(path, "rb") as fp:
        data = orjson.loads(fp.read())
        return data


def check_token_access(token: str, required_scopes: set[str]) -> None:
    if token.startswith("xoxp-"):
        logging.info("This is a Slack user token, which grants all rights the user has!")
    elif token.startswith("xoxb-"):
        data = requests.get(
            "https://slack.com/api/api.test", headers={"Authorization": f"Bearer {token}"}
        )
        if data.status_code != 200:
            raise ValueError(
                f"Failed to fetch data (HTTP status {data.status_code}) for Slack token: {token}"
            )
        if not data.json()["ok"]:
            error = data.json()["error"]
            if error != "missing_scope":
                logging.error("Slack token is invalid: %s", error)
                raise ValueError(f"Invalid token: {token}")
        has_scopes = set(data.headers.get("x-oauth-scopes", "").split(","))
        missing_scopes = required_scopes - has_scopes
        if missing_scopes:
            raise ValueError(
                f"Slack token is missing the following required scopes: {sorted(missing_scopes)}"
            )
    else:
        raise Exception("Invalid token. Valid tokens start with xoxb-.")


def get_slack_api_data(
    slack_api_url: str,
    get_param: str,
    *,
    pagination_limit: int | None = None,
    raise_if_rate_limited: bool = False,
    **kwargs: Any,
) -> Any:
    if not kwargs.get("token"):
        raise AssertionError("Slack token missing in kwargs")

    token = kwargs.pop("token")
    accumulated_result = []
    cursor: str | None = None
    while True:
        if pagination_limit is not None:
            # If we're fetching with pagination, this might take a while, so we want reasonable logging to show
            # progress and what's being fetched.
            logging.info(
                "Fetching page from %s with cursor: %s and limit: %s",
                slack_api_url,
                cursor,
                pagination_limit,
            )

        params: dict[str, int | str] = {"limit": pagination_limit} if pagination_limit else {}
        if cursor:
            params["cursor"] = cursor
        params.update(kwargs)

        response = requests.get(
            slack_api_url, headers={"Authorization": f"Bearer {token}"}, params=params
        )

        if response.status_code == 429:
            if raise_if_rate_limited:
                raise Exception("Exceeded Slack rate limits.")
            retry_after = int(response.headers.get("retry-after", 1))
            logging.info("Rate limit exceeded. Retrying in %s seconds...", retry_after)
            time.sleep(retry_after)
            continue

        if response.status_code != requests.codes.ok:
            logging.info("HTTP error: %s, Response: %s", response.status_code, response.text)
            raise Exception("HTTP error accessing the Slack API.")

        result = response.json()
        if not result["ok"]:
            if result["error"] == "bot_not_found":
                raise SlackBotNotFoundError

            raise Exception("Error accessing Slack API: {}".format(result["error"]))

        result_data = result[get_param]

        if pagination_limit is None:
            # We're not using pagination, so we don't want to loop and should just return the result.
            return result_data

        accumulated_result.extend(result_data)
        if not result.get("response_metadata", {}).get("next_cursor"):
            # Everything has been fetched.
            break

        cursor = result["response_metadata"]["next_cursor"]

    return accumulated_result


class SlackBotNotFoundError(Exception):
    pass
