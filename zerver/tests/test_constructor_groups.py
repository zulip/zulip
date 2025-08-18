from unittest.mock import Mock, patch

import orjson
from django.test import override_settings
from typing_extensions import override

from zerver.lib.test_classes import ZulipTestCase
from zerver.views.video_calls import ConstructorGroupsService


class ConstructorGroupsServiceTest(ZulipTestCase):
    @patch("zerver.views.video_calls.settings.CONSTRUCTOR_GROUPS_URL", None)
    def test_not_configured_url(self) -> None:
        """Test service correctly detects missing URL configuration"""
        self.assertFalse(ConstructorGroupsService._is_configured())

    @patch("zerver.views.video_calls.settings.CONSTRUCTOR_GROUPS_ACCESS_KEY", None)
    def test_not_configured_access_key(self) -> None:
        """Test service correctly detects missing access key configuration"""
        self.assertFalse(ConstructorGroupsService._is_configured())

    @patch("zerver.views.video_calls.settings.CONSTRUCTOR_GROUPS_SECRET_KEY", None)
    def test_not_configured_secret_key(self) -> None:
        """Test service correctly detects missing secret key configuration"""
        self.assertFalse(ConstructorGroupsService._is_configured())

    @patch(
        "zerver.views.video_calls.settings.CONSTRUCTOR_GROUPS_URL",
        "https://constructor.app/api/groups/xapi-public",
    )
    @patch("zerver.views.video_calls.settings.CONSTRUCTOR_GROUPS_ACCESS_KEY", "test-access-key")
    @patch("zerver.views.video_calls.settings.CONSTRUCTOR_GROUPS_SECRET_KEY", "test-secret-key")
    def test_configured_correctly(self) -> None:
        """Test service correctly detects complete configuration"""
        self.assertTrue(ConstructorGroupsService._is_configured())


