import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import responses

from zerver.data_import.discord import (
    DISCORD_API_BASE_URL,
    MAIN_DISCORD_IMPORT_TOPIC,
    DiscordChannel,
    convert_channels,
    convert_messages,
    do_convert_directory,
    get_discord_api_data,
    get_zulip_compatible_full_name,
    group_messages_into_channels,
    is_private_channel,
    process_message_attachments,
    should_convert_message,
)
from zerver.data_import.import_util import AttachmentRecordData, UploadRecordData
from zerver.lib.import_realm import do_import_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import messages_for_topic
from zerver.models import Attachment, Message
from zerver.models.realms import get_realm
from zerver.models.streams import Stream, Subscription
from zerver.models.users import UserProfile
from zerver.tests.test_import_export import make_export_output_dir
from zproject.backends import EMAIL_WITH_ENCODED_DISCORD_ID

# Guild ID of the server in the export fixture.
DISCORD_GUILD_ID = "1519311536839983195"

# Discord user IDs of the message authors in the export fixture. "bot" is a
# Discord bot account.
DISCORD_USER_ID = {
    "pieter": "1000000000000000001",
    "hamlet": "1000000000000000002",
    "bot": "1000000000000000003",
}

# Channel IDs of the channels in the export fixture. "general" is split across
# several export files, "private" is a private channel, and "voice" is a voice
# channel that also carries text chat.
DISCORD_CHANNEL_ID = {
    "general": "1519311538035490958",
    "general-2": "1519313380647764018",
    "private": "1519314256007266425",
    "voice": "1519311538035490959",
}

# Full names, taken from each author's server nickname in the fixture.
DISCORD_USER_FULL_NAME = {
    "pieter": "pieter",
    "hamlet": "hamlet",
    "bot": "test-zulip-import",
}

# The realm's external host when the fixture is converted. Bots, unlike humans,
# get a readable "<name>-bot@<host>" email derived from this host rather than
# the Discord-ID-encoded scheme.
DISCORD_IMPORT_EXTERNAL_HOST = "zulip.example.com"
DISCORD_BOT_EMAIL = f"{DISCORD_USER_FULL_NAME['bot']}-bot@{DISCORD_IMPORT_EXTERNAL_HOST}"

DISCORD_BOT_TOKEN = "DISCORD_BOT_TOKEN"

# Maps each export channel to the Zulip stream it is imported as. The voice
# channel's text chat gets a prefixed name; see VOICE_CHANNEL_NAME_PREFIX.
DISCORD_CHANNEL_ID_TO_STREAM_NAME = {
    DISCORD_CHANNEL_ID["general"]: "general",
    DISCORD_CHANNEL_ID["general-2"]: "general-2",
    DISCORD_CHANNEL_ID["private"]: "private",
    DISCORD_CHANNEL_ID["voice"]: "[voice] General",
}

# The Discord message types the importer converts; every other type (system
# messages like joins and pins) is dropped. Defined here independently of the
# importer so the tests cross-check its message selection.
CONVERTIBLE_DISCORD_MESSAGE_TYPES = {"Default", "Reply"}

GET_GUILD_URL = urljoin(DISCORD_API_BASE_URL, f"guilds/{DISCORD_GUILD_ID}")


def encoded_discord_email(discord_user_id: str) -> str:
    return EMAIL_WITH_ENCODED_DISCORD_ID.format(discord_user_id=discord_user_id)


def expected_sender_email(discord_user_id: str) -> str:
    if discord_user_id == DISCORD_USER_ID["bot"]:  # nocoverage
        return DISCORD_BOT_EMAIL
    return encoded_discord_email(discord_user_id)


def get_channel_url(channel_id: str) -> str:
    return urljoin(DISCORD_API_BASE_URL, f"channels/{channel_id}")


