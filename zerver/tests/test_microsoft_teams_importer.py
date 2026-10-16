import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from functools import cached_property
from typing import Any, TypeAlias
from urllib.parse import parse_qs, urlsplit

import orjson
import responses
from bs4 import BeautifulSoup
from django.test import override_settings
from django.utils.timezone import now as timezone_now
from requests import PreparedRequest
from typing_extensions import override

from zerver.data_import.import_util import AttachmentRecordData, get_data_file
from zerver.data_import.microsoft_teams import (
    MICROSOFT_GRAPH_API_URL,
    ChannelMetadata,
    MicrosoftTeamsFieldsT,
    MicrosoftTeamsUserIdToZulipUserIdT,
    MicrosoftTeamsUserRoleData,
    ODataQueryParameter,
    convert_users,
    do_convert_directory,
    download_and_export_microsoft_teams_upload_file,
    get_batched_export_message_data,
    get_microsoft_graph_api_data,
    get_microsoft_teams_sender_id_from_message,
    get_timestamp_from_message,
    get_user_roles,
    is_microsoft_teams_event_message,
    process_hosted_content_attachments,
)
from zerver.data_import.microsoft_teams_message_conversion import (
    HOSTED_CONTENT_GRAPH_API_URL_REGEX,
    convert_microsoft_teams_html_to_markdown,
)
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE
from zerver.lib.partial import partial
from zerver.lib.test_classes import (
    ExpectedChannel,
    ExpectedMessage,
    ExpectedUser,
    ImporterContractTestBase,
    ZulipTestCase,
)
from zerver.lib.test_helpers import read_test_image_file
from zerver.lib.topic import messages_for_topic
from zerver.models.streams import Stream
from zerver.models.users import UserProfile

ResponseTuple: TypeAlias = tuple[int, dict[str, str], str]

EXPORTED_MICROSOFT_TEAMS_USER_EMAIL = dict(
    aaron="aaron@ZulipChat.onmicrosoft.com",
    alya="alya@ZulipChat.onmicrosoft.com",
    cordelia="cordelia@ZulipChat.onmicrosoft.com",
    guest="guest@example.com",
    pieter="pieterk@ZulipChat.onmicrosoft.com",
    zoe="zoe@ZulipChat.onmicrosoft.com",
)

EXPORTED_REALM_OWNER_EMAILS = [
    EXPORTED_MICROSOFT_TEAMS_USER_EMAIL["pieter"],
    EXPORTED_MICROSOFT_TEAMS_USER_EMAIL["alya"],
]

GUEST_USER_EMAILS = [EXPORTED_MICROSOFT_TEAMS_USER_EMAIL["guest"]]

MICROSOFT_TEAMS_EXPORT_USER_ROLE_DATA = MicrosoftTeamsUserRoleData(
    global_administrator_user_ids={
        "88cbf3c2-0810-4d32-aa19-863c12bf7be9",
        "3c6ee395-529d-4681-b5f7-582c707570f6",
    },
    guest_user_ids={"16741626-4cd8-46cc-bf36-42ecc2b5fdce"},
)

DELETED_MICROSOFT_TEAMS_USERS = ["9bd4aca7-99cf-4b1b-a16d-e25717dc9414"]

PRIVATE_MICROSOFT_TEAMS_CHANNELS = ["19:42c4944387224bf79bcad3cb6809a335@thread.tacv2"]

FAILED_HOSTED_CONTENT_DOWNLOAD_URL = "https://graph.microsoft.com/v1.0/teams/1d513e46-d8cd-41db-b84f-381fe5730794/channels/19:f0088fc2bb264dfe9a7a7924a23c7252@thread.tacv2/messages/1755003422344/hostedContents/aWQ9eF8wLXd1cy1kMi1iNGM5NjhiYmNhMDU1OWViYWFkMzdiMGUzMzBmMzY5MSx0eXBlPTEsdXJsPWh0dHBzOi8vdXMtYXBpLmFzbS5za3lwZS5jb20vdjEvb2JqZWN0cy8wLXd1cy1kMi1iNGM5NjhiYmNhMDU1OWViYWFkMzdiMGUzMzBmMzY5MS92aWV3cy9pbWdv/$value"

EXPORTED_MICROSOFT_TEAMS_TEAM_ID: dict[str, str] = {
    "Core team": "7c050abd-3cbb-448b-a9de-405f54cc14b2",
    "Community": "002145f2-eaba-4962-997d-6d841a9f50af",
    "Contributors": "2a00a70a-00f5-4da5-8618-8281194f0de0",
    "Feedback & support": "5e5f1988-3216-4ca0-83e9-18c04ecc7533",
    "Kandra Labs": "1d513e46-d8cd-41db-b84f-381fe5730794",
}


