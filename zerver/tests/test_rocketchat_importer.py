import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import orjson

from zerver.data_import.import_util import SubscriberHandler, ZerverFieldsT, build_recipients
from zerver.data_import.rocketchat import (
    build_custom_emoji,
    build_reactions,
    categorize_channels_and_map_with_id,
    convert_channel_data,
    convert_huddle_data,
    convert_stream_subscription_data,
    do_convert_data,
    map_receiver_id_to_recipient_id,
    map_upload_id_to_upload_data,
    map_user_id_to_user,
    map_username_to_user_id,
    process_message_attachment,
    process_users,
    rocketchat_data_to_dict,
    separate_channel_private_and_livechat_messages,
    truncate_name,
)
from zerver.data_import.sequencer import IdMapper
from zerver.data_import.user_handler import UserHandler
from zerver.lib.emoji import name_to_codepoint
from zerver.lib.import_realm import do_import_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Reaction, Recipient, UserProfile, get_realm, get_user


class RocketChatImporter(ZulipTestCase):
    def test_rocketchat_data_to_dict(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)
        self.assert_length(rocketchat_data, 7)

        self.assert_length(rocketchat_data["user"], 6)
        self.assertEqual(rocketchat_data["user"][2]["username"], "harry.potter")
        self.assert_length(rocketchat_data["user"][2]["__rooms"], 10)

        self.assert_length(rocketchat_data["room"], 16)
        self.assertEqual(rocketchat_data["room"][0]["_id"], "GENERAL")
        self.assertEqual(rocketchat_data["room"][0]["name"], "general")

        self.assert_length(rocketchat_data["message"], 87)
        self.assertEqual(rocketchat_data["message"][1]["msg"], "Hey everyone, how's it going??")
        self.assertEqual(rocketchat_data["message"][1]["rid"], "GENERAL")
        self.assertEqual(rocketchat_data["message"][1]["u"]["username"], "priyansh3133")

        self.assert_length(rocketchat_data["custom_emoji"]["emoji"], 3)
        self.assertEqual(rocketchat_data["custom_emoji"]["emoji"][0]["name"], "tick")

        self.assert_length(rocketchat_data["upload"]["upload"], 4)
        self.assertEqual(rocketchat_data["upload"]["upload"][0]["name"], "harry-ron.jpg")

    def test_map_user_id_to_user(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)

        user_id_to_user_map = map_user_id_to_user(rocketchat_data["user"])

        self.assert_length(rocketchat_data["user"], 6)
        self.assert_length(user_id_to_user_map, 6)

        self.assertEqual(
            user_id_to_user_map[rocketchat_data["user"][0]["_id"]], rocketchat_data["user"][0]
        )

    def test_map_username_to_user_id(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)

        user_id_to_user_map = map_user_id_to_user(rocketchat_data["user"])
        username_to_user_id_map = map_username_to_user_id(user_id_to_user_map)

        self.assert_length(rocketchat_data["user"], 6)
        self.assert_length(username_to_user_id_map, 6)

        self.assertEqual(
            username_to_user_id_map[rocketchat_data["user"][0]["username"]],
            rocketchat_data["user"][0]["_id"],
        )

    def test_process_users(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)

        user_id_to_user_map = map_user_id_to_user(rocketchat_data["user"])

        realm_id = 3
        domain_name = "zulip.com"

        user_handler = UserHandler()
        user_id_mapper = IdMapper()

        process_users(
            user_id_to_user_map=user_id_to_user_map,
            realm_id=realm_id,
            domain_name=domain_name,
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
        )

        self.assert_length(user_handler.get_all_users(), 6)
        self.assertTrue(user_id_mapper.has(rocketchat_data["user"][0]["_id"]))
        self.assertTrue(user_id_mapper.has(rocketchat_data["user"][4]["_id"]))

        user_id = user_id_mapper.get(rocketchat_data["user"][0]["_id"])
        user = user_handler.get_user(user_id)

        self.assertEqual(user["full_name"], rocketchat_data["user"][0]["name"])
        self.assertEqual(user["avatar_source"], "G")
        self.assertEqual(user["delivery_email"], "rocket.cat-bot@zulip.com")
        self.assertEqual(user["email"], "rocket.cat-bot@zulip.com")
        self.assertEqual(user["full_name"], "Rocket.Cat")
        self.assertEqual(user["id"], 1)
        self.assertEqual(user["is_active"], False)
        self.assertEqual(user["is_mirror_dummy"], False)
        self.assertEqual(user["is_bot"], True)
        self.assertEqual(user["bot_type"], 1)
        self.assertEqual(user["bot_owner"], 2)
        self.assertEqual(user["role"], UserProfile.ROLE_MEMBER)
        self.assertEqual(user["realm"], realm_id)
        self.assertEqual(user["short_name"], "rocket.cat")
        self.assertEqual(user["timezone"], "UTC")

        user_id = user_id_mapper.get(rocketchat_data["user"][2]["_id"])
        user = user_handler.get_user(user_id)

        self.assertEqual(user["full_name"], rocketchat_data["user"][2]["name"])
        self.assertEqual(user["avatar_source"], "G")
        self.assertEqual(user["delivery_email"], "harrypotter@email.com")
        self.assertEqual(user["email"], "harrypotter@email.com")
        self.assertEqual(user["full_name"], "Harry Potter")
        self.assertEqual(user["id"], 3)
        self.assertEqual(user["is_active"], True)
        self.assertEqual(user["is_mirror_dummy"], False)
        self.assertEqual(user["is_bot"], False)
        self.assertEqual(user["bot_type"], None)
        self.assertEqual(user["bot_owner"], None)
        self.assertEqual(user["role"], UserProfile.ROLE_REALM_OWNER)
        self.assertEqual(user["realm"], realm_id)
        self.assertEqual(user["short_name"], "harry.potter")
        self.assertEqual(user["timezone"], "UTC")

        # Test `is_mirror_dummy` set for users of type `unknown`
        rocketchat_data["user"].append(
            {
                "_id": "s0m34ndmID",
                "createdAt": datetime(2019, 11, 6, 0, 38, 42, 796000, tzinfo=timezone.utc),
                "type": "unknown",
                "roles": ["unknown"],
                "name": "Unknown user",
                "username": "unknown",
            }
        )
        user_id_to_user_map = map_user_id_to_user(rocketchat_data["user"])

        process_users(
            user_id_to_user_map=user_id_to_user_map,
            realm_id=realm_id,
            domain_name=domain_name,
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
        )

        self.assert_length(user_handler.get_all_users(), 7)
        self.assertTrue(user_id_mapper.has(rocketchat_data["user"][6]["_id"]))

        user_id = user_id_mapper.get(rocketchat_data["user"][6]["_id"])
        user = user_handler.get_user(user_id)

        self.assertEqual(user["id"], 7)
        self.assertEqual(user["is_active"], False)
        self.assertEqual(user["is_mirror_dummy"], True)
        self.assertEqual(user["is_bot"], False)

    def test_categorize_channels_and_map_with_id(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)

        room_id_to_room_map: Dict[str, Dict[str, Any]] = {}
        team_id_to_team_map: Dict[str, Dict[str, Any]] = {}
        dsc_id_to_dsc_map: Dict[str, Dict[str, Any]] = {}
        direct_id_to_direct_map: Dict[str, Dict[str, Any]] = {}
        huddle_id_to_huddle_map: Dict[str, Dict[str, Any]] = {}
        livechat_id_to_livechat_map: Dict[str, Dict[str, Any]] = {}

        with self.assertLogs(level="INFO"):
            categorize_channels_and_map_with_id(
                channel_data=rocketchat_data["room"],
                room_id_to_room_map=room_id_to_room_map,
                team_id_to_team_map=team_id_to_team_map,
                dsc_id_to_dsc_map=dsc_id_to_dsc_map,
                direct_id_to_direct_map=direct_id_to_direct_map,
                huddle_id_to_huddle_map=huddle_id_to_huddle_map,
                livechat_id_to_livechat_map=livechat_id_to_livechat_map,
            )

        self.assert_length(rocketchat_data["room"], 16)
        # Teams are a subset of rooms.
        self.assert_length(room_id_to_room_map, 6)
        self.assert_length(team_id_to_team_map, 1)
        self.assert_length(dsc_id_to_dsc_map, 5)
        self.assert_length(direct_id_to_direct_map, 2)
        self.assert_length(huddle_id_to_huddle_map, 1)
        self.assert_length(livechat_id_to_livechat_map, 2)

        room_id = rocketchat_data["room"][0]["_id"]
        self.assertIn(room_id, room_id_to_room_map)
        self.assertEqual(room_id_to_room_map[room_id], rocketchat_data["room"][0])

        team_id = rocketchat_data["room"][3]["teamId"]
        self.assertIn(team_id, team_id_to_team_map)
        self.assertEqual(team_id_to_team_map[team_id], rocketchat_data["room"][3])

        dsc_id = rocketchat_data["room"][7]["_id"]
        self.assertIn(dsc_id, dsc_id_to_dsc_map)
        self.assertEqual(dsc_id_to_dsc_map[dsc_id], rocketchat_data["room"][7])

        direct_id = rocketchat_data["room"][4]["_id"]
        self.assertIn(direct_id, direct_id_to_direct_map)
        self.assertEqual(direct_id_to_direct_map[direct_id], rocketchat_data["room"][4])

        huddle_id = rocketchat_data["room"][12]["_id"]
        self.assertIn(huddle_id, huddle_id_to_huddle_map)
        self.assertEqual(huddle_id_to_huddle_map[huddle_id], rocketchat_data["room"][12])

        livechat_id = rocketchat_data["room"][14]["_id"]
        self.assertIn(livechat_id, livechat_id_to_livechat_map)
        self.assertEqual(livechat_id_to_livechat_map[livechat_id], rocketchat_data["room"][14])

    def test_convert_channel_data(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)

        realm_id = 3
        stream_id_mapper = IdMapper()

        room_id_to_room_map: Dict[str, Dict[str, Any]] = {}
        team_id_to_team_map: Dict[str, Dict[str, Any]] = {}
        dsc_id_to_dsc_map: Dict[str, Dict[str, Any]] = {}
        direct_id_to_direct_map: Dict[str, Dict[str, Any]] = {}
        huddle_id_to_huddle_map: Dict[str, Dict[str, Any]] = {}
        livechat_id_to_livechat_map: Dict[str, Dict[str, Any]] = {}

        with self.assertLogs(level="INFO"):
            categorize_channels_and_map_with_id(
                channel_data=rocketchat_data["room"],
                room_id_to_room_map=room_id_to_room_map,
                team_id_to_team_map=team_id_to_team_map,
                dsc_id_to_dsc_map=dsc_id_to_dsc_map,
                direct_id_to_direct_map=direct_id_to_direct_map,
                huddle_id_to_huddle_map=huddle_id_to_huddle_map,
                livechat_id_to_livechat_map=livechat_id_to_livechat_map,
            )

        zerver_stream = convert_channel_data(
            room_id_to_room_map=room_id_to_room_map,
            team_id_to_team_map=team_id_to_team_map,
            stream_id_mapper=stream_id_mapper,
            realm_id=realm_id,
        )

        # Only rooms are converted to streams.
        self.assert_length(room_id_to_room_map, 6)
        self.assert_length(zerver_stream, 6)

        # Normal public stream
        self.assertEqual(zerver_stream[0]["name"], "general")
        self.assertEqual(zerver_stream[0]["invite_only"], False)
        self.assertEqual(zerver_stream[0]["description"], "This is a general channel.")
        self.assertEqual(zerver_stream[0]["rendered_description"], "")
        self.assertEqual(zerver_stream[0]["stream_post_policy"], 1)
        self.assertEqual(zerver_stream[0]["realm"], realm_id)

        # Private stream
        self.assertEqual(zerver_stream[1]["name"], "random")
        self.assertEqual(zerver_stream[1]["invite_only"], True)
        self.assertEqual(zerver_stream[1]["description"], "")
        self.assertEqual(zerver_stream[1]["rendered_description"], "")
        self.assertEqual(zerver_stream[1]["stream_post_policy"], 1)
        self.assertEqual(zerver_stream[1]["realm"], realm_id)

        # Team main
        self.assertEqual(zerver_stream[3]["name"], "[TEAM] team-harry-potter")
        self.assertEqual(zerver_stream[3]["invite_only"], True)
        self.assertEqual(
            zerver_stream[3]["description"], "Welcome to the official Harry Potter team."
        )
        self.assertEqual(zerver_stream[3]["rendered_description"], "")
        self.assertEqual(zerver_stream[3]["stream_post_policy"], 1)
        self.assertEqual(zerver_stream[3]["realm"], realm_id)

        # Team channel
        self.assertEqual(zerver_stream[5]["name"], "thp-channel-2")
        self.assertEqual(zerver_stream[5]["invite_only"], False)
        self.assertEqual(zerver_stream[5]["description"], "[Team team-harry-potter channel]. ")
        self.assertEqual(zerver_stream[5]["rendered_description"], "")
        self.assertEqual(zerver_stream[5]["stream_post_policy"], 1)
        self.assertEqual(zerver_stream[5]["realm"], realm_id)

    def test_convert_stream_subscription_data(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)

        realm_id = 3
        domain_name = "zulip.com"

        user_handler = UserHandler()
        subscriber_handler = SubscriberHandler()
        user_id_mapper = IdMapper()
        stream_id_mapper = IdMapper()

        user_id_to_user_map = map_user_id_to_user(rocketchat_data["user"])

        process_users(
            user_id_to_user_map=user_id_to_user_map,
            realm_id=realm_id,
            domain_name=domain_name,
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
        )

        room_id_to_room_map: Dict[str, Dict[str, Any]] = {}
        team_id_to_team_map: Dict[str, Dict[str, Any]] = {}
        dsc_id_to_dsc_map: Dict[str, Dict[str, Any]] = {}
        direct_id_to_direct_map: Dict[str, Dict[str, Any]] = {}
        huddle_id_to_huddle_map: Dict[str, Dict[str, Any]] = {}
        livechat_id_to_livechat_map: Dict[str, Dict[str, Any]] = {}

        with self.assertLogs(level="INFO"):
            categorize_channels_and_map_with_id(
                channel_data=rocketchat_data["room"],
                room_id_to_room_map=room_id_to_room_map,
                team_id_to_team_map=team_id_to_team_map,
                dsc_id_to_dsc_map=dsc_id_to_dsc_map,
                direct_id_to_direct_map=direct_id_to_direct_map,
                huddle_id_to_huddle_map=huddle_id_to_huddle_map,
                livechat_id_to_livechat_map=livechat_id_to_livechat_map,
            )

        zerver_stream = convert_channel_data(
            room_id_to_room_map=room_id_to_room_map,
            team_id_to_team_map=team_id_to_team_map,
            stream_id_mapper=stream_id_mapper,
            realm_id=realm_id,
        )

        convert_stream_subscription_data(
            user_id_to_user_map=user_id_to_user_map,
            dsc_id_to_dsc_map=dsc_id_to_dsc_map,
            zerver_stream=zerver_stream,
            stream_id_mapper=stream_id_mapper,
            user_id_mapper=user_id_mapper,
            subscriber_handler=subscriber_handler,
        )

        priyansh_id = user_id_mapper.get(rocketchat_data["user"][1]["_id"])
        harry_id = user_id_mapper.get(rocketchat_data["user"][2]["_id"])
        hermione_id = user_id_mapper.get(rocketchat_data["user"][3]["_id"])
        ron_id = user_id_mapper.get(rocketchat_data["user"][4]["_id"])
        voldemort_id = user_id_mapper.get(rocketchat_data["user"][5]["_id"])

        self.assertEqual(
            subscriber_handler.get_users(stream_id=zerver_stream[0]["id"]),
            {priyansh_id, harry_id, ron_id, hermione_id, voldemort_id},
        )
        self.assertEqual(
            subscriber_handler.get_users(stream_id=zerver_stream[1]["id"]), {priyansh_id, harry_id}
        )
        self.assertEqual(
            subscriber_handler.get_users(stream_id=zerver_stream[2]["id"]), {harry_id, hermione_id}
        )
        self.assertEqual(
            subscriber_handler.get_users(stream_id=zerver_stream[3]["id"]),
            {harry_id, ron_id, hermione_id},
        )
        self.assertEqual(subscriber_handler.get_users(stream_id=zerver_stream[4]["id"]), {harry_id})
        self.assertEqual(subscriber_handler.get_users(stream_id=zerver_stream[5]["id"]), {harry_id})

        # Add a new channel with no user.
        no_user_channel: Dict[str, Any] = {
            "_id": "rand0mID",
            "ts": datetime(2021, 7, 15, 10, 58, 23, 647000, tzinfo=timezone.utc),
            "t": "c",
            "name": "no-user-channel",
        }
        room_id_to_room_map[no_user_channel["_id"]] = no_user_channel

        zerver_stream = convert_channel_data(
            room_id_to_room_map=room_id_to_room_map,
            team_id_to_team_map=team_id_to_team_map,
            stream_id_mapper=stream_id_mapper,
            realm_id=realm_id,
        )

        convert_stream_subscription_data(
            user_id_to_user_map=user_id_to_user_map,
            dsc_id_to_dsc_map=dsc_id_to_dsc_map,
            zerver_stream=zerver_stream,
            stream_id_mapper=stream_id_mapper,
            user_id_mapper=user_id_mapper,
            subscriber_handler=subscriber_handler,
        )

        self.assert_length(subscriber_handler.get_users(stream_id=zerver_stream[6]["id"]), 0)
        self.assertTrue(zerver_stream[6]["deactivated"])

    def test_convert_huddle_data(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)

        realm_id = 3
        domain_name = "zulip.com"

        user_handler = UserHandler()
        subscriber_handler = SubscriberHandler()
        user_id_mapper = IdMapper()
        huddle_id_mapper = IdMapper()

        user_id_to_user_map = map_user_id_to_user(rocketchat_data["user"])

        process_users(
            user_id_to_user_map=user_id_to_user_map,
            realm_id=realm_id,
            domain_name=domain_name,
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
        )

        room_id_to_room_map: Dict[str, Dict[str, Any]] = {}
        team_id_to_team_map: Dict[str, Dict[str, Any]] = {}
        dsc_id_to_dsc_map: Dict[str, Dict[str, Any]] = {}
        direct_id_to_direct_map: Dict[str, Dict[str, Any]] = {}
        huddle_id_to_huddle_map: Dict[str, Dict[str, Any]] = {}
        livechat_id_to_livechat_map: Dict[str, Dict[str, Any]] = {}

        with self.assertLogs(level="INFO"):
            categorize_channels_and_map_with_id(
                channel_data=rocketchat_data["room"],
                room_id_to_room_map=room_id_to_room_map,
                team_id_to_team_map=team_id_to_team_map,
                dsc_id_to_dsc_map=dsc_id_to_dsc_map,
                direct_id_to_direct_map=direct_id_to_direct_map,
                huddle_id_to_huddle_map=huddle_id_to_huddle_map,
                livechat_id_to_livechat_map=livechat_id_to_livechat_map,
            )

        zerver_huddle = convert_huddle_data(
            huddle_id_to_huddle_map=huddle_id_to_huddle_map,
            huddle_id_mapper=huddle_id_mapper,
            user_id_mapper=user_id_mapper,
            subscriber_handler=subscriber_handler,
        )

        self.assert_length(zerver_huddle, 1)

        rc_huddle_id = rocketchat_data["room"][12]["_id"]
        self.assertTrue(huddle_id_mapper.has(rc_huddle_id))

        huddle_id = huddle_id_mapper.get(rc_huddle_id)
        self.assertEqual(subscriber_handler.get_users(huddle_id=huddle_id), {3, 4, 5})

    def test_write_emoticon_data(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)
        output_dir = self.make_import_output_dir("rocketchat")

        with self.assertLogs(level="INFO"):
            zerver_realmemoji = build_custom_emoji(
                realm_id=3,
                custom_emoji_data=rocketchat_data["custom_emoji"],
                output_dir=output_dir,
            )

        self.assert_length(zerver_realmemoji, 5)
        self.assertEqual(zerver_realmemoji[0]["name"], "tick")
        self.assertEqual(zerver_realmemoji[0]["file_name"], "tick.png")
        self.assertEqual(zerver_realmemoji[0]["realm"], 3)
        self.assertEqual(zerver_realmemoji[0]["deactivated"], False)

        self.assertEqual(zerver_realmemoji[1]["name"], "check")
        self.assertEqual(zerver_realmemoji[1]["file_name"], "tick.png")
        self.assertEqual(zerver_realmemoji[1]["realm"], 3)
        self.assertEqual(zerver_realmemoji[1]["deactivated"], False)

        self.assertEqual(zerver_realmemoji[2]["name"], "zulip")
        self.assertEqual(zerver_realmemoji[2]["file_name"], "zulip.png")
        self.assertEqual(zerver_realmemoji[2]["realm"], 3)
        self.assertEqual(zerver_realmemoji[2]["deactivated"], False)

        records_file = os.path.join(output_dir, "emoji", "records.json")
        with open(records_file, "rb") as f:
            records_json = orjson.loads(f.read())

        self.assertEqual(records_json[0]["name"], "tick")
        self.assertEqual(records_json[0]["file_name"], "tick.png")
        self.assertEqual(records_json[0]["realm_id"], 3)
        self.assertEqual(records_json[1]["name"], "check")
        self.assertEqual(records_json[1]["file_name"], "tick.png")
        self.assertEqual(records_json[1]["realm_id"], 3)
        self.assertTrue(os.path.isfile(records_json[0]["path"]))

        self.assertEqual(records_json[2]["name"], "zulip")
        self.assertEqual(records_json[2]["file_name"], "zulip.png")
        self.assertEqual(records_json[2]["realm_id"], 3)
        self.assertTrue(os.path.isfile(records_json[2]["path"]))

    def test_map_receiver_id_to_recipient_id(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)

        realm_id = 3
        domain_name = "zulip.com"

        user_handler = UserHandler()
        subscriber_handler = SubscriberHandler()
        user_id_mapper = IdMapper()
        stream_id_mapper = IdMapper()
        huddle_id_mapper = IdMapper()

        user_id_to_user_map = map_user_id_to_user(rocketchat_data["user"])

        process_users(
            user_id_to_user_map=user_id_to_user_map,
            realm_id=realm_id,
            domain_name=domain_name,
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
        )

        room_id_to_room_map: Dict[str, Dict[str, Any]] = {}
        team_id_to_team_map: Dict[str, Dict[str, Any]] = {}
        dsc_id_to_dsc_map: Dict[str, Dict[str, Any]] = {}
        direct_id_to_direct_map: Dict[str, Dict[str, Any]] = {}
        huddle_id_to_huddle_map: Dict[str, Dict[str, Any]] = {}
        livechat_id_to_livechat_map: Dict[str, Dict[str, Any]] = {}

        with self.assertLogs(level="INFO"):
            categorize_channels_and_map_with_id(
                channel_data=rocketchat_data["room"],
                room_id_to_room_map=room_id_to_room_map,
                team_id_to_team_map=team_id_to_team_map,
                dsc_id_to_dsc_map=dsc_id_to_dsc_map,
                direct_id_to_direct_map=direct_id_to_direct_map,
                huddle_id_to_huddle_map=huddle_id_to_huddle_map,
                livechat_id_to_livechat_map=livechat_id_to_livechat_map,
            )

        zerver_stream = convert_channel_data(
            room_id_to_room_map=room_id_to_room_map,
            team_id_to_team_map=team_id_to_team_map,
            stream_id_mapper=stream_id_mapper,
            realm_id=realm_id,
        )

        zerver_huddle = convert_huddle_data(
            huddle_id_to_huddle_map=huddle_id_to_huddle_map,
            huddle_id_mapper=huddle_id_mapper,
            user_id_mapper=user_id_mapper,
            subscriber_handler=subscriber_handler,
        )

        all_users = user_handler.get_all_users()

        zerver_recipient = build_recipients(
            zerver_userprofile=all_users,
            zerver_stream=zerver_stream,
            zerver_huddle=zerver_huddle,
        )

        stream_id_to_recipient_id: Dict[int, int] = {}
        user_id_to_recipient_id: Dict[int, int] = {}
        huddle_id_to_recipient_id: Dict[int, int] = {}

        map_receiver_id_to_recipient_id(
            zerver_recipient=zerver_recipient,
            stream_id_to_recipient_id=stream_id_to_recipient_id,
            user_id_to_recipient_id=user_id_to_recipient_id,
            huddle_id_to_recipient_id=huddle_id_to_recipient_id,
        )

        # 6 for streams and 6 for users.
        self.assert_length(zerver_recipient, 13)
        self.assert_length(stream_id_to_recipient_id, 6)
        self.assert_length(user_id_to_recipient_id, 6)
        self.assert_length(huddle_id_to_recipient_id, 1)

        # First user recipients are built, followed by stream recipients in `build_recipients`.
        self.assertEqual(
            user_id_to_recipient_id[zerver_recipient[0]["type_id"]], zerver_recipient[0]["id"]
        )
        self.assertEqual(
            user_id_to_recipient_id[zerver_recipient[1]["type_id"]], zerver_recipient[1]["id"]
        )

        self.assertEqual(
            stream_id_to_recipient_id[zerver_recipient[6]["type_id"]], zerver_recipient[6]["id"]
        )
        self.assertEqual(
            stream_id_to_recipient_id[zerver_recipient[7]["type_id"]], zerver_recipient[7]["id"]
        )

        self.assertEqual(
            huddle_id_to_recipient_id[zerver_recipient[12]["type_id"]], zerver_recipient[12]["id"]
        )

    def test_separate_channel_private_and_livechat_messages(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)

        room_id_to_room_map: Dict[str, Dict[str, Any]] = {}
        team_id_to_team_map: Dict[str, Dict[str, Any]] = {}
        dsc_id_to_dsc_map: Dict[str, Dict[str, Any]] = {}
        direct_id_to_direct_map: Dict[str, Dict[str, Any]] = {}
        huddle_id_to_huddle_map: Dict[str, Dict[str, Any]] = {}
        livechat_id_to_livechat_map: Dict[str, Dict[str, Any]] = {}

        with self.assertLogs(level="INFO"):
            categorize_channels_and_map_with_id(
                channel_data=rocketchat_data["room"],
                room_id_to_room_map=room_id_to_room_map,
                team_id_to_team_map=team_id_to_team_map,
                dsc_id_to_dsc_map=dsc_id_to_dsc_map,
                direct_id_to_direct_map=direct_id_to_direct_map,
                huddle_id_to_huddle_map=huddle_id_to_huddle_map,
                livechat_id_to_livechat_map=livechat_id_to_livechat_map,
            )

        channel_messages: List[Dict[str, Any]] = []
        private_messages: List[Dict[str, Any]] = []
        livechat_messages: List[Dict[str, Any]] = []

        separate_channel_private_and_livechat_messages(
            messages=rocketchat_data["message"],
            dsc_id_to_dsc_map=dsc_id_to_dsc_map,
            direct_id_to_direct_map=direct_id_to_direct_map,
            huddle_id_to_huddle_map=huddle_id_to_huddle_map,
            livechat_id_to_livechat_map=livechat_id_to_livechat_map,
            channel_messages=channel_messages,
            private_messages=private_messages,
            livechat_messages=livechat_messages,
        )

        self.assert_length(rocketchat_data["message"], 87)
        self.assert_length(channel_messages, 68)
        self.assert_length(private_messages, 11)
        self.assert_length(livechat_messages, 8)

        self.assertIn(rocketchat_data["message"][0], channel_messages)
        self.assertIn(rocketchat_data["message"][1], channel_messages)
        self.assertIn(rocketchat_data["message"][4], channel_messages)

        self.assertIn(rocketchat_data["message"][11], private_messages)
        self.assertIn(rocketchat_data["message"][12], private_messages)
        self.assertIn(rocketchat_data["message"][50], private_messages)  # Huddle message

        self.assertIn(rocketchat_data["message"][79], livechat_messages)
        self.assertIn(rocketchat_data["message"][83], livechat_messages)
        self.assertIn(rocketchat_data["message"][86], livechat_messages)

        # Message in a Discussion originating from a direct channel
        self.assertIn(rocketchat_data["message"][70], private_messages)
        self.assertIn(rocketchat_data["message"][70]["rid"], direct_id_to_direct_map)

        # Add a message with no `rid`
        rocketchat_data["message"].append(
            {
                "_id": "p4v37myxc6yLZ8AHh",
                "t": "livechat_navigation_history",
                "ts": datetime(2019, 11, 6, 0, 38, 42, 796000, tzinfo=timezone.utc),
                "msg": " - applewebdata://9124F033-BFEF-43C5-9215-DA369E4DA22D",
                "u": {"_id": "rocket.cat", "username": "cat"},
                "groupable": False,
                "unread": True,
                "navigation": {
                    "page": {
                        "change": "url",
                        "title": "",
                        "location": {"href": "applewebdata://9124F033-BFEF-43C5-9215-DA369E4DA22D"},
                    },
                    "token": "ebxuypgh0updo6klkobzhp",
                },
                "expireAt": 1575592722794.0,
                "_hidden": True,
                "_updatedAt": datetime(2019, 11, 6, 0, 38, 42, 796000, tzinfo=timezone.utc),
            }
        )

        channel_messages = []
        private_messages = []
        livechat_messages = []

        separate_channel_private_and_livechat_messages(
            messages=rocketchat_data["message"],
            dsc_id_to_dsc_map=dsc_id_to_dsc_map,
            direct_id_to_direct_map=direct_id_to_direct_map,
            huddle_id_to_huddle_map=huddle_id_to_huddle_map,
            livechat_id_to_livechat_map=livechat_id_to_livechat_map,
            channel_messages=channel_messages,
            private_messages=private_messages,
            livechat_messages=livechat_messages,
        )

        # No new message added to channel, private or livechat messages
        self.assert_length(channel_messages, 68)
        self.assert_length(private_messages, 11)
        self.assert_length(livechat_messages, 8)

    def test_map_upload_id_to_upload_data(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)

        upload_id_to_upload_data_map = map_upload_id_to_upload_data(rocketchat_data["upload"])

        self.assert_length(rocketchat_data["upload"]["upload"], 4)
        self.assert_length(upload_id_to_upload_data_map, 4)

        upload_id = rocketchat_data["upload"]["upload"][0]["_id"]
        upload_name = rocketchat_data["upload"]["upload"][0]["name"]
        self.assertEqual(upload_id_to_upload_data_map[upload_id]["name"], upload_name)
        self.assert_length(upload_id_to_upload_data_map[upload_id]["chunk"], 1)

    def test_build_reactions(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)
        output_dir = self.make_import_output_dir("rocketchat")

        with self.assertLogs(level="INFO"):
            zerver_realmemoji = build_custom_emoji(
                realm_id=3,
                custom_emoji_data=rocketchat_data["custom_emoji"],
                output_dir=output_dir,
            )

        total_reactions: List[ZerverFieldsT] = []

        reactions = [
            {"name": "grin", "user_id": 3},
            {"name": "grinning", "user_id": 3},
            {"name": "innocent", "user_id": 2},
            {"name": "star_struck", "user_id": 4},
            {"name": "heart", "user_id": 3},
            {"name": "rocket", "user_id": 4},
            {"name": "check", "user_id": 2},
            {"name": "zulip", "user_id": 3},
            {"name": "harry-ron", "user_id": 4},
        ]

        build_reactions(
            total_reactions=total_reactions,
            reactions=reactions,
            message_id=3,
            zerver_realmemoji=zerver_realmemoji,
        )

        # :grin: is not present in Zulip's default emoji set,
        # or in Reaction.UNICODE_EMOJI reaction type.
        self.assert_length(total_reactions, 8)

        grinning_emoji_code = name_to_codepoint["grinning"]
        innocent_emoji_code = name_to_codepoint["innocent"]
        heart_emoji_code = name_to_codepoint["heart"]
        rocket_emoji_code = name_to_codepoint["rocket"]
        star_struck_emoji_code = name_to_codepoint["star_struck"]

        realmemoji_code = {}
        for emoji in zerver_realmemoji:
            realmemoji_code[emoji["name"]] = emoji["id"]

        self.assertEqual(
            self.get_set(total_reactions, "reaction_type"),
            {Reaction.UNICODE_EMOJI, Reaction.REALM_EMOJI},
        )
        self.assertEqual(
            self.get_set(total_reactions, "emoji_name"),
            {
                "grinning",
                "innocent",
                "star_struck",
                "heart",
                "rocket",
                "check",
                "zulip",
                "harry-ron",
            },
        )
        self.assertEqual(
            self.get_set(total_reactions, "emoji_code"),
            {
                grinning_emoji_code,
                innocent_emoji_code,
                heart_emoji_code,
                rocket_emoji_code,
                star_struck_emoji_code,
                realmemoji_code["check"],
                realmemoji_code["zulip"],
                realmemoji_code["harry-ron"],
            },
        )
        self.assertEqual(self.get_set(total_reactions, "user_profile"), {2, 3, 4})
        self.assert_length(self.get_set(total_reactions, "id"), 8)
        self.assert_length(self.get_set(total_reactions, "message"), 1)

    def test_process_message_attachment(self) -> None:
        fixture_dir_name = self.fixture_file_name("", "rocketchat_fixtures")
        rocketchat_data = rocketchat_data_to_dict(fixture_dir_name)
        output_dir = self.make_import_output_dir("mattermost")

        user_id_to_user_map = map_user_id_to_user(rocketchat_data["user"])

        realm_id = 3
        domain_name = "zulip.com"

        user_handler = UserHandler()
        user_id_mapper = IdMapper()

        process_users(
            user_id_to_user_map=user_id_to_user_map,
            realm_id=realm_id,
            domain_name=domain_name,
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
        )

        zerver_attachments: List[ZerverFieldsT] = []
        uploads_list: List[ZerverFieldsT] = []

        upload_id_to_upload_data_map = map_upload_id_to_upload_data(rocketchat_data["upload"])

        message_with_attachment = rocketchat_data["message"][55]

        process_message_attachment(
            upload=message_with_attachment["file"],
            realm_id=3,
            message_id=1,
            user_id=3,
            user_handler=user_handler,
            zerver_attachment=zerver_attachments,
            uploads_list=uploads_list,
            upload_id_to_upload_data_map=upload_id_to_upload_data_map,
            output_dir=output_dir,
        )

        self.assert_length(zerver_attachments, 1)
        self.assertEqual(zerver_attachments[0]["file_name"], "harry-ron.jpg")
        self.assertEqual(zerver_attachments[0]["owner"], 3)
        self.assertEqual(
            user_handler.get_user(zerver_attachments[0]["owner"])["email"], "harrypotter@email.com"
        )
        # TODO: Assert this for False after fixing the file permissions in direct messages
        self.assertTrue(zerver_attachments[0]["is_realm_public"])

        self.assert_length(uploads_list, 1)
        self.assertEqual(uploads_list[0]["user_profile_email"], "harrypotter@email.com")

        attachment_out_path = os.path.join(output_dir, "uploads", zerver_attachments[0]["path_id"])
        self.assertTrue(os.path.exists(attachment_out_path))
        self.assertTrue(os.path.isfile(attachment_out_path))

    def read_file(self, team_output_dir: str, output_file: str) -> Any:
        full_path = os.path.join(team_output_dir, output_file)
        with open(full_path, "rb") as f:
            return orjson.loads(f.read())

    def test_do_convert_data(self) -> None:
        rocketchat_data_dir = self.fixture_file_name("", "rocketchat_fixtures")
        output_dir = self.make_import_output_dir("rocketchat")

        with self.assertLogs(level="INFO") as info_log, self.settings(
            EXTERNAL_HOST="zulip.example.com"
        ):
            # We need to mock EXTERNAL_HOST to be a valid domain because rocketchat's importer
            # uses it to generate email addresses for users without an email specified.
            do_convert_data(
                rocketchat_data_dir=rocketchat_data_dir,
                output_dir=output_dir,
            )
        self.assertEqual(
            info_log.output,
            [
                "INFO:root:Huddle channel found. UIDs: ['LdBZ7kPxtKESyHPEe', 'M2sXGqoQRJQwQoXY2', 'os6N2Xg2JkNMCSW9Z'] -> hash 752a5854d2b6eec337fe81f0066a5dd72c3f0639",
                "INFO:root:Starting to process custom emoji",
                "INFO:root:Done processing emoji",
                "INFO:root:skipping direct messages discussion mention: Discussion with Hermione",
            ],
        )

        self.assertEqual(os.path.exists(os.path.join(output_dir, "avatars")), True)
        self.assertEqual(os.path.exists(os.path.join(output_dir, "emoji")), True)
        self.assertEqual(os.path.exists(os.path.join(output_dir, "uploads")), True)
        self.assertEqual(os.path.exists(os.path.join(output_dir, "attachment.json")), True)

        realm = self.read_file(output_dir, "realm.json")

        self.assertEqual(
            "Organization imported from Rocket.Chat!", realm["zerver_realm"][0]["description"]
        )

        exported_user_ids = self.get_set(realm["zerver_userprofile"], "id")
        self.assert_length(exported_user_ids, 6)

        exported_user_full_names = self.get_set(realm["zerver_userprofile"], "full_name")
        self.assertEqual(
            exported_user_full_names,
            {
                "Rocket.Cat",
                "Priyansh Garg",
                "Harry Potter",
                "Hermione Granger",
                "Ron Weasley",
                "Lord Voldemort",
            },
        )

        exported_user_emails = self.get_set(realm["zerver_userprofile"], "email")
        self.assertEqual(
            exported_user_emails,
            {
                "rocket.cat-bot@zulip.example.com",
                "priyansh3133@email.com",
                "harrypotter@email.com",
                "hermionegranger@email.com",
                "ronweasley@email.com",
                "lordvoldemort@email.com",
            },
        )

        self.assert_length(realm["zerver_stream"], 6)
        exported_stream_names = self.get_set(realm["zerver_stream"], "name")
        self.assertEqual(
            exported_stream_names,
            {
                "general",
                "random",
                "gryffindor-common-room",
                "[TEAM] team-harry-potter",
                "heya",
                "thp-channel-2",
            },
        )
        self.assertEqual(
            self.get_set(realm["zerver_stream"], "realm"), {realm["zerver_realm"][0]["id"]}
        )
        self.assertEqual(self.get_set(realm["zerver_stream"], "deactivated"), {False})

        self.assert_length(realm["zerver_defaultstream"], 0)

        exported_recipient_ids = self.get_set(realm["zerver_recipient"], "id")
        self.assert_length(exported_recipient_ids, 13)
        exported_recipient_types = self.get_set(realm["zerver_recipient"], "type")
        self.assertEqual(exported_recipient_types, {1, 2, 3})

        exported_subscription_userprofile = self.get_set(
            realm["zerver_subscription"], "user_profile"
        )
        self.assert_length(exported_subscription_userprofile, 6)
        exported_subscription_recipients = self.get_set(realm["zerver_subscription"], "recipient")
        self.assert_length(exported_subscription_recipients, 13)

        messages = self.read_file(output_dir, "messages-000001.json")

        exported_messages_id = self.get_set(messages["zerver_message"], "id")
        self.assertIn(messages["zerver_message"][0]["sender"], exported_user_ids)
        self.assertIn(messages["zerver_message"][0]["recipient"], exported_recipient_ids)
        self.assertIn(
            messages["zerver_message"][0]["content"], "Hey everyone, how's it going??\n\n"
        )

        exported_usermessage_userprofiles = self.get_set(
            messages["zerver_usermessage"], "user_profile"
        )
        # Rocket.Cat is not subscribed to any recipient (stream/direct messages) with messages.
        self.assert_length(exported_usermessage_userprofiles, 5)
        exported_usermessage_messages = self.get_set(messages["zerver_usermessage"], "message")
        self.assertEqual(exported_usermessage_messages, exported_messages_id)

        with self.assertLogs(level="INFO"):
            do_import_realm(
                import_dir=output_dir,
                subdomain="hogwarts",
            )

        realm = get_realm("hogwarts")

        self.assertFalse(get_user("rocket.cat-bot@zulip.example.com", realm).is_mirror_dummy)
        self.assertTrue(get_user("rocket.cat-bot@zulip.example.com", realm).is_bot)
        self.assertFalse(get_user("harrypotter@email.com", realm).is_mirror_dummy)
        self.assertFalse(get_user("harrypotter@email.com", realm).is_bot)
        self.assertFalse(get_user("ronweasley@email.com", realm).is_mirror_dummy)
        self.assertFalse(get_user("ronweasley@email.com", realm).is_bot)
        self.assertFalse(get_user("hermionegranger@email.com", realm).is_mirror_dummy)
        self.assertFalse(get_user("hermionegranger@email.com", realm).is_bot)

        messages = Message.objects.filter(realm_id=realm.id)
        for message in messages:
            self.assertIsNotNone(message.rendered_content)
        # After removing user_joined, added_user, discussion_created, etc.
        # messages. (Total messages were 66.)
        self.assert_length(messages, 43)

        stream_messages = messages.filter(recipient__type=Recipient.STREAM).order_by("date_sent")
        stream_recipients = stream_messages.values_list("recipient", flat=True)
        self.assert_length(stream_messages, 35)
        self.assert_length(set(stream_recipients), 5)
        self.assertEqual(stream_messages[0].sender.email, "priyansh3133@email.com")
        self.assertEqual(stream_messages[0].content, "Hey everyone, how's it going??")

        self.assertEqual(stream_messages[23].sender.email, "harrypotter@email.com")
        self.assertRegex(
            stream_messages[23].content,
            "Just a random pic!\n\n\\[harry-ron.jpg\\]\\(.*\\)",
        )
        self.assertTrue(stream_messages[23].has_attachment)
        self.assertTrue(stream_messages[23].has_image)
        self.assertTrue(stream_messages[23].has_link)

        huddle_messages = messages.filter(recipient__type=Recipient.HUDDLE).order_by("date_sent")
        huddle_recipients = huddle_messages.values_list("recipient", flat=True)
        self.assert_length(huddle_messages, 4)
        self.assert_length(set(huddle_recipients), 1)
        self.assertEqual(huddle_messages[0].sender.email, "hermionegranger@email.com")
        self.assertEqual(huddle_messages[0].content, "Hey people!")

        self.assertEqual(huddle_messages[2].sender.email, "harrypotter@email.com")
        self.assertRegex(
            huddle_messages[2].content,
            "This year's curriculum is out.\n\n\\[Hogwarts Curriculum.pdf\\]\\(.*\\)",
        )
        self.assertTrue(huddle_messages[2].has_attachment)
        self.assertFalse(huddle_messages[2].has_image)
        self.assertTrue(huddle_messages[2].has_link)

        personal_messages = messages.filter(recipient__type=Recipient.PERSONAL).order_by(
            "date_sent"
        )
        personal_recipients = personal_messages.values_list("recipient", flat=True)
        self.assert_length(personal_messages, 4)
        self.assert_length(set(personal_recipients), 2)
        self.assertEqual(personal_messages[0].sender.email, "harrypotter@email.com")
        self.assertEqual(
            personal_messages[0].content,
            "Hey @**Hermione Granger** :grin:, how's everything going?",
        )

        self.verify_emoji_code_foreign_keys()

    def test_truncate_name(self) -> None:
        self.assertEqual("foobar", truncate_name("foobar", 42, 60))

        self.assertEqual("1234567890 [42]", truncate_name("12345678901234567890", 42, 15))