@override_settings(
    CONSTRUCTOR_GROUPS_URL="https://constructor.app/api/groups/xapi-public",
    CONSTRUCTOR_GROUPS_ACCESS_KEY="test-access-key",
    CONSTRUCTOR_GROUPS_SECRET_KEY="test-secret-key",
)
class ConstructorGroupsCallTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("hamlet")
        self.login_user(self.user_profile)

    @patch("zerver.views.video_calls.ConstructorGroupsService._is_configured")
    def test_not_configured_error(self, mock_configured: Mock) -> None:
        """Test error when Constructor Groups is not configured"""
        mock_configured.return_value = False

        response = self.client_post(
            "/json/calls/constructorgroups/create", {"is_video_call": orjson.dumps(True).decode()}
        )

        self.assert_json_error(response, "Constructor Groups is not configured.")

    @patch("zerver.views.video_calls.ConstructorGroupsService._make_authenticated_request")
    @patch("zerver.views.video_calls.ConstructorGroupsService._is_configured")
    def test_existing_room_reuse(self, mock_configured: Mock, mock_request: Mock) -> None:
        """Test finding and reusing existing room"""
        mock_configured.return_value = True
        mock_request.return_value = {
            "data": [
                {
                    "room_guid": "room-123",
                    "name": "King Hamlet's Zulip Videoconferencing Room",
                    "url": "https://constructor.app/groups/room/room-123",
                }
            ]
        }

        response = self.client_post(
            "/json/calls/constructorgroups/create", {"is_video_call": orjson.dumps(True).decode()}
        )

        response_dict = self.assert_json_success(response)
        self.assertEqual(response_dict["url"], "https://constructor.app/groups/room/room-123")

        # Verify search was called with correct parameters
        room_name_pattern = f"{self.user_profile.full_name}'s Zulip Videoconferencing Room"
        mock_request.assert_called_once_with(
            "GET",
            "/room/search",
            {
                "query": room_name_pattern,
                "creator_email": self.user_profile.delivery_email,
                "page": 1,
                "size": 1,
            },
        )

    @patch("zerver.views.video_calls.ConstructorGroupsService._make_authenticated_request")
    @patch("zerver.views.video_calls.ConstructorGroupsService._is_configured")
    def test_create_new_room(self, mock_configured: Mock, mock_request: Mock) -> None:
        """Test creating new room when none exists"""
        mock_configured.return_value = True

        # First call (search) returns empty, second call (create) returns new room
        mock_request.side_effect = [
            {"data": []},  # Search returns no rooms
            {  # Create returns new room
                "room_guid": "room-456",
                "name": "King Hamlet's Zulip Videoconferencing Room",
                "url": "https://constructor.app/groups/room/room-456",
            },
        ]

        response = self.client_post(
            "/json/calls/constructorgroups/create", {"is_video_call": orjson.dumps(True).decode()}
        )

        response_dict = self.assert_json_success(response)
        self.assertEqual(response_dict["url"], "https://constructor.app/groups/room/room-456")

        # Verify both search and create were called
        self.assertEqual(mock_request.call_count, 2)
        search_args, search_kwargs = mock_request.call_args_list[0]
        create_args, create_kwargs = mock_request.call_args_list[1]

        # Verify search call
        expected_room_name = f"{self.user_profile.full_name}'s Zulip Videoconferencing Room"
        self.assertEqual(search_args[0], "GET")
        self.assertEqual(search_args[1], "/room/search")
        self.assertEqual(
            search_args[2],
            {
                "query": expected_room_name,
                "creator_email": self.user_profile.delivery_email,
                "page": 1,
                "size": 1,
            },
        )

        # Verify create call
        expected_name = f"{self.user_profile.full_name}'s Zulip Videoconferencing Room"
        self.assertEqual(create_args[0], "POST")
        self.assertEqual(create_args[1], "/room")
        self.assertEqual(create_args[2]["name"], expected_name)
        self.assertEqual(create_args[2]["creator_email"], self.user_profile.delivery_email)

    @patch("zerver.views.video_calls.ConstructorGroupsService._make_authenticated_request")
    @patch("zerver.views.video_calls.ConstructorGroupsService._is_configured")
    def test_api_error_handling(self, mock_configured: Mock, mock_request: Mock) -> None:
        """Test API error handling"""
        mock_configured.return_value = True
        mock_request.side_effect = Exception("API connection failed")

        response = self.client_post(
            "/json/calls/constructorgroups/create", {"is_video_call": orjson.dumps(True).decode()}
        )

        self.assert_json_error(response, "Failed to create video call")

    @patch("zerver.views.video_calls.ConstructorGroupsService._make_authenticated_request")
    @patch("zerver.views.video_calls.ConstructorGroupsService._is_configured")
    def test_audio_call_creation(self, mock_configured: Mock, mock_request: Mock) -> None:
        """Test audio call creation (same logic as video)"""
        mock_configured.return_value = True
        mock_request.return_value = {
            "data": [
                {"room_guid": "room-789", "url": "https://constructor.app/groups/room/room-789"}
            ]
        }

        response = self.client_post(
            "/json/calls/constructorgroups/create",
            {"is_video_call": orjson.dumps(False).decode()},  # Audio call
        )

        response_dict = self.assert_json_success(response)
        self.assertEqual(response_dict["url"], "https://constructor.app/groups/room/room-789")

    @patch("zerver.views.video_calls.ConstructorGroupsService._make_authenticated_request")
    @patch("zerver.views.video_calls.ConstructorGroupsService._is_configured")
    def test_room_url_validation(self, mock_configured: Mock, mock_request: Mock) -> None:
        """Test proper room URL validation"""
        mock_configured.return_value = True

        # Test invalid room data (no url)
        mock_request.return_value = {"data": [{"room_guid": "room-123", "name": "Test Room"}]}

        response = self.client_post(
            "/json/calls/constructorgroups/create", {"is_video_call": orjson.dumps(True).decode()}
        )

        self.assert_json_error(response, "Invalid room data received from Constructor Groups.")
