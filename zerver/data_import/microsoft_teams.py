import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias
from urllib.parse import SplitResult

from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    ZerverFieldsT,
    build_realm,
    build_zerver_realm,
    create_converted_data_files,
    validate_user_emails_for_import,
)
from zerver.data_import.sequencer import NEXT_ID
from zerver.data_import.slack import get_data_file
from zerver.lib.export import do_common_export_processes
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


MicrosoftTeamsUserIdToZulipUserIdT: TypeAlias = dict[str, int]
MicrosoftTeamsFieldsT: TypeAlias = dict[str, Any]


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


def do_convert_directory(
    microsoft_teams_dir: str,
    output_dir: str,
    threads: int = 6,
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    if os.listdir(output_dir):
        raise Exception("Output directory should be empty!")
    users_data_dir = os.path.join(microsoft_teams_dir, "users")
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
        users_data_dir=users_data_dir,
        timestamp=int(NOW),
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
