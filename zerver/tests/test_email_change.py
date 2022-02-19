import datetime
from unittest import mock

from django.conf import settings
from django.core import mail
from django.utils.timezone import now

from confirmation.models import (
    Confirmation,
    confirmation_url,
    create_confirmation_link,
    generate_key,
)
from zerver.lib.actions import (
    do_deactivate_realm,
    do_deactivate_user,
    do_set_realm_property,
    do_start_email_change_process,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    EmailChangeStatus,
    Realm,
    UserProfile,
    get_realm,
    get_user,
    get_user_by_delivery_email,
    get_user_profile_by_id,
)


class EmailChangeTestCase(ZulipTestCase):
    def test_confirm_email_change_with_non_existent_key(self) -> None:
        self.login("hamlet")
        key = generate_key()
        url = confirmation_url(key, None, Confirmation.EMAIL_CHANGE)
        response = self.client_get(url)
        self.assertEqual(response.status_code, 404)
        self.assert_in_response(
            "Whoops. We couldn't find your confirmation link in the system.", response
        )

    def test_confirm_email_change_with_invalid_key(self) -> None:
        self.login("hamlet")
        key = "invalid_key"
        url = confirmation_url(key, None, Confirmation.EMAIL_CHANGE)
        response = self.client_get(url)
        self.assertEqual(response.status_code, 404)
        self.assert_in_response("Whoops. The confirmation link is malformed.", response)

    def test_confirm_email_change_when_time_exceeded(self) -> None:
        user_profile = self.example_user("hamlet")
        old_email = user_profile.email
        new_email = "hamlet-new@zulip.com"
        self.login("hamlet")
        obj = EmailChangeStatus.objects.create(
            new_email=new_email,
            old_email=old_email,
            user_profile=user_profile,
            realm=user_profile.realm,
        )
        date_sent = now() - datetime.timedelta(days=2)
        with mock.patch("confirmation.models.timezone_now", return_value=date_sent):
            url = create_confirmation_link(obj, Confirmation.EMAIL_CHANGE)

        response = self.client_get(url)
        self.assertEqual(response.status_code, 404)
        self.assert_in_response("The confirmation link has expired or been deactivated.", response)

    def test_confirm_email_change(self) -> None:
        user_profile = self.example_user("hamlet")
        do_set_realm_property(
            user_profile.realm,
            "email_address_visibility",
            Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )

        old_email = user_profile.delivery_email
        new_email = "hamlet-new@zulip.com"
        new_realm = get_realm("zulip")
        self.login("hamlet")
        obj = EmailChangeStatus.objects.create(
            new_email=new_email,
            old_email=old_email,
            user_profile=user_profile,
            realm=user_profile.realm,
        )
        url = create_confirmation_link(obj, Confirmation.EMAIL_CHANGE)
        response = self.client_get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_in_success_response(
            ["This confirms that the email address for your Zulip"], response
        )
        user_profile = get_user_by_delivery_email(new_email, new_realm)
        self.assertTrue(bool(user_profile))
        obj.refresh_from_db()
        self.assertEqual(obj.status, 1)

    def test_change_email_deactivated_user_realm(self) -> None:
        data = {"email": "hamlet-new@zulip.com"}
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        url = "/json/settings"
        self.assert_length(mail.outbox, 0)
        result = self.client_patch(url, data)
        self.assert_length(mail.outbox, 1)
        self.assert_json_success(result)
        email_message = mail.outbox[0]
        self.assertEqual(
            email_message.subject,
            "Verify your new email address",
        )
        body = email_message.body
        self.assertIn("We received a request to change the email", body)

        activation_url = [s for s in body.split("\n") if s][2]

        do_deactivate_user(user_profile, acting_user=None)
        response = self.client_get(activation_url)
        self.assertEqual(response.status_code, 401)

        do_deactivate_realm(user_profile.realm, acting_user=None)

        response = self.client_get(activation_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith("/accounts/deactivated/"))

    def test_start_email_change_process(self) -> None:
        user_profile = self.example_user("hamlet")
        do_start_email_change_process(user_profile, "hamlet-new@zulip.com")
        self.assertEqual(EmailChangeStatus.objects.count(), 1)

    def test_end_to_end_flow(self) -> None:
        data = {"email": "hamlet-new@zulip.com"}
        self.login("hamlet")
        url = "/json/settings"
        self.assert_length(mail.outbox, 0)
        result = self.client_patch(url, data)
        self.assert_json_success(result)
        self.assert_length(mail.outbox, 1)
        email_message = mail.outbox[0]
        self.assertEqual(
            email_message.subject,
            "Verify your new email address",
        )
        body = email_message.body
        self.assertIn("We received a request to change the email", body)
        self.assertEqual(self.email_envelope_from(email_message), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertRegex(
            self.email_display_from(email_message),
            rf"^Zulip Account Security <{self.TOKENIZED_NOREPLY_REGEX}>\Z",
        )

        self.assertEqual(email_message.extra_headers["List-Id"], "Zulip Dev <zulip.testserver>")

        activation_url = [s for s in body.split("\n") if s][2]
        response = self.client_get(activation_url)

        self.assert_in_success_response(["This confirms that the email address"], response)

        # Now confirm trying to change your email back doesn't throw an immediate error
        result = self.client_patch(url, {"email": "hamlet@zulip.com"})
        self.assert_json_success(result)

    def test_unauthorized_email_change(self) -> None:
        data = {"email": "hamlet-new@zulip.com"}
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        do_set_realm_property(
            user_profile.realm,
            "email_changes_disabled",
            True,
            acting_user=None,
        )
        url = "/json/settings"
        result = self.client_patch(url, data)
        self.assert_length(mail.outbox, 0)
        self.assertEqual(result.status_code, 400)
        self.assert_in_response("Email address changes are disabled in this organization.", result)
        # Realm admins can change their email address even setting is disabled.
        data = {"email": "iago-new@zulip.com"}
        self.login("iago")
        url = "/json/settings"
        result = self.client_patch(url, data)
        self.assert_json_success(result)

    def test_email_change_already_taken(self) -> None:
        data = {"email": "cordelia@zulip.com"}
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)

        url = "/json/settings"
        result = self.client_patch(url, data)
        self.assert_length(mail.outbox, 0)
        self.assertEqual(result.status_code, 400)
        self.assert_in_response("Already has an account", result)

    def test_unauthorized_email_change_from_email_confirmation_link(self) -> None:
        data = {"email": "hamlet-new@zulip.com"}
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        url = "/json/settings"
        self.assert_length(mail.outbox, 0)
        result = self.client_patch(url, data)
        self.assert_length(mail.outbox, 1)
        self.assert_json_success(result)
        email_message = mail.outbox[0]
        self.assertEqual(
            email_message.subject,
            "Verify your new email address",
        )
        body = email_message.body
        self.assertIn("We received a request to change the email", body)

        do_set_realm_property(
            user_profile.realm,
            "email_changes_disabled",
            True,
            acting_user=None,
        )

        activation_url = [s for s in body.split("\n") if s][2]
        response = self.client_get(activation_url)

        self.assertEqual(response.status_code, 400)
        self.assert_in_response(
            "Email address changes are disabled in this organization.", response
        )

    def test_post_invalid_email(self) -> None:
        data = {"email": "hamlet-new"}
        self.login("hamlet")
        url = "/json/settings"
        result = self.client_patch(url, data)
        self.assert_in_response("Invalid address", result)

    def test_post_same_email(self) -> None:
        data = {"email": self.example_email("hamlet")}
        self.login("hamlet")
        url = "/json/settings"
        result = self.client_patch(url, data)
        self.assertEqual("success", result.json()["result"])
        self.assertEqual("", result.json()["msg"])

    def test_change_delivery_email_end_to_end_with_admins_visibility(self) -> None:
        user_profile = self.example_user("hamlet")
        do_set_realm_property(
            user_profile.realm,
            "email_address_visibility",
            Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )

        self.login_user(user_profile)
        old_email = user_profile.delivery_email
        new_email = "hamlet-new@zulip.com"
        obj = EmailChangeStatus.objects.create(
            new_email=new_email,
            old_email=old_email,
            user_profile=user_profile,
            realm=user_profile.realm,
        )
        url = create_confirmation_link(obj, Confirmation.EMAIL_CHANGE)
        response = self.client_get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_in_success_response(
            ["This confirms that the email address for your Zulip"], response
        )
        user_profile = get_user_profile_by_id(user_profile.id)
        self.assertEqual(user_profile.delivery_email, new_email)
        self.assertEqual(user_profile.email, f"user{user_profile.id}@zulip.testserver")
        obj.refresh_from_db()
        self.assertEqual(obj.status, 1)
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user(old_email, user_profile.realm)
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user_by_delivery_email(old_email, user_profile.realm)
        self.assertEqual(get_user_by_delivery_email(new_email, user_profile.realm), user_profile)
