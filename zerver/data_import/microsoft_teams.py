import logging
import os
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias
from urllib.parse import SplitResult

import requests
from dateutil import parser
from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    ZerverFieldsT,
    build_message,
    build_realm,
    build_recipient,
    build_stream,
    build_subscription,
    build_user_profile,
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

    display_name: str
    is_favourite_by_default: bool
    is_archived: bool
    is_favorite_by_deafult: bool
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
    # regardless of whether the organization actually has or uses it.
    # In the chance where it is used, we'll use that as the default
    # announcement channels. If not, create an artificial one.
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
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
    realm: dict[str, Any],
    realm_id: int,
    teams_data_dir: str,
) -> AddedTeamsT:
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

    # Compile teamsSettings.json and teamsList.json and convert
    # teams to Zulip channels.
    teams_list = get_data_file(os.path.join(teams_data_dir, "teamsList.json"))
    teams_settings = get_data_file(os.path.join(teams_data_dir, "teamsSettings.json"))
    team_dict: dict[str, Any] = {team["GroupsId"]: team for team in teams_list}
    default_announcement_channel_id: int | None = None
    teams_metadata: AddedTeamsT = {}
    for team_settings in teams_settings:
        team_id = team_settings.get("Id")

        if not team_id or team_id not in team_dict:  # nocoverage
            # Normally, each team has corresponding data in both teamsList.json and
            # teamsSettings.json, so this is likely a very rare edge case.
            logging.info("A Team settings data is not in the list of exported teams: ")
            logging.info(str(team_settings))
            continue

        compiled_team_data: MicrosoftTeamsFieldsT = {**team_dict[team_id], **team_settings}

        channel_id = NEXT_ID("channel")
        recipient_id = NEXT_ID("recipient")

        channel = build_stream(
            # Microsoft Teams export doesn't include teams creation date.
            date_created=float(timezone_now().timestamp()),
            realm_id=realm_id,
            name=compiled_team_data["Name"],
            description=compiled_team_data["Description"] or "",
            stream_id=channel_id,
            deactivated=compiled_team_data["IsArchived"],
            invite_only=compiled_team_data["Visibility"] == "private",
        )
        realm["zerver_stream"].append(channel)

        recipient = build_recipient(channel_id, recipient_id, Recipient.STREAM)
        realm["zerver_recipient"].append(recipient)

        for zulip_user_id in raw_teams_subscription_data[team_id]:
            sub = build_subscription(
                recipient_id=recipient_id,
                user_id=zulip_user_id,
                subscription_id=NEXT_ID("subscription"),
            )
            realm["zerver_subscription"].append(sub)

        if compiled_team_data["Name"] == MICROSOFT_TEAMS_DEFAULT_ANNOUNCEMENTS_CHANNEL_NAME:
            default_announcement_channel_id = channel_id  # nocoverage

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

    return teams_metadata


@dataclass
class MicrosoftTeamsUserRoleData:
    global_administrator_user_ids: set[str]
    guest_user_ids: set[str]


@dataclass
class ODataQueryParameter:
    parameter: Literal["$filter", "$search", "$select"]
    expression: str


def get_microsoft_graph_api_data(
    endpoint: str,
    odata_parameters: list[ODataQueryParameter] | None = None,
    **kwargs: Any,
) -> Any:
    if not kwargs.get("token"):
        raise AssertionError("Microsoft authorization token missing in kwargs")
    token = kwargs.pop("token")
    api_url = f"https://graph.microsoft.com/v1.0{endpoint}"

    parameters = {}
    if odata_parameters is not None:
        for parameter in odata_parameters:
            assert parameter.parameter not in parameters
            parameters[parameter.parameter] = parameter.expression

    response = requests.get(
        api_url, headers={"Authorization": f"Bearer {token}"}, params=parameters
    )

    if response.status_code != requests.codes.ok:
        logging.info("HTTP error: %s, Response: %s", response.status_code, response.text)
        raise Exception("HTTP error accessing the Microsoft Graph API.")
    return response.json()


