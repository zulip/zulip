import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias
from urllib.parse import SplitResult

import requests
from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    ZerverFieldsT,
    build_realm,
    build_recipient,
    build_stream,
    build_subscription,
    build_user_profile,
    build_zerver_realm,
    create_converted_data_files,
    validate_user_emails_for_import,
)
from zerver.data_import.sequencer import NEXT_ID
from zerver.data_import.slack import get_data_file
from zerver.lib.export import do_common_export_processes
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
            compiled_team_data["Description"] or "",
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
        if response.status_code == 403:
            result = response.json()
            error = result["error"]
            if error["code"] == "Authorization_RequestDenied":
                raise Exception("Make sure your Microsoft Graph API token has the necessary scope.")
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
    realm: dict[str, Any],
    realm_id: int,
    users_list: list[MicrosoftTeamsFieldsT],
    microsoft_teams_user_role_data: MicrosoftTeamsUserRoleData,
    timestamp: int,
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
            has_admin = True
        elif microsoft_teams_user_id in microsoft_teams_user_role_data.guest_user_ids:
            user_role = UserProfile.ROLE_GUEST
        else:
            user_role = UserProfile.ROLE_MEMBER

        # TODO: The user email is probably tied to the Microsoft Teams
        # tenant, we might not want to use the same email when converting
        # them to Zulip user accounts.
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
            is_mirror_dummy=False,
            realm_id=realm_id,
            short_name=user_full_name,
            timezone="UTC",
        )
        user_profile_dict: ZerverFieldsT = user_profile
        user_profile_dict["realm"] = realm_id
        zerver_user_profile.append(user_profile_dict)
        microsoft_teams_user_id_to_zulip_user_id[microsoft_teams_user_id] = zulip_user_id

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


def do_convert_directory(
    microsoft_teams_dir: str,
    output_dir: str,
    microsoft_graph_api_token: str,
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
    realm["zerver_stream"] = []
    realm["zerver_defaultstream"] = []
    realm["zerver_recipient"] = []
    realm["zerver_subscription"] = []

    microsoft_teams_user_id_to_zulip_user_id = convert_users(
        realm=realm,
        realm_id=realm_id,
        users_list=get_data_file(os.path.join(users_data_dir, "usersList.json")),
        microsoft_teams_user_role_data=get_user_roles(microsoft_graph_api_token),
        timestamp=int(NOW),
    )

    convert_teams_to_channels(
        realm=realm,
        realm_id=realm_id,
        teams_data_dir=teams_data_dir,
        microsoft_teams_user_id_to_zulip_user_id=microsoft_teams_user_id_to_zulip_user_id,
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
