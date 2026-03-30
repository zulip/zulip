import filecmp
import json
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import orjson
from django.db.models import Q
from django.test import override_settings
from django_stubs_ext import QuerySetAny

from zerver.data_import.import_util import SubscriberHandler, UploadRecordData, ZerverFieldsT
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
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.thumbnail import THUMBNAIL_ACCEPT_IMAGE_TYPES
from zerver.models import Attachment, Message, Reaction, Recipient, UserProfile
from zerver.models.presence import PresenceSequence
from zerver.models.realms import Realm, get_realm
from zerver.models.streams import Stream, get_stream
from zerver.models.users import get_user
from zerver.tests.test_import_export import make_export_output_dir
from zerver.tests.test_microsoft_teams_importer import get_channel_subscriber_emails
from zproject.computed_settings import CROSS_REALM_BOT_EMAILS


@dataclass
class MattermostUserMaps:
    username_to_email_map: dict[str, str]
    exported_channel_subscriber_dict: dict[str, set[str]]


class MattermostImportTestBase(ZulipTestCase):
    def team_output_dir(self, output_dir: str, team_name: str) -> str:
        return os.path.join(output_dir, team_name)

    def read_file(self, team_output_dir: str, output_file: str) -> Any:
        full_path = os.path.join(team_output_dir, output_file)
        with open(full_path, "rb") as f:
            return orjson.loads(f.read())

    def assert_imported_messages_match_exported(
        self,
        importable_messages: Sequence[dict[str, Any]],
        imported_messages: QuerySetAny[Message, Message],
        username_to_email_map: dict[str, str],
    ) -> None:
        exported_message_datetimes: list[float] = []
        exported_sender_messages_map: dict[str, list[float]] = defaultdict(list)

        for message in importable_messages:
            message_datesent = float(int(message["create_at"] / 1000))
            exported_message_datetimes.append(message_datesent)
            exported_sender_messages_map[username_to_email_map[message["user"]]].append(
                message_datesent
            )

        imported_message_datetimes: list[float] = []
        imported_sender_messages_map: dict[str, list[float]] = defaultdict(list)
        last_date_sent: float = float("-inf")

        for imported_message in imported_messages:
            message_date_sent = imported_message.date_sent.timestamp()

            # Imported messages are sorted chronologically.
            self.assertLessEqual(last_date_sent, message_date_sent)
            last_date_sent = message_date_sent

            # We have some unit tests that check the message content is converted
            # correctly: test_do_convert_data, test_do_convert_data_with_direct_messages
            # and test_do_convert_data_with_prefering_direct_messages_for_1_to_1_messages.
            self.assertIsNotNone(imported_message.content)
            self.assertIsNotNone(imported_message.rendered_content)

            imported_message_datetimes.append(message_date_sent)
            imported_sender_messages_map[imported_message.sender.email].append(message_date_sent)

        self.assertListEqual(
            sorted(imported_message_datetimes),
            sorted(exported_message_datetimes),
        )

        # Message sender is correct.
        for sender_email, users_exported_message_datetimes in exported_sender_messages_map.items():
            self.assertListEqual(
                sorted(users_exported_message_datetimes),
                sorted(imported_sender_messages_map[sender_email]),
            )

    def build_user_maps(
        self,
        team_name: str,
        mattermost_data: dict[str, Any],
    ) -> MattermostUserMaps:
        # Bot user's team and channel data is added here.
        backfill_user_data_from_posts(
            1,
            team_name,
            mattermost_data,
            create_username_to_user_mapping(mattermost_data["user"]),
        )
        username_to_email_map: dict[str, str] = {}
        exported_channel_subscriber_dict: dict[str, set[str]] = defaultdict(set)

        for user in mattermost_data["user"]:
            if user["teams"] == []:
                # Bots that don't send any messages won't be part of any team/channel
                # and won't get converted.
                continue
            if user.get("is_bot"):
                email = f"{user['username']}-bot@zulip.example.com"
            else:
                email = user["email"]
            username_to_email_map[user["username"]] = email
            for channel in user["teams"][0]["channels"]:
                exported_channel_subscriber_dict[channel["name"]].add(email)

        return MattermostUserMaps(
            username_to_email_map=username_to_email_map,
            exported_channel_subscriber_dict=exported_channel_subscriber_dict,
        )

    def run_convert_and_import(
        self,
        export_file_name: str,
        fixture_dir: str,
        team_name: str,
        subdomain: str,
        combine_into_one_realm: bool = False,
    ) -> tuple[dict[str, Any], Any]:
        fixture_file = self.fixture_file_name(export_file_name, fixture_dir)
        mattermost_data = mattermost_data_file_to_dict(fixture_file, combine_into_one_realm)

        mattermost_data_dir = self.fixture_file_name("", fixture_dir)
        output_dir = make_export_output_dir()

        with self.assertLogs(level="INFO"):
            do_convert_data(
                mattermost_data_dir=mattermost_data_dir,
                output_dir=output_dir,
                masking_content=False,
                combine_into_one_realm=combine_into_one_realm,
            )

        team_output_dir = self.team_output_dir(output_dir, team_name)

        with self.assertLogs(level="INFO"):
            do_import_realm(import_dir=team_output_dir, subdomain=subdomain)

        imported_realm = get_realm(subdomain)
        return mattermost_data, imported_realm

    def assert_user_conversion(
        self,
        mattermost_data: dict[str, Any],
        imported_realm: Any,
        expected_owner_emails: set[str],
        expected_guest_emails: set[str],
        expected_bot_user_emails: set[str],
        expected_number_of_imported_users: int,
    ) -> None:
        imported_user_profiles = UserProfile.objects.filter(realm=imported_realm)
        self.assert_length(imported_user_profiles, expected_number_of_imported_users)

        imported_users = imported_user_profiles.filter(is_bot=False, is_mirror_dummy=False)
        self.assert_length(
            imported_users, expected_number_of_imported_users - len(expected_bot_user_emails)
        )

        imported_realm_owners = imported_user_profiles.filter(
            is_bot=False, role=UserProfile.ROLE_REALM_OWNER, is_mirror_dummy=False
        )
        self.assertSetEqual(
            {owner.email for owner in imported_realm_owners},
            expected_owner_emails,
        )

        imported_realm_guests = imported_user_profiles.filter(
            is_bot=False, role=UserProfile.ROLE_GUEST, is_mirror_dummy=False
        )
        self.assertSetEqual(
            {guest.email for guest in imported_realm_guests},
            expected_guest_emails,
        )

        imported_bot_users = imported_user_profiles.filter(
            is_bot=True, bot_type=UserProfile.DEFAULT_BOT
        )

        self.assertSetEqual(
            {bot.email for bot in imported_bot_users},
            expected_bot_user_emails,
        )

    def assert_channel_conversion(
        self,
        mattermost_data: dict[str, Any],
        imported_realm: Realm,
        exported_channel_subscriber_dict: dict[str, set[str]],
    ) -> None:
        checked_channels: list[str] = []
        for channel_data in mattermost_data["channel"]:
            channel_name = channel_data["display_name"]
            if channel_name in checked_channels:
                # This can't handle realms with colliding channel names for now.
                # test_convert_channel_data has some tests on channel name collision.
                continue
            mattermost_channel_id = channel_data["name"]
            imported_channel = Stream.objects.get(realm=imported_realm, name=channel_name)

            self.assertEqual(imported_channel.description, channel_data["purpose"])
            self.assertEqual(imported_channel.invite_only, channel_data["type"] == "P")

            expected_subscribers = set(exported_channel_subscriber_dict[mattermost_channel_id])

            self.assertSetEqual(
                expected_subscribers,
                get_channel_subscriber_emails(imported_realm, imported_channel),
            )
            checked_channels.append(channel_name)

    def assert_channel_messages(
        self,
        mattermost_data: dict[str, Any],
        imported_realm: Any,
        mattermost_channel_id: str,
        channel_name: str,
        username_to_email_map: dict[str, str],
        expected_number_of_bot_messages: int,
    ) -> None:
        imported_channel = get_stream(channel_name, imported_realm)
        imported_channel_messages = (
            Message.objects.filter(
                Q(sender__is_bot=False) | Q(sender__bot_type=UserProfile.DEFAULT_BOT),
                recipient=imported_channel.recipient,
                realm=imported_realm,
            )
            .exclude(sender__email__in=CROSS_REALM_BOT_EMAILS)
            .order_by("id")
        )

        importable_messages: list[dict[str, Any]] = []
        # Get all exported channel messages that in theory we should be able to
        # convert and import. We can't import bot users and their messages just yet.
        for m in mattermost_data["post"]["channel_post"]:
            if m["channel"] != mattermost_channel_id:
                continue
            importable_messages.append(m)
            if m["replies"] is not None:
                importable_messages += m["replies"]

        self.assert_length(imported_channel_messages, len(importable_messages))
        self.assert_imported_messages_match_exported(
            importable_messages, imported_channel_messages, username_to_email_map
        )
        self.assert_length(
            imported_channel_messages.filter(sender__is_bot=True), expected_number_of_bot_messages
        )

    def assert_direct_messages(
        self,
        mattermost_data: dict[str, Any],
        imported_realm: Any,
        username_to_email_map: dict[str, str],
        expected_number_of_bot_messages: int,
    ) -> None:
        imported_dms = (
            Message.objects.filter(
                Q(sender__is_bot=False) | Q(sender__bot_type=UserProfile.DEFAULT_BOT),
                realm=imported_realm,
            )
            .exclude(
                Q(recipient__type=Recipient.STREAM) | Q(sender__email__in=CROSS_REALM_BOT_EMAILS)
            )
            .order_by("id")
        )

        importable_dms: list[dict[str, Any]] = []
        for m in mattermost_data["post"]["direct_post"]:
            # We don't convert deleted users yet. So 1-1 direct messages sent from importable
            # users to them also won't be converted.
            if len(set(m["channel_members"])) < 2:  # nocoverage
                continue
            importable_dms.append(m)
            if m["replies"] is not None:
                importable_dms += m["replies"]

        self.assert_length(imported_dms, len(importable_dms))
        self.assert_imported_messages_match_exported(
            importable_dms, imported_dms, username_to_email_map
        )
        self.assert_length(
            imported_dms.filter(sender__is_bot=True), expected_number_of_bot_messages
        )

    def assert_attachments(
        self,
        imported_realm: Any,
        expected_count: int,
    ) -> None:
        imported_attachments = Attachment.objects.filter(realm=imported_realm)
        self.assertTrue(imported_attachments.exists())
        self.assert_length(imported_attachments, expected_count)

        for attachment in imported_attachments:
            for message in Message.objects.filter(realm=imported_realm, attachment=attachment):
                self.assertTrue(message.has_attachment)
                self.assertEqual(
                    message.has_image, attachment.content_type in THUMBNAIL_ACCEPT_IMAGE_TYPES
                )
                self.assertTrue(message.has_link)
                assert isinstance(message.rendered_content, str)
                self.assertIn(
                    f"/user_uploads/{attachment.path_id}",
                    message.rendered_content,
                )