def get_users_with_directory_role_id(
    directory_role_id: str, api_token: str
) -> list[MicrosoftTeamsFieldsT]:
    result = get_microsoft_graph_api_data(
        f"/directoryRoles/{directory_role_id}/members", token=api_token
    )
    return result["value"]


def get_users_with_member_type(
    member_type: Literal["Member", "Guest"], api_token: str
) -> list[MicrosoftTeamsFieldsT]:
    odata_parameter = [
        ODataQueryParameter(parameter="$filter", expression=f"userType eq '{member_type}'"),
    ]
    result = get_microsoft_graph_api_data(
        "/users",
        odata_parameter,
        token=api_token,
    )
    return result["value"]


def get_user_roles(api_token: str) -> MicrosoftTeamsUserRoleData:
    """
    User roles are not included in the export file, so this calls
    to Microsoft Graph API endpoints for that data. We mainly
    want to find out who the admins and guests are.
    """
    result = get_microsoft_graph_api_data("/directoryRoles", token=api_token)
    directory_roles: list[MicrosoftTeamsFieldsT] = result["value"]
    global_administrator_role_id = None
    for role in directory_roles:
        if role["displayName"] == "Global Administrator":
            global_administrator_role_id = role["id"]

    if global_administrator_role_id is None:
        raise AssertionError("Could not find Microsoft Teams organization owners/administrators.")

    admin_users_data = get_users_with_directory_role_id(global_administrator_role_id, api_token)
    guest_users_data = get_users_with_member_type("Guest", api_token)

    return MicrosoftTeamsUserRoleData(
        global_administrator_user_ids={user_data["id"] for user_data in admin_users_data},
        guest_user_ids={user_data["id"] for user_data in guest_users_data},
    )


def convert_users(
    microsoft_teams_user_role_data: MicrosoftTeamsUserRoleData,
    realm: dict[str, Any],
    realm_id: int,
    timestamp: int,
    users_list: list[MicrosoftTeamsFieldsT],
) -> MicrosoftTeamsUserIdToZulipUserIdT:
    zerver_user_profile: list[ZerverFieldsT] = []
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT = defaultdict(int)
    found_emails: dict[str, int] = {}
    has_admin = False

    logging.info("######### IMPORTING USERS STARTED #########\n")
    for user in users_list:
        microsoft_teams_user_id = user["Id"]
        user_full_name = user["DisplayName"]

        if microsoft_teams_user_id in microsoft_teams_user_role_data.global_administrator_user_ids:
            user_role = UserProfile.ROLE_REALM_OWNER
        elif microsoft_teams_user_id in microsoft_teams_user_role_data.guest_user_ids:
            user_role = UserProfile.ROLE_GUEST
        else:
            user_role = UserProfile.ROLE_MEMBER

        microsoft_teams_user_email: str | None = (
            user["Mail"] if user["Mail"] else user["UserPrincipalName"]
        )
        if microsoft_teams_user_email is None:
            raise AssertionError(f"Could not find email address for a Microsoft Teams user: {user}")

        zulip_user_id = NEXT_ID("user")
        found_emails[microsoft_teams_user_email.lower()] = zulip_user_id

        user_profile = build_user_profile(
            avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
            date_joined=timestamp,
            delivery_email=microsoft_teams_user_email,
            email=microsoft_teams_user_email,
            full_name=user_full_name,
            id=zulip_user_id,
            is_active=True,
            role=user_role,
            is_mirror_dummy=True,
            realm_id=realm_id,
            short_name=user_full_name,
            timezone="UTC",
        )

        user_profile_dict: ZerverFieldsT = user_profile
        user_profile_dict["realm"] = realm_id
        zerver_user_profile.append(user_profile_dict)
        microsoft_teams_user_id_to_zulip_user_id[microsoft_teams_user_id] = zulip_user_id

        if user_role == UserProfile.ROLE_REALM_OWNER:
            has_admin = True

        recipient_id = NEXT_ID("recipient")
        subscription_id = NEXT_ID("subscription")
        recipient = build_recipient(zulip_user_id, recipient_id, Recipient.PERSONAL)
        sub = build_subscription(recipient_id, zulip_user_id, subscription_id)
        realm["zerver_recipient"].append(recipient)
        realm["zerver_subscription"].append(sub)

        logging.info(
            "%s: %s -> %s",
            microsoft_teams_user_id,
            user_full_name,
            microsoft_teams_user_email,
        )

    if not has_admin:
        logging.info("Converted realm has no administrators!")

    validate_user_emails_for_import(list(found_emails))
    realm["zerver_userprofile"] = zerver_user_profile
    logging.info("######### IMPORTING USERS FINISHED #########\n")
    return microsoft_teams_user_id_to_zulip_user_id


