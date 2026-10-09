import filecmp
import glob
import json
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import orjson
from django.test import override_settings
from typing_extensions import override

from zerver.data_import.import_util import (
    AttachmentRecordData,
    SubscriberHandler,
    UploadRecordData,
    ZerverFieldsT,
)
from zerver.data_import.mattermost import (
    COMPILED_CHANNEL_ID_FORMAT,
    DEFAULT_SINGLE_TEAM_OBJECT,
    backfill_user_data_from_posts,
    build_reactions,
    check_user_in_team,
    convert_channel_data,
    convert_direct_message_group_data,
    convert_user_data,
    create_username_to_user_mapping,
    do_convert_data,
    get_mentioned_user_ids,
    make_realm,
    mattermost_data_file_to_dict,
    process_message_attachments,
    process_user,
    reset_mirror_dummy_users,
    write_emoticon_data,
)
from zerver.data_import.sequencer import IdMapper
from zerver.data_import.user_handler import UserHandler
from zerver.lib.emoji import name_to_codepoint
from zerver.lib.import_realm import do_import_realm
from zerver.lib.test_classes import (
    ExpectedChannel,
    ExpectedMessage,
    ExpectedUser,
    ImporterContractTestBase,
    ZulipTestCase,
)
from zerver.models import Attachment, Message, Reaction, Recipient, UserProfile
from zerver.models.presence import PresenceSequence
from zerver.models.realms import get_realm
from zerver.models.streams import Stream
from zerver.models.users import get_user
from zerver.tests.test_import_export import make_export_output_dir


class MattermostImportTestBase(ZulipTestCase):
    def team_output_dir(self, output_dir: str, team_name: str) -> str:
        return os.path.join(output_dir, team_name)

    def read_file(self, team_output_dir: str, output_file: str) -> Any:
        full_path = os.path.join(team_output_dir, output_file)
        with open(full_path, "rb") as f:
            return orjson.loads(f.read())


