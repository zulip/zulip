import logging
import os
import shutil
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from email.headerregistry import Address
from typing import Any, Literal, TypeAlias
from urllib.parse import SplitResult

import regex
import requests
from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    AttachmentRecordData,
    UploadFileRequest,
    UploadRecordData,
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
    get_attachment_path_and_content,
    get_data_file,
    make_subscriber_map,
    request_file_stream,
    validate_user_emails_for_import,
)
from zerver.data_import.sequencer import NEXT_ID
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE, do_common_export_processes
from zerver.lib.mime_types import bare_content_type
from zerver.lib.parallel import run_parallel_queue
from zerver.lib.partial import partial
from zerver.models.recipients import Recipient
from zerver.models.users import UserProfile


@dataclass
class TeamMetadata:
    """
    "team" is equivalent to a Zulip channel
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
    "channel" is equivalent to Zulip topics.
    """

    display_name: str
    is_favourite_by_default: bool
    is_archived: bool
    is_favorite_by_default: bool
    membership_type: str
    team_id: str


@dataclass
class MessageConversionResult:
    zerver_messages: list[ZerverFieldsT]
    zerver_usermessages: list[ZerverFieldsT]
    upload_records: list[UploadRecordData]


@dataclass
class AttachmentConversionResult:
    updated_content: str
    upload_records: list[UploadRecordData]


@dataclass
class ExportMessageAttachmentParameter:
    realm_id: int
    message_id: int
    sender_id: int
    upload_file_request: UploadFileRequest


AddedTeamsT: TypeAlias = dict[str, TeamMetadata]
TeamIdToZulipRecipientIdT: TypeAlias = dict[str, int]
MicrosoftTeamsUserIdToZulipUserIdT: TypeAlias = dict[str, int]
MicrosoftTeamsFieldsT: TypeAlias = dict[str, Any]

MICROSOFT_TEAMS_DEFAULT_ANNOUNCEMENTS_CHANNEL_NAME = "All company"


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
    team_id_to_zulip_subscriber_ids: dict[str, set[int]] = defaultdict(set)
    for team_id in team_data_folders:
        team_members_file_name = f"teamMembers_{team_id}.json"
        team_members_file_path = os.path.join(teams_data_dir, team_id, team_members_file_name)
        team_members: list[MicrosoftTeamsFieldsT] = get_data_file(team_members_file_path)

        for member in team_members:
            zulip_user_id = microsoft_teams_user_id_to_zulip_user_id[member["UserId"]]
            team_id_to_zulip_subscriber_ids[team_id].add(zulip_user_id)

    # Compile teamsSettings.json and teamsList.json and convert
    # teams to Zulip channels.
    teams_list = get_data_file(os.path.join(teams_data_dir, "teamsList.json"))
    teams_settings = get_data_file(os.path.join(teams_data_dir, "teamsSettings.json"))
    team_dict: dict[str, Any] = {team["GroupsId"]: team for team in teams_list}
    teams_metadata: AddedTeamsT = {}
    for team_settings in teams_settings:
        team_id = team_settings.get("Id")

        assert team_id and team_id in team_dict, (
            f"Team {team_id} appears in teamsSettings.json but not teamsList.json!"
        )

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

        for zulip_user_id in team_id_to_zulip_subscriber_ids[team_id]:
            sub = build_subscription(
                recipient_id=recipient_id,
                user_id=zulip_user_id,
                subscription_id=NEXT_ID("subscription"),
            )
            realm["zerver_subscription"].append(sub)

        # If the org uses the "All company" team, set it as the announcements channel.
        if (
            compiled_team_data["Name"] == MICROSOFT_TEAMS_DEFAULT_ANNOUNCEMENTS_CHANNEL_NAME
        ):  # nocoverage
            realm["zerver_realm"][0]["new_stream_announcements_stream"] = channel_id
            realm["zerver_realm"][0]["zulip_update_announcements_stream"] = channel_id
            realm["zerver_realm"][0]["signup_announcements_stream"] = channel_id
            logging.info("Using the channel 'All company' as default announcements channel.")

        teams_metadata[team_id] = TeamMetadata(
            description=compiled_team_data["Description"],
            display_name=compiled_team_data["DisplayName"],
            visibility=compiled_team_data["Visibility"],
            is_archived=compiled_team_data["IsArchived"],
            zulip_channel_id=channel_id,
            zulip_recipient_id=recipient_id,
        )

    return teams_metadata


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