class MatterMostImporter(MattermostImportTestBase):
    def test_mattermost_data_file_to_dict(self) -> None:
        fixture_file_name = self.fixture_file_name("export.json", "mattermost_fixtures")
        mattermost_data = mattermost_data_file_to_dict(fixture_file_name)
        self.assert_length(mattermost_data, 8)

        self.assertEqual(mattermost_data["version"], [1])

        self.assert_length(mattermost_data["team"], 2)
        self.assertEqual(mattermost_data["team"][0]["name"], "gryffindor")

        self.assert_length(mattermost_data["channel"], 9)
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
        self.assert_length(zerver_stream, 7)

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

        self.assert_length(zerver_huddle, 1)
        direct_message_group_members = frozenset(mattermost_data["direct_channel"][1]["members"])

        self.assertTrue(direct_message_group_id_mapper.has(direct_message_group_members))
        self.assertEqual(
            subscriber_handler.get_users(
                direct_message_group_id=direct_message_group_id_mapper.get(
                    direct_message_group_members
                )
            ),
            {1, 2, 3},
        )
        self.assertEqual(
            mock_log.output,
            ["INFO:root:Duplicate direct message group found in the export data. Skipping."],
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_convert_direct_message_group_data_without_personal_recipient(self) -> None:
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
        self.assertTrue(filecmp.cmp(records_json[0]["path"], exported_emoji_path))

        self.assertEqual(records_json[1]["file_name"], "tick")
        self.assertEqual(records_json[1]["realm_id"], 3)
        exported_emoji_path = self.fixture_file_name(
            mattermost_data["emoji"][1]["image"], "mattermost_fixtures"
        )
        self.assertTrue(filecmp.cmp(records_json[1]["path"], exported_emoji_path))

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

        zerver_attachments: list[ZerverFieldsT] = []
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
        self.assertEqual(zerver_attachments[0]["file_name"], "harry-ron.jpg")
        self.assertEqual(zerver_attachments[0]["owner"], 2)
        self.assertEqual(
            user_handler.get_user(zerver_attachments[0]["owner"])["email"], "ron@zulip.com"
        )
        # TODO: Assert this for False after fixing the file permissions in direct messages
        self.assertTrue(zerver_attachments[0]["is_realm_public"])

        self.assert_length(uploads_list, 1)
        self.assertEqual(uploads_list[0].user_profile_id, 2)

        attachment_path = self.fixture_file_name(
            mattermost_data["post"]["direct_post"][0]["attachments"][0]["path"],
            "mattermost_fixtures/direct_channel/data",
        )
        attachment_out_path = os.path.join(output_dir, "uploads", zerver_attachments[0]["path_id"])
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
                *(
                    [
                        # Check error log when trying to process a message with faulty HTML.
                        "WARNING:root:Error converting HTML to text for message: 'This will crash html2text!!! <g:brand><![CDATSALOMON NORTH AMERICA, IN}}]]></g:brand>'; continuing",
                        "WARNING:root:{'sender_id': 2, 'content': 'This will crash html2text!!! <g:brand><![CDATSALOMON NORTH AMERICA, IN}}]]></g:brand>', 'date_sent': 1553166657, 'reactions': [], 'channel_name': 'dumbledores-army'}",
                    ]
                    if sys.version_info < (3, 13)
                    else []
                ),
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

        self.assert_length(realm["zerver_stream"], 7)
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
            },
        )
        self.assertEqual(
            self.get_set(realm["zerver_stream"], "realm"), {realm["zerver_realm"][0]["id"]}
        )
        self.assertEqual(self.get_set(realm["zerver_stream"], "deactivated"), {False})

        self.assert_length(realm["zerver_defaultstream"], 0)

        exported_recipient_ids = self.get_set(realm["zerver_recipient"], "id")
        self.assert_length(exported_recipient_ids, 10)
        exported_recipient_types = self.get_set(realm["zerver_recipient"], "type")
        self.assertEqual(exported_recipient_types, {1, 2})
        exported_recipient_type_ids = self.get_set(realm["zerver_recipient"], "type_id")
        self.assert_length(exported_recipient_type_ids, 7)

        exported_subscription_userprofile = self.get_set(
            realm["zerver_subscription"], "user_profile"
        )
        self.assert_length(exported_subscription_userprofile, 3)
        exported_subscription_recipients = self.get_set(realm["zerver_subscription"], "recipient")
        self.assert_length(exported_subscription_recipients, 6)

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

    def test_do_convert_data_with_direct_messages(self) -> None:
        mattermost_data_dir = self.fixture_file_name("direct_channel", "mattermost_fixtures")
        output_dir = self.make_import_output_dir("mattermost")

        with self.assertLogs(level="INFO"):
            do_convert_data(
                mattermost_data_dir=mattermost_data_dir,
                output_dir=output_dir,
                masking_content=False,
            )

        harry_team_output_dir = self.team_output_dir(output_dir, "gryffindor")
        self.assertEqual(os.path.exists(os.path.join(harry_team_output_dir, "avatars")), True)
        self.assertEqual(os.path.exists(os.path.join(harry_team_output_dir, "emoji")), True)
        self.assertEqual(os.path.exists(os.path.join(harry_team_output_dir, "uploads")), True)
        self.assertEqual(
            os.path.exists(os.path.join(harry_team_output_dir, "attachment.json")), True
        )

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
        self.assert_length(exported_recipient_ids, 8)
        exported_recipient_types = self.get_set(realm["zerver_recipient"], "type")
        self.assertEqual(exported_recipient_types, {1, 2, 3})
        exported_recipient_type_ids = self.get_set(realm["zerver_recipient"], "type_id")
        self.assert_length(exported_recipient_type_ids, 4)

        exported_subscription_userprofile = self.get_set(
            realm["zerver_subscription"], "user_profile"
        )
        self.assert_length(exported_subscription_userprofile, 4)
        exported_subscription_recipients = self.get_set(realm["zerver_subscription"], "recipient")
        self.assert_length(exported_subscription_recipients, 8)

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
        self.assertEqual(stream_messages[0].sender.email, "ron@zulip.com")
        self.assertEqual(stream_messages[0].content, "ron joined the channel.\n\n")

        self.assertEqual(stream_messages[3].sender.email, "harry@zulip.com")
        self.assertRegex(
            stream_messages[3].content,
            "Looks like this channel is empty\n\n\\[this is a file\\]\\(.*\\)",
        )
        self.assertTrue(stream_messages[3].has_attachment)
        self.assertFalse(stream_messages[3].has_image)
        self.assertTrue(stream_messages[3].has_link)

        group_direct_messages = messages.filter(
            recipient__type=Recipient.DIRECT_MESSAGE_GROUP
        ).order_by("date_sent")
        direct_message_group_recipients = group_direct_messages.values_list("recipient", flat=True)
        self.assert_length(group_direct_messages, 3)
        self.assert_length(set(direct_message_group_recipients), 1)
        self.assertEqual(group_direct_messages[0].sender.email, "ginny@zulip.com")
        self.assertEqual(
            group_direct_messages[0].content, "Who is going to Hogsmeade this weekend?\n\n"
        )
        self.assertEqual(group_direct_messages[0].topic_name(), Message.DM_TOPIC)

        personal_messages = messages.filter(recipient__type=Recipient.PERSONAL).order_by(
            "date_sent"
        )
        personal_recipients = personal_messages.values_list("recipient", flat=True)
        self.assert_length(personal_messages, 8)
        self.assert_length(set(personal_recipients), 4)
        self.assertEqual(personal_messages[0].sender.email, "ron@zulip.com")
        self.assertRegex(personal_messages[0].content, "hey harry\n\n\\[harry-ron.jpg\\]\\(.*\\)")
        self.assertTrue(personal_messages[0].has_attachment)
        self.assertTrue(personal_messages[0].has_image)
        self.assertTrue(personal_messages[0].has_link)
        self.assertEqual(personal_messages[0].topic_name(), Message.DM_TOPIC)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
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
        self.assert_length(exported_recipient_ids, 10)
        exported_recipient_types = self.get_set(realm["zerver_recipient"], "type")
        self.assertEqual(
            exported_recipient_types,
            {Recipient.PERSONAL, Recipient.STREAM, Recipient.DIRECT_MESSAGE_GROUP},
        )
        exported_recipient_type_ids = self.get_set(realm["zerver_recipient"], "type_id")
        self.assert_length(exported_recipient_type_ids, 4)

        exported_subscription_userprofile = self.get_set(
            realm["zerver_subscription"], "user_profile"
        )
        self.assert_length(exported_subscription_userprofile, 4)
        exported_subscription_recipients = self.get_set(realm["zerver_subscription"], "recipient")
        self.assert_length(exported_subscription_recipients, 10)

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
        self.assert_length(group_direct_messages, 7)

        direct_message_group_recipients = group_direct_messages.values_list("recipient", flat=True)
        self.assert_length(set(direct_message_group_recipients), 3)

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
            group_direct_messages[1].content, "Who is going to Hogsmeade this weekend?\n\n"
        )
        self.assertEqual(group_direct_messages[1].topic_name(), Message.DM_TOPIC)

        personal_messages = messages.filter(recipient__type=Recipient.PERSONAL).order_by(
            "date_sent"
        )
        self.assert_length(personal_messages, 4)

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
                *(
                    [
                        "WARNING:root:Error converting HTML to text for message: 'Xxxx xxxx xxxxx xxxx2xxxx!!! <x:xxxxx><![XXXXXXXXXXX XXXXX XXXXXXX, XX}}]]></x:xxxxx>'; continuing",
                        "WARNING:root:{'sender_id': 2, 'content': 'Xxxx xxxx xxxxx xxxx2xxxx!!! <x:xxxxx><![XXXXXXXXXXX XXXXX XXXXXXX, XX}}]]></x:xxxxx>', 'date_sent': 1553166657, 'reactions': [], 'channel_name': 'dumbledores-army'}",
                    ]
                    if sys.version_info < (3, 13)
                    else []
                ),
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
                *(
                    [
                        "WARNING:root:Error converting HTML to text for message: 'Xxxx xxxx xxxxx xxxx2xxxx!!! <x:xxxxx><![XXXXXXXXXXX XXXXX XXXXXXX, XX}}]]></x:xxxxx>'; continuing",
                        "WARNING:root:{'sender_id': 2, 'content': 'Xxxx xxxx xxxxx xxxx2xxxx!!! <x:xxxxx><![XXXXXXXXXXX XXXXX XXXXXXX, XX}}]]></x:xxxxx>', 'date_sent': 1553166657, 'reactions': [], 'channel_name': 'dumbledores-army'}",
                    ]
                    if sys.version_info < (3, 13)
                    else []
                ),
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


