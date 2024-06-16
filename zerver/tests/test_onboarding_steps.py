from typing_extensions import override

from zerver.actions.create_user import do_create_user
from zerver.actions.onboarding_steps import do_mark_onboarding_step_as_read
from zerver.lib.onboarding_steps import ONE_TIME_NOTICES, get_next_onboarding_steps
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import OnboardingStep
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

    def test_some_done_some_not(self) -> None:
        do_mark_onboarding_step_as_read(self.user, "visibility_policy_banner")
        do_mark_onboarding_step_as_read(self.user, "intro_inbox_view_modal")
        onboarding_steps = get_next_onboarding_steps(self.user)
        self.assert_length(onboarding_steps, 3)
        self.assertEqual(onboarding_steps[0]["name"], "intro_recent_view_modal")
        self.assertEqual(onboarding_steps[1]["name"], "first_stream_created_banner")
        self.assertEqual(onboarding_steps[2]["name"], "jump_to_conversation_banner")

        with self.settings(TUTORIAL_ENABLED=False):
            onboarding_steps = get_next_onboarding_steps(self.user)
        self.assert_length(onboarding_steps, 0)

    def test_all_onboarding_steps_done(self) -> None:
        self.assertNotEqual(get_next_onboarding_steps(self.user), [])

        for one_time_notice in ONE_TIME_NOTICES:  # nocoverage
            do_mark_onboarding_step_as_read(self.user, one_time_notice.name)

        self.assertEqual(get_next_onboarding_steps(self.user), [])


class TestOnboardingSteps(ZulipTestCase):
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
