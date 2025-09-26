import itertools
import logging
import os
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias
from urllib.parse import SplitResult

from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    ZerverFieldsT,
    build_realm,
    build_recipient,
    build_stream,
    build_subscription,
    build_zerver_realm,
    validate_user_emails_for_import,
)
from zerver.data_import.sequencer import NEXT_ID
from zerver.data_import.slack import get_data_file
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE
from zerver.models.recipients import Recipient
from zerver.models.users import UserProfile


@dataclass
class TeamsMetadata:
    description: str
    display_name: str
    visibility: Literal["public", "private"]
    is_archived: bool
    zulip_channel_id: int
    zulip_recipient_id: int


AddedTeamsT: TypeAlias = dict[str, TeamsMetadata]
TeamIdToZulipRecipientIdT: TypeAlias = dict[str, int]
MicrosoftTeamsUserIdToZulipUserIdT: TypeAlias = dict[str, int]
MicrosoftTeamsFieldsT: TypeAlias = dict[str, Any]


def convert_teams_to_channels(
    realm: dict[str, Any],
    realm_id: int,
    teams_data_dir: str,
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
) -> tuple[AddedTeamsT, TeamIdToZulipRecipientIdT]:
    # Compile teamsSettings.json and teamsList.json
    teams_list = get_data_file(os.path.join(teams_data_dir, "teamsList.json"))

    team_id_to_zulip_recipient_id: TeamIdToZulipRecipientIdT = {}
    teams_metadata: AddedTeamsT = {}
    team_data_folders = os.listdir(teams_data_dir)
    logging.info("######### IMPORTING TEAMS STARTED #########\n")

    raw_teams_subscription_data: dict[str, set[int]] = defaultdict(set)
    for team_id in team_data_folders:
        team_members_file_name = f"teamMembers_{team_id}.json"
        team_members_file_path = os.path.join(teams_data_dir, team_members_file_name)
        team_members: list[MicrosoftTeamsFieldsT] = get_data_file(team_members_file_path)
        for member in team_members:
            zulip_user_id = microsoft_teams_user_id_to_zulip_user_id[member["UserId"]]
            raw_teams_subscription_data[team_id].append(zulip_user_id)
    teams_settings = get_data_file(os.path.join(teams_data_dir, "teamsSettings.json"))
    teams_dict: dict[str, Any] = {team["Id"]: team for team in teams_list}

    for team_settings in teams_settings:
        team_id = team_settings.get("GroupId")

        if not team_id or team_id not in teams_dict:
            continue

        channel_id = NEXT_ID("channel")
        recipient_id = NEXT_ID("recipient")

        channel = build_stream(
            # Microsoft Teams export doesn't include teams creation
            # date.
            float(timezone_now().timestamp()),
            realm_id,
            teams_dict[team_id]["display_name"],
            teams_dict[team_id]["description"],
            channel_id,
            team_settings["IsArchived"],
            team_settings["Visibility"],
        )
        realm["zerver_stream"].append(channel)

        recipient = build_recipient(channel_id, recipient_id, Recipient.STREAM)
        realm["zerver_recipient"].append(recipient)
        team_id_to_zulip_recipient_id[team_id] = recipient_id
        for zulip_user_id in raw_teams_subscription_data[team_id]:
            build_subscription(
                recipient_id=recipient_id,
                user_id=zulip_user_id,
                subscription_id=NEXT_ID("subscription"),
            )
        teams_metadata[team_id] = TeamsMetadata(
            display_name=teams_dict[team_id]["display_name"],
            visibility=team_settings["Visibility"],
            is_archived=team_settings["IsArchived"],
            zulip_channel_id=channel_id,
            zulip_recipient_id=recipient_id,
        )
        return (teams_metadata, team_id_to_zulip_recipient_id)


def convert_users(
    realm_id: int, users_data_dir: str, timestamp: int
) -> tuple[list[ZerverFieldsT], MicrosoftTeamsUserIdToZulipUserIdT]:
    zerver_userprofile: list[ZerverFieldsT] = []
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT = []
    found_emails: list[str] = []
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
            # Deleted users won't be included in the
            is_active=True,
            is_mirror_dummy=False,
            id=zulip_user_id,
            email=microsoft_teams_user_email,
            delivery_email=microsoft_teams_user_email,
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
    logging.info("######### IMPORTING USERS FINISHED #########\n")
    return (
        zerver_userprofile,
        microsoft_teams_user_id_to_zulip_user_id,
    )


def process_messages(messages: list[MicrosoftTeamsFieldsT]):
    # Build subscription list
    # Import messages
    zerver_messages: list[ZerverFieldsT] = []
    for message in messages:
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
        zerver_messages.append(zulip_message)


def read_message_data(path: str, chunk_size: int) -> Iterator[MicrosoftTeamsFieldsT]:
    # Since all messages from a user is stored in a single JSON file, `get_data_file`
    # won't cut it if the file is large. Some sort of JSON data streaming / chunking
    # implementation is needed to support that.
    if os.path.getsize(path) >= 1073741824:
        file_name = os.path.basename(path)
        raise AssertionError(f"Message file is too large to be imported: {file_name}")
    user_messages: list[MicrosoftTeamsFieldsT] = get_data_file(path)

    return itertools.islice(user_messages, chunk_size)


def traverse_all_message_data(
    users_data_dir: str,
    teams_data_dir: str,
    teams_metadata: list[TeamsMetadata],
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
    chunk_size: int = MESSAGE_BATCH_CHUNK_SIZE,
) -> None:
    """
    This function processes all message data in the export file. It specifically
    does the following:
    """
    # Process user messages
    user_data_folders = os.listdir(users_data_dir)
    for microsoft_teams_user_id in user_data_folders:
        user_messages_data_folder = os.path.join(users_data_dir, microsoft_teams_user_id)
        user_messages_file_name = f"messages_{microsoft_teams_user_id}.json"
        user_messages_file_path = os.path.join(user_messages_data_folder, user_messages_file_name)
        for messages in read_message_data(user_messages_file_path, chunk_size):
            process_messages(messages)

    teams_data_folders = os.listdir(teams_data_dir)
    for team_id in teams_data_folders:
        teams_message_data_folder = os.path.join(teams_data_dir, team_id)
        team_messages_file_name = f"messages_{team_id}.json"
        team_messages_file_path = os.path.join(teams_message_data_folder, team_messages_file_name)
        for messages in read_message_data(team_messages_file_path, chunk_size):
            process_messages(messages)


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
    zerver_realm: list[ZerverFieldsT] = build_zerver_realm(realm_id, "", NOW, "Slack")
    realm = build_realm(zerver_realm, realm_id, domain_name, import_source="slack")

    (zerver_userprofile, microsoft_teams_user_id_to_zulip_user_id) = convert_users(
        users_data_dir, int(NOW)
    )

    (teams_metadata, team_id_to_zulip_recipient_id) = convert_teams_to_channels(
        realm, realm_id, teams_data_dir, microsoft_teams_user_id_to_zulip_user_id
    )

    traverse_all_message_data(users_data_dir, teams_data_dir)
