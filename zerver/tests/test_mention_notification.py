from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import mock

import orjson
from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils.timezone import now as timezone_now

from zerver.actions.mention_notification import notify_unsubscribed_mention
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTestCase, ZulipTransactionTestCase
from zerver.lib.test_helpers import make_client
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message, Recipient, Subscription, UserMessage, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.messages import MentionNotification
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot


class MentionNotificationTest(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor = self.example_user("hamlet")
        self.target = self.example_user("othello")
        self.stream = self.make_stream("mention-notification")
        self.subscribe(self.actor, self.stream.name)
        self.login_user(self.actor)

    def send(self, *, notify: bool = True, content: str | None = None) -> int:
        data = {
            "type": "stream",
            "to": orjson.dumps([self.stream.id]).decode(),
            "topic": "CoreX",
            "content": content or f"Hello @**|{self.target.id}**",
        }
        if notify:
            data["notify_mentioned_user_ids"] = orjson.dumps([self.target.id]).decode()
        result = self.client_post("/json/messages", data)
        return self.assert_json_success(result)["id"]

    def bot_messages(self) -> list[Message]:
        bot = get_system_bot(settings.NOTIFICATION_BOT, self.actor.realm_id)
        return list(Message.objects.filter(sender=bot).order_by("id"))

    def test_explicit_delivery_and_retry(self) -> None:
        before = list(Subscription.objects.filter(user_profile=self.target).values())
        bot_before = len(self.bot_messages())
        message_id = self.send()
        self.assertEqual(len(self.bot_messages()), bot_before + 1)
        dm = self.bot_messages()[-1]
        self.assertEqual(dm.recipient.type, Recipient.PERSONAL)
        self.assertTrue(UserMessage.objects.filter(message=dm, user_profile=self.target).exists())
        self.assertIn(f"/near/{message_id}", dm.content)
        self.assertIn("Hello", dm.content)
        self.assertIn("quote", dm.content)
        self.assertIn("mention-notification", dm.content)
        self.assertFalse(notify_unsubscribed_mention(self.actor, message_id, self.target.id))
        self.assertEqual(len(self.bot_messages()), bot_before + 1)
        self.assertEqual(
            before, list(Subscription.objects.filter(user_profile=self.target).values())
        )

    def test_no_consent_and_no_actual_mention(self) -> None:
        before = len(self.bot_messages())
        self.send(notify=False)
        self.send(content="No mention")
        self.send(content=f"`@**|{self.target.id}**`")
        self.send(content=f"@_**|{self.target.id}**")
        self.assertEqual(len(self.bot_messages()), before)
        self.assertEqual(MentionNotification.objects.count(), 0)

    def test_ineligible_recipients(self) -> None:
        message_id = self.send(notify=False)
        before = len(self.bot_messages())
        for recipient_id in [-1, self.example_user("cordelia").id, self.mit_user("sipbtest").id]:
            self.assertFalse(notify_unsubscribed_mention(self.actor, message_id, recipient_id))
        self.subscribe(self.target, self.stream.name)
        self.assertFalse(notify_unsubscribed_mention(self.actor, message_id, self.target.id))
        self.unsubscribe(self.target, self.stream.name)
        UserProfile.objects.filter(id=self.target.id).update(is_active=False)
        self.assertFalse(notify_unsubscribed_mention(self.actor, message_id, self.target.id))
        UserProfile.objects.filter(id=self.target.id).update(
            is_active=True, role=UserProfile.ROLE_GUEST
        )
        self.assertFalse(notify_unsubscribed_mention(self.actor, message_id, self.target.id))
        self.assertEqual(len(self.bot_messages()), before)

    def test_private_channel_and_revoked_access(self) -> None:
        message_id = self.send(notify=False)
        self.stream.invite_only = True
        self.stream.save(update_fields=["invite_only"])
        self.assertFalse(notify_unsubscribed_mention(self.actor, message_id, self.target.id))
        with self.assertRaises(JsonableError):
            notify_unsubscribed_mention(self.target, message_id, self.actor.id)

    def test_private_joinable_channel_and_web_public_channel(self) -> None:
        self.stream.invite_only = True
        self.stream.can_subscribe_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.actor.realm_id
        )
        self.stream.save(update_fields=["invite_only", "can_subscribe_group"])
        message_id = self.send()
        self.assertTrue(MentionNotification.objects.filter(message_id=message_id).exists())
        self.stream.invite_only = False
        self.stream.is_web_public = True
        self.stream.save(update_fields=["invite_only", "is_web_public"])
        second_message_id = self.send()
        self.assertNotEqual(message_id, second_message_id)
        self.assertTrue(MentionNotification.objects.filter(message_id=second_message_id).exists())

    def test_subscribed_mention_keeps_ordinary_delivery(self) -> None:
        self.subscribe(self.target, self.stream.name)
        before = len(self.bot_messages())
        message_id = self.send()
        receipt = UserMessage.objects.get(user_profile=self.target, message_id=message_id)
        self.assertTrue(receipt.flags.mentioned)
        self.assertEqual(len(self.bot_messages()), before)

    def test_permission_revoked_between_send_and_delivery(self) -> None:
        before = len(self.bot_messages())

        def revoke_and_deliver(actor: UserProfile, message_id: int, recipient_id: int) -> bool:
            self.stream.invite_only = True
            self.stream.save(update_fields=["invite_only"])
            return notify_unsubscribed_mention(actor, message_id, recipient_id)

        with mock.patch(
            "zerver.views.message_send.notify_unsubscribed_mention", side_effect=revoke_and_deliver
        ):
            message_id = self.send()
        self.assertTrue(Message.objects.filter(id=message_id).exists())
        self.assertEqual(len(self.bot_messages()), before)
        self.assertEqual(MentionNotification.objects.count(), 0)

    def test_rollback_includes_original_and_dm(self) -> None:
        before = Message.objects.count()
        with self.assertRaisesRegex(RuntimeError, "rollback"), transaction.atomic():
            self.send()
            raise RuntimeError("rollback")
        self.assertEqual(Message.objects.count(), before)
        self.assertEqual(MentionNotification.objects.count(), 0)

    def test_failed_delivery_rolls_back_original(self) -> None:
        before = Message.objects.count()
        with (
            mock.patch(
                "zerver.actions.mention_notification.internal_send_private_message",
                side_effect=RuntimeError("delivery failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "delivery failed"),
        ):
            self.send()
        self.assertEqual(Message.objects.count(), before)
        self.assertEqual(MentionNotification.objects.count(), 0)


class MentionNotificationConcurrencyTest(ZulipTransactionTestCase):
    def test_concurrent_delivery(self) -> None:
        actor = self.example_user("hamlet")
        target = self.example_user("othello")
        stream = get_stream("Denmark", actor.realm)
        # This original is persisted independently of either delivery transaction.
        message = Message.objects.create(
            sender=actor,
            recipient_id=stream.recipient_id,
            realm=actor.realm,
            content=f"Hello @**|{target.id}**",
            subject="CoreX concurrency",
            sending_client=make_client("test suite"),
            date_sent=timezone_now(),
        )
        subscription, subscription_created = Subscription.objects.get_or_create(
            user_profile=target, recipient_id=stream.recipient_id, defaults={"active": False}
        )
        was_active = subscription.active
        subscription.active = False
        subscription.save(update_fields=["active"])
        before = set(Message.objects.values_list("id", flat=True))
        barrier = Barrier(2)

        def deliver() -> bool:
            close_old_connections()
            try:
                worker_actor = UserProfile.objects.get(id=actor.id)
                barrier.wait(timeout=10)
                return notify_unsubscribed_mention(worker_actor, message.id, target.id)
            finally:
                close_old_connections()

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(deliver) for _ in range(2)]
                self.assertEqual(
                    sorted(future.result(timeout=30) for future in futures), [False, True]
                )
            self.assertEqual(MentionNotification.objects.filter(message=message).count(), 1)
            self.assertEqual(Message.objects.exclude(id__in=before).count(), 1)
        finally:
            Message.objects.exclude(id__in=before - {message.id}).delete()
            subscription.active = was_active
            if subscription_created:
                subscription.delete()
            else:
                subscription.save(update_fields=["active"])
