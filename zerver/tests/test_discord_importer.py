import json
import os
import tempfile
from typing import Any
from urllib.parse import urljoin

import responses
from responses import matchers

from zerver.data_import.discord import (
    DISCORD_API_BASE_URL,
    DiscordPaginationConfig,
    do_convert_directory,
    get_discord_api_data,
    get_zulip_compatible_full_name,
    group_messages_into_channels,
)
from zerver.lib.import_realm import do_import_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zerver.models.realms import get_realm
from zerver.tests.test_import_export import make_export_output_dir

DISCORD_GUILD_ID = "1519311536839983195"
GET_GUILD_URL = urljoin(DISCORD_API_BASE_URL, f"guilds/{DISCORD_GUILD_ID}")
DISCORD_BOT_TOKEN = "DISCORD_BOT_TOKEN"
GET_GUILD_MEMBERS_URL = urljoin(DISCORD_API_BASE_URL, f"guilds/{DISCORD_GUILD_ID}/members")


class DiscordImporterTestCase(ZulipTestCase):
    def add_get_guild_response(
        self, requests_mock: responses.RequestsMock, fixture_name: str
    ) -> None:
        requests_mock.add(
            responses.GET,
            GET_GUILD_URL,
            self.fixture_data(fixture_name, "discord_api_response_fixtures/get_guilds"),
        )

    def get_guild_members_response(self) -> str:
        return self.fixture_data(
            f"{DISCORD_GUILD_ID}.json", "discord_api_response_fixtures/get_guild_members"
        )

    def get_exported_channels(self) -> list[dict[str, Any]]:
        channels_dir = self.fixture_file_name("channels", "discord_fixtures")
        exported_channels = []
        for file_name in sorted(os.listdir(channels_dir)):
            with open(os.path.join(channels_dir, file_name)) as f:
                exported_channels.append(json.load(f))
        return exported_channels


class DiscordImporterIntegrationTest(DiscordImporterTestCase):
    SUBDOMAIN = "test-import-discord-realm"

    def do_import_realm_fixture(self) -> None:
        converted_file_output_dir = make_export_output_dir()
        with (
            responses.RequestsMock() as requests_mock,
            self.assertLogs(level="INFO"),
            self.settings(EXTERNAL_HOST="zulip.example.com"),
        ):
            self.add_get_guild_response(requests_mock, f"{DISCORD_GUILD_ID}.json")
            requests_mock.add(
                responses.GET,
                GET_GUILD_MEMBERS_URL,
                self.get_guild_members_response(),
            )
            do_convert_directory(
                self.fixture_file_name("", "discord_fixtures"),
                converted_file_output_dir,
                DISCORD_BOT_TOKEN,
            )
        with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
            do_import_realm(converted_file_output_dir, self.SUBDOMAIN)

    def test_imported_users(self) -> None:
        self.do_import_realm_fixture()
        guild_response = self.fixture_data(
            f"{DISCORD_GUILD_ID}.json", "discord_api_response_fixtures/get_guilds"
        )
        guild = json.loads(guild_response)
        guild_members = json.loads(self.get_guild_members_response())

        def expected_user(
            discord_user_id: str, full_name: str, is_bot: bool, is_mirror_dummy: bool
        ) -> dict[str, Any]:
            if is_bot:
                email = f"{full_name}-bot@zulip.example.com"
                bot_type = UserProfile.DEFAULT_BOT
            else:
                email = f"{discord_user_id}@discordexport.zulip.com"
                bot_type = None

            if discord_user_id == guild["owner_id"]:
                role = UserProfile.ROLE_REALM_OWNER
            else:
                role = UserProfile.ROLE_MEMBER

            return {
                "delivery_email": email,
                "full_name": full_name,
                "role": role,
                "is_bot": is_bot,
                "bot_type": bot_type,
                "is_active": not is_mirror_dummy,
                "is_mirror_dummy": is_mirror_dummy,
            }

        expected_users: dict[str, dict[str, Any]] = {}

        # Every current member is imported, including those who never
        # posted.
        for member in guild_members:
            user = member["user"]
            full_name = member["nick"] or user["global_name"] or user["username"]
            is_bot = user.get("bot", False)
            expected_users[user["id"]] = expected_user(
                user["id"], full_name, is_bot, is_mirror_dummy=False
            )

        # The fixture has no threads or direct messages, so every message
        # author who isn't a member, like hamlet, is a mirror dummy.
        for exported_channel in self.get_exported_channels():
            for message in exported_channel["messages"]:
                author = message["author"]
                if author["id"] in expected_users:
                    continue
                expected_users[author["id"]] = expected_user(
                    author["id"], author["nickname"], author["isBot"], is_mirror_dummy=True
                )
        self.assertTrue(any(user["is_mirror_dummy"] for user in expected_users.values()))

        self.assertCountEqual(
            UserProfile.objects.filter(realm=get_realm(self.SUBDOMAIN)).values(
                "delivery_email",
                "full_name",
                "role",
                "is_bot",
                "bot_type",
                "is_active",
                "is_mirror_dummy",
            ),
            expected_users.values(),
        )


