from unittest import mock

from confirmation.models import Confirmation, ConfirmationObjT
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realms import get_realm
from zerver.views.auth import create_preregistration_user


class RegistrationCoverageTests(ZulipTestCase):
    def test_get_prereg_key_with_missing_confirmation(self) -> None:
        """Exception handling when confirmation manager .get() fails."""
        realm = get_realm("zulip")
        email = "missingconfirm+test@zulip.com"
        prereg = create_preregistration_user(email, realm, password_required=False)
        activation_url = self.make_confirmation_link(prereg, Confirmation.USER_REGISTRATION)
        key = activation_url.split("/")[-1]

        # Patch the related manager .get() to raise an arbitrary Exception
        with mock.patch.object(
            prereg.confirmation, "get", side_effect=Exception("No confirmation")
        ):
            resp = self.client_get(f"/accounts/do_confirm/{key}")
            # Should gracefully render the preregistration confirm page (no redirect)
            self.assertEqual(resp.status_code, 200)

    def test_accounts_home_post_with_invalid_invitation_key(self) -> None:
        """POST /register with invalid invitation_key falls through gracefully."""
        self.login("hamlet")
        payload = {"email": "newuser+postflow@zulip.com"}
        resp = self.client_post(
            "/register/?invitation_key=invalid_key_12345",
            payload,
            subdomain="zulip",
        )
        self.assertIn(resp.status_code, [200, 302])

    def test_accounts_home_get_with_prefill_email(self) -> None:
        """GET /register/?email=... initializes form with prefilled email."""
        email = "prefill+signup@zulip.com"
        resp = self.client_get(f"/register/?email={email}", subdomain="zulip")
        self.assertEqual(resp.status_code, 200)
        self.assert_in_success_response([email], resp)

    def test_accounts_home_get_with_invalid_invitation_key(self) -> None:
        """GET /register/?invitation_key=invalid falls through gracefully."""
        resp = self.client_get("/register/?invitation_key=invalid_key_12345", subdomain="zulip")
        # Should render the registration page without crashing
        self.assertEqual(resp.status_code, 200)

    # Helper to generate confirmation link consistent with production flows
    def make_confirmation_link(self, obj: ConfirmationObjT, confirmation_type: int) -> str:
        from confirmation.models import create_confirmation_link

        return create_confirmation_link(obj, confirmation_type)