class MattermostV1110ImportTest(MattermostImportTestBase):
    FIXTURE_DIR = "mattermost_v11.1.0_fixtures/raw_mmctl_output"
    SUBDOMAIN = "test-realm"
    TEAM = "ad-1"

    OWNER_EMAILS = {"sysadmin@sample.mattermost.com"}
    GUEST_EMAILS = {"guest@sample.mattermost.com"}
    BOT_EMAILS = {"lori.carter-bot@zulip.example.com"}

    def test_mattermost_data_file_to_dict(self) -> None:
        fixture_file = self.fixture_file_name("import.jsonl", self.FIXTURE_DIR)
        mattermost_data = mattermost_data_file_to_dict(fixture_file)

        self.assert_length(mattermost_data, 8)
        self.assert_length(mattermost_data["team"], 1)
        self.assertEqual(mattermost_data["team"][0]["name"], "ad-1")
        self.assert_length(mattermost_data["channel"], 4)
        self.assert_length(mattermost_data["user"], 20)
        self.assert_length(mattermost_data["emoji"], 0)
        self.assert_length(mattermost_data["post"]["channel_post"], 50)
        self.assert_length(mattermost_data["post"]["direct_post"], 50)
        self.assert_length(mattermost_data["direct_channel"], 79)
        self.assert_length(mattermost_data["role"], 23)
        exported_bot_users = [user for user in mattermost_data["user"] if user.get("is_bot")]
        self.assert_length(exported_bot_users, 3)

    def test_e2e_export_data_v11_1_0(self) -> None:
        with self.settings(EXTERNAL_HOST="zulip.example.com"):
            mattermost_data, imported_realm = self.run_convert_and_import(
                export_file_name="import.jsonl",
                fixture_dir=self.FIXTURE_DIR,
                team_name=self.TEAM,
                subdomain="test-realm",
            )
        user_map_data = self.build_user_maps(self.TEAM, mattermost_data)

        with self.subTest("test user conversion"):
            self.assert_user_conversion(
                mattermost_data=mattermost_data,
                imported_realm=imported_realm,
                expected_owner_emails=self.OWNER_EMAILS,
                expected_guest_emails=self.GUEST_EMAILS,
                expected_bot_user_emails=self.BOT_EMAILS,
                # Out of the three bots, two (Jira bot and system-bot) never participated in
                # any channel, so they don't get converted.
                expected_number_of_imported_users=len(mattermost_data["user"]) - 2,
            )

        with self.subTest("test channel conversion"):
            self.assert_channel_conversion(
                mattermost_data=mattermost_data,
                imported_realm=imported_realm,
                exported_channel_subscriber_dict=user_map_data.exported_channel_subscriber_dict,
            )

        with self.subTest("test channel message conversion"):
            self.assert_channel_messages(
                mattermost_data,
                imported_realm,
                # "sequi-7" is the Mattermost channel ID of "nesciunt"
                mattermost_channel_id="sequi-7",
                channel_name="nesciunt",
                username_to_email_map=user_map_data.username_to_email_map,
                expected_number_of_bot_messages=2,
            )

        with self.subTest("test direct messages"):
            self.assert_direct_messages(
                mattermost_data=mattermost_data,
                imported_realm=imported_realm,
                username_to_email_map=user_map_data.username_to_email_map,
                expected_number_of_bot_messages=2,
            )

        with self.subTest("test attachments"):
            self.assert_attachments(imported_realm, expected_count=3)