class DiscordImporterUnitTest(DiscordImporterTestCase):
    def test_convert_directory_without_channels_dir(self) -> None:
        with self.assertRaises(ValueError) as e:
            do_convert_directory(tempfile.mkdtemp(), make_export_output_dir(), DISCORD_BOT_TOKEN)
        self.assertEqual(
            "Import does not have the layout we expect! Export every channel data "
            "in a 'channels' directory.",
            str(e.exception),
        )

    def test_convert_directory_with_several_guilds(self) -> None:
        data_dir = tempfile.mkdtemp()
        os.mkdir(os.path.join(data_dir, "channels"))
        for guild_id in ["1", "2"]:
            with open(os.path.join(data_dir, "channels", f"{guild_id}.json"), "w") as f:
                json.dump(
                    {
                        "guild": {"id": guild_id},
                        "channel": {"id": guild_id, "type": "GuildTextChat"},
                        "messages": [],
                    },
                    f,
                )
        with self.assertRaises(ValueError) as e:
            do_convert_directory(data_dir, make_export_output_dir(), DISCORD_BOT_TOKEN)
        self.assertEqual(
            "The export must contain the channels of exactly one Discord server.",
            str(e.exception),
        )

    def test_paginated_get_discord_api_data(self) -> None:
        members = [{"user": {"id": str(user_id)}} for user_id in [2, 1, 3]]
        with responses.RequestsMock() as requests_mock:
            requests_mock.add(
                responses.GET,
                GET_GUILD_MEMBERS_URL,
                json=members[:2],
                match=[
                    matchers.header_matcher({"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}),
                    matchers.query_param_matcher({"limit": "2"}),
                ],
            )
            requests_mock.add(
                responses.GET,
                GET_GUILD_MEMBERS_URL,
                json=members[2:],
                match=[matchers.query_param_matcher({"limit": "2", "after": "2"})],
            )
            pagination = DiscordPaginationConfig(
                limit=2, id_getter=lambda member: member["user"]["id"]
            )
            fetched_members = get_discord_api_data(
                f"guilds/{DISCORD_GUILD_ID}/members", DISCORD_BOT_TOKEN, pagination
            )
        self.assertEqual(fetched_members, members)

    def test_failed_get_discord_api_data(self) -> None:
        with (
            responses.RequestsMock() as requests_mock,
            self.assertLogs(level="INFO") as logs,
            self.assertRaises(Exception) as e,
        ):
            requests_mock.add(responses.GET, GET_GUILD_URL, status=401, body="Unauthorized")
            get_discord_api_data(f"guilds/{DISCORD_GUILD_ID}", DISCORD_BOT_TOKEN)
        self.assertEqual("HTTP error accessing the Discord API.", str(e.exception))
        self.assertEqual(logs.output, ["INFO:root:HTTP error: 401, Response: Unauthorized"])

    def test_group_messages_into_channels(self) -> None:
        def channel_export(
            channel_id: str, channel_type: str, message_ids: list[str], category_id: str = ""
        ) -> dict[str, Any]:
            return {
                "channel": {"id": channel_id, "type": channel_type, "categoryId": category_id},
                "messages": [{"id": message_id} for message_id in message_ids],
            }

        with self.assertLogs(level="WARNING") as logs:
            discord_channels = group_messages_into_channels(
                [
                    # Listed before its parent channel.
                    channel_export("200", "GuildPublicThread", ["2"], category_id="100"),
                    channel_export("100", "GuildTextChat", ["3", "1"]),
                    # A second export file of the same channel.
                    channel_export("100", "GuildTextChat", ["4"]),
                    channel_export("150", "GuildVoiceChat", ["7"]),
                    channel_export("250", "GuildPrivateThread", ["8"], category_id="150"),
                    channel_export("300", "GuildPublicThread", ["5"], category_id="absent"),
                    channel_export("400", "GuildCategory", []),
                    channel_export("500", "DirectTextChat", ["6"]),
                ]
            )

        self.assertEqual(
            {
                discord_channel.channel["id"]: [
                    message["id"] for message in discord_channel.messages
                ]
                for discord_channel in discord_channels
            },
            {"100": ["1", "2", "3", "4"], "150": ["7"]},
        )
        self.assertEqual(
            logs.output,
            [
                "WARNING:root:Skipping private Discord thread 250.",
                "WARNING:root:Skipping Discord thread 300; its parent channel absent is missing.",
            ],
        )

    def test_get_zulip_compatible_full_name(self) -> None:
        def full_name(*discord_names: str | None) -> str:
            return get_zulip_compatible_full_name(list(discord_names), discord_user_id="12345")

        self.assertEqual(full_name("eruXP"), "eruXP")
        self.assertEqual(full_name('a*b`c\\d>e"f@g'), "a_b_c_d_e_f_g")
        self.assertEqual(full_name("  a\x00b  "), "ab")
        self.assertEqual(full_name("Bob|15"), "Bob")
        self.assertEqual(full_name("Bob|15 "), "Bob")
        self.assertEqual(full_name("Bob|1|2"), "Bob")
        self.assertEqual(full_name("\x00\x01"), "Discord user 12345")
        self.assertEqual(full_name(None, "|42", "alice"), "alice")
        self.assertEqual(full_name(None, "\x00"), "Discord user 12345")