def get_exported_team_data(team_id: str) -> MicrosoftTeamsFieldsT:
    test_class = ZulipTestCase()
    team_list = json.loads(
        test_class.fixture_data(
            "teamsList.json",
            "microsoft_teams_fixtures/TeamsData_ZulipChat/teams",
        )
    )

    team_list_data = next(team_data for team_data in team_list if team_id == team_data["GroupsId"])
    team_settings = json.loads(
        test_class.fixture_data(
            "teamsSettings.json",
            "microsoft_teams_fixtures/TeamsData_ZulipChat/teams",
        )
    )
    team_settings_data = next(
        team_data for team_data in team_settings if team_data["Id"] == team_id
    )
    return {**team_list_data, **team_settings_data}


def get_exported_team_ids() -> list[str]:
    test_class = ZulipTestCase()
    team_settings = json.loads(
        test_class.fixture_data(
            "teamsSettings.json",
            "microsoft_teams_fixtures/TeamsData_ZulipChat/teams",
        )
    )
    return [team_data["Id"] for team_data in team_settings]


def get_exported_team_subscription_list(team_id: str) -> list[MicrosoftTeamsFieldsT]:
    test_class = ZulipTestCase()
    return json.loads(
        test_class.fixture_data(
            f"teamMembers_{team_id}.json",
            f"microsoft_teams_fixtures/TeamsData_ZulipChat/teams/{team_id}",
        )
    )


def get_exported_team_message_list(team_id: str) -> list[MicrosoftTeamsFieldsT]:
    test_class = ZulipTestCase()
    return json.loads(
        test_class.fixture_data(
            f"messages_{team_id}.json",
            f"microsoft_teams_fixtures/TeamsData_ZulipChat/teams/{team_id}",
        )
    )


def get_exported_team_channel_metadata(team_id: str) -> dict[str, ChannelMetadata]:
    test_class = ZulipTestCase()
    microsoft_teams_channel_metadata = {}
    team_channels = json.loads(
        test_class.fixture_data(
            f"channels_{team_id}.json",
            f"microsoft_teams_fixtures/TeamsData_ZulipChat/teams/{team_id}",
        )
    )

    for team_channel in team_channels:
        microsoft_teams_channel_metadata[team_channel["Id"]] = ChannelMetadata(
            display_name=team_channel["DisplayName"],
            is_favourite_by_default=team_channel["IsFavoriteByDefault"],
            is_archived=team_channel["IsArchived"],
            is_favorite_by_default=team_channel["IsFavoriteByDefault"],
            membership_type=team_channel["MembershipType"],
            team_id=team_id,
        )
    return microsoft_teams_channel_metadata


@dataclass
class ConvertibleExportedMessage:
    message: MicrosoftTeamsFieldsT
    team_name: str
    microsoft_teams_channel: ChannelMetadata


def graph_api_users_callback(request: PreparedRequest) -> ResponseTuple:
    assert request.url is not None
    parsed = urlsplit(request.url)
    query_params = parse_qs(parsed.query)

    if query_params.get("$filter") == ["userType eq 'Guest'"]:
        test_class = ZulipTestCase()
        body = test_class.fixture_data(
            "users_guest.json",
            "microsoft_graph_api_response_fixtures",
        )
    else:
        raise AssertionError("There are no response fixture for this request.")

    # https://learn.microsoft.com/en-us/graph/query-parameters?tabs=http#select
    selected_fields = query_params.get("$select")
    if selected_fields:
        trimmed_values = []
        response = json.loads(body)
        for data in response["value"]:
            trimmed_data = {}
            for field in selected_fields:
                trimmed_data[field] = data[field]
            trimmed_values.append(trimmed_data)

        response["value"] = trimmed_values
        body = json.dumps(response)

    headers = {"Content-Type": "application/json"}
    return 200, headers, body


def add_microsoft_graph_api_responses(requests_mock: responses.RequestsMock) -> None:
    test_class = ZulipTestCase()
    requests_mock.add_callback(
        responses.GET,
        "https://graph.microsoft.com/v1.0/users",
        callback=graph_api_users_callback,
        content_type="application/json",
    )
    requests_mock.add(
        responses.GET,
        "https://graph.microsoft.com/v1.0/directoryRoles",
        test_class.fixture_data("directory_roles.json", "microsoft_graph_api_response_fixtures"),
    )
    requests_mock.add(
        responses.GET,
        "https://graph.microsoft.com/v1.0/directoryRoles/240d3723-f4d5-4e70-aa3b-2e574c4f6ea3/members",
        test_class.fixture_data(
            "directory_roles_global_administrator_members.json",
            "microsoft_graph_api_response_fixtures",
        ),
    )
    # Add one failed download to test scrub_uploads_records_after_download.
    requests_mock.add(responses.GET, FAILED_HOSTED_CONTENT_DOWNLOAD_URL, status=400)
    requests_mock.add(
        responses.GET,
        re.compile(HOSTED_CONTENT_GRAPH_API_URL_REGEX),
        body=read_test_image_file("img.png"),
        content_type="image/png",
        status=200,
    )


class MicrosoftTeamsImportTestCase(ZulipTestCase):
    def get_exported_microsoft_teams_user_data(self) -> list[MicrosoftTeamsFieldsT]:
        return json.loads(
            self.fixture_data(
                "usersList.json", "microsoft_teams_fixtures/TeamsData_ZulipChat/users"
            )
        )