class MatterMostImporter(MattermostImportTestBase):
    def test_mattermost_data_file_to_dict(self) -> None:
        fixture_file_name = self.fixture_file_name("export.json", "mattermost_fixtures")
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        self.assert_length(mattermost_data, 8)

        self.assertEqual(mattermost_data["version"], [1])

        self.assert_length(mattermost_data["team"], 2)
        self.assertEqual(mattermost_data["team"][0]["name"], "gryffindor")

        self.assert_length(mattermost_data["channel"], 13)
        self.assertEqual(mattermost_data["channel"][0]["name"], "gryffindor-common-room")
        self.assertEqual(mattermost_data["channel"][0]["team"], "gryffindor")

        self.assert_length(mattermost_data["user"], 5)
        self.assertEqual(mattermost_data["user"][1]["username"], "harry")
        self.assert_length(mattermost_data["user"][1]["teams"], 1)

        self.assert_length(mattermost_data["post"]["channel_post"], 21)
        self.assertEqual(mattermost_data["post"]["channel_post"][0]["team"], "gryffindor")
        self.assertEqual(mattermost_data["post"]["channel_post"][0]["channel"], "dumbledores-army")
        self.assertEqual(mattermost_data["post"]["channel_post"][0]["user"], "harry")
        self.assert_length(mattermost_data["post"]["channel_post"][0]["replies"], 1)

        self.assert_length(mattermost_data["emoji"], 2)
        self.assertEqual(mattermost_data["emoji"][0]["name"], "peerdium")

        fixture_file_name = self.fixture_file_name(
            "export.json", "mattermost_fixtures/direct_channel"
        )
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)

        self.assert_length(mattermost_data["post"]["channel_post"], 4)
        self.assertEqual(mattermost_data["post"]["channel_post"][0]["team"], "gryffindor")
        self.assertEqual(
            mattermost_data["post"]["channel_post"][0]["channel"], "gryffindor-common-room"
        )
        self.assertEqual(mattermost_data["post"]["channel_post"][0]["user"], "ron")
        self.assertEqual(mattermost_data["post"]["channel_post"][0]["replies"], None)

        self.assert_length(mattermost_data["post"]["direct_post"], 7)
        self.assertEqual(mattermost_data["post"]["direct_post"][0]["user"], "ron")
        self.assertEqual(mattermost_data["post"]["direct_post"][0]["replies"], None)
        self.assertEqual(mattermost_data["post"]["direct_post"][0]["message"], "hey harry")
        self.assertEqual(
            mattermost_data["post"]["direct_post"][0]["channel_members"], ["ron", "harry"]
        )

    def test_process_user(self) -> None:
        user_id_mapper = IdMapper[str]()
        fixture_file_name = self.fixture_file_name("export.json", "mattermost_fixtures")
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        username_to_user = create_username_to_user_mapping(mattermost_data["user"])
        reset_mirror_dummy_users(username_to_user)

        harry_dict = username_to_user["harry"]
        harry_dict["is_mirror_dummy"] = False

        realm_id = 3

        team_name = "gryffindor"
        user = process_user(harry_dict, realm_id, team_name, user_id_mapper)
        self.assertEqual(user["avatar_source"], "J")
        self.assertEqual(user["delivery_email"], "harry@zulip.com")
        self.assertEqual(user["email"], "harry@zulip.com")
        self.assertEqual(user["full_name"], "Harry Potter")
        self.assertEqual(user["id"], 1)
        self.assertEqual(user["is_active"], True)
        self.assertEqual(user["role"], UserProfile.ROLE_REALM_OWNER)
        self.assertEqual(user["is_mirror_dummy"], False)
        self.assertEqual(user["realm"], 3)
        self.assertEqual(user["short_name"], "harry")
        self.assertEqual(user["timezone"], "UTC")
        self.assertEqual(user["is_imported_stub"], True)

        # A user with a `null` team value shouldn't be an admin.
        harry_dict["teams"] = None
        user = process_user(harry_dict, realm_id, team_name, user_id_mapper)
        self.assertEqual(user["role"], UserProfile.ROLE_MEMBER)

        team_name = "slytherin"
        snape_dict = username_to_user["snape"]
        snape_dict["is_mirror_dummy"] = True
        user = process_user(snape_dict, realm_id, team_name, user_id_mapper)
        self.assertEqual(user["avatar_source"], "J")
        self.assertEqual(user["delivery_email"], "snape@zulip.com")
        self.assertEqual(user["email"], "snape@zulip.com")
        self.assertEqual(user["full_name"], "Severus Snape")
        self.assertEqual(user["id"], 2)
        self.assertEqual(user["is_active"], False)
        self.assertEqual(user["role"], UserProfile.ROLE_MEMBER)
        self.assertEqual(user["is_mirror_dummy"], True)
        self.assertEqual(user["realm"], 3)
        self.assertEqual(user["short_name"], "snape")
        self.assertEqual(user["timezone"], "UTC")
        self.assertEqual(user["is_imported_stub"], True)

    def test_process_guest_user(self) -> None:
        user_id_mapper = IdMapper[str]()
        fixture_file_name = self.fixture_file_name("guestExport.json", "mattermost_fixtures")
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        username_to_user = create_username_to_user_mapping(mattermost_data["user"])
        reset_mirror_dummy_users(username_to_user)

        sirius_dict = username_to_user["sirius"]
        sirius_dict["is_mirror_dummy"] = False

        realm_id = 3

        team_name = "slytherin"
        user = process_user(sirius_dict, realm_id, team_name, user_id_mapper)
        self.assertEqual(user["avatar_source"], "J")
        self.assertEqual(user["delivery_email"], "sirius@zulip.com")
        self.assertEqual(user["email"], "sirius@zulip.com")
        self.assertEqual(user["full_name"], "Sirius Black")
        self.assertEqual(user["role"], UserProfile.ROLE_GUEST)
        self.assertEqual(user["is_mirror_dummy"], False)
        self.assertEqual(user["realm"], 3)
        self.assertEqual(user["short_name"], "sirius")
        self.assertEqual(user["timezone"], "UTC")
        self.assertEqual(user["is_imported_stub"], True)

        # A guest user with a `null` team value should be a regular
        # user. (It's a bit of a mystery why the Mattermost export
        # tool generates such `teams` lists).
        sirius_dict["teams"] = None
        user = process_user(sirius_dict, realm_id, team_name, user_id_mapper)
        self.assertEqual(user["role"], UserProfile.ROLE_MEMBER)

    def test_convert_user_data(self) -> None:
        user_id_mapper = IdMapper[str]()
        realm_id = 3
        fixture_file_name = self.fixture_file_name("export.json", "mattermost_fixtures")
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        username_to_user = create_username_to_user_mapping(mattermost_data["user"])
        reset_mirror_dummy_users(username_to_user)

        team_name = "gryffindor"
        user_handler = UserHandler()
        realm = make_realm(realm_id=0, team={"name": team_name})
        convert_user_data(
            user_handler, user_id_mapper, username_to_user, realm, realm_id, team_name
        )
        self.assert_length(user_handler.get_all_users(), 2)
        self.assertTrue(user_id_mapper.has("harry"))
        self.assertTrue(user_id_mapper.has("ron"))
        self.assertEqual(
            user_handler.get_user(user_id_mapper.get("harry"))["full_name"], "Harry Potter"
        )
        self.assertEqual(
            user_handler.get_user(user_id_mapper.get("ron"))["full_name"], "Ron Weasley"
        )

        team_name = "slytherin"
        user_handler = UserHandler()
        realm = make_realm(realm_id=0, team={"name": team_name})
        convert_user_data(
            user_handler, user_id_mapper, username_to_user, realm, realm_id, team_name
        )
        self.assert_length(user_handler.get_all_users(), 3)
        self.assertTrue(user_id_mapper.has("malfoy"))
        self.assertTrue(user_id_mapper.has("pansy"))
        self.assertTrue(user_id_mapper.has("snape"))

        team_name = "gryffindor"
        # Snape is a mirror dummy user in Harry's team.
        backfill_user_data_from_posts(2, team_name, mattermost_data, username_to_user)
        user_handler = UserHandler()
        realm = make_realm(realm_id=0, team={"name": team_name})
        convert_user_data(
            user_handler, user_id_mapper, username_to_user, realm, realm_id, team_name
        )
        self.assert_length(user_handler.get_all_users(), 3)
        self.assertTrue(user_id_mapper.has("snape"))

        team_name = "slytherin"
        user_handler = UserHandler()
        realm = make_realm(realm_id=0, team={"name": team_name})
        convert_user_data(
            user_handler, user_id_mapper, username_to_user, realm, realm_id, team_name
        )
        self.assert_length(user_handler.get_all_users(), 3)

        # Warn if the converted realm will have no realm owner.
        team_name = "gryffindor"
        user_map_with_no_realm_owner = {
            k: v
            for k, v in username_to_user.items()
            if any("team_admin" not in team["roles"] for team in v["teams"])
        }
        with self.assertLogs(level="INFO") as info_log:
            convert_user_data(
                user_handler,
                user_id_mapper,
                user_map_with_no_realm_owner,
                realm,
                realm_id,
                team_name,
            )
        self.assertEqual(
            info_log.output,
            ["WARNING:root:Converted realm has no owners!"],
        )

        # Importer should raise error when user emails are malformed
        team_name = "gryffindor"
        bad_email1 = username_to_user["harry"]["email"] = "harry.ceramicist@zuL1[p.c0m"
        bad_email2 = username_to_user["ron"]["email"] = "ron.ferret@zulup...com"
        realm = make_realm(realm_id=0, team={"name": team_name})
        with self.assertRaises(Exception) as e:
            convert_user_data(
                user_handler, user_id_mapper, username_to_user, realm, realm_id, team_name
            )
        error_message = str(e.exception)
        expected_error_message = f"['Invalid email format, please fix the following email(s) and try again: {bad_email2}, {bad_email1}']"
        self.assertEqual(error_message, expected_error_message)

    def test_convert_channel_data(self) -> None:
        fixture_file_name = self.fixture_file_name("export.json", "mattermost_fixtures")
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        username_to_user = create_username_to_user_mapping(mattermost_data["user"])
        reset_mirror_dummy_users(username_to_user)

        user_handler = UserHandler()
        subscriber_handler = SubscriberHandler[frozenset[str]]()
        stream_id_mapper = IdMapper[str]()
        user_id_mapper = IdMapper[str]()
        team_name = "gryffindor"

        mock_realm_dict: ZerverFieldsT = make_realm(realm_id=0, team={"name": team_name})
        zerver_realm = mock_realm_dict["zerver_realm"]

        convert_user_data(
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
            user_data_map=username_to_user,
            realm=mock_realm_dict,
            realm_id=3,
            team_name=team_name,
        )

        with patch(
            "zerver.data_import.mattermost.MATTERMOST_DEFAULT_ANNOUNCEMENTS_CHANNEL_NAME",
            "Gryffindor common room",
        ):
            convert_channel_data(
                realm=mock_realm_dict,
                channel_data=mattermost_data["channel"],
                user_data_map=username_to_user,
                subscriber_handler=subscriber_handler,
                stream_id_mapper=stream_id_mapper,
                user_id_mapper=user_id_mapper,
                realm_id=3,
                team_name=team_name,
            )
        zerver_stream = mock_realm_dict["zerver_stream"]
        self.assert_length(zerver_stream, 11)

        self.assertEqual(zerver_stream[0]["name"], "Gryffindor common room")
        self.assertEqual(zerver_stream[0]["invite_only"], False)
        self.assertEqual(
            zerver_stream[0]["description"], "A place for talking about Gryffindor common room"
        )
        self.assertEqual(zerver_stream[0]["rendered_description"], "")
        self.assertEqual(zerver_stream[0]["realm"], 3)

        self.assertEqual(
            zerver_realm[0]["zulip_update_announcements_stream"], zerver_stream[0]["id"]
        )
        self.assertEqual(zerver_realm[0]["new_stream_announcements_stream"], zerver_stream[0]["id"])

        self.assertEqual(zerver_stream[1]["name"], "Gryffindor quidditch team")
        self.assertEqual(zerver_stream[1]["invite_only"], False)
        self.assertEqual(
            zerver_stream[1]["description"], "A place for talking about Gryffindor quidditch team"
        )
        self.assertEqual(zerver_stream[1]["rendered_description"], "")
        self.assertEqual(zerver_stream[1]["realm"], 3)

        self.assertEqual(zerver_stream[2]["name"], "Dumbledores army")
        self.assertEqual(zerver_stream[2]["invite_only"], True)
        self.assertEqual(
            zerver_stream[2]["description"], "A place for talking about Dumbledores army"
        )
        self.assertEqual(zerver_stream[2]["rendered_description"], "")
        self.assertEqual(zerver_stream[2]["realm"], 3)
        # Long channel name is truncated
        self.assertEqual(
            zerver_stream[3]["name"],
            "Super long channel name, it's more than 60 characters, whic…",  # codespell:ignore whic
        )
        self.assertGreaterEqual(Stream.MAX_NAME_LENGTH, len(zerver_stream[3]["name"]))
        self.assertEqual(
            zerver_stream[4]["name"], "Super long channel name, it's more than 60 characters, … (2)"
        )
        self.assertGreaterEqual(Stream.MAX_NAME_LENGTH, len(zerver_stream[4]["name"]))
        # Identical truncated channel names doesn't collide
        self.assertEqual(
            zerver_stream[5]["name"], "Super long channel name, it's more than 60 characters, … (3)"
        )
        self.assertGreaterEqual(Stream.MAX_NAME_LENGTH, len(zerver_stream[5]["name"]))

        # Channel names which differ only in capitalization need collision resolution,
        # because Zulip treats them case-insensitively.
        self.assertEqual(zerver_stream[7]["name"], "Slug club")
        self.assertEqual(zerver_stream[8]["name"], "SLUG CLUB (2)")
        # "Slug club (3)" is imported as an original channel name from Mattermost.
        # Collision resolution for the "slug club" channel then generates the same name,
        # which therefore needs another round of collision resolution itself, resulting
        # in a doubly suffixed name.
        self.assertEqual(zerver_stream[9]["name"], "Slug club (3)")
        self.assertEqual(zerver_stream[10]["name"], "slug club (3) (2)")

        self.assertTrue(stream_id_mapper.has("gryffindor-common-room"))
        self.assertTrue(stream_id_mapper.has("gryffindor-quidditch-team"))
        self.assertTrue(stream_id_mapper.has("dumbledores-army"))

        # TODO: Add ginny
        ron_id = user_id_mapper.get("ron")
        harry_id = user_id_mapper.get("harry")
        self.assertEqual({ron_id, harry_id}, {1, 2})
        self.assertEqual(
            subscriber_handler.get_users(stream_id=stream_id_mapper.get("gryffindor-common-room")),
            {ron_id, harry_id},
        )
        self.assertEqual(
            subscriber_handler.get_users(
                stream_id=stream_id_mapper.get("gryffindor-quidditch-team")
            ),
            {ron_id, harry_id},
        )
        self.assertEqual(
            subscriber_handler.get_users(stream_id=stream_id_mapper.get("dumbledores-army")),
            {ron_id, harry_id},
        )

        # Converting channel data when a user's `teams` value is `null`.
        username_to_user["ron"].update(teams=None)
        mock_realm_dict = make_realm(realm_id=0, team={"name": "test-realm"})
        zerver_stream = convert_channel_data(
            realm=mock_realm_dict,
            channel_data=mattermost_data["channel"],
            user_data_map=username_to_user,
            subscriber_handler=subscriber_handler,
            stream_id_mapper=stream_id_mapper,
            user_id_mapper=user_id_mapper,
            realm_id=3,
            team_name=team_name,
        )
        harry_id = user_id_mapper.get("harry")
        self.assertIn(harry_id, {1, 2})
        self.assertEqual(
            subscriber_handler.get_users(stream_id=stream_id_mapper.get("gryffindor-common-room")),
            {harry_id},
        )
        self.assertEqual(
            subscriber_handler.get_users(
                stream_id=stream_id_mapper.get("gryffindor-quidditch-team")
            ),
            {harry_id},
        )
        self.assertEqual(
            subscriber_handler.get_users(stream_id=stream_id_mapper.get("dumbledores-army")),
            {harry_id},
        )

        team_name = "slytherin"
        mock_realm_dict = make_realm(realm_id=0, team={"name": "test-realm"})
        zerver_stream = convert_channel_data(
            realm=mock_realm_dict,
            channel_data=mattermost_data["channel"],
            user_data_map=username_to_user,
            subscriber_handler=subscriber_handler,
            stream_id_mapper=stream_id_mapper,
            user_id_mapper=user_id_mapper,
            realm_id=4,
            team_name=team_name,
        )

        malfoy_id = user_id_mapper.get("malfoy")
        pansy_id = user_id_mapper.get("pansy")
        snape_id = user_id_mapper.get("snape")
        self.assertEqual({malfoy_id, pansy_id, snape_id}, {3, 4, 5})
        self.assertEqual(
            subscriber_handler.get_users(stream_id=stream_id_mapper.get("slytherin-common-room")),
            {malfoy_id, pansy_id, snape_id},
        )
        self.assertEqual(
            subscriber_handler.get_users(
                stream_id=stream_id_mapper.get("slytherin-quidditch-team")
            ),
            {malfoy_id, pansy_id},
        )

    def test_convert_direct_message_group_data(self) -> None:
        fixture_file_name = self.fixture_file_name(
            "export.json", "mattermost_fixtures/direct_channel"
        )
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        username_to_user = create_username_to_user_mapping(mattermost_data["user"])
        reset_mirror_dummy_users(username_to_user)

        user_handler = UserHandler()
        subscriber_handler = SubscriberHandler[frozenset[str]]()
        direct_message_group_id_mapper = IdMapper[frozenset[str]]()
        user_id_mapper = IdMapper[str]()
        team_name = "gryffindor"
        realm = make_realm(realm_id=0, team={"name": team_name})

        convert_user_data(
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
            user_data_map=username_to_user,
            realm=realm,
            realm_id=3,
            team_name=team_name,
        )

        with self.assertLogs(level="INFO") as mock_log:
            zerver_huddle = convert_direct_message_group_data(
                direct_message_group_data=mattermost_data["direct_channel"],
                user_data_map=username_to_user,
                subscriber_handler=subscriber_handler,
                direct_message_group_id_mapper=direct_message_group_id_mapper,
                user_id_mapper=user_id_mapper,
                realm=realm,
                realm_id=3,
                team_name=team_name,
            )

        self.assert_length(zerver_huddle, 3)

        expected_dm_groups = [
            (0, {2, 3}),  # direct_channel[0] should have users 2, 3
            (1, {1, 2, 3}),  # direct_channel[1] should have users 1, 2, 3
            (3, {3}),  # direct_channel[3] should have users 3
        ]

        for channel_index, expected_users in expected_dm_groups:
            direct_message_group_members = frozenset(
                [
                    username
                    for username in mattermost_data["direct_channel"][channel_index]["members"]
                    if user_id_mapper.has(username)
                ]
            )
            self.assertTrue(direct_message_group_id_mapper.has(direct_message_group_members))
            actual_users = subscriber_handler.get_users(
                direct_message_group_id=direct_message_group_id_mapper.get(
                    direct_message_group_members
                )
            )
            self.assertEqual(actual_users, expected_users)

        self.assertEqual(
            mock_log.output,
            ["INFO:root:Duplicate direct message group found in the export data. Skipping."],
        )

    def test_write_emoticon_data(self) -> None:
        fixture_file_name = self.fixture_file_name("export.json", "mattermost_fixtures")
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        output_dir = self.make_import_output_dir("mattermost")

        with self.assertLogs(level="INFO"):
            zerver_realm_emoji = write_emoticon_data(
                realm_id=3,
                custom_emoji_data=mattermost_data["emoji"],
                data_dir=self.fixture_file_name("", "mattermost_fixtures"),
                output_dir=output_dir,
            )

        self.assert_length(zerver_realm_emoji, 2)
        self.assertEqual(zerver_realm_emoji[0]["file_name"], "peerdium")
        self.assertEqual(zerver_realm_emoji[0]["realm"], 3)
        self.assertEqual(zerver_realm_emoji[0]["deactivated"], False)

        self.assertEqual(zerver_realm_emoji[1]["file_name"], "tick")
        self.assertEqual(zerver_realm_emoji[1]["realm"], 3)
        self.assertEqual(zerver_realm_emoji[1]["deactivated"], False)

        records_file = os.path.join(output_dir, "emoji", "records.json")
        with open(records_file, "rb") as f:
            records_json = orjson.loads(f.read())

        self.assertEqual(records_json[0]["file_name"], "peerdium")
        self.assertEqual(records_json[0]["realm_id"], 3)
        exported_emoji_path = self.fixture_file_name(
            mattermost_data["emoji"][0]["image"], "mattermost_fixtures"
        )
        emoji_dir = os.path.join(output_dir, "emoji")
        self.assertTrue(
            filecmp.cmp(os.path.join(emoji_dir, records_json[0]["path"]), exported_emoji_path)
        )

        self.assertEqual(records_json[1]["file_name"], "tick")
        self.assertEqual(records_json[1]["realm_id"], 3)
        exported_emoji_path = self.fixture_file_name(
            mattermost_data["emoji"][1]["image"], "mattermost_fixtures"
        )
        self.assertTrue(
            filecmp.cmp(os.path.join(emoji_dir, records_json[1]["path"]), exported_emoji_path)
        )

    def test_process_message_attachments(self) -> None:
        mattermost_data_dir = self.fixture_file_name("", "mattermost_fixtures/direct_channel")
        output_dir = self.make_import_output_dir("mattermost")

        fixture_file_name = self.fixture_file_name(
            "export.json", "mattermost_fixtures/direct_channel"
        )
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        username_to_user = create_username_to_user_mapping(mattermost_data["user"])
        reset_mirror_dummy_users(username_to_user)

        user_handler = UserHandler()
        user_id_mapper = IdMapper[str]()
        team_name = "gryffindor"
        realm = make_realm(realm_id=0, team={"name": team_name})

        convert_user_data(
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
            user_data_map=username_to_user,
            realm=realm,
            realm_id=3,
            team_name=team_name,
        )

        zerver_attachments: list[AttachmentRecordData] = []
        uploads_list: list[UploadRecordData] = []

        process_message_attachments(
            attachments=mattermost_data["post"]["direct_post"][0]["attachments"],
            realm_id=3,
            message_id=1,
            user_id=2,
            zerver_attachment=zerver_attachments,
            uploads_list=uploads_list,
            mattermost_data_dir=mattermost_data_dir,
            output_dir=output_dir,
        )

        self.assert_length(zerver_attachments, 1)
        self.assertEqual(zerver_attachments[0].file_name, "harry-ron.jpg")
        self.assertEqual(zerver_attachments[0].owner, 2)
        self.assertEqual(
            user_handler.get_user(zerver_attachments[0].owner)["email"], "ron@zulip.com"
        )
        # TODO: Assert this for False after fixing the file permissions in direct messages
        self.assertTrue(zerver_attachments[0].is_realm_public)

        self.assert_length(uploads_list, 1)
        self.assertEqual(uploads_list[0].user_profile_id, 2)

        attachment_path = self.fixture_file_name(
            mattermost_data["post"]["direct_post"][0]["attachments"][0]["path"],
            "mattermost_fixtures/direct_channel/data",
        )
        attachment_out_path = os.path.join(output_dir, "uploads", zerver_attachments[0].path_id)
        self.assertTrue(os.path.exists(attachment_out_path))
        self.assertTrue(filecmp.cmp(attachment_path, attachment_out_path))

    def test_get_mentioned_user_ids(self) -> None:
        user_id_mapper = IdMapper[str]()
        harry_id = user_id_mapper.get("harry")

        raw_message = {
            "content": "Hello @harry",
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id])

        raw_message = {
            "content": "Hello",
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [])

        raw_message = {
            "content": "@harry How are you?",
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id])

        raw_message = {
            "content": "@harry @ron Where are you folks?",
        }
        ron_id = user_id_mapper.get("ron")
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id, ron_id])

        raw_message = {
            "content": "@harry.com How are you?",
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [])

        raw_message = {
            "content": "hello@harry.com How are you?",
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [])

        harry_id = user_id_mapper.get("harry_")
        raw_message = {
            "content": "Hello @harry_",
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id])

        harry_id = user_id_mapper.get("harry.")
        raw_message = {
            "content": "Hello @harry.",
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id])

        harry_id = user_id_mapper.get("ha_rry.")
        raw_message = {
            "content": "Hello @ha_rry.",
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [harry_id])

        ron_id = user_id_mapper.get("ron")
        raw_message = {
            "content": "Hello @ron.",
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [])

        raw_message = {
            "content": "Hello @ron_",
        }
        ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        self.assertEqual(list(ids), [])

    def test_check_user_in_team(self) -> None:
        fixture_file_name = self.fixture_file_name("export.json", "mattermost_fixtures")
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        username_to_user = create_username_to_user_mapping(mattermost_data["user"])
        reset_mirror_dummy_users(username_to_user)

        harry = username_to_user["harry"]
        self.assertTrue(check_user_in_team(harry, "gryffindor"))
        self.assertFalse(check_user_in_team(harry, "slytherin"))

        snape = username_to_user["snape"]
        self.assertFalse(check_user_in_team(snape, "gryffindor"))
        self.assertTrue(check_user_in_team(snape, "slytherin"))

        snape.update(teams=None)
        self.assertFalse(check_user_in_team(snape, "slytherin"))

    def test_backfill_user_data_from_posts(self) -> None:
        fixture_file_name = self.fixture_file_name("export.json", "mattermost_fixtures")
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        username_to_user = create_username_to_user_mapping(mattermost_data["user"])
        reset_mirror_dummy_users(username_to_user)

        backfill_user_data_from_posts(
            num_teams=2,
            team_name="gryffindor",
            mattermost_data=mattermost_data,
            username_to_user=username_to_user,
        )
        self.assertFalse(username_to_user["harry"]["is_mirror_dummy"])
        self.assertFalse(username_to_user["ron"]["is_mirror_dummy"])
        self.assertFalse(username_to_user["malfoy"]["is_mirror_dummy"])

        # snape is mirror dummy since the user sent a message in gryffindor and
        # left the team
        self.assertTrue(username_to_user["snape"]["is_mirror_dummy"])

    def test_build_reactions(self) -> None:
        fixture_file_name = self.fixture_file_name("export.json", "mattermost_fixtures")
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)

        total_reactions: list[dict[str, Any]] = []

        reactions = [
            {"user": "harry", "create_at": 1553165521410, "emoji_name": "tick"},
            {"user": "ron", "create_at": 1553166530805, "emoji_name": "smile"},
            {"user": "ron", "create_at": 1553166540953, "emoji_name": "world_map"},
            {"user": "harry", "create_at": 1553166540957, "emoji_name": "world_map"},
        ]

        with self.assertLogs(level="INFO"):
            zerver_realmemoji = write_emoticon_data(
                realm_id=3,
                custom_emoji_data=mattermost_data["emoji"],
                data_dir=self.fixture_file_name("", "mattermost_fixtures"),
                output_dir=self.make_import_output_dir("mattermost"),
            )

        # Make sure tick is present in fixture data
        self.assertEqual(zerver_realmemoji[1]["name"], "tick")
        tick_emoji_code = zerver_realmemoji[1]["id"]

        user_id_mapper = IdMapper[str]()
        harry_id = user_id_mapper.get("harry")
        ron_id = user_id_mapper.get("ron")

        build_reactions(
            realm_id=3,
            total_reactions=total_reactions,
            reactions=reactions,
            message_id=5,
            user_id_mapper=user_id_mapper,
            zerver_realmemoji=zerver_realmemoji,
        )

        smile_emoji_code = name_to_codepoint["smile"]
        world_map_emoji_code = name_to_codepoint["world_map"]

        self.assert_length(total_reactions, 4)
        self.assertEqual(
            self.get_set(total_reactions, "reaction_type"),
            {Reaction.REALM_EMOJI, Reaction.UNICODE_EMOJI},
        )
        self.assertEqual(
            self.get_set(total_reactions, "emoji_name"), {"tick", "smile", "world_map"}
        )
        self.assertEqual(
            self.get_set(total_reactions, "emoji_code"),
            {tick_emoji_code, smile_emoji_code, world_map_emoji_code},
        )
        self.assertEqual(self.get_set(total_reactions, "user_profile"), {harry_id, ron_id})
        self.assert_length(self.get_set(total_reactions, "id"), 4)
        self.assert_length(self.get_set(total_reactions, "message"), 1)

    def test_do_convert_data(self) -> None:
        mattermost_data_dir = self.fixture_file_name("", "mattermost_fixtures")
        output_dir = self.make_import_output_dir("mattermost")

        with self.assertLogs(level="WARNING") as warn_log:
            do_convert_data(
                mattermost_data_dir=mattermost_data_dir,
                output_dir=output_dir,
                masking_content=False,
            )
        self.assertEqual(
            warn_log.output,
            [
                "WARNING:root:Skipping importing direct message groups and DMs since there are multiple teams in the export",
                "WARNING:root:Skipping importing direct message groups and DMs since there are multiple teams in the export",
            ],
        )

        harry_team_output_dir = self.team_output_dir(output_dir, "gryffindor")
        self.assertEqual(os.path.exists(os.path.join(harry_team_output_dir, "avatars")), True)
        self.assertEqual(os.path.exists(os.path.join(harry_team_output_dir, "emoji")), True)
        self.assertEqual(
            os.path.exists(os.path.join(harry_team_output_dir, "attachment.json")), True
        )
        self.assertEqual(
            os.path.exists(os.path.join(harry_team_output_dir, "migration_status.json")), True
        )

        realm = self.read_file(harry_team_output_dir, "realm.json")

        self.assertEqual(
            "Organization imported from Mattermost!", realm["zerver_realm"][0]["description"]
        )

        exported_user_ids = self.get_set(realm["zerver_userprofile"], "id")
        exported_user_full_names = self.get_set(realm["zerver_userprofile"], "full_name")
        self.assertEqual({"Harry Potter", "Ron Weasley", "Severus Snape"}, exported_user_full_names)

        exported_user_emails = self.get_set(realm["zerver_userprofile"], "email")
        self.assertEqual(
            {"harry@zulip.com", "ron@zulip.com", "snape@zulip.com"}, exported_user_emails
        )

        self.assert_length(realm["zerver_stream"], 11)
        exported_stream_names = self.get_set(realm["zerver_stream"], "name")
        self.assertSetEqual(
            exported_stream_names,
            {
                "Gryffindor common room",
                "Gryffindor quidditch team",
                "Dumbledores army",
                "Super long channel name, it's more than 60 characters, whic…",  # codespell:ignore whic
                "Super long channel name, it's more than 60 characters, … (2)",
                "Super long channel name, it's more than 60 characters, … (3)",
                "Gryffindor quidditch team (2)",
                "Slug club",
                "SLUG CLUB (2)",
                "Slug club (3)",
                "slug club (3) (2)",
            },
        )
        self.assertEqual(
            self.get_set(realm["zerver_stream"], "realm"), {realm["zerver_realm"][0]["id"]}
        )
        self.assertEqual(self.get_set(realm["zerver_stream"], "deactivated"), {False})

        self.assert_length(realm["zerver_defaultstream"], 0)

        exported_recipient_ids = self.get_set(realm["zerver_recipient"], "id")
        self.assert_length(exported_recipient_ids, 11)
        exported_recipient_types = self.get_set(realm["zerver_recipient"], "type")
        self.assertEqual(exported_recipient_types, {Recipient.STREAM})
        exported_recipient_type_ids = self.get_set(realm["zerver_recipient"], "type_id")
        self.assert_length(exported_recipient_type_ids, 11)

        exported_subscription_userprofile = self.get_set(
            realm["zerver_subscription"], "user_profile"
        )
        self.assert_length(exported_subscription_userprofile, 2)
        exported_subscription_recipients = self.get_set(realm["zerver_subscription"], "recipient")
        self.assert_length(exported_subscription_recipients, 3)

        messages = self.read_file(harry_team_output_dir, "messages-000001.json")

        exported_messages_id = self.get_set(messages["zerver_message"], "id")
        self.assertIn(messages["zerver_message"][0]["sender"], exported_user_ids)
        self.assertIn(messages["zerver_message"][0]["recipient"], exported_recipient_ids)
        self.assertIn(messages["zerver_message"][0]["content"], "harry joined the channel.\n\n")

        exported_usermessage_userprofiles = self.get_set(
            messages["zerver_usermessage"], "user_profile"
        )
        self.assert_length(exported_usermessage_userprofiles, 3)
        exported_usermessage_messages = self.get_set(messages["zerver_usermessage"], "message")
        self.assertEqual(exported_usermessage_messages, exported_messages_id)

        with self.assertLogs(level="INFO"):
            do_import_realm(
                import_dir=harry_team_output_dir,
                subdomain="gryffindor",
            )

        realm = get_realm("gryffindor")

        presence_sequence = PresenceSequence.objects.get(realm=realm)
        self.assertEqual(presence_sequence.last_update_id, 0)

        self.assertFalse(get_user("harry@zulip.com", realm).is_mirror_dummy)
        self.assertFalse(get_user("ron@zulip.com", realm).is_mirror_dummy)
        self.assertTrue(get_user("snape@zulip.com", realm).is_mirror_dummy)

        messages = Message.objects.filter(realm=realm)
        for message in messages:
            self.assertIsNotNone(message.rendered_content)

        self.verify_emoji_code_foreign_keys()

    def test_do_convert_data_with_prefering_direct_messages_for_1_to_1_messages(self) -> None:
        mattermost_data_dir = self.fixture_file_name("direct_channel", "mattermost_fixtures")
        output_dir = self.make_import_output_dir("mattermost")

        with self.assertLogs(level="INFO"):
            do_convert_data(
                mattermost_data_dir=mattermost_data_dir,
                output_dir=output_dir,
                masking_content=False,
            )

        harry_team_output_dir = self.team_output_dir(output_dir, "gryffindor")
        realm = self.read_file(harry_team_output_dir, "realm.json")

        self.assertEqual(
            "Organization imported from Mattermost!", realm["zerver_realm"][0]["description"]
        )

        exported_user_ids = self.get_set(realm["zerver_userprofile"], "id")
        exported_user_full_names = self.get_set(realm["zerver_userprofile"], "full_name")
        self.assertEqual(
            {"Harry Potter", "Ron Weasley", "Ginny Weasley", "Tom Riddle"}, exported_user_full_names
        )

        exported_user_emails = self.get_set(realm["zerver_userprofile"], "email")
        self.assertEqual(
            {"harry@zulip.com", "ron@zulip.com", "ginny@zulip.com", "voldemort@zulip.com"},
            exported_user_emails,
        )

        self.assert_length(realm["zerver_stream"], 3)
        exported_stream_names = self.get_set(realm["zerver_stream"], "name")
        self.assertEqual(
            exported_stream_names,
            {"Gryffindor common room", "Gryffindor quidditch team", "Dumbledores army"},
        )
        self.assertEqual(
            self.get_set(realm["zerver_stream"], "realm"), {realm["zerver_realm"][0]["id"]}
        )
        self.assertEqual(self.get_set(realm["zerver_stream"], "deactivated"), {False})

        self.assert_length(realm["zerver_defaultstream"], 0)

        exported_recipient_ids = self.get_set(realm["zerver_recipient"], "id")
        self.assert_length(exported_recipient_ids, 6)
        exported_recipient_types = self.get_set(realm["zerver_recipient"], "type")
        self.assertEqual(
            exported_recipient_types,
            {Recipient.STREAM, Recipient.DIRECT_MESSAGE_GROUP},
        )
        exported_recipient_type_ids = self.get_set(realm["zerver_recipient"], "type_id")
        self.assert_length(exported_recipient_type_ids, 3)

        exported_subscription_userprofile = self.get_set(
            realm["zerver_subscription"], "user_profile"
        )
        self.assert_length(exported_subscription_userprofile, 4)
        exported_subscription_recipients = self.get_set(realm["zerver_subscription"], "recipient")
        self.assert_length(exported_subscription_recipients, 6)

        messages = self.read_file(harry_team_output_dir, "messages-000001.json")

        exported_messages_id = self.get_set(messages["zerver_message"], "id")
        self.assertIn(messages["zerver_message"][0]["sender"], exported_user_ids)
        self.assertIn(messages["zerver_message"][0]["recipient"], exported_recipient_ids)
        self.assertIn(messages["zerver_message"][0]["content"], "ron joined the channel.\n\n")

        exported_usermessage_userprofiles = self.get_set(
            messages["zerver_usermessage"], "user_profile"
        )
        self.assert_length(exported_usermessage_userprofiles, 3)
        exported_usermessage_messages = self.get_set(messages["zerver_usermessage"], "message")
        self.assertEqual(exported_usermessage_messages, exported_messages_id)

        with self.assertLogs(level="INFO"):
            do_import_realm(
                import_dir=harry_team_output_dir,
                subdomain="gryffindor",
            )

        realm = get_realm("gryffindor")

        messages = Message.objects.filter(realm=realm)
        for message in messages:
            self.assertIsNotNone(message.rendered_content)
        self.assert_length(messages, 24)

        stream_messages = messages.filter(recipient__type=Recipient.STREAM).order_by("date_sent")
        stream_recipients = stream_messages.values_list("recipient", flat=True)
        self.assert_length(stream_messages, 13)
        self.assert_length(set(stream_recipients), 2)

        group_direct_messages = messages.filter(
            recipient__type=Recipient.DIRECT_MESSAGE_GROUP
        ).order_by("date_sent")
        self.assert_length(group_direct_messages, 11)

        direct_message_group_recipients = group_direct_messages.values_list("recipient", flat=True)
        self.assert_length(set(direct_message_group_recipients), 7)

        self.assertEqual(group_direct_messages[0].sender.email, "ron@zulip.com")
        self.assertRegex(
            group_direct_messages[0].content, "hey harry\n\n\\[harry-ron.jpg\\]\\(.*\\)"
        )
        self.assertTrue(group_direct_messages[0].has_attachment)
        self.assertTrue(group_direct_messages[0].has_image)
        self.assertTrue(group_direct_messages[0].has_link)
        self.assertEqual(group_direct_messages[0].topic_name(), Message.DM_TOPIC)

        self.assertEqual(group_direct_messages[1].sender.email, "ginny@zulip.com")
        self.assertEqual(
            group_direct_messages[1].content, "Who is going to Hogsmeade this weekend?"
        )
        self.assertEqual(group_direct_messages[1].topic_name(), Message.DM_TOPIC)

    def test_do_convert_data_with_masking(self) -> None:
        mattermost_data_dir = self.fixture_file_name("", "mattermost_fixtures")
        output_dir = self.make_import_output_dir("mattermost")

        with self.assertLogs(level="WARNING") as warn_log:
            do_convert_data(
                mattermost_data_dir=mattermost_data_dir,
                output_dir=output_dir,
                masking_content=True,
            )

        self.assertEqual(
            warn_log.output,
            [
                "WARNING:root:Skipping importing direct message groups and DMs since there are multiple teams in the export",
                "WARNING:root:Skipping importing direct message groups and DMs since there are multiple teams in the export",
            ],
        )

        harry_team_output_dir = self.team_output_dir(output_dir, "gryffindor")
        messages = self.read_file(harry_team_output_dir, "messages-000001.json")

        self.assertIn(messages["zerver_message"][0]["content"], "xxxxx xxxxxx xxx xxxxxxx.\n\n")

    def test_import_data_to_existing_database(self) -> None:
        mattermost_data_dir = self.fixture_file_name("", "mattermost_fixtures")
        output_dir = self.make_import_output_dir("mattermost")

        with self.assertLogs(level="WARNING") as warn_log:
            do_convert_data(
                mattermost_data_dir=mattermost_data_dir,
                output_dir=output_dir,
                masking_content=True,
            )
        self.assertEqual(
            warn_log.output,
            [
                "WARNING:root:Skipping importing direct message groups and DMs since there are multiple teams in the export",
                "WARNING:root:Skipping importing direct message groups and DMs since there are multiple teams in the export",
            ],
        )

        harry_team_output_dir = self.team_output_dir(output_dir, "gryffindor")

        with self.assertLogs(level="INFO"):
            do_import_realm(
                import_dir=harry_team_output_dir,
                subdomain="gryffindor",
            )

        realm = get_realm("gryffindor")

        messages = Message.objects.filter(realm=realm)
        for message in messages:
            self.assertIsNotNone(message.rendered_content)

        self.verify_emoji_code_foreign_keys()

    def test_import_unknown_jsonl_file(self) -> None:
        export_dir = tempfile.mkdtemp()
        output_dir = self.make_import_output_dir("mattermost")
        try:
            with self.assertRaises(AssertionError) as e:
                do_convert_data(
                    mattermost_data_dir=export_dir,
                    output_dir=output_dir,
                    masking_content=True,
                )
            self.assertEqual(
                f"Missing import.jsonl or export.json file in {export_dir}. Files: []",
                str(e.exception),
            )
        finally:
            shutil.rmtree(export_dir)


