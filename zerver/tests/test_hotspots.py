from zerver.lib.actions import do_create_realm, do_create_user, do_mark_hotspot_as_read
from zerver.lib.hotspots import ALL_HOTSPOTS, INTRO_HOTSPOTS, get_next_hotspots
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserHotspot, UserProfile, get_realm


# Splitting this out, since I imagine this will eventually have most of the
# complicated hotspots logic.
class TestGetNextHotspots(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = do_create_user(
            "user@zulip.com", "password", get_realm("zulip"), "user", acting_user=None
        )

    def test_first_hotspot(self) -> None:
        hotspots = get_next_hotspots(self.user)
        self.assert_length(hotspots, 1)
        self.assertEqual(hotspots[0]["name"], "intro_reply")

    def test_some_done_some_not(self) -> None:
        do_mark_hotspot_as_read(self.user, "intro_reply")
        do_mark_hotspot_as_read(self.user, "intro_compose")
        hotspots = get_next_hotspots(self.user)
        self.assert_length(hotspots, 1)
        self.assertEqual(hotspots[0]["name"], "intro_streams")

    def test_all_intro_hotspots_done(self) -> None:
        with self.settings(TUTORIAL_ENABLED=True):
            self.assertNotEqual(self.user.tutorial_status, UserProfile.TUTORIAL_FINISHED)
            for hotspot in INTRO_HOTSPOTS:
                do_mark_hotspot_as_read(self.user, hotspot)
            self.assertEqual(self.user.tutorial_status, UserProfile.TUTORIAL_FINISHED)
            self.assertEqual(get_next_hotspots(self.user), [])

    def test_send_all(self) -> None:
        with self.settings(DEVELOPMENT=True, ALWAYS_SEND_ALL_HOTSPOTS=True):
            self.assert_length(ALL_HOTSPOTS, len(get_next_hotspots(self.user)))

    def test_tutorial_disabled(self) -> None:
        with self.settings(TUTORIAL_ENABLED=False):
            self.assertEqual(get_next_hotspots(self.user), [])

    def test_three_users_with_same_email_all_done(self) -> None:
        for hotspot in ALL_HOTSPOTS:
            do_mark_hotspot_as_read(self.user, hotspot)

        self.assertEqual(get_next_hotspots(self.user), [])

        user_in_red = do_create_user(
            self.user.delivery_email,
            "password",
            do_create_realm("red", "red"),
            "user",
            acting_user=None,
        )

        user_in_blue = do_create_user(
            self.user.delivery_email,
            "password",
            do_create_realm("blue", "blue"),
            "user",
            acting_user=None,
        )

        self.assertEqual(get_next_hotspots(user_in_red), [])
        self.assertEqual(get_next_hotspots(user_in_blue), [])

    def test_three_users_with_same_email_some_done_some_not(self) -> None:
        for hotspot in ["intro_reply", "intro_streams"]:
            do_mark_hotspot_as_read(self.user, hotspot)

        hotspots = get_next_hotspots(self.user)
        self.assert_length(hotspots, 1)
        self.assertEqual(hotspots[0]["name"], "intro_topics")

        user_in_red = do_create_user(
            self.user.delivery_email,
            "password",
            do_create_realm("red", "red"),
            "user",
            acting_user=None,
        )

        user_in_blue = do_create_user(
            self.user.delivery_email,
            "password",
            do_create_realm("blue", "blue"),
            "user",
            acting_user=None,
        )

        hotspots = get_next_hotspots(user_in_red)
        self.assert_length(hotspots, 1)
        self.assertEqual(hotspots[0]["name"], "intro_topics")

        hotspots = get_next_hotspots(user_in_blue)
        self.assert_length(hotspots, 1)
        self.assertEqual(hotspots[0]["name"], "intro_topics")

        do_mark_hotspot_as_read(user_in_red, "intro_topics")

        hotspots = get_next_hotspots(self.user)
        self.assert_length(hotspots, 1)
        self.assertEqual(hotspots[0]["name"], "intro_gear")

        hotspots = get_next_hotspots(user_in_red)
        self.assert_length(hotspots, 1)
        self.assertEqual(hotspots[0]["name"], "intro_gear")

        hotspots = get_next_hotspots(user_in_blue)
        self.assert_length(hotspots, 1)
        self.assertEqual(hotspots[0]["name"], "intro_gear")


class TestHotspots(ZulipTestCase):
    def test_do_mark_hotspot_as_read(self) -> None:
        user = self.example_user("hamlet")
        do_mark_hotspot_as_read(user, "intro_compose")
        self.assertEqual(
            list(UserHotspot.objects.filter(user=user).values_list("hotspot", flat=True)),
            ["intro_compose"],
        )

    def test_hotspots_url_endpoint(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        result = self.client_post("/json/users/me/hotspots", {"hotspot": "intro_reply"})
        self.assert_json_success(result)
        self.assertEqual(
            list(UserHotspot.objects.filter(user=user).values_list("hotspot", flat=True)),
            ["intro_reply"],
        )

        result = self.client_post("/json/users/me/hotspots", {"hotspot": "invalid"})
        self.assert_json_error(result, "Unknown hotspot: invalid")
        self.assertEqual(
            list(UserHotspot.objects.filter(user=user).values_list("hotspot", flat=True)),
            ["intro_reply"],
        )