class MicrosoftTeamsImporterIntegrationTest(MicrosoftTeamsImportTestCase, ImporterContractTestBase):
    """Translates the Microsoft Teams export fixture into the
    importer-agnostic expectations checked by ImporterContractTestBase."""

    IMPORT_SOURCE = "microsoft_teams"
    converted_output_dir: str

    @classmethod
    @override
    def convert_export(cls) -> str:
        cls.converted_output_dir = cls.make_converted_output_dir()
        fixture_dir = os.path.join(
            os.path.dirname(__file__), "fixtures", "microsoft_teams_fixtures", "TeamsData_ZulipChat"
        )
        with (
            responses.RequestsMock(assert_all_requests_are_fired=False) as requests_mock,
            override_settings(EXTERNAL_HOST="zulip.example.com"),
        ):
            add_microsoft_graph_api_responses(requests_mock)
            do_convert_directory(
                fixture_dir,
                cls.converted_output_dir,
                "MICROSOFT_GRAPH_API_TOKEN",
                processes=1,
            )
        return cls.converted_output_dir

    @cached_property
    def exported_user_data_map(self) -> dict[str, MicrosoftTeamsFieldsT]:
        return {user["Id"]: user for user in self.get_exported_microsoft_teams_user_data()}

    def get_convertible_exported_messages(self) -> list[ConvertibleExportedMessage]:
        """Returns every exported message that should be converted."""
        convertible_exported_messages = []
        for team_id in get_exported_team_ids():
            team_name = get_exported_team_data(team_id)["Name"]
            channel_metadata = get_exported_team_channel_metadata(team_id)
            for message in get_exported_team_message_list(team_id):
                if is_microsoft_teams_event_message(message):
                    continue
                microsoft_teams_channel = channel_metadata[message["ChannelIdentity"]["ChannelId"]]
                if microsoft_teams_channel.membership_type == "private":
                    continue
                convertible_exported_messages.append(
                    ConvertibleExportedMessage(
                        message=message,
                        team_name=team_name,
                        microsoft_teams_channel=microsoft_teams_channel,
                    )
                )
        return convertible_exported_messages

    def get_deleted_user_ids(self) -> set[str]:
        return {
            get_microsoft_teams_sender_id_from_message(exported_message.message)
            for exported_message in self.get_convertible_exported_messages()
        } - self.exported_user_data_map.keys()

    def get_expected_email(self, microsoft_teams_user_id: str) -> str:
        if microsoft_teams_user_id in self.exported_user_data_map:
            return self.exported_user_data_map[microsoft_teams_user_id]["Mail"]
        # Deleted users are imported as mirror dummies.
        return f"{microsoft_teams_user_id}@zulip.example.com"

    @override
    def get_expected_users(self) -> list[ExpectedUser]:
        expected_users = []
        for user in self.get_exported_microsoft_teams_user_data():
            if user["Mail"] in EXPORTED_REALM_OWNER_EMAILS:
                role = UserProfile.ROLE_REALM_OWNER
            elif user["Mail"] in GUEST_USER_EMAILS:
                role = UserProfile.ROLE_GUEST
            else:
                role = UserProfile.ROLE_MEMBER
            expected_users.append(
                ExpectedUser(
                    email=user["Mail"],
                    full_name=user["DisplayName"],
                    role=role,
                    is_bot=False,
                    bot_type=None,
                    is_active=True,
                    is_mirror_dummy=False,
                )
            )
        expected_users.extend(
            ExpectedUser(
                email=self.get_expected_email(user_id),
                full_name=f"Deleted Teams user {user_id}",
                role=UserProfile.ROLE_MEMBER,
                is_bot=False,
                bot_type=None,
                is_active=False,
                is_mirror_dummy=True,
            )
            for user_id in self.get_deleted_user_ids()
        )
        return expected_users

    @override
    def get_expected_channels(self) -> list[ExpectedChannel]:
        expected_channels = []
        for team_id in get_exported_team_ids():
            raw_team_data = get_exported_team_data(team_id)
            expected_channels.append(
                ExpectedChannel(
                    name=raw_team_data["Name"],
                    description=raw_team_data["Description"] or "",
                    invite_only=raw_team_data["Visibility"] == "private",
                    deactivated=raw_team_data["IsArchived"],
                    subscriber_emails=frozenset(
                        self.get_expected_email(subscription["UserId"])
                        for subscription in get_exported_team_subscription_list(team_id)
                    ),
                )
            )
        return expected_channels

    @override
    def get_expected_messages(self) -> list[ExpectedMessage]:
        # Microsoft Teams channels are converted into topics in the
        # channel for their team.
        return [
            ExpectedMessage(
                sender_email=self.get_expected_email(
                    get_microsoft_teams_sender_id_from_message(exported_message.message)
                ),
                date_sent=get_timestamp_from_message(exported_message.message),
                channel_name=exported_message.team_name,
                topic_name=exported_message.microsoft_teams_channel.display_name,
                direct_message_participant_emails=None,
            )
            for exported_message in self.get_convertible_exported_messages()
        ]

    @override
    def get_expected_attachment_file_names(self) -> list[str]:
        # Hosted-content images are downloaded and named after their
        # message's ID; a failed download is skipped.
        expected_attachment_file_names = []
        for exported_message in self.get_convertible_exported_messages():
            message = exported_message.message
            message_html = BeautifulSoup(message["Body"]["Content"], "html.parser")
            for image in message_html.find_all("img"):
                image_url = image.get("src")
                if (
                    isinstance(image_url, str)
                    and re.fullmatch(HOSTED_CONTENT_GRAPH_API_URL_REGEX, image_url)
                    and image_url != FAILED_HOSTED_CONTENT_DOWNLOAD_URL
                ):
                    expected_attachment_file_names.append(message["Id"])
        return expected_attachment_file_names

    def test_failed_download_has_no_upload_records(self) -> None:
        self.assertIn("INFO:root:HTTP error: 400, Response: ", self.conversion_log_output)

        uploads_records_path = os.path.join(self.converted_output_dir, "uploads", "records.json")
        with open(uploads_records_path, "rb") as f:
            upload_records = orjson.loads(f.read())
        for record in upload_records:
            file_path = os.path.join(self.converted_output_dir, "uploads", record["path"])
            self.assertTrue(os.path.isfile(file_path))

        attachment_records_path = os.path.join(self.converted_output_dir, "attachment.json")
        with open(attachment_records_path, "rb") as f:
            attachment_records = orjson.loads(f.read())
        for record in attachment_records["zerver_attachment"]:
            file_path = os.path.join(self.converted_output_dir, "uploads", record["path_id"])
            self.assertTrue(os.path.isfile(file_path))

    def test_deleted_users_imported_as_mirror_dummies(self) -> None:
        # test_imported_users derives deleted users from the export, so
        # check that the fixture actually has one.
        self.assertSetEqual(self.get_deleted_user_ids(), set(DELETED_MICROSOFT_TEAMS_USERS))
        mirror_dummy_emails = UserProfile.objects.filter(
            realm=self.imported_realm, is_mirror_dummy=True, is_active=False
        ).values_list("email", flat=True)
        self.assertCountEqual(
            mirror_dummy_emails,
            [f"{user_id}@zulip.example.com" for user_id in DELETED_MICROSOFT_TEAMS_USERS],
        )

    def test_private_channel_messages_not_imported(self) -> None:
        # test_imported_messages skips private channels when deriving
        # expected messages, so check that the fixture actually has
        # messages in one.
        team_id = EXPORTED_MICROSOFT_TEAMS_TEAM_ID["Core team"]
        channel_metadata = get_exported_team_channel_metadata(team_id)
        private_channel_messages = [
            message
            for message in get_exported_team_message_list(team_id)
            if not is_microsoft_teams_event_message(message)
            and message["ChannelIdentity"]["ChannelId"] in PRIVATE_MICROSOFT_TEAMS_CHANNELS
        ]
        self.assertNotEqual(private_channel_messages, [])

        team_channel = Stream.objects.get(realm=self.imported_realm, name="Core team")
        assert team_channel.recipient_id is not None
        for private_channel_id in PRIVATE_MICROSOFT_TEAMS_CHANNELS:
            private_channel = channel_metadata[private_channel_id]
            self.assertEqual(private_channel.membership_type, "private")
            self.assertFalse(
                messages_for_topic(
                    self.imported_realm.id, team_channel.recipient_id, private_channel.display_name
                ).exists()
            )