# https://learn.microsoft.com/en-us/graph/api/chatmessagehostedcontent-get
GRAPH_API_HOSTED_CONTENT_REGEX = r"https://graph\.microsoft\.com/v1\.0/teams/[^/]+/channels/[^/]+/messages/[^/]+/hostedContents/[^/]+/\$value"


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


def create_is_mirror_dummy_user(
    microsoft_team_user_id: str,
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
    realm: dict[str, Any],
    realm_id: int,
    domain_name: str,
) -> None:
    zulip_user_id = NEXT_ID("user")
    user_full_name = f"Deleted Teams user {microsoft_team_user_id}"
    email = Address(username=microsoft_team_user_id, domain=domain_name).addr_spec
    user_profile_dict = build_user_profile(
        avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
        date_joined=int(timezone_now().timestamp()),
        delivery_email=email,
        email=email,
        full_name=user_full_name,
        id=zulip_user_id,
        is_active=False,
        role=UserProfile.ROLE_MEMBER,
        is_mirror_dummy=True,
        realm_id=realm_id,
        short_name=user_full_name,
        timezone="UTC",
    )
    realm["zerver_userprofile"].append(user_profile_dict)
    microsoft_teams_user_id_to_zulip_user_id[microsoft_team_user_id] = zulip_user_id

    recipient_id = NEXT_ID("recipient")
    subscription_id = NEXT_ID("subscription")
    recipient = build_recipient(zulip_user_id, recipient_id, Recipient.PERSONAL)
    sub = build_subscription(recipient_id, zulip_user_id, subscription_id)
    realm["zerver_recipient"].append(recipient)
    realm["zerver_subscription"].append(sub)


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

        user_profile_dict = build_user_profile(
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


def get_timestamp_from_message(message: MicrosoftTeamsFieldsT) -> float:
    return datetime.fromisoformat(message["CreatedDateTime"]).timestamp()


def get_microsoft_teams_sender_id_from_message(message: MicrosoftTeamsFieldsT) -> str:
    return message["From"]["User"]["Id"]


def is_microsoft_teams_event_message(message: MicrosoftTeamsFieldsT) -> bool:
    return message["MessageType"] == "unknownFutureValue" and message["From"] is None


def download_and_export_microsoft_teams_upload_file(
    attachment_records: list[AttachmentRecordData],
    output_dir: str,
    args: ExportMessageAttachmentParameter,
) -> None:
    upload_file_request = args.upload_file_request
    response = request_file_stream(
        upload_file_request.request_url,
        upload_file_request.params,
        upload_file_request.headers,
        **upload_file_request.kwargs,
    )

    # Don't add the file type extension here. The file path will be remapped
    # during import and must match the updated URL in the message content.
    # The actual file's content type will be included in its attachment
    # record.
    file_output_path = os.path.join(
        output_dir, "uploads", f"{upload_file_request.output_file_path_id}"
    )

    os.makedirs(os.path.dirname(file_output_path), exist_ok=True)
    with open(file_output_path, "wb") as upload_file:
        shutil.copyfileobj(response.raw, upload_file)

    raw_content_type = response.headers.get("Content-Type")
    assert raw_content_type is not None

    # Can't use build_attachment here since Django doesn't support parallel
    # connection to the db.
    attachment_records.append(
        AttachmentRecordData(
            content_type=bare_content_type(raw_content_type),
            create_time=os.path.getmtime(file_output_path),
            file_name=os.path.basename(file_output_path),
            id=NEXT_ID("attachment"),
            is_realm_public=True,
            messages=[args.message_id],
            owner=args.sender_id,
            path_id=upload_file_request.output_file_path_id,
            realm=args.realm_id,
            scheduled_messages=[],
            size=os.path.getsize(file_output_path),
        )
    )


def process_hosted_content_attachments(
    content: str,
    do_download_and_export_upload_file: Callable[[ExportMessageAttachmentParameter], None],
    is_direct_message_type: bool,
    microsoft_graph_api_token: str,
    realm_id: int,
    teams_message_id: str,
    zulip_message_id: int,
    zulip_user_id: int,
) -> AttachmentConversionResult:
    """
    "Hosted contents" are message file attachments that can be fetched straight
    from Microsoft Graph API.

    https://learn.microsoft.com/en-us/graph/api/chatmessagehostedcontent-get
    """
    upload_records: list[UploadRecordData] = []

    def export_file_and_get_zulip_url(match: regex.Match[str]) -> str:
        # Hosted content attachments don't have a user-specified filename.
        attachment_data = get_attachment_path_and_content("", teams_message_id, realm_id)

        upload_records.append(
            UploadRecordData(
                content_type=None,
                last_modified=float(timezone_now().timestamp()),
                path=attachment_data.path_id,
                realm_id=realm_id,
                s3_path=attachment_data.path_id,
                size=0,
                user_profile_id=zulip_user_id,
            )
        )

        do_download_and_export_upload_file(
            ExportMessageAttachmentParameter(
                realm_id=realm_id,
                message_id=zulip_message_id,
                sender_id=zulip_user_id,
                upload_file_request=UploadFileRequest(
                    output_file_path_id=attachment_data.path_id,
                    request_url=match.group(),
                    params=None,
                    headers={"Authorization": f"Bearer {microsoft_graph_api_token}"},
                    kwargs={},
                ),
            )
        )
        return attachment_data.url

    if is_direct_message_type:
        # TODO: hosted content URL for private chats have a different format, we
        # can process it once we support converting direct messages.
        return AttachmentConversionResult(updated_content=content, upload_records=upload_records)
    else:
        updated_content = regex.sub(
            GRAPH_API_HOSTED_CONTENT_REGEX,
            export_file_and_get_zulip_url,
            content,
        )
        return AttachmentConversionResult(
            updated_content=updated_content,
            upload_records=upload_records,
        )


def process_messages(
    added_teams: dict[str, TeamMetadata],
    channel_metadata: None | dict[str, ChannelMetadata],
    do_download_and_export_upload_file: Callable[[ExportMessageAttachmentParameter], None],
    domain_name: str,
    messages: list[MicrosoftTeamsFieldsT],
    microsoft_graph_api_token: str,
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
    realm: dict[str, Any],
    realm_id: int,
    subscriber_map: dict[int, set[int]],
) -> MessageConversionResult:
    zerver_usermessage: list[ZerverFieldsT] = []
    zerver_messages: list[ZerverFieldsT] = []
    upload_records: list[UploadRecordData] = []

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
            current_channel = channel_metadata[message["ChannelIdentity"]["ChannelId"]]
            if current_channel.membership_type == "private":
                # Don't include private channel messages.
                continue
            topic_name = current_channel.display_name
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
            create_is_mirror_dummy_user(
                microsoft_teams_sender_id,
                microsoft_teams_user_id_to_zulip_user_id,
                realm,
                realm_id,
                domain_name,
            )

        message_id = NEXT_ID("message")
        user_id = microsoft_teams_user_id_to_zulip_user_id[microsoft_teams_sender_id]
        attachment_result = process_hosted_content_attachments(
            content=content,
            do_download_and_export_upload_file=do_download_and_export_upload_file,
            is_direct_message_type=is_direct_message_type,
            microsoft_graph_api_token=microsoft_graph_api_token,
            realm_id=realm_id,
            teams_message_id=message["Id"],
            zulip_user_id=user_id,
            zulip_message_id=message_id,
        )
        content = attachment_result.updated_content
        upload_records += attachment_result.upload_records

        if upload_records != []:
            has_image = True
            has_link = True
            has_attachments = True
        else:
            has_image = False
            has_link = False
            has_attachments = False

        zulip_message = build_message(
            topic_name=topic_name,
            date_sent=get_timestamp_from_message(message),
            message_id=message_id,
            content=content,
            rendered_content=None,
            user_id=user_id,
            recipient_id=recipient_id,
            realm_id=realm_id,
            is_channel_message=not is_direct_message_type,
            has_image=has_image,
            has_link=has_link,
            has_attachment=has_attachments,
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
        )

        logging.debug(
            "Created %s UserMessages; deferred %s due to long-term idle",
            num_created,
            num_skipped,
        )

    return MessageConversionResult(
        zerver_messages=zerver_messages,
        zerver_usermessages=zerver_usermessage,
        upload_records=upload_records,
    )


def get_batched_export_message_data(
    message_data_paths: list[str], chunk_size: int = MESSAGE_BATCH_CHUNK_SIZE
) -> Iterable[list[MicrosoftTeamsFieldsT]]:
    batched_messages: list[MicrosoftTeamsFieldsT] = []
    for path in message_data_paths:
        messages = get_data_file(path)
        # Teams export tool doesn't sort messages in chronological order.
        # Sort Microsoft Teams messages by their ID, which is their date
        # sent in unix time.
        for message in sorted(messages, key=lambda m: int(m["Id"])):
            if len(batched_messages) == chunk_size:
                yield batched_messages
                batched_messages.clear()
            batched_messages.append(message)

    if batched_messages:
        yield batched_messages


def convert_messages(
    added_teams: dict[str, TeamMetadata],
    domain_name: str,
    microsoft_graph_api_token: str,
    microsoft_teams_user_id_to_zulip_user_id: MicrosoftTeamsUserIdToZulipUserIdT,
    output_dir: str,
    processes: int,
    realm_id: int,
    realm: dict[str, Any],
    teams_data_dir: str,
    chunk_size: int = MESSAGE_BATCH_CHUNK_SIZE,
) -> tuple[list[UploadRecordData], list[AttachmentRecordData]]:
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
                is_favorite_by_default=team_channel["IsFavoriteByDefault"],
                membership_type=team_channel["MembershipType"],
                team_id=team_id,
            )
    total_attachment_records: list[AttachmentRecordData] = []
    total_upload_records: list[UploadRecordData] = []
    with run_parallel_queue(
        partial(
            download_and_export_microsoft_teams_upload_file, total_attachment_records, output_dir
        ),
        processes,
        catch=True,
        report_every=100,
        report=lambda count: logging.info("Downloaded %s attachments", count),
    ) as do_download_and_export_upload_file:
        dump_file_id = 1
        for message_chunk in get_batched_export_message_data(message_file_paths, chunk_size):
            conversion_result = process_messages(
                added_teams=added_teams,
                channel_metadata=microsoft_teams_channel_metadata,
                do_download_and_export_upload_file=do_download_and_export_upload_file,
                domain_name=domain_name,
                messages=message_chunk,
                microsoft_graph_api_token=microsoft_graph_api_token,
                microsoft_teams_user_id_to_zulip_user_id=microsoft_teams_user_id_to_zulip_user_id,
                realm=realm,
                realm_id=realm_id,
                subscriber_map=subscriber_map,
            )
            total_upload_records += conversion_result.upload_records
            create_converted_data_files(
                dict(
                    zerver_message=conversion_result.zerver_messages,
                    zerver_usermessage=conversion_result.zerver_usermessages,
                ),
                output_dir,
                f"/messages-{dump_file_id:06}.json",
            )
            dump_file_id += 1
    return (total_upload_records, total_attachment_records)


