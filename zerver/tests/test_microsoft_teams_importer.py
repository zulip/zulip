import json
import math
import os
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from typing import Any, Concatenate, TypeAlias
from urllib.parse import parse_qs, urlsplit

import responses
from django.utils.timezone import now as timezone_now
from requests import PreparedRequest
from typing_extensions import ParamSpec

from zerver.data_import.import_util import get_data_file
from zerver.data_import.microsoft_teams import (
    MICROSOFT_GRAPH_API_URL,
    ChannelMetadata,
    MicrosoftTeamsFieldsT,
    MicrosoftTeamsUserIdToZulipUserIdT,
    MicrosoftTeamsUserRoleData,
    ODataQueryParameter,
    convert_users,
    do_convert_directory,
    get_batched_export_message_data,
    get_microsoft_graph_api_data,
    get_microsoft_teams_sender_id_from_message,
    get_timestamp_from_message,
    get_user_roles,
    is_microsoft_teams_event_message,
)
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE
from zerver.lib.import_realm import do_import_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import messages_for_topic
from zerver.models.messages import Message
from zerver.models.realms import get_realm
from zerver.models.recipients import Recipient
from zerver.models.streams import Stream, Subscription
from zerver.models.users import UserProfile, get_system_bot
from zerver.tests.test_import_export import make_export_output_dir
from zproject import settings

ParamT = ParamSpec("ParamT")

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

EXPORTED_MICROSOFT_TEAMS_TEAM_ID: dict[str, str] = {
    "Core team": "7c050abd-3cbb-448b-a9de-405f54cc14b2",
    "Community": "002145f2-eaba-4962-997d-6d841a9f50af",
    "Contributors": "2a00a70a-00f5-4da5-8618-8281194f0de0",
    "Feedback & support": "5e5f1988-3216-4ca0-83e9-18c04ecc7533",
    "Kandra Labs": "1d513e46-d8cd-41db-b84f-381fe5730794",
}


def get_exported_microsoft_teams_user_data() -> list[MicrosoftTeamsFieldsT]:
    test_class = ZulipTestCase()
    return json.loads(
        test_class.fixture_data(
            "usersList.json", "microsoft_teams_fixtures/TeamsData_ZulipChat/users"
        )
    )


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


def mock_microsoft_graph_api_calls(
    test_func: Callable[Concatenate["MicrosoftTeamsImporterIntegrationTest", ParamT], None],
) -> Callable[Concatenate["MicrosoftTeamsImporterIntegrationTest", ParamT], None]:
    @wraps(test_func)
    @responses.activate
    def _wrapped(
        self: "MicrosoftTeamsImporterIntegrationTest",
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> None:
        responses.add_callback(
            responses.GET,
            "https://graph.microsoft.com/v1.0/users",
            callback=graph_api_users_callback,
            content_type="application/json",
        )
        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/directoryRoles",
            self.fixture_data("directory_roles.json", "microsoft_graph_api_response_fixtures"),
        )
        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/directoryRoles/240d3723-f4d5-4e70-aa3b-2e574c4f6ea3/members",
            self.fixture_data(
                "directory_roles_global_administrator_members.json",
                "microsoft_graph_api_response_fixtures",
            ),
        )
        test_func(self, *args, **kwargs)

    return _wrapped


class MicrosoftTeamsImportTestCase(ZulipTestCase):
    def get_exported_microsoft_teams_user_data(self) -> list[MicrosoftTeamsFieldsT]:
        return json.loads(
            self.fixture_data(
                "usersList.json", "microsoft_teams_fixtures/TeamsData_ZulipChat/users"
            )
        )