def get_timestamp_from_message(message: MicrosoftTeamsFieldsT) -> float:
    # We should update this to use datetime.fromisoformat() once we upgrade
    # to Python >=3.11.
    # https://github.com/python/cpython/issues/95221
    return parser.isoparse(message["CreatedDateTime"]).timestamp()


def get_microsoft_teams_sender_id_from_message(message: MicrosoftTeamsFieldsT) -> str:
    return message["From"]["User"]["Id"]


def is_microsoft_teams_event_message(message: MicrosoftTeamsFieldsT) -> bool:
    return message["MessageType"] == "unknownFutureValue" and message["From"] is None


def process_messages(
    added_teams: dict[str, TeamMetadata],
    channel_metadata: None | dict[str, ChannelMetadata],
    is_private: bool,
    messages: list[MicrosoftTeamsFieldsT],
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
    realm_id: int,
    subscriber_map: dict[int, set[int]],
) -> tuple[list[ZerverFieldsT], list[ZerverFieldsT]]:
    zerver_usermessage: list[ZerverFieldsT] = []
    zerver_messages: list[ZerverFieldsT] = []
    total_user_messages = 0
    total_skipped_user_messages = 0
    skipped_deleted_users_message = 0

    for message in messages:
        if is_microsoft_teams_event_message(message):
            continue

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
        else:  # nocoverage
            logging.warning("Unable to convert this message content type: %s", message_content_type)
            continue

        # Determine message type, private or channel.
        if message["ChannelIdentity"] is not None:
            if channel_metadata is None:
                raise AssertionError("Failed to build channel data.")
            topic_name = channel_metadata[message["ChannelIdentity"]["ChannelId"]].display_name
            is_direct_message_type = False
            recipient_id = added_teams[message["ChannelIdentity"]["TeamId"]].zulip_recipient_id
        else:  # nocoverage
            assert message["ChatId"] is not None
            # TODO: Converting direct messages is not yet supported. Since
            # subscription list and recipient map of direct message conversations
            # are not listed, we have to manually build them as we iterate over
            # the user messages.
            continue

        microsoft_teams_sender_id: str = get_microsoft_teams_sender_id_from_message(message)

        if microsoft_teams_sender_id not in microsoft_teams_user_id_to_zulip_user_id:
            # TODO: Deleted users are not included in the exported user list but their
            # messages are still exported and point to the deactivated user as the sender.
            skipped_deleted_users_message += 1
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
        )

        total_user_messages += num_created
        total_skipped_user_messages += num_skipped

        logging.debug(
            "Created %s UserMessages; deferred %s due to long-term idle",
            total_user_messages,
            total_skipped_user_messages,
        )

    logging.info(
        "Unable to convert %s message(s) from deleted users.",
        skipped_deleted_users_message,
    )

    return (
        zerver_messages,
        zerver_usermessage,
    )


def get_batched_export_message_data(
    message_data_paths: list[str], chunk_size: int = MESSAGE_BATCH_CHUNK_SIZE
) -> Iterable[list[MicrosoftTeamsFieldsT]]:
    batched_messages: list[MicrosoftTeamsFieldsT] = []
    for path in message_data_paths:
        messages = get_data_file(path)
        for message in messages:
            if len(batched_messages) == chunk_size:
                yield batched_messages
                batched_messages.clear()
            batched_messages.append(message)

    if batched_messages:
        yield batched_messages


