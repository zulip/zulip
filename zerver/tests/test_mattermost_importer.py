import os
import ujson
import filecmp
import logging

from typing import Dict, Any, List

from zerver.lib.import_realm import (
    do_import_realm,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.data_import.mattermost_user import UserHandler
from zerver.data_import.mattermost import mattermost_data_file_to_dict, process_user, convert_user_data, \
    create_username_to_user_mapping, label_mirror_dummy_users, reset_mirror_dummy_users, \
    convert_channel_data, write_emoticon_data, get_mentioned_user_ids, check_user_in_team, \
    build_reactions, get_name_to_codepoint_dict, do_convert_data
from zerver.data_import.sequencer import IdMapper
from zerver.data_import.import_util import SubscriberHandler
from zerver.models import Reaction, UserProfile, Message, get_realm

class MatterMostImporter(ZulipTestCase):
    logger = logging.getLogger()
    # set logger to a higher level to suppress 'logger.INFO' outputs
    logger.setLevel(logging.WARNING)

    def setUp(self) -> None:
        fixture_file_name = self.fixture_file_name("export.json", "mattermost_fixtures")
        self.mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        self.username_to_user = create_username_to_user_mapping(self.mattermost_data["user"])
        reset_mirror_dummy_users(self.username_to_user)

    def test_mattermost_data_file_to_dict(self) -> None:
        self.assertEqual(len(self.mattermost_data), 6)

        self.assertEqual(self.mattermost_data["version"], [1])

        self.assertEqual(len(self.mattermost_data["team"]), 2)
        self.assertEqual(self.mattermost_data["team"][0]["name"], "gryffindor")

        self.assertEqual(len(self.mattermost_data["channel"]), 5)
        self.assertEqual(self.mattermost_data["channel"][0]["name"], "gryffindor-common-room")
        self.assertEqual(self.mattermost_data["channel"][0]["team"], "gryffindor")

        self.assertEqual(len(self.mattermost_data["user"]), 5)
        self.assertEqual(self.mattermost_data["user"][1]["username"], "harry")
        self.assertEqual(len(self.mattermost_data["user"][1]["teams"]), 1)

        self.assertEqual(len(self.mattermost_data["post"]), 20)
        self.assertEqual(self.mattermost_data["post"][0]["team"], "gryffindor")
        self.assertEqual(self.mattermost_data["post"][0]["channel"], "dumbledores-army")
        self.assertEqual(self.mattermost_data["post"][0]["user"], "harry")
        self.assertEqual(len(self.mattermost_data["post"][0]["replies"]), 1)

        self.assertEqual(len(self.mattermost_data["emoji"]), 2)
        self.assertEqual(self.mattermost_data["emoji"][0]["name"], "peerdium")

    def test_process_user(self) -> None:
        user_id_mapper = IdMapper()

        harry_dict = self.username_to_user["harry"]
        harry_dict["is_mirror_dummy"] = False

        realm_id = 3

        team_name = "gryffindor"
        user = process_user(harry_dict, realm_id, team_name, user_id_mapper)
        self.assertEqual(user["avatar_source"], 'G')
        self.assertEqual(user["delivery_email"], "harry@zulip.com")
        self.assertEqual(user["email"], "harry@zulip.com")
        self.assertEqual(user["full_name"], "Harry Potter")
        self.assertEqual(user["id"], 1)
        self.assertEqual(user["is_active"], True)
        self.assertEqual(user["is_realm_admin"], True)
        self.assertEqual(user["is_guest"], False)
        self.assertEqual(user["is_mirror_dummy"], False)
        self.assertEqual(user["realm"], 3)
        self.assertEqual(user["short_name"], "harry")
        self.assertEqual(user["timezone"], "UTC")

        team_name = "slytherin"
        snape_dict = self.username_to_user["snape"]
        snape_dict["is_mirror_dummy"] = True
        user = process_user(snape_dict, realm_id, team_name, user_id_mapper)
        self.assertEqual(user["avatar_source"], 'G')
        self.assertEqual(user["delivery_email"], "snape@zulip.com")
        self.assertEqual(user["email"], "snape@zulip.com")
        self.assertEqual(user["full_name"], "Severus Snape")
        self.assertEqual(user["id"], 2)
        self.assertEqual(user["is_active"], False)
        self.assertEqual(user["is_realm_admin"], False)
        self.assertEqual(user["is_guest"], False)
        self.assertEqual(user["is_mirror_dummy"], True)
        self.assertEqual(user["realm"], 3)
        self.assertEqual(user["short_name"], "snape")
        self.assertEqual(user["timezone"], "UTC")

    def test_convert_user_data(self) -> None:
        user_id_mapper = IdMapper()
        realm_id = 3

        team_name = "gryffindor"
        user_handler = UserHandler()
        convert_user_data(user_handler, user_id_mapper, self.username_to_user, realm_id, team_name)
        self.assertTrue(user_id_mapper.has("harry"))
        self.assertTrue(user_id_mapper.has("ron"))
        self.assertEqual(user_handler.get_user(user_id_mapper.get("harry"))["full_name"], "Harry Potter")
        self.assertEqual(user_handler.get_user(user_id_mapper.get("ron"))["full_name"], "Ron Weasley")

        team_name = "slytherin"
        user_handler = UserHandler()
        convert_user_data(user_handler, user_id_mapper, self.username_to_user, realm_id, team_name)
        self.assertEqual(len(user_handler.get_all_users()), 3)
        self.assertTrue(user_id_mapper.has("malfoy"))
        self.assertTrue(user_id_mapper.has("pansy"))
        self.assertTrue(user_id_mapper.has("snape"))

        team_name = "gryffindor"
        # Snape is a mirror dummy user in Harry's team.
        label_mirror_dummy_users(team_name, self.mattermost_data, self.username_to_user)
        user_handler = UserHandler()
        convert_user_data(user_handler, user_id_mapper, self.username_to_user, realm_id, team_name)
        self.assertEqual(len(user_handler.get_all_users()), 3)
        self.assertTrue(user_id_mapper.has("snape"))

        team_name = "slytherin"
        user_handler = UserHandler()
        convert_user_data(user_handler, user_id_mapper, self.username_to_user, realm_id, team_name)
        self.assertEqual(len(user_handler.get_all_users()), 3)

    def test_convert_channel_data(self) -> None:
        user_handler = UserHandler()
        subscriber_handler = SubscriberHandler()
        stream_id_mapper = IdMapper()
        user_id_mapper = IdMapper()
        team_name = "gryffindor"

        convert_user_data(
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
            user_data_map=self.username_to_user,
            realm_id=3,
            team_name=team_name,
        )

        zerver_stream = convert_channel_data(
            channel_data=self.mattermost_data["channel"],
            user_data_map=self.username_to_user,
            subscriber_handler=subscriber_handler,
            stream_id_mapper=stream_id_mapper,
            user_id_mapper=user_id_mapper,
            realm_id=3,
            team_name=team_name,
        )

        self.assertEqual(len(zerver_stream), 3)

        self.assertEqual(zerver_stream[0]["name"], "Gryffindor common room")
        self.assertEqual(zerver_stream[0]["invite_only"], False)
        self.assertEqual(zerver_stream[0]["description"], "A place for talking about Gryffindor common room")
        self.assertEqual(zerver_stream[0]["rendered_description"], "")
        self.assertEqual(zerver_stream[0]["realm"], 3)

        self.assertEqual(zerver_stream[1]["name"], "Gryffindor quidditch team")
        self.assertEqual(zerver_stream[1]["invite_only"], False)
        self.assertEqual(zerver_stream[1]["description"], "A place for talking about Gryffindor quidditch team")
        self.assertEqual(zerver_stream[1]["rendered_description"], "")
        self.assertEqual(zerver_stream[1]["realm"], 3)

        self.assertEqual(zerver_stream[2]["name"], "Dumbledores army")
        self.assertEqual(zerver_stream[2]["invite_only"], True)
        self.assertEqual(zerver_stream[2]["description"], "A place for talking about Dumbledores army")
        self.assertEqual(zerver_stream[2]["rendered_description"], "")
        self.assertEqual(zerver_stream[2]["realm"], 3)

        self.assertTrue(stream_id_mapper.has("gryffindor-common-room"))
        self.assertTrue(stream_id_mapper.has("gryffindor-quidditch-team"))
        self.assertTrue(stream_id_mapper.has("dumbledores-army"))

        # TODO: Add ginny
        self.assertEqual(subscriber_handler.get_users(stream_id_mapper.get("gryffindor-common-room")), {1, 2})
        self.assertEqual(subscriber_handler.get_users(stream_id_mapper.get("gryffindor-quidditch-team")), {1, 2})
        self.assertEqual(subscriber_handler.get_users(stream_id_mapper.get("dumbledores-army")), {1, 2})

        team_name = "slytherin"
        zerver_stream = convert_channel_data(
            channel_data=self.mattermost_data["channel"],
            user_data_map=self.username_to_user,
            subscriber_handler=subscriber_handler,
            stream_id_mapper=stream_id_mapper,
            user_id_mapper=user_id_mapper,
            realm_id=4,
            team_name=team_name,
        )

        self.assertEqual(subscriber_handler.get_users(stream_id_mapper.get("slytherin-common-room")), {3, 4, 5})
        self.assertEqual(subscriber_handler.get_users(stream_id_mapper.get("slytherin-quidditch-team")), {3, 4})

    def test_write_emoticon_data(self) -> None:
        output_dir = self.make_import_output_dir("mattermost")
        zerver_realm_emoji = write_emoticon_data(
            realm_id=3,
            custom_emoji_data=self.mattermost_data["emoji"],
            data_dir=self.fixture_file_name("", "mattermost_fixtures"),
            output_dir = output_dir
        )
        self.assertEqual(len(zerver_realm_emoji), 2)
        self.assertEqual(zerver_realm_emoji[0]["file_name"], "peerdium")
        self.assertEqual(zerver_realm_emoji[0]["realm"], 3)
        self.assertEqual(zerver_realm_emoji[0]["deactivated"], False)

        self.assertEqual(zerver_realm_emoji[1]["file_name"], "tick")
        self.assertEqual(zerver_realm_emoji[1]["realm"], 3)
        self.assertEqual(zerver_realm_emoji[1]["deactivated"], False)

        records_file = os.path.join(output_dir, "emoji", "records.json")
        with open(records_file, "r") as f:
            records_json = ujson.load(f)

        self.assertEqual(records_json[0]["file_name"], "peerdium")
        self.assertEqual(records_json[0]["realm_id"], 3)
        exported_emoji_path = self.fixture_file_name(self.mattermost_data["emoji"][0]["image"], "mattermost_fixtures")
        self.assertTrue(filecmp.cmp(records_json[0]["path"], exported_emoji_path))

        self.assertEqual(records_json[1]["file_name"], "tick")
        self.assertEqual(records_json[1]["realm_id"], 3)
        exported_emoji_path = self.fixture_file_name(self.mattermost_data["emoji"][1]["image"], "mattermost_fixtures")
        self.assertTrue(filecmp.cmp(records_json[1]["path"], exported_emoji_path))

    def test_get_mentioned_user_ids(self) -> None:
        user_id_mapper = IdMapper()
        harry_id = user_id_mapper.get("harry")

        raw_message = {
            "content": "Hello @harry"
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id])

        raw_message = {
            "content": "Hello"
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [])

        raw_message = {
            "content": "@harry How are you?"
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id])

        raw_message = {
            "content": "@harry @ron Where are you folks?"
        }
        ron_id = user_id_mapper.get("ron")
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id, ron_id])

        raw_message = {
            "content": "@harry.com How are you?"
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [])

        raw_message = {
            "content": "hello@harry.com How are you?"
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [])

        harry_id = user_id_mapper.get("harry_")
        raw_message = {
            "content": "Hello @harry_"
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id])

        harry_id = user_id_mapper.get("harry.")
        raw_message = {
            "content": "Hello @harry."
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id])

        harry_id = user_id_mapper.get("ha_rry.")
        raw_message = {
            "content": "Hello @ha_rry."
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id])

        ron_id = user_id_mapper.get("ron")
        raw_message = {
            "content": "Hello @ron."
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [])

        raw_message = {
            "content": "Hello @ron_"
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [])

    def test_check_user_in_team(self) -> None:
        harry = self.username_to_user["harry"]
        self.assertTrue(check_user_in_team(harry, "gryffindor"))
        self.assertFalse(check_user_in_team(harry, "slytherin"))

        snape = self.username_to_user["snape"]
        self.assertFalse(check_user_in_team(snape, "gryffindor"))
        self.assertTrue(check_user_in_team(snape, "slytherin"))

    def test_label_mirror_dummy_users(self) -> None:
        label_mirror_dummy_users(
            team_name="gryffindor",
            mattermost_data=self.mattermost_data,
            username_to_user=self.username_to_user,
        )
        self.assertFalse(self.username_to_user["harry"]["is_mirror_dummy"])
        self.assertFalse(self.username_to_user["ron"]["is_mirror_dummy"])
        self.assertFalse(self.username_to_user["malfoy"]["is_mirror_dummy"])

        # snape is mirror dummy since the user sent a message in gryffindor and
        # left the team
        self.assertTrue(self.username_to_user["snape"]["is_mirror_dummy"])

    def test_build_reactions(self) -> None:
        total_reactions = []  # type: List[Dict[str, Any]]

        reactions = [
            {"user": "harry", "create_at": 1553165521410, "emoji_name": "tick"},
            {"user": "ron", "create_at": 1553166530805, "emoji_name": "smile"},
            {"user": "ron", "create_at": 1553166540953, "emoji_name": "world_map"},
            {"user": "harry", "create_at": 1553166540957, "emoji_name": "world_map"}
        ]

        zerver_realmemoji = write_emoticon_data(
            realm_id=3,
            custom_emoji_data=self.mattermost_data["emoji"],
            data_dir=self.fixture_file_name("", "mattermost_fixtures"),
            output_dir=self.make_import_output_dir("mattermost")
        )

        # Make sure tick is present in fixture data
        self.assertEqual(zerver_realmemoji[1]["name"], "tick")
        tick_emoji_code = zerver_realmemoji[1]["id"]

        name_to_codepoint = get_name_to_codepoint_dict()
        user_id_mapper = IdMapper()
        harry_id = user_id_mapper.get("harry")
        ron_id = user_id_mapper.get("ron")

        build_reactions(
            realm_id=3,
            total_reactions=total_reactions,
            reactions=reactions,
            message_id=5,
            name_to_codepoint=name_to_codepoint,
            user_id_mapper=user_id_mapper,
            zerver_realmemoji=zerver_realmemoji
        )

        smile_emoji_code = name_to_codepoint["smile"]
        world_map_emoji_code = name_to_codepoint["world_map"]

        self.assertEqual(len(total_reactions), 4)
        self.assertEqual(self.get_set(total_reactions, "reaction_type"), set([Reaction.REALM_EMOJI, Reaction.UNICODE_EMOJI]))
        self.assertEqual(self.get_set(total_reactions, "emoji_name"), set(["tick", "smile", "world_map"]))
        self.assertEqual(self.get_set(total_reactions, "emoji_code"), set([tick_emoji_code, smile_emoji_code,
                                                                           world_map_emoji_code]))
        self.assertEqual(self.get_set(total_reactions, "user_profile"), set([harry_id, ron_id]))
        self.assertEqual(len(self.get_set(total_reactions, "id")), 4)
        self.assertEqual(len(self.get_set(total_reactions, "message")), 1)

    def team_output_dir(self, output_dir: str, team_name: str) -> str:
        return os.path.join(output_dir, team_name)

    def read_file(self, team_output_dir: str, output_file: str) -> Any:
        full_path = os.path.join(team_output_dir, output_file)
        with open(full_path) as f:
            return ujson.load(f)

    def test_do_convert_data(self) -> None:
        mattermost_data_dir = self.fixture_file_name("", "mattermost_fixtures")
        output_dir = self.make_import_output_dir("mattermost")

        do_convert_data(
            mattermost_data_dir=mattermost_data_dir,
            output_dir=output_dir,
            masking_content=False
        )

        harry_team_output_dir = self.team_output_dir(output_dir, "gryffindor")
        self.assertEqual(os.path.exists(os.path.join(harry_team_output_dir, 'avatars')), True)
        self.assertEqual(os.path.exists(os.path.join(harry_team_output_dir, 'emoji')), True)
        self.assertEqual(os.path.exists(os.path.join(harry_team_output_dir, 'attachment.json')), True)

        realm = self.read_file(harry_team_output_dir, 'realm.json')

        self.assertEqual('Organization imported from Mattermost!',
                         realm['zerver_realm'][0]['description'])

        exported_user_ids = self.get_set(realm['zerver_userprofile'], 'id')
        exported_user_full_names = self.get_set(realm['zerver_userprofile'], 'full_name')
        self.assertEqual(set(['Harry Potter', 'Ron Weasley', 'Severus Snape']), exported_user_full_names)

        exported_user_emails = self.get_set(realm['zerver_userprofile'], 'email')
        self.assertEqual(set(['harry@zulip.com', 'ron@zulip.com', 'snape@zulip.com']), exported_user_emails)

        self.assertEqual(len(realm['zerver_stream']), 3)
        exported_stream_names = self.get_set(realm['zerver_stream'], 'name')
        self.assertEqual(exported_stream_names, set(['Gryffindor common room', 'Gryffindor quidditch team', 'Dumbledores army']))
        self.assertEqual(self.get_set(realm['zerver_stream'], 'realm'), set([realm['zerver_realm'][0]['id']]))
        self.assertEqual(self.get_set(realm['zerver_stream'], 'deactivated'), set([False]))

        self.assertEqual(len(realm['zerver_defaultstream']), 0)

        exported_recipient_ids = self.get_set(realm['zerver_recipient'], 'id')
        self.assertEqual(len(exported_recipient_ids), 6)
        exported_recipient_types = self.get_set(realm['zerver_recipient'], 'type')
        self.assertEqual(exported_recipient_types, set([1, 2]))
        exported_recipient_type_ids = self.get_set(realm['zerver_recipient'], 'type_id')
        self.assertEqual(len(exported_recipient_type_ids), 3)

        exported_subscription_userprofile = self.get_set(realm['zerver_subscription'], 'user_profile')
        self.assertEqual(len(exported_subscription_userprofile), 3)
        exported_subscription_recipients = self.get_set(realm['zerver_subscription'], 'recipient')
        self.assertEqual(len(exported_subscription_recipients), 6)

        messages = self.read_file(harry_team_output_dir, 'messages-000001.json')

        exported_messages_id = self.get_set(messages['zerver_message'], 'id')
        self.assertIn(messages['zerver_message'][0]['sender'], exported_user_ids)
        self.assertIn(messages['zerver_message'][0]['recipient'], exported_recipient_ids)
        self.assertIn(messages['zerver_message'][0]['content'], 'harry joined the channel.\n\n')

        exported_usermessage_userprofiles = self.get_set(messages['zerver_usermessage'], 'user_profile')
        self.assertEqual(len(exported_usermessage_userprofiles), 2)
        exported_usermessage_messages = self.get_set(messages['zerver_usermessage'], 'message')
        self.assertEqual(exported_usermessage_messages, exported_messages_id)

        do_import_realm(
            import_dir=harry_team_output_dir,
            subdomain='gryffindor'
        )
        realm = get_realm('gryffindor')

        realm_users = UserProfile.objects.filter(realm=realm)
        messages = Message.objects.filter(sender__in=realm_users)
        for message in messages:
            self.assertIsNotNone(message.rendered_content)

    def test_do_convert_data_with_masking(self) -> None:
        mattermost_data_dir = self.fixture_file_name("", "mattermost_fixtures")
        output_dir = self.make_import_output_dir("mattermost")

        do_convert_data(
            mattermost_data_dir=mattermost_data_dir,
            output_dir=output_dir,
            masking_content=True
        )

        harry_team_output_dir = self.team_output_dir(output_dir, "gryffindor")
        messages = self.read_file(harry_team_output_dir, 'messages-000001.json')

        self.assertIn(messages['zerver_message'][0]['content'], 'xxxxx xxxxxx xxx xxxxxxx.\n\n')

    def test_import_data_to_existing_database(self) -> None:
        mattermost_data_dir = self.fixture_file_name("", "mattermost_fixtures")
        output_dir = self.make_import_output_dir("mattermost")

        do_convert_data(
            mattermost_data_dir=mattermost_data_dir,
            output_dir=output_dir,
            masking_content=True
        )

        harry_team_output_dir = self.team_output_dir(output_dir, "gryffindor")

        do_import_realm(
            import_dir=harry_team_output_dir,
            subdomain='gryffindor'
        )
        realm = get_realm('gryffindor')

        realm_users = UserProfile.objects.filter(realm=realm)
        messages = Message.objects.filter(sender__in=realm_users)
        for message in messages:
            self.assertIsNotNone(message.rendered_content)
