import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, TypeAlias
from urllib.parse import SplitResult

from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    ZerverFieldsT,
    build_message,
    build_realm,
    build_recipient,
    build_stream,
    build_subscription,
    build_usermessages,
    build_zerver_realm,
    convert_html_to_text,
    create_converted_data_files,
    make_subscriber_map,
    validate_user_emails_for_import,
)
from zerver.data_import.sequencer import NEXT_ID
from zerver.data_import.slack import get_data_file
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE, do_common_export_processes
from zerver.models.recipients import Recipient
from zerver.models.users import UserProfile


@dataclass
class TeamMetadata:
    """
    Microsoft Teams' "teams" is equivalent to Zulip channels.
    """

    description: str
    display_name: str
    visibility: Literal["public", "private"]
    is_archived: bool
    zulip_channel_id: int
    zulip_recipient_id: int


@dataclass
class ChannelMetadata:
    """
    Microsoft Teams' "channels" is equivalent to Zulip topics.
    """

    description: str
    display_name: str
    is_favourite_by_default: bool
    is_archived: bool
    membership_type: str
    team_id: str


AddedTeamsT: TypeAlias = dict[str, TeamMetadata]
TeamIdToZulipRecipientIdT: TypeAlias = dict[str, int]
MicrosoftTeamsUserIdToZulipUserIdT: TypeAlias = dict[str, int]
MicrosoftTeamsFieldsT: TypeAlias = dict[str, Any]

MICROSOFT_TEAMS_DEFAULT_ANNOUNCEMENTS_CHANNEL_NAME = "All company"


def add_custom_announcements_channel(
    realm: dict[str, Any],
    realm_id: int,
    default_announcement_channel_id: int | None,
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
) -> None:
    channel_id = default_announcement_channel_id

    # A team called "All Company" is always included in the export data
    # regardless of whether or not the organization actually has and uses
    # the team. In the chance where it is used, we'll use that as the
    # default announcement channels. If not, create an artificial one.
    if default_announcement_channel_id is None:
        recipient_id = NEXT_ID("recipient")
        channel_id = NEXT_ID("channel")
        channel = build_stream(
            # Microsoft Teams export doesn't include teams creation date.
            float(timezone_now().timestamp()),
            realm_id,
            MICROSOFT_TEAMS_DEFAULT_ANNOUNCEMENTS_CHANNEL_NAME,
            "This is the default group for everyone in the network",
            channel_id,
            False,
            False,
        )
        realm["zerver_stream"].append(channel)
        channel_id = channel["id"]

        recipient = build_recipient(channel_id, recipient_id, Recipient.STREAM)
        realm["zerver_recipient"].append(recipient)

        all_user_ids = list(microsoft_teams_user_id_to_zulip_user_id.values())
        for user_id in all_user_ids:
            sub = build_subscription(
                recipient_id=recipient_id,
                user_id=user_id,
                subscription_id=NEXT_ID("subscription"),
            )
            realm["zerver_subscription"].append(sub)

    realm["zerver_realm"][0]["new_stream_announcements_stream"] = channel_id
    realm["zerver_realm"][0]["zulip_update_announcements_stream"] = channel_id
    realm["zerver_realm"][0]["signup_announcements_stream"] = channel_id
    logging.info("Using the channel 'All Company' as default announcements channel.")