class DiscordImporterTestCase(ZulipTestCase):
    FIXTURE_DIR = "discord_fixtures"

    def discord_api_response(self, file_name: str) -> str:
        return self.fixture_data(file_name, "discord_api_response_fixtures")

    def add_get_guild_response(self, fixture_name: str | None = None) -> None:
        # Defaults to the export's own guild response; pass a name to override.
        fixture_name = fixture_name or f"get_guilds/{DISCORD_GUILD_ID}.json"
        responses.add(responses.GET, GET_GUILD_URL, self.discord_api_response(fixture_name))

    def add_get_channel_response(self, channel_id: str, fixture_name: str | None = None) -> None:
        # Defaults to the get_channels response named for the channel ID.
        fixture_name = fixture_name or f"get_channels/{channel_id}.json"
        responses.add(
            responses.GET, get_channel_url(channel_id), self.discord_api_response(fixture_name)
        )

    def read_convertible_exported_messages(self) -> dict[str, list[dict[str, Any]]]:
        """Group the export fixture's convertible messages by Discord channel ID.

        This re-derives the importer's message selection independently of the
        importer: it merges a channel's export partitions and keeps only the
        message types we convert that have content to import, so tests can
        assert that the imported messages match the export exactly. The fixture
        has no thread or direct message exports, so every channel file becomes a
        Zulip stream.
        """
        channels_dir = os.path.join(self.fixture_file_name("", self.FIXTURE_DIR), "channels")
        messages_by_channel_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for file_name in os.listdir(channels_dir):
            if not file_name.endswith(".json"):  # nocoverage
                continue
            with open(os.path.join(channels_dir, file_name)) as channel_export_file:
                channel_export = json.load(channel_export_file)
            channel_id = channel_export["channel"]["id"]
            for message in channel_export["messages"]:
                if message["type"] not in CONVERTIBLE_DISCORD_MESSAGE_TYPES:
                    continue
                # The importer drops a convertible message that would have no
                # content: neither text nor an attachment to link below it.
                if not message["content"].strip() and not message["attachments"]:
                    continue
                messages_by_channel_id[channel_id].append(message)
        return messages_by_channel_id


