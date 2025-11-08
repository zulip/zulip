import orjson

from zerver.actions.default_streams import (
    do_add_default_stream,
    do_add_streams_to_default_stream_group,
    do_change_default_stream_group_description,
    do_change_default_stream_group_name,
    do_create_default_stream_group,
    do_remove_default_stream,
    do_remove_default_stream_group,
    do_remove_streams_from_default_stream_group,
    lookup_default_stream_groups,
)
from zerver.actions.streams import do_change_stream_group_based_setting
from zerver.actions.user_groups import check_add_user_group
from zerver.actions.users import do_change_user_role
from zerver.lib.default_streams import (
    get_default_stream_ids_for_realm,
    get_slim_realm_default_streams,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import ensure_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import queries_captured
from zerver.lib.user_groups import is_user_in_group
from zerver.models import DefaultStream, DefaultStreamGroup, Realm, Stream, UserProfile
from zerver.models.realms import get_realm
from zerver.models.streams import get_default_stream_groups


class DefaultStreamTest(ZulipTestCase):
    def get_default_stream_names(self, realm: Realm) -> set[str]:
        streams = get_slim_realm_default_streams(realm.id)
        return {s.name for s in streams}

    def test_query_count(self) -> None:
        DefaultStream.objects.all().delete()
        realm = get_realm("zulip")

        new_stream_ids = set()

        for i in range(5):
            stream = ensure_stream(realm, f"stream {i}", acting_user=None)
            new_stream_ids.add(stream.id)
            do_add_default_stream(stream)

        with queries_captured() as queries:
            default_stream_ids = get_default_stream_ids_for_realm(realm.id)

        self.assert_length(queries, 1)
        self.assertEqual(default_stream_ids, new_stream_ids)

    def test_add_and_remove_default_stream(self) -> None:
        realm = get_realm("zulip")
        stream = ensure_stream(realm, "Added stream", acting_user=None)
        orig_stream_names = self.get_default_stream_names(realm)
        do_add_default_stream(stream)
        new_stream_names = self.get_default_stream_names(realm)
        added_stream_names = new_stream_names - orig_stream_names
        self.assertEqual(added_stream_names, {"Added stream"})
        # idempotency--2nd call to add_default_stream should be a noop
        do_add_default_stream(stream)
        self.assertEqual(self.get_default_stream_names(realm), new_stream_names)

        # start removing
        do_remove_default_stream(stream)
        self.assertEqual(self.get_default_stream_names(realm), orig_stream_names)
        # idempotency--2nd call to remove_default_stream should be a noop
        do_remove_default_stream(stream)
        self.assertEqual(self.get_default_stream_names(realm), orig_stream_names)

    def test_api_calls(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)

        DefaultStream.objects.filter(realm=user_profile.realm).delete()

        stream_name = "stream ADDED via api"
        stream = ensure_stream(user_profile.realm, stream_name, acting_user=None)
        result = self.client_post("/json/default_streams", dict(stream_id=stream.id))
        self.assert_json_error(result, "Must be an organization administrator")
        self.assertFalse(stream_name in self.get_default_stream_names(user_profile.realm))

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        result = self.client_post("/json/default_streams", dict(stream_id=stream.id))
        self.assert_json_success(result)
        self.assertTrue(stream_name in self.get_default_stream_names(user_profile.realm))

        # look for it
        self.subscribe(user_profile, stream_name)
        payload = dict(
            include_public="true",
            include_default="true",
        )
        result = self.client_get("/json/streams", payload)
        streams = self.assert_json_success(result)["streams"]
        default_streams = {stream["name"] for stream in streams if stream["is_default"]}
        self.assertEqual(default_streams, {stream_name})

        other_streams = {stream["name"] for stream in streams if not stream["is_default"]}
        self.assertGreater(len(other_streams), 0)

        # and remove it
        result = self.client_delete("/json/default_streams", dict(stream_id=stream.id))
        self.assert_json_success(result)
        self.assertFalse(stream_name in self.get_default_stream_names(user_profile.realm))

        # Test admin can't access unsubscribed private stream for adding.
        stream_name = "private_stream"
        stream = self.make_stream(stream_name, invite_only=True)
        self.subscribe(self.example_user("iago"), stream_name)
        result = self.client_post("/json/default_streams", dict(stream_id=stream.id))
        self.assert_json_error(result, "Invalid channel ID")

        # Test admin can't add subscribed private stream also.
        self.subscribe(user_profile, stream_name)
        result = self.client_post("/json/default_streams", dict(stream_id=stream.id))
        self.assert_json_error(result, "Private channels cannot be made default.")

    def test_add_and_remove_stream_as_default(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        realm = user_profile.realm
        stream = self.make_stream("stream", realm=realm)
        stream_id = self.subscribe(user_profile, "stream").id

        params = {
            "is_default_stream": orjson.dumps(True).decode(),
        }
        self.assertFalse(is_user_in_group(stream.can_administer_channel_group_id, user_profile))
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_error(result, "You do not have permission to administer this channel.")
        self.assertFalse(stream_id in get_default_stream_ids_for_realm(realm.id))

        # User still needs to be an admin to add a default channel.
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=None)
        user_profile_group = check_add_user_group(
            realm, "user_profile_group", [user_profile], acting_user=user_profile
        )
        do_change_stream_group_based_setting(
            stream,
            "can_administer_channel_group",
            user_profile_group,
            acting_user=user_profile,
        )
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_error(result, "You do not have permission to change default channels.")
        self.assertFalse(stream_id in get_default_stream_ids_for_realm(realm.id))

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_success(result)
        self.assertTrue(stream_id in get_default_stream_ids_for_realm(realm.id))

        params = {
            "is_private": orjson.dumps(True).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_error(result, "A default channel cannot be private.")
        stream.refresh_from_db()
        self.assertFalse(stream.invite_only)

        params = {
            "is_private": orjson.dumps(True).decode(),
            "is_default_stream": orjson.dumps(False).decode(),
        }

        # User still needs to be an admin to remove a default channel.
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=None)
        self.assertTrue(is_user_in_group(stream.can_administer_channel_group_id, user_profile))
        self.assertTrue(stream_id in get_default_stream_ids_for_realm(realm.id))
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_error(result, "You do not have permission to change default channels.")
        self.assertTrue(stream_id in get_default_stream_ids_for_realm(realm.id))
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)

        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_success(result)
        stream.refresh_from_db()
        self.assertTrue(stream.invite_only)
        self.assertFalse(stream_id in get_default_stream_ids_for_realm(realm.id))

        stream_2 = self.make_stream("stream_2", realm=realm)
        stream_2_id = self.subscribe(user_profile, "stream_2").id

        bad_params = {
            "is_default_stream": orjson.dumps(True).decode(),
            "is_private": orjson.dumps(True).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream_2_id}", bad_params)
        self.assert_json_error(result, "A default channel cannot be private.")
        stream.refresh_from_db()
        self.assertFalse(stream_2.invite_only)
        self.assertFalse(stream_2_id in get_default_stream_ids_for_realm(realm.id))

        private_stream = self.make_stream("private_stream", realm=realm, invite_only=True)
        private_stream_id = self.subscribe(user_profile, "private_stream").id

        params = {
            "is_default_stream": orjson.dumps(True).decode(),
        }
        result = self.client_patch(f"/json/streams/{private_stream_id}", params)
        self.assert_json_error(result, "A default channel cannot be private.")
        self.assertFalse(private_stream_id in get_default_stream_ids_for_realm(realm.id))

        params = {
            "is_private": orjson.dumps(False).decode(),
            "is_default_stream": orjson.dumps(True).decode(),
        }
        result = self.client_patch(f"/json/streams/{private_stream_id}", params)
        self.assert_json_success(result)
        private_stream.refresh_from_db()
        self.assertFalse(private_stream.invite_only)
        self.assertTrue(private_stream_id in get_default_stream_ids_for_realm(realm.id))