def convert_teams_to_channels(
    realm: dict[str, Any],
    realm_id: int,
    teams_data_dir: str,
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
) -> tuple[AddedTeamsT, TeamIdToZulipRecipientIdT]:
    realm["zerver_stream"] = []
    realm["zerver_subscription"] = []
    realm["zerver_recipient"] = []
    realm["zerver_defaultstream"] = []

    team_id_to_zulip_recipient_id: TeamIdToZulipRecipientIdT = {}
    teams_metadata: AddedTeamsT = {}
    team_data_folders = []
    for f in os.listdir(teams_data_dir):
        path = os.path.join(teams_data_dir, f)
        if os.path.isdir(path):
            team_data_folders.append(f)

    logging.info("######### IMPORTING TEAMS STARTED #########\n")

    # Build teams subscription map
    raw_teams_subscription_data: dict[str, list[int]] = defaultdict(list)
    for team_id in team_data_folders:
        team_members_file_name = f"teamMembers_{team_id}.json"
        team_members_file_path = os.path.join(teams_data_dir, team_id, team_members_file_name)
        team_members: list[MicrosoftTeamsFieldsT] = get_data_file(team_members_file_path)

        for member in team_members:
            zulip_user_id = microsoft_teams_user_id_to_zulip_user_id[member["UserId"]]
            raw_teams_subscription_data[team_id].append(zulip_user_id)

    # Compile teamsSettings.json and teamsList.json and build
    # teams Zulip channels.
    teams_list = get_data_file(os.path.join(teams_data_dir, "teamsList.json"))
    teams_settings = get_data_file(os.path.join(teams_data_dir, "teamsSettings.json"))
    team_dict: dict[str, Any] = {team["GroupsId"]: team for team in teams_list}

    default_announcement_channel_id: int | None = None
    for team_settings in teams_settings:
        team_id = team_settings.get("Id")

        if not team_id or team_id not in team_dict:
            continue
        compiled_team_data: MicrosoftTeamsFieldsT = {**team_dict[team_id], **team_settings}

        channel_id = NEXT_ID("channel")
        recipient_id = NEXT_ID("recipient")
        invite_only = compiled_team_data["Visibility"] == "private"

        channel = build_stream(
            # Microsoft Teams export doesn't include teams creation date.
            float(timezone_now().timestamp()),
            realm_id,
            compiled_team_data["Name"],
            compiled_team_data["Description"],
            channel_id,
            compiled_team_data["IsArchived"],
            invite_only,
        )
        realm["zerver_stream"].append(channel)

        recipient = build_recipient(channel_id, recipient_id, Recipient.STREAM)
        realm["zerver_recipient"].append(recipient)
        team_id_to_zulip_recipient_id[team_id] = recipient_id

        for zulip_user_id in raw_teams_subscription_data[team_id]:
            sub = build_subscription(
                recipient_id=recipient_id,
                user_id=zulip_user_id,
                subscription_id=NEXT_ID("subscription"),
            )
            realm["zerver_subscription"].append(sub)

        if compiled_team_data["Name"] == MICROSOFT_TEAMS_DEFAULT_ANNOUNCEMENTS_CHANNEL_NAME:
            default_announcement_channel_id = channel_id

        teams_metadata[team_id] = TeamMetadata(
            description=compiled_team_data["Description"],
            display_name=compiled_team_data["DisplayName"],
            visibility=compiled_team_data["Visibility"],
            is_archived=compiled_team_data["IsArchived"],
            zulip_channel_id=channel_id,
            zulip_recipient_id=recipient_id,
        )

    # Microsoft Teams doesn't have a default team(channel). The
    # closest thing to that is "org-wide" teams, but it's practically
    # indistinguishable from a normal public team once exported.
    add_custom_announcements_channel(
        realm=realm,
        realm_id=realm_id,
        default_announcement_channel_id=default_announcement_channel_id,
        microsoft_teams_user_id_to_zulip_user_id=microsoft_teams_user_id_to_zulip_user_id,
    )

    return (teams_metadata, team_id_to_zulip_recipient_id)


def convert_users(
    realm: dict[str, Any],
    realm_id: int,
    users_data_dir: str,
    timestamp: int,
) -> MicrosoftTeamsUserIdToZulipUserIdT:
    zerver_userprofile: list[ZerverFieldsT] = []
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT = defaultdict(int)
    found_emails: dict[str, int] = {}
    users_list: list[MicrosoftTeamsFieldsT] = get_data_file(
        os.path.join(users_data_dir, "usersList.json")
    )
    logging.info("######### IMPORTING USERS STARTED #########\n")
    for user in users_list:
        microsoft_teams_user_id = user["Id"]
        microsoft_teams_user_full_name = user["DisplayName"]
        zulip_user_id = NEXT_ID("user")

        # TODO: The user email is probably tied to the Microsoft Teams
        # tenant, we might not want to use the same email when converting
        # them to Zulip user accounts.
        microsoft_teams_user_email: str | None = (
            user["Mail"] if user["Mail"] else user["DisplayName"]
        )
        if microsoft_teams_user_email is None:
            raise AssertionError(f"Could not find email address for Microsoft Teams user: {user}")
        found_emails[microsoft_teams_user_email.lower()] = zulip_user_id

        userprofile = UserProfile(
            full_name=microsoft_teams_user_full_name,
            # Deleted users won't be included in the export users list.
            is_active=True,
            is_mirror_dummy=False,
            id=zulip_user_id,
            email=microsoft_teams_user_email,
            delivery_email=microsoft_teams_user_email,
            # Avatars are not exported.
            avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
            # Microsoft Teams apps or integrations doesn't have user accounts.
            is_bot=False,
            # TODO: User roles aren't included in the export.
            role=UserProfile.ROLE_MEMBER,
            bot_type=None,
            date_joined=timestamp,
            timezone="",
            last_login=timestamp,
        )
        userprofile_dict: ZerverFieldsT = model_to_dict(userprofile)
        userprofile_dict["realm"] = realm_id
        zerver_userprofile.append(userprofile_dict)
        microsoft_teams_user_id_to_zulip_user_id[microsoft_teams_user_id] = zulip_user_id

        logging.info(
            "%s: %s -> %s",
            microsoft_teams_user_id,
            microsoft_teams_user_full_name,
            microsoft_teams_user_email,
        )

    validate_user_emails_for_import(list(found_emails))
    realm["zerver_userprofile"] = zerver_userprofile
    logging.info("######### IMPORTING USERS FINISHED #########\n")
    return microsoft_teams_user_id_to_zulip_user_id


