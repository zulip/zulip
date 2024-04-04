from typing_extensions import override

from zerver.actions.create_user import do_create_user
from zerver.actions.hotspots import do_mark_onboarding_step_as_read
from zerver.lib.hotspots import (
    ALL_HOTSPOTS,
    INTRO_HOTSPOTS,
    NON_INTRO_HOTSPOTS,
    ONE_TIME_NOTICES,
    get_next_onboarding_steps,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import OnboardingStep, UserProfile
from zerver.models.realms import get_realm


# Splitting this out, since I imagine this will eventually have most of the
# complicated onboarding steps logic.
class TestGetNextOnboardingSteps(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = do_create_user(
            "user@zulip.com", "password", get_realm("zulip"), "user", acting_user=None
        )

    def test_first_hotspot(self) -> None:
        for hotspot in NON_INTRO_HOTSPOTS:  # nocoverage
            do_mark_onboarding_step_as_read(self.user, hotspot.name)

        for one_time_notice in ONE_TIME_NOTICES:  # nocoverage
            do_mark_onboarding_step_as_read(self.user, one_time_notice.name)

        hotspots = get_next_onboarding_steps(self.user)
        self.assert_length(hotspots, 1)
        self.assertEqual(hotspots[0]["name"], "intro_streams")

    def test_some_done_some_not(self) -> None:
        do_mark_onboarding_step_as_read(self.user, "intro_streams")
        do_mark_onboarding_step_as_read(self.user, "intro_compose")
        onboarding_steps = get_next_onboarding_steps(self.user)
        self.assert_length(onboarding_steps, 5)
        self.assertEqual(onboarding_steps[0]["name"], "visibility_policy_banner")
        self.assertEqual(onboarding_steps[1]["name"], "intro_inbox_view_modal")
        self.assertEqual(onboarding_steps[2]["name"], "intro_recent_view_modal")
        self.assertEqual(onboarding_steps[3]["name"], "first_stream_created_banner")
        self.assertEqual(onboarding_steps[4]["name"], "intro_topics")

    def test_all_onboarding_steps_done(self) -> None:
        with self.settings(TUTORIAL_ENABLED=True):
            self.assertNotEqual(self.user.tutorial_status, UserProfile.TUTORIAL_FINISHED)
            for hotspot in NON_INTRO_HOTSPOTS:  # nocoverage
                do_mark_onboarding_step_as_read(self.user, hotspot.name)

            self.assertNotEqual(self.user.tutorial_status, UserProfile.TUTORIAL_FINISHED)
            for one_time_notice in ONE_TIME_NOTICES:  # nocoverage
                do_mark_onboarding_step_as_read(self.user, one_time_notice.name)

            self.assertNotEqual(self.user.tutorial_status, UserProfile.TUTORIAL_FINISHED)
            for hotspot in INTRO_HOTSPOTS:
                do_mark_onboarding_step_as_read(self.user, hotspot.name)

            self.assertEqual(self.user.tutorial_status, UserProfile.TUTORIAL_FINISHED)
            self.assertEqual(get_next_onboarding_steps(self.user), [])

    def test_send_all_hotspots(self) -> None:
        with self.settings(DEVELOPMENT=True, ALWAYS_SEND_ALL_HOTSPOTS=True):
            self.assert_length(ALL_HOTSPOTS, len(get_next_onboarding_steps(self.user)))

    def test_tutorial_disabled(self) -> None:
        with self.settings(TUTORIAL_ENABLED=False):
            self.assertEqual(get_next_onboarding_steps(self.user), [])


class TestOnboardingSteps(ZulipTestCase):
    def test_do_mark_onboarding_step_as_read(self) -> None:
        user = self.example_user("hamlet")
        do_mark_onboarding_step_as_read(user, "intro_compose")
        self.assertEqual(
            list(
                OnboardingStep.objects.filter(user=user).values_list("onboarding_step", flat=True)
            ),
            ["intro_compose"],
        )

    def test_onboarding_steps_url_endpoint(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        result = self.client_post(
            "/json/users/me/onboarding_steps", {"onboarding_step": "intro_streams"}
        )
        self.assert_json_success(result)
        self.assertEqual(
            list(
                OnboardingStep.objects.filter(user=user).values_list("onboarding_step", flat=True)
            ),
            ["intro_streams"],
        )

        result = self.client_post("/json/users/me/onboarding_steps", {"onboarding_step": "invalid"})
        self.assert_json_error(result, "Unknown onboarding_step: invalid")
        self.assertEqual(
            list(
                OnboardingStep.objects.filter(user=user).values_list("onboarding_step", flat=True)
            ),
            ["intro_streams"],
        )
