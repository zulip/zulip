import json
import os
from collections.abc import Callable
from functools import wraps
from typing import Any, Concatenate, TypeAlias
from urllib.parse import parse_qs, urlsplit

import responses
from django.utils.timezone import now as timezone_now
from requests import PreparedRequest
from typing_extensions import ParamSpec

from zerver.data_import.microsoft_teams import (
    MICROSOFT_GRAPH_API_URL,
    MicrosoftTeamsFieldsT,
    MicrosoftTeamsUserIdToZulipUserIdT,
    MicrosoftTeamsUserRoleData,
    ODataQueryParameter,
    convert_users,
    do_convert_directory,
    get_microsoft_graph_api_data,
    get_user_roles,
)
from zerver.lib.import_realm import do_import_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realms import get_realm
from zerver.models.recipients import Recipient
from zerver.models.users import UserProfile
from zerver.tests.test_import_export import make_export_output_dir

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

        # For now the importer doesn't generate any mirror dummy accounts.
        mirror_dummy_accounts = self.get_imported_realm_user_field_values(
            "id", is_mirror_dummy=True, is_active=False
        )
        self.assertListEqual(mirror_dummy_accounts, [])

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
        imported_user_full_names = self.get_imported_realm_user_field_values("full_name")
        self.assertEqual(sorted(raw_exported_user_full_names), sorted(imported_user_full_names))


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