class DiscordImporterIntegrationTest(DiscordImporterTestCase):
    SUBDOMAIN = "test-import-discord-realm"

    @responses.activate
    def import_discord_fixture(self) -> None:
        # The Discord server owner and each channel's privacy are looked up
        # via the Discord API.
        self.add_get_guild_response()
        self.add_get_channel_response(DISCORD_CHANNEL_ID["general"])
        self.add_get_channel_response(DISCORD_CHANNEL_ID["general-2"])
        self.add_get_channel_response(DISCORD_CHANNEL_ID["private"])
        self.add_get_channel_response(DISCORD_CHANNEL_ID["voice"])

        output_dir = make_export_output_dir()
        fixture_dir = self.fixture_file_name("", self.FIXTURE_DIR)
        with (
            self.assertLogs(level="INFO"),
            self.settings(EXTERNAL_HOST=DISCORD_IMPORT_EXTERNAL_HOST),
        ):
            do_convert_directory(fixture_dir, output_dir, DISCORD_BOT_TOKEN)

        with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
            do_import_realm(output_dir, self.SUBDOMAIN)

    def test_imported_users(self) -> None:
        self.import_discord_fixture()
        realm = get_realm(self.SUBDOMAIN)

        imported_users = UserProfile.objects.filter(realm=realm)
        # The two human authors get Discord-ID-encoded emails, while the bot
        # account that posted a join message gets a readable "<name>-bot" email.
        self.assertSetEqual(
            {user.delivery_email for user in imported_users},
            {encoded_discord_email(DISCORD_USER_ID[name]) for name in ("pieter", "hamlet")}
            | {DISCORD_BOT_EMAIL},
        )

        # The server nickname is used as the Zulip full name.
        self.assertSetEqual(
            {user.full_name for user in imported_users},
            set(DISCORD_USER_FULL_NAME.values()),
        )

        # The Discord bot account, identified via the guild's roles, is imported
        # as a bot; the human authors are not.
        bot = UserProfile.objects.get(realm=realm, delivery_email=DISCORD_BOT_EMAIL)
        self.assertTrue(bot.is_bot)
        self.assertEqual(bot.bot_type, UserProfile.DEFAULT_BOT)
        self.assertSetEqual(
            {user.delivery_email for user in imported_users.filter(is_bot=False)},
            {encoded_discord_email(DISCORD_USER_ID[name]) for name in ("pieter", "hamlet")},
        )

        # All users are imported as active, non-dummy accounts.
        for user in imported_users:
            self.assertTrue(user.is_active)
            self.assertFalse(user.is_mirror_dummy)

        # The Discord server owner is imported as the realm owner; everyone
        # else is a member.
        owner = UserProfile.objects.get(
            realm=realm, delivery_email=encoded_discord_email(DISCORD_USER_ID["pieter"])
        )
        self.assertEqual(owner.role, UserProfile.ROLE_REALM_OWNER)
        member = UserProfile.objects.get(
            realm=realm, delivery_email=encoded_discord_email(DISCORD_USER_ID["hamlet"])
        )
        self.assertEqual(member.role, UserProfile.ROLE_MEMBER)

    def test_imported_channels(self) -> None:
        self.import_discord_fixture()
        realm = get_realm(self.SUBDOMAIN)

        # The export has "general", "general-2", "private", and a voice channel;
        # the thread that "private" references has no export file of its own and
        # so contributes no standalone channel.
        self.assert_length(Stream.objects.filter(realm=realm), 4)

        # A channel the @everyone role can view imports as a public channel;
        # one hidden from @everyone imports as invite-only.
        general = Stream.objects.get(realm=realm, name="general")
        self.assertFalse(general.invite_only)
        private = Stream.objects.get(realm=realm, name="private")
        self.assertTrue(private.invite_only)

        # A voice channel's text chat is imported under a prefixed name, so it
        # doesn't collide with the "general" text channel.
        voice = Stream.objects.get(realm=realm, name="[voice] General")
        self.assertFalse(voice.invite_only)

        # The channel's message authors (including the bot, which posted a join
        # message there) are subscribed to its Zulip channel.
        subscriber_emails = {
            subscription.user_profile.delivery_email
            for subscription in Subscription.objects.filter(recipient=general.recipient)
        }
        self.assertSetEqual(
            subscriber_emails,
            {encoded_discord_email(DISCORD_USER_ID[name]) for name in ("pieter", "hamlet")}
            | {DISCORD_BOT_EMAIL},
        )

    def test_imported_messages(self) -> None:
        self.import_discord_fixture()
        realm = get_realm(self.SUBDOMAIN)
        convertible_messages_by_channel_id = self.read_convertible_exported_messages()

        for channel_id, channel_name in DISCORD_CHANNEL_ID_TO_STREAM_NAME.items():
            channel = Stream.objects.get(realm=realm, name=channel_name)
            assert channel.recipient is not None
            imported_messages = messages_for_topic(
                realm.id, channel.recipient.id, MAIN_DISCORD_IMPORT_TOPIC
            )
            exported_messages = convertible_messages_by_channel_id[channel_id]

            # Each channel's convertible messages are all imported into its
            # single "imported from Discord" topic with the right sender and
            # send time -- and nothing else is, so system messages like joins
            # and pins, empty messages, and the messages of dropped channels,
            # are excluded.
            self.assertEqual(
                sorted(
                    (message.sender.delivery_email, message.date_sent.timestamp())
                    for message in imported_messages
                ),
                sorted(
                    (
                        expected_sender_email(message["author"]["id"]),
                        datetime.fromisoformat(message["timestamp"]).timestamp(),
                    )
                    for message in exported_messages
                ),
            )

        # The imported users author no messages beyond their converted ones, so
        # nothing is duplicated or imported into an unexpected channel.
        imported_users = UserProfile.objects.filter(realm=realm)
        self.assertEqual(
            Message.objects.filter(realm=realm, sender__in=imported_users).count(),
            sum(len(messages) for messages in convertible_messages_by_channel_id.values()),
        )

        # Messages within a topic are imported in chronological order.
        general = Stream.objects.get(realm=realm, name="general")
        assert general.recipient is not None
        dates_sent = [
            message.date_sent
            for message in messages_for_topic(
                realm.id, general.recipient.id, MAIN_DISCORD_IMPORT_TOPIC
            ).order_by("id")
        ]
        self.assertEqual(dates_sent, sorted(dates_sent))

        # Message content is imported verbatim for now; translating
        # Discord-specific markup is a TODO.
        self.assertEqual(
            Message.objects.get(
                realm=realm, content="**Bold** *italic* __underline__"
            ).sender.delivery_email,
            encoded_discord_email(DISCORD_USER_ID["pieter"]),
        )

        # Each attachment on a convertible message is copied out of the export's
        # media directory, which is referenced by a path relative to each export
        # file, and imported under its original file name.
        exported_file_names = {
            attachment["fileName"]
            for messages in self.read_convertible_exported_messages().values()
            for message in messages
            for attachment in message["attachments"]
        }
        attachments = Attachment.objects.filter(realm=realm)
        self.assertSetEqual(
            {attachment.file_name for attachment in attachments},
            exported_file_names,
        )

        image_attachment = attachments.get(file_name="Screenshot_2026-03-18_222549.png")
        # The attachment is owned by the sender of its message and linked to it.
        self.assertEqual(
            image_attachment.owner.delivery_email,
            encoded_discord_email(DISCORD_USER_ID["pieter"]),
        )
        message = image_attachment.messages.get()
        self.assertTrue(message.has_attachment)
        # The original message text is kept and the uploaded file is linked
        # below it.
        self.assertEqual(message.content.split("\n\n")[0], "Image files")
        self.assertIn(
            f"[Screenshot_2026-03-18_222549.png](/user_uploads/{image_attachment.path_id})",
            message.content,
        )