def get_timestamp_from_message(message: MicrosoftTeamsFieldsT) -> float:
    return datetime.fromisoformat(message["CreatedDateTime"]).timestamp()


def get_microsoft_teams_sender_id_from_message(message: MicrosoftTeamsFieldsT) -> str:
    return message["From"]["User"]["Id"]


def process_messages(
    added_teams: dict[str, TeamMetadata],
    channel_metadata: None | dict[str, ChannelMetadata],
    messages: list[MicrosoftTeamsFieldsT],
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
    realm_id: int,
    subscriber_map: dict[int, list[int]],
) -> None:
    # Build subscription list
    # Import messages
    zerver_usermessage: list[ZerverFieldsT] = []
    zerver_messages: list[ZerverFieldsT] = []
    total_user_messages = 0
    total_skipped_user_messages = 0

    for message in messages:
        print(message)
        message_content_type = message["Body"]["ContentType"]
        if message_content_type == "html":
            try:
                content = convert_html_to_text(message["Body"]["Content"])
            except Exception:  # nocoverage
                logging.warning(
                    "Error converting HTML to text for message: '%s'; continuing", content
                )
                logging.warning(str(message))
                continue
        else:
            logging.warning("Unable to convert this message content type: %s", message_content_type)
            continue

        # Determine message type -- private or channel.
        if message["ChannelIdentity"] is not None:
            if channel_metadata is None:
                raise AssertionError("Failed to build channel data.")
            topic_name = channel_metadata[message["ChannelIdentity"]["ChannelId"]]
            is_direct_message_type = False
            recipient_id = added_teams[message["ChannelIdentity"]["TeamId"]]
        else:
            if message["ChatId"] is not None:
                logging.warning("Unknown message format.")
                logging.warning(str(message))
            # TODO: Converting direct messages is not yet supported. Since
            # subscription list and recipient map of direct message conversations
            # are not listed, we have to manually build them as we iterate over
            # the user messages.
            continue

        microsoft_teams_sender_id: str = get_microsoft_teams_sender_id_from_message(message)
        if microsoft_teams_sender_id not in microsoft_teams_user_id_to_zulip_user_id:
            # TODO: Create is_mirror_dummy user for deactivated / deleted users. Those
            # users are not included in the exported user list but their message still
            # point to them as the sender.
            logging.warning("Unable to convert message from deleted user.")
            continue

        message_id = NEXT_ID("message")
        zulip_message = build_message(
            topic_name=topic_name,
            date_sent=get_timestamp_from_message(message),
            message_id=message_id,
            content=content,
            rendered_content=None,
            user_id=microsoft_teams_user_id_to_zulip_user_id[microsoft_teams_sender_id],
            recipient_id=recipient_id,
            realm_id=realm_id,
            is_channel_message=not is_direct_message_type,
            # TODO: Process links and attachments
            has_image=False,
            has_link=False,
            has_attachment=False,
            is_direct_message_type=is_direct_message_type,
        )
        zerver_messages.append(zulip_message)

        (num_created, num_skipped) = build_usermessages(
            zerver_usermessage=zerver_usermessage,
            subscriber_map=subscriber_map,
            recipient_id=recipient_id,
            mentioned_user_ids=[],
            message_id=message_id,
            is_private=is_direct_message_type,
            # TODO: Process long term idle users
            long_term_idle=(),
        )

        total_user_messages += num_created
        total_skipped_user_messages += num_skipped

        logging.debug(
            "Created %s UserMessages; deferred %s due to long-term idle",
            total_user_messages,
            total_skipped_user_messages,
        )


