from datetime import timedelta
from unittest import mock

import time_machine
from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.zulip_update_announcements import (
    ZulipUpdateAnnouncement,
    send_zulip_update_announcements,
)
from zerver.models.messages import Message
from zerver.models.realms import get_realm
from zerver.models.recipients import Recipient, get_huddle_user_ids
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot

test_zulip_update_announcements = [
    ZulipUpdateAnnouncement(
        level=1,
        message="Announcement message 1.",
    ),
    ZulipUpdateAnnouncement(
        level=2,
        message="Announcement message 2.",
    ),
]


class ZulipUpdateAnnouncementsTest(ZulipTestCase):
    @mock.patch(
        "zerver.lib.zulip_update_announcements.zulip_update_announcements",
        test_zulip_update_announcements,
    )
    def test_send_zulip_update_announcements(self) -> None:
        realm = get_realm("zulip")

        # realm predates the "zulip updates" feature with the
        # zulip_update_announcements_stream set to None.
        realm.zulip_update_announcements_level = None
        realm.zulip_update_announcements_stream = None
        realm.save(
            update_fields=["zulip_update_announcements_level", "zulip_update_announcements_stream"]
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
            send_zulip_update_announcements()

        realm.refresh_from_db()
        group_direct_message = group_direct_messages.first()
        assert group_direct_message is not None
        self.assertEqual(group_direct_message.sender, notification_bot)
        self.assertEqual(group_direct_message.date_sent, now)
        self.assertEqual(
            set(get_huddle_user_ids(group_direct_message.recipient)),
            expected_group_direct_message_user_ids,
        )
        self.assertEqual(realm.zulip_update_announcements_level, 0)
        self.assertIn(
            "These notifications are currently turned off in your organization.",
            group_direct_message.content,
        )

        # Wait for one week before starting to skip sending updates.
        with time_machine.travel(now + timedelta(days=2), tick=False):
            send_zulip_update_announcements()
        realm.refresh_from_db()
        self.assertEqual(realm.zulip_update_announcements_level, 0)

        with time_machine.travel(now + timedelta(days=8), tick=False):
            send_zulip_update_announcements()
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
        test_zulip_update_announcements.extend(new_updates)

        # verify zulip update announcements sent to configured stream.
        with time_machine.travel(now + timedelta(days=10), tick=False):
            send_zulip_update_announcements()
        realm.refresh_from_db()
        stream_messages = Message.objects.filter(
            realm=realm,
            sender=notification_bot,
            recipient__type_id=verona.id,
            date_sent__gte=now + timedelta(days=10),
        ).order_by("id")
        self.assert_length(stream_messages, 2)
        self.assertEqual(stream_messages[0].content, "Announcement message 3.")
        self.assertEqual(stream_messages[1].content, "Announcement message 4.")
        self.assertEqual(realm.zulip_update_announcements_level, 4)

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
            send_zulip_update_announcements()

        realm.refresh_from_db()
        group_direct_message = group_direct_messages.first()
        assert group_direct_message is not None
        self.assertEqual(group_direct_message.sender, notification_bot)
        self.assertEqual(group_direct_message.date_sent, now)
        self.assertEqual(
            set(get_huddle_user_ids(group_direct_message.recipient)),
            expected_group_direct_message_user_ids,
        )
        self.assertEqual(realm.zulip_update_announcements_level, 0)
        self.assertIn(
            "Users in your organization will now receive "
            "[updates](/help/configure-automated-notices#zulip-update-announcements) about new Zulip features in "
            f"#**{realm.zulip_update_announcements_stream}>{realm.ZULIP_UPDATE_ANNOUNCEMENTS_TOPIC_NAME}**",
            group_direct_message.content,
        )
