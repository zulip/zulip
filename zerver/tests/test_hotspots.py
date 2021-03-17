from zerver.lib.actions import do_create_user, do_mark_hotspot_as_read
from zerver.lib.hotspots import ALL_HOTSPOTS, INTRO_HOTSPOTS, NON_INTRO_HOTSPOTS, get_next_hotspots
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
        self.assertEqual(len(hotspots), 2)
        self.assertEqual(hotspots[0]["name"], "intro_draft")
        self.assertEqual(hotspots[1]["name"], "intro_reply")

    def test_some_done_some_not(self) -> None:
        do_mark_hotspot_as_read(self.user, "intro_reply")
        do_mark_hotspot_as_read(self.user, "intro_compose")
        do_mark_hotspot_as_read(self.user, "intro_draft")
        hotspots = get_next_hotspots(self.user)
        self.assertEqual(len(hotspots), 1)
        self.assertEqual(hotspots[0]["name"], "intro_streams")

    def test_all_hotspots_done(self) -> None:
        with self.settings(TUTORIAL_ENABLED=True):
            self.assertNotEqual(self.user.tutorial_status, UserProfile.TUTORIAL_FINISHED)
            for hotspot in INTRO_HOTSPOTS:
                do_mark_hotspot_as_read(self.user, hotspot)
            self.assertEqual(len(get_next_hotspots(self.user)), len(NON_INTRO_HOTSPOTS))

            for hotspot in NON_INTRO_HOTSPOTS:
                do_mark_hotspot_as_read(self.user, hotspot)

            self.assertEqual(self.user.tutorial_status, UserProfile.TUTORIAL_FINISHED)
            self.assertEqual(get_next_hotspots(self.user), [])

    def test_send_all(self) -> None:
        with self.settings(DEVELOPMENT=True, ALWAYS_SEND_ALL_HOTSPOTS=True):
            self.assertEqual(len(ALL_HOTSPOTS), len(get_next_hotspots(self.user)))

    def test_tutorial_disabled(self) -> None:
        with self.settings(TUTORIAL_ENABLED=False):
            self.assertEqual(get_next_hotspots(self.user), [])


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