class MicrosoftTeamsImporterUnitTest(MicrosoftTeamsImportTestCase):
    def convert_users_handler(
        self,
        realm: dict[str, Any] | None = None,
        realm_id: int = 0,
        users_list: list[MicrosoftTeamsFieldsT] | None = None,
        user_data_fixture_name: str | None = None,
        microsoft_teams_user_role_data: MicrosoftTeamsUserRoleData = MICROSOFT_TEAMS_EXPORT_USER_ROLE_DATA,
    ) -> MicrosoftTeamsUserIdToZulipUserIdT:
        if users_list is None:
            users_list = self.get_exported_microsoft_teams_user_data()

        if realm is None:
            realm = {}
            realm["zerver_stream"] = []
            realm["zerver_defaultstream"] = []
            realm["zerver_recipient"] = []
            realm["zerver_subscription"] = []

        if user_data_fixture_name is not None:
            users_list = json.loads(
                self.fixture_data(user_data_fixture_name, "microsoft_teams_fixtures/test_fixtures")
            )

        return convert_users(
            realm=realm,
            realm_id=realm_id,
            users_list=users_list,
            microsoft_teams_user_role_data=microsoft_teams_user_role_data,
            timestamp=int(float(timezone_now().timestamp())),
        )

    @responses.activate
    def get_user_roles_handler(
        self,
        directory_roles_response_fixture: str | None = "directory_roles.json",
        global_administrators_response_fixture: str
        | None = "directory_roles_global_administrator_members.json",
        guest_users_response_fixture: str | None = "users_guest.json",
    ) -> MicrosoftTeamsUserRoleData:
        # TODO: For simplicity, this test assumes we only query for the guest userss.
        # This can be updated to use `add_callback` and call something like
        # `graph_api_users_callback` if the importer performs other types of queries.
        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/users?%24filter=userType+eq+%27Guest%27&%24select=id",
            self.fixture_data(
                guest_users_response_fixture,
                "microsoft_graph_api_response_fixtures",
            )
            if guest_users_response_fixture
            else json.dumps({"value": []}),
        )
        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/directoryRoles",
            self.fixture_data(
                directory_roles_response_fixture, "microsoft_graph_api_response_fixtures"
            )
            if directory_roles_response_fixture
            else json.dumps({"value": []}),
        )
        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/directoryRoles/240d3723-f4d5-4e70-aa3b-2e574c4f6ea3/members",
            self.fixture_data(
                global_administrators_response_fixture,
                "microsoft_graph_api_response_fixtures",
            )
            if global_administrators_response_fixture
            else json.dumps({"value": []}),
        )
        return get_user_roles("MICROSOFT_GRAPH_API_TOKEN")

    def test_convert_users_with_no_admin(self) -> None:
        microsoft_teams_user_role_data = MicrosoftTeamsUserRoleData(
            global_administrator_user_ids=set(), guest_user_ids=set()
        )
        with self.assertLogs(level="INFO") as info_logs:
            self.convert_users_handler(
                microsoft_teams_user_role_data=microsoft_teams_user_role_data
            )
        self.assertIn(
            "WARNING:root:Converted realm has no owners!",
            info_logs.output,
        )

    def test_conver_users_with_missing_email(self) -> None:
        with self.assertLogs(level="INFO"), self.assertRaises(AssertionError) as e:
            self.convert_users_handler(user_data_fixture_name="user_list_with_missing_email.json")
        self.assertEqual(
            "Could not find email address for Microsoft Teams user {'BusinessPhones': [], 'JobTitle': None, 'Mail': None, 'MobilePhone': None, 'OfficeLocation': None, 'PreferredLanguage': None, 'UserPrincipalName': None, 'Id': '5dbe468a-1e96-4aaa-856d-cdf825081e11', 'UserId': None, 'DisplayName': 'zoe', 'UserName': None, 'PhoneNumber': None, 'Location': None, 'InterpretedUserType': None, 'DirectoryStatus': None, 'AudioConferencing': None, 'PhoneSystems': None, 'CallingPlan': None, 'AssignedPlans': None, 'OnlineDialinConferencingPolicy': None, 'FeatureTypes': None, 'State': None, 'City': None, 'Surname': None, 'GivenName': 'zoe'}",
            str(e.exception),
        )

    def test_convert_microsoft_teams_html_to_markdown_list_conversion(self) -> None:
        """
        convert_html_to_text used to mangle plain-text bulleted lists by
        escaping the leading dashes and collapsing the line breaks;
        convert_microsoft_teams_html_to_markdown leaves them intact.
        See #39351.
        """
        html = "<p>- bullet 1<br>- bullet 2<br>- bullet 3<br>- bullet 4</p>"
        content = convert_microsoft_teams_html_to_markdown(html)

        self.assertEqual(content, "- bullet 1  \n- bullet 2  \n- bullet 3  \n- bullet 4")

    def test_convert_microsoft_teams_html_to_markdown_image_conversion(self) -> None:
        hosted_content_url = "https://graph.microsoft.com/v1.0/teams/1d513e46-d8cd-41db-b84f-381fe5730794/channels/19:f0088fc2bb264dfe9a7a7924a23c7252@thread.tacv2/messages/1755002994809/hostedContents/aWQ9eF8wLXd1cy1kNi0zZDZkYmNiODA0OGFhODhmMWMxY2Q1N2ZhYWIzYzRhZA==/$value"
        self.assertEqual(
            convert_microsoft_teams_html_to_markdown(
                f'<img src="{hosted_content_url}" alt="image">'
            ),
            f"![image]({hosted_content_url})",
        )

        external_url = (
            "https://raw.githubusercontent.com/zulip/zulip/main/static/images/logo/"
            "zulip-icon-128x128.png"
        )
        self.assertEqual(
            convert_microsoft_teams_html_to_markdown(f'<img src="{external_url}" alt="logo">'),
            f"[logo]({external_url})",
        )

    @responses.activate
    def test_failed_get_microsoft_graph_api_data(self) -> None:
        responses.add(
            method=responses.GET,
            url="https://graph.microsoft.com/v1.0/directoryRoles",
            status=403,
        )
        with self.assertRaises(Exception) as e, self.assertLogs(level="INFO"):
            get_microsoft_graph_api_data(
                MICROSOFT_GRAPH_API_URL.format(endpoint="/directoryRoles"),
                token="MICROSOFT_GRAPH_API_TOKEN",
            )
        self.assertEqual("HTTP error accessing the Microsoft Graph API.", str(e.exception))

    def test_get_user_roles(self) -> None:
        with self.subTest("No global administrator role found"):
            with self.assertRaises(AssertionError) as e:
                # This is primarily only for test coverage, it's likely a very rare case since
                # this role is one of the built-in roles.
                self.get_user_roles_handler(directory_roles_response_fixture=None)
            self.assertEqual(
                "Could not find Microsoft Teams organization owners/administrators.",
                str(e.exception),
            )

    @responses.activate
    def test_paginated_get_microsoft_graph_api_data(self) -> None:
        def paginated_graph_api_users_callback(request: PreparedRequest) -> ResponseTuple:
            assert request.url is not None
            parsed = urlsplit(request.url)
            query_params = parse_qs(parsed.query)
            queries = set(query_params.keys())

            if queries == {"$filter", "$top"}:
                body = self.fixture_data(
                    "paginated_users_member.json",
                    "microsoft_graph_api_response_fixtures",
                )
            elif queries == {"$filter", "$skiptoken", "$top"}:
                body = self.fixture_data(
                    "paginated_users_member_2.json",
                    "microsoft_graph_api_response_fixtures",
                )
            else:
                raise AssertionError("There is no response fixture for this request.")

            headers = {"Content-Type": "application/json"}
            return 200, headers, body

        responses.add_callback(
            responses.GET,
            "https://graph.microsoft.com/v1.0/users",
            callback=paginated_graph_api_users_callback,
            content_type="application/json",
        )

        odata_parameter = [
            ODataQueryParameter(parameter="$filter", expression="userType eq 'Member'"),
            ODataQueryParameter(parameter="$top", expression="3"),
        ]
        result = get_microsoft_graph_api_data(
            MICROSOFT_GRAPH_API_URL.format(endpoint="/users"),
            odata_parameter,
            token="MICROSOFT_GRAPH_API_TOKEN",
        )
        result_user_ids = {user["id"] for user in result}
        expected_member_users = {
            user["Id"]
            for user in self.get_exported_microsoft_teams_user_data()
            if user["Mail"] not in GUEST_USER_EMAILS
        }
        self.assertSetEqual(result_user_ids, expected_member_users)

    def test_get_batched_export_message_data(self) -> None:
        # Load a couple separate files to see how it handles combining and batching
        # messages from multiple files.
        message_file_paths = [
            self.fixture_file_name(
                "TeamsData_ZulipChat/teams/7c050abd-3cbb-448b-a9de-405f54cc14b2/messages_7c050abd-3cbb-448b-a9de-405f54cc14b2.json",
                "microsoft_teams_fixtures",
            ),
            self.fixture_file_name(
                "TeamsData_ZulipChat/teams/2a00a70a-00f5-4da5-8618-8281194f0de0/messages_2a00a70a-00f5-4da5-8618-8281194f0de0.json",
                "microsoft_teams_fixtures",
            ),
        ]
        total_messages = 0
        for path in message_file_paths:
            total_messages += len(get_data_file(path))

        chunk_sizes = [5, 10, MESSAGE_BATCH_CHUNK_SIZE]
        for chunk_size in chunk_sizes:
            message_batches = 0
            expected_batch_amount = math.ceil(total_messages / chunk_size)
            messages_left = total_messages
            for batched_messages in get_batched_export_message_data(message_file_paths, chunk_size):
                if chunk_size <= messages_left:
                    self.assertGreaterEqual(chunk_size, len(batched_messages))
                    messages_left -= len(batched_messages)
                else:
                    self.assertGreaterEqual(messages_left, len(batched_messages))
                message_batches += 1
            self.assertTrue(message_batches == expected_batch_amount)

    @responses.activate
    def test_process_hosted_content_attachments(self) -> None:
        responses.add(
            responses.GET,
            re.compile(HOSTED_CONTENT_GRAPH_API_URL_REGEX),
            body=read_test_image_file("img.png"),
            content_type="image/png",
            status=200,
        )

        @dataclass
        class MessageFixture:
            content: str
            hosted_content_count: int
            test_name: str
            is_direct_message_type: bool
            teams_message_id: str = "T"
            zulip_message_id: int = 0
            zulip_user_id: int = 0

        message_fixtures: list[MessageFixture] = [
            # This is actual decoded content from a message in messages_1d513e46-d8cd-41db-b84f-381fe5730794.json
            # The original message was just some text followed by an image.
            MessageFixture(
                content=convert_microsoft_teams_html_to_markdown(
                    """
                    <ul>
                        <li>dashes are ok</li>
                        <li>asterisks are ok</li>
                    </ul>
                    <p>+ Pluses are not counted as bullet point</p>
                    <p>&nbsp;</p>
                    <p>Rendered:</p>
                    <p>
                        <img
                         src="https://graph.microsoft.com/v1.0/teams/1d513e46-d8cd-41db-b84f-381fe5730794/channels/19:f0088fc2bb264dfe9a7a7924a23c7252@thread.tacv2/messages/1755002994809/hostedContents/aWQ9eF8wLXd1cy1kNi0zZDZkYmNiODA0OGFhODhmMWMxY2Q1N2ZhYWIzYzRhZCx0eXBlPTEsdXJsPWh0dHBzOi8vdXMtYXBpLmFzbS5za3lwZS5jb20vdjEvb2JqZWN0cy8wLXd1cy1kNi0zZDZkYmNiODA0OGFhODhmMWMxY2Q1N2ZhYWIzYzRhZC92aWV3cy9pbWdv/$value"
                         width="1189"
                         height="208"
                         alt="image"
                         itemid="0-wus-d6-3d6dbcb8048aa88f1c1cd57faab3c4ad">
                    </p>
                    """,
                ),
                hosted_content_count=1,
                is_direct_message_type=False,
                test_name="text and an image",
            ),
            # Unprocessed converted html
            MessageFixture(
                content="Normal text and an ![image](https://graph.microsoft.com/v1.0/teams/1d513e46-d8cd-41db-b84f-381fe5730794/channels/19:f0088fc2bb264dfe9a7a7924a23c7252@thread.tacv2/messages/1755002994809/hostedContents/aWQ9eF8wLXd1cy1kNi0zZDZkYmNiODA0OGFhODhmMWMxY2Q1N2ZhYWIzYzRhZCx0eXBlPTEsdXJsPWh0dHBzOi8vdXMtYXBpLmFzbS5za3lwZS5jb20vdjEvb2JqZWN0cy8wLXd1cy1kNi0zZDZkYmNiODA0OGFhODhmMWMxY2Q1N2ZhYWIzYzRhZC92aWV3cy9pbWdv/$value)",
                hosted_content_count=1,
                is_direct_message_type=False,
                test_name="text and an image 2",
            ),
            MessageFixture(
                content=(
                    "First ![image](https://graph.microsoft.com/v1.0/teams/1d513e46-d8cd-41db-b84f-381fe5730794/channels/19:f0088fc2bb264dfe9a7a7924a23c7252@thread.tacv2/messages/1755002994809/hostedContents/aWQ9eF8wLXd1cy1kNi0zZDZkYmNiODA0OGFhODhmMWMxY2Q1N2ZhYWIzYzRhZCx0eXBlPTEsdXJsPWh0dHBzOi8vdXMtYXBpLmFzbS5za3lwZS5jb20vdjEvb2JqZWN0cy8wLXd1cy1kNi0zZDZkYmNiODA0OGFhODhmMWMxY2Q1N2ZhYWIzYzRhZC92aWV3cy9pbWdv/$value)"
                    "Second ![image](https://graph.microsoft.com/v1.0/teams/1d513e46-d8cd-41db-b84f-381fe5730794/channels/19:f0088fc2bb264dfe9a7a7924a23c7252@thread.tacv2/messages/1755002994809/hostedContents/ABC/$value)"
                    "Third ![image](https://graph.microsoft.com/v1.0/teams/1d513e46-d8cd-41db-b84f-381fe5730794/channels/19:f0088fc2bb264dfe9a7a7924a23c7252@thread.tacv2/messages/1755002994809/hostedContents/DEF/$value)"
                ),
                hosted_content_count=3,
                is_direct_message_type=False,
                test_name="multiple images",
            ),
            # This is actual decoded content from a message in messages_002145f2-eaba-4962-997d-6d841a9f50af.json
            # The original message was just two custom emojis, nothing else.
            # convert_microsoft_teams_html_to_markdown doesn't know how to process MS
            # Teams-specific tags such as <customemoji>, so this will be converted to
            # empty string.
            MessageFixture(
                content=convert_microsoft_teams_html_to_markdown(
                    """
                    <p>
                        <span>
                            <customemoji
                             id="MC13dXMtZDEtZWMzY2I4NmY3MmM5YzBjNGJlMjE2Zjk3MTM1MDZkNTQ="
                             alt="notif-bot"
                             source="https://graph.microsoft.com/v1.0/teams/002145f2-eaba-4962-997d-6d841a9f50af/channels/19:9OOyLpkB8mEaoB17Z5CJx-RDBuMCZ5IZfuZVTCV97Bg1@thread.tacv2/messages/1759320958611/hostedContents/aWQ9LHR5cGU9MSx1cmw9aHR0cHM6Ly91cy1wcm9kLmFzeW5jZ3cudGVhbXMubWljcm9zb2Z0LmNvbS92MS9vYmplY3RzLzAtd3VzLWQxLWVjM2NiODZmNzJjOWMwYzRiZTIxNmY5NzEzNTA2ZDU0L3ZpZXdzL2ltZ3QyX2FuaW0=/$value">
                            </customemoji>
                        </span>
                        <span>
                            <customemoji
                             id="MC13dXMtZDItMWNmOWZmOGQ2OTFiOGM5ZjExYzhhM2ZhMzJiMzFlMDU="
                             alt="zlp-logo"
                             source="https://graph.microsoft.com/v1.0/teams/002145f2-eaba-4962-997d-6d841a9f50af/channels/19:9OOyLpkB8mEaoB17Z5CJx-RDBuMCZ5IZfuZVTCV97Bg1@thread.tacv2/messages/1759320958611/hostedContents/aWQ9LHR5cGU9MSx1cmw9aHR0cHM6Ly91cy1wcm9kLmFzeW5jZ3cudGVhbXMubWljcm9zb2Z0LmNvbS92MS9vYmplY3RzLzAtd3VzLWQyLTFjZjlmZjhkNjkxYjhjOWYxMWM4YTNmYTMyYjMxZTA1L3ZpZXdzL2ltZ3QyX2FuaW0=/$value">
                            </customemoji>
                        </span>
                    </p>
                    """,
                ),
                hosted_content_count=0,
                is_direct_message_type=False,
                test_name="two custom emojis",
            ),
            MessageFixture(
                content="Normal message",
                hosted_content_count=0,
                is_direct_message_type=False,
                test_name="text only",
            ),
            MessageFixture(
                content="MS Sharepoint attachment URL ![image](https://zulipchat.sharepoint.com/sites/Community/Shared Documents/General/wp12245700.jpg)",
                hosted_content_count=0,
                is_direct_message_type=False,
                test_name="text and other URL",
            ),
            MessageFixture(
                content=(
                    "List all hosted content ![invalid](https://graph.microsoft.com/v1.0/teams/FOO/channels/BAZ/hostedContents)"
                    "Get a hosted content ![valid](https://graph.microsoft.com/v1.0/teams/FOO/channels/BAZ/messages/BAR/hostedContents/QUX/$value)"
                ),
                hosted_content_count=1,
                is_direct_message_type=False,
                test_name="invalid get hosted content URL and a valid one",
            ),
            MessageFixture(
                content=(
                    "DM ![image](https://graph.microsoft.com/v1.0/chats/{chat-id}/messages/{message-id}/hostedContents/{hosted-content-id}/$value)"
                ),
                hosted_content_count=0,
                is_direct_message_type=True,
                test_name="DM hosted content",
            ),
        ]
        output_dir = tempfile.mkdtemp()
        realm_id = 0
        try:
            for id_count, fixture in enumerate(message_fixtures, 1):
                # Increment the fixture IDs to make them unique.
                fixture.teams_message_id += str(id_count)
                fixture.zulip_message_id += id_count
                # Multiply by 10 to help verify that we're computing each
                # object ID correctly for this code path.
                fixture.zulip_user_id += id_count * 10

                total_attachment_records: list[AttachmentRecordData] = []
                do_download_and_export_upload_file = partial(
                    download_and_export_microsoft_teams_upload_file,
                    total_attachment_records,
                    output_dir,
                )
                with self.subTest(fixture.test_name):
                    attachment_result = process_hosted_content_attachments(
                        content=fixture.content,
                        do_download_and_export_upload_file=do_download_and_export_upload_file,
                        is_direct_message_type=fixture.is_direct_message_type,
                        microsoft_graph_api_token="MICROSOFT_GRAPH_API_TOKEN",
                        realm_id=realm_id,
                        teams_message_id=fixture.teams_message_id,
                        zulip_message_id=fixture.zulip_message_id,
                        zulip_user_id=fixture.zulip_user_id,
                    )

                    self.assert_length(
                        attachment_result.upload_records, fixture.hosted_content_count
                    )
                    self.assert_length(total_attachment_records, fixture.hosted_content_count)

                    for upload_record in attachment_result.upload_records:
                        self.assertEqual(upload_record.realm_id, realm_id)
                        self.assertEqual(upload_record.user_profile_id, fixture.zulip_user_id)
                        self.assertRegex(
                            upload_record.path, rf"^{realm_id}/.*/.*/{fixture.teams_message_id}$"
                        )
                        upload_file = os.path.join(output_dir, "uploads", upload_record.path)
                        self.assertTrue(os.path.exists(upload_file))
                        self.assertIn(
                            os.path.join("/user_uploads", upload_record.path),
                            attachment_result.updated_content,
                        )

                    for attachment_record in total_attachment_records:
                        self.assertEqual(attachment_record.realm, realm_id)
                        self.assertListEqual(attachment_record.messages, [fixture.zulip_message_id])
                        self.assertEqual(attachment_record.owner, fixture.zulip_user_id)
                        self.assertEqual(attachment_record.content_type, "image/png")
                        self.assertEqual(attachment_record.file_name, fixture.teams_message_id)
                        self.assertRegex(
                            attachment_record.path_id,
                            rf"^{realm_id}/.*/.*/{fixture.teams_message_id}$",
                        )
        finally:
            shutil.rmtree(output_dir)


# Abstract base class; the subclasses above run its tests.
del ImporterContractTestBase
