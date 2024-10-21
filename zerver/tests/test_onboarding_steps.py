from datetime import timedelta

import time_machine
from django.conf import settings
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.create_user import do_create_user
from zerver.actions.onboarding_steps import do_mark_onboarding_step_as_read
from zerver.lib.onboarding_steps import ALL_ONBOARDING_STEPS, get_next_onboarding_steps
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import OnboardingStep, ScheduledMessage
from zerver.models.realms import get_realm
from zerver.models.users import get_system_bot


# Splitting this out, since I imagine this will eventually have most of the
# complicated onboarding steps logic.
class TestGetNextOnboardingSteps(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = do_create_user(
            "user@zulip.com", "password", get_realm("zulip"), "user", acting_user=None
        )

    def test_some_done_some_not(self) -> None:
        # "visibility_policy_banner" is already marked as read for a new user.
        onboarding_step = OnboardingStep.objects.get(user=self.user)
        self.assertEqual(onboarding_step.onboarding_step, "visibility_policy_banner")

        do_mark_onboarding_step_as_read(self.user, "intro_inbox_view_modal")
        onboarding_steps = get_next_onboarding_steps(self.user)
        self.assert_length(onboarding_steps, 8)
        self.assertEqual(onboarding_steps[0]["name"], "intro_recent_view_modal")
        self.assertEqual(onboarding_steps[1]["name"], "first_stream_created_banner")
        self.assertEqual(onboarding_steps[2]["name"], "jump_to_conversation_banner")
        self.assertEqual(onboarding_steps[3]["name"], "non_interleaved_view_messages_fading")
        self.assertEqual(onboarding_steps[4]["name"], "interleaved_view_messages_fading")
        self.assertEqual(onboarding_steps[5]["name"], "intro_resolve_topic")
        self.assertEqual(onboarding_steps[6]["name"], "navigation_tour_video")
        self.assertEqual(onboarding_steps[7]["name"], "narrow_to_dm_with_welcome_bot_new_user")

        with self.settings(TUTORIAL_ENABLED=False):
            onboarding_steps = get_next_onboarding_steps(self.user)
        self.assert_length(onboarding_steps, 0)

        with self.settings(NAVIGATION_TOUR_VIDEO_URL=None):
            onboarding_steps = get_next_onboarding_steps(self.user)
        self.assertNotIn("navigation_tour_video", onboarding_steps)

    def test_all_onboarding_steps_done(self) -> None:
        self.assertNotEqual(get_next_onboarding_steps(self.user), [])

        for onboarding_step in ALL_ONBOARDING_STEPS:  # nocoverage
            do_mark_onboarding_step_as_read(self.user, onboarding_step.name)

        self.assertEqual(get_next_onboarding_steps(self.user), [])


class TestOnboardingSteps(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        OnboardingStep.objects.filter(user=self.example_user("hamlet")).delete()

    def test_do_mark_onboarding_step_as_read(self) -> None:
        user = self.example_user("hamlet")
        do_mark_onboarding_step_as_read(user, "intro_inbox_view_modal")
        self.assertEqual(
            list(
                OnboardingStep.objects.filter(user=user).values_list("onboarding_step", flat=True)
            ),
            ["intro_inbox_view_modal"],
        )

    def test_onboarding_steps_url_endpoint(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        result = self.client_post(
            "/json/users/me/onboarding_steps", {"onboarding_step": "intro_recent_view_modal"}
        )
        self.assert_json_success(result)
        self.assertEqual(
            list(
                OnboardingStep.objects.filter(user=user).values_list("onboarding_step", flat=True)
            ),
            ["intro_recent_view_modal"],
        )

        result = self.client_post("/json/users/me/onboarding_steps", {"onboarding_step": "invalid"})
        self.assert_json_error(result, "Unknown onboarding_step: invalid")
        self.assertEqual(
            list(
                OnboardingStep.objects.filter(user=user).values_list("onboarding_step", flat=True)
            ),
            ["intro_recent_view_modal"],
        )

    def test_schedule_navigation_tour_video_reminder(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        now = timezone_now()
        with time_machine.travel(now, tick=False):
            result = self.client_post(
                "/json/users/me/onboarding_steps",
                {
                    "onboarding_step": "navigation_tour_video",
                    "schedule_navigation_tour_video_reminder_delay": 30,
                },
            )
        self.assert_json_success(result)
        self.assertEqual(
            list(
                OnboardingStep.objects.filter(user=user).values_list("onboarding_step", flat=True)
            ),
            ["navigation_tour_video"],
        )
        scheduled_message = ScheduledMessage.objects.last()
        assert scheduled_message is not None
        expected_scheduled_timestamp = now + timedelta(seconds=30)
        self.assertEqual(scheduled_message.scheduled_timestamp, expected_scheduled_timestamp)
        self.assertEqual(
            scheduled_message.sender.id, get_system_bot(settings.WELCOME_BOT, user.realm_id).id
        )
        self.assertIn("Welcome to Zulip video", scheduled_message.content)
