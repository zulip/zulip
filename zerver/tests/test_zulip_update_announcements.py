import os
from datetime import timedelta
from unittest import mock
from unittest.mock import call, patch

import time_machine
from django.conf import settings
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.create_realm import do_create_realm
from zerver.actions.streams import do_deactivate_stream
from zerver.data_import.mattermost import do_convert_data
from zerver.lib.import_realm import do_import_realm
from zerver.lib.message import remove_single_newlines
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.zulip_update_announcements import (
    ZulipUpdateAnnouncement,
    send_zulip_update_announcements,
)
from zerver.models.messages import Message
from zerver.models.realms import get_realm
from zerver.models.recipients import Recipient, get_direct_message_group_user_ids
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot


class ZulipUpdateAnnouncementsTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()

        self.zulip_update_announcements = [
            ZulipUpdateAnnouncement(
                level=1,
                message="Announcement message 1.",
            ),
            ZulipUpdateAnnouncement(
                level=2,
                message="Announcement message 2.",
            ),
        ]

    def test_send_zulip_update_announcements(self) -> None:
        with mock.patch(
            "zerver.lib.zulip_update_announcements.zulip_update_announcements",
            self.zulip_update_announcements,
        ):
            realm = get_realm("zulip")

            # realm predates the "zulip updates" feature with the
            # zulip_update_announcements_stream set to None.
            realm.zulip_update_announcements_level = None
            realm.zulip_update_announcements_stream = None
            realm.save(
                update_fields=[
                    "zulip_update_announcements_level",
                    "zulip_update_announcements_stream",
                ]
            )

            group_direct_messages = Message.objects.filter(
                realm=realm, recipient__type=Recipient.DIRECT_MESSAGE_GROUP
            )
            self.assertFalse(group_direct_messages.exists())

            admin_user_ids = set(realm.get_human_admin_users().values_list("id", flat=True))
            notification_bot = get_system_bot(settings.NOTIFICATION_BOT, realm.id)
            expected_group_direct_message_user_ids = admin_user_ids | {notification_bot.id}

            now = timezone_now()
            with time_machine.travel(now, tick=False):
                send_zulip_update_announcements(skip_delay=False)

            realm.refresh_from_db()
            group_direct_message = group_direct_messages.first()
            assert group_direct_message is not None
            self.assertEqual(group_direct_message.sender, notification_bot)
            self.assertEqual(group_direct_message.date_sent, now)
            self.assertEqual(
                set(get_direct_message_group_user_ids(group_direct_message.recipient)),
                expected_group_direct_message_user_ids,
            )
            self.assertEqual(realm.zulip_update_announcements_level, 0)
            self.assertIn(
                "These notifications are currently turned off in your organization.",
                group_direct_message.content,
            )

            # Wait for one week before starting to skip sending updates.
            with time_machine.travel(now + timedelta(days=2), tick=False):
                send_zulip_update_announcements(skip_delay=False)
            realm.refresh_from_db()
            self.assertEqual(realm.zulip_update_announcements_level, 0)

            with time_machine.travel(now + timedelta(days=8), tick=False):
                send_zulip_update_announcements(skip_delay=False)
            realm.refresh_from_db()
            self.assertEqual(realm.zulip_update_announcements_level, 2)

            # Configure a stream. Two new updates added.
            verona = get_stream("verona", realm)
            realm.zulip_update_announcements_stream = verona
            realm.save(update_fields=["zulip_update_announcements_stream"])
            new_updates = [
                ZulipUpdateAnnouncement(
                    level=3,
                    message="Announcement message 3.",
                ),
                ZulipUpdateAnnouncement(
                    level=4,
                    message="Announcement message 4.",
                ),
            ]
            self.zulip_update_announcements.extend(new_updates)

            # verify zulip update announcements sent to configured stream.
            with time_machine.travel(now + timedelta(days=10), tick=False):
                send_zulip_update_announcements(skip_delay=False)
            realm.refresh_from_db()
            stream_messages = Message.objects.filter(
                realm=realm,
                sender=notification_bot,
                recipient__type_id=verona.id,
                date_sent__gte=now + timedelta(days=10),
            ).order_by("id")
            self.assert_length(stream_messages, 3)
            self.assertIn("To help you learn about new features", stream_messages[0].content)
            self.assertEqual(stream_messages[1].content, "Announcement message 3.")
            self.assertEqual(stream_messages[2].content, "Announcement message 4.")
            self.assertEqual(realm.zulip_update_announcements_level, 4)

    def test_send_zulip_update_announcements_with_stream_configured(self) -> None:
        with mock.patch(
            "zerver.lib.zulip_update_announcements.zulip_update_announcements",
            self.zulip_update_announcements,
        ):
            realm = get_realm("zulip")

            # realm predates the "zulip updates" feature with the
            # zulip_update_announcements_stream configured.
            realm.zulip_update_announcements_level = None
            realm.zulip_update_announcements_stream = get_stream("verona", realm)
            realm.save(
                update_fields=[
                    "zulip_update_announcements_level",
                    "zulip_update_announcements_stream",
                ]
            )

            group_direct_messages = Message.objects.filter(
                realm=realm, recipient__type=Recipient.DIRECT_MESSAGE_GROUP
            )
            self.assertFalse(group_direct_messages.exists())

            now = timezone_now()
            with time_machine.travel(now, tick=False):
                send_zulip_update_announcements(skip_delay=False)

            realm.refresh_from_db()
            self.assertTrue(group_direct_messages.exists())
            self.assertEqual(realm.zulip_update_announcements_level, 0)

            # Wait for 24 hours before starting to send updates.
            with time_machine.travel(now + timedelta(hours=10), tick=False):
                send_zulip_update_announcements(skip_delay=False)
            realm.refresh_from_db()
            self.assertEqual(realm.zulip_update_announcements_level, 0)

            with time_machine.travel(now + timedelta(days=1), tick=False):
                send_zulip_update_announcements(skip_delay=False)
            realm.refresh_from_db()
            self.assertEqual(realm.zulip_update_announcements_level, 2)

            # Two new updates added.
            new_updates = [
                ZulipUpdateAnnouncement(
                    level=3,
                    message="Announcement message 3.",
                ),
                ZulipUpdateAnnouncement(
                    level=4,
                    message="Announcement message 4.",
                ),
            ]
            self.zulip_update_announcements.extend(new_updates)

            # verify zulip update announcements sent to configured stream.
            with time_machine.travel(now + timedelta(days=2), tick=False):
                send_zulip_update_announcements(skip_delay=False)
            realm.refresh_from_db()
            notification_bot = get_system_bot(settings.NOTIFICATION_BOT, realm.id)
            stream_messages = Message.objects.filter(
                realm=realm,
                sender=notification_bot,
                recipient__type_id=realm.zulip_update_announcements_stream.id,
                date_sent__gte=now + timedelta(days=2),
            ).order_by("id")
            self.assert_length(stream_messages, 2)
            self.assertEqual(stream_messages[0].content, "Announcement message 3.")
            self.assertEqual(stream_messages[1].content, "Announcement message 4.")
            self.assertEqual(realm.zulip_update_announcements_level, 4)

            # One new update added.
            new_updates = [
                ZulipUpdateAnnouncement(
                    level=5,
                    message="Announcement message 5.",
                ),
            ]
            self.zulip_update_announcements.extend(new_updates)

            # Verify that update message is skipped if configured channel gets deactivated.
            # Note: 'do_deactivate_stream' sets 'zulip_update_announcements_stream' to None.
            channel_id = realm.zulip_update_announcements_stream.id
            do_deactivate_stream(realm.zulip_update_announcements_stream, acting_user=None)

            with time_machine.travel(now + timedelta(days=8), tick=False):
                send_zulip_update_announcements(skip_delay=False)
            realm.refresh_from_db()
            channel_messages = Message.objects.filter(
                realm=realm,
                sender=notification_bot,
                recipient__type_id=channel_id,
                date_sent__gte=now + timedelta(days=8),
            ).order_by("id")
            self.assert_length(channel_messages, 0)
            self.assertEqual(realm.zulip_update_announcements_level, 5)

    def test_send_zulip_update_announcements_skip_delay(self) -> None:
        with mock.patch(
            "zerver.lib.zulip_update_announcements.zulip_update_announcements",
            self.zulip_update_announcements,
        ):
            realm = get_realm("zulip")

            # realm predates the "zulip updates" feature with the
            # zulip_update_announcements_stream configured.
            realm.zulip_update_announcements_level = None
            realm.zulip_update_announcements_stream = get_stream("verona", realm)
            realm.save(
                update_fields=[
                    "zulip_update_announcements_level",
                    "zulip_update_announcements_stream",
                ]
            )

            group_direct_messages = Message.objects.filter(
                realm=realm, recipient__type=Recipient.DIRECT_MESSAGE_GROUP
            )
            self.assertFalse(group_direct_messages.exists())

            # post-upgrade hook sends a group DM.
            now = timezone_now()
            with time_machine.travel(now, tick=False):
                send_zulip_update_announcements(skip_delay=False)

            realm.refresh_from_db()
            self.assertTrue(group_direct_messages.exists())
            self.assertEqual(realm.zulip_update_announcements_level, 0)

            # For self-hosted servers, 9.0 upgrade notes suggests to run
            # 'send_zulip_update_announcements' management command with
            # '--skip-delay' argument to immediately send update messages.
            # 'zulip_update_announcements_stream' should be configured.
            with time_machine.travel(now, tick=False):
                send_zulip_update_announcements(skip_delay=True)

            realm.refresh_from_db()
            self.assertEqual(realm.zulip_update_announcements_level, 2)

    def test_group_direct_message_with_zulip_updates_stream_set(self) -> None:
        realm = get_realm("zulip")

        # realm predates the "zulip updates" feature.
        realm.zulip_update_announcements_level = None
        realm.save(update_fields=["zulip_update_announcements_level"])

        self.assertIsNotNone(realm.zulip_update_announcements_stream)

        group_direct_messages = Message.objects.filter(
            realm=realm, recipient__type=Recipient.DIRECT_MESSAGE_GROUP
        )
        self.assertFalse(group_direct_messages.exists())

        admin_user_ids = set(realm.get_human_admin_users().values_list("id", flat=True))
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, realm.id)
        expected_group_direct_message_user_ids = admin_user_ids | {notification_bot.id}

        now = timezone_now()
        with time_machine.travel(now, tick=False):
            send_zulip_update_announcements(skip_delay=False)

        realm.refresh_from_db()
        group_direct_message = group_direct_messages.first()
        assert group_direct_message is not None
        self.assertEqual(group_direct_message.sender, notification_bot)
        self.assertEqual(group_direct_message.date_sent, now)
        self.assertEqual(
            set(get_direct_message_group_user_ids(group_direct_message.recipient)),
            expected_group_direct_message_user_ids,
        )
        self.assertEqual(realm.zulip_update_announcements_level, 0)
        self.assertIn(
            "Starting tomorrow, users in your organization will receive "
            "[updates](/help/configure-automated-notices#zulip-update-announcements) about new Zulip features in "
            f"#**{realm.zulip_update_announcements_stream}>{realm.ZULIP_UPDATE_ANNOUNCEMENTS_TOPIC_NAME}**",
            group_direct_message.content,
        )

    def test_remove_single_newlines(self) -> None:
        # single newlines and double newlines
        input_text = "This is a sentence.\nThis is another sentence.\n\nThis is a third sentence."
        expected_output = (
            "This is a sentence. This is another sentence.\n\nThis is a third sentence."
        )
        self.assertEqual(remove_single_newlines(input_text), expected_output)

        # single newline at the beginning
        input_text = "\nThis is a sentence.\nThis is another sentence.\n\nThis is a third sentence."
        expected_output = (
            "This is a sentence. This is another sentence.\n\nThis is a third sentence."
        )
        self.assertEqual(remove_single_newlines(input_text), expected_output)

        # single newline at the end
        input_text = "This is a sentence.\nThis is another sentence.\n\nThis is a third sentence.\n"
        expected_output = (
            "This is a sentence. This is another sentence.\n\nThis is a third sentence."
        )
        self.assertEqual(remove_single_newlines(input_text), expected_output)

        # only single newlines in the middle
        input_text = "This is a sentence.\nThis is another sentence.\nThis is a third sentence.\nThis is a fourth sentence."
        expected_output = "This is a sentence. This is another sentence. This is a third sentence. This is a fourth sentence."
        self.assertEqual(remove_single_newlines(input_text), expected_output)

        # Bulleted lists on lines.
        input_text = "- This is a bullet.\n- This is another bullet.\n\n1. This is a list\n1. This is more list."
        expected_output = "- This is a bullet.\n- This is another bullet.\n\n1. This is a list\n1. This is more list."
        self.assertEqual(remove_single_newlines(input_text), expected_output)

        # Asterisks after newline for bold.
        input_text = "* This is a bullet.\n**word in bold** on the same line.\n* Another bullet."
        expected_output = (
            "* This is a bullet. **word in bold** on the same line.\n* Another bullet."
        )
        self.assertEqual(remove_single_newlines(input_text), expected_output)

        # Digit after newline.
        input_text = "1. This is a numbered list.\n2. Second list element.\n3.5 is a decimal.\n3. Third list element."
        expected_output = "1. This is a numbered list.\n2. Second list element. 3.5 is a decimal.\n3. Third list element."
        self.assertEqual(remove_single_newlines(input_text), expected_output)

        # Hyphen after newline.
        input_text = "- This is a list.\n-C-C- organic molecule structure.\n- Another list element."
        expected_output = (
            "- This is a list. -C-C- organic molecule structure.\n- Another list element."
        )
        self.assertEqual(remove_single_newlines(input_text), expected_output)

    def test_zulip_updates_for_realm_imported_from_other_product(self) -> None:
        with mock.patch(
            "zerver.lib.zulip_update_announcements.zulip_update_announcements",
            self.zulip_update_announcements,
        ):
            mattermost_data_dir = self.fixture_file_name("", "mattermost_fixtures")
            output_dir = self.make_import_output_dir("mattermost")

            with patch("builtins.print") as mock_print, self.assertLogs(level="WARNING"):
                do_convert_data(
                    mattermost_data_dir=mattermost_data_dir,
                    output_dir=output_dir,
                    masking_content=True,
                )
            self.assertEqual(
                mock_print.mock_calls,
                [
                    call("Generating data for", "gryffindor"),
                    call("Generating data for", "slytherin"),
                ],
            )

            gryffindor_output_dir = os.path.join(output_dir, "gryffindor")

            with self.assertLogs(level="INFO"):
                do_import_realm(
                    import_dir=gryffindor_output_dir,
                    subdomain="gryffindor",
                )

            imported_realm = get_realm("gryffindor")
            notification_bot = get_system_bot(settings.NOTIFICATION_BOT, imported_realm.id)

            gryffindor_common_room = get_stream("Gryffindor common room", imported_realm)

            # Verify for realm imported from other product:
            # * zulip_update_announcements_level = latest level
            # * zulip_update_announcements_stream = gryffindor_common_room - channel with the most subscribers,
            #   with earliest id as tiebreaker.
            # * announcements sent to the channel.
            self.assertEqual(imported_realm.zulip_update_announcements_level, 2)
            self.assertEqual(
                imported_realm.zulip_update_announcements_stream, gryffindor_common_room
            )
            personal_message = Message.objects.filter(
                realm=imported_realm, sender=notification_bot, recipient__type=Recipient.PERSONAL
            ).first()
            assert personal_message is not None
            self.assertIn(
                "Starting tomorrow, users in your organization will receive",
                personal_message.content,
            )

            # Two new updates added.
            new_updates = [
                ZulipUpdateAnnouncement(
                    level=3,
                    message="Announcement message 3.",
                ),
                ZulipUpdateAnnouncement(
                    level=4,
                    message="Announcement message 4.",
                ),
            ]
            self.zulip_update_announcements.extend(new_updates)

            # Wait for 24h before starting to send updates.
            now = timezone_now()
            with time_machine.travel(now + timedelta(hours=23), tick=False):
                send_zulip_update_announcements(skip_delay=False)
            imported_realm.refresh_from_db()
            self.assertEqual(imported_realm.zulip_update_announcements_level, 2)

            # After 24h, send updates.
            with time_machine.travel(now + timedelta(hours=25), tick=False):
                send_zulip_update_announcements(skip_delay=False)
            imported_realm.refresh_from_db()
            self.assertEqual(imported_realm.zulip_update_announcements_level, 4)
            zulip_updates_message_query = Message.objects.filter(
                realm=imported_realm,
                sender=notification_bot,
                recipient__type=Recipient.STREAM,
            )
            self.assertTrue(zulip_updates_message_query.exists())

    def test_send_zulip_update_announcements_new_realm(self) -> None:
        with mock.patch(
            "zerver.lib.zulip_update_announcements.zulip_update_announcements",
            self.zulip_update_announcements,
        ):
            new_realm = do_create_realm(string_id="new_realm", name="new_realm")
            # New realm created is on the latest level.
            self.assertEqual(new_realm.zulip_update_announcements_level, 2)
            assert new_realm.zulip_update_announcements_stream is not None

            # New update added.
            new_updates = [
                ZulipUpdateAnnouncement(
                    level=3,
                    message="Announcement message 3.",
                ),
            ]
            self.zulip_update_announcements.extend(new_updates)

            now = timezone_now()
            with time_machine.travel(now, tick=False):
                send_zulip_update_announcements(skip_delay=False)
            new_realm.refresh_from_db()
            notification_bot = get_system_bot(settings.NOTIFICATION_BOT, new_realm.id)
            stream_messages = Message.objects.filter(
                realm=new_realm,
                sender=notification_bot,
                recipient__type_id=new_realm.zulip_update_announcements_stream.id,
                date_sent__gte=now,
            ).order_by("id")
            # Verify introductory message + update message sent.
            self.assert_length(stream_messages, 2)
            self.assertIn("To help you learn about new features", stream_messages[0].content)
            self.assertEqual(stream_messages[1].content, "Announcement message 3.")
            self.assertEqual(new_realm.zulip_update_announcements_level, 3)

            new_realm.zulip_update_announcements_stream = None
            new_realm.save(update_fields=["zulip_update_announcements_stream"])

            # Another new update added.
            new_updates = [
                ZulipUpdateAnnouncement(
                    level=4,
                    message="Announcement message 4.",
                ),
            ]
            self.zulip_update_announcements.extend(new_updates)

            # Verify update message missed as stream was manually set to None.
            with time_machine.travel(now + timedelta(days=1), tick=False):
                send_zulip_update_announcements(skip_delay=False)
            new_realm.refresh_from_db()
            stream_messages = Message.objects.filter(
                realm=new_realm,
                sender=notification_bot,
                date_sent__gte=now + timedelta(days=1),
            ).order_by("id")
            self.assert_length(stream_messages, 0)
            self.assertEqual(new_realm.zulip_update_announcements_level, 4)
