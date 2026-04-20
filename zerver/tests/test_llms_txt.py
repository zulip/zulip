from zerver.actions.realm_settings import do_set_realm_property
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realms import get_realm


class LlmsTxtTest(ZulipTestCase):
    def test_llms_txt_with_web_public_streams(self) -> None:
        """
        GET /llms.txt returns 200 with text/plain content when the realm
        has web-public streams enabled and at least one web-public channel exists.
        """
        realm = get_realm("zulip")
        do_set_realm_property(realm, "enable_spectator_access", True, acting_user=None)
        # "Rome" is a web-public stream in the test fixtures.
        result = self.client_get("/llms.txt")
        self.assertEqual(result.status_code, 200)
        self.assertIn("text/plain", result["Content-Type"])
        content = result.content.decode()
        # Should mention the API endpoint
        self.assertIn("/json/messages", content)
        # Should mention the required narrow operator
        self.assertIn("channels", content)
        self.assertIn("web-public", content)
        # Should list the web-public channel available in test fixtures
        self.assertIn("Rome", content)
        # Should follow llms.txt format (starts with # heading)
        self.assertTrue(content.startswith("#"))

    def test_llms_txt_spectator_access_disabled(self) -> None:
        """
        GET /llms.txt returns 404 when spectator access is disabled.
        """
        realm = get_realm("zulip")
        do_set_realm_property(realm, "enable_spectator_access", False, acting_user=None)
        result = self.client_get("/llms.txt")
        self.assertEqual(result.status_code, 404)

    def test_llms_txt_no_web_public_streams(self) -> None:
        """
        GET /llms.txt returns 404 when spectator access is enabled but there
        are no web-public channels in the realm.
        """
        from zerver.models.streams import Stream

        realm = get_realm("zulip")
        do_set_realm_property(realm, "enable_spectator_access", True, acting_user=None)
        # Mark all previously web-public streams as not web-public.
        Stream.objects.filter(realm=realm, is_web_public=True).update(is_web_public=False)
        result = self.client_get("/llms.txt")
        self.assertEqual(result.status_code, 404)

    def test_llms_txt_lists_only_web_public_channels(self) -> None:
        """
        /llms.txt lists web-public channels but not private or regular public channels.
        """
        realm = get_realm("zulip")
        do_set_realm_property(realm, "enable_spectator_access", True, acting_user=None)

        result = self.client_get("/llms.txt")
        self.assertEqual(result.status_code, 200)
        content = result.content.decode()

        # "Rome" is web-public in test fixtures — should be listed.
        self.assertIn("Rome", content)
        # "Scotland" is a private stream — should NOT be listed.
        self.assertNotIn("Scotland", content)
