from oauth2_provider.models import Application, get_application_model

from zerver.lib.test_classes import ZulipTestCase


class OAuthApplicationFormTest(ZulipTestCase):
    def test_register_page_fixes_grant_type_as_disabled_field(self) -> None:
        self.login("hamlet")
        result = self.client_get("/o/applications/register/")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Register a new application", result)
        self.assert_in_response("authorization_grant_type", result)
        self.assert_in_response("disabled", result)
        self.assert_in_response("Authorization code", result)
        # Other grant types must not be offered as choices.
        content = result.content.decode()
        self.assertNotIn("Device Code", content)
        self.assertNotIn("Resource owner password-based", content)
        self.assertNotIn("Client credentials", content)
        self.assertNotIn("Implicit", content)
        self.assertNotIn("OpenID connect hybrid", content)

    def test_register_ignores_tampered_grant_type(self) -> None:
        """Disabled fields are not taken from POST; value stays authorization code."""
        self.login("hamlet")
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
                "post_logout_redirect_uris": "",
                "allowed_origins": "",
            },
        )

        self.assertEqual(result.status_code, 302)
        self.assertEqual(ApplicationModel.objects.count(), before_count + 1)
        app = ApplicationModel.objects.get(name="Tampered Grant App")
        self.assertEqual(app.authorization_grant_type, Application.GRANT_AUTHORIZATION_CODE)

    def test_register_accepts_authorization_code_grant(self) -> None:
        self.login("hamlet")
        ApplicationModel = get_application_model()
        before_count = ApplicationModel.objects.count()

        result = self.client_post(
            "/o/applications/register/",
            {
                "name": "Auth Code App",
                "client_id": "test-client-id-auth-code",
                "client_secret": "test-client-secret",
                "client_type": Application.CLIENT_CONFIDENTIAL,
                # Omitted on purpose: disabled fields are not submitted by browsers.
                "redirect_uris": "http://127.0.0.1:8000/callback",
                "post_logout_redirect_uris": "",
                "allowed_origins": "",
            },
        )

        self.assertEqual(result.status_code, 302)
        self.assertEqual(ApplicationModel.objects.count(), before_count + 1)
        app = ApplicationModel.objects.get(name="Auth Code App")
        self.assertEqual(app.authorization_grant_type, Application.GRANT_AUTHORIZATION_CODE)

    def test_update_keeps_authorization_code_grant(self) -> None:
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
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
                "post_logout_redirect_uris": "",
                "allowed_origins": "",
            },
        )

        self.assertEqual(result.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.name, "Existing App Renamed")
        self.assertEqual(app.authorization_grant_type, Application.GRANT_AUTHORIZATION_CODE)