def convert_messages(
    added_teams: dict[str, TeamMetadata],
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
    output_dir: str,
    realm_id: int,
    realm: dict[str, Any],
    teams_data_dir: str,
    chunk_size: int = MESSAGE_BATCH_CHUNK_SIZE,
) -> None:
    microsoft_teams_channel_metadata: dict[str, ChannelMetadata] = {}
    subscriber_map = make_subscriber_map(
        zerver_subscription=realm["zerver_subscription"],
    )
    team_data_folders = []
    for f in os.listdir(teams_data_dir):
        path = os.path.join(teams_data_dir, f)
        if os.path.isdir(path):
            team_data_folders.append(f)

    message_file_paths = []
    for team_id in team_data_folders:
        team_data_folder = os.path.join(teams_data_dir, team_id)
        team_messages_file_path = os.path.join(team_data_folder, f"messages_{team_id}.json")
        message_file_paths.append(team_messages_file_path)

        team_channels_list = get_data_file(
            os.path.join(team_data_folder, f"channels_{team_id}.json")
        )
        for team_channel in team_channels_list:
            microsoft_teams_channel_metadata[team_channel["Id"]] = ChannelMetadata(
                display_name=team_channel["DisplayName"],
                is_favourite_by_default=team_channel["IsFavoriteByDefault"],
                is_archived=team_channel["IsArchived"],
                is_favorite_by_deafult=team_channel["IsFavoriteByDefault"],
                membership_type=team_channel["MembershipType"],
                team_id=team_id,
            )

    dump_file_id = 1
    for raw_message_chunk in get_batched_export_message_data(message_file_paths, chunk_size):
        # Sort Microsoft Teams messages by their ID, which is their date sent in unix time.
        sorted_message_chunk = sorted(raw_message_chunk, key=lambda m: int(m["Id"]))
        (zerver_messages, zerver_usermessage) = process_messages(
            added_teams=added_teams,
            channel_metadata=microsoft_teams_channel_metadata,
            is_private=False,
            messages=sorted_message_chunk,
            microsoft_teams_user_id_to_zulip_user_id=microsoft_teams_user_id_to_zulip_user_id,
            subscriber_map=subscriber_map,
            realm_id=realm_id,
        )

        create_converted_data_files(
            dict(zerver_message=zerver_messages, zerver_usermessage=zerver_usermessage),
            output_dir,
            f"/messages-{dump_file_id:06}.json",
        )
        dump_file_id += 1


def do_convert_directory(
    microsoft_teams_dir: str,
    output_dir: str,
    microsoft_graph_api_token: str,
    threads: int = 6,
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    if os.listdir(output_dir):  # nocoverage
        raise Exception("Output directory should be empty!")
    users_data_dir = os.path.join(microsoft_teams_dir, "users")
    if not os.path.isdir(users_data_dir):  # nocoverage
        raise ValueError("Import does not have the layout we expect from a Microsoft Teams export!")

    realm_id = 0
    domain_name = SplitResult("", settings.EXTERNAL_HOST, "", "", "").hostname
    assert isinstance(domain_name, str)

    NOW = float(timezone_now().timestamp())
    zerver_realm: list[ZerverFieldsT] = build_zerver_realm(realm_id, "", NOW, "Microsoft Teams")
    realm = build_realm(zerver_realm, realm_id, domain_name, import_source="microsoft_teams")
    realm["zerver_stream"] = []
    realm["zerver_defaultstream"] = []
    realm["zerver_recipient"] = []
    realm["zerver_subscription"] = []

    microsoft_teams_user_id_to_zulip_user_id = convert_users(
        microsoft_teams_user_role_data=get_user_roles(microsoft_graph_api_token),
        realm=realm,
        realm_id=realm_id,
        timestamp=int(NOW),
        users_list=get_data_file(os.path.join(users_data_dir, "usersList.json")),
    )

    teams_data_dir = os.path.join(microsoft_teams_dir, "teams")

    added_teams = convert_teams_to_channels(
        microsoft_teams_user_id_to_zulip_user_id=microsoft_teams_user_id_to_zulip_user_id,
        realm=realm,
        realm_id=realm_id,
        teams_data_dir=teams_data_dir,
    )

    convert_messages(
        added_teams=added_teams,
        microsoft_teams_user_id_to_zulip_user_id=microsoft_teams_user_id_to_zulip_user_id,
        output_dir=output_dir,
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
