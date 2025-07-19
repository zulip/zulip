import os
import shutil
from collections.abc import Iterator
from io import BytesIO
from typing import TYPE_CHECKING, Any
from unittest import mock
from unittest.mock import ANY
from urllib.parse import parse_qs, urlsplit

import orjson
import responses
from django.conf import settings
from django.http import HttpResponse
from django.utils.timezone import now as timezone_now
from requests.models import PreparedRequest

from confirmation import settings as confirmation_settings
from confirmation.models import Confirmation, get_object_from_key
from zerver.actions.create_realm import do_create_realm
from zerver.actions.data_import import import_slack_data
from zerver.data_import.import_util import (
    ZerverFieldsT,
    build_defaultstream,
    build_recipient,
    build_subscription,
    build_usermessages,
    build_zerver_realm,
)
from zerver.data_import.sequencer import NEXT_ID
from zerver.data_import.slack import (
    SLACK_IMPORT_TOKEN_SCOPES,
    AddedChannelsT,
    AddedMPIMsT,
    DMMembersT,
    SlackBotEmail,
    SlackBotNotFoundError,
    channel_message_to_zerver_message,
    channels_to_zerver_stream,
    check_token_access,
    convert_slack_workspace_messages,
    do_convert_zipfile,
    fetch_shared_channel_users,
    get_admin,
    get_guest,
    get_message_sending_user,
    get_owner,
    get_slack_api_data,
    get_subscription,
    get_user_timezone,
    process_message_files,
    slack_emoji_name_to_codepoint,
    slack_workspace_to_realm,
    users_to_zerver_userprofile,
)
from zerver.lib.exceptions import SlackImportInvalidFileError
from zerver.lib.import_realm import do_import_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import find_key_by_email, read_test_image_file
from zerver.lib.topic import EXPORT_TOPIC_NAME
from zerver.models import (
    Message,
    PreregistrationRealm,
    Realm,
    RealmAuditLog,
    Recipient,
    UserProfile,
)
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


def remove_folder(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)


def request_callback(request: PreparedRequest) -> tuple[int, dict[str, str], bytes]:
    valid_endpoint = False
    endpoints = [
        "https://slack.com/api/users.list",
        "https://slack.com/api/users.info",
        "https://slack.com/api/team.info",
        "https://slack.com/api/bots.info",
        "https://slack.com/api/api.test",
    ]
    for endpoint in endpoints:
        if request.url and endpoint in request.url:
            valid_endpoint = True
            break
    if not valid_endpoint:
        return (404, {}, b"")

    if request.headers.get("Authorization") != "Bearer xoxb-valid-token":
        return (200, {}, orjson.dumps({"ok": False, "error": "invalid_auth"}))

    if request.url == "https://slack.com/api/users.list":
        return (200, {}, orjson.dumps({"ok": True, "members": "user_data"}))

    query_from_url = str(urlsplit(request.url).query)
    qs = parse_qs(query_from_url)
    if request.url and "https://slack.com/api/users.info" in request.url:
        user2team_dict = {
            "U061A3E0G": "T6LARQE2Z",
            "U061A8H1G": "T7KJRQE8Y",
            "U8X25EBAB": "T5YFFM2QY",
            "U11111111": "T7KJRQE8Y",
            "U22222222": "T7KJRQE8Y",
            "U33333333": "T7KJRQE8Y",
        }
        try:
            user_id = qs["user"][0]
            team_id = user2team_dict[user_id]
        except KeyError:
            return (200, {}, orjson.dumps({"ok": False, "error": "user_not_found"}))
        return (200, {}, orjson.dumps({"ok": True, "user": {"id": user_id, "team_id": team_id}}))

    if request.url and "https://slack.com/api/bots.info" in request.url:
        bot_info_dict = {
            "B06NWMNUQ3W": {
                "id": "B06NWMNUQ3W",
                "deleted": False,
                "name": "ClickUp",
                "updated": 1714669546,
                "app_id": "A3G4A68V9",
                "icons": {
                    "image_36": "https://avatars.slack-edge.com/2024-05-01/7057208497908_a4351f6deb91094eac4c_36.png",
                    "image_48": "https://avatars.slack-edge.com/2024-05-01/7057208497908_a4351f6deb91094eac4c_48.png",
                    "image_72": "https://avatars.slack-edge.com/2024-05-01/7057208497908_a4351f6deb91094eac4c_72.png",
                },
            }
        }
        try:
            bot_id = qs["bot"][0]
            bot_info = bot_info_dict[bot_id]
        except KeyError:
            return (200, {}, orjson.dumps({"ok": False, "error": "bot_not_found"}))
        return (200, {}, orjson.dumps({"ok": True, "bot": bot_info}))

    if request.url and "https://slack.com/api/api.test" in request.url:
        return (200, {}, orjson.dumps({"ok": True}))
    # Else, https://slack.com/api/team.info
    team_not_found: tuple[int, dict[str, str], bytes] = (
        200,
        {},
        orjson.dumps({"ok": False, "error": "team_not_found"}),
    )
    try:
        team_id = qs["team"][0]
    except KeyError:
        return team_not_found

    team_dict = {
        "T6LARQE2Z": "foreignteam1",
        "T7KJRQE8Y": "foreignteam2",
    }
    try:
        team_domain = team_dict[team_id]
    except KeyError:
        return team_not_found
    return (200, {}, orjson.dumps({"ok": True, "team": {"id": team_id, "domain": team_domain}}))


