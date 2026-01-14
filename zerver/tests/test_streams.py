import json

from zerver.lib.test_classes import ZulipTestCase


class StreamCreationErrorTests(ZulipTestCase):
    def test_create_stream_with_archived_channel_name_user_can_view(self) -> None:
        """Error for archived channel should be specific when user can view it."""
        user = self.example_user("hamlet")
        self.login_user(user)
        realm = user.realm

        # Create and archive a stream
        archived_stream = self.make_stream("archived_channel", realm=realm)
        archived_stream.deactivated = True
        archived_stream.save()

        # Subscribe user to the archived stream so they can view it
        self.subscribe(user, "archived_channel")

        # Try to create stream with same name - should get 409 conflict
        response = self.client_post(
            "/json/channels/create",
            {
                "name": "archived_channel",
                "announce": json.dumps(False),
                "subscribers": json.dumps([]),
            },
        )

        # Should get conflict status
        self.assertEqual(response.status_code, 409, response.json())
        error_data = response.json()

        # Verify error message indicates archived channel
        self.assertIn("archived", error_data["msg"].lower())

    def test_create_stream_with_private_channel_name_user_cannot_view(self) -> None:
        """Error should be generic when user cannot view conflicting channel."""
        user = self.example_user("hamlet")
        self.login_user(user)
        other_user = self.example_user("othello")
        realm = user.realm

        # Create private stream that user is NOT subscribed to
        self.make_stream(
            "private_channel",
            realm=realm,
            invite_only=True,
        )
        # Only subscribe othello, not hamlet
        self.subscribe(other_user, "private_channel")

        # Try to create stream with same name
        response = self.client_post(
            "/json/channels/create",
            {
                "name": "private_channel",
                "announce": json.dumps(False),
                "subscribers": json.dumps([]),
            },
        )

        # Should get error response (409 Conflict)
        self.assertEqual(response.status_code, 409)
        error_data = response.json()

        # Should show generic message (not reveal private/archived details)
        msg = error_data["msg"].lower()
        self.assertIn("channel", msg)
        self.assertIn("already exists", msg)

        # Verify is_private is False to prevent information leakage
        self.assertFalse(error_data["is_private"])
        self.assertFalse(error_data["can_view_channel"])

    def test_create_stream_with_private_channel_name_user_can_view(self) -> None:
        """Error should reveal channel type when user can view it."""
        user = self.example_user("hamlet")
        self.login_user(user)
        realm = user.realm

        # Create private stream and subscribe the user
        self.make_stream(
            "private_channel_visible",
            realm=realm,
            invite_only=True,
        )
        self.subscribe(user, "private_channel_visible")

        # Try to create stream with same name
        response = self.client_post(
            "/json/channels/create",
            {
                "name": "private_channel_visible",
                "announce": json.dumps(False),
                "subscribers": json.dumps([]),
            },
        )

        # Should get error response (409 Conflict)
        self.assertEqual(response.status_code, 409)
        error_data = response.json()

        # Should show message indicating it's a private channel
        self.assertIn("already exists", error_data["msg"].lower())

        # Verify is_private is True when user can view
        self.assertTrue(error_data["is_private"])
        self.assertTrue(error_data["can_view_channel"])

    def test_create_stream_with_public_channel_name(self) -> None:
        """Error should show public channel details for public channels."""
        user = self.example_user("hamlet")
        self.login_user(user)
        realm = user.realm

        # Create public stream
        self.make_stream(
            "public_channel",
            realm=realm,
            invite_only=False,
        )

        # Try to create stream with same name
        response = self.client_post(
            "/json/channels/create",
            {
                "name": "public_channel",
                "announce": json.dumps(False),
                "subscribers": json.dumps([]),
            },
        )

        # Should get error response (409 Conflict)
        self.assertEqual(response.status_code, 409)
        error_data = response.json()

        # Should show message
        self.assertIn("already exists", error_data["msg"].lower())

        # Verify is_private is False for public channels
        self.assertFalse(error_data["is_private"])
        self.assertTrue(error_data["can_view_channel"])
