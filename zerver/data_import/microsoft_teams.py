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

MicrosoftTeamsUserIdToZulipUserIdT: TypeAlias = dict[str, int]
MicrosoftTeamsFieldsT: TypeAlias = dict[str, Any]


@dataclass
class MicrosoftTeamsUserRoleData:
    global_administrator_user_ids: set[str]
    guest_user_ids: set[str]


@dataclass
class ODataQueryParameter:
    # This is used to compute a request's OData query. It specifies the
    # amount, type, and order of the data returned for the resource
    # identified by the URL.
    # https://learn.microsoft.com/en-us/graph/query-parameters?tabs=http
    parameter: Literal["$filter", "$search", "$select", "$top"]
    expression: str


MICROSOFT_GRAPH_API_URL = "https://graph.microsoft.com/v1.0{endpoint}"


def get_microsoft_graph_api_data(
    api_url: str,
    odata_parameters: list[ODataQueryParameter] | None = None,
    **kwargs: Any,
) -> Any:
    if not kwargs.get("token"):
        raise AssertionError("Microsoft authorization token missing in kwargs")
    token = kwargs.pop("token")
    accumulated_result = []
    parameters = {}
    if odata_parameters is not None:
        for parameter in odata_parameters:
            assert parameter.parameter not in parameters
            parameters[parameter.parameter] = parameter.expression

    # If a request is paginated, "@odata.nextLink" will be included in the response,
    # it points to the next page of result. Even if the `$top` query is not specified,
    # depending on the endpoint and the result size, it may be paged by the server.
    # https://learn.microsoft.com/en-us/graph/paging?tabs=http#server-side-paging
    next_link: str | None = api_url
    while next_link is not None:
        response = requests.get(
            next_link, headers={"Authorization": f"Bearer {token}"}, params=parameters
        )

        if response.status_code != requests.codes.ok:
            logging.info("HTTP error: %s, Response: %s", response.status_code, response.text)
            raise Exception("HTTP error accessing the Microsoft Graph API.")

        response_data = response.json()
        accumulated_result.extend(response_data["value"])
        next_link = response_data.get("@odata.nextLink")

        # Don't apply initial request's parameters to subsequent paginated requests.
        if next_link is not None:
            parameters = {}

    return accumulated_result


def get_directory_roles(api_token: str) -> list[MicrosoftTeamsFieldsT]:
    """
    https://learn.microsoft.com/en-us/graph/api/directoryrole-list?view=graph-rest-1.0
    """
    return get_microsoft_graph_api_data(
        MICROSOFT_GRAPH_API_URL.format(endpoint="/directoryRoles"), token=api_token
    )


def get_users_with_directory_role_id(
    directory_role_id: str, api_token: str
) -> list[MicrosoftTeamsFieldsT]:
    """
    https://learn.microsoft.com/en-us/graph/api/directoryrole-list-members?view=graph-rest-1.0
    """
    return get_microsoft_graph_api_data(
        MICROSOFT_GRAPH_API_URL.format(endpoint=f"/directoryRoles/{directory_role_id}/members"),
        token=api_token,
    )


def get_user_ids_with_member_type(
    member_type: Literal["Member", "Guest"], api_token: str
) -> list[MicrosoftTeamsFieldsT]:
    """
    https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0
    """
    odata_parameter = [
        ODataQueryParameter(parameter="$filter", expression=f"userType eq '{member_type}'"),
        ODataQueryParameter(parameter="$select", expression="id"),
    ]
    return get_microsoft_graph_api_data(
        MICROSOFT_GRAPH_API_URL.format(endpoint="/users"),
        odata_parameter,
        token=api_token,
    )


def get_user_roles(api_token: str) -> MicrosoftTeamsUserRoleData:
    """
    User roles are not included in the export file, so this calls
    to Microsoft Graph API endpoints for that data. We mainly
    want to find out who the admins and guests are.
    """
    directory_roles: list[MicrosoftTeamsFieldsT] = get_directory_roles(api_token)
    global_administrator_role_id = None
    for role in directory_roles:
        if role["displayName"] == "Global Administrator":
            global_administrator_role_id = role["id"]

    if global_administrator_role_id is None:
        raise AssertionError("Could not find Microsoft Teams organization owners/administrators.")

    admin_users_data = get_users_with_directory_role_id(global_administrator_role_id, api_token)
    guest_users_data = get_user_ids_with_member_type("Guest", api_token)

    return MicrosoftTeamsUserRoleData(
        global_administrator_user_ids={user_data["id"] for user_data in admin_users_data},
        guest_user_ids={user_data["id"] for user_data in guest_users_data},
    )


def get_user_email(user: MicrosoftTeamsFieldsT) -> str:
    if user["Mail"]:
        return user["Mail"]
    else:
        raise AssertionError(f"Could not find email address for Microsoft Teams user {user}")


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
    has_owner = False

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

        microsoft_teams_user_email = get_user_email(user)

        zulip_user_id = NEXT_ID("user")
        found_emails[microsoft_teams_user_email.lower()] = zulip_user_id

        user_profile = build_user_profile(
            avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
            date_joined=timestamp,
            delivery_email=microsoft_teams_user_email,
            email=microsoft_teams_user_email,
            full_name=user_full_name,
            id=zulip_user_id,
            # This function only processes user data from `users/usersList.json` which only
            # lists active users -- no bot or deleted user accounts.
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

        if user_role == UserProfile.ROLE_REALM_OWNER:
            has_owner = True

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

    if not has_owner:
        logging.info("Converted realm has no owners!")

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

    convert_users(
        microsoft_teams_user_role_data=get_user_roles(microsoft_graph_api_token),
        realm=realm,
        realm_id=realm_id,
        timestamp=int(NOW),
        users_list=get_data_file(os.path.join(users_data_dir, "usersList.json")),
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