@dataclass(frozen=True)
class MattermostExportedPost:
    post: dict[str, Any]
    # None for direct messages.
    channel_id: str | None
    # None for channel posts.
    direct_message_usernames: list[str] | None


class MattermostContractTestBase(MattermostImportTestBase, ImporterContractTestBase):
    """Translates a Mattermost export fixture into the importer-agnostic
    expectations checked by ImporterContractTestBase."""

    IMPORT_SOURCE = "mattermost"
    FIXTURE_DIR: str
    TEAM: str
    COMBINE_INTO_ONE_REALM = False

    OWNER_EMAILS: set[str]
    GUEST_EMAILS: set[str]

    mattermost_data: dict[str, Any]
    converted_team_output_dir: str

    @classmethod
    def get_fixture_dir_path(cls) -> str:
        return os.path.join(os.path.dirname(__file__), "fixtures", cls.FIXTURE_DIR)

    @classmethod
    @override
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.mattermost_data = mattermost_data_file_to_dict(
            os.path.join(cls.get_fixture_dir_path(), "import.jsonl"), cls.COMBINE_INTO_ONE_REALM
        )
        # Bot user's team and channel data is added here.
        backfill_user_data_from_posts(
            len(cls.mattermost_data["team"]),
            cls.TEAM,
            cls.mattermost_data,
            create_username_to_user_mapping(cls.mattermost_data["user"]),
        )

    @classmethod
    @override
    def convert_export(cls) -> str:
        output_dir = cls.make_converted_output_dir()
        with override_settings(EXTERNAL_HOST="zulip.example.com"):
            do_convert_data(
                mattermost_data_dir=cls.get_fixture_dir_path(),
                output_dir=output_dir,
                masking_content=False,
                combine_into_one_realm=cls.COMBINE_INTO_ONE_REALM,
            )
        cls.converted_team_output_dir = os.path.join(output_dir, cls.TEAM)
        return cls.converted_team_output_dir

    def get_team_membership(self, user: dict[str, Any]) -> dict[str, Any] | None:
        return next((team for team in user["teams"] or [] if team["name"] == self.TEAM), None)

    def get_converted_users(self) -> list[dict[str, Any]]:
        # Users outside the team, including bots that never posted in
        # it, are only converted as mirror dummies for their messages.
        return [
            user
            for user in self.mattermost_data["user"]
            if self.get_team_membership(user) is not None or user.get("is_mirror_dummy")
        ]

    def get_team_channels(self) -> list[dict[str, Any]]:
        return [
            channel for channel in self.mattermost_data["channel"] if channel["team"] == self.TEAM
        ]

    def get_expected_full_name(self, user: dict[str, Any]) -> str:
        full_name = "{} {}".format(user["first_name"], user["last_name"])
        if full_name.strip():
            return full_name
        # Bots only have display_name.
        return user.get("display_name") or user["username"]

    def get_expected_email(self, user: dict[str, Any]) -> str:
        if user.get("is_bot"):
            return f"{user['username']}-bot@zulip.example.com"
        return user["email"]

    def get_expected_channel_names(self) -> dict[str, str]:
        """Maps each Mattermost channel ID to its expected Zulip channel name."""
        channel_names: dict[str, str] = {}
        name_counts: Counter[str] = Counter()
        for channel in self.get_team_channels():
            name = channel["display_name"]
            # Channel names that only differ in capitalization collide,
            # and get a numeric suffix.
            name_counts[name.lower()] += 1
            if name_counts[name.lower()] > 1:
                name = f"{name} ({name_counts[name.lower()]})"
            channel_names[channel["name"]] = name
        return channel_names

    def get_exported_posts(self) -> list[MattermostExportedPost]:
        """Returns every exported post and reply that should be imported."""
        posts: list[MattermostExportedPost] = []
        for post in self.mattermost_data["post"]["channel_post"]:
            if post["team"] != self.TEAM:
                continue
            # Replies are in the same channel as the post they reply to.
            thread = [post, *(post["replies"] or [])]
            posts.extend(
                MattermostExportedPost(
                    post=thread_post,
                    channel_id=post["channel"],
                    direct_message_usernames=None,
                )
                for thread_post in thread
            )

        # Direct messages aren't tied to a team, so they're only
        # imported from single-team exports.
        if len(self.mattermost_data["team"]) == 1:
            for post in self.mattermost_data["post"]["direct_post"]:
                thread = [post, *(post["replies"] or [])]
                posts.extend(
                    MattermostExportedPost(
                        post=thread_post,
                        channel_id=None,
                        direct_message_usernames=post["channel_members"],
                    )
                    for thread_post in thread
                )
        return posts

    @override
    def get_expected_users(self) -> list[ExpectedUser]:
        expected_users = []
        for user in self.get_converted_users():
            email = self.get_expected_email(user)
            if email in self.OWNER_EMAILS:
                role = UserProfile.ROLE_REALM_OWNER
            elif email in self.GUEST_EMAILS:
                role = UserProfile.ROLE_GUEST
            else:
                role = UserProfile.ROLE_MEMBER
            is_mirror_dummy = bool(user.get("is_mirror_dummy"))
            is_bot = bool(user.get("is_bot"))
            expected_users.append(
                ExpectedUser(
                    email=email,
                    full_name=self.get_expected_full_name(user),
                    role=role,
                    is_bot=is_bot,
                    bot_type=UserProfile.DEFAULT_BOT if is_bot else None,
                    is_active=not is_mirror_dummy,
                    is_mirror_dummy=is_mirror_dummy,
                )
            )
        return expected_users

    @override
    def get_expected_channels(self) -> list[ExpectedChannel]:
        channel_subscriber_emails: dict[str, set[str]] = defaultdict(set)
        for user in self.mattermost_data["user"]:
            team_membership = self.get_team_membership(user)
            if team_membership is None:
                continue
            for channel in team_membership["channels"]:
                channel_subscriber_emails[channel["name"]].add(self.get_expected_email(user))

        channel_names = self.get_expected_channel_names()
        return [
            ExpectedChannel(
                name=channel_names[channel["name"]],
                description=channel["purpose"] or channel["header"],
                invite_only=channel["type"] == "P",
                # Mattermost exports don't include archived channels.
                deactivated=False,
                subscriber_emails=frozenset(channel_subscriber_emails[channel["name"]]),
            )
            for channel in self.get_team_channels()
        ]

    @override
    def get_expected_messages(self) -> list[ExpectedMessage]:
        username_to_email = {
            user["username"]: self.get_expected_email(user) for user in self.get_converted_users()
        }
        channel_names = self.get_expected_channel_names()

        expected_messages = []
        for exported_post in self.get_exported_posts():
            if exported_post.channel_id is not None:
                channel_name: str | None = channel_names[exported_post.channel_id]
                topic_name: str | None = "imported from mattermost"
                direct_message_participant_emails = None
            else:
                assert exported_post.direct_message_usernames is not None
                channel_name = None
                topic_name = None
                direct_message_participant_emails = frozenset(
                    username_to_email[username]
                    for username in exported_post.direct_message_usernames
                )

            expected_messages.append(
                ExpectedMessage(
                    sender_email=username_to_email[exported_post.post["user"]],
                    date_sent=exported_post.post["create_at"] // 1000,
                    channel_name=channel_name,
                    topic_name=topic_name,
                    direct_message_participant_emails=direct_message_participant_emails,
                )
            )
        return expected_messages

    @override
    def get_expected_attachment_file_names(self) -> list[str]:
        data_dir = os.path.join(self.get_fixture_dir_path(), "data")

        expected_file_names = []
        for exported_post in self.get_exported_posts():
            attachments = exported_post.post.get("attachments") or []
            for attachment in attachments:
                file_path = os.path.join(data_dir, attachment["path"])
                # The converter skips attachments whose file is missing
                # from the export.
                if not os.path.isfile(file_path):
                    continue
                expected_file_names.append(os.path.basename(attachment["path"]))
        return expected_file_names

    def test_attachment_messages_have_links(self) -> None:
        # Mattermost attachments are converted to links, rather than
        # inline images, so has_link should be set.
        imported_attachments = Attachment.objects.filter(realm=self.imported_realm)
        self.assertTrue(imported_attachments.exists())
        for attachment in imported_attachments:
            for message in Message.objects.filter(realm=self.imported_realm, attachment=attachment):
                self.assertTrue(message.has_link)

    def test_converted_messages_only_flag_exported_attachments(self) -> None:
        # do_import_realm recomputes has_attachment, so this checks
        # the converter's output directly.
        team_output_dir = self.converted_team_output_dir
        attachment_records = self.read_file(team_output_dir, "attachment.json")
        attachment_message_ids = {
            message_id
            for attachment in attachment_records["zerver_attachment"]
            for message_id in attachment["messages"]
        }
        converted_messages = []
        for messages_file in glob.glob(os.path.join(team_output_dir, "messages-*.json")):
            message_records = self.read_file(team_output_dir, os.path.basename(messages_file))
            converted_messages.extend(message_records["zerver_message"])
        # Posts whose attachment files are all missing from the export
        # aren't flagged.
        self.assertSetEqual(
            {message["id"] for message in converted_messages if message["has_attachment"]},
            attachment_message_ids,
        )
        self.assertSetEqual(
            {message["id"] for message in converted_messages if message["has_link"]},
            attachment_message_ids,
        )