class DiscordImporterUnitTest(DiscordImporterTestCase):
    def test_convert_directory_without_channels_dir(self) -> None:
        # An export directory missing the required "channels" directory is
        # rejected.
        output_dir = make_export_output_dir()
        data_dir = tempfile.mkdtemp()
        with self.assertRaises(ValueError) as e:
            do_convert_directory(data_dir, output_dir, DISCORD_BOT_TOKEN)
        self.assertEqual(
            "Import does not have the layout we expect! Export every channel data "
            "in a 'channels' directory.",
            str(e.exception),
        )

    @responses.activate
    def test_convert_directory_when_owner_sent_no_messages(self) -> None:
        # The Discord API reports an owner who never posted, so they aren't
        # discovered as a user and no realm owner can be assigned.
        # The owner_id in this fixture is "0000", matching unimportable_owner_id.
        unimportable_owner_id = "0000"
        self.add_get_guild_response("get_guilds/guild_with_unimportable_owner.json")
        self.add_get_channel_response(DISCORD_CHANNEL_ID["general"])
        self.add_get_channel_response(DISCORD_CHANNEL_ID["general-2"])
        self.add_get_channel_response(DISCORD_CHANNEL_ID["private"])
        self.add_get_channel_response(DISCORD_CHANNEL_ID["voice"])

        output_dir = make_export_output_dir()
        fixture_dir = self.fixture_file_name("", self.FIXTURE_DIR)
        with (
            self.assertLogs(level="INFO"),
            self.settings(EXTERNAL_HOST="zulip.example.com"),
            self.assertRaises(AssertionError) as e,
        ):
            do_convert_directory(fixture_dir, output_dir, DISCORD_BOT_TOKEN)
        self.assertEqual(
            f"The Discord server owner (user ID {unimportable_owner_id}) did not send "
            "any messages in the export, so no realm owner could be assigned.",
            str(e.exception),
        )

    def test_process_message_attachments_skips_missing_file(self) -> None:
        # An attachment whose file isn't present in the export is skipped with a
        # warning rather than failing the import.
        discord_data_dir = tempfile.mkdtemp()
        zerver_attachment: list[AttachmentRecordData] = []
        uploads_list: list[UploadRecordData] = []

        with self.assertLogs(level="INFO") as logs:
            markdown = process_message_attachments(
                # A Windows-style relative path, as Discord Chat Exporter writes
                # on Windows.
                attachments=[{"url": "media\\missing.png", "fileName": "missing.png"}],
                realm_id=0,
                message_id=1,
                user_id=1,
                zerver_attachment=zerver_attachment,
                uploads_list=uploads_list,
                discord_data_dir=discord_data_dir,
                output_dir=make_export_output_dir(),
            )

        self.assertEqual(markdown, "")
        self.assertEqual(zerver_attachment, [])
        self.assertEqual(uploads_list, [])
        self.assertIn("Message attachment file not found: 'media\\missing.png'", logs.output[0])

    @responses.activate
    def test_failed_get_discord_api_data(self) -> None:
        responses.add(responses.GET, GET_GUILD_URL, status=401)
        with self.assertRaises(Exception) as e, self.assertLogs(level="INFO"):
            get_discord_api_data(f"guilds/{DISCORD_GUILD_ID}", DISCORD_BOT_TOKEN)
        self.assertEqual("HTTP error accessing the Discord API.", str(e.exception))

    def test_should_convert_message(self) -> None:
        # Messages with user-authored content are converted.
        self.assertTrue(should_convert_message({"id": "1", "type": "Default"}))
        self.assertTrue(should_convert_message({"id": "2", "type": "Reply"}))

        # Known system messages are skipped without warning.
        with self.assertNoLogs(level="WARNING"):
            self.assertFalse(should_convert_message({"id": "3", "type": "GuildMemberJoin"}))

        # An unrecognized type (such as a slash-command message, which
        # DiscordChatExporter leaves unnamed) is skipped but logs a warning so
        # that any dropped content is visible.
        with self.assertLogs(level="WARNING") as logs:
            self.assertFalse(should_convert_message({"id": "4", "type": "20"}))
        self.assertIn("Skipping Discord message 4 of unsupported type 20", logs.output[0])

    def test_convert_messages_drops_empty_messages(self) -> None:
        # A convertible message with no text and no attachment to link would
        # import as a blank Zulip message, so it is dropped; whitespace-only
        # content counts as empty too.
        discord_channel_id = "100"

        def discord_message(message_id: str, content: str) -> dict[str, Any]:
            return {
                "id": message_id,
                "type": "Default",
                "timestamp": "2026-03-18T22:25:49.000+00:00",
                "author": {"id": DISCORD_USER_ID["pieter"]},
                "content": content,
                "attachments": [],
            }

        discord_channels = [
            DiscordChannel(
                channel={"id": discord_channel_id},
                messages=[
                    discord_message("1", "Hello"),
                    discord_message("2", ""),
                    discord_message("3", "   \n  "),
                ],
                invite_only=False,
            )
        ]

        output_dir = make_export_output_dir()
        with self.assertLogs(level="INFO"):
            convert_messages(
                discord_channels=discord_channels,
                recipient_id_by_discord_channel_id={discord_channel_id: 1},
                discord_user_id_to_zulip_user_id={DISCORD_USER_ID["pieter"]: 5},
                realm={"zerver_subscription": []},
                realm_id=0,
                discord_data_dir=tempfile.mkdtemp(),
                output_dir=output_dir,
                zerver_attachment=[],
                uploads_list=[],
            )

        with open(os.path.join(output_dir, "messages-000001.json")) as messages_file:
            zerver_message = json.load(messages_file)["zerver_message"]

        # Only the message with text survives the two empty ones.
        self.assertEqual([message["content"] for message in zerver_message], ["Hello"])

    @responses.activate
    def test_group_messages_into_channels(self) -> None:
        def channel_export(
            channel_id: str, channel_type: str, message_ids: list[str], category_id: str = ""
        ) -> dict[str, object]:
            return {
                "channel": {"id": channel_id, "type": channel_type, "categoryId": category_id},
                "messages": [
                    {"id": message_id, "author": {"id": "1"}} for message_id in message_ids
                ],
            }

        # Privacy is looked up via the API: "100" reuses a real public channel's
        # response and "150" a real private one.
        self.add_get_channel_response("100", f"get_channels/{DISCORD_CHANNEL_ID['general']}.json")
        self.add_get_channel_response("150", f"get_channels/{DISCORD_CHANNEL_ID['private']}.json")

        with self.assertLogs(level="WARNING") as logs:
            discord_channels = group_messages_into_channels(
                [
                    # The thread "200" is listed before its parent "100" to
                    # check that threads are still merged regardless of the
                    # order channels appear in the export.
                    channel_export("200", "GuildPublicThread", ["2"], category_id="100"),
                    channel_export("100", "GuildTextChat", ["3", "1"]),
                    # A second export partition of channel "100"; its messages
                    # merge in and its privacy isn't looked up a second time.
                    channel_export("100", "GuildTextChat", ["4"]),
                    channel_export("150", "GuildTextChat", ["7"]),
                    # A private thread is dropped even though its parent "150"
                    # is a converted channel; we don't convert private threads.
                    channel_export("250", "GuildPrivateThread", ["8"], category_id="150"),
                    # A public thread whose parent is absent from the export is
                    # dropped too.
                    channel_export("300", "GuildPublicThread", ["5"], category_id="absent"),
                    channel_export("400", "GuildCategory", []),
                    channel_export("500", "DirectTextChat", ["6"]),
                ],
                DISCORD_GUILD_ID,
                DISCORD_BOT_TOKEN,
            )

        channels_by_id = {
            discord_channel.channel["id"]: discord_channel for discord_channel in discord_channels
        }

        # Categories, direct messages, and threads don't become standalone
        # Zulip channels.
        self.assertEqual(sorted(channels_by_id), ["100", "150"])

        # The two partitions of "100" and its public thread are merged, and the
        # parent's messages are ordered chronologically by snowflake ID.
        self.assertEqual(
            [message["id"] for message in channels_by_id["100"].messages], ["1", "2", "3", "4"]
        )
        self.assertFalse(channels_by_id["100"].invite_only)

        # A private channel becomes invite-only. Its private thread "250" is
        # dropped, so only the channel's own message remains.
        self.assertTrue(channels_by_id["150"].invite_only)
        self.assertEqual([message["id"] for message in channels_by_id["150"].messages], ["7"])

        # The dropped private thread and the orphaned public thread contribute
        # no messages to any channel. These are rare edge cases.
        all_imported_message_ids = [
            message["id"]
            for discord_channel in discord_channels
            for message in discord_channel.messages
        ]
        self.assertNotIn("8", all_imported_message_ids)
        self.assertNotIn("5", all_imported_message_ids)
        warnings = "\n".join(logs.output)
        self.assertIn("Skipping private Discord thread 250.", warnings)
        self.assertIn(
            "Skipping Discord thread 300; its parent channel absent is missing.", warnings
        )

    def test_announcement_channel_becomes_update_announcements_stream(self) -> None:
        # A Discord announcement channel (GuildNews) is designated the realm's
        # update announcements channel.
        realm = {
            "zerver_realm": [{"zulip_update_announcements_stream": None}],
            "zerver_stream": [],
            "zerver_recipient": [],
            "zerver_subscription": [],
        }
        announcement_channel = DiscordChannel(
            channel={"id": "1", "name": "announcements", "type": "GuildNews", "topic": None},
            messages=[{"author": {"id": "10"}}],
            invite_only=False,
        )
        with self.assertLogs(level="INFO"):
            convert_channels(
                discord_channels=[announcement_channel],
                discord_user_id_to_zulip_user_id={"10": 100},
                realm=realm,
                realm_id=0,
                timestamp=0.0,
            )
        self.assertEqual(
            realm["zerver_realm"][0]["zulip_update_announcements_stream"],
            realm["zerver_stream"][0]["id"],
        )

    @responses.activate
    def test_is_private_channel(self) -> None:
        # The private channel denies the @everyone role the View Channel
        # permission; the public channel carries no permission overwrites.
        self.add_get_channel_response(DISCORD_CHANNEL_ID["private"])
        self.add_get_channel_response(DISCORD_CHANNEL_ID["general"])
        # A channel with only a member overwrite (no @everyone role overwrite)
        # is treated as public.
        self.add_get_channel_response(
            "no-everyone-overwrite", "get_channels/channel_member_overwrite_only.json"
        )

        self.assertTrue(
            is_private_channel(DISCORD_CHANNEL_ID["private"], DISCORD_GUILD_ID, DISCORD_BOT_TOKEN)
        )
        self.assertFalse(
            is_private_channel(DISCORD_CHANNEL_ID["general"], DISCORD_GUILD_ID, DISCORD_BOT_TOKEN)
        )
        self.assertFalse(
            is_private_channel("no-everyone-overwrite", DISCORD_GUILD_ID, DISCORD_BOT_TOKEN)
        )

    def test_get_zulip_compatible_full_name(self) -> None:
        # A name Zulip already accepts is returned unchanged.
        self.assertEqual(get_zulip_compatible_full_name("eruXP", fallback="0"), "eruXP")

        # Characters Zulip disallows in names are replaced with "_".
        self.assertEqual(
            get_zulip_compatible_full_name('a*b`c\\d>e"f@g', fallback="0"), "a_b_c_d_e_f_g"
        )

        # Non-printable characters are dropped, and surrounding whitespace is
        # stripped.
        self.assertEqual(get_zulip_compatible_full_name("  a\x00b  ", fallback="0"), "ab")

        # A trailing "|<number>" is removed (it's ambiguous with mention markup).
        self.assertEqual(get_zulip_compatible_full_name("Bob|15", fallback="0"), "Bob")

        # If nothing usable remains, the fallback is returned.
        self.assertEqual(get_zulip_compatible_full_name("\x00\x01", fallback="12345"), "12345")
