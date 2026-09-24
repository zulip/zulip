from django.conf import settings
from oauth2_provider.models import Application, get_application_model

from zerver.actions.users import change_user_is_active
from zerver.lib.oauth2 import ZulipAuthorizationView
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock


class OAuthApplicationFormTest(ZulipTestCase):
    def test_register_page_fixes_grant_type_as_disabled_field(self) -> None:
        self.login("iago")
        result = self.client_get("/o/applications/register/")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Register a new application", result)
        self.assert_in_response("authorization_grant_type", result)
        self.assert_in_response("Authorization code", result)
        content = result.content.decode()
        self.assertNotIn("hash_client_secret", content)
        self.assertNotIn("post_logout_redirect_uris", content)
        self.assertNotIn("allowed_origins", content)
        self.assertNotIn("algorithm", content)
        # Other grant types must not be offered as choices.
        self.assertNotIn("Device Code", content)
        self.assertNotIn("Resource owner password-based", content)
        self.assertNotIn("Client credentials", content)
        self.assertNotIn("Implicit", content)
        self.assertNotIn("OpenID connect hybrid", content)

    def test_register_ignores_tampered_grant_type(self) -> None:
        """Disabled fields are not taken from POST; value stays authorization code."""
        self.login("iago")
        ApplicationModel = get_application_model()
        before_count = ApplicationModel.objects.count()

        result = self.client_post(
            "/o/applications/register/",
            {
                "name": "Tampered Grant App",
                "client_id": "test-client-id-password-grant",
                "client_secret": "test-client-secret",
                "client_type": Application.CLIENT_CONFIDENTIAL,
                # Client tries to force password grant; disabled field ignores this.
                "authorization_grant_type": Application.GRANT_PASSWORD,
                "redirect_uris": "http://127.0.0.1:8000/callback",
            },
        )

        self.assertEqual(result.status_code, 302)
        self.assertEqual(ApplicationModel.objects.count(), before_count + 1)
        app = ApplicationModel.objects.get(name="Tampered Grant App")
        self.assertEqual(app.authorization_grant_type, Application.GRANT_AUTHORIZATION_CODE)

    def test_register_accepts_authorization_code_grant(self) -> None:
        self.login("iago")
        ApplicationModel = get_application_model()
        before_count = ApplicationModel.objects.count()
        iago = self.example_user("iago")

        result = self.client_post(
            "/o/applications/register/",
            {
                "name": "Auth Code App",
                "client_id": "test-client-id-auth-code",
                "client_secret": "test-client-secret",
                "client_type": Application.CLIENT_CONFIDENTIAL,
                # Omitted on purpose: disabled fields are not submitted by browsers.
                "redirect_uris": "http://127.0.0.1:8000/callback",
            },
        )

        self.assertEqual(result.status_code, 302)
        self.assertEqual(ApplicationModel.objects.count(), before_count + 1)
        app = ApplicationModel.objects.get(name="Auth Code App")
        self.assertEqual(app.authorization_grant_type, Application.GRANT_AUTHORIZATION_CODE)
        self.assertEqual(app.user_id, iago.id)

    def _create_iago_application(self) -> Application:
        return Application.objects.create(
            name="Iago App",
            user=self.example_user("iago"),
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="http://127.0.0.1:8000/callback",
        )

    def _assert_cannot_manage_applications(self) -> None:
        app = self._create_iago_application()
        before_count = Application.objects.count()

        for url in (
            "/o/applications/",
            "/o/applications/register/",
            f"/o/applications/{app.id}/",
            f"/o/applications/{app.id}/delete/",
            f"/o/applications/{app.id}/update/",
        ):
            result = self.client_get(url)
            self.assertEqual(result.status_code, 404, url)
            self.assert_in_response("Page not found (404)", result)

        result = self.client_post(
            "/o/applications/register/",
            {
                "name": "Unauthorized App",
                "client_id": "test-client-id-unauthorized",
                "client_secret": "test-client-secret",
                "client_type": Application.CLIENT_CONFIDENTIAL,
                "redirect_uris": "http://127.0.0.1:8000/callback",
            },
        )
        self.assertEqual(result.status_code, 404)
        self.assertEqual(Application.objects.count(), before_count)

        result = self.client_post(f"/o/applications/{app.id}/delete/")
        self.assertEqual(result.status_code, 404)
        self.assertTrue(Application.objects.filter(id=app.id).exists())

    def test_member_cannot_manage_applications(self) -> None:
        self.login("hamlet")
        self._assert_cannot_manage_applications()

    def test_moderator_cannot_manage_applications(self) -> None:
        self.login("shiva")
        self._assert_cannot_manage_applications()

    def test_guest_cannot_manage_applications(self) -> None:
        self.login("polonius")
        self._assert_cannot_manage_applications()

    def test_logged_out_user_cannot_manage_applications(self) -> None:
        app = self._create_iago_application()
        for url in (
            "/o/applications/",
            "/o/applications/register/",
            f"/o/applications/{app.id}/",
            f"/o/applications/{app.id}/delete/",
            f"/o/applications/{app.id}/update/",
        ):
            result = self.client_get(url)
            self.assertEqual(result.status_code, 302, url)
            self.assertEqual(result["Location"].split("?")[0], settings.HOME_NOT_LOGGED_IN)

    def test_update_keeps_authorization_code_grant(self) -> None:
        self.login("iago")
        user_profile = self.example_user("iago")
        app = Application.objects.create(
            name="Existing App",
            user=user_profile,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="http://127.0.0.1:8000/callback",
        )

        result = self.client_post(
            f"/o/applications/{app.id}/update/",
            {
                "name": "Existing App Renamed",
                "client_id": app.client_id,
                "client_secret": app.client_secret,
                "client_type": Application.CLIENT_CONFIDENTIAL,
                "authorization_grant_type": Application.GRANT_CLIENT_CREDENTIALS,
                "redirect_uris": app.redirect_uris,
            },
        )

        self.assertEqual(result.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.name, "Existing App Renamed")
        self.assertEqual(app.authorization_grant_type, Application.GRANT_AUTHORIZATION_CODE)

    def test_authorization_view_ignores_prompt_none_redirect_uri(self) -> None:
        # zulip_login_required wraps the URL, so this path is only hit
        # if that wrap is skipped. Call the view method directly.
        request = HostRequestMock()
        request.GET["prompt"] = "none"
        request.GET["redirect_uri"] = "https://evil.example/x"
        view = ZulipAuthorizationView()
        view.setup(request)
        view.raise_exception = False
        result = view.handle_no_permission()
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"].split("?")[0], settings.LOGIN_URL)

    def test_logged_out_prompt_none_redirects_to_login(self) -> None:
        result = self.client_get(
            "/o/authorize/",
            {
                "prompt": "none",
                "client_id": "anything",
                "redirect_uri": "https://evil.example/x",
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"].split("?")[0], settings.HOME_NOT_LOGGED_IN)

    def test_deactivated_user_cannot_authorize(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        change_user_is_active(user_profile, False)
        result = self.client_get(
            "/o/authorize/",
            {
                "response_type": "code",
                "client_id": "anything",
                "redirect_uri": "http://127.0.0.1:8000/callback",
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"].split("?")[0], settings.HOME_NOT_LOGGED_IN)

    def test_other_admin_cannot_update_application(self) -> None:
        iago = self.example_user("iago")
        app = Application.objects.create(
            name="Iago App",
            user=iago,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="http://127.0.0.1:8000/callback",
        )

        self.login("desdemona")
        result = self.client_post(
            f"/o/applications/{app.id}/update/",
            {
                "name": "Stolen App",
                "client_id": app.client_id,
                "client_secret": app.client_secret,
                "client_type": Application.CLIENT_CONFIDENTIAL,
                "redirect_uris": app.redirect_uris,
            },
        )
        self.assertEqual(result.status_code, 404)
        app.refresh_from_db()
        self.assertEqual(app.name, "Iago App")