class MattermostV1110ImportTest(MattermostContractTestBase):
    FIXTURE_DIR = "mattermost_v11.1.0_fixtures/raw_mmctl_output"
    TEAM = "ad-1"

    OWNER_EMAILS = {"sysadmin@sample.mattermost.com"}
    GUEST_EMAILS = {"guest@sample.mattermost.com"}

    def test_mattermost_data_file_to_dict(self) -> None:
        fixture_file = self.fixture_file_name("import.jsonl", self.FIXTURE_DIR)
        mattermost_data = mattermost_data_file_to_dict(fixture_file)

        self.assert_length(mattermost_data, 8)
        self.assert_length(mattermost_data["team"], 1)
        self.assertEqual(mattermost_data["team"][0]["name"], "ad-1")
        self.assert_length(mattermost_data["channel"], 5)
        self.assert_length(mattermost_data["user"], 20)
        self.assert_length(mattermost_data["emoji"], 1)
        self.assert_length(mattermost_data["post"]["channel_post"], 51)
        self.assert_length(mattermost_data["post"]["direct_post"], 50)
        self.assert_length(mattermost_data["direct_channel"], 79)
        self.assert_length(mattermost_data["role"], 23)
        exported_bot_users = [user for user in mattermost_data["user"] if user.get("is_bot")]
        self.assert_length(exported_bot_users, 3)

    def test_conversion_logs(self) -> None:
        # There's a post that references a missing attachment file, the importer
        # should continue processing the message but skip processing the missing
        # attachment file. Missing custom emoji files should also be treated the
        # same.
        self.assertListEqual(
            [
                "INFO:root:Generating data for ad-1",
                "INFO:root:Starting to process emoticons",
                "INFO:root:Emoji file no found: 'data/bogus/emoji.png'; continuing.",
                "INFO:root:Done processing emoticons",
                "INFO:root:Message attachment file not found: '20260123/bogus/path/to/file.txt'; continuing.",
                "INFO:root:Processed messages up to 63 / 63",
                "INFO:root:Processed messages up to 60 / 60",
                "INFO:root:Exporting migration status",
            ],
            self.conversion_log_output,
        )