class DefaultStreamGroupTest(ZulipTestCase):
    def test_create_update_and_remove_default_stream_group(self) -> None:
        realm = get_realm("zulip")

        # Test creating new default stream group
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 0)

        streams = [
            ensure_stream(realm, stream_name, acting_user=None)
            for stream_name in ["stream1", "stream2", "stream3"]
        ]

        def get_streams(group: DefaultStreamGroup) -> list[Stream]:
            return list(group.streams.all().order_by("name"))

        group_name = "group1"
        description = "This is group1"
        do_create_default_stream_group(realm, group_name, description, streams)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(default_stream_groups[0].description, description)
        self.assertEqual(get_streams(default_stream_groups[0]), streams)

        # Test adding streams to existing default stream group
        group = lookup_default_stream_groups(["group1"], realm)[0]
        new_stream_names = [
            "stream4",
            "stream5",
            "stream6",
            "stream7",
            "stream8",
            "stream9",
        ]
        new_streams = [
            ensure_stream(realm, new_stream_name, acting_user=None)
            for new_stream_name in new_stream_names
        ]
        streams += new_streams

        do_add_streams_to_default_stream_group(realm, group, new_streams)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(get_streams(default_stream_groups[0]), streams)

        # Test removing streams from existing default stream group
        with self.assert_database_query_count(5):
            do_remove_streams_from_default_stream_group(realm, group, new_streams)
        remaining_streams = streams[0:3]
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(get_streams(default_stream_groups[0]), remaining_streams)

        # Test changing default stream group description
        new_description = "group1 new description"
        do_change_default_stream_group_description(realm, group, new_description)
        default_stream_groups = get_default_stream_groups(realm)
        self.assertEqual(default_stream_groups[0].description, new_description)
        self.assert_length(default_stream_groups, 1)

        # Test changing default stream group name
        new_group_name = "new group1"
        do_change_default_stream_group_name(realm, group, new_group_name)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, new_group_name)
        self.assertEqual(get_streams(default_stream_groups[0]), remaining_streams)

        # Test removing default stream group
        do_remove_default_stream_group(realm, group)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 0)

        # Test creating a default stream group which contains a default stream
        do_add_default_stream(remaining_streams[0])
        with self.assertRaisesRegex(
            JsonableError, "'stream1' is a default channel and cannot be added to 'new group1'"
        ):
            do_create_default_stream_group(
                realm, new_group_name, "This is group1", remaining_streams
            )

    def test_api_calls(self) -> None:
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        realm = user_profile.realm
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)

        # Test creating new default stream group
        stream_names = ["stream1", "stream2", "stream3"]
        group_name = "group1"
        description = "This is group1"
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 0)

        streams = [
            ensure_stream(realm, stream_name, acting_user=None) for stream_name in stream_names
        ]

        result = self.client_post(
            "/json/default_stream_groups/create",
            {
                "group_name": group_name,
                "description": description,
                "stream_names": orjson.dumps(stream_names).decode(),
            },
        )
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(default_stream_groups[0].description, description)
        self.assertEqual(list(default_stream_groups[0].streams.all().order_by("id")), streams)

        # Try adding the same streams to the group.
        result = self.client_post(
            "/json/default_stream_groups/create",
            {
                "group_name": group_name,
                "description": description,
                "stream_names": orjson.dumps(stream_names).decode(),
            },
        )
        self.assert_json_error(result, "Default channel group 'group1' already exists")

        # Test adding streams to existing default stream group
        group_id = default_stream_groups[0].id
        new_stream_names = ["stream4", "stream5"]
        new_streams = [
            ensure_stream(realm, new_stream_name, acting_user=None)
            for new_stream_name in new_stream_names
        ]
        streams += new_streams

        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}/streams",
            {"stream_names": orjson.dumps(new_stream_names).decode()},
        )
        self.assert_json_error(result, "Missing 'op' argument")

        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}/streams",
            {"op": "invalid", "stream_names": orjson.dumps(new_stream_names).decode()},
        )
        self.assert_json_error(result, 'Invalid value for "op". Specify one of "add" or "remove".')

        result = self.client_patch(
            "/json/default_stream_groups/12345/streams",
            {"op": "add", "stream_names": orjson.dumps(new_stream_names).decode()},
        )
        self.assert_json_error(result, "Default channel group with id '12345' does not exist.")

        result = self.client_patch(f"/json/default_stream_groups/{group_id}/streams", {"op": "add"})
        self.assert_json_error(result, "Missing 'stream_names' argument")

        do_add_default_stream(new_streams[0])
        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}/streams",
            {"op": "add", "stream_names": orjson.dumps(new_stream_names).decode()},
        )
        self.assert_json_error(
            result, "'stream4' is a default channel and cannot be added to 'group1'"
        )

        do_remove_default_stream(new_streams[0])
        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}/streams",
            {"op": "add", "stream_names": orjson.dumps(new_stream_names).decode()},
        )
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(list(default_stream_groups[0].streams.all().order_by("name")), streams)

        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}/streams",
            {"op": "add", "stream_names": orjson.dumps(new_stream_names).decode()},
        )
        self.assert_json_error(
            result, "Channel 'stream4' is already present in default channel group 'group1'"
        )

        # Test removing streams from default stream group
        result = self.client_patch(
            "/json/default_stream_groups/12345/streams",
            {"op": "remove", "stream_names": orjson.dumps(new_stream_names).decode()},
        )
        self.assert_json_error(result, "Default channel group with id '12345' does not exist.")

        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}/streams",
            {"op": "remove", "stream_names": orjson.dumps(["random stream name"]).decode()},
        )
        self.assert_json_error(result, "Invalid channel name 'random stream name'")

        streams.remove(new_streams[0])
        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}/streams",
            {"op": "remove", "stream_names": orjson.dumps([new_stream_names[0]]).decode()},
        )
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(list(default_stream_groups[0].streams.all().order_by("name")), streams)

        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}/streams",
            {"op": "remove", "stream_names": orjson.dumps(new_stream_names).decode()},
        )
        self.assert_json_error(
            result, "Channel 'stream4' is not present in default channel group 'group1'"
        )

        # Test changing description of default stream group
        new_description = "new group1 description"

        result = self.client_patch(f"/json/default_stream_groups/{group_id}")
        self.assert_json_error(result, 'You must pass "new_description" or "new_group_name".')

        result = self.client_patch(
            "/json/default_stream_groups/12345",
            {"new_description": new_description},
        )
        self.assert_json_error(result, "Default channel group with id '12345' does not exist.")

        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}",
            {"new_description": new_description},
        )
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(default_stream_groups[0].description, new_description)

        # Test changing name of default stream group
        new_group_name = "new group1"
        do_create_default_stream_group(realm, "group2", "", [])
        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}",
            {"new_group_name": "group2"},
        )
        self.assert_json_error(result, "Default channel group 'group2' already exists")
        new_group = lookup_default_stream_groups(["group2"], realm)[0]
        do_remove_default_stream_group(realm, new_group)

        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}",
            {"new_group_name": group_name},
        )
        self.assert_json_error(result, "This default channel group is already named 'group1'")

        result = self.client_patch(
            f"/json/default_stream_groups/{group_id}",
            {"new_group_name": new_group_name},
        )
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, new_group_name)
        self.assertEqual(default_stream_groups[0].description, new_description)

        # Test deleting a default stream group
        result = self.client_delete(f"/json/default_stream_groups/{group_id}")
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 0)

        result = self.client_delete(f"/json/default_stream_groups/{group_id}")
        self.assert_json_error(
            result, f"Default channel group with id '{group_id}' does not exist."
        )

    def test_invalid_default_stream_group_name(self) -> None:
        self.login("iago")
        user_profile = self.example_user("iago")
        realm = user_profile.realm

        stream_names = ["stream1", "stream2", "stream3"]
        description = "This is group1"
        for stream_name in stream_names:
            ensure_stream(realm, stream_name, acting_user=None)

        result = self.client_post(
            "/json/default_stream_groups/create",
            {
                "group_name": "",
                "description": description,
                "stream_names": orjson.dumps(stream_names).decode(),
            },
        )
        self.assert_json_error(result, "Invalid default channel group name ''")

        result = self.client_post(
            "/json/default_stream_groups/create",
            {
                "group_name": "x" * 100,
                "description": description,
                "stream_names": orjson.dumps(stream_names).decode(),
            },
        )
        self.assert_json_error(
            result,
            f"Default channel group name too long (limit: {DefaultStreamGroup.MAX_NAME_LENGTH} characters)",
        )

        result = self.client_post(
            "/json/default_stream_groups/create",
            {
                "group_name": "abc\000",
                "description": description,
                "stream_names": orjson.dumps(stream_names).decode(),
            },
        )
        self.assert_json_error(
            result, "Default channel group name 'abc\000' contains NULL (0x00) characters."
        )

        # Also test that lookup_default_stream_groups raises an
        # error if we pass it a bad name.  This function is used
        # during registration, but it's a bit heavy to do a full
        # test of that.
        with self.assertRaisesRegex(JsonableError, "Invalid default channel group invalid-name"):
            lookup_default_stream_groups(["invalid-name"], realm)
