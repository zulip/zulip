from typing import TYPE_CHECKING

import orjson

from zerver.actions.direct_message_groups import do_set_direct_message_group_pin
from zerver.lib.message import get_recent_private_conversations
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Subscription, UserProfile
from zerver.models.recipients import get_direct_message_group

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class DirectMessageConversationPinTest(ZulipTestCase):
    def get_subscription(
        self, user_profile: UserProfile, other_user_ids: list[int]
    ) -> Subscription:
        direct_message_group = get_direct_message_group(sorted({user_profile.id, *other_user_ids}))
        assert direct_message_group is not None
        return Subscription.objects.get(
            user_profile=user_profile, recipient=direct_message_group.recipient
        )

    def pin(self, user_ids: list[int], pinned: bool) -> "TestHttpResponse":
        return self.client_post(
            "/json/users/me/dm_conversations/pin",
            {
                "user_ids": orjson.dumps(user_ids).decode(),
                "pinned": orjson.dumps(pinned).decode(),
            },
        )

    def test_pin_and_unpin_direct_message_conversation(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.login("hamlet")
        self.send_personal_message(hamlet, cordelia)

        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.pin([cordelia.id], True)
        self.assert_json_success(result)

        self.assertEqual(events[0]["event"]["type"], "direct_message_conversation")
        self.assertEqual(events[0]["event"]["user_ids"], [cordelia.id])
        self.assertTrue(events[0]["event"]["pinned"])
        self.assertEqual(events[0]["users"], [hamlet.id])

        self.assertTrue(self.get_subscription(hamlet, [cordelia.id]).pin_to_top)
        recent = get_recent_private_conversations(hamlet)
        self.assertTrue(recent[frozenset([cordelia.id])]["pinned"])

        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.pin([cordelia.id], False)
        self.assert_json_success(result)
        self.assertFalse(events[0]["event"]["pinned"])
        self.assertFalse(self.get_subscription(hamlet, [cordelia.id]).pin_to_top)
        recent = get_recent_private_conversations(hamlet)
        self.assertFalse(recent[frozenset([cordelia.id])]["pinned"])

    def test_pin_is_idempotent(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.login("hamlet")
        self.send_personal_message(hamlet, cordelia)
        do_set_direct_message_group_pin(hamlet, [cordelia.id], pinned=True)

        # Pinning an already-pinned conversation is a no-op that sends no event.
        with self.capture_send_event_calls(expected_num_events=0):
            result = self.pin([cordelia.id], True)
        self.assert_json_success(result)

    def test_pin_group_direct_message_conversation(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        self.login("hamlet")
        self.send_group_direct_message(hamlet, [cordelia, othello])

        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.pin([cordelia.id, othello.id], True)
        self.assert_json_success(result)
        self.assertEqual(
            sorted(events[0]["event"]["user_ids"]), sorted([cordelia.id, othello.id])
        )
        self.assertTrue(self.get_subscription(hamlet, [cordelia.id, othello.id]).pin_to_top)

    def test_pin_self_direct_message_conversation(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")
        self.send_personal_message(hamlet, hamlet)

        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.pin([], True)
        self.assert_json_success(result)
        self.assertEqual(events[0]["event"]["user_ids"], [])
        self.assertTrue(self.get_subscription(hamlet, []).pin_to_top)

    def test_pin_nonexistent_conversation(self) -> None:
        othello = self.example_user("othello")
        self.login("hamlet")
        # Hamlet and Othello have never had a direct message conversation.
        result = self.pin([othello.id], True)
        self.assert_json_error(result, "No such direct message conversation.")