class MattermostCombinedTeamsImportTest(MattermostContractTestBase):
    # With combine_into_one_realm=True, the export's multiple Mattermost
    # teams are all converted into this single Zulip realm.
    FIXTURE_DIR = "mattermost_v11.6.0_fixtures/raw_mmctl_output"
    TEAM = "zulip-1"
    COMBINE_INTO_ONE_REALM = True

    OWNER_EMAILS = {
        "user-4@sample.mattermost.com",
        "user-8@sample.mattermost.com",
        "user-7@sample.mattermost.com",
        "sysadmin@sample.mattermost.com",
        "adminuser123@gmail.com",
        "user-10@sample.mattermost.com",
        "user-9@sample.mattermost.com",
    }
    # The user "bobby.watson" is a team guest in reiciendis-0, they will be converted
    # into a normal Zulip user since they're a normal user in at least one other team.
    GUEST_EMAILS = {"guest@sample.mattermost.com"}

    def test_mattermost_data_file_to_dict(self) -> None:
        fixture_file = self.fixture_file_name("import.jsonl", self.FIXTURE_DIR)
        mattermost_data = mattermost_data_file_to_dict(fixture_file, combine_into_one_realm=True)
        exported_bot_users = [user for user in mattermost_data["user"] if user.get("is_bot")]
        self.assert_length(mattermost_data, 8)
        self.assert_length(mattermost_data["team"], 1)
        self.assertDictEqual(mattermost_data["team"][0], DEFAULT_SINGLE_TEAM_OBJECT)
        self.assert_length(mattermost_data["channel"], 26)
        self.assert_length(mattermost_data["user"], 19)
        self.assert_length(mattermost_data["emoji"], 0)
        self.assert_length(mattermost_data["post"]["channel_post"], 105)
        self.assertEqual(
            mattermost_data["post"]["channel_post"][0]["team"], DEFAULT_SINGLE_TEAM_OBJECT["name"]
        )
        self.assertEqual(
            mattermost_data["post"]["channel_post"][0]["channel"],
            COMPILED_CHANNEL_ID_FORMAT.format(id="off-topic", team="ad-1"),
        )
        self.assert_length(mattermost_data["post"]["direct_post"], 97)
        self.assert_length(mattermost_data["direct_channel"], 79)
        self.assert_length(mattermost_data["role"], 25)
        exported_bot_users = [user for user in mattermost_data["user"] if user.get("is_bot")]
        self.assert_length(exported_bot_users, 4)

    def test_combining_user_not_in_any_team(self) -> None:
        # Mattermost exports "teams": null for users who are not a
        # member of any team. Verify such users are passed through
        # unchanged when combining teams, so that they are imported
        # only as mirror dummies backfilled from their posts, just
        # like in the non-combined code path.
        user_object = {"type": "user", "user": {"username": "teamless.user", "teams": None}}
        jsonl_line = json.dumps(user_object)

        with tempfile.TemporaryDirectory() as tmp_dir:
            import_jsonl_path = os.path.join(tmp_dir, "import.jsonl")
            with open(import_jsonl_path, "w") as f:
                f.write(jsonl_line + "\n")

            mattermost_data = mattermost_data_file_to_dict(
                import_jsonl_path, combine_into_one_realm=True
            )
        self.assert_length(mattermost_data["user"], 1)
        self.assertEqual(mattermost_data["user"][0], {"username": "teamless.user", "teams": None})

    def test_combining_unknown_object(self) -> None:
        unknown_object = {"type": "unknown", "unknown": {"team": "some-team", "foo": "bar"}}
        jsonl_line = json.dumps(unknown_object)

        with tempfile.TemporaryDirectory() as tmp_dir:
            import_jsonl_path = os.path.join(tmp_dir, "import.jsonl")
            with open(import_jsonl_path, "w") as f:
                f.write(jsonl_line + "\n")

            with self.assertRaises(AssertionError) as e:
                do_convert_data(
                    mattermost_data_dir=tmp_dir,
                    output_dir=make_export_output_dir(),
                    masking_content=False,
                    combine_into_one_realm=True,
                )
        self.assertEqual(
            str(e.exception),
            f"Found unexpected 'unknown' object while compiling into combined realm. {unknown_object}",
        )


# Abstract base classes; the subclasses above run these tests.
del ImporterContractTestBase
del MattermostContractTestBase