class MattermostCombinedTeamsImportTest(MattermostImportTestBase):
    FIXTURE_DIR = "mattermost_v11.6.0_fixtures/raw_mmctl_output"
    SUBDOMAIN = "test-realm"
    TEAM = "zulip-1"

    OWNER_EMAILS = {
        "user-4@sample.mattermost.com",
        "user-8@sample.mattermost.com",
        "user-7@sample.mattermost.com",
        "sysadmin@sample.mattermost.com",
        "adminuser123@gmail.com",
        "user-10@sample.mattermost.com",
        "user-9@sample.mattermost.com",
    }
    GUEST_EMAILS = {"guest@sample.mattermost.com"}
    BOT_EMAILS = {
        "system-bot-bot@zulip.example.com",
        "keith.ryan-bot@zulip.example.com",
        "robert.ward-bot@zulip.example.com",
        "lori.carter-bot@zulip.example.com",
    }

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
        self.assert_length(exported_bot_users, len(self.BOT_EMAILS))

    def test_e2e_export_data_v11_6_0(self) -> None:
        # The assert functions here iterate over the exported Mattermost objects and checks
        # whether a corresponding Zulip object exists in the imported realm. So, If
        # combined_into_one_realm=True and the export fixture contains multiple teams, it
        # should check that all rows from different Mattermost teams exist inside a single
        # Zulip realm.

        with self.settings(EXTERNAL_HOST="zulip.example.com"):
            mattermost_data, imported_realm = self.run_convert_and_import(
                export_file_name="import.jsonl",
                fixture_dir=self.FIXTURE_DIR,
                team_name=self.TEAM,
                subdomain="test-realm",
                combine_into_one_realm=True,
            )
        user_map_data = self.build_user_maps(self.TEAM, mattermost_data)

        with self.subTest("test user conversion"):
            self.assert_user_conversion(
                mattermost_data=mattermost_data,
                imported_realm=imported_realm,
                expected_owner_emails=self.OWNER_EMAILS,
                # The user "bobby.watson" is a team guest in ad-1, they will be converted into
                # a normal Zulip user since they're a normal user in at least one other team.
                expected_guest_emails=self.GUEST_EMAILS,
                expected_bot_user_emails=self.BOT_EMAILS,
                expected_number_of_imported_users=len(mattermost_data["user"]),
            )

        with self.subTest("test channel conversion"):
            self.assert_channel_conversion(
                mattermost_data=mattermost_data,
                imported_realm=imported_realm,
                exported_channel_subscriber_dict=user_map_data.exported_channel_subscriber_dict,
            )

        with self.subTest("test channel message conversion"):
            mattermost_channels = [
                (
                    COMPILED_CHANNEL_ID_FORMAT.format(id="voluptas-9", team="reiciendis-0"),
                    "voluptatem",
                    3,
                ),
                (COMPILED_CHANNEL_ID_FORMAT.format(id="minima-3", team="ad-1"), "veritatis", 0),
            ]
            for mattermost_channel_id, channel_name, number_of_bot_messages in mattermost_channels:
                self.assert_channel_messages(
                    mattermost_data,
                    imported_realm,
                    mattermost_channel_id=mattermost_channel_id,
                    channel_name=channel_name,
                    username_to_email_map=user_map_data.username_to_email_map,
                    expected_number_of_bot_messages=number_of_bot_messages,
                )

        with self.subTest("test direct messages"):
            self.assert_direct_messages(
                mattermost_data=mattermost_data,
                imported_realm=imported_realm,
                username_to_email_map=user_map_data.username_to_email_map,
                expected_number_of_bot_messages=24,
            )

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