class SlackImporter(ZulipTestCase):
    @responses.activate
    def test_get_slack_api_data_with_pagination(self) -> None:
        token = "xoxb-valid-token"
        pagination_limit = 40

        api_users_list = [f"user{i}" for i in range(100)]
        count = 0

        def paginated_request_callback(
            request: PreparedRequest,
        ) -> tuple[int, dict[str, str], bytes]:
            """
            A callback that in a very simple way simulates Slack's /users.list API
            with support for Pagination and some rate-limiting behavior.
            """
            assert request.url is not None
            assert request.url.startswith("https://slack.com/api/users.list")
            # Otherwise mypy complains about PreparedRequest not having params attribute:
            assert hasattr(request, "params")

            nonlocal count
            count += 1

            self.assertEqual(request.params["limit"], str(pagination_limit))
            cursor = int(request.params.get("cursor", 0))
            next_cursor = cursor + pagination_limit

            if count % 3 == 0:
                # Simulate a rate limit hit on every third request.
                return (
                    429,
                    {"retry-after": "30"},
                    orjson.dumps({"ok": False, "error": "rate_limit_hit"}),
                )

            result_user_data = api_users_list[cursor:next_cursor]

            if next_cursor >= len(api_users_list):
                # The fetch is completed.
                response_metadata = {}
            else:
                response_metadata = {"next_cursor": str(next_cursor)}
            return (
                200,
                {},
                orjson.dumps(
                    {
                        "ok": True,
                        "members": result_user_data,
                        "response_metadata": response_metadata,
                    }
                ),
            )

        responses.add_callback(
            responses.GET, "https://slack.com/api/users.list", callback=paginated_request_callback
        )
        with (
            mock.patch("zerver.data_import.slack.time.sleep", return_value=None) as mock_sleep,
            self.assertLogs(level="INFO") as mock_log,
        ):
            result = get_slack_api_data(
                "https://slack.com/api/users.list",
                "members",
                token=token,
                pagination_limit=pagination_limit,
            )
        self.assertEqual(result, api_users_list)
        self.assertEqual(mock_sleep.call_count, 1)
        self.assertIn("INFO:root:Rate limit exceeded. Retrying in 30 seconds...", mock_log.output)

    @responses.activate
    def test_get_slack_api_data(self) -> None:
        token = "xoxb-valid-token"

        # Users list
        slack_user_list_url = "https://slack.com/api/users.list"
        responses.add_callback(responses.GET, slack_user_list_url, callback=request_callback)
        self.assertEqual(
            get_slack_api_data(slack_user_list_url, "members", token=token), "user_data"
        )

        # Users info
        slack_users_info_url = "https://slack.com/api/users.info"
        user_id = "U8X25EBAB"
        responses.add_callback(responses.GET, slack_users_info_url, callback=request_callback)
        self.assertEqual(
            get_slack_api_data(slack_users_info_url, "user", token=token, user=user_id),
            {"id": user_id, "team_id": "T5YFFM2QY"},
        )
        # Should error if the required user argument is not specified
        with self.assertRaises(Exception) as invalid:
            get_slack_api_data(slack_users_info_url, "user", token=token)
        self.assertEqual(invalid.exception.args, ("Error accessing Slack API: user_not_found",))
        # Should error if the required user is not found
        with self.assertRaises(Exception) as invalid:
            get_slack_api_data(slack_users_info_url, "user", token=token, user="idontexist")
        self.assertEqual(invalid.exception.args, ("Error accessing Slack API: user_not_found",))

        # Bot info
        slack_bots_info_url = "https://slack.com/api/bots.info"
        responses.add_callback(responses.GET, slack_bots_info_url, callback=request_callback)
        with self.assertRaises(SlackBotNotFoundError):
            get_slack_api_data(slack_bots_info_url, "XXXYYYZZZ", token=token)

        # Api test
        api_test_info_url = "https://slack.com/api/api.test"
        responses.add_callback(responses.GET, api_test_info_url, callback=request_callback)
        self.assertTrue(get_slack_api_data(api_test_info_url, "ok", token=token))

        # Team info
        slack_team_info_url = "https://slack.com/api/team.info"
        responses.add_callback(responses.GET, slack_team_info_url, callback=request_callback)
        with self.assertRaises(Exception) as invalid:
            get_slack_api_data(slack_team_info_url, "team", token=token, team="wedontexist")
        self.assertEqual(invalid.exception.args, ("Error accessing Slack API: team_not_found",))
        # Should error if the required user argument is not specified
        with self.assertRaises(Exception) as invalid:
            get_slack_api_data(slack_team_info_url, "team", token=token)
        self.assertEqual(invalid.exception.args, ("Error accessing Slack API: team_not_found",))

        token = "xoxb-invalid-token"
        with self.assertRaises(Exception) as invalid:
            get_slack_api_data(slack_user_list_url, "members", token=token)
        self.assertEqual(invalid.exception.args, ("Error accessing Slack API: invalid_auth",))

        with self.assertRaises(Exception) as invalid:
            get_slack_api_data(slack_user_list_url, "members")
        self.assertEqual(invalid.exception.args, ("Slack token missing in kwargs",))

        token = "xoxb-status404"
        wrong_url = "https://slack.com/api/wrong"
        responses.add_callback(responses.GET, wrong_url, callback=request_callback)
        with self.assertRaises(Exception) as invalid, self.assertLogs(level="INFO") as mock_log:
            get_slack_api_data(wrong_url, "members", token=token)
        self.assertEqual(invalid.exception.args, ("HTTP error accessing the Slack API.",))
        self.assertEqual(mock_log.output, ["INFO:root:HTTP error: 404, Response: "])

    def test_build_zerver_realm(self) -> None:
        realm_id = 2
        realm_subdomain = "test-realm"
        time = float(timezone_now().timestamp())
        test_realm: list[dict[str, Any]] = build_zerver_realm(
            realm_id, realm_subdomain, time, "Slack"
        )
        test_zerver_realm_dict = test_realm[0]

        self.assertEqual(test_zerver_realm_dict["id"], realm_id)
        self.assertEqual(test_zerver_realm_dict["string_id"], realm_subdomain)
        self.assertEqual(test_zerver_realm_dict["name"], realm_subdomain)
        self.assertEqual(test_zerver_realm_dict["date_created"], time)
        self.assertNotIn("uuid", test_zerver_realm_dict)
        self.assertNotIn("uuid_owner_secret", test_zerver_realm_dict)

    @responses.activate
    def test_check_token_access(self) -> None:
        def token_request_callback(request: PreparedRequest) -> tuple[int, dict[str, str], bytes]:
            auth = request.headers.get("Authorization")
            if auth == "Bearer xoxb-broken-request":
                return (400, {}, orjson.dumps({"ok": False, "error": "invalid_auth"}))

            if auth == "Bearer xoxb-invalid-token":
                return (200, {}, orjson.dumps({"ok": False, "error": "invalid_auth"}))

            if auth == "Bearer xoxb-very-limited-scopes":
                return (
                    200,
                    {"x-oauth-scopes": "emoji:read,bogus:scope"},
                    orjson.dumps(
                        {
                            "ok": False,
                            "error": "missing_scope",
                            "needed": "team:read",
                            "provided": "emoji:read,bogus:scope",
                        }
                    ),
                )
            if auth == "Bearer xoxb-limited-scopes":
                return (
                    200,
                    {"x-oauth-scopes": "team:read,bogus:scope"},
                    orjson.dumps({"ok": True}),
                )
            if auth == "Bearer xoxb-valid-token":
                return (
                    200,
                    {"x-oauth-scopes": "emoji:read,users:read,users:read.email,team:read"},
                    orjson.dumps({"ok": True}),
                )
            else:  # nocoverage
                raise Exception("Unknown token mock")

        responses.add_callback(
            responses.GET, "https://slack.com/api/api.test", callback=token_request_callback
        )

        def exception_for(token: str, required_scopes: set[str] = SLACK_IMPORT_TOKEN_SCOPES) -> str:
            with self.assertRaises(Exception) as invalid:
                check_token_access(token, required_scopes)
            return invalid.exception.args[0]

        self.assertEqual(
            exception_for("xoxq-unknown"),
            "Invalid token. Valid tokens start with xoxb-.",
        )

        with self.assertLogs(level="ERROR"):
            self.assertEqual(
                exception_for("xoxb-invalid-token"),
                "Invalid token: xoxb-invalid-token",
            )

        self.assertEqual(
            exception_for("xoxb-broken-request"),
            "Failed to fetch data (HTTP status 400) for Slack token: xoxb-broken-request",
        )

        self.assertEqual(
            exception_for("xoxb-limited-scopes"),
            "Slack token is missing the following required scopes: ['emoji:read', 'users:read', 'users:read.email']",
        )
        self.assertEqual(
            exception_for("xoxb-very-limited-scopes"),
            "Slack token is missing the following required scopes: ['team:read', 'users:read', 'users:read.email']",
        )

        check_token_access("xoxb-valid-token", required_scopes=SLACK_IMPORT_TOKEN_SCOPES)

    def test_get_owner(self) -> None:
        user_data = [
            {"is_owner": False, "is_primary_owner": False},
            {"is_owner": True, "is_primary_owner": False},
            {"is_owner": False, "is_primary_owner": True},
            {"is_owner": True, "is_primary_owner": True},
        ]
        self.assertEqual(get_owner(user_data[0]), False)
        self.assertEqual(get_owner(user_data[1]), True)
        self.assertEqual(get_owner(user_data[2]), True)
        self.assertEqual(get_owner(user_data[3]), True)

    def test_get_admin(self) -> None:
        user_data = [{"is_admin": True}, {"is_admin": False}]
        self.assertEqual(get_admin(user_data[0]), True)
        self.assertEqual(get_admin(user_data[1]), False)

    def test_get_guest(self) -> None:
        user_data = [
            {"is_restricted": False, "is_ultra_restricted": False},
            {"is_restricted": True, "is_ultra_restricted": False},
            {"is_restricted": False, "is_ultra_restricted": True},
            {"is_restricted": True, "is_ultra_restricted": True},
        ]
        self.assertEqual(get_guest(user_data[0]), False)
        self.assertEqual(get_guest(user_data[1]), True)
        self.assertEqual(get_guest(user_data[2]), True)
        self.assertEqual(get_guest(user_data[3]), True)

    def test_get_timezone(self) -> None:
        user_chicago_timezone = {"tz": "America/Chicago"}
        user_timezone_none = {"tz": None}
        user_no_timezone: dict[str, Any] = {}

        self.assertEqual(get_user_timezone(user_chicago_timezone), "America/Chicago")
        self.assertEqual(get_user_timezone(user_timezone_none), "America/New_York")
        self.assertEqual(get_user_timezone(user_no_timezone), "America/New_York")

    @mock.patch("zerver.data_import.slack.get_data_file")
    @mock.patch("zerver.data_import.slack.get_messages_iterator")
    @responses.activate
    def test_fetch_shared_channel_users(
        self, messages_mock: mock.Mock, data_file_mock: mock.Mock
    ) -> None:
        users = [{"id": "U061A1R2R"}, {"id": "U061A5N1G"}, {"id": "U064KUGRJ"}]
        data_file_mock.side_effect = [
            [  # Channels
                {"name": "general", "members": ["U061A1R2R", "U061A5N1G"]},
                {"name": "sharedchannel", "members": ["U061A1R2R", "U061A3E0G"]},
            ],
            [  # Private channels ("groups")
                {"name": "private", "members": ["U061A1R2R", "U11111111"]},
            ],
            [  # Direct message groups ("mpims")
                {
                    "name": "mpdm-foo--bar--baz-1",
                    "members": ["U061A1R2R", "U061A5N1G", "U22222222"],
                },
            ],
            [  # DMs
                {"id": "D123456", "members": ["U064KUGRJ", "U33333333"]},
            ],
        ]
        messages_mock.return_value = [
            {"user": "U061A1R2R", "team": "T6LARQE2Z"},
            {"user": "U061A5N1G", "team": "T6LARQE2Z"},
            {"user": "U061A8H1G", "team": "T6LARQE2Z"},
            {"subtype": "bot_message", "text": "", "username": "ClickUp", "bot_id": "B06NWMNUQ3W"},
        ]
        # Users info
        slack_users_info_url = "https://slack.com/api/users.info"
        responses.add_callback(responses.GET, slack_users_info_url, callback=request_callback)
        # Team info
        slack_team_info_url = "https://slack.com/api/team.info"
        responses.add_callback(responses.GET, slack_team_info_url, callback=request_callback)
        # Bot info
        slack_bot_info_url = "https://slack.com/api/bots.info"
        responses.add_callback(responses.GET, slack_bot_info_url, callback=request_callback)

        slack_data_dir = self.fixture_file_name("", type="slack_fixtures")
        fetch_shared_channel_users(users, slack_data_dir, "xoxb-valid-token")

        # Normal users
        self.assert_length(users, 9)
        self.assertEqual(users[0]["id"], "U061A1R2R")
        self.assertEqual(users[0]["is_mirror_dummy"], False)
        self.assertFalse("team_domain" in users[0])
        self.assertEqual(users[1]["id"], "U061A5N1G")
        self.assertEqual(users[2]["id"], "U064KUGRJ")

        # Shared channel users
        # We need to do this because the outcome order of `users` list is
        # not deterministic.
        later_users = sorted(users[3:], key=lambda x: x["id"])
        expected_users = [
            ("B06NWMNUQ3W", "ClickUp"),
            ("U061A3E0G", "foreignteam1"),
            ("U061A8H1G", "foreignteam2"),
            ("U11111111", "foreignteam2"),
            ("U22222222", "foreignteam2"),
            ("U33333333", "foreignteam2"),
        ]
        for expected, found in zip(expected_users, later_users, strict=False):
            self.assertEqual(found["id"], expected[0])
            if "bot_id" in found.get("profile", {}):
                self.assertEqual(found["real_name"], expected[1])
                self.assertEqual(found["is_mirror_dummy"], False)
            else:
                self.assertEqual(found["team_domain"], expected[1])
                self.assertEqual(found["is_mirror_dummy"], True)

    @mock.patch("zerver.data_import.slack.get_data_file")
    def test_users_to_zerver_userprofile(self, mock_get_data_file: mock.Mock) -> None:
        custom_profile_field_user1 = {
            "Xf06054BBB": {"value": "random1"},
            "Xf023DSCdd": {"value": "employee"},
        }
        custom_profile_field_user2 = {
            "Xf06054BBB": {"value": "random2"},
            "Xf023DSCdd": {"value": "employer"},
        }
        user_data: list[dict[str, Any]] = [
            {
                "id": "U08RGD1RD",
                "team_id": "T5YFFM2QY",
                "name": "john",
                "deleted": False,
                "is_mirror_dummy": False,
                "real_name": "John Doe",
                "profile": {
                    "image_32": "",
                    "email": "jon@gmail.com",
                    "avatar_hash": "hash",
                    "phone": "+1-123-456-77-868",
                    "fields": custom_profile_field_user1,
                },
            },
            {
                "id": "U0CBK5KAT",
                "team_id": "T5YFFM2QY",
                "is_admin": True,
                "is_bot": False,
                "is_owner": True,
                "is_primary_owner": True,
                "name": "Jane",
                "real_name": "Jane Doe",
                "deleted": False,
                "is_mirror_dummy": False,
                "profile": {
                    "image_32": "https://secure.gravatar.com/avatar/random.png",
                    "fields": custom_profile_field_user2,
                    "email": "jane@foo.com",
                    "avatar_hash": "hash",
                },
            },
            {
                "id": "U09TYF5Sk",
                "team_id": "T5YFFM2QY",
                "name": "Bot",
                "real_name": "Bot",
                "is_bot": True,
                "deleted": False,
                "is_mirror_dummy": False,
                "profile": {
                    "image_32": "https://secure.gravatar.com/avatar/random1.png",
                    "skype": "test_skype_name",
                    "email": "bot1@zulipchat.com",
                    "avatar_hash": "hash",
                },
            },
            {
                "id": "UHSG7OPQN",
                "team_id": "T6LARQE2Z",
                "name": "matt.perry",
                "color": "9d8eee",
                "is_bot": False,
                "is_app_user": False,
                "is_mirror_dummy": True,
                "team_domain": "foreignteam",
                "profile": {
                    "image_32": "https://secure.gravatar.com/avatar/random6.png",
                    "avatar_hash": "hash",
                    "first_name": "Matt",
                    "last_name": "Perry",
                    "real_name": "Matt Perry",
                    "display_name": "matt.perry",
                    "team": "T6LARQE2Z",
                },
            },
            {
                "id": "U8VAHEVUY",
                "team_id": "T5YFFM2QY",
                "name": "steviejacob34",
                "real_name": "Steve Jacob",
                "is_admin": False,
                "is_owner": False,
                "is_primary_owner": False,
                "is_restricted": True,
                "is_ultra_restricted": False,
                "is_bot": False,
                "is_mirror_dummy": False,
                "profile": {
                    "email": "steviejacob34@yahoo.com",
                    "avatar_hash": "hash",
                    "image_32": "https://secure.gravatar.com/avatar/random6.png",
                },
            },
            {
                "id": "U8X25EBAB",
                "team_id": "T5YFFM2QY",
                "name": "pratikweb_0",
                "real_name": "Pratik",
                "is_admin": False,
                "is_owner": False,
                "is_primary_owner": False,
                "is_restricted": True,
                "is_ultra_restricted": True,
                "is_bot": False,
                "is_mirror_dummy": False,
                "profile": {
                    "email": "pratik@mit.edu",
                    "avatar_hash": "hash",
                    "image_32": "https://secure.gravatar.com/avatar/random.png",
                },
            },
            {
                "id": "U015J7JSE",
                "team_id": "T5YFFM2QY",
                "name": "georgesm27",
                "real_name": "George",
                "is_admin": True,
                "is_owner": True,
                "is_primary_owner": False,
                "is_restricted": False,
                "is_ultra_restricted": False,
                "is_bot": False,
                "is_mirror_dummy": False,
                "profile": {
                    "email": "george@yahoo.com",
                    "avatar_hash": "hash",
                    "image_32": "https://secure.gravatar.com/avatar/random5.png",
                },
            },
            {
                "id": "U1RDFEC80",
                "team_id": "T5YFFM2QY",
                "name": "daniel.smith",
                "real_name": "Daniel Smith",
                "is_admin": True,
                "is_owner": False,
                "is_primary_owner": False,
                "is_restricted": False,
                "is_ultra_restricted": False,
                "is_bot": False,
                "is_mirror_dummy": False,
                "profile": {
                    "email": "daniel@gmail.com",
                    "avatar_hash": "hash",
                    "image_32": "https://secure.gravatar.com/avatar/random7.png",
                },
            },
            # Unknown user data format.
            {
                "id": "U1ZYFEC91",
                "team_id": "T5YFFM2QZ",
                "name": "daniel.who",
                "real_name": "Daniel Who",
                "is_admin": True,
                "is_owner": False,
                "is_primary_owner": False,
                "is_restricted": False,
                "is_ultra_restricted": False,
                "is_bot": False,
                "is_mirror_dummy": False,
                "profile": {
                    "email": "daniel.who@gmail.com",
                },
                # Missing the `avatar_hash` value.
            },
            {
                "id": "U1MBOTC81",
                "name": "Integration Bot",
                "deleted": False,
                "is_mirror_dummy": False,
                "real_name": "Integration Bot",
                "is_integration_bot": True,
                "profile": {
                    "image_72": "https://avatars.slack-edge.com/2024-05-01/7057208497908_a4351f6deb91094eac4c_512.png",
                    "bot_id": "B06NWMNUQ3W",
                    "first_name": "Integration Bot",
                },
            },
            # Test error-handling for a bot user with an unknown avatar URL format.
            # In reality, we expect the file to have a file extension type to be
            # `.png` or within the range of `THUMBNAIL_ACCEPT_IMAGE_TYPES`.
            {
                "id": "U1RDFEC90",
                "name": "Unknown Bot",
                "deleted": False,
                "is_mirror_dummy": False,
                "real_name": "Unknown Bot",
                "is_integration_bot": True,
                "profile": {
                    "image_72": "https://avatars.slack-edge.com/2024-05-01/dasdasdasdasdXXXXXX",
                    "bot_id": "B0DSAMNUQ3W",
                    "first_name": "Unknown Bot",
                },
            },
        ]

        mock_get_data_file.return_value = user_data
        # As user with slack_id 'U0CBK5KAT' is the primary owner, that user should be imported first
        # and hence has zulip_id = 1
        test_slack_user_id_to_zulip_user_id = {
            "U08RGD1RD": 1,
            "U0CBK5KAT": 0,
            "U09TYF5Sk": 2,
            "UHSG7OPQN": 3,
            "U8VAHEVUY": 4,
            "U8X25EBAB": 5,
            "U015J7JSE": 6,
            "U1RDFEC80": 7,
            "U1ZYFEC91": 8,
            "U1MBOTC81": 9,
            "U1RDFEC90": 10,
        }
        slack_data_dir = "./random_path"
        timestamp = int(timezone_now().timestamp())
        mock_get_data_file.return_value = user_data

        with self.assertLogs(level="INFO"):
            (
                zerver_userprofile,
                avatar_list,
                slack_user_id_to_zulip_user_id,
                customprofilefield,
                customprofilefield_value,
            ) = users_to_zerver_userprofile(
                slack_data_dir, user_data, 1, timestamp, "testdomain.com"
            )

        # Test custom profile fields
        self.assertEqual(customprofilefield[0]["field_type"], 1)
        self.assertEqual(customprofilefield[3]["name"], "skype")
        cpf_name = {cpf["name"] for cpf in customprofilefield}
        self.assertIn("phone", cpf_name)
        self.assertIn("skype", cpf_name)
        cpf_name.remove("phone")
        cpf_name.remove("skype")
        for name in cpf_name:
            self.assertTrue(name.startswith("Slack custom field "))

        self.assert_length(customprofilefield_value, 6)
        self.assertEqual(customprofilefield_value[0]["field"], 0)
        self.assertEqual(customprofilefield_value[0]["user_profile"], 1)
        self.assertEqual(customprofilefield_value[3]["user_profile"], 0)
        self.assertEqual(customprofilefield_value[5]["value"], "test_skype_name")

        # test that the primary owner should always be imported first
        self.assertDictEqual(slack_user_id_to_zulip_user_id, test_slack_user_id_to_zulip_user_id)
        self.assert_length(avatar_list, 9)

        self.assert_length(zerver_userprofile, 11)

        self.assertEqual(zerver_userprofile[0]["is_staff"], False)
        self.assertEqual(zerver_userprofile[0]["is_bot"], False)
        self.assertEqual(zerver_userprofile[0]["is_active"], True)
        self.assertEqual(zerver_userprofile[0]["is_mirror_dummy"], False)
        self.assertEqual(zerver_userprofile[0]["role"], UserProfile.ROLE_MEMBER)
        self.assertEqual(zerver_userprofile[0]["enable_desktop_notifications"], True)
        self.assertEqual(zerver_userprofile[0]["email"], "jon@gmail.com")
        self.assertEqual(zerver_userprofile[0]["full_name"], "John Doe")

        self.assertEqual(
            zerver_userprofile[1]["id"], test_slack_user_id_to_zulip_user_id["U0CBK5KAT"]
        )
        self.assertEqual(zerver_userprofile[1]["role"], UserProfile.ROLE_REALM_OWNER)
        self.assertEqual(zerver_userprofile[1]["is_staff"], False)
        self.assertEqual(zerver_userprofile[1]["is_active"], True)
        self.assertEqual(zerver_userprofile[0]["is_mirror_dummy"], False)

        self.assertEqual(
            zerver_userprofile[2]["id"], test_slack_user_id_to_zulip_user_id["U09TYF5Sk"]
        )
        self.assertEqual(zerver_userprofile[2]["is_bot"], True)
        self.assertEqual(zerver_userprofile[2]["is_active"], True)
        self.assertEqual(zerver_userprofile[2]["is_mirror_dummy"], False)
        self.assertEqual(zerver_userprofile[2]["email"], "bot1@zulipchat.com")
        self.assertEqual(zerver_userprofile[2]["bot_type"], 1)
        self.assertEqual(zerver_userprofile[2]["avatar_source"], "U")

        self.assertEqual(
            zerver_userprofile[3]["id"], test_slack_user_id_to_zulip_user_id["UHSG7OPQN"]
        )
        self.assertEqual(zerver_userprofile[3]["role"], UserProfile.ROLE_MEMBER)
        self.assertEqual(zerver_userprofile[3]["is_staff"], False)
        self.assertEqual(zerver_userprofile[3]["is_active"], False)
        self.assertEqual(zerver_userprofile[3]["email"], "matt.perry@foreignteam.slack.com")
        self.assertEqual(zerver_userprofile[3]["realm"], 1)
        self.assertEqual(zerver_userprofile[3]["full_name"], "Matt Perry")
        self.assertEqual(zerver_userprofile[3]["is_mirror_dummy"], True)
        self.assertEqual(zerver_userprofile[3]["can_forge_sender"], False)

        self.assertEqual(
            zerver_userprofile[4]["id"], test_slack_user_id_to_zulip_user_id["U8VAHEVUY"]
        )
        self.assertEqual(zerver_userprofile[4]["role"], UserProfile.ROLE_GUEST)
        self.assertEqual(zerver_userprofile[4]["is_staff"], False)
        self.assertEqual(zerver_userprofile[4]["is_active"], True)
        self.assertEqual(zerver_userprofile[4]["is_mirror_dummy"], False)

        self.assertEqual(
            zerver_userprofile[5]["id"], test_slack_user_id_to_zulip_user_id["U8X25EBAB"]
        )
        self.assertEqual(zerver_userprofile[5]["role"], UserProfile.ROLE_GUEST)
        self.assertEqual(zerver_userprofile[5]["is_staff"], False)
        self.assertEqual(zerver_userprofile[5]["is_active"], True)
        self.assertEqual(zerver_userprofile[5]["is_mirror_dummy"], False)

        self.assertEqual(
            zerver_userprofile[6]["id"], test_slack_user_id_to_zulip_user_id["U015J7JSE"]
        )
        self.assertEqual(zerver_userprofile[6]["role"], UserProfile.ROLE_REALM_OWNER)
        self.assertEqual(zerver_userprofile[6]["is_staff"], False)
        self.assertEqual(zerver_userprofile[6]["is_active"], True)
        self.assertEqual(zerver_userprofile[6]["is_mirror_dummy"], False)

        self.assertEqual(
            zerver_userprofile[7]["id"], test_slack_user_id_to_zulip_user_id["U1RDFEC80"]
        )
        self.assertEqual(zerver_userprofile[7]["role"], UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.assertEqual(zerver_userprofile[7]["is_staff"], False)
        self.assertEqual(zerver_userprofile[7]["is_active"], True)
        self.assertEqual(zerver_userprofile[7]["is_mirror_dummy"], False)

        # Importer should raise error when user emails are malformed
        bad_email1 = user_data[0]["profile"]["email"] = "jon@gmail,com"
        bad_email2 = user_data[1]["profile"]["email"] = "jane@gmail.m"
        with self.assertRaises(Exception) as e, self.assertLogs(level="INFO"):
            users_to_zerver_userprofile(slack_data_dir, user_data, 1, timestamp, "test_domain")
        error_message = str(e.exception)
        expected_error_message = f"['Invalid email format, please fix the following email(s) and try again: {bad_email1}, {bad_email2}']"
        self.assertEqual(error_message, expected_error_message)

        # Test converting unknown user data format that doesn't have
        # an `avatar_hash` in its user profile.
        self.assertEqual(
            zerver_userprofile[8]["id"], test_slack_user_id_to_zulip_user_id["U1ZYFEC91"]
        )
        self.assertEqual(zerver_userprofile[8]["is_active"], True)
        self.assertEqual(zerver_userprofile[8]["avatar_source"], "G")

        # Test converting Slack's integration bot
        self.assertEqual(
            zerver_userprofile[9]["id"], test_slack_user_id_to_zulip_user_id["U1MBOTC81"]
        )
        self.assertEqual(zerver_userprofile[9]["is_active"], True)
        self.assertEqual(zerver_userprofile[9]["avatar_source"], "U")

        self.assertEqual(
            zerver_userprofile[10]["id"], test_slack_user_id_to_zulip_user_id["U1RDFEC90"]
        )
        self.assertEqual(zerver_userprofile[10]["is_active"], True)
        self.assertEqual(zerver_userprofile[10]["avatar_source"], "G")

    def test_build_defaultstream(self) -> None:
        realm_id = 1
        stream_id = 1
        default_channel_general = build_defaultstream(realm_id, stream_id, 1)
        test_default_channel = {"stream": 1, "realm": 1, "id": 1}
        self.assertDictEqual(test_default_channel, default_channel_general)
        default_channel_general = build_defaultstream(realm_id, stream_id, 1)
        test_default_channel = {"stream": 1, "realm": 1, "id": 1}
        self.assertDictEqual(test_default_channel, default_channel_general)

    def test_build_pm_recipient_sub_from_user(self) -> None:
        zulip_user_id = 3
        recipient_id = 5
        subscription_id = 7
        sub = build_subscription(recipient_id, zulip_user_id, subscription_id)
        recipient = build_recipient(zulip_user_id, recipient_id, Recipient.PERSONAL)

        self.assertEqual(recipient["id"], sub["recipient"])
        self.assertEqual(recipient["type_id"], sub["user_profile"])

        self.assertEqual(recipient["type"], Recipient.PERSONAL)
        self.assertEqual(recipient["type_id"], 3)

        self.assertEqual(sub["recipient"], 5)
        self.assertEqual(sub["id"], 7)
        self.assertEqual(sub["active"], True)

    def test_build_subscription(self) -> None:
        channel_members = ["U061A1R2R", "U061A3E0G", "U061A5N1G", "U064KUGRJ"]
        slack_user_id_to_zulip_user_id = {
            "U061A1R2R": 1,
            "U061A3E0G": 8,
            "U061A5N1G": 7,
            "U064KUGRJ": 5,
        }
        subscription_id_count = 0
        recipient_id = 12
        zerver_subscription: list[dict[str, Any]] = []
        final_subscription_id = get_subscription(
            channel_members,
            zerver_subscription,
            recipient_id,
            slack_user_id_to_zulip_user_id,
            subscription_id_count,
        )
        # sanity checks
        self.assertEqual(final_subscription_id, 4)
        self.assertEqual(zerver_subscription[0]["recipient"], 12)
        self.assertEqual(zerver_subscription[0]["id"], 0)
        self.assertEqual(
            zerver_subscription[0]["user_profile"],
            slack_user_id_to_zulip_user_id[channel_members[0]],
        )
        self.assertEqual(
            zerver_subscription[2]["user_profile"],
            slack_user_id_to_zulip_user_id[channel_members[2]],
        )
        self.assertEqual(zerver_subscription[3]["id"], 3)
        self.assertEqual(zerver_subscription[1]["recipient"], zerver_subscription[3]["recipient"])
        self.assertEqual(zerver_subscription[1]["pin_to_top"], False)

    def test_channels_to_zerver_stream(self) -> None:
        slack_user_id_to_zulip_user_id = {
            "U061A1R2R": 1,
            "U061A3E0G": 8,
            "U061A5N1G": 7,
            "U064KUGRJ": 5,
        }
        zerver_userprofile = [{"id": 1}, {"id": 8}, {"id": 7}, {"id": 5}]
        realm_id = 3
        realm: ZerverFieldsT = {"zerver_userpresence": [], "zerver_realm": [dict()]}
        zerver_realm = realm["zerver_realm"]

        with (
            self.assertLogs(level="INFO"),
            mock.patch(
                "zerver.data_import.slack.SLACK_DEFAULT_ANNOUNCEMENTS_CHANNEL_NAME", "random"
            ),
        ):
            (
                realm,
                added_channels,
                added_mpims,
                dm_members,
                slack_recipient_name_to_zulip_recipient_id,
            ) = channels_to_zerver_stream(
                self.fixture_file_name("", "slack_fixtures"),
                realm_id,
                realm,
                slack_user_id_to_zulip_user_id,
                zerver_userprofile,
            )

        test_added_channels = {
            "sharedchannel": ("C061A0HJG", 3),
            "general": ("C061A0YJG", 1),
            "general1": ("C061A0YJP", 2),
            "random": ("C061A0WJG", 0),
        }
        test_added_mpims = {
            "mpdm-user9--user2--user10-1": ("G9HBG2A5D", 0),
            "mpdm-user6--user7--user4-1": ("G6H1Z0ZPS", 1),
            "mpdm-user4--user1--user5-1": ("G6N944JPL", 2),
        }
        test_dm_members = {
            "DJ47BL849": ("U061A1R2R", "U061A5N1G"),
            "DHX1UP7EG": ("U061A5N1G", "U064KUGRJ"),
            "DK8HSJDHS": ("U061A1R2R", "U064KUGRJ"),
            "DRS3PSLDK": ("U064KUGRJ", "U064KUGRJ"),
        }
        slack_recipient_names = (
            set(slack_user_id_to_zulip_user_id.keys())
            | set(test_added_channels.keys())
            | set(test_added_mpims.keys())
        )

        self.assertDictEqual(test_added_channels, added_channels)
        # zerver defaultstream already tested in helper functions.
        # Note that the `random` stream is archived and thus should
        # not be created as a DefaultStream.
        self.assertEqual(realm["zerver_defaultstream"], [{"id": 0, "realm": 3, "stream": 1}])

        self.assertDictEqual(test_added_mpims, added_mpims)
        self.assertDictEqual(test_dm_members, dm_members)

        # We can't do an assertDictEqual since during the construction of personal
        # recipients, slack_user_id_to_zulip_user_id are iterated in different order in Python 3.5 and 3.6.
        self.assertEqual(
            set(slack_recipient_name_to_zulip_recipient_id.keys()), slack_recipient_names
        )
        self.assertEqual(set(slack_recipient_name_to_zulip_recipient_id.values()), set(range(11)))

        # functioning of zerver subscriptions are already tested in the helper functions
        # This is to check the concatenation of the output lists from the helper functions
        # subscriptions for stream
        zerver_subscription = realm["zerver_subscription"]
        zerver_recipient = realm["zerver_recipient"]
        zerver_stream = realm["zerver_stream"]

        self.assertEqual(self.get_set(zerver_subscription, "recipient"), set(range(11)))
        self.assertEqual(self.get_set(zerver_subscription, "user_profile"), {1, 5, 7, 8})

        self.assertEqual(
            self.get_set(zerver_recipient, "id"), self.get_set(zerver_subscription, "recipient")
        )
        self.assertEqual(self.get_set(zerver_recipient, "type_id"), {0, 1, 2, 3, 5, 7, 8})
        self.assertEqual(self.get_set(zerver_recipient, "type"), {1, 2, 3})

        # stream mapping
        self.assertEqual(zerver_stream[0]["name"], "random")
        self.assertEqual(zerver_stream[0]["deactivated"], True)
        self.assertEqual(zerver_stream[0]["description"], "no purpose")
        self.assertEqual(zerver_stream[0]["invite_only"], False)
        self.assertEqual(zerver_stream[0]["history_public_to_subscribers"], True)
        self.assertEqual(zerver_stream[0]["realm"], realm_id)
        self.assertEqual(zerver_stream[2]["id"], test_added_channels[zerver_stream[2]["name"]][1])

        self.assertEqual(
            zerver_realm[0]["zulip_update_announcements_stream"], zerver_stream[0]["id"]
        )
        self.assertEqual(zerver_realm[0]["new_stream_announcements_stream"], zerver_stream[0]["id"])

        self.assertEqual(self.get_set(realm["zerver_huddle"], "id"), {0, 1, 2})
        self.assertEqual(realm["zerver_userpresence"], [])

    @mock.patch(
        "zerver.data_import.slack.users_to_zerver_userprofile", return_value=[[], [], {}, [], []]
    )
    @mock.patch(
        "zerver.data_import.slack.channels_to_zerver_stream",
        return_value=[{"zerver_stream": []}, {}, {}, {}, {}],
    )
    def test_slack_workspace_to_realm(
        self, mock_channels_to_zerver_stream: mock.Mock, mock_users_to_zerver_userprofile: mock.Mock
    ) -> None:
        realm_id = 1
        user_list: list[dict[str, Any]] = []
        (
            realm,
            slack_user_id_to_zulip_user_id,
            slack_recipient_name_to_zulip_recipient_id,
            added_channels,
            added_mpims,
            dm_members,
            avatar_list,
            em,
        ) = slack_workspace_to_realm(
            "testdomain", realm_id, user_list, "test-realm", "./random_path", {}
        )

        test_zerver_realmdomain = [
            {"realm": realm_id, "allow_subdomains": False, "domain": "testdomain", "id": realm_id}
        ]
        # Functioning already tests in helper functions
        self.assertEqual(slack_user_id_to_zulip_user_id, {})
        self.assertEqual(added_channels, {})
        self.assertEqual(added_mpims, {})
        self.assertEqual(slack_recipient_name_to_zulip_recipient_id, {})
        self.assertEqual(avatar_list, [])

        mock_channels_to_zerver_stream.assert_called_once_with("./random_path", 1, ANY, {}, [])
        passed_realm = mock_channels_to_zerver_stream.call_args_list[0][0][2]
        zerver_realmdomain = passed_realm["zerver_realmdomain"]
        self.assertListEqual(zerver_realmdomain, test_zerver_realmdomain)
        self.assertEqual(
            passed_realm["zerver_realm"][0]["description"], "Organization imported from Slack!"
        )
        self.assertEqual(passed_realm["zerver_userpresence"], [])
        self.assertEqual(passed_realm["import_source"], "slack")
        self.assert_length(passed_realm.keys(), 17)

        self.assertEqual(realm["zerver_stream"], [])
        self.assertEqual(realm["zerver_userprofile"], [])
        self.assertEqual(realm["zerver_realmemoji"], [])
        self.assertEqual(realm["zerver_customprofilefield"], [])
        self.assertEqual(realm["zerver_customprofilefieldvalue"], [])
        self.assert_length(realm.keys(), 5)

    def test_get_message_sending_user(self) -> None:
        message_with_file = {"subtype": "file", "type": "message", "file": {"user": "U064KUGRJ"}}
        message_without_file = {"subtype": "file", "type": "message", "user": "U064KUGRJ"}

        user_file = get_message_sending_user(message_with_file)
        self.assertEqual(user_file, "U064KUGRJ")
        user_without_file = get_message_sending_user(message_without_file)
        self.assertEqual(user_without_file, "U064KUGRJ")

    def test_build_zerver_message(self) -> None:
        zerver_usermessage: list[dict[str, Any]] = []

        # recipient_id -> set of user_ids
        subscriber_map = {
            2: {3, 7, 15, 16},  # these we care about
            4: {12},
            6: {19, 21},
        }

        recipient_id = 2
        mentioned_user_ids = [7]
        message_id = 9

        um_id = NEXT_ID("user_message")

        build_usermessages(
            zerver_usermessage=zerver_usermessage,
            subscriber_map=subscriber_map,
            recipient_id=recipient_id,
            mentioned_user_ids=mentioned_user_ids,
            message_id=message_id,
            is_private=False,
        )

        self.assertEqual(zerver_usermessage[0]["id"], um_id + 1)
        self.assertEqual(zerver_usermessage[0]["message"], message_id)
        self.assertEqual(zerver_usermessage[0]["flags_mask"], 1)

        self.assertEqual(zerver_usermessage[1]["id"], um_id + 2)
        self.assertEqual(zerver_usermessage[1]["message"], message_id)
        self.assertEqual(zerver_usermessage[1]["user_profile"], 7)
        self.assertEqual(zerver_usermessage[1]["flags_mask"], 9)  # mentioned

        self.assertEqual(zerver_usermessage[2]["id"], um_id + 3)
        self.assertEqual(zerver_usermessage[2]["message"], message_id)

        self.assertEqual(zerver_usermessage[3]["id"], um_id + 4)
        self.assertEqual(zerver_usermessage[3]["message"], message_id)

    @mock.patch("zerver.data_import.slack.build_usermessages", return_value=(2, 4))
    def test_channel_message_to_zerver_message(self, mock_build_usermessage: mock.Mock) -> None:
        user_data = [
            {"id": "U066MTL5U", "name": "john doe", "deleted": False, "real_name": "John"},
            {"id": "U061A5N1G", "name": "jane doe", "deleted": False, "real_name": "Jane"},
            {
                "id": "U061A1R2R",
                "name": "jon",
                "deleted": False,
                "real_name": "Jon",
                "profile": {"email": "jon@example.com"},
            },
        ]

        slack_user_id_to_zulip_user_id = {"U066MTL5U": 5, "U061A5N1G": 24, "U061A1R2R": 43}

        reactions = [{"name": "grinning", "users": ["U061A5N1G"], "count": 1}]

        all_messages: list[dict[str, Any]] = [
            {
                "text": "<@U066MTL5U> has joined the channel",
                "subtype": "channel_join",
                "user": "U066MTL5U",
                "ts": "1434139102.000002",
                "channel_name": "random",
            },
            {
                "text": "<@U061A5N1G>: hey!",
                "user": "U061A1R2R",
                "ts": "1437868294.000006",
                "has_image": True,
                "channel_name": "random",
            },
            {
                "text": "random",
                "user": "U061A5N1G",
                "reactions": reactions,
                "ts": "1439868294.000006",
                "channel_name": "random",
            },
            {
                "text": "without a user",
                "user": None,  # this message will be ignored as it has no user
                "ts": "1239868294.000006",
                "channel_name": "general",
            },
            {
                "text": "<http://journals.plos.org/plosone/article>",
                "user": "U061A1R2R",
                "ts": "1463868370.000008",
                "channel_name": "general",
            },
            {
                "text": "added bot",
                "user": "U061A5N1G",
                "subtype": "bot_add",
                "ts": "1433868549.000010",
                "channel_name": "general",
            },
            # This message will be ignored since it has no user and file is None.
            # See #9217 for the situation; likely file uploads on archived channels
            {
                "upload": False,
                "file": None,
                "text": "A file was shared",
                "channel_name": "general",
                "type": "message",
                "ts": "1433868549.000011",
                "subtype": "file_share",
            },
            {
                "text": "random test",
                "user": "U061A1R2R",
                "ts": "1433868669.000012",
                "channel_name": "general",
            },
            {
                "text": "Hello everyone",
                "user": "U061A1R2R",
                "type": "message",
                "ts": "1433868669.000015",
                "mpim_name": "mpdm-user9--user2--user10-1",
            },
            {
                "text": "Who is watching the World Cup",
                "user": "U061A5N1G",
                "type": "message",
                "ts": "1433868949.000015",
                "mpim_name": "mpdm-user6--user7--user4-1",
            },
            {
                "client_msg_id": "998d9229-35aa-424f-8d87-99e00df27dc9",
                "type": "message",
                "text": "Who is coming for camping this weekend?",
                "user": "U061A1R2R",
                "ts": "1553607595.000700",
                "pm_name": "DHX1UP7EG",
            },
            {
                "client_msg_id": "998d9229-35aa-424f-8d87-99e00df27dc9",
                "type": "message",
                "text": "<@U061A5N1G>: Are you in Kochi?",
                "user": "U066MTL5U",
                "ts": "1553607595.000700",
                "pm_name": "DJ47BL849",
            },
            {
                "text": "Look!",
                "user": "U061A1R2R",
                "ts": "1553607596.000700",
                "has_image": True,
                "channel_name": "random",
                "files": [
                    {
                        "url_private": "https://files.slack.com/apple.png",
                        "title": "Apple",
                        "name": "apple.png",
                        "mimetype": "image/png",
                        "timestamp": 9999,
                        "created": 8888,
                        "size": 3000000,
                    }
                ],
            },
        ]

        slack_recipient_name_to_zulip_recipient_id = {
            "random": 2,
            "general": 1,
            "mpdm-user9--user2--user10-1": 5,
            "mpdm-user6--user7--user4-1": 6,
            "U066MTL5U": 7,
            "U061A5N1G": 8,
            "U061A1R2R": 8,
        }
        dm_members = {
            "DJ47BL849": ("U066MTL5U", "U061A5N1G"),
            "DHX1UP7EG": ("U061A5N1G", "U061A1R2R"),
        }

        zerver_usermessage: list[dict[str, Any]] = []
        subscriber_map: dict[int, set[int]] = {}
        added_channels: dict[str, tuple[str, int]] = {"random": ("c5", 1), "general": ("c6", 2)}

        (
            zerver_message,
            zerver_usermessage,
            attachment,
            uploads,
            reaction,
        ) = channel_message_to_zerver_message(
            1,
            user_data,
            slack_user_id_to_zulip_user_id,
            slack_recipient_name_to_zulip_recipient_id,
            all_messages,
            [],
            subscriber_map,
            added_channels,
            dm_members,
            "domain",
            set(),
            convert_slack_threads=False,
        )
        # functioning already tested in helper function
        self.assertEqual(zerver_usermessage, [])
        # subtype: channel_join is filtered
        self.assert_length(zerver_message, 10)

        # Test reactions
        self.assertEqual(reaction[0]["user_profile"], 24)
        self.assertEqual(reaction[0]["emoji_name"], reactions[0]["name"])

        # Message conversion already tested in tests.test_slack_message_conversion
        self.assertEqual(zerver_message[0]["content"], "@**Jane**: hey!")
        self.assertEqual(zerver_message[0]["has_link"], False)
        self.assertEqual(zerver_message[2]["content"], "http://journals.plos.org/plosone/article")
        self.assertEqual(zerver_message[2]["has_link"], True)
        self.assertEqual(zerver_message[5]["has_link"], False)
        self.assertEqual(zerver_message[7]["has_link"], False)

        # Test that topic_name is set to '\x07' for direct messages and
        # group direct messages.
        self.assertEqual(zerver_message[6][EXPORT_TOPIC_NAME], Message.DM_TOPIC)
        self.assertEqual(zerver_message[8][EXPORT_TOPIC_NAME], Message.DM_TOPIC)

        self.assertEqual(zerver_message[3][EXPORT_TOPIC_NAME], "imported from Slack")
        self.assertEqual(zerver_message[3]["content"], "/me added bot")
        self.assertEqual(
            zerver_message[4]["recipient"], slack_recipient_name_to_zulip_recipient_id["general"]
        )
        self.assertEqual(zerver_message[2][EXPORT_TOPIC_NAME], "imported from Slack")
        self.assertEqual(
            zerver_message[1]["recipient"], slack_recipient_name_to_zulip_recipient_id["random"]
        )
        self.assertEqual(
            zerver_message[5]["recipient"],
            slack_recipient_name_to_zulip_recipient_id["mpdm-user9--user2--user10-1"],
        )
        self.assertEqual(
            zerver_message[6]["recipient"],
            slack_recipient_name_to_zulip_recipient_id["mpdm-user6--user7--user4-1"],
        )
        self.assertEqual(
            zerver_message[7]["recipient"], slack_recipient_name_to_zulip_recipient_id["U061A5N1G"]
        )
        self.assertEqual(
            zerver_message[7]["recipient"], slack_recipient_name_to_zulip_recipient_id["U061A5N1G"]
        )

        self.assertEqual(zerver_message[3]["id"], zerver_message[0]["id"] + 3)
        self.assertEqual(zerver_message[4]["id"], zerver_message[0]["id"] + 4)
        self.assertEqual(zerver_message[5]["id"], zerver_message[0]["id"] + 5)
        self.assertEqual(zerver_message[7]["id"], zerver_message[0]["id"] + 7)

        self.assertIsNone(zerver_message[3]["rendered_content"])
        self.assertEqual(zerver_message[0]["has_image"], False)
        self.assertEqual(zerver_message[0]["date_sent"], float(all_messages[1]["ts"]))
        self.assertEqual(zerver_message[2]["rendered_content_version"], 1)

        self.assertEqual(zerver_message[0]["sender"], 43)
        self.assertEqual(zerver_message[3]["sender"], 24)
        self.assertEqual(zerver_message[5]["sender"], 43)
        self.assertEqual(zerver_message[6]["sender"], 24)
        self.assertEqual(zerver_message[7]["sender"], 43)
        self.assertEqual(zerver_message[8]["sender"], 5)

        # Test uploads
        self.assert_length(uploads, 1)
        self.assertEqual(uploads[0]["path"], "https://files.slack.com/apple.png")
        self.assert_length(attachment, 1)
        self.assertEqual(attachment[0]["file_name"], "apple.png")
        self.assertEqual(attachment[0]["is_realm_public"], True)
        self.assertEqual(attachment[0]["is_web_public"], False)
        self.assertEqual(attachment[0]["content_type"], "image/png")

        self.assertEqual(zerver_message[9]["has_image"], True)
        self.assertEqual(zerver_message[9]["has_attachment"], True)
        self.assertTrue(zerver_message[9]["content"].startswith("Look!\n[Apple](/user_uploads/"))

    @mock.patch("zerver.data_import.slack.build_usermessages", return_value=(2, 4))
    def test_channel_message_to_zerver_message_with_threads(
        self, mock_build_usermessage: mock.Mock
    ) -> None:
        user_data = [
            {"id": "U066MTL5U", "name": "john doe", "deleted": False, "real_name": "John"},
            {"id": "U061A5N1G", "name": "jane doe", "deleted": False, "real_name": "Jane"},
            {
                "id": "U061A1R2R",
                "name": "jon",
                "deleted": False,
                "real_name": "Jon",
                "profile": {"email": "jon@example.com"},
            },
        ]

        slack_user_id_to_zulip_user_id = {"U066MTL5U": 5, "U061A5N1G": 24, "U061A1R2R": 43}

        all_messages: list[dict[str, Any]] = [
            {
                "text": "<@U066MTL5U> has joined the channel",
                "subtype": "channel_join",
                "user": "U066MTL5U",
                "ts": "1434139102.000002",
                "channel_name": "random",
            },
            {
                "text": "<@U061A5N1G>: hey!",
                "user": "U061A1R2R",
                "ts": "1437868294.000006",
                "has_image": True,
                "channel_name": "random",
            },
            {
                "text": "message body text",
                "user": "U061A5N1G",
                "ts": "1434139102.000002",
                # Start of thread 1!
                "thread_ts": "1434139102.000002",
                "channel_name": "random",
            },
            {
                "text": "random",
                "user": "U061A5N1G",
                "ts": "1439868294.000007",
                # A reply to thread 1
                "parent_user_id": "U061A5N1G",
                "thread_ts": "1434139102.000002",
                "channel_name": "random",
            },
            {
                "text": "random message but it's too long for the thread topic name",
                "user": "U061A5N1G",
                "ts": "1439868294.000008",
                # Start of thread 2!
                "thread_ts": "1439868294.000008",
                "channel_name": "random",
            },
            {
                "text": "replying to the second thread :)",
                "user": "U061A1R2R",
                "ts": "1439869294.000008",
                # A reply to thread 2
                "parent_user_id": "U061A5N1G",
                "thread_ts": "1439868294.000008",
                "channel_name": "random",
            },
            {
                "text": "message body text",
                "user": "U061A5N1G",
                "ts": "1434139200.000002",
                # Start of thread 3!
                "thread_ts": "1434139200.000002",
                "channel_name": "random",
            },
            {
                "text": "The first reply to the third thread",
                "user": "U061A1R2R",
                "ts": "1439869295.000008",
                # A reply to thread 3!
                "parent_user_id": "U061A5N1G",
                "thread_ts": "1434139200.000002",
                "channel_name": "random",
            },
            {
                "text": "<@U061A1R2R> please reply to this message",
                "user": "U061A5N1G",
                "ts": "1437139200.000002",
                # Start of thread 4!
                "thread_ts": "1437139200.000002",
                "channel_name": "random",
            },
            {
                "text": "Yes?",
                "user": "U061A1R2R",
                "ts": "1440869295.000008",
                # A reply to thread 4!
                "parent_user_id": "U061A5N1G",
                "thread_ts": "1434139200.000002",
                "channel_name": "random",
            },
            {
                "text": "Look!",
                "user": "U061A1R2R",
                "ts": "1537139200.000002",
                # Start of thread 5!
                "thread_ts": "1537139200.000002",
                "has_image": True,
                "channel_name": "random",
                "files": [
                    {
                        "url_private": "https://files.slack.com/apple.png",
                        "title": "Apple",
                        "name": "apple.png",
                        "mimetype": "image/png",
                        "timestamp": 9999,
                        "created": 8888,
                        "size": 3000000,
                    }
                ],
            },
            {
                "text": "Delicious",
                "user": "U061A5N1G",
                "ts": "1637139200.000002",
                # A reply to thread 5!
                "parent_user_id": "U061A1R2R",
                "thread_ts": "1537139200.000002",
                "channel_name": "random",
            },
            {
                "text": "*foo* _bar_ ~baz~ [qux](https://chat.zulip.org)",
                "user": "U061A1R2R",
                "ts": "1547139200.000002",
                # Start of thread 6!
                "thread_ts": "1547139200.000002",
                "channel_name": "random",
            },
            {
                "text": "Delicious",
                "user": "U061A5N1G",
                "ts": "1637139200.000002",
                # A reply to thread 6!
                "parent_user_id": "U061A1R2R",
                "thread_ts": "1547139200.000002",
                "channel_name": "random",
            },
        ]

        slack_recipient_name_to_zulip_recipient_id = {
            "random": 2,
            "general": 1,
        }
        dm_members: DMMembersT = {}

        zerver_usermessage: list[dict[str, Any]] = []
        subscriber_map: dict[int, set[int]] = {}
        added_channels: dict[str, tuple[str, int]] = {"random": ("c5", 1), "general": ("c6", 2)}

        (
            zerver_message,
            zerver_usermessage,
            attachment,
            uploads,
            reaction,
        ) = channel_message_to_zerver_message(
            1,
            user_data,
            slack_user_id_to_zulip_user_id,
            slack_recipient_name_to_zulip_recipient_id,
            all_messages,
            [],
            subscriber_map,
            added_channels,
            dm_members,
            "domain",
            set(),
            convert_slack_threads=True,
        )
        # functioning already tested in helper function
        self.assertEqual(zerver_usermessage, [])
        # subtype: channel_join is filtered
        self.assert_length(zerver_message, 13)

        self.assert_length(uploads, 1)
        self.assert_length(attachment, 1)

        # Message conversion already tested in tests.test_slack_message_conversion
        self.assertEqual(zerver_message[0]["content"], "@**Jane**: hey!")
        self.assertEqual(zerver_message[0]["has_link"], False)
        self.assertEqual(
            zerver_message[1]["recipient"], slack_recipient_name_to_zulip_recipient_id["random"]
        )

        ### THREAD 1 CONVERSATION ###
        # Test thread topic name contains message snippet
        expected_thread_1_message_1_content = "message body text"
        expected_thread_1_topic_name = "2015-06-12 message body text"
        self.assertEqual(zerver_message[1]["content"], expected_thread_1_message_1_content)
        self.assertEqual(zerver_message[1][EXPORT_TOPIC_NAME], expected_thread_1_topic_name)

        # Thread reply is in the correct thread topic
        self.assertEqual(zerver_message[2]["content"], "random")
        self.assertEqual(zerver_message[2][EXPORT_TOPIC_NAME], expected_thread_1_topic_name)

        ### THREAD 2 CONVERSATION ###
        # Test thread topic name cut off
        expected_thread_2_message_1_content = (
            "random message but it's too long for the thread topic name"
        )
        expected_thread_2_topic_name = (
            "2015-08-18 random message but it's too long for the thread …"
        )
        self.assertEqual(zerver_message[3]["content"], expected_thread_2_message_1_content)
        self.assertEqual(zerver_message[3][EXPORT_TOPIC_NAME], expected_thread_2_topic_name)
        # Record that truncation should use the full maximum topic length.
        self.assert_length(zerver_message[3][EXPORT_TOPIC_NAME], 60)

        expected_thread_2_reply_1_message = "replying to the second thread :)"
        self.assertEqual(zerver_message[4]["content"], expected_thread_2_reply_1_message)
        self.assertEqual(zerver_message[4][EXPORT_TOPIC_NAME], expected_thread_2_topic_name)

        ### THREAD 3 CONVERSATION ###
        # Test thread topic name collision
        expected_thread_3_message_1_content = "message body text"
        expected_thread_3_topic_name = "2015-06-12 message body text (2)"
        self.assertEqual(zerver_message[5]["content"], expected_thread_3_message_1_content)
        self.assertEqual(zerver_message[5][EXPORT_TOPIC_NAME], expected_thread_3_topic_name)

        ### THREAD 4 CONVERSATION ###
        # Test mention syntax in thread topic name
        expected_thread_4_message_1_content = "@**Jon** please reply to this message"
        expected_thread_4_topic_name = "2015-07-17 @**Jon** please reply to this message"
        self.assertEqual(zerver_message[7]["content"], expected_thread_4_message_1_content)
        self.assertEqual(zerver_message[7][EXPORT_TOPIC_NAME], expected_thread_4_topic_name)

        ### THREAD 5 CONVERSATION ###
        # Test file link in thread topic name
        expected_thread_4_message_1_content = "Look!\n[Apple](/user_uploads/"
        expected_thread_4_topic_name = "2018-09-16 Look!\n[Apple](/user_uploads/"
        self.assertTrue(
            zerver_message[9]["content"].startswith(expected_thread_4_message_1_content)
        )
        self.assertTrue(
            zerver_message[9][EXPORT_TOPIC_NAME].startswith(expected_thread_4_topic_name)
        )

        ### THREAD 6 CONVERSATION ###
        # Test various formatting syntaxes in thread topic name
        expected_thread_4_message_1_content = "**foo** *bar* ~~baz~~ [qux](https://chat.zulip.org)"
        expected_thread_4_topic_name = (
            "2019-01-10 **foo** *bar* ~~baz~~ [qux](https://chat.zulip.o…"
        )
        self.assertEqual(zerver_message[11]["content"], expected_thread_4_message_1_content)
        self.assertEqual(zerver_message[11][EXPORT_TOPIC_NAME], expected_thread_4_topic_name)

    @mock.patch("zerver.data_import.slack.build_usermessages", return_value=(2, 4))
    def test_channel_message_to_zerver_message_with_integration_bots(
        self, mock_build_usermessage: mock.Mock
    ) -> None:
        """
        Most of the core logic for converting Slack blocks is in slack_incoming/test.py,
        so the purpose for this test is to verify the import tool portion of this system.
        """
        user_data = [
            {"id": "U066MTL5U", "name": "john doe", "deleted": False, "real_name": "John"},
            {"id": "U061A5N1G", "name": "jane doe", "deleted": False, "real_name": "Jane"},
            {
                "id": "B06NWMNUQ3W",  # Bot user
                "name": "ClickUp",
                "deleted": False,
                "real_name": "ClickUp",
            },
        ]

        slack_user_id_to_zulip_user_id = {"U066MTL5U": 5, "U061A5N1G": 24, "B06NWMNUQ3W": 43}

        all_messages: list[dict[str, Any]] = [
            {
                "subtype": "bot_message",
                "text": "",
                "username": "ClickUp",
                "attachments": [
                    {
                        "id": 1,
                        "color": "008844",
                        "fallback": "dsdaddsa",
                        "text": "Added assignee Pieter\n\nby Pieter\n_<https://app.clickup.com/25567147/v/s/43687023|Task one> &gt; <https://app.clickup.com/25567147/v/li/901601846060|dsad>_",
                        "title": "dsdaddsa",
                        "title_link": "https://app.clickup.com/t/86cv0v5my",
                        "mrkdwn_in": ["text"],
                    }
                ],
                "type": "message",
                "ts": "1712027355.830689",
                "bot_id": "B06NWMNUQ3W",
                "app_id": "A3G4A68V9",
                "channel_name": "general",
            },
            {
                "subtype": "bot_message",
                "text": "",
                "username": "ClickUp",
                "attachments": [
                    {
                        "id": 1,
                        "blocks": [
                            {
                                "type": "section",
                                "block_id": "qvtCh",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "<https://app.clickup.com/t/86cv0v5my| dsda>",
                                    "verbatim": False,
                                },
                            },
                            {
                                "type": "section",
                                "block_id": "7LtRa",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Task Created\nBy Pieter\n",
                                    "verbatim": False,
                                },
                            },
                            {
                                "type": "section",
                                "block_id": "XgOBF",
                                "fields": [
                                    {
                                        "type": "mrkdwn",
                                        "text": "_<https://app.clickup.com/25567147/v/s/43687023|Task one> &gt; <https://app.clickup.com/25567147/v/li/901601846060|dsad>_",
                                        "verbatim": False,
                                    }
                                ],
                            },
                        ],
                        "color": "#656f7d",
                        "fallback": "[no preview available]",
                    }
                ],
                "type": "message",
                "ts": "1712026462.647119",
                "bot_id": "B06NWMNUQ3W",
                "app_id": "A3G4A68V9",
                "channel_name": "general",
            },
            {
                "subtype": "bot_message",
                "text": "",
                "username": "ClickUp",
                "attachments": [
                    {
                        "id": 1,
                        "color": "656f7d",
                        "fallback": "Buy Ingredients!",
                        "text": "New comment:  where can I buy it?\n\nby Pieter\n_<https://app.clickup.com/25567147/v/s/43687023|Task one> &gt; <https://app.clickup.com/25567147/v/li/901601846060|dsad>_",
                        "title": "Buy Ingredients!",
                        "title_link": "https://app.clickup.com/t/86cuy8e4y?comment=90160026391938",
                        "mrkdwn_in": ["text"],
                    }
                ],
                "type": "message",
                "ts": "1711032565.114789",
                "bot_id": "B06NWMNUQ3W",
                "app_id": "A3G4A68V9",
                "channel_name": "general",
            },
        ]

        slack_recipient_name_to_zulip_recipient_id = {
            "random": 2,
            "general": 1,
        }
        dm_members: DMMembersT = {}

        zerver_usermessage: list[dict[str, Any]] = []
        subscriber_map: dict[int, set[int]] = {}
        added_channels: dict[str, tuple[str, int]] = {"random": ("c5", 1), "general": ("c6", 2)}

        (
            zerver_message,
            zerver_usermessage,
            attachment,
            uploads,
            reaction,
        ) = channel_message_to_zerver_message(
            1,
            user_data,
            slack_user_id_to_zulip_user_id,
            slack_recipient_name_to_zulip_recipient_id,
            all_messages,
            [],
            subscriber_map,
            added_channels,
            dm_members,
            "domain",
            set(),
            convert_slack_threads=True,
        )
        # functioning already tested in helper function
        self.assertEqual(zerver_usermessage, [])
        # subtype: channel_join is filtered
        self.assert_length(zerver_message, 3)

        self.assertEqual(uploads, [])
        self.assertEqual(attachment, [])

        expected_message_attachment = """## [dsdaddsa](https://app.clickup.com/t/86cv0v5my)

Added assignee Pieter

by Pieter
*[Task one](https://app.clickup.com/25567147/v/s/43687023) &gt; [dsad](https://app.clickup.com/25567147/v/li/901601846060)*
""".strip()
        self.assertEqual(zerver_message[0]["content"], expected_message_attachment)
        self.assertEqual(zerver_message[0]["sender"], slack_user_id_to_zulip_user_id["B06NWMNUQ3W"])

        expected_message_block = """[ dsda](https://app.clickup.com/t/86cv0v5my)

Task Created
By Pieter

*[Task one](https://app.clickup.com/25567147/v/s/43687023) &gt; [dsad](https://app.clickup.com/25567147/v/li/901601846060)*
""".strip()
        self.assertEqual(zerver_message[1]["content"], expected_message_block)
        self.assertEqual(zerver_message[1]["sender"], slack_user_id_to_zulip_user_id["B06NWMNUQ3W"])

        expected_message_block_2 = """## [Buy Ingredients!](https://app.clickup.com/t/86cuy8e4y?comment=90160026391938)

New comment:  where can I buy it?

by Pieter
*[Task one](https://app.clickup.com/25567147/v/s/43687023) &gt; [dsad](https://app.clickup.com/25567147/v/li/901601846060)*
""".strip()
        self.assertEqual(zerver_message[2]["content"], expected_message_block_2)
        self.assertEqual(zerver_message[2]["sender"], slack_user_id_to_zulip_user_id["B06NWMNUQ3W"])

    @mock.patch("zerver.data_import.slack.channel_message_to_zerver_message")
    @mock.patch("zerver.data_import.slack.get_messages_iterator")
    def test_convert_slack_workspace_messages(
        self, mock_get_messages_iterator: mock.Mock, mock_message: mock.Mock
    ) -> None:
        output_dir = os.path.join(settings.TEST_WORKER_DIR, "test-slack-import")
        os.makedirs(output_dir, exist_ok=True)

        added_channels: dict[str, tuple[str, int]] = {"random": ("c5", 1), "general": ("c6", 2)}

        time = float(timezone_now().timestamp())
        zerver_message = [{"id": 1, "ts": time}, {"id": 5, "ts": time}]

        def fake_get_messages_iter(
            slack_data_dir: str,
            added_channels: AddedChannelsT,
            added_mpims: AddedMPIMsT,
            dm_members: DMMembersT,
        ) -> Iterator[ZerverFieldsT]:
            import copy

            return iter(copy.deepcopy(zerver_message))

        realm: dict[str, Any] = {"zerver_subscription": []}
        user_list: list[dict[str, Any]] = []
        reactions = [{"name": "grinning", "users": ["U061A5N1G"], "count": 1}]
        attachments: list[dict[str, Any]] = []
        uploads: list[dict[str, Any]] = []

        zerver_usermessage = [{"id": 3}, {"id": 5}, {"id": 6}, {"id": 9}]

        mock_get_messages_iterator.side_effect = fake_get_messages_iter
        mock_message.side_effect = [
            [zerver_message[:1], zerver_usermessage[:2], attachments, uploads, reactions[:1]],
            [zerver_message[1:2], zerver_usermessage[2:5], attachments, uploads, reactions[1:1]],
        ]

        with self.assertLogs(level="INFO"):
            # Hacky: We should include a zerver_userprofile, not the empty []
            test_reactions, uploads, zerver_attachment = convert_slack_workspace_messages(
                "./random_path",
                user_list,
                2,
                {},
                {},
                added_channels,
                {},
                {},
                realm,
                [],
                [],
                "domain",
                output_dir=output_dir,
                convert_slack_threads=False,
                chunk_size=1,
            )

        messages_file_1 = os.path.join(output_dir, "messages-000001.json")
        self.assertTrue(os.path.exists(messages_file_1))
        messages_file_2 = os.path.join(output_dir, "messages-000002.json")
        self.assertTrue(os.path.exists(messages_file_2))

        with open(messages_file_1, "rb") as f:
            message_json = orjson.loads(f.read())
        self.assertEqual(message_json["zerver_message"], zerver_message[:1])
        self.assertEqual(message_json["zerver_usermessage"], zerver_usermessage[:2])

        with open(messages_file_2, "rb") as f:
            message_json = orjson.loads(f.read())
        self.assertEqual(message_json["zerver_message"], zerver_message[1:2])
        self.assertEqual(message_json["zerver_usermessage"], zerver_usermessage[2:5])

        self.assertEqual(test_reactions, reactions)

    @mock.patch("zerver.data_import.slack.requests.get")
    @mock.patch("zerver.data_import.slack.process_uploads", return_value=[])
    @mock.patch("zerver.data_import.slack.build_attachment", return_value=[])
    @mock.patch("zerver.data_import.slack.build_avatar_url", return_value=("", ""))
    @mock.patch("zerver.data_import.slack.build_avatar")
    @mock.patch("zerver.data_import.slack.get_slack_api_data")
    @mock.patch("zerver.data_import.slack.check_token_access")
    def test_slack_import_to_existing_database(
        self,
        mock_check_token_access: mock.Mock,
        mock_get_slack_api_data: mock.Mock,
        mock_build_avatar_url: mock.Mock,
        mock_build_avatar: mock.Mock,
        mock_process_uploads: mock.Mock,
        mock_attachment: mock.Mock,
        mock_requests_get: mock.Mock,
    ) -> None:
        test_slack_dir = os.path.join(
            settings.DEPLOY_ROOT, "zerver", "tests", "fixtures", "slack_fixtures"
        )
        test_slack_zip_file = os.path.join(test_slack_dir, "test_slack_importer.zip")
        test_slack_unzipped_file = os.path.join(test_slack_dir, "test_slack_importer")

        test_realm_subdomain = "test-slack-import"
        output_dir = os.path.join(settings.DEPLOY_ROOT, "var", "test-slack-importer-data")
        token = "xoxb-valid-token"

        # If the test fails, the 'output_dir' would not be deleted and hence it would give an
        # error when we run the tests next time, as 'do_convert_data' expects an empty 'output_dir'
        # hence we remove it before running 'do_convert_data'
        self.rm_tree(output_dir)
        # Also the unzipped data file should be removed if the test fails at 'do_convert_data'
        self.rm_tree(test_slack_unzipped_file)

        user_data_fixture = orjson.loads(self.fixture_data("user_data.json", type="slack_fixtures"))
        team_info_fixture = orjson.loads(self.fixture_data("team_info.json", type="slack_fixtures"))
        mock_get_slack_api_data.side_effect = [
            user_data_fixture["members"],
            {},
            team_info_fixture["team"],
        ]
        mock_requests_get.return_value.raw = BytesIO(read_test_image_file("img.png"))
        mock_requests_get.return_value.headers = {"Content-Type": "image/png"}

        with self.assertLogs(level="INFO"), self.settings(EXTERNAL_HOST="zulip.example.com"):
            # We need to mock EXTERNAL_HOST to be a valid domain because Slack's importer
            # uses it to generate email addresses for users without an email specified.
            do_convert_zipfile(test_slack_zip_file, output_dir, token)

        self.assertTrue(os.path.exists(output_dir))
        self.assertTrue(os.path.exists(output_dir + "/realm.json"))
        self.assertTrue(os.path.exists(output_dir + "/migration_status.json"))

        realm_icons_path = os.path.join(output_dir, "realm_icons")
        realm_icon_records_path = os.path.join(realm_icons_path, "records.json")

        self.assertTrue(os.path.exists(realm_icon_records_path))
        with open(realm_icon_records_path, "rb") as f:
            records = orjson.loads(f.read())
            self.assert_length(records, 2)
            self.assertEqual(records[0]["path"], "0/icon.original")
            self.assertTrue(os.path.exists(os.path.join(realm_icons_path, records[0]["path"])))

            self.assertEqual(records[1]["path"], "0/icon.png")
            self.assertTrue(os.path.exists(os.path.join(realm_icons_path, records[1]["path"])))

        # test import of the converted slack data into an existing database
        with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
            do_import_realm(output_dir, test_realm_subdomain)
        realm = get_realm(test_realm_subdomain)
        self.assertTrue(realm.name, test_realm_subdomain)
        self.assertEqual(realm.icon_source, Realm.ICON_UPLOADED)

        # test RealmAuditLog
        realmauditlog = RealmAuditLog.objects.filter(realm=realm)
        realmauditlog_event_type = {log.event_type for log in realmauditlog}
        self.assertEqual(
            realmauditlog_event_type,
            {
                AuditLogEventType.SUBSCRIPTION_CREATED,
                AuditLogEventType.REALM_PLAN_TYPE_CHANGED,
                AuditLogEventType.REALM_PROPERTY_CHANGED,
                AuditLogEventType.REALM_CREATED,
                AuditLogEventType.REALM_IMPORTED,
                AuditLogEventType.USER_GROUP_CREATED,
                AuditLogEventType.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
                AuditLogEventType.USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED,
                AuditLogEventType.USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED,
            },
        )

        self.assertEqual(Message.objects.filter(realm=realm).count(), 96)

        # All auth backends are enabled initially.
        self.assertTrue(all(realm.authentication_methods_dict().values()))

        Realm.objects.filter(name=test_realm_subdomain).delete()

        remove_folder(output_dir)
        self.assertFalse(os.path.exists(output_dir))

    def test_message_files(self) -> None:
        alice_id = 7
        alice = dict(
            id=alice_id,
            profile=dict(
                email="alice@example.com",
            ),
        )
        files = [
            dict(
                url_private="https://files.slack.com/apple.png",
                title="Apple",
                name="apple.png",
                mimetype="image/png",
                timestamp=9999,
                created=8888,
                size=3000000,
            ),
            dict(
                url_private="https://example.com/banana.zip",
                title="banana",
            ),
        ]
        message = dict(
            user=alice_id,
            files=files,
        )
        domain_name = "example.com"
        realm_id = 5
        message_id = 99
        slack_user_id = "alice"
        users = [alice]
        slack_user_id_to_zulip_user_id = {
            "alice": alice_id,
        }

        zerver_attachment: list[dict[str, Any]] = []
        uploads_list: list[dict[str, Any]] = []

        info = process_message_files(
            message=message,
            domain_name=domain_name,
            realm_id=realm_id,
            message_id=message_id,
            slack_user_id=slack_user_id,
            users=users,
            slack_user_id_to_zulip_user_id=slack_user_id_to_zulip_user_id,
            zerver_attachment=zerver_attachment,
            uploads_list=uploads_list,
        )
        self.assert_length(zerver_attachment, 1)
        self.assert_length(uploads_list, 1)

        image_path = zerver_attachment[0]["path_id"]
        expected_content = (
            f"[Apple](/user_uploads/{image_path})\n[banana](https://example.com/banana.zip)"
        )
        self.assertEqual(info["content"], expected_content)

        self.assertTrue(info["has_link"])
        self.assertTrue(info["has_image"])

        self.assertEqual(uploads_list[0]["s3_path"], image_path)
        self.assertEqual(uploads_list[0]["realm_id"], realm_id)
        self.assertEqual(uploads_list[0]["user_profile_email"], "alice@example.com")

    def test_bot_duplicates(self) -> None:
        self.assertEqual(
            SlackBotEmail.get_email(
                {"real_name_normalized": "Real Bot", "bot_id": "foo"}, "example.com"
            ),
            "real-bot@example.com",
        )

        # SlackBotEmail keeps state -- doing it again appends a "2", "3", etc
        self.assertEqual(
            SlackBotEmail.get_email(
                {"real_name_normalized": "Real Bot", "bot_id": "bar"}, "example.com"
            ),
            "real-bot-2@example.com",
        )
        self.assertEqual(
            SlackBotEmail.get_email(
                {"real_name_normalized": "Real Bot", "bot_id": "baz"}, "example.com"
            ),
            "real-bot-3@example.com",
        )

        # But caches based on the bot_id
        self.assertEqual(
            SlackBotEmail.get_email(
                {"real_name_normalized": "Real Bot", "bot_id": "foo"}, "example.com"
            ),
            "real-bot@example.com",
        )

        self.assertEqual(
            SlackBotEmail.get_email({"first_name": "Other Name", "bot_id": "other"}, "example.com"),
            "othername-bot@example.com",
        )

    def test_slack_emoji_name_to_codepoint(self) -> None:
        self.assertEqual(slack_emoji_name_to_codepoint["thinking_face"], "1f914")
        self.assertEqual(slack_emoji_name_to_codepoint["tophat"], "1f3a9")
        self.assertEqual(slack_emoji_name_to_codepoint["dog2"], "1f415")
        self.assertEqual(slack_emoji_name_to_codepoint["dog"], "1f436")

    @mock.patch("zerver.data_import.slack.requests.get")
    @mock.patch("zerver.data_import.slack.process_uploads", return_value=[])
    @mock.patch("zerver.data_import.slack.build_attachment", return_value=[])
    @mock.patch("zerver.data_import.slack.build_avatar_url", return_value=("", ""))
    @mock.patch("zerver.data_import.slack.build_avatar")
    @mock.patch("zerver.data_import.slack.get_slack_api_data")
    @mock.patch("zerver.data_import.slack.check_token_access")
    def test_slack_import_unicode_filenames(
        self,
        mock_check_token_access: mock.Mock,
        mock_get_slack_api_data: mock.Mock,
        mock_build_avatar_url: mock.Mock,
        mock_build_avatar: mock.Mock,
        mock_process_uploads: mock.Mock,
        mock_attachment: mock.Mock,
        mock_requests_get: mock.Mock,
    ) -> None:
        test_slack_dir = os.path.join(
            settings.DEPLOY_ROOT, "zerver", "tests", "fixtures", "slack_fixtures"
        )
        test_slack_zip_file = os.path.join(test_slack_dir, "test_unicode_slack_importer.zip")
        test_slack_unzipped_file = os.path.join(test_slack_dir, "test_unicode_slack_importer")
        output_dir = os.path.join(settings.DEPLOY_ROOT, "var", "test-unicode-slack-importer-data")
        token = "xoxb-valid-token"

        # If the test fails, the 'output_dir' would not be deleted and hence it would give an
        # error when we run the tests next time, as 'do_convert_data' expects an empty 'output_dir'
        # hence we remove it before running 'do_convert_data'
        self.rm_tree(output_dir)
        # Also the unzipped data file should be removed if the test fails at 'do_convert_data'
        self.rm_tree(test_slack_unzipped_file)

        user_data_fixture = orjson.loads(
            self.fixture_data("unicode_user_data.json", type="slack_fixtures")
        )
        team_info_fixture = orjson.loads(
            self.fixture_data("unicode_team_info.json", type="slack_fixtures")
        )
        mock_get_slack_api_data.side_effect = [
            user_data_fixture["members"],
            {},
            team_info_fixture["team"],
        ]
        mock_requests_get.return_value.raw = BytesIO(read_test_image_file("img.png"))

        with self.assertLogs(level="INFO"), self.settings(EXTERNAL_HOST="zulip.example.com"):
            # We need to mock EXTERNAL_HOST to be a valid domain because Slack's importer
            # uses it to generate email addresses for users without an email specified.
            do_convert_zipfile(test_slack_zip_file, output_dir, token)

    @mock.patch("zerver.data_import.slack.check_token_access")
    @responses.activate
    def test_end_to_end_slack_import(
        self,
        mock_check_token_access: mock.Mock,
    ) -> None:
        # Choose import from slack
        email = "ete-slack-import@zulip.com"
        string_id = "ete-slack-import"
        result = self.submit_realm_creation_form(
            email,
            realm_subdomain=string_id,
            realm_name="Slack import end to end",
            import_from="slack",
        )

        # Confirm email
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                "/accounts/new/send_confirm/?email=ete-slack-import%40zulip.com&realm_name=Slack+import+end+to+end&realm_type=10&realm_default_language=en&realm_subdomain=ete-slack-import"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        prereg_realm = PreregistrationRealm.objects.get(email=email)
        self.assertEqual(prereg_realm.name, "Slack import end to end")
        self.assertEqual(prereg_realm.data_import_metadata["import_from"], "slack")

        # Redirect to slack data import form
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assert_in_success_response(["new/import/slack"], result)

        confirmation_key = find_key_by_email(email)
        assert confirmation_key is not None

        # Check that the we show an error message if the token is invalid.
        mock_check_token_access.side_effect = ValueError("Invalid slack token")
        result = self.client_post(
            "/new/import/slack/",
            {
                "key": confirmation_key,
                "slack_access_token": "xoxb-invalid-token",
            },
        )
        self.assert_in_response("Invalid slack token", result)
        mock_check_token_access.side_effect = None

        # Mock slack API response and mark token as valid
        access_token = "xoxb-valid-token"
        slack_team_info_url = "https://slack.com/api/team.info"
        responses.add_callback(
            responses.GET,
            slack_team_info_url,
            callback=lambda _: (
                200,
                {"x-oauth-scopes": "emoji:read,users:read,users:read.email,team:read"},
                orjson.dumps({"ok": True}),
            ),
        )

        result = self.client_post(
            "/new/import/slack/",
            {
                "key": confirmation_key,
                "slack_access_token": access_token,
            },
        )
        self.assertEqual(result.status_code, 200)
        prereg_realm.refresh_from_db()
        self.assertEqual(prereg_realm.data_import_metadata["import_from"], "slack")
        self.assertEqual(prereg_realm.data_import_metadata["slack_access_token"], access_token)

        # Assume user uploaded a file.
        prereg_realm.data_import_metadata["uploaded_import_file_name"] = "test_slack_importer.zip"
        prereg_realm.save()

        # Check that deferred_work for import is queued.
        with mock.patch("zerver.views.registration.queue_json_publish_rollback_unsafe") as m:
            result = self.client_post(
                "/new/import/slack/",
                {
                    "key": confirmation_key,
                    "start_slack_import": "true",
                },
            )
            self.assert_in_success_response(["Import progress"], result)
            prereg_realm.refresh_from_db()
            self.assertTrue(prereg_realm.data_import_metadata["is_import_work_queued"])

        m.assert_called_once_with(
            "deferred_work",
            {
                "type": "import_slack_data",
                "preregistration_realm_id": prereg_realm.id,
                "filename": f"import/{prereg_realm.id}/slack.zip",
                "slack_access_token": access_token,
            },
        )

        # We don't want to test to whole realm import process here but only that
        # realm import calls are made with correct arguments and different cases
        # are handled well.
        realm = do_create_realm(
            string_id=prereg_realm.string_id,
            name=prereg_realm.name,
        )
        with (
            mock.patch(
                "zerver.actions.data_import.save_attachment_contents"
            ) as mocked_save_attachment,
            mock.patch("zerver.actions.data_import.do_convert_zipfile") as mocked_convert_zipfile,
            mock.patch(
                "zerver.actions.data_import.do_import_realm", return_value=realm
            ) as mocked_import_realm,
        ):
            from zerver.lib.queue import queue_json_publish_rollback_unsafe

            queue_json_publish_rollback_unsafe(
                "deferred_work",
                {
                    "type": "import_slack_data",
                    "preregistration_realm_id": prereg_realm.id,
                    "filename": f"import/{prereg_realm.id}/slack.zip",
                    "slack_access_token": access_token,
                },
            )
        self.assertTrue(mocked_save_attachment.called)
        self.assertTrue(mocked_convert_zipfile.called)
        self.assertTrue(mocked_import_realm.called)
        realm.refresh_from_db()
        self.assertEqual(realm.org_type, prereg_realm.org_type)
        self.assertEqual(realm.default_language, prereg_realm.default_language)
        prereg_realm.refresh_from_db()
        self.assertTrue(prereg_realm.data_import_metadata["need_select_realm_owner"])

        # Confirmation key at this point is marked, used but since we
        # are mocking the process, we need to do it manually here.
        get_object_from_key(confirmation_key, [Confirmation.REALM_CREATION], mark_object_used=True)
        result = self.client_get(f"/json/realm/import/status/{confirmation_key}")
        self.assert_in_success_response(["No users matching provided email"], result)

        # Create a user who become the realm owner, ideally this will be created
        # as part of the import process or we will add form for user to do so.
        imported_user_to_be_owner = UserProfile.objects.create(realm=realm, delivery_email=email)
        imported_user_to_be_owner.set_unusable_password()
        imported_user_to_be_owner.save()

        def post_process_request(key: str | None = confirmation_key) -> "TestHttpResponse":
            return self.client_post(
                f"/realm/import/post_process/{key}",
                {
                    "user_id": str(imported_user_to_be_owner.id),
                },
            )

        # Show error on using wrong confirmation key.
        with mock.patch(
            "zerver.views.registration.render_confirmation_key_error",
            return_value=HttpResponse(status=200),
        ) as m:
            post_process_request("malformed_key")
            m.assert_called_once()

        # Check if we cannot find the realm, preregistration_realm is revoked.
        prereg_realm.string_id = "non_existent_realm"
        prereg_realm.save()
        result = post_process_request()
        prereg_realm.refresh_from_db()
        self.assertEqual(prereg_realm.status, confirmation_settings.STATUS_REVOKED)

        # Reset status for further tests.
        prereg_realm.string_id = string_id
        prereg_realm.status = 0
        prereg_realm.save()

        # Redirect user to password reset page on successful import.
        result = post_process_request()
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith(
                "http://ete-slack-import.testserver/accounts/password/reset/"
            )
        )

        # If user refreshes the page, redirect to login page if the import was successful.
        result = self.client_get(f"/realm/import/post_process/{confirmation_key}")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://ete-slack-import.testserver/accounts/login/")

        # Check if we render a form for user to select a user if there
        # are no users matching the provided email.
        prereg_realm.data_import_metadata["need_select_realm_owner"] = True
        prereg_realm.save()
        result = self.client_get(f"/realm/import/post_process/{confirmation_key}")
        self.assert_in_success_response(["Select your account"], result)

        # Check that user is redirected to this form using email confirmation link.
        result = self.client_get(confirmation_url)
        self.assert_in_success_response(["new/import/slack"], result)
        result = self.client_post(
            "/new/import/slack/",
            {
                "key": confirmation_key,
                "slack_access_token": access_token,
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"/realm/import/post_process/{confirmation_key}")
        result = self.client_get(f"/realm/import/post_process/{confirmation_key}")
        self.assert_in_success_response(["Select your account"], result)

    @mock.patch("zerver.actions.data_import.do_import_realm")
    @mock.patch("zerver.actions.data_import.do_convert_zipfile")
    @mock.patch("zerver.actions.data_import.save_attachment_contents")
    def test_import_slack_data_found_user_matching_email_of_importer(
        self,
        mock_save_attachment_contents: mock.Mock,
        mock_do_convert_zipfile: mock.Mock,
        mock_do_import_realm: mock.Mock,
    ) -> None:
        prereg_realm = PreregistrationRealm.objects.create(
            string_id="test-realm-slack-import",
            name="Test Realm",
            email="test_import_slack_data_user@example.com",
            data_import_metadata={"import_from": "slack"},
        )
        mock_realm = do_create_realm(
            string_id=prereg_realm.string_id,
            name=prereg_realm.name,
        )
        mock_do_import_realm.return_value = mock_realm

        importing_user = UserProfile.objects.create(
            realm=mock_realm,
            delivery_email=prereg_realm.email,
        )

        event = {
            "preregistration_realm_id": prereg_realm.id,
            "filename": "import/test/slack.zip",
            "slack_access_token": "xoxb-valid-token",
        }

        import_slack_data(event)

        mock_save_attachment_contents.assert_called_once()
        mock_do_convert_zipfile.assert_called_once_with(
            mock.ANY, mock.ANY, event["slack_access_token"]
        )
        mock_do_import_realm.assert_called_once_with(mock.ANY, prereg_realm.string_id)

        prereg_realm.refresh_from_db()
        self.assertEqual(prereg_realm.status, 1)  # STATUS_USED
        self.assertEqual(prereg_realm.created_realm, mock_realm)
        self.assertFalse(prereg_realm.data_import_metadata["is_import_work_queued"])
        self.assertFalse(prereg_realm.data_import_metadata.get("need_select_realm_owner"))

        # Check that the importing user was made the realm owner
        importing_user.refresh_from_db()
        self.assertEqual(importing_user.role, UserProfile.ROLE_REALM_OWNER)

    @mock.patch("zerver.actions.data_import.do_import_realm")
    @mock.patch("zerver.actions.data_import.do_convert_zipfile")
    @mock.patch("zerver.actions.data_import.save_attachment_contents")
    def test_import_slack_data_failure_cleanup_realm_not_created(
        self,
        mock_save_attachment_contents: mock.Mock,
        mock_do_convert_zipfile: mock.Mock,
        mock_do_import_realm: mock.Mock,
    ) -> None:
        prereg_realm = PreregistrationRealm.objects.create(
            string_id="test-realm",
            name="Test Realm",
            email="test@example.com",
            data_import_metadata={"import_from": "slack"},
        )
        mock_do_import_realm.side_effect = SlackImportInvalidFileError("Invalid file")

        event = {
            "preregistration_realm_id": prereg_realm.id,
            "filename": "import/test/slack.zip",
            "slack_access_token": "xoxb-valid-token",
        }

        with (
            self.assertRaises(SlackImportInvalidFileError),
            self.assertLogs("zerver.actions.data_import", "ERROR"),
        ):
            import_slack_data(event)

        prereg_realm.refresh_from_db()
        self.assertIsNone(prereg_realm.created_realm)
        self.assertFalse(prereg_realm.data_import_metadata["is_import_work_queued"])
        self.assertEqual(
            prereg_realm.data_import_metadata["invalid_file_error_message"], "Invalid file"
        )
        self.assertFalse(Realm.objects.filter(string_id="test-realm").exists())

    @mock.patch("zerver.actions.data_import.do_import_realm")
    @mock.patch("zerver.actions.data_import.do_convert_zipfile")
    @mock.patch("zerver.actions.data_import.save_attachment_contents")
    def test_import_slack_data_failure_cleanup_realm_created(
        self,
        mock_save_attachment_contents: mock.Mock,
        mock_do_convert_zipfile: mock.Mock,
        mock_do_import_realm: mock.Mock,
    ) -> None:
        prereg_realm = PreregistrationRealm.objects.create(
            string_id="test-realm",
            name="Test Realm",
            email="test@example.com",
            data_import_metadata={"import_from": "slack"},
        )
        do_create_realm(
            string_id=prereg_realm.string_id,
            name=prereg_realm.name,
        )
        self.assertTrue(Realm.objects.filter(string_id=prereg_realm.string_id).exists())
        mock_do_import_realm.side_effect = AssertionError("Import failed")
        event = {
            "preregistration_realm_id": prereg_realm.id,
            "filename": "import/test/slack.zip",
            "slack_access_token": "xoxb-valid-token",
        }

        with (
            self.assertRaises(AssertionError),
            self.assertLogs("zerver.actions.data_import", "ERROR"),
        ):
            import_slack_data(event)

        prereg_realm.refresh_from_db()
        self.assertIsNone(prereg_realm.created_realm)
        self.assertFalse(prereg_realm.data_import_metadata["is_import_work_queued"])
        self.assertFalse(Realm.objects.filter(string_id=prereg_realm.string_id).exists())

    @responses.activate
    def test_cancel_realm_import(self) -> None:
        # Choose import from slack
        email = "ete-slack-import@zulip.com"
        self.submit_realm_creation_form(
            email,
            realm_subdomain="ete-slack-import",
            realm_name="Slack import end to end",
            import_from="slack",
        )
        prereg_realm = PreregistrationRealm.objects.get(email=email)
        self.assertEqual(prereg_realm.data_import_metadata["import_from"], "slack")

        # If the import is already in process, don't allow import cancellation.
        prereg_realm.data_import_metadata["is_import_work_queued"] = True
        prereg_realm.save()

        confirmation_key = find_key_by_email(email)
        assert confirmation_key is not None
        response = self.client_post(
            "/new/import/slack/",
            {
                "key": confirmation_key,
                "cancel_import": "true",
            },
        )
        self.assert_in_success_response(["Unable to cancel import"], response)
        prereg_realm.refresh_from_db()
        self.assertTrue(prereg_realm.data_import_metadata["is_import_work_queued"])

        # Allow cancellation if the import work is not queued.
        prereg_realm.data_import_metadata["is_import_work_queued"] = False
        prereg_realm.save()
        response = self.client_post(
            "/new/import/slack/",
            {
                "key": confirmation_key,
                "cancel_import": "true",
            },
        )

        prereg_realm.refresh_from_db()
        self.assertIsNone(prereg_realm.data_import_metadata.get("import_from"))

    @responses.activate
    def test_cancel_realm_import_realm_created(self) -> None:
        # If user cancelled import after realm was created,
        # clean up the created realm.
        email = "ete-slack-import@zulip.com"
        self.submit_realm_creation_form(
            email,
            realm_subdomain="ete-slack-import",
            realm_name="Slack import end to end",
            import_from="slack",
        )
        prereg_realm = PreregistrationRealm.objects.get(email=email)
        self.assertEqual(prereg_realm.data_import_metadata["import_from"], "slack")
        realm = do_create_realm(
            string_id=prereg_realm.string_id,
            name=prereg_realm.name,
        )
        self.assertTrue(Realm.objects.filter(string_id=prereg_realm.string_id).exists())
        prereg_realm.created_realm = realm
        prereg_realm.save()

        confirmation_key = find_key_by_email(email)
        assert confirmation_key is not None
        # We don't allow cancellation if the complete import work is done.
        with self.assertRaises(AssertionError), self.assertLogs("django.request", "ERROR"):
            self.client_post(
                "/new/import/slack/",
                {
                    "key": confirmation_key,
                    "cancel_import": "true",
                },
            )
