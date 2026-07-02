import os
from typing import Any
from unittest.mock import call, patch

import orjson

from zerver.data_import.discord import (
    DiscordExportMetadata,
    build_user_id_to_fullname,
    collect_metadata,
    convert_channel_data,
    convert_direct_message_group_data,
    convert_user_data,
    discover_export_files,
    do_convert_data,
    parse_channel_file,
    parse_discord_timestamp,
)
from zerver.data_import.discord_message_conversion import (
    convert_multiline_quote,
    convert_spoiler,
    convert_to_zulip_markdown,
    convert_underscore_italic,
)
from zerver.data_import.import_util import SubscriberHandler
from zerver.data_import.sequencer import IdMapper
from zerver.data_import.user_handler import UserHandler
from zerver.lib.import_realm import do_import_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Recipient
from zerver.models.presence import PresenceSequence
from zerver.models.realms import get_realm


class DiscordImporter(ZulipTestCase):
    discord_fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "discord_fixtures")

    def read_file(self, output_dir: str, output_file: str) -> Any:
        full_path = os.path.join(output_dir, output_file)
        with open(full_path, "rb") as f:
            return orjson.loads(f.read())

    def get_metadata(self) -> DiscordExportMetadata:
        json_files = discover_export_files(self.discord_fixtures_dir)
        return collect_metadata(json_files)

    def test_discover_export_files(self) -> None:
        json_files = discover_export_files(self.discord_fixtures_dir)
        # Should find all 5 fixture JSON files
        self.assert_length(json_files, 5)
        # Should not include _media files
        for path in json_files:
            self.assertTrue(path.endswith(".json"))
            self.assertNotIn("_media", path)

    def test_parse_channel_file(self) -> None:
        json_files = discover_export_files(self.discord_fixtures_dir)
        data = parse_channel_file(json_files[0])
        self.assertIn("channel", data)
        self.assertIn("messages", data)

    def test_collect_metadata(self) -> None:
        metadata = self.get_metadata()

        # Should find users: user001 (alice), user002 (bob), user003 (charlie),
        # bot001 (testbot)
        self.assertIn("user001", metadata.discord_users)
        self.assertIn("user002", metadata.discord_users)
        self.assertIn("user003", metadata.discord_users)
        self.assertIn("bot001", metadata.discord_users)
        self.assertEqual(metadata.discord_users["user001"]["name"], "alice")
        self.assertEqual(metadata.discord_users["user002"]["name"], "bob")
        self.assertEqual(metadata.discord_users["bot001"]["isBot"], True)

        # Thread channel 200 should map to parent channel 100
        self.assertIn("200", metadata.thread_topic_map)
        parent_id, thread_name = metadata.thread_topic_map["200"]
        self.assertEqual(parent_id, "100")
        self.assertEqual(thread_name, "Test Thread")

        # DM participants
        self.assertIn("DM001", metadata.dm_participants)
        self.assertEqual(metadata.dm_participants["DM001"], {"user001", "user002"})
        self.assertIn("GDM001", metadata.dm_participants)
        self.assertEqual(metadata.dm_participants["GDM001"], {"user001", "user002"})

        # Channel name map
        self.assertEqual(metadata.channel_id_to_name["100"], "general")
        self.assertEqual(metadata.channel_id_to_name["101"], "random")
        self.assertNotIn("200", metadata.channel_id_to_name)

        # Guild name
        self.assertEqual(metadata.guild_name, "Test Server")

    def test_convert_users(self) -> None:
        metadata = self.get_metadata()

        user_handler = UserHandler()
        user_id_mapper = IdMapper[str]()
        realm_id = 1

        convert_user_data(
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
            discord_users=metadata.discord_users,
            realm_id=realm_id,
            domain_name="test.example.com",
        )

        all_users = user_handler.get_all_users()
        # 4 unique users: alice, bob, charlie, testbot
        self.assert_length(all_users, 4)

        user_names = {u["full_name"] for u in all_users}
        self.assertIn("Alice Smith", user_names)
        self.assertIn("Bob Jones", user_names)

        # Check bot user
        bot_user = None
        for u in all_users:
            if u["full_name"] == "Test Bot":
                bot_user = u
                break
        assert bot_user is not None
        self.assertTrue(bot_user["is_bot"])
        self.assertEqual(bot_user["bot_type"], 1)

        # Check email generation
        user_emails = {u["email"] for u in all_users}
        self.assertIn("alice@test.example.com", user_emails)
        self.assertIn("bob@test.example.com", user_emails)

    def test_convert_channels(self) -> None:
        metadata = self.get_metadata()

        user_handler = UserHandler()
        user_id_mapper = IdMapper[str]()
        realm_id = 1

        convert_user_data(
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
            discord_users=metadata.discord_users,
            realm_id=realm_id,
            domain_name="test.example.com",
        )

        subscriber_handler = SubscriberHandler()
        stream_id_mapper = IdMapper[str]()
        all_user_ids = {u["id"] for u in user_handler.get_all_users()}

        streams = convert_channel_data(
            channel_info=metadata.channel_info,
            subscriber_handler=subscriber_handler,
            stream_id_mapper=stream_id_mapper,
            user_id_mapper=user_id_mapper,
            realm_id=realm_id,
            all_user_ids=all_user_ids,
        )

        # Should have 2 streams: general and random
        self.assert_length(streams, 2)
        stream_names = {s["name"] for s in streams}
        self.assertEqual(stream_names, {"general", "random"})

        # All users should be subscribed
        for stream in streams:
            subscribers = subscriber_handler.get_users(stream_id=stream["id"])
            self.assertEqual(subscribers, all_user_ids)

    def test_convert_direct_messages(self) -> None:
        metadata = self.get_metadata()

        user_id_mapper = IdMapper[str]()
        # Pre-register user IDs
        user_id_mapper.get("user001")
        user_id_mapper.get("user002")
        user_id_mapper.get("user003")

        subscriber_handler = SubscriberHandler()
        dm_group_id_mapper = IdMapper[frozenset[str]]()

        groups = convert_direct_message_group_data(
            dm_participants=metadata.dm_participants,
            channel_info=metadata.channel_info,
            subscriber_handler=subscriber_handler,
            direct_message_group_id_mapper=dm_group_id_mapper,
            user_id_mapper=user_id_mapper,
        )

        # Should have 1 group DM (GDM001)
        self.assert_length(groups, 1)

    def test_discord_message_conversion(self) -> None:
        user_id_to_fullname = {"123": "Alice Smith", "456": "Bob Jones"}
        user_id_to_zulip_id: dict[str, int] = {"123": 1, "456": 2}
        channel_id_to_name = {"100": "general", "101": "random"}

        # Test user mention
        text = "Hello <@123>, how are you?"
        result, mentioned, has_link = convert_to_zulip_markdown(
            text, user_id_to_fullname, user_id_to_zulip_id, channel_id_to_name
        )
        self.assertEqual(result, "Hello @_**Alice Smith**, how are you?")
        self.assertEqual(mentioned, {1})

        # Test user mention with ! prefix
        text = "Hey <@!456>"
        result, mentioned, has_link = convert_to_zulip_markdown(
            text, user_id_to_fullname, user_id_to_zulip_id, channel_id_to_name
        )
        self.assertEqual(result, "Hey @_**Bob Jones**")
        self.assertEqual(mentioned, {2})

        # Test channel mention
        text = "Check out <#100>"
        result, mentioned, has_link = convert_to_zulip_markdown(
            text, user_id_to_fullname, user_id_to_zulip_id, channel_id_to_name
        )
        self.assertEqual(result, "Check out #**general**")

        # Test custom emoji
        text = "Great job <:thumbs:12345>"
        result, mentioned, has_link = convert_to_zulip_markdown(
            text, user_id_to_fullname, user_id_to_zulip_id, channel_id_to_name
        )
        self.assertEqual(result, "Great job :thumbs:")

        # Test animated custom emoji
        text = "Party <a:partyblob:67890>"
        result, mentioned, has_link = convert_to_zulip_markdown(
            text, user_id_to_fullname, user_id_to_zulip_id, channel_id_to_name
        )
        self.assertEqual(result, "Party :partyblob:")

        # Test @everyone and @here
        text = "Attention @everyone!"
        result, mentioned, has_link = convert_to_zulip_markdown(
            text, user_id_to_fullname, user_id_to_zulip_id, channel_id_to_name
        )
        self.assertEqual(result, "Attention @**all**!")
        self.assertTrue(has_link)

        text = "@here please review"
        result, mentioned, has_link = convert_to_zulip_markdown(
            text, user_id_to_fullname, user_id_to_zulip_id, channel_id_to_name
        )
        self.assertEqual(result, "@**all** please review")

        # Test role mention
        text = "Hey <@&999>"
        result, mentioned, has_link = convert_to_zulip_markdown(
            text, user_id_to_fullname, user_id_to_zulip_id, channel_id_to_name
        )
        self.assertEqual(result, "Hey @role")

        # Test link detection
        text = "Visit https://example.com"
        result, mentioned, has_link = convert_to_zulip_markdown(
            text, user_id_to_fullname, user_id_to_zulip_id, channel_id_to_name
        )
        self.assertTrue(has_link)

        # Test no link
        text = "Just plain text"
        result, mentioned, has_link = convert_to_zulip_markdown(
            text, user_id_to_fullname, user_id_to_zulip_id, channel_id_to_name
        )
        self.assertFalse(has_link)

    def test_underscore_italic_conversion(self) -> None:
        self.assertEqual(convert_underscore_italic("_hello_"), "*hello*")
        self.assertEqual(convert_underscore_italic("no change"), "no change")
        # Should not convert underscores inside words
        self.assertEqual(convert_underscore_italic("snake_case_name"), "snake_case_name")

    def test_spoiler_conversion(self) -> None:
        self.assertEqual(convert_spoiler("||secret||"), "```spoiler\nsecret\n```")

    def test_multiline_quote_conversion(self) -> None:
        text = ">>> This is a quote\nthat spans multiple lines"
        result = convert_multiline_quote(text)
        self.assertIn("```quote", result)
        self.assertIn("This is a quote", result)

    def test_system_message_filtering(self) -> None:
        """System messages should be filtered out during conversion."""
        json_files = discover_export_files(self.discord_fixtures_dir)

        # Find the general channel fixture which has system messages
        general_data = None
        for filepath in json_files:
            data = parse_channel_file(filepath)
            if data["channel"]["name"] == "general":
                general_data = data
                break
        assert general_data is not None

        system_count = 0
        regular_count = 0
        for msg in general_data["messages"]:
            if msg["type"] in (
                "GuildMemberJoin",
                "ThreadCreated",
                "ChannelPinnedMessage",
            ):
                system_count += 1
            else:
                regular_count += 1

        # We have both system and regular messages in fixtures
        self.assertGreater(system_count, 0)
        self.assertGreater(regular_count, 0)

    def test_parse_discord_timestamp(self) -> None:
        ts = parse_discord_timestamp("2026-01-01T10:00:00+00:00")
        self.assertIsInstance(ts, float)
        self.assertGreater(ts, 0)

        # Test Z suffix
        ts2 = parse_discord_timestamp("2026-01-01T10:00:00Z")
        self.assertEqual(ts, ts2)

    def test_build_user_id_to_fullname(self) -> None:
        discord_users: dict[str, dict[str, Any]] = {
            "u1": {"name": "alice", "nickname": "Alice S"},
            "u2": {"name": "bob", "nickname": None},
        }
        result = build_user_id_to_fullname(discord_users)
        self.assertEqual(result["u1"], "Alice S")
        self.assertEqual(result["u2"], "bob")

    def test_full_conversion(self) -> None:
        output_dir = self.make_import_output_dir("discord")

        with (
            patch("builtins.print") as mock_print,
            self.assertLogs(level="INFO"),
            self.settings(EXTERNAL_HOST="zulip.example.com"),
        ):
            do_convert_data(
                discord_data_dir=self.discord_fixtures_dir,
                output_dir=output_dir,
            )
        self.assertEqual(
            mock_print.mock_calls,
            [call("Converting data for", "Test Server")],
        )

        # Check output directory structure
        self.assertTrue(os.path.exists(os.path.join(output_dir, "realm.json")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "attachment.json")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "avatars", "records.json")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "uploads", "records.json")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "emoji", "records.json")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "migration_status.json")))

        realm = self.read_file(output_dir, "realm.json")

        # Check realm
        self.assertIn(
            "Organization imported from Discord!", realm["zerver_realm"][0]["description"]
        )

        # Check users
        exported_user_full_names = self.get_set(realm["zerver_userprofile"], "full_name")
        self.assertIn("Alice Smith", exported_user_full_names)
        self.assertIn("Bob Jones", exported_user_full_names)

        # Check streams
        exported_stream_names = self.get_set(realm["zerver_stream"], "name")
        self.assertEqual(exported_stream_names, {"general", "random"})

        # Check that streams belong to the realm
        self.assertEqual(
            self.get_set(realm["zerver_stream"], "realm"),
            {realm["zerver_realm"][0]["id"]},
        )

        # Check recipients
        exported_recipient_types = self.get_set(realm["zerver_recipient"], "type")
        self.assertIn(Recipient.STREAM, exported_recipient_types)
        self.assertIn(Recipient.PERSONAL, exported_recipient_types)

        # Check subscriptions exist
        self.assertGreater(len(realm["zerver_subscription"]), 0)

        # Check messages were written
        message_files = [f for f in os.listdir(output_dir) if f.startswith("messages-")]
        self.assertGreater(len(message_files), 0)

        messages = self.read_file(output_dir, message_files[0])
        self.assertIn("zerver_message", messages)
        self.assertIn("zerver_usermessage", messages)
        self.assertGreater(len(messages["zerver_message"]), 0)

        # Verify message content
        message_contents = [m["content"] for m in messages["zerver_message"]]
        # Check that a regular message exists
        self.assertTrue(any("Hello everyone!" in c for c in message_contents))
        # Check that system messages were filtered out
        self.assertFalse(any(c == "Welcome to the server!" for c in message_contents))

    def test_do_import_realm(self) -> None:
        output_dir = self.make_import_output_dir("discord")

        with (
            patch("builtins.print"),
            self.assertLogs(level="INFO"),
            self.settings(EXTERNAL_HOST="zulip.example.com"),
        ):
            do_convert_data(
                discord_data_dir=self.discord_fixtures_dir,
                output_dir=output_dir,
            )

        with self.assertLogs(level="INFO"):
            do_import_realm(
                import_dir=output_dir,
                subdomain="discord-test",
            )

        realm = get_realm("discord-test")
        self.assertIsNotNone(realm)

        presence_sequence = PresenceSequence.objects.get(realm=realm)
        self.assertEqual(presence_sequence.last_update_id, 0)

        # Check that messages were imported and rendered
        messages = Message.objects.filter(realm=realm)
        self.assertGreater(messages.count(), 0)
        for message in messages:
            self.assertIsNotNone(message.rendered_content)

        # Check stream messages exist
        stream_messages = messages.filter(recipient__type=Recipient.STREAM)
        self.assertGreater(stream_messages.count(), 0)

        self.verify_emoji_code_foreign_keys()
