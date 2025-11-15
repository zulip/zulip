from zerver.actions.create_user import do_create_user
from zerver.lib.avatar import avatar_url
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realms import get_realm


class TestJdenticonAvatar(ZulipTestCase):
    def test_jdenticon_endpoint(self) -> None:
        seed = "abc123"
        response = self.client_get(f"/avatar/jdenticon/{seed}/80")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/svg+xml")
        self.assertIn("<svg", response.content.decode())


class TestDefaultAvatarSetting(ZulipTestCase):
    def test_default_avatar_jdenticon(self) -> None:
        realm = get_realm("zulip")
        realm.default_new_user_avatar = "jdenticon"
        realm.save()

        user = do_create_user(
            email="jdenticon@example.com",
            password="test",
            realm=realm,
            full_name="Test",
            acting_user=None,
        )

        url = avatar_url(user)
        assert url is not None
        self.assertIn("jdenticon", url)

    def test_default_avatar_gravatar(self) -> None:
        realm = get_realm("zulip")
        realm.default_new_user_avatar = "gravatar"
        realm.save()

        user = do_create_user(
            email="gravtest@example.com",
            password="test",
            realm=realm,
            full_name="Test",
            acting_user=None,
        )

        url = avatar_url(user)
        assert url is not None
        self.assertIn("gravatar", url)

    def test_default_avatar_silhouette(self) -> None:
        realm = get_realm("zulip")
        realm.default_new_user_avatar = "colorful_silhouette"
        realm.save()

        user = do_create_user(
            email="color@example.com",
            password="test",
            realm=realm,
            full_name="Test",
            acting_user=None,
        )

        url = avatar_url(user)
        assert url is not None
        self.assertIn("silhouette", url)
