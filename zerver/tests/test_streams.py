import json

from zerver.actions.streams import do_change_stream_group_based_setting
from zerver.lib.exceptions import ChannelExistsError
from zerver.lib.streams import check_stream_name_available
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.types import UserGroupMembersData


class CheckStreamNameAvailableTests(ZulipTestCase):
    def test_check_stream_name_available_with_nonexistent_stream(self) -> None:
        """Test that check_stream_name_available passes for non-existent streams."""
        user = self.example_user("hamlet")
        realm = user.realm

        # Should not raise any exception for a non-existent stream name
        check_stream_name_available(realm, "nonexistent_stream_name")

    def test_check_stream_name_available_with_existing_stream(self) -> None:
        """Test that check_stream_name_available raises ChannelExistsError for existing streams."""
        user = self.example_user("hamlet")
        realm = user.realm

        # Create a stream first
        self.make_stream("existing_stream", realm=realm)

        # Should raise ChannelExistsError when trying to check an existing stream
        with self.assertRaises(ChannelExistsError):
            check_stream_name_available(realm, "existing_stream")


class StreamRenamePermissionTests(ZulipTestCase):
    def test_rename_stream_to_existing_stream_as_realm_admin(self) -> None:
        """Test renaming stream to existing stream when admin can view target."""
        from zerver.models import UserProfile

        admin = self.example_user("desdemona")
        self.set_user_role(admin, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login_user(admin)
        realm = admin.realm

        # Create two streams and subscribe admin to both
        stream1 = self.make_stream("stream_one", realm=realm)
        self.make_stream("stream_two", realm=realm, invite_only=True)
        self.subscribe(admin, "stream_one")
        self.subscribe(admin, "stream_two")

        # Admin should see error about conflict with can_view = True
        response = self.client_patch(
            f"/json/streams/{stream1.id}",
            {"new_name": "stream_two"},
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertTrue(data.get("can_view_channel"))

    def test_rename_stream_to_existing_public_stream_as_admin(self) -> None:
        """Test renaming stream to existing public stream as admin."""
        from zerver.models import UserProfile

        admin = self.example_user("desdemona")
        self.set_user_role(admin, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login_user(admin)
        realm = admin.realm

        # Create two streams - one public, one private
        stream1 = self.make_stream("stream_one", realm=realm, invite_only=True)
        self.make_stream("stream_two", realm=realm, invite_only=False)

        # Subscribe admin to stream_one so they can rename it
        self.subscribe(admin, "stream_one")

        # Admin trying to rename to public stream should show can_view = True
        response = self.client_patch(
            f"/json/streams/{stream1.id}",
            {"new_name": "stream_two"},
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        # Admin can always view
        self.assertTrue(data.get("can_view_channel"))

    def test_rename_stream_private_without_subscription_as_admin(self) -> None:
        """Test renaming to existing private stream where admin has no subscription."""
        from zerver.models import UserProfile

        admin = self.example_user("desdemona")
        self.set_user_role(admin, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login_user(admin)
        realm = admin.realm

        # Create two private streams
        stream1 = self.make_stream("stream_one", realm=realm, invite_only=True)
        self.make_stream("stream_two", realm=realm, invite_only=True)

        # Subscribe admin to stream_one only
        self.subscribe(admin, "stream_one")

        # Admin should see can_view as True (admins can view all streams)
        response = self.client_patch(
            f"/json/streams/{stream1.id}",
            {"new_name": "stream_two"},
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        # Admin can view even without subscription
        self.assertTrue(data.get("can_view_channel"))

    def test_rename_stream_to_private_stream_with_subscription(self) -> None:
        """Test renaming stream to existing private stream with subscription."""
        from zerver.models import UserProfile

        admin = self.example_user("desdemona")
        self.set_user_role(admin, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login_user(admin)
        realm = admin.realm

        # Create two private streams
        stream1 = self.make_stream("stream_one", realm=realm, invite_only=True)
        self.make_stream("stream_two", realm=realm, invite_only=True)

        # Subscribe admin to both streams
        self.subscribe(admin, "stream_one")
        self.subscribe(admin, "stream_two")

        # Admin can see stream_two
        response = self.client_patch(
            f"/json/streams/{stream1.id}",
            {"new_name": "stream_two"},
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertTrue(data.get("can_view_channel"))

    def test_rename_to_public_as_channel_admin_not_realm_admin(self) -> None:
        """Test channel admin (non-realm-admin) renaming to existing public stream.

        This covers line 484-485: elif existing_stream.is_public(): can_view = True
        """
        from zerver.models import UserProfile

        # Use a regular member (not realm admin)
        user = self.example_user("hamlet")
        self.set_user_role(user, UserProfile.ROLE_MEMBER)
        self.login_user(user)
        realm = user.realm

        # Create the stream that user will try to rename
        stream1 = self.make_stream("my_stream", realm=realm)
        self.subscribe(user, "my_stream")

        # Create a public stream that already exists with the target name
        self.make_stream("existing_public", realm=realm, invite_only=False)

        # Make user a channel admin of stream1 (but not realm admin)
        user_group_data = UserGroupMembersData(direct_members=[user.id], direct_subgroups=[])
        do_change_stream_group_based_setting(
            stream1, "can_administer_channel_group", user_group_data, acting_user=user
        )

        # Now user (non-realm-admin but channel admin) tries to rename to existing public stream
        response = self.client_patch(
            f"/json/streams/{stream1.id}",
            {"new_name": "existing_public"},
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        # User can view public stream (hits line 484-485: is_public() check)
        self.assertTrue(data.get("can_view_channel"))

    def test_rename_to_private_with_sub_as_channel_admin_not_realm_admin(self) -> None:
        """Test channel admin (non-realm-admin) renaming to private stream they're subscribed to.

        This covers line 487: can_view = Subscription.objects.filter().exists()
        """
        from zerver.models import UserProfile

        # Use a regular member (not realm admin)
        user = self.example_user("hamlet")
        self.set_user_role(user, UserProfile.ROLE_MEMBER)
        self.login_user(user)
        realm = user.realm

        # Create the stream that user will try to rename
        stream1 = self.make_stream("my_stream", realm=realm)
        self.subscribe(user, "my_stream")

        # Create a private stream and subscribe the user
        self.make_stream("existing_private", realm=realm, invite_only=True)
        self.subscribe(user, "existing_private")

        # Make user a channel admin of stream1 (but not realm admin)
        user_group_data = UserGroupMembersData(direct_members=[user.id], direct_subgroups=[])
        do_change_stream_group_based_setting(
            stream1, "can_administer_channel_group", user_group_data, acting_user=user
        )

        # Now user (non-realm-admin but channel admin) tries to rename
        response = self.client_patch(
            f"/json/streams/{stream1.id}",
            {"new_name": "existing_private"},
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        # User is subscribed, so can view (hits line 487: Subscription check returns True)
        self.assertTrue(data.get("can_view_channel"))

    def test_rename_to_private_without_sub_as_channel_admin_not_realm_admin(self) -> None:
        """Test channel admin (non-realm-admin) renaming to private stream not subscribed.

        This covers line 487: can_view = Subscription.objects.filter().exists() returns False
        """
        from zerver.models import UserProfile

        # Use a regular member (not realm admin)
        user = self.example_user("hamlet")
        other_user = self.example_user("othello")
        self.set_user_role(user, UserProfile.ROLE_MEMBER)
        self.login_user(user)
        realm = user.realm

        # Create the stream that user will try to rename
        stream1 = self.make_stream("my_stream", realm=realm)
        self.subscribe(user, "my_stream")

        # Create a private stream and subscribe only other_user
        self.make_stream("existing_private", realm=realm, invite_only=True)
        self.subscribe(other_user, "existing_private")

        # Make user a channel admin of stream1 (but not realm admin)
        user_group_data = UserGroupMembersData(direct_members=[user.id], direct_subgroups=[])
        do_change_stream_group_based_setting(
            stream1, "can_administer_channel_group", user_group_data, acting_user=user
        )

        # Now user (non-realm-admin but channel admin) tries to rename
        response = self.client_patch(
            f"/json/streams/{stream1.id}",
            {"new_name": "existing_private"},
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        # User is NOT subscribed, so cannot view (hits line 487: returns False)
        self.assertFalse(data.get("can_view_channel"))

    def test_rename_stream_to_public_as_non_admin(self) -> None:
        """Test non-admin attempting to create stream with public channel name."""
        user = self.example_user("hamlet")
        self.login_user(user)
        realm = user.realm

        # Create a public stream first
        self.make_stream("public_channel", realm=realm, invite_only=False)

        # Non-admin tries to create stream with existing public stream name
        response = self.client_post(
            "/json/channels/create",
            {
                "name": "public_channel",
                "announce": json.dumps(False),
                "subscribers": json.dumps([]),
            },
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        # User can view public stream (line 765: not is_private_stream)
        self.assertTrue(data.get("can_view_channel"))

    def test_create_stream_private_with_subscription(self) -> None:
        """Test creating stream with existing private stream name (user subscribed)."""
        user = self.example_user("hamlet")
        self.login_user(user)
        realm = user.realm

        # Create a private stream and subscribe user
        self.make_stream("private_channel", realm=realm, invite_only=True)
        self.subscribe(user, "private_channel")

        # User tries to create stream with existing private stream name
        response = self.client_post(
            "/json/channels/create",
            {
                "name": "private_channel",
                "announce": json.dumps(False),
                "subscribers": json.dumps([]),
            },
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        # User can view private stream (line 769: Subscription.objects.filter().exists())
        self.assertTrue(data.get("can_view_channel"))

    def test_create_stream_private_without_subscription(self) -> None:
        """Test creating stream with private stream name (user not subscribed)."""
        user = self.example_user("hamlet")
        other_user = self.example_user("othello")
        self.login_user(user)
        realm = user.realm

        # Create a private stream and subscribe only other_user
        self.make_stream("private_channel", realm=realm, invite_only=True)
        self.subscribe(other_user, "private_channel")

        # User tries to create stream with existing private stream name
        response = self.client_post(
            "/json/channels/create",
            {
                "name": "private_channel",
                "announce": json.dumps(False),
                "subscribers": json.dumps([]),
            },
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        # User cannot view private stream they're not subscribed to
        # This hits line 769: Subscription.objects.filter().exists() returns False
        self.assertFalse(data.get("can_view_channel"))


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