class MicrosoftTeamsImporterIntegrationTest(MicrosoftTeamsImportTestCase):
    def get_imported_channel_subscriber_emails(self, channel: str | Stream) -> set[str]:
        if isinstance(channel, str):
            imported_channel = Stream.objects.get(
                name=channel,
                realm=get_realm(self.test_realm_subdomain),
            )
        else:
            imported_channel = channel  # nocoverage
        subscriptions = Subscription.objects.filter(recipient=imported_channel.recipient)
        users = {sub.user_profile.email for sub in subscriptions}
        return users

    def convert_microsoft_teams_export_fixture(self, fixture_folder: str) -> None:
        fixture_file_path = self.fixture_file_name(fixture_folder, "microsoft_teams_fixtures")
        if not os.path.isdir(fixture_file_path):
            raise AssertionError(f"Fixture file not found: {fixture_file_path}")
        with self.assertLogs(level="INFO"), self.settings(EXTERNAL_HOST="zulip.example.com"):
            do_convert_directory(
                fixture_file_path, self.converted_file_output_dir, "MICROSOFT_GRAPH_API_TOKEN"
            )

    def import_microsoft_teams_export_fixture(self, fixture_folder: str) -> None:
        self.convert_microsoft_teams_export_fixture(fixture_folder)
        with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
            do_import_realm(self.converted_file_output_dir, self.test_realm_subdomain)

    @mock_microsoft_graph_api_calls
    def do_import_realm_fixture(self, fixture: str = "TeamsData_ZulipChat/") -> None:
        self.converted_file_output_dir = make_export_output_dir()
        self.test_realm_subdomain = "test-import-teams-realm"
        self.import_microsoft_teams_export_fixture(fixture)
        exported_user_data = get_exported_microsoft_teams_user_data()
        self.exported_user_data_map = {u["Id"]: u for u in exported_user_data}

    def get_imported_realm_user_field_values(self, field: str, **kwargs: Any) -> list[str | int]:
        return list(
            UserProfile.objects.filter(
                realm=get_realm(self.test_realm_subdomain),
                **kwargs,
            ).values_list(field, flat=True)
        )

    def test_imported_users(self) -> None:
        self.do_import_realm_fixture()
        imported_user_emails = set(
            self.get_imported_realm_user_field_values(
                "email", is_mirror_dummy=False, is_active=True
            )
        )
        self.assertSetEqual(imported_user_emails, set(EXPORTED_MICROSOFT_TEAMS_USER_EMAIL.values()))

        mirror_dummy_accounts = self.get_imported_realm_user_field_values(
            "id", is_mirror_dummy=True, is_active=False
        )
        self.assert_length(mirror_dummy_accounts, 1)

        imported_realm_owner_emails = set(
            self.get_imported_realm_user_field_values("email", role=UserProfile.ROLE_REALM_OWNER)
        )
        self.assertSetEqual(imported_realm_owner_emails, set(EXPORTED_REALM_OWNER_EMAILS))

        imported_guest_user_emails = set(
            self.get_imported_realm_user_field_values("email", role=UserProfile.ROLE_GUEST)
        )
        self.assertSetEqual(imported_guest_user_emails, set(GUEST_USER_EMAILS))

        raw_exported_users_data = self.get_exported_microsoft_teams_user_data()

        raw_exported_user_full_names = [user["DisplayName"] for user in raw_exported_users_data]
        deleted_user_full_names = [
            f"Deleted Teams user {user_id}" for user_id in DELETED_MICROSOFT_TEAMS_USERS
        ]

        imported_user_full_names = self.get_imported_realm_user_field_values("full_name")
        self.assertEqual(
            sorted(raw_exported_user_full_names + deleted_user_full_names),
            sorted(imported_user_full_names),
        )

    def test_imported_channels(self) -> None:
        self.do_import_realm_fixture()
        all_imported_channels = Stream.objects.filter(
            realm=get_realm(self.test_realm_subdomain),
        )

        self.assert_length(all_imported_channels, len(EXPORTED_MICROSOFT_TEAMS_TEAM_ID))

        for channel in all_imported_channels:
            channel_name = channel.name

            # Teams data are imported correctly
            raw_team_data = get_exported_team_data(EXPORTED_MICROSOFT_TEAMS_TEAM_ID[channel_name])
            self.assertEqual(channel_name, raw_team_data["Name"])
            self.assertEqual(channel.description, raw_team_data["Description"] or "")
            self.assertEqual(channel.deactivated, raw_team_data["IsArchived"])
            self.assertEqual(channel.invite_only, raw_team_data["Visibility"] == "private")

            # Teams subscription are imported correctly.
            imported_channel_subscriber_emails = self.get_imported_channel_subscriber_emails(
                channel_name
            )
            raw_subscription_list = get_exported_team_subscription_list(
                EXPORTED_MICROSOFT_TEAMS_TEAM_ID[channel_name]
            )
            expected_subscriber_emails: set[str] = {
                self.exported_user_data_map[sub["UserId"]]["Mail"] for sub in raw_subscription_list
            }
            self.assertSetEqual(expected_subscriber_emails, imported_channel_subscriber_emails)

    def test_imported_channel_messages(self) -> None:
        self.do_import_realm_fixture()
        channel_name = "Core team"
        exported_team_messages = get_exported_team_message_list(
            EXPORTED_MICROSOFT_TEAMS_TEAM_ID[channel_name]
        )
        test_realm = get_realm(self.test_realm_subdomain)
        channel = Stream.objects.get(
            name=channel_name,
            realm=test_realm,
        )
        assert channel.recipient is not None

        convertable_exported_messages: list[MicrosoftTeamsFieldsT] = []
        convertable_exported_message_datetimes: list[float] = []
        exported_sender_messages_map: dict[str, list[float]] = defaultdict(list)
        private_channel_message_exists: bool
        deleted_user_message_exists: bool

        for message in exported_team_messages:
            if is_microsoft_teams_event_message(message):
                continue
            if message["ChannelIdentity"]["ChannelId"] in PRIVATE_MICROSOFT_TEAMS_CHANNELS:
                private_channel_message_exists = True
                continue
            sender_id = get_microsoft_teams_sender_id_from_message(message)
            if sender_id not in self.exported_user_data_map:
                assert sender_id in DELETED_MICROSOFT_TEAMS_USERS
                sender_email = f"{sender_id}@zulip.example.com"
                deleted_user_message_exists = True
            else:
                sender_email = self.exported_user_data_map[sender_id]["Mail"]

            convertable_exported_messages.append(message)
            message_datetime = get_timestamp_from_message(message)
            convertable_exported_message_datetimes.append(message_datetime)
            exported_sender_messages_map[sender_email].append(message_datetime)
        self.assertTrue(private_channel_message_exists)
        self.assertTrue(deleted_user_message_exists)

        imported_channel_messages = (
            Message.objects.filter(
                recipient=channel.recipient,
                realm=test_realm,
            )
            .exclude(sender_id=get_system_bot(settings.WELCOME_BOT, test_realm.id).id)
            .order_by("id")
        )
        self.assertTrue(imported_channel_messages.exists())

        imported_message_datetimes: list[float] = []
        imported_sender_messages_map: dict[str, list[float]] = defaultdict(list)
        last_date_sent: float = float("-inf")

        for imported_message in imported_channel_messages:
            message_date_sent = imported_message.date_sent.timestamp()
            # Imported messages are sorted chronologically.
            self.assertLessEqual(last_date_sent, message_date_sent)
            last_date_sent = max(last_date_sent, message_date_sent)

            # Message content is not empty.
            self.assertIsNotNone(imported_message.content)
            self.assertIsNotNone(imported_message.rendered_content)

            imported_message_datetimes.append(message_date_sent)
            imported_sender_messages_map[imported_message.sender.email].append(message_date_sent)

        self.assertListEqual(
            sorted(imported_message_datetimes),
            sorted(convertable_exported_message_datetimes),
        )

        # Message sender is correct.
        for sender_email, exported_message_datetimes in exported_sender_messages_map.items():
            self.assertListEqual(
                sorted(exported_message_datetimes),
                sorted(imported_sender_messages_map[sender_email]),
            )

        microsoft_team_channel_metadata = get_exported_team_channel_metadata(
            EXPORTED_MICROSOFT_TEAMS_TEAM_ID[channel_name]
        )

        # Microsoft Teams channels are correctly converted and imported
        # as Zulip topics.
        for (
            microsoft_team_channel_id,
            microsoft_team_channel_data,
        ) in microsoft_team_channel_metadata.items():
            messages_in_a_microsoft_team_channel = [
                m
                for m in convertable_exported_messages
                if m["ChannelIdentity"]["ChannelId"] == microsoft_team_channel_id
            ]

            topic_name = microsoft_team_channel_data.display_name

            imported_messages_in_a_zulip_topic = messages_for_topic(
                test_realm.id, channel.recipient.id, topic_name
            )
            self.assertEqual(
                len(messages_in_a_microsoft_team_channel), len(imported_messages_in_a_zulip_topic)
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
            "INFO:root:Converted realm has no owners!",
            info_logs.output,
        )

    def test_conver_users_with_missing_email(self) -> None:
        with self.assertLogs(level="INFO"), self.assertRaises(AssertionError) as e:
            self.convert_users_handler(user_data_fixture_name="user_list_with_missing_email.json")
        self.assertEqual(
            "Could not find email address for Microsoft Teams user {'BusinessPhones': [], 'JobTitle': None, 'Mail': None, 'MobilePhone': None, 'OfficeLocation': None, 'PreferredLanguage': None, 'UserPrincipalName': None, 'Id': '5dbe468a-1e96-4aaa-856d-cdf825081e11', 'UserId': None, 'DisplayName': 'zoe', 'UserName': None, 'PhoneNumber': None, 'Location': None, 'InterpretedUserType': None, 'DirectoryStatus': None, 'AudioConferencing': None, 'PhoneSystems': None, 'CallingPlan': None, 'AssignedPlans': None, 'OnlineDialinConferencingPolicy': None, 'FeatureTypes': None, 'State': None, 'City': None, 'Surname': None, 'GivenName': 'zoe'}",
            str(e.exception),
        )

    def test_at_least_one_recipient_per_user(self) -> None:
        """
        Make sure each user at least has a recipient field. This makes sure the
        the onboarding messages, runs smoothly even for users without any
        personal messages.
        """
        realm: dict[str, Any] = {}
        realm["zerver_stream"] = []
        realm["zerver_defaultstream"] = []
        realm["zerver_recipient"] = []
        realm["zerver_subscription"] = []
        with self.assertLogs(level="INFO"):
            microsoft_teams_user_id_to_zulip_user_id = self.convert_users_handler(
                realm=realm, microsoft_teams_user_role_data=MICROSOFT_TEAMS_EXPORT_USER_ROLE_DATA
            )

        self.assert_length(
            realm["zerver_recipient"], len(self.get_exported_microsoft_teams_user_data())
        )
        zulip_user_ids = set(microsoft_teams_user_id_to_zulip_user_id.values())
        for recipient in realm["zerver_recipient"]:
            self.assertTrue(recipient["type_id"] in zulip_user_ids)
            self.assertTrue(recipient["type"] == Recipient.PERSONAL)

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
        with (
            self.subTest("No global administrator role found"),
            self.assertRaises(AssertionError) as e,
        ):
            # This is primarily only for test coverage, it's likely a very rare case since
            # this role is one of the built-in roles.
            self.get_user_roles_handler(directory_roles_response_fixture=None)
            self.assertEqual(  # nocoverage
                "Could not find Microsoft Teams organization owners/administrators.",
                str(e.exception),
            )
        microsoft_teams_user_role_data: MicrosoftTeamsUserRoleData = self.get_user_roles_handler()
        self.assertSetEqual(
            microsoft_teams_user_role_data.global_administrator_user_ids,
            MICROSOFT_TEAMS_EXPORT_USER_ROLE_DATA.global_administrator_user_ids,
        )
        self.assertSetEqual(
            microsoft_teams_user_role_data.guest_user_ids,
            MICROSOFT_TEAMS_EXPORT_USER_ROLE_DATA.guest_user_ids,
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