def do_convert_directory(
    microsoft_teams_dir: str,
    output_dir: str,
    microsoft_graph_api_token: str,
    processes: int = 6,
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

    upload_records, attachment_records = convert_messages(
        added_teams=added_teams,
        domain_name=domain_name,
        microsoft_graph_api_token=microsoft_graph_api_token,
        microsoft_teams_user_id_to_zulip_user_id=microsoft_teams_user_id_to_zulip_user_id,
        output_dir=output_dir,
        processes=processes,
        realm_id=realm_id,
        realm=realm,
        teams_data_dir=teams_data_dir,
    )

    create_converted_data_files(realm, output_dir, "/realm.json")
    create_converted_data_files(upload_records, output_dir, "/uploads/records.json")
    attachment: dict[str, list[Any]] = {"zerver_attachment": attachment_records}
    create_converted_data_files(attachment, output_dir, "/attachment.json")
    # TODO:
    create_converted_data_files([], output_dir, "/emoji/records.json")
    create_converted_data_files([], output_dir, "/avatars/records.json")
    create_converted_data_files([], output_dir, "/realm_icons/records.json")
    do_common_export_processes(output_dir)

    logging.info("######### DATA CONVERSION FINISHED #########\n")
    logging.info("Zulip data dump created at %s", output_dir)