def read_message_data(path: str) -> list[MicrosoftTeamsFieldsT]:
    # Since all messages from a user is stored in a single JSON file, `get_data_file`
    # won't cut it if the file is large. Some sort of JSON data streaming / chunking
    # implementation is needed to support that.
    if os.path.getsize(path) >= 1073741824:
        file_name = os.path.basename(path)
        raise AssertionError(f"Message file is too large to be imported: {file_name}")
    user_messages: list[MicrosoftTeamsFieldsT] = get_data_file(path)
    return user_messages


def convert_messages(
    added_teams: dict[str, TeamMetadata],
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
    realm_id: int,
    realm: dict[str, Any],
    teams_data_dir: str,
    chunk_size: int = MESSAGE_BATCH_CHUNK_SIZE,
) -> None:
    """
    This function processes all message data in the export file. It specifically
    does the following:
    """
    microsoft_teams_channel_metadata: dict[str, ChannelMetadata] = {}
    teams_data_folders = os.listdir(teams_data_dir)
    subscriber_map = make_subscriber_map(
        zerver_subscription=realm["zerver_subscription"],
    )
    for team_id in teams_data_folders:
        team_data_folder = os.path.join(teams_data_dir, team_id)
        team_messages_file_path = os.path.join(team_data_folder, f"messages_{team_id}.json")

        # A Microsoft Teams' channel are Zulip's topic
        team_channels_list = get_data_file(
            os.path.join(team_data_folder, f"channels_{team_id}.json")
        )
        for channel in team_channels_list:
            microsoft_teams_channel_metadata[channel["Id"]] = ChannelMetadata(
                description=channel["Description"],
                display_name=channel["DisplayName"],
                is_favourite_by_default=channel["IsFavoriteByDefault"],
                is_archived=channel["IsArchived"],
                membership_type=channel["MembershipType"],
                team_id=team_id,
            )
        process_messages(
            added_teams=added_teams,
            channel_metadata=microsoft_teams_channel_metadata,
            messages=read_message_data(team_messages_file_path),
            microsoft_teams_user_id_to_zulip_user_id=microsoft_teams_user_id_to_zulip_user_id,
            subscriber_map=subscriber_map,
            realm_id=realm_id,
        )


def do_convert_directory(
    microsoft_teams_dir: str,
    output_dir: str,
    threads: int = 6,
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    if os.listdir(output_dir):
        raise Exception("Output directory should be empty!")
    users_data_dir = os.path.join(microsoft_teams_dir, "users")
    teams_data_dir = os.path.join(microsoft_teams_dir, "teams")
    if not os.path.isdir(users_data_dir):
        raise ValueError("Import does not have the layout we expect from a Microsoft Teams export!")

    realm_id = 0
    domain_name = SplitResult("", settings.EXTERNAL_HOST, "", "", "").hostname
    assert isinstance(domain_name, str)

    NOW = float(timezone_now().timestamp())
    zerver_realm: list[ZerverFieldsT] = build_zerver_realm(realm_id, "", NOW, "Microsoft Teams")
    realm = build_realm(zerver_realm, realm_id, domain_name, import_source="microsoft_teams")

    microsoft_teams_user_id_to_zulip_user_id = convert_users(
        realm=realm,
        realm_id=realm_id,
        users_data_dir=users_data_dir,
        timestamp=int(NOW),
    )

    (added_teams, team_id_to_zulip_recipient_id) = convert_teams_to_channels(
        realm=realm,
        realm_id=realm_id,
        teams_data_dir=teams_data_dir,
        microsoft_teams_user_id_to_zulip_user_id=microsoft_teams_user_id_to_zulip_user_id,
    )

    convert_messages(
        added_teams=added_teams,
        microsoft_teams_user_id_to_zulip_user_id=microsoft_teams_user_id_to_zulip_user_id,
        realm_id=realm_id,
        realm=realm,
        teams_data_dir=teams_data_dir,
    )

    create_converted_data_files(realm, output_dir, "/realm.json")
    # TODO:
    create_converted_data_files([], output_dir, "/emoji/records.json")
    create_converted_data_files([], output_dir, "/avatars/records.json")
    create_converted_data_files([], output_dir, "/uploads/records.json")
    attachment: dict[str, list[Any]] = {"zerver_attachment": []}
    create_converted_data_files(attachment, output_dir, "/attachment.json")
    create_converted_data_files([], output_dir, "/realm_icons/records.json")
    do_common_export_processes(output_dir)

    logging.info("######### DATA CONVERSION FINISHED #########\n")
    logging.info("Zulip data dump created at %s", output_dir)
