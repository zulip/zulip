import re
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Union
from unittest.mock import MagicMock, patch
from urllib.parse import quote, quote_plus, urlencode, urlsplit

import orjson
from django.conf import settings
from django.contrib.auth.views import PasswordResetConfirmView
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.http import HttpResponse, HttpResponseBase
from django.template.response import TemplateResponse
from django.test import Client, override_settings
from django.utils import translation

from confirmation import settings as confirmation_settings
from confirmation.models import Confirmation, one_click_unsubscribe_link
from zerver.actions.create_realm import do_change_realm_subdomain, do_create_realm
from zerver.actions.create_user import add_new_user_history
from zerver.actions.default_streams import do_add_default_stream, do_create_default_stream_group
from zerver.actions.realm_settings import (
    do_deactivate_realm,
    do_set_realm_authentication_methods,
    do_set_realm_property,
    do_set_realm_user_default_setting,
)
from zerver.actions.users import change_user_is_active, do_change_user_role, do_deactivate_user
from zerver.decorator import do_two_factor_login
from zerver.forms import HomepageForm, check_subdomain_available
from zerver.lib.default_streams import get_default_streams_for_realm_as_dicts
from zerver.lib.email_notifications import enqueue_welcome_emails
from zerver.lib.i18n import get_default_language_for_new_user
from zerver.lib.initial_password import initial_password
from zerver.lib.mobile_auth_otp import (
    ascii_to_hex,
    hex_to_ascii,
    is_valid_otp,
    otp_decrypt_api_key,
    otp_encrypt_api_key,
    xor_hex_strings,
)
from zerver.lib.name_restrictions import is_disposable_domain
from zerver.lib.send_email import EmailNotDeliveredError, FromAddress, send_future_email
from zerver.lib.stream_subscription import get_stream_subscriptions_for_user
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.subdomains import is_root_domain_available
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    HostRequestMock,
    avatar_disk_path,
    find_key_by_email,
    get_test_image_file,
    load_subdomain_token,
    message_stream_count,
    most_recent_message,
    most_recent_usermessage,
    ratelimit_rule,
    reset_email_visibility_to_everyone_in_zulip_realm,
)
from zerver.models import (
    CustomProfileField,
    CustomProfileFieldValue,
    DefaultStream,
    Message,
    PreregistrationRealm,
    PreregistrationUser,
    Realm,
    RealmAuditLog,
    RealmUserDefault,
    Recipient,
    ScheduledEmail,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)
from zerver.models.realms import get_realm
from zerver.models.recipients import get_huddle_user_ids
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot, get_user, get_user_by_delivery_email
from zerver.views.auth import redirect_and_log_into_subdomain, start_two_factor_auth
from zerver.views.development.registration import confirmation_key
from zproject.backends import ExternalAuthDataDict, ExternalAuthResult, email_auth_enabled

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class RedirectAndLogIntoSubdomainTestCase(ZulipTestCase):
    def test_data(self) -> None:
        realm = get_realm("zulip")
        user_profile = self.example_user("hamlet")
        name = user_profile.full_name
        email = user_profile.delivery_email
        response = redirect_and_log_into_subdomain(ExternalAuthResult(user_profile=user_profile))
        data = load_subdomain_token(response)
        self.assertDictEqual(
            data,
            {"full_name": name, "email": email, "subdomain": realm.subdomain, "is_signup": False},
        )

        data_dict = ExternalAuthDataDict(is_signup=True, multiuse_object_key="key")
        response = redirect_and_log_into_subdomain(
            ExternalAuthResult(user_profile=user_profile, data_dict=data_dict)
        )
        data = load_subdomain_token(response)
        self.assertDictEqual(
            data,
            {
                "full_name": name,
                "email": email,
                "subdomain": realm.subdomain,
                # the email has an account at the subdomain,
                # so is_signup get overridden to False:
                "is_signup": False,
                "multiuse_object_key": "key",
            },
        )

        data_dict = ExternalAuthDataDict(
            email=self.nonreg_email("alice"),
            full_name="Alice",
            subdomain=realm.subdomain,
            is_signup=True,
            full_name_validated=True,
            multiuse_object_key="key",
        )
        response = redirect_and_log_into_subdomain(ExternalAuthResult(data_dict=data_dict))
        data = load_subdomain_token(response)
        self.assertDictEqual(
            data,
            {
                "full_name": "Alice",
                "email": self.nonreg_email("alice"),
                "full_name_validated": True,
                "subdomain": realm.subdomain,
                "is_signup": True,
                "multiuse_object_key": "key",
            },
        )


class DeactivationNoticeTestCase(ZulipTestCase):
    def test_redirection_for_deactivated_realm(self) -> None:
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        for url in ("/register/", "/login/"):
            result = self.client_get(url)
            self.assertRedirects(result, "/accounts/deactivated/", status_code=302)

    def test_redirection_for_active_realm(self) -> None:
        for url in ("/register/", "/login/"):
            result = self.client_get(url)
            self.assertEqual(result.status_code, 200)

    def test_deactivation_notice_when_realm_is_active(self) -> None:
        result = self.client_get("/accounts/deactivated/")
        self.assertRedirects(result, "/devlogin/", status_code=302)

    def test_deactivation_notice_when_deactivated(self) -> None:
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.client_get("/login/", follow=True)
        self.assertEqual(result.redirect_chain[-1], ("/accounts/deactivated/", 302))
        self.assertIn("Zulip Dev, has been deactivated.", result.content.decode())
        self.assertNotIn("It has moved to", result.content.decode())

    def test_deactivation_notice_when_deactivated_and_deactivated_redirect_is_set(self) -> None:
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.deactivated_redirect = "http://example.zulipchat.com"
        realm.save(update_fields=["deactivated", "deactivated_redirect"])

        result = self.client_get("/login/", follow=True)
        self.assertIn(
            'It has moved to <a href="http://example.zulipchat.com">http://example.zulipchat.com</a>.',
            result.content.decode(),
        )

    def test_deactivation_notice_when_realm_subdomain_is_changed(self) -> None:
        realm = get_realm("zulip")
        do_change_realm_subdomain(realm, "new-subdomain-name", acting_user=None)

        result = self.client_get("/login/", follow=True)
        self.assertIn(
            'It has moved to <a href="http://new-subdomain-name.testserver">http://new-subdomain-name.testserver</a>.',
            result.content.decode(),
        )

    def test_no_deactivation_notice_with_no_redirect(self) -> None:
        realm = get_realm("zulip")
        do_change_realm_subdomain(
            realm, "new-subdomain-name", acting_user=None, add_deactivated_redirect=False
        )

        result = self.client_get("/login/", follow=True)
        self.assertEqual(result.status_code, 404)
        self.assertNotIn(
            "new-subdomain-name",
            result.content.decode(),
        )

    def test_deactivated_redirect_field_of_placeholder_realms_are_modified_on_changing_subdomain_multiple_times(
        self,
    ) -> None:
        realm = get_realm("zulip")
        do_change_realm_subdomain(realm, "new-name-1", acting_user=None)

        result = self.client_get("/login/", follow=True)
        self.assertIn(
            'It has moved to <a href="http://new-name-1.testserver">http://new-name-1.testserver</a>.',
            result.content.decode(),
        )

        realm = get_realm("new-name-1")
        do_change_realm_subdomain(realm, "new-name-2", acting_user=None)
        result = self.client_get("/login/", follow=True)
        self.assertIn(
            'It has moved to <a href="http://new-name-2.testserver">http://new-name-2.testserver</a>.',
            result.content.decode(),
        )


class AddNewUserHistoryTest(ZulipTestCase):
    def test_add_new_user_history_race(self) -> None:
        """Sends a message during user creation"""
        # Create a user who hasn't had historical messages added
        realm = get_realm("zulip")
        stream = Stream.objects.get(realm=realm, name="Denmark")
        DefaultStream.objects.create(stream=stream, realm=realm)
        # Make sure at least 3 messages are sent to Denmark and it's a default stream.
        message_id = self.send_stream_message(self.example_user("hamlet"), stream.name, "test 1")
        self.send_stream_message(self.example_user("hamlet"), stream.name, "test 2")
        self.send_stream_message(self.example_user("hamlet"), stream.name, "test 3")

        with patch("zerver.actions.create_user.add_new_user_history"):
            self.register(self.nonreg_email("test"), "test")
        user_profile = self.nonreg_user("test")
        subs = Subscription.objects.select_related("recipient").filter(
            user_profile=user_profile, recipient__type=Recipient.STREAM
        )
        streams = Stream.objects.filter(id__in=[sub.recipient.type_id for sub in subs])

        # Sent a message afterwards to trigger a race between message
        # sending and `add_new_user_history`.
        race_message_id = self.send_stream_message(
            self.example_user("hamlet"), streams[0].name, "test"
        )

        # Overwrite MAX_NUM_ONBOARDING_UNREAD_MESSAGES to 2
        MAX_NUM_ONBOARDING_UNREAD_MESSAGES = 2
        with patch(
            "zerver.actions.create_user.MAX_NUM_ONBOARDING_UNREAD_MESSAGES",
            MAX_NUM_ONBOARDING_UNREAD_MESSAGES,
        ):
            add_new_user_history(user_profile, streams)

        # Our first message is in the user's history
        self.assertTrue(
            UserMessage.objects.filter(user_profile=user_profile, message_id=message_id).exists()
        )
        # The race message is in the user's history and marked unread.
        self.assertTrue(
            UserMessage.objects.filter(
                user_profile=user_profile, message_id=race_message_id
            ).exists()
        )
        self.assertFalse(
            UserMessage.objects.get(
                user_profile=user_profile, message_id=race_message_id
            ).flags.read.is_set
        )

        # Verify that the MAX_NUM_ONBOARDING_UNREAD_MESSAGES latest messages
        # that weren't the race message are marked as unread.
        latest_messages = (
            UserMessage.objects.filter(
                user_profile=user_profile,
                message__recipient__type=Recipient.STREAM,
            )
            .exclude(message_id=race_message_id)
            .order_by("-message_id")[0:MAX_NUM_ONBOARDING_UNREAD_MESSAGES]
        )
        self.assert_length(latest_messages, 2)
        for msg in latest_messages:
            self.assertFalse(msg.flags.read.is_set)

        # Verify that older messages are correctly marked as read.
        older_messages = (
            UserMessage.objects.filter(
                user_profile=user_profile,
                message__recipient__type=Recipient.STREAM,
            )
            .exclude(message_id=race_message_id)
            .order_by("-message_id")[
                MAX_NUM_ONBOARDING_UNREAD_MESSAGES : MAX_NUM_ONBOARDING_UNREAD_MESSAGES + 1
            ]
        )
        self.assertGreater(len(older_messages), 0)
        for msg in older_messages:
            self.assertTrue(msg.flags.read.is_set)

    def test_auto_subbed_to_personals(self) -> None:
        """
        Newly created users are auto-subbed to the ability to receive
        personals.
        """
        test_email = self.nonreg_email("test")
        self.register(test_email, "test")
        user_profile = self.nonreg_user("test")
        old_messages_count = message_stream_count(user_profile)
        self.send_personal_message(user_profile, user_profile)
        new_messages_count = message_stream_count(user_profile)
        self.assertEqual(new_messages_count, old_messages_count + 1)

        recipient = Recipient.objects.get(type_id=user_profile.id, type=Recipient.PERSONAL)
        message = most_recent_message(user_profile)
        self.assertEqual(message.recipient, recipient)

        with patch("zerver.models.Recipient.label", return_value="recip"):
            self.assertEqual(
                repr(message),
                "<Message: recip /  / "
                f"<UserProfile: {user_profile.email} {user_profile.realm!r}>>",
            )

            user_message = most_recent_usermessage(user_profile)
            self.assertEqual(
                repr(user_message),
                f"<UserMessage: recip / {user_profile.email} (['read'])>",
            )


class InitialPasswordTest(ZulipTestCase):
    def test_none_initial_password_salt(self) -> None:
        with self.settings(INITIAL_PASSWORD_SALT=None):
            self.assertIsNone(initial_password("test@test.com"))


class PasswordResetTest(ZulipTestCase):
    """
    Log in, reset password, log out, log in with new password.
    """

    def get_reset_mail_body(self, subdomain: str = "zulip") -> str:
        from django.core.mail import outbox

        [message] = outbox
        self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertRegex(
            self.email_display_from(message),
            # The email might be sent in different languages for i18n testing
            rf"^testserver .* <{self.TOKENIZED_NOREPLY_REGEX}>\Z",
        )
        self.assertIn(f"{subdomain}.testserver", message.extra_headers["List-Id"])

        return str(message.body)

    def test_password_reset(self) -> None:
        user = self.example_user("hamlet")
        email = user.delivery_email
        old_password = initial_password(email)
        assert old_password is not None

        self.login_user(user)

        # test password reset template
        result = self.client_get("/accounts/password/reset/")
        self.assert_in_response("Reset your password", result)

        # start the password reset process by supplying an email address
        result = self.client_post("/accounts/password/reset/", {"email": email})

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        # Check that the password reset email is from a noreply address.
        body = self.get_reset_mail_body()
        self.assertIn("reset your password", body)

        # Visit the password reset link.
        password_reset_url = self.get_confirmation_url_from_outbox(
            email, url_pattern=settings.EXTERNAL_HOST + r"(\S\S+)"
        )
        result = self.client_get(password_reset_url)
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/{PasswordResetConfirmView.reset_url_token}/")
        )

        final_reset_url = result["Location"]
        result = self.client_get(final_reset_url)
        self.assertEqual(result.status_code, 200)

        # Reset your password
        with self.settings(PASSWORD_MIN_LENGTH=3, PASSWORD_MIN_GUESSES=1000):
            # Verify weak passwords don't work.
            result = self.client_post(
                final_reset_url, {"new_password1": "easy", "new_password2": "easy"}
            )
            self.assert_in_response("The password is too weak.", result)

            result = self.client_post(
                final_reset_url, {"new_password1": "f657gdGGk9", "new_password2": "f657gdGGk9"}
            )
            # password reset succeeded
            self.assertEqual(result.status_code, 302)
            self.assertTrue(result["Location"].endswith("/password/done/"))

            # log back in with new password
            self.login_by_email(email, password="f657gdGGk9")
            user_profile = self.example_user("hamlet")
            self.assert_logged_in_user_id(user_profile.id)

            # make sure old password no longer works
            self.assert_login_failure(email, password=old_password)

    @patch("django.http.HttpRequest.get_host")
    def test_password_reset_page_redirects_for_root_alias_when_root_domain_landing_page_is_enabled(
        self, mock_get_host: MagicMock
    ) -> None:
        mock_get_host.return_value = "alias.testserver"
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True, ROOT_SUBDOMAIN_ALIASES=["alias"]):
            result = self.client_get("/accounts/password/reset/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(
                result["Location"], "/accounts/go/?next=%2Faccounts%2Fpassword%2Freset%2F"
            )

        mock_get_host.return_value = "www.testserver"
        with self.settings(
            ROOT_DOMAIN_LANDING_PAGE=True,
        ):
            result = self.client_get("/accounts/password/reset/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(
                result["Location"], "/accounts/go/?next=%2Faccounts%2Fpassword%2Freset%2F"
            )

    @patch("django.http.HttpRequest.get_host")
    def test_password_reset_page_redirects_for_root_domain_when_root_domain_landing_page_is_enabled(
        self, mock_get_host: MagicMock
    ) -> None:
        mock_get_host.return_value = "testserver"
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/accounts/password/reset/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(
                result["Location"], "/accounts/go/?next=%2Faccounts%2Fpassword%2Freset%2F"
            )

        mock_get_host.return_value = "www.zulip.example.com"
        with self.settings(
            ROOT_DOMAIN_LANDING_PAGE=True,
            EXTERNAL_HOST="www.zulip.example.com",
        ):
            result = self.client_get("/accounts/password/reset/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(
                result["Location"], "/accounts/go/?next=%2Faccounts%2Fpassword%2Freset%2F"
            )

    @patch("django.http.HttpRequest.get_host")
    def test_password_reset_page_works_for_root_alias_when_root_domain_landing_page_is_not_enabled(
        self, mock_get_host: MagicMock
    ) -> None:
        mock_get_host.return_value = "alias.testserver"
        with self.settings(ROOT_SUBDOMAIN_ALIASES=["alias"]):
            result = self.client_get("/accounts/password/reset/")
            self.assertEqual(result.status_code, 200)

        mock_get_host.return_value = "www.testserver"
        result = self.client_get("/accounts/password/reset/")
        self.assertEqual(result.status_code, 200)

    @patch("django.http.HttpRequest.get_host")
    def test_password_reset_page_works_for_root_domain_when_root_domain_landing_page_is_not_enabled(
        self, mock_get_host: MagicMock
    ) -> None:
        mock_get_host.return_value = "testserver"
        result = self.client_get("/accounts/password/reset/")
        self.assertEqual(result.status_code, 200)

        mock_get_host.return_value = "www.zulip.example.com"
        with self.settings(EXTERNAL_HOST="www.zulip.example.com", ROOT_SUBDOMAIN_ALIASES=[]):
            result = self.client_get("/accounts/password/reset/")
            self.assertEqual(result.status_code, 200)

    @patch("django.http.HttpRequest.get_host")
    def test_password_reset_page_works_always_for_subdomains(
        self, mock_get_host: MagicMock
    ) -> None:
        mock_get_host.return_value = "lear.testserver"
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/accounts/password/reset/")
            self.assertEqual(result.status_code, 200)

        result = self.client_get("/accounts/password/reset/")
        self.assertEqual(result.status_code, 200)

    def test_password_reset_for_non_existent_user(self) -> None:
        email = "nonexisting@mars.com"

        # start the password reset process by supplying an email address
        result = self.client_post("/accounts/password/reset/", {"email": email})

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        # Check that the password reset email is from a noreply address.
        body = self.get_reset_mail_body()
        self.assertIn("Somebody (possibly you) requested a new password", body)
        self.assertIn("You do not have an account", body)
        self.assertIn("safely ignore", body)
        self.assertNotIn("reset your password", body)
        self.assertNotIn("deactivated", body)

    def test_password_reset_for_deactivated_user(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email
        do_deactivate_user(user_profile, acting_user=None)

        # start the password reset process by supplying an email address
        result = self.client_post("/accounts/password/reset/", {"email": email})

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        # Check that the password reset email is from a noreply address.
        body = self.get_reset_mail_body()
        self.assertIn("Somebody (possibly you) requested a new password", body)
        self.assertIn("has been deactivated", body)
        self.assertIn("safely ignore", body)
        self.assertNotIn("reset your password", body)
        self.assertNotIn("not have an account", body)

    def test_password_reset_with_deactivated_realm(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email
        do_deactivate_realm(user_profile.realm, acting_user=None)

        # start the password reset process by supplying an email address
        with self.assertLogs(level="INFO") as m:
            result = self.client_post("/accounts/password/reset/", {"email": email})
            self.assertEqual(m.output, ["INFO:root:Realm is deactivated"])

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        # Check that the password reset email is from a noreply address.
        from django.core.mail import outbox

        self.assert_length(outbox, 0)

    @ratelimit_rule(10, 2, domain="password_reset_form_by_email")
    def test_rate_limiting(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email
        from django.core.mail import outbox

        start_time = time.time()
        with patch("time.time", return_value=start_time):
            self.client_post("/accounts/password/reset/", {"email": email})
            self.client_post("/accounts/password/reset/", {"email": email})
            self.assert_length(outbox, 2)

            # Too many password reset emails sent to the address, we won't send more.
            with self.assertLogs(level="INFO") as info_logs:
                self.client_post("/accounts/password/reset/", {"email": email})
            self.assertEqual(
                info_logs.output,
                [
                    "INFO:root:Too many password reset attempts for email hamlet@zulip.com from 127.0.0.1"
                ],
            )
            self.assert_length(outbox, 2)

            # Resetting for a different address works though.
            self.client_post("/accounts/password/reset/", {"email": self.example_email("othello")})
            self.assert_length(outbox, 3)
            self.client_post("/accounts/password/reset/", {"email": self.example_email("othello")})
            self.assert_length(outbox, 4)

        # After time, password reset emails can be sent again.
        with patch("time.time", return_value=start_time + 11):
            self.client_post("/accounts/password/reset/", {"email": email})
            self.client_post("/accounts/password/reset/", {"email": email})
            self.assert_length(outbox, 6)

    def test_wrong_subdomain(self) -> None:
        email = self.example_email("hamlet")

        # start the password reset process by supplying an email address
        result = self.client_post("/accounts/password/reset/", {"email": email}, subdomain="zephyr")

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        body = self.get_reset_mail_body("zephyr")
        self.assertIn("Somebody (possibly you) requested a new password", body)
        self.assertIn("You do not have an account", body)
        self.assertIn(
            "active accounts in the following organization(s).\nhttp://zulip.testserver", body
        )
        self.assertIn("safely ignore", body)
        self.assertNotIn("reset your password", body)
        self.assertNotIn("deactivated", body)

    def test_wrong_subdomain_i18n(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email

        # Send a password reset request with a different language to a wrong subdomain
        result = self.client_post(
            "/accounts/password/reset/",
            {"email": email},
            HTTP_ACCEPT_LANGUAGE="de",
            subdomain="lear",
        )
        self.assertEqual(result.status_code, 302)

        with translation.override("de"):
            body = self.get_reset_mail_body("lear")
            self.assertIn("hat ein neues Passwort", body)

    def test_invalid_subdomain(self) -> None:
        email = self.example_email("hamlet")

        # start the password reset process by supplying an email address
        result = self.client_post(
            "/accounts/password/reset/", {"email": email}, subdomain="invalid"
        )

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 404)
        self.assert_in_response("There is no Zulip organization hosted at this subdomain.", result)

        from django.core.mail import outbox

        self.assert_length(outbox, 0)

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_auth_only(self) -> None:
        """If the email auth backend is not enabled, password reset should do nothing"""
        email = self.example_email("hamlet")
        with self.assertLogs(level="INFO") as m:
            result = self.client_post("/accounts/password/reset/", {"email": email})
            self.assertEqual(
                m.output,
                [
                    "INFO:root:Password reset attempted for hamlet@zulip.com even though password auth is disabled."
                ],
            )

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        from django.core.mail import outbox

        self.assert_length(outbox, 0)

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.EmailAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_and_email_auth(self) -> None:
        """If both email and LDAP auth backends are enabled, limit password
        reset to users outside the LDAP domain"""
        # If the domain matches, we don't generate an email
        with self.settings(LDAP_APPEND_DOMAIN="zulip.com"):
            email = self.example_email("hamlet")
            with self.assertLogs(level="INFO") as m:
                result = self.client_post("/accounts/password/reset/", {"email": email})
                self.assertEqual(
                    m.output, ["INFO:root:Password reset not allowed for user in LDAP domain"]
                )
        from django.core.mail import outbox

        self.assert_length(outbox, 0)

        # If the domain doesn't match, we do generate an email
        with self.settings(LDAP_APPEND_DOMAIN="example.com"):
            email = self.example_email("hamlet")
            result = self.client_post("/accounts/password/reset/", {"email": email})
            self.assertEqual(result.status_code, 302)
            self.assertTrue(result["Location"].endswith("/accounts/password/reset/done/"))
            result = self.client_get(result["Location"])

        body = self.get_reset_mail_body()
        self.assertIn("reset your password", body)

    def test_redirect_endpoints(self) -> None:
        """
        These tests are mostly designed to give us 100% URL coverage
        in our URL coverage reports.  Our mechanism for finding URL
        coverage doesn't handle redirects, so we just have a few quick
        tests here.
        """
        result = self.client_get("/accounts/password/reset/done/")
        self.assert_in_success_response(["Check your email"], result)

        result = self.client_get("/accounts/password/done/")
        self.assert_in_success_response(["You've set a new password!"], result)

        result = self.client_get("/accounts/send_confirm/?email=alice@example.com")
        self.assert_in_success_response(["/accounts/home/"], result)

        result = self.client_get(
            "/accounts/new/send_confirm/?email=alice@example.com&realm_name=Zulip+test&realm_type=10&realm_default_language=en&realm_subdomain=zuliptest"
        )
        self.assert_in_success_response(["/new/"], result)

    def test_password_reset_for_soft_deactivated_user(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email

        def reset_password() -> None:
            # start the password reset process by supplying an email address
            result = self.client_post("/accounts/password/reset/", {"email": email})

            # check the redirect link telling you to check mail for password reset link
            self.assertEqual(result.status_code, 302)
            self.assertTrue(result["Location"].endswith("/accounts/password/reset/done/"))

        self.soft_deactivate_user(user_profile)
        self.expect_soft_reactivation(user_profile, reset_password)


class LoginTest(ZulipTestCase):
    """
    Logging in, registration, and logging out.
    """

    def test_login(self) -> None:
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        self.assert_logged_in_user_id(user_profile.id)

    def test_login_deactivated_user(self) -> None:
        user_profile = self.example_user("hamlet")
        do_deactivate_user(user_profile, acting_user=None)
        result = self.login_with_return(user_profile.delivery_email, "xxx")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response(
            f"Your account {user_profile.delivery_email} has been deactivated.", result
        )
        self.assert_logged_in_user_id(None)

    def test_login_deactivate_user_error(self) -> None:
        """
        This is meant to test whether the error message signaled by the
        is_deactivated is shown independently of whether the Email
        backend is enabled.
        """
        user_profile = self.example_user("hamlet")
        realm = user_profile.realm
        self.assertTrue(email_auth_enabled(realm))

        url = f"{realm.uri}/login/?" + urlencode({"is_deactivated": user_profile.delivery_email})
        result = self.client_get(url)
        self.assertEqual(result.status_code, 200)
        self.assert_in_response(
            f"Your account {user_profile.delivery_email} has been deactivated.", result
        )

        auth_dict = realm.authentication_methods_dict()
        auth_dict["Email"] = False
        do_set_realm_authentication_methods(realm, auth_dict, acting_user=None)
        result = self.client_get(url)
        self.assertEqual(result.status_code, 200)
        self.assert_in_response(
            f"Your account {user_profile.delivery_email} has been deactivated.", result
        )

    def test_login_bad_password(self) -> None:
        user = self.example_user("hamlet")
        password: Optional[str] = "wrongpassword"
        result = self.login_with_return(user.delivery_email, password=password)
        self.assert_in_success_response([user.delivery_email], result)
        self.assert_logged_in_user_id(None)

        # Parallel test to confirm that the right password works using the
        # same login code, which verifies our failing test isn't broken
        # for some other reason.
        password = initial_password(user.delivery_email)
        result = self.login_with_return(user.delivery_email, password=password)
        self.assertEqual(result.status_code, 302)
        self.assert_logged_in_user_id(user.id)

    @override_settings(RATE_LIMITING_AUTHENTICATE=True)
    @ratelimit_rule(10, 2, domain="authenticate_by_username")
    def test_login_bad_password_rate_limiter(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email

        start_time = time.time()
        with patch("time.time", return_value=start_time):
            self.login_with_return(email, password="wrongpassword")
            self.assert_logged_in_user_id(None)
            self.login_with_return(email, password="wrongpassword")
            self.assert_logged_in_user_id(None)

            # We're over the allowed limit, so the next attempt, even with the correct
            # password, will get blocked.
            result = self.login_with_return(email)
            self.assert_in_success_response(["Try again in 10 seconds"], result)

        # After time passes, we should be able to log in.
        with patch("time.time", return_value=start_time + 11):
            self.login_with_return(email)
            self.assert_logged_in_user_id(user_profile.id)

    def test_login_with_old_weak_password_after_hasher_change(self) -> None:
        user_profile = self.example_user("hamlet")
        password = "a_password_of_22_chars"

        with self.settings(PASSWORD_HASHERS=("django.contrib.auth.hashers.SHA1PasswordHasher",)):
            user_profile.set_password(password)
            user_profile.save()

        with self.settings(
            PASSWORD_HASHERS=(
                "django.contrib.auth.hashers.MD5PasswordHasher",
                "django.contrib.auth.hashers.SHA1PasswordHasher",
            ),
            PASSWORD_MIN_LENGTH=30,
        ), self.assertLogs("zulip.auth.email", level="INFO"):
            result = self.login_with_return(self.example_email("hamlet"), password)
            self.assertEqual(result.status_code, 200)
            self.assert_in_response(
                "Your password has been disabled because it is too weak.", result
            )
            self.assert_logged_in_user_id(None)

    def test_login_nonexistent_user(self) -> None:
        result = self.login_with_return("xxx@zulip.com", "xxx")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Please enter a correct email and password", result)
        self.assert_logged_in_user_id(None)

    def test_login_wrong_subdomain(self) -> None:
        user_profile = self.mit_user("sipbtest")
        email = user_profile.delivery_email
        with self.assertLogs("zulip.auth.OurAuthenticationForm", level="INFO") as m:
            result = self.login_with_return(email, "xxx")
            matching_accounts_dict = {"realm_id": user_profile.realm_id, "id": user_profile.id}
            self.assertEqual(
                m.output,
                [
                    f"INFO:zulip.auth.OurAuthenticationForm:User attempted password login to wrong subdomain zulip. Matching accounts: [{matching_accounts_dict}]"
                ],
            )
        self.assertEqual(result.status_code, 200)
        expected_error = (
            "Please enter a correct email and password. Note that both fields may be case-sensitive"
        )
        self.assert_in_response(expected_error, result)
        self.assert_logged_in_user_id(None)

    def test_login_invalid_subdomain(self) -> None:
        result = self.login_with_return(self.example_email("hamlet"), "xxx", subdomain="invalid")
        self.assertEqual(result.status_code, 404)
        self.assert_in_response("There is no Zulip organization hosted at this subdomain.", result)
        self.assert_logged_in_user_id(None)

    def test_register(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        stream_names = [f"stream_{i}" for i in range(40)]
        for stream_name in stream_names:
            stream = self.make_stream(stream_name, realm=realm)
            DefaultStream.objects.create(stream=stream, realm=realm)

        # Make sure there's at least one recent message to be mark
        # unread.  This prevents a bug where this test would start
        # failing the test database was generated more than
        # ONBOARDING_RECENT_TIMEDELTA ago.
        self.subscribe(hamlet, "stream_0")
        self.send_stream_message(
            hamlet,
            "stream_0",
            topic_name="test topic",
            content="test message",
        )

        # Clear the ContentType cache.
        ContentType.objects.clear_cache()

        # Ensure the number of queries we make is not O(streams)
        # We can probably avoid a couple cache hits here, but there doesn't
        # seem to be any O(N) behavior.  Some of the cache hits are related
        # to sending messages, such as getting the welcome bot, looking up
        # the alert words for a realm, etc.
        with self.assert_database_query_count(104), self.assert_memcached_count(18):
            with self.captureOnCommitCallbacks(execute=True):
                self.register(self.nonreg_email("test"), "test")

        user_profile = self.nonreg_user("test")
        self.assert_logged_in_user_id(user_profile.id)
        self.assertFalse(user_profile.enable_stream_desktop_notifications)
        self.check_user_added_in_system_group(user_profile)

    def test_register_deactivated(self) -> None:
        """
        If you try to register for a deactivated realm, you get a clear error
        page.
        """
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.client_post(
            "/accounts/home/", {"email": self.nonreg_email("test")}, subdomain="zulip"
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual("/accounts/deactivated/", result["Location"])

        with self.assertRaises(UserProfile.DoesNotExist):
            self.nonreg_user("test")

    def test_register_with_invalid_email(self) -> None:
        """
        If you try to register with invalid email, you get an invalid email
        page
        """
        invalid_email = "foo\x00bar"
        result = self.client_post("/accounts/home/", {"email": invalid_email}, subdomain="zulip")

        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Enter a valid email address")

    def test_register_deactivated_partway_through(self) -> None:
        """
        If you try to register for a deactivated realm, you get a clear error
        page.
        """
        email = self.nonreg_email("test")
        result = self.client_post("/accounts/home/", {"email": email}, subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertNotIn("deactivated", result["Location"])

        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.submit_reg_form_for_user(email, "abcd1234", subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual("/accounts/deactivated/", result["Location"])

        with self.assertRaises(UserProfile.DoesNotExist):
            self.nonreg_user("test")

    def test_login_deactivated_realm(self) -> None:
        """
        If you try to log in to a deactivated realm, you get a clear error page.
        """
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.login_with_return(self.example_email("hamlet"), subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual("/accounts/deactivated/", result["Location"])

    def test_logout(self) -> None:
        self.login("hamlet")
        # We use the logout API, not self.logout, to make sure we test
        # the actual logout code path.
        self.client_post("/accounts/logout/")
        self.assert_logged_in_user_id(None)

    def test_non_ascii_login(self) -> None:
        """
        You can log in even if your password contain non-ASCII characters.
        """
        email = self.nonreg_email("test")
        password = "hÃ¼mbÃ¼Çµ"

        # Registering succeeds.
        self.register(email, password)
        user_profile = self.nonreg_user("test")
        self.assert_logged_in_user_id(user_profile.id)
        self.logout()
        self.assert_logged_in_user_id(None)

        # Logging in succeeds.
        self.logout()
        self.login_by_email(email, password)
        self.assert_logged_in_user_id(user_profile.id)

    @override_settings(TWO_FACTOR_AUTHENTICATION_ENABLED=False)
    def test_login_page_redirects_logged_in_user(self) -> None:
        """You will be redirected to the app's main page if you land on the
        login page when already logged in.
        """
        self.login("cordelia")
        response = self.client_get("/login/")
        self.assertEqual(response["Location"], "http://zulip.testserver/")

    def test_options_request_to_login_page(self) -> None:
        response = self.client_options("/login/")
        self.assertEqual(response.status_code, 200)

    @override_settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True)
    def test_login_page_redirects_logged_in_user_under_2fa(self) -> None:
        """You will be redirected to the app's main page if you land on the
        login page when already logged in.
        """
        user_profile = self.example_user("cordelia")
        self.create_default_device(user_profile)

        self.login("cordelia")
        self.login_2fa(user_profile)

        response = self.client_get("/login/")
        self.assertEqual(response["Location"], "http://zulip.testserver/")

    def test_start_two_factor_auth(self) -> None:
        request = HostRequestMock()
        with patch("zerver.views.auth.TwoFactorLoginView") as mock_view:
            mock_view.as_view.return_value = lambda *a, **k: HttpResponse()
            response = start_two_factor_auth(request)
            self.assertTrue(isinstance(response, HttpResponse))

    def test_do_two_factor_login(self) -> None:
        user_profile = self.example_user("hamlet")
        self.create_default_device(user_profile)
        request = HostRequestMock()
        with patch("zerver.decorator.django_otp.login") as mock_login:
            do_two_factor_login(request, user_profile)
            mock_login.assert_called_once()

    def test_zulip_default_context_does_not_load_inline_previews(self) -> None:
        realm = get_realm("zulip")
        description = "https://www.google.com/images/srpr/logo4w.png"
        realm.description = description
        realm.save(update_fields=["description"])
        response: HttpResponseBase = self.client_get("/login/")
        expected_response = """<p><a href="https://www.google.com/images/srpr/logo4w.png">\
https://www.google.com/images/srpr/logo4w.png</a></p>"""
        assert isinstance(response, TemplateResponse)
        assert response.context_data is not None
        self.assertEqual(response.context_data["realm_description"], expected_response)
        self.assertEqual(response.status_code, 200)


class EmailUnsubscribeTests(ZulipTestCase):
    def test_error_unsubscribe(self) -> None:
        # An invalid unsubscribe token "test123" produces an error.
        result = self.client_get("/accounts/unsubscribe/missed_messages/test123")
        self.assert_in_response("Unknown email unsubscribe request", result)

        # An unknown message type "fake" produces an error.
        user_profile = self.example_user("hamlet")
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "fake")
        result = self.client_get(urlsplit(unsubscribe_link).path)
        self.assert_in_response("Unknown email unsubscribe request", result)

    def test_message_notification_emails_unsubscribe(self) -> None:
        """
        We provide one-click unsubscribe links in message notification emails
        that you can click even when logged out to update your
        email notification settings.
        """
        user_profile = self.example_user("hamlet")
        user_profile.enable_offline_email_notifications = True
        user_profile.save()

        unsubscribe_link = one_click_unsubscribe_link(user_profile, "missed_messages")
        result = self.client_get(urlsplit(unsubscribe_link).path)

        self.assertEqual(result.status_code, 200)

        user_profile.refresh_from_db()
        self.assertFalse(user_profile.enable_offline_email_notifications)

    def test_welcome_unsubscribe(self) -> None:
        """
        We provide one-click unsubscribe links in welcome e-mails that you can
        click even when logged out to stop receiving them.
        """
        user_profile = self.example_user("hamlet")
        # Simulate scheduling welcome e-mails for a new user.
        enqueue_welcome_emails(user_profile)
        self.assertEqual(2, ScheduledEmail.objects.filter(users=user_profile).count())

        # Simulate unsubscribing from the welcome e-mails.
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "welcome")
        result = self.client_get(urlsplit(unsubscribe_link).path)

        # The welcome email jobs are no longer scheduled.
        self.assertEqual(result.status_code, 200)
        self.assertEqual(0, ScheduledEmail.objects.filter(users=user_profile).count())

    def test_digest_unsubscribe(self) -> None:
        """
        We provide one-click unsubscribe links in digest e-mails that you can
        click even when logged out to stop receiving them.

        Unsubscribing from these emails also dequeues any digest email jobs that
        have been queued.
        """
        user_profile = self.example_user("hamlet")
        self.assertTrue(user_profile.enable_digest_emails)

        # Enqueue a fake digest email.
        context = {
            "name": "",
            "realm_uri": "",
            "unread_pms": [],
            "hot_conversations": [],
            "new_users": [],
            "new_streams": {"plain": []},
            "unsubscribe_link": "",
        }
        send_future_email(
            "zerver/emails/digest",
            user_profile.realm,
            to_user_ids=[user_profile.id],
            context=context,
        )

        self.assertEqual(1, ScheduledEmail.objects.filter(users=user_profile).count())

        # Simulate unsubscribing from digest e-mails.
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "digest")
        result = self.client_get(urlsplit(unsubscribe_link).path)

        # The setting is toggled off, and scheduled jobs have been removed.
        self.assertEqual(result.status_code, 200)
        # Circumvent user_profile caching.

        user_profile.refresh_from_db()
        self.assertFalse(user_profile.enable_digest_emails)
        self.assertEqual(0, ScheduledEmail.objects.filter(users=user_profile).count())

    def test_login_unsubscribe(self) -> None:
        """
        We provide one-click unsubscribe links in login
        e-mails that you can click even when logged out to update your
        email notification settings.
        """
        user_profile = self.example_user("hamlet")
        user_profile.enable_login_emails = True
        user_profile.save()

        unsubscribe_link = one_click_unsubscribe_link(user_profile, "login")
        result = self.client_get(urlsplit(unsubscribe_link).path)

        self.assertEqual(result.status_code, 200)

        user_profile.refresh_from_db()
        self.assertFalse(user_profile.enable_login_emails)

    def test_marketing_unsubscribe(self) -> None:
        """
        We provide one-click unsubscribe links in marketing e-mails that you can
        click even when logged out to stop receiving them.
        """
        user_profile = self.example_user("hamlet")
        self.assertTrue(user_profile.enable_marketing_emails)

        # Simulate unsubscribing from marketing e-mails.
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "marketing")
        result = self.client_get(urlsplit(unsubscribe_link).path)
        self.assertEqual(result.status_code, 200)

        # Circumvent user_profile caching.
        user_profile.refresh_from_db()
        self.assertFalse(user_profile.enable_marketing_emails)

    def test_marketing_unsubscribe_post(self) -> None:
        """
        The List-Unsubscribe-Post header lets email clients trigger an
        automatic unsubscription request via POST (see RFC 8058), so
        test that too.
        """
        user_profile = self.example_user("hamlet")
        self.assertTrue(user_profile.enable_marketing_emails)

        # Simulate unsubscribing from marketing e-mails.
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "marketing")
        client = Client(enforce_csrf_checks=True)
        result = client.post(urlsplit(unsubscribe_link).path, {"List-Unsubscribe": "One-Click"})
        self.assertEqual(result.status_code, 200)

        # Circumvent user_profile caching.
        user_profile.refresh_from_db()
        self.assertFalse(user_profile.enable_marketing_emails)


class RealmCreationTest(ZulipTestCase):
    @override_settings(OPEN_REALM_CREATION=True)
    def check_able_to_create_realm(self, email: str, password: str = "test") -> None:
        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, internal_realm.id)
        signups_stream, _ = create_stream_if_needed(notification_bot.realm, "signups")

        string_id = "custom-test"
        org_name = "Zulip Test"
        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=org_name
        )

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(org_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        prereg_realm = PreregistrationRealm.objects.get(email=email)
        self.assertEqual(prereg_realm.name, "Zulip Test")
        self.assertEqual(prereg_realm.org_type, Realm.ORG_TYPES["business"]["id"])
        self.assertEqual(prereg_realm.default_language, "en")
        self.assertEqual(prereg_realm.string_id, string_id)

        # Check confirmation email has the correct subject and body, extract
        # confirmation link and visit it
        confirmation_url = self.get_confirmation_url_from_outbox(
            email,
            email_subject_contains="Create your Zulip organization",
            email_body_contains="You have requested a new Zulip organization",
        )
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain=string_id, realm_name=org_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith("http://custom-test.testserver/accounts/login/subdomain/")
        )

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)

        # Check that user is the owner.
        self.assertEqual(user.role, UserProfile.ROLE_REALM_OWNER)

        # Check defaults
        self.assertEqual(realm.org_type, Realm.ORG_TYPES["business"]["id"])
        self.assertEqual(realm.default_language, "en")
        self.assertEqual(realm.emails_restricted_to_domains, False)
        self.assertEqual(realm.invite_required, True)

        prereg_realm = PreregistrationRealm.objects.get(email=email)
        # Check created_realm and created_user field of PreregistrationRealm object
        self.assertEqual(prereg_realm.created_realm, realm)
        self.assertEqual(prereg_realm.created_user, user)
        self.assertEqual(prereg_realm.status, confirmation_settings.STATUS_USED)

        # Check welcome messages
        for stream_name, text, message_count in [
            (Realm.DEFAULT_NOTIFICATION_STREAM_NAME, "with the topic", 4),
            (Realm.INITIAL_PRIVATE_STREAM_NAME, "private channel", 1),
        ]:
            stream = get_stream(stream_name, realm)
            recipient = stream.recipient
            messages = Message.objects.filter(realm_id=realm.id, recipient=recipient).order_by(
                "date_sent"
            )
            self.assert_length(messages, message_count)
            self.assertIn(text, messages[0].content)

        # Check admin organization's signups stream messages
        recipient = signups_stream.recipient
        messages = Message.objects.filter(realm_id=internal_realm.id, recipient=recipient).order_by(
            "id"
        )
        self.assert_length(messages, 1)
        # Check organization name, subdomain and organization type are in message content
        self.assertIn("Zulip Test", messages[0].content)
        self.assertIn("custom-test", messages[0].content)
        self.assertIn("Organization type: Business", messages[0].content)
        self.assertEqual("new organizations", messages[0].topic_name())

        realm_creation_audit_log = RealmAuditLog.objects.get(
            realm=realm, event_type=RealmAuditLog.REALM_CREATED
        )
        self.assertEqual(realm_creation_audit_log.acting_user, user)
        self.assertEqual(realm_creation_audit_log.event_time, realm.date_created)

        # Piggyback a little check for how we handle
        # empty string_ids.
        realm.string_id = ""
        self.assertEqual(realm.display_subdomain, ".")

    def test_create_realm_non_existing_email(self) -> None:
        self.check_able_to_create_realm("user1@test.com")

    def test_create_realm_existing_email(self) -> None:
        self.check_able_to_create_realm("hamlet@zulip.com")

    @override_settings(AUTHENTICATION_BACKENDS=("zproject.backends.ZulipLDAPAuthBackend",))
    def test_create_realm_ldap_email(self) -> None:
        self.init_default_ldap_database()

        with self.settings(LDAP_EMAIL_ATTR="mail"):
            self.check_able_to_create_realm(
                "newuser_email@zulip.com", self.ldap_password("newuser_with_email")
            )

    def test_create_realm_as_system_bot(self) -> None:
        result = self.submit_realm_creation_form(
            email="notification-bot@zulip.com",
            realm_subdomain="custom-test",
            realm_name="Zulip test",
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("notification-bot@zulip.com is reserved for system bots", result)

    def test_create_realm_no_creation_key(self) -> None:
        """
        Trying to create a realm without a creation_key should fail when
        OPEN_REALM_CREATION is false.
        """
        email = "user1@test.com"

        with self.settings(OPEN_REALM_CREATION=False):
            # Create new realm with the email, but no creation key.
            result = self.submit_realm_creation_form(
                email, realm_subdomain="custom-test", realm_name="Zulip test"
            )
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("Organization creation link required", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_subdomain(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(
            email, email_body_contains="Organization URL"
        )
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://custom-test.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        self.assertEqual(get_user(email, realm).realm, realm)

        self.assertEqual(realm.name, realm_name)
        self.assertEqual(realm.subdomain, string_id)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_marketing_emails_enabled(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
            enable_marketing_emails=True,
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://custom-test.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)
        self.assertTrue(user.enable_marketing_emails)

    @override_settings(OPEN_REALM_CREATION=True, CORPORATE_ENABLED=False)
    def test_create_realm_without_prompting_for_marketing_emails(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        # Simulate the initial POST that is made by confirm-preregistration.js
        # by triggering submit on confirm_preregistration.html.
        payload = {
            "full_name": "",
            "key": find_key_by_email(email),
            "from_confirmation": "1",
        }
        result = self.client_post("/realm/register/", payload)
        # Assert that the form did not prompt the user for enabling
        # marketing emails.
        self.assert_not_in_success_response(['input id="id_enable_marketing_emails"'], result)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://custom-test.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)
        self.assertFalse(user.enable_marketing_emails)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_marketing_emails_disabled(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Zulip test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
            enable_marketing_emails=False,
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://custom-test.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)
        self.assertFalse(user.enable_marketing_emails)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_regular_realm_welcome_bot_direct_message(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Create new realm with the email.
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
            enable_marketing_emails=False,
        )
        self.assertEqual(result.status_code, 302)

        # Make sure the correct Welcome Bot direct message is sent.
        welcome_msg = Message.objects.filter(
            realm_id=get_realm(string_id).id,
            sender__email="welcome-bot@zulip.com",
            recipient__type=Recipient.PERSONAL,
        ).latest("id")
        self.assertTrue(welcome_msg.content.startswith("Hello, and welcome to Zulip!"))

        # Organization type is not education or education_nonprofit,
        # and organization is not a demo organization.
        self.assertIn("Getting started guide", welcome_msg.content)
        self.assertNotIn("Using Zulip for a class guide", welcome_msg.content)
        self.assertNotIn("demo organization", welcome_msg.content)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_education_demo_organization_welcome_bot_direct_message(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Create new realm with the email.
        result = self.submit_realm_creation_form(
            email,
            realm_subdomain=string_id,
            realm_name=realm_name,
            realm_type=Realm.ORG_TYPES["education"]["id"],
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=35&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
            enable_marketing_emails=False,
            realm_type=Realm.ORG_TYPES["education"]["id"],
            is_demo_organization=True,
        )
        self.assertEqual(result.status_code, 302)

        # Make sure the correct Welcome Bot direct message is sent.
        welcome_msg = Message.objects.filter(
            realm_id=get_realm(string_id).id,
            sender__email="welcome-bot@zulip.com",
            recipient__type=Recipient.PERSONAL,
        ).latest("id")
        self.assertTrue(welcome_msg.content.startswith("Hello, and welcome to Zulip!"))

        # Organization type is education, and organization is a demo organization.
        self.assertNotIn("Getting started guide", welcome_msg.content)
        self.assertIn("Using Zulip for a class guide", welcome_msg.content)
        self.assertIn("demo organization", welcome_msg.content)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_custom_language(self) -> None:
        email = "user1@test.com"
        password = "test"
        string_id = "custom-test"
        realm_name = "Zulip Test"
        realm_language = "it"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email,
            realm_subdomain=string_id,
            realm_name=realm_name,
            realm_default_language=realm_language,
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language={realm_language}&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        prereg_realm = PreregistrationRealm.objects.get(email=email)
        # Check default_language field of PreregistrationRealm object
        self.assertEqual(prereg_realm.default_language, realm_language)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
            realm_default_language=realm_language,
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://custom-test.testserver")

        # Make sure the realm is created and check default_language field
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        self.assertEqual(realm.default_language, realm_language)

        # TODO: When Italian translated strings are updated for changes
        # that are part of the stream -> channel rename, uncomment below.
        # # Check welcome messages
        # with_the_topic_in_italian = "con l'argomento"
        # private_stream_in_italian = "canale privato"

        # for stream_name, text, message_count in [
        #     (Realm.DEFAULT_NOTIFICATION_STREAM_NAME, with_the_topic_in_italian, 4),
        #     (Realm.INITIAL_PRIVATE_STREAM_NAME, private_stream_in_italian, 1),
        # ]:
        #     stream = get_stream(stream_name, realm)
        #     recipient = stream.recipient
        #     messages = Message.objects.filter(realm_id=realm.id, recipient=recipient).order_by(
        #         "date_sent"
        #     )
        #     self.assert_length(messages, message_count)
        #     self.assertIn(text, messages[0].content)

    @override_settings(OPEN_REALM_CREATION=True, CLOUD_FREE_TRIAL_DAYS=30)
    def test_create_realm_during_free_trial(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        confirmation_url = self.get_confirmation_url_from_outbox(
            email, email_body_contains="Organization URL"
        )
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result["Location"], "http://custom-test.testserver/upgrade/")

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assert_in_success_response(["Your card will not be charged", "free trial"], result)

        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        self.assertEqual(get_user(email, realm).realm, realm)

        self.assertEqual(realm.name, realm_name)
        self.assertEqual(realm.subdomain, string_id)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_two_realms(self) -> None:
        """
        Verify correct behavior and PreregistrationRealm handling when using
        two pre-generated realm creation links to create two different realms.
        """
        password = "test"
        first_string_id = "custom-test"
        second_string_id = "custom-test2"
        email = "user1@test.com"
        first_realm_name = "Test"
        second_realm_name = "Test"

        # Make sure the realms do not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(first_string_id)
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(second_string_id)

        # Now we pre-generate two realm creation links
        result = self.submit_realm_creation_form(
            email, realm_subdomain=first_string_id, realm_name=first_realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(first_realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={first_string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        first_confirmation_url = self.get_confirmation_url_from_outbox(
            email, email_body_contains="Organization URL"
        )
        self.assertEqual(PreregistrationRealm.objects.filter(email=email, status=0).count(), 1)

        result = self.submit_realm_creation_form(
            email, realm_subdomain=second_string_id, realm_name=second_realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(second_realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={second_string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        second_confirmation_url = self.get_confirmation_url_from_outbox(
            email, email_body_contains="Organization URL"
        )

        self.assertNotEqual(first_confirmation_url, second_confirmation_url)
        self.assertEqual(PreregistrationRealm.objects.filter(email=email, status=0).count(), 2)

        # Create and verify the first realm
        result = self.client_get(first_confirmation_url)
        self.assertEqual(result.status_code, 200)
        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=first_string_id,
            realm_name=first_realm_name,
            key=first_confirmation_url.split("/")[-1],
        )
        self.assertEqual(result.status_code, 302)
        # Make sure the realm is created
        realm = get_realm(first_string_id)
        self.assertEqual(realm.string_id, first_string_id)
        self.assertEqual(realm.name, first_realm_name)

        # One of the PreregistrationRealm should have been used up:
        self.assertEqual(PreregistrationRealm.objects.filter(email=email, status=0).count(), 1)

        # Create and verify the second realm
        result = self.client_get(second_confirmation_url)
        self.assertEqual(result.status_code, 200)
        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=second_string_id,
            realm_name=second_realm_name,
            key=second_confirmation_url.split("/")[-1],
        )
        self.assertEqual(result.status_code, 302)
        # Make sure the realm is created
        realm = get_realm(second_string_id)
        self.assertEqual(realm.string_id, second_string_id)
        self.assertEqual(realm.name, second_realm_name)

        # The remaining PreregistrationRealm should have been used up:
        self.assertEqual(PreregistrationRealm.objects.filter(email=email, status=0).count(), 0)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_invalid_email_signup(self) -> None:
        result = self.submit_realm_creation_form(
            email="<foo", realm_subdomain="custom-test", realm_name="Zulip test"
        )
        self.assert_in_response("Please use your real email address.", result)

        result = self.submit_realm_creation_form(
            email="foo\x00bar", realm_subdomain="custom-test", realm_name="Zulip test"
        )
        self.assert_in_response("Please use your real email address.", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_mailinator_signup(self) -> None:
        result = self.client_post("/new/", {"email": "hi@mailinator.com"})
        self.assert_in_response("Please use your real email address.", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        errors = {
            "id": "length 3 or greater",
            "-id": "cannot start or end with a",
            "string-ID": "lowercase letters",
            "string_id": "lowercase letters",
            "stream": "reserved",
            "streams": "reserved",
            "about": "reserved",
            "abouts": "reserved",
            "zephyr": "already in use",
        }
        for string_id, error_msg in errors.items():
            result = self.submit_realm_creation_form(
                email, realm_subdomain=string_id, realm_name=realm_name
            )
            self.assert_in_response(error_msg, result)

        # test valid subdomain
        result = self.submit_realm_creation_form(
            email, realm_subdomain="a-0", realm_name=realm_name
        )
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain="a-0", realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith("http://a-0.testserver/accounts/login/subdomain/")
        )

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_using_old_subdomain_of_a_realm(self) -> None:
        realm = get_realm("zulip")
        do_change_realm_subdomain(realm, "new-name", acting_user=None)

        email = "user1@test.com"

        result = self.submit_realm_creation_form(email, realm_subdomain="test", realm_name="Test")
        self.assert_in_response("Subdomain reserved. Please choose a different one.", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions_root_domain(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        # test root domain will fail with ROOT_DOMAIN_LANDING_PAGE
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.submit_realm_creation_form(
                email, realm_subdomain="", realm_name=realm_name
            )
            self.assert_in_response("already in use", result)

        # test valid use of root domain
        result = self.submit_realm_creation_form(email, realm_subdomain="", realm_name=realm_name)
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain="", realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith("http://testserver/accounts/login/subdomain/")
        )

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions_root_domain_option(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        # test root domain will fail with ROOT_DOMAIN_LANDING_PAGE
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.submit_realm_creation_form(
                email, realm_subdomain="abcdef", realm_name=realm_name, realm_in_root_domain="true"
            )
            self.assert_in_response("already in use", result)

        # test valid use of root domain
        result = self.submit_realm_creation_form(
            email, realm_subdomain="abcdef", realm_name=realm_name, realm_in_root_domain="true"
        )

        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain="abcdef",
            realm_in_root_domain="true",
            realm_name=realm_name,
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith("http://testserver/accounts/login/subdomain/")
        )

    def test_is_root_domain_available(self) -> None:
        self.assertTrue(is_root_domain_available())
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            self.assertFalse(is_root_domain_available())
        realm = get_realm("zulip")
        realm.string_id = Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
        realm.save()
        self.assertFalse(is_root_domain_available())

    def test_subdomain_check_api(self) -> None:
        result = self.client_get("/json/realm/subdomain/zulip")
        self.assert_in_success_response(
            ["Subdomain already in use. Please choose a different one."], result
        )

        result = self.client_get("/json/realm/subdomain/zu_lip")
        self.assert_in_success_response(
            ["Subdomain can only have lowercase letters, numbers, and '-'s."], result
        )

        with self.settings(SOCIAL_AUTH_SUBDOMAIN="zulipauth"):
            result = self.client_get("/json/realm/subdomain/zulipauth")
            self.assert_in_success_response(
                ["Subdomain reserved. Please choose a different one."], result
            )

        with self.settings(SELF_HOSTING_MANAGEMENT_SUBDOMAIN="zulipselfhosting"):
            result = self.client_get("/json/realm/subdomain/zulipselfhosting")
            self.assert_in_success_response(
                ["Subdomain reserved. Please choose a different one."], result
            )

        result = self.client_get("/json/realm/subdomain/hufflepuff")
        self.assert_in_success_response(["available"], result)
        self.assert_not_in_success_response(["already in use"], result)
        self.assert_not_in_success_response(["reserved"], result)

    def test_subdomain_check_management_command(self) -> None:
        # Short names should not work, even with the flag
        with self.assertRaises(ValidationError):
            check_subdomain_available("aa")
        with self.assertRaises(ValidationError):
            check_subdomain_available("aa", allow_reserved_subdomain=True)

        # Malformed names should never work
        with self.assertRaises(ValidationError):
            check_subdomain_available("-ba_d-")
        with self.assertRaises(ValidationError):
            check_subdomain_available("-ba_d-", allow_reserved_subdomain=True)

        with patch("zerver.lib.name_restrictions.is_reserved_subdomain", return_value=False):
            # Existing realms should never work even if they are not reserved keywords
            with self.assertRaises(ValidationError):
                check_subdomain_available("zulip")
            with self.assertRaises(ValidationError):
                check_subdomain_available("zulip", allow_reserved_subdomain=True)

        # Reserved ones should only work with the flag
        with self.assertRaises(ValidationError):
            check_subdomain_available("stream")
        check_subdomain_available("stream", allow_reserved_subdomain=True)

        # "zulip" and "kandra" are allowed if not CORPORATE_ENABLED or with the flag
        with self.settings(CORPORATE_ENABLED=False):
            check_subdomain_available("we-are-zulip-team")
        with self.settings(CORPORATE_ENABLED=True):
            with self.assertRaises(ValidationError):
                check_subdomain_available("we-are-zulip-team")
            check_subdomain_available("we-are-zulip-team", allow_reserved_subdomain=True)


class UserSignUpTest(ZulipTestCase):
    def verify_signup(
        self,
        *,
        email: str = "newguy@zulip.com",
        password: Optional[str] = "newpassword",
        full_name: str = "New user's name",
        realm: Optional[Realm] = None,
        subdomain: Optional[str] = None,
    ) -> Union[UserProfile, "TestHttpResponse"]:
        """Common test function for signup tests.  It is a goal to use this
        common function for all signup tests to avoid code duplication; doing
        so will likely require adding new parameters."""

        if realm is None:  # nocoverage
            realm = get_realm("zulip")

        client_kwargs: Dict[str, Any] = {}
        if subdomain:
            client_kwargs["subdomain"] = subdomain

        result = self.client_post("/accounts/home/", {"email": email}, **client_kwargs)
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"], **client_kwargs)
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(
            email, email_body_contains="You recently signed up for Zulip. Awesome!"
        )
        result = self.client_get(confirmation_url, **client_kwargs)
        self.assertEqual(result.status_code, 200)

        # Pick a password and agree to the ToS. This should create our
        # account, log us in, and redirect to the app.
        result = self.submit_reg_form_for_user(
            email, password, full_name=full_name, **client_kwargs
        )

        if result.status_code == 200:
            # This usually indicated an error returned when submitting the form.
            # Return the result for the caller to deal with reacting to this, since
            # in many tests this is expected and the caller wants to assert the content
            # of the error.
            return result

        # Verify that we were served a redirect to the app.
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{realm.uri}/")

        # Verify that we successfully logged in.
        user_profile = get_user_by_delivery_email(email, realm)
        self.assert_logged_in_user_id(user_profile.id)
        return user_profile

    @override_settings(CORPORATE_ENABLED=False)
    def test_bad_email_configuration_for_accounts_home(self) -> None:
        """
        Make sure we show an error page for EmailNotDeliveredError.
        """
        email = self.nonreg_email("newguy")

        smtp_mock = patch(
            "zerver.views.registration.send_confirm_registration_email",
            side_effect=EmailNotDeliveredError,
        )

        with smtp_mock, self.assertLogs(level="ERROR") as m:
            result = self.client_post("/accounts/home/", {"email": email})

        self.assertEqual(result.status_code, 500)
        self.assert_in_response(
            "https://zulip.readthedocs.io/en/latest/subsystems/email.html", result
        )
        self.assertTrue(
            "ERROR:root:Failed to deliver email during user registration" in m.output[0]
        )

    @override_settings(CORPORATE_ENABLED=True)
    def test_bad_email_configuration_for_corporate_accounts_home(self) -> None:
        """
        This should show a generic 500.
        """
        email = self.nonreg_email("newguy")

        smtp_mock = patch(
            "zerver.views.registration.send_confirm_registration_email",
            side_effect=EmailNotDeliveredError,
        )

        with smtp_mock, self.assertLogs(level="ERROR") as m:
            result = self.client_post("/accounts/home/", {"email": email})

        self.assertEqual(result.status_code, 500)
        self.assertNotIn(
            "https://zulip.readthedocs.io/en/latest/subsystems/email.html", result.content.decode()
        )
        self.assert_in_response("server is experiencing technical difficulties", result)
        self.assertTrue(
            "ERROR:root:Failed to deliver email during user registration" in m.output[0]
        )

    @override_settings(CORPORATE_ENABLED=False)
    def test_bad_email_configuration_for_create_realm(self) -> None:
        """
        Make sure we show an error page for EmailNotDeliveredError.
        """
        email = self.nonreg_email("newguy")

        smtp_mock = patch(
            "zerver.views.registration.send_confirm_registration_email",
            side_effect=EmailNotDeliveredError,
        )

        with smtp_mock, self.assertLogs(level="ERROR") as m:
            result = self.submit_realm_creation_form(
                email, realm_subdomain="custom-test", realm_name="Zulip test"
            )

        self.assertEqual(result.status_code, 500)
        self.assert_in_response(
            "https://zulip.readthedocs.io/en/latest/subsystems/email.html", result
        )
        self.assertTrue("ERROR:root:Failed to deliver email during realm creation" in m.output[0])

    @override_settings(CORPORATE_ENABLED=True)
    def test_bad_email_configuration_for_corporate_create_realm(self) -> None:
        """
        This should show a generic 500.
        """
        email = self.nonreg_email("newguy")

        smtp_mock = patch(
            "zerver.views.registration.send_confirm_registration_email",
            side_effect=EmailNotDeliveredError,
        )

        with smtp_mock, self.assertLogs(level="ERROR") as m:
            result = self.submit_realm_creation_form(
                email, realm_subdomain="custom-test", realm_name="Zulip test"
            )

        self.assertEqual(result.status_code, 500)
        self.assertNotIn(
            "https://zulip.readthedocs.io/en/latest/subsystems/email.html", result.content.decode()
        )
        self.assert_in_response("server is experiencing technical difficulties", result)
        self.assertTrue("ERROR:root:Failed to deliver email during realm creation" in m.output[0])

    def test_user_default_language_and_timezone(self) -> None:
        """
        Check if the default language of new user is set using the browser locale
        """
        email = self.nonreg_email("newguy")
        password = "newpassword"
        timezone = "America/Denver"
        realm = get_realm("zulip")
        do_set_realm_property(realm, "default_language", "de", acting_user=None)

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        # Pick a password and agree to the ToS.
        result = self.submit_reg_form_for_user(
            email, password, timezone=timezone, HTTP_ACCEPT_LANGUAGE="fr,en;q=0.9"
        )
        self.assertEqual(result.status_code, 302)

        user_profile = self.nonreg_user("newguy")
        self.assertNotEqual(user_profile.default_language, realm.default_language)
        self.assertEqual(user_profile.default_language, "fr")
        self.assertEqual(user_profile.timezone, timezone)
        from django.core.mail import outbox

        outbox.pop()

    def test_default_language_with_unsupported_browser_locale(self) -> None:
        email = self.nonreg_email("newguy")
        password = "newpassword"
        realm = get_realm("zulip")
        do_set_realm_property(realm, "default_language", "de", acting_user=None)

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        # Pick a password and agree to the ToS.
        result = self.submit_reg_form_for_user(email, password, HTTP_ACCEPT_LANGUAGE="en-IND")
        self.assertEqual(result.status_code, 302)

        user_profile = self.nonreg_user("newguy")
        self.assertEqual(user_profile.default_language, realm.default_language)
        from django.core.mail import outbox

        outbox.pop()

    def test_default_twenty_four_hour_time(self) -> None:
        """
        Check if the default twenty_four_hour_time setting of new user
        is the default twenty_four_hour_time of the realm.
        """
        email = self.nonreg_email("newguy")
        password = "newpassword"
        realm = get_realm("zulip")
        realm_user_default = RealmUserDefault.objects.get(realm=realm)
        do_set_realm_user_default_setting(
            realm_user_default, "twenty_four_hour_time", True, acting_user=None
        )

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(email, password)
        self.assertEqual(result.status_code, 302)

        user_profile = self.nonreg_user("newguy")
        realm_user_default = RealmUserDefault.objects.get(realm=realm)
        self.assertEqual(
            user_profile.twenty_four_hour_time, realm_user_default.twenty_four_hour_time
        )

    def test_email_address_visibility_for_new_user(self) -> None:
        email = self.nonreg_email("newguy")
        password = "newpassword"
        realm = get_realm("zulip")
        realm_user_default = RealmUserDefault.objects.get(realm=realm)
        self.assertEqual(
            realm_user_default.email_address_visibility, UserProfile.EMAIL_ADDRESS_VISIBILITY_ADMINS
        )

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        # Pick a password and agree to the ToS.
        result = self.submit_reg_form_for_user(
            email, password, email_address_visibility=UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY
        )
        self.assertEqual(result.status_code, 302)

        # Realm-level default is overridden by the value passed during signup.
        user_profile = self.nonreg_user("newguy")
        self.assertEqual(
            user_profile.email_address_visibility, UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY
        )
        from django.core.mail import outbox

        outbox.pop()

    def test_signup_already_active(self) -> None:
        """
        Check if signing up with an active email redirects to a login page.
        """
        email = self.example_email("hamlet")
        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertIn("login", result["Location"])
        result = self.client_get(result["Location"])
        self.assert_in_response("You've already registered", result)

    def test_signup_system_bot(self) -> None:
        email = "notification-bot@zulip.com"
        result = self.client_post("/accounts/home/", {"email": email}, subdomain="lear")
        self.assertEqual(result.status_code, 302)
        self.assertIn("login", result["Location"])
        result = self.client_get(result["Location"])

        # This is not really the right error message, but at least it's an error.
        self.assert_in_response("You've already registered", result)

    def test_signup_existing_email(self) -> None:
        """
        Check if signing up with an email used in another realm succeeds.
        """
        email = self.example_email("hamlet")
        self.verify_signup(email=email, realm=get_realm("lear"), subdomain="lear")
        self.assertEqual(UserProfile.objects.filter(delivery_email=email).count(), 2)

    def test_signup_invalid_name(self) -> None:
        """
        Check if an invalid name during signup is handled properly.
        """

        result = self.verify_signup(full_name="<invalid>")
        # _WSGIPatchedWSGIResponse does not exist in Django, thus the inverted isinstance check.
        assert not isinstance(result, UserProfile)
        self.assert_in_success_response(["Invalid characters in name!"], result)

        # Verify that the user is asked for name and password
        self.assert_in_success_response(["id_password", "id_full_name"], result)

    def test_signup_with_existing_name(self) -> None:
        """
        Check if signing up with an existing name when organization
        has set "Require Unique Names"is handled properly.
        """

        iago = self.example_user("iago")
        email = "newguy@zulip.com"
        password = "newpassword"

        do_set_realm_property(iago.realm, "require_unique_names", True, acting_user=None)
        result = self.verify_signup(email=email, password=password, full_name="IaGo")
        assert not isinstance(result, UserProfile)
        self.assert_in_success_response(["Unique names required in this organization."], result)

        do_set_realm_property(iago.realm, "require_unique_names", False, acting_user=None)
        result = self.verify_signup(email=email, password=password, full_name="IaGo")
        assert isinstance(result, UserProfile)

    def test_signup_without_password(self) -> None:
        """
        Check if signing up without a password works properly when
        password_auth_enabled is False.
        """
        email = self.nonreg_email("newuser")
        with patch("zerver.views.registration.password_auth_enabled", return_value=False):
            user_profile = self.verify_signup(email=email, password=None)

        assert isinstance(user_profile, UserProfile)
        # User should now be logged in.
        self.assert_logged_in_user_id(user_profile.id)

    def test_signup_without_full_name(self) -> None:
        """
        Check if signing up without a full name redirects to a registration
        form.
        """
        email = "newguy@zulip.com"
        password = "newpassword"
        result = self.verify_signup(email=email, password=password, full_name="")
        # _WSGIPatchedWSGIResponse does not exist in Django, thus the inverted isinstance check.
        assert not isinstance(result, UserProfile)
        self.assert_in_success_response(
            ["Enter your account details to complete registration."], result
        )

        # Verify that the user is asked for name and password
        self.assert_in_success_response(["id_password", "id_full_name"], result)

    def test_signup_email_message_contains_org_header(self) -> None:
        email = "newguy@zulip.com"

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        from django.core.mail import outbox

        self.assertEqual(outbox[0].extra_headers["List-Id"], "Zulip Dev <zulip.testserver>")

    def test_correct_signup(self) -> None:
        """
        Verify the happy path of signing up with name and email address.
        """
        email = "newguy@zulip.com"
        password = "newpassword"

        result = self.verify_signup(email=email, password=password)
        assert isinstance(result, UserProfile)

    def test_signup_with_email_address_race(self) -> None:
        """
        The check for if an email is in use can race with other user
        creation; it is caught by database uniqueness rules.  Verify
        that that is transformed into a redirect to log into the
        account.
        """
        email = "newguy@zulip.com"
        password = "newpassword"

        self.client_post("/accounts/home/", {"email": email})
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)
        self.client_post(
            "/accounts/register/",
            {
                "password": password,
                "key": find_key_by_email(email),
                "terms": True,
                "full_name": "New Guy",
                "from_confirmation": "1",
            },
        )
        with patch("zerver.actions.create_user.create_user", side_effect=IntegrityError):
            result = self.submit_reg_form_for_user(email, "easy", full_name="New Guy")
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/login/?email={quote(email)}&already_registered=1"
            )
        )

    def test_signup_with_weak_password(self) -> None:
        """
        Check if signing up with a weak password fails.
        """
        email = "newguy@zulip.com"

        with self.settings(PASSWORD_MIN_LENGTH=6, PASSWORD_MIN_GUESSES=1000):
            result = self.verify_signup(email=email, password="easy")
            # _WSGIPatchedWSGIResponse does not exist in Django, thus the inverted isinstance check.
            assert not isinstance(result, UserProfile)
            self.assert_in_success_response(["The password is too weak."], result)
            with self.assertRaises(UserProfile.DoesNotExist):
                # Account wasn't created.
                get_user(email, get_realm("zulip"))

    def test_signup_with_default_stream_group(self) -> None:
        # Check if user is subscribed to the streams of default
        # stream group as well as default streams.
        email = self.nonreg_email("newguy")
        password = "newpassword"
        realm = get_realm("zulip")

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"])

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        default_streams = []

        existing_default_streams = DefaultStream.objects.filter(realm=realm)
        self.assert_length(existing_default_streams, 1)
        self.assertEqual(existing_default_streams[0].stream.name, "Verona")
        default_streams.append(existing_default_streams[0].stream)

        for stream_name in ["venice", "rome"]:
            stream = get_stream(stream_name, realm)
            do_add_default_stream(stream)
            default_streams.append(stream)

        group1_streams = []
        for stream_name in ["scotland", "denmark"]:
            stream = get_stream(stream_name, realm)
            group1_streams.append(stream)
        do_create_default_stream_group(realm, "group 1", "group 1 description", group1_streams)

        result = self.submit_reg_form_for_user(email, password, default_stream_groups=["group 1"])
        self.check_user_subscribed_only_to_streams("newguy", default_streams + group1_streams)

    def test_signup_two_confirmation_links(self) -> None:
        email = self.nonreg_email("newguy")
        password = "newpassword"

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"])
        first_confirmation_url = self.get_confirmation_url_from_outbox(email)
        first_confirmation_key = find_key_by_email(email)

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"])
        second_confirmation_url = self.get_confirmation_url_from_outbox(email)

        # Sanity check:
        self.assertNotEqual(first_confirmation_url, second_confirmation_url)

        # Register the account (this will use the second confirmation url):
        result = self.submit_reg_form_for_user(
            email, password, full_name="New Guy", from_confirmation="1"
        )
        self.assert_in_success_response(
            ["Enter your account details to complete registration.", "New Guy", email], result
        )
        result = self.submit_reg_form_for_user(email, password, full_name="New Guy")
        user_profile = UserProfile.objects.get(delivery_email=email)
        self.assertEqual(user_profile.delivery_email, email)

        # Now try to to register using the first confirmation url:
        result = self.client_get(first_confirmation_url)
        self.assertEqual(result.status_code, 404)
        result = self.client_post(
            "/accounts/register/",
            {
                "password": password,
                "key": first_confirmation_key,
                "terms": True,
                "full_name": "New Guy",
                "from_confirmation": "1",
            },
        )
        # Error page should be displayed
        self.assertEqual(result.status_code, 404)
        self.assert_in_response(
            "Whoops. The confirmation link has expired or been deactivated.", result
        )

    def test_signup_with_multiple_default_stream_groups(self) -> None:
        # Check if user is subscribed to the streams of default
        # stream groups as well as default streams.
        email = self.nonreg_email("newguy")
        password = "newpassword"
        realm = get_realm("zulip")

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"])

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        DefaultStream.objects.filter(realm=realm).delete()
        default_streams = []
        for stream_name in ["venice", "verona"]:
            stream = get_stream(stream_name, realm)
            do_add_default_stream(stream)
            default_streams.append(stream)

        group1_streams = []
        for stream_name in ["scotland", "denmark"]:
            stream = get_stream(stream_name, realm)
            group1_streams.append(stream)
        do_create_default_stream_group(realm, "group 1", "group 1 description", group1_streams)

        group2_streams = []
        for stream_name in ["scotland", "rome"]:
            stream = get_stream(stream_name, realm)
            group2_streams.append(stream)
        do_create_default_stream_group(realm, "group 2", "group 2 description", group2_streams)

        result = self.submit_reg_form_for_user(
            email, password, default_stream_groups=["group 1", "group 2"]
        )
        self.check_user_subscribed_only_to_streams(
            "newguy", list(set(default_streams + group1_streams + group2_streams))
        )

    def test_signup_without_user_settings_from_another_realm(self) -> None:
        hamlet_in_zulip = self.example_user("hamlet")
        email = hamlet_in_zulip.delivery_email
        password = "newpassword"
        subdomain = "lear"
        realm = get_realm("lear")

        # Make an account in the Zulip realm, but we're not copying from there.
        hamlet_in_zulip.left_side_userlist = True
        hamlet_in_zulip.default_language = "de"
        hamlet_in_zulip.emojiset = "twitter"
        hamlet_in_zulip.high_contrast_mode = True
        hamlet_in_zulip.enter_sends = True
        hamlet_in_zulip.tutorial_status = UserProfile.TUTORIAL_FINISHED
        hamlet_in_zulip.email_address_visibility = UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE
        hamlet_in_zulip.save()

        result = self.client_post("/accounts/home/", {"email": email}, subdomain=subdomain)
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"], subdomain=subdomain)

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url, subdomain=subdomain)
        self.assertEqual(result.status_code, 200)
        result = self.submit_reg_form_for_user(
            email, password, source_realm_id="", HTTP_HOST=subdomain + ".testserver"
        )

        hamlet = get_user(self.example_email("hamlet"), realm)
        self.assertEqual(hamlet.left_side_userlist, False)
        self.assertEqual(hamlet.default_language, "en")
        self.assertEqual(hamlet.emojiset, "google")
        self.assertEqual(hamlet.high_contrast_mode, False)
        self.assertEqual(hamlet.enable_stream_audible_notifications, False)
        self.assertEqual(hamlet.enter_sends, False)
        self.assertEqual(hamlet.tutorial_status, UserProfile.TUTORIAL_WAITING)

    def test_signup_with_user_settings_from_another_realm(self) -> None:
        hamlet_in_zulip = self.example_user("hamlet")
        email = hamlet_in_zulip.delivery_email
        password = "newpassword"
        subdomain = "lear"
        lear_realm = get_realm("lear")

        self.login("hamlet")
        with get_test_image_file("img.png") as image_file:
            self.client_post("/json/users/me/avatar", {"file": image_file})
        hamlet_in_zulip.refresh_from_db()
        hamlet_in_zulip.left_side_userlist = True
        hamlet_in_zulip.default_language = "de"
        hamlet_in_zulip.emojiset = "twitter"
        hamlet_in_zulip.high_contrast_mode = True
        hamlet_in_zulip.enter_sends = True
        hamlet_in_zulip.tutorial_status = UserProfile.TUTORIAL_FINISHED
        hamlet_in_zulip.email_address_visibility = UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE
        hamlet_in_zulip.save()

        # Now we'll be making requests to another subdomain, so we need to logout
        # to avoid polluting the session in the test environment by still being
        # logged in.
        self.logout()

        result = self.client_post("/accounts/home/", {"email": email}, subdomain=subdomain)
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"], subdomain=subdomain)

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url, subdomain=subdomain)
        self.assertEqual(result.status_code, 200)

        result = self.client_post(
            "/accounts/register/",
            {"password": password, "key": find_key_by_email(email), "from_confirmation": "1"},
            subdomain=subdomain,
        )
        self.assert_in_success_response(
            [
                "Import settings from existing Zulip account",
                "selected >\n                                Zulip Dev",
                "Enter your account details to complete registration.",
            ],
            result,
        )

        result = self.submit_reg_form_for_user(
            email,
            password,
            source_realm_id=str(hamlet_in_zulip.realm.id),
            HTTP_HOST=subdomain + ".testserver",
            email_address_visibility=UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY,
        )

        hamlet_in_lear = get_user_by_delivery_email(email, lear_realm)
        self.assertEqual(hamlet_in_lear.left_side_userlist, True)
        self.assertEqual(hamlet_in_lear.default_language, "de")
        self.assertEqual(hamlet_in_lear.emojiset, "twitter")
        self.assertEqual(hamlet_in_lear.high_contrast_mode, True)
        self.assertEqual(hamlet_in_lear.enter_sends, True)
        self.assertEqual(hamlet_in_lear.enable_stream_audible_notifications, False)
        self.assertEqual(hamlet_in_lear.tutorial_status, UserProfile.TUTORIAL_FINISHED)
        self.assertEqual(
            hamlet_in_lear.email_address_visibility, UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY
        )

        zulip_path_id = avatar_disk_path(hamlet_in_zulip)
        lear_path_id = avatar_disk_path(hamlet_in_lear)
        with open(zulip_path_id, "rb") as f:
            zulip_avatar_bits = f.read()
        with open(lear_path_id, "rb") as f:
            lear_avatar_bits = f.read()

        self.assertGreater(len(zulip_avatar_bits), 500)
        self.assertEqual(zulip_avatar_bits, lear_avatar_bits)

    def test_signup_invalid_subdomain(self) -> None:
        """
        Check if attempting to authenticate to the wrong subdomain logs an
        error and redirects.
        """
        email = "newuser@zulip.com"
        password = "newpassword"

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        def invalid_subdomain(**kwargs: Any) -> Any:
            return_data = kwargs.get("return_data", {})
            return_data["invalid_subdomain"] = True

        with patch("zerver.views.registration.authenticate", side_effect=invalid_subdomain):
            with self.assertLogs(level="ERROR") as m:
                result = self.client_post(
                    "/accounts/register/",
                    {
                        "password": password,
                        "full_name": "New User",
                        "key": find_key_by_email(email),
                        "terms": True,
                    },
                )
                self.assertEqual(
                    m.output,
                    ["ERROR:root:Subdomain mismatch in registration zulip: newuser@zulip.com"],
                )
        self.assertEqual(result.status_code, 302)

    def test_signup_using_invalid_subdomain_preserves_state_of_form(self) -> None:
        """
        Check that when we give invalid subdomain and submit the registration form
        all the values in the form are preserved.
        """
        realm = get_realm("zulip")

        email = self.example_email("iago")
        realm_name = "Test"

        result = self.submit_realm_creation_form(
            email, realm_subdomain=realm.string_id, realm_name=realm_name
        )
        self.assert_in_success_response(
            [
                "Subdomain already in use. Please choose a different one.",
                'value="Test"',
                'name="realm_name"',
            ],
            result,
        )

    def test_replace_subdomain_in_confirmation_link(self) -> None:
        """
        Check that manually changing the subdomain in a registration
        confirmation link doesn't allow you to register to a different realm.
        """
        email = "newuser@zulip.com"
        self.client_post("/accounts/home/", {"email": email})
        result = self.client_post(
            "/accounts/register/",
            {
                "password": "password",
                "key": find_key_by_email(email),
                "terms": True,
                "full_name": "New User",
                "from_confirmation": "1",
            },
            subdomain="zephyr",
        )
        self.assertEqual(result.status_code, 404)
        self.assert_in_response("We couldn't find your confirmation link", result)

    def test_signup_to_realm_on_manual_license_plan(self) -> None:
        realm = get_realm("zulip")
        admin_user_ids = set(realm.get_human_admin_users().values_list("id", flat=True))
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, realm.id)
        expected_group_direct_message_user_ids = admin_user_ids | {notification_bot.id}

        _, ledger = self.subscribe_realm_to_monthly_plan_on_manual_license_management(realm, 5, 5)

        with self.settings(BILLING_ENABLED=True):
            form = HomepageForm({"email": self.nonreg_email("test")}, realm=realm)
            self.assertIn(
                "New members cannot join this organization because all Zulip licenses",
                form.errors["email"][0],
            )
            last_message = Message.objects.last()
            assert last_message is not None
            self.assertIn(
                f"A new member ({self.nonreg_email('test')}) was unable to join your organization because all Zulip",
                last_message.content,
            )
            self.assertEqual(
                set(get_huddle_user_ids(last_message.recipient)),
                expected_group_direct_message_user_ids,
            )

        ledger.licenses_at_next_renewal = 50
        ledger.save(update_fields=["licenses_at_next_renewal"])
        with self.settings(BILLING_ENABLED=True):
            form = HomepageForm({"email": self.nonreg_email("test")}, realm=realm)
            self.assertIn(
                "New members cannot join this organization because all Zulip licenses",
                form.errors["email"][0],
            )

        ledger.licenses = 50
        ledger.save(update_fields=["licenses"])
        with self.settings(BILLING_ENABLED=True):
            form = HomepageForm({"email": self.nonreg_email("test")}, realm=realm)
            self.assertEqual(form.errors, {})

    def test_failed_signup_due_to_restricted_domain(self) -> None:
        realm = get_realm("zulip")
        do_set_realm_property(realm, "invite_required", False, acting_user=None)
        do_set_realm_property(realm, "emails_restricted_to_domains", True, acting_user=None)

        email = "user@acme.com"
        form = HomepageForm({"email": email}, realm=realm)
        self.assertIn(
            f"Your email address, {email}, is not in one of the domains", form.errors["email"][0]
        )

    def test_failed_signup_due_to_disposable_email(self) -> None:
        realm = get_realm("zulip")
        realm.emails_restricted_to_domains = False
        realm.disallow_disposable_email_addresses = True
        realm.save()

        email = "abc@mailnator.com"
        form = HomepageForm({"email": email}, realm=realm)
        self.assertIn("Please use your real email address", form.errors["email"][0])

    def test_failed_signup_due_to_email_containing_plus(self) -> None:
        realm = get_realm("zulip")
        realm.emails_restricted_to_domains = True
        realm.save()

        email = "iago+label@zulip.com"
        form = HomepageForm({"email": email}, realm=realm)
        self.assertIn(
            "Email addresses containing + are not allowed in this organization.",
            form.errors["email"][0],
        )

    def test_failed_signup_due_to_invite_required(self) -> None:
        realm = get_realm("zulip")
        realm.invite_required = True
        realm.save()
        email = "user@zulip.com"
        form = HomepageForm({"email": email}, realm=realm)
        self.assertIn(f"Please request an invite for {email} from", form.errors["email"][0])

    def test_failed_signup_due_to_nonexistent_realm(self) -> None:
        email = "user@acme.com"
        form = HomepageForm({"email": email}, realm=None)
        self.assertIn(
            f"organization you are trying to join using {email} does not exist",
            form.errors["email"][0],
        )

    def test_signup_confirm_injection(self) -> None:
        result = self.client_get("/accounts/send_confirm/?email=bogus@example.com")
        self.assert_in_success_response(
            [
                'check your email account (<span class="user_email semi-bold">bogus@example.com</span>)'
            ],
            result,
        )

        result = self.client_get(
            "/accounts/send_confirm/?email={quote(email)}",
            {"email": "bogus@example.com for example"},
        )
        self.assertEqual(result.status_code, 400)
        self.assert_in_response(
            "The email address you are trying to sign up with is not valid", result
        )

    def test_access_signup_page_in_root_domain_without_realm(self) -> None:
        result = self.client_get("/register", subdomain="", follow=True)
        self.assert_in_success_response(["Find your Zulip accounts"], result)

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_registration_from_confirmation(self) -> None:
        password = self.ldap_password("newuser")
        email = "newuser@zulip.com"
        subdomain = "zulip"
        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}

        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        # Visit the confirmation link.
        from django.core.mail import outbox

        for message in reversed(outbox):
            if email in message.to:
                match = re.search(settings.EXTERNAL_HOST + r"(\S+)>", str(message.body))
                assert match is not None
                [confirmation_url] = match.groups()
                break
        else:
            raise AssertionError("Couldn't find a confirmation email.")

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            result = self.client_get(confirmation_url)
            self.assertEqual(result.status_code, 200)

            # Full name should be set from LDAP
            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Ignore",
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )

            self.assert_in_success_response(
                [
                    "Enter your account details to complete registration.",
                    "New LDAP fullname",
                    "newuser@zulip.com",
                ],
                result,
            )

            # Verify that the user is asked for name
            self.assert_in_success_response(["id_full_name"], result)
            # Verify that user is asked for its LDAP/Active Directory password.
            self.assert_in_success_response(
                ["Enter your LDAP/Active Directory password.", "ldap-password"], result
            )
            self.assert_not_in_success_response(["id_password"], result)

            # Test the TypeError exception handler
            with patch(
                "zproject.backends.ZulipLDAPAuthBackendBase.get_mapped_name", side_effect=TypeError
            ):
                result = self.submit_reg_form_for_user(
                    email,
                    password,
                    from_confirmation="1",
                    # Pass HTTP_HOST for the target subdomain
                    HTTP_HOST=subdomain + ".testserver",
                )
            self.assert_in_success_response(
                ["Enter your account details to complete registration.", "newuser@zulip.com"],
                result,
            )

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.EmailAuthBackend",
            "zproject.backends.ZulipLDAPUserPopulator",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_populate_only_registration_from_confirmation(self) -> None:
        password = self.ldap_password("newuser")
        email = "newuser@zulip.com"
        subdomain = "zulip"
        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}

        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        # Visit the confirmation link.
        from django.core.mail import outbox

        for message in reversed(outbox):
            if email in message.to:
                match = re.search(settings.EXTERNAL_HOST + r"(\S+)>", str(message.body))
                assert match is not None
                [confirmation_url] = match.groups()
                break
        else:
            raise AssertionError("Couldn't find a confirmation email.")

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_BIND_PASSWORD="",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
            AUTH_LDAP_USER_DN_TEMPLATE="uid=%(user)s,ou=users,dc=zulip,dc=com",
        ):
            result = self.client_get(confirmation_url)
            self.assertEqual(result.status_code, 200)

            # Full name should be set from LDAP
            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Ignore",
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )

            self.assert_in_success_response(
                [
                    "Enter your account details to complete registration.",
                    "New LDAP fullname",
                    "newuser@zulip.com",
                ],
                result,
            )

            # Verify that the user is asked for name
            self.assert_in_success_response(["id_full_name"], result)
            # Verify that user is NOT asked for its LDAP/Active Directory password.
            # LDAP is not configured for authentication in this test.
            self.assert_not_in_success_response(
                ["Enter your LDAP/Active Directory password.", "ldap-password"], result
            )
            # If we were using e.g. the SAML auth backend, there
            # shouldn't be a password prompt, but since it uses the
            # EmailAuthBackend, there should be password field here.
            self.assert_in_success_response(["id_password"], result)

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.SAMLAuthBackend",
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_registration_email_backend_disabled_bypass_attempt(self) -> None:
        """
        Tests for the case of LDAP + external auth backend being the ones enabled and
        a user using the registration page to get a confirmation link and then trying
        to use it to create a new account with their own email that's not authenticated
        by either of the backends.
        """
        email = "no_such_user_in_ldap@example.com"
        subdomain = "zulip"

        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}
        full_name = "New LDAP fullname"

        result = self.client_post("/register/", {"email": email}, subdomain=subdomain)

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ), self.assertLogs("zulip.ldap", level="DEBUG") as ldap_logs, self.assertLogs(
            level="WARNING"
        ) as root_logs:
            # Click confirmation link
            result = self.submit_reg_form_for_user(
                email,
                None,
                full_name="Ignore",
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )

            self.assert_in_success_response(
                ["Enter your account details to complete registration.", email], result
            )

            # Submit the final form, attempting to register the user despite
            # no match in ldap.
            result = self.submit_reg_form_for_user(
                email,
                "newpassword",
                full_name=full_name,
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            # Didn't create an account
            with self.assertRaises(UserProfile.DoesNotExist):
                UserProfile.objects.get(delivery_email=email)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(
                result["Location"], "/accounts/login/?email=no_such_user_in_ldap%40example.com"
            )
            self.assertEqual(
                root_logs.output,
                [
                    "WARNING:root:New account email no_such_user_in_ldap@example.com could not be found in LDAP",
                ],
            )
            self.assertEqual(
                ldap_logs.output,
                [
                    "DEBUG:zulip.ldap:ZulipLDAPAuthBackend: Email no_such_user_in_ldap@example.com does not match LDAP domain zulip.com.",
                ],
            )

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_registration_end_to_end(self) -> None:
        password = self.ldap_password("newuser")
        email = "newuser@zulip.com"
        subdomain = "zulip"

        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}
        full_name = "New LDAP fullname"

        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            # Click confirmation link
            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Ignore",
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )

            # Full name should be set from LDAP
            self.assert_in_success_response(
                [
                    "Enter your account details to complete registration.",
                    full_name,
                    "newuser@zulip.com",
                ],
                result,
            )

            # Submit the final form with the wrong password.
            result = self.submit_reg_form_for_user(
                email,
                "wrongpassword",
                full_name=full_name,
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            # Didn't create an account
            with self.assertRaises(UserProfile.DoesNotExist):
                user_profile = UserProfile.objects.get(delivery_email=email)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "/accounts/login/?email=newuser%40zulip.com")

            # Submit the final form with the correct password.
            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name=full_name,
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            user_profile = UserProfile.objects.get(delivery_email=email)
            # Name comes from form which was set by LDAP.
            self.assertEqual(user_profile.full_name, full_name)

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_split_full_name_mapping(self) -> None:
        self.init_default_ldap_database()
        ldap_user_attr_map = {"first_name": "sn", "last_name": "cn"}

        subdomain = "zulip"
        email = "newuser_splitname@zulip.com"
        password = self.ldap_password("newuser_splitname")
        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            # Click confirmation link
            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Ignore",
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )

            # Test split name mapping.
            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Ignore",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            user_profile = UserProfile.objects.get(delivery_email=email)
            # Name comes from form which was set by LDAP.
            self.assertEqual(user_profile.full_name, "First Last")

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_auto_registration_on_login(self) -> None:
        """The most common way for LDAP authentication to be used is with a
        server that doesn't have a terms-of-service required, in which
        case we offer a complete single-sign-on experience (where the
        user just enters their LDAP username and password, and their
        account is created if it doesn't already exist).

        This test verifies that flow.
        """
        password = self.ldap_password("newuser")
        email = "newuser@zulip.com"
        subdomain = "zulip"

        self.init_default_ldap_database()
        ldap_user_attr_map = {
            "full_name": "cn",
            "custom_profile_field__phone_number": "homePhone",
        }
        full_name = "New LDAP fullname"

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            self.login_with_return(email, password, HTTP_HOST=subdomain + ".testserver")

            user_profile = UserProfile.objects.get(delivery_email=email)
            # Name comes from form which was set by LDAP.
            self.assertEqual(user_profile.full_name, full_name)

            # Test custom profile fields are properly synced.
            phone_number_field = CustomProfileField.objects.get(
                realm=user_profile.realm, name="Phone number"
            )
            phone_number_field_value = CustomProfileFieldValue.objects.get(
                user_profile=user_profile, field=phone_number_field
            )
            self.assertEqual(phone_number_field_value.value, "a-new-number")

    @override_settings(AUTHENTICATION_BACKENDS=("zproject.backends.ZulipLDAPAuthBackend",))
    def test_ldap_auto_registration_on_login_invalid_email_in_directory(self) -> None:
        password = self.ldap_password("newuser_with_email")
        username = "newuser_with_email"
        subdomain = "zulip"

        self.init_default_ldap_database()

        self.change_ldap_user_attr("newuser_with_email", "mail", "thisisnotavalidemail")

        with self.settings(
            LDAP_EMAIL_ATTR="mail",
        ), self.assertLogs("zulip.auth.ldap", "WARNING") as mock_log:
            original_user_count = UserProfile.objects.count()
            self.login_with_return(username, password, HTTP_HOST=subdomain + ".testserver")
            # Verify that the process failed as intended - no UserProfile is created.
            self.assertEqual(UserProfile.objects.count(), original_user_count)
            self.assertEqual(
                mock_log.output,
                ["WARNING:zulip.auth.ldap:thisisnotavalidemail is not a valid email address."],
            )

    @override_settings(AUTHENTICATION_BACKENDS=("zproject.backends.ZulipLDAPAuthBackend",))
    def test_ldap_registration_multiple_realms(self) -> None:
        password = self.ldap_password("newuser")
        email = "newuser@zulip.com"

        self.init_default_ldap_database()
        ldap_user_attr_map = {
            "full_name": "cn",
        }
        do_create_realm("test", "test", emails_restricted_to_domains=False)

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            subdomain = "zulip"
            self.login_with_return(email, password, HTTP_HOST=subdomain + ".testserver")

            user_profile = UserProfile.objects.get(delivery_email=email, realm=get_realm("zulip"))
            self.logout()

            # Test registration in another realm works.
            subdomain = "test"
            self.login_with_return(email, password, HTTP_HOST=subdomain + ".testserver")

            user_profile = UserProfile.objects.get(delivery_email=email, realm=get_realm("test"))
            self.assertEqual(user_profile.delivery_email, email)

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_registration_when_names_changes_are_disabled(self) -> None:
        password = self.ldap_password("newuser")
        email = "newuser@zulip.com"
        subdomain = "zulip"

        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}

        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            # Click confirmation link. This will 'authenticated_full_name'
            # session variable which will be used to set the fullname of
            # the user.
            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Ignore",
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )

            with patch("zerver.views.registration.name_changes_disabled", return_value=True):
                result = self.submit_reg_form_for_user(
                    email,
                    password,
                    # Pass HTTP_HOST for the target subdomain
                    HTTP_HOST=subdomain + ".testserver",
                )
            user_profile = UserProfile.objects.get(delivery_email=email)
            # Name comes from LDAP session.
            self.assertEqual(user_profile.full_name, "New LDAP fullname")

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.EmailAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_signup_with_ldap_and_email_enabled_using_email_with_ldap_append_domain(self) -> None:
        password = "nonldappassword"
        email = "newuser@zulip.com"
        subdomain = "zulip"

        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}

        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # If the user's email is inside the LDAP directory and we just
        # have a wrong password, then we refuse to create an account
        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            result = self.submit_reg_form_for_user(
                email,
                password,
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            self.assertEqual(result.status_code, 200)

            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Non-LDAP Full Name",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            self.assertEqual(result.status_code, 302)
            # We get redirected back to the login page because password was wrong
            self.assertEqual(result["Location"], "/accounts/login/?email=newuser%40zulip.com")
            self.assertFalse(UserProfile.objects.filter(delivery_email=email).exists())

        # For the rest of the test we delete the user from ldap.
        del self.mock_ldap.directory["uid=newuser,ou=users,dc=zulip,dc=com"]

        # If the user's email is not in the LDAP directory, but fits LDAP_APPEND_DOMAIN,
        # we refuse to create the account.
        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ), self.assertLogs("zulip.ldap", "DEBUG") as debug_log:
            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Non-LDAP Full Name",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            self.assertEqual(result.status_code, 302)
            # We get redirected back to the login page because emails matching LDAP_APPEND_DOMAIN,
            # aren't allowed to create non-LDAP accounts.
            self.assertEqual(result["Location"], "/accounts/login/?email=newuser%40zulip.com")
            self.assertFalse(UserProfile.objects.filter(delivery_email=email).exists())
            self.assertEqual(
                debug_log.output,
                [
                    "DEBUG:zulip.ldap:ZulipLDAPAuthBackend: No LDAP user matching django_to_ldap_username result: newuser. Input username: newuser@zulip.com"
                ],
            )

        # If the email is outside of LDAP_APPEND_DOMAIN, we successfully create a non-LDAP account,
        # with the password managed in the Zulip database.
        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="example.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            with self.assertLogs(level="WARNING") as m:
                result = self.submit_reg_form_for_user(
                    email,
                    password,
                    from_confirmation="1",
                    # Pass HTTP_HOST for the target subdomain
                    HTTP_HOST=subdomain + ".testserver",
                )
            self.assertEqual(result.status_code, 200)
            self.assertEqual(
                m.output,
                ["WARNING:root:New account email newuser@zulip.com could not be found in LDAP"],
            )
            with self.assertLogs("zulip.ldap", "DEBUG") as debug_log:
                result = self.submit_reg_form_for_user(
                    email,
                    password,
                    full_name="Non-LDAP Full Name",
                    # Pass HTTP_HOST for the target subdomain
                    HTTP_HOST=subdomain + ".testserver",
                )
            self.assertEqual(
                debug_log.output,
                [
                    "DEBUG:zulip.ldap:ZulipLDAPAuthBackend: Email newuser@zulip.com does not match LDAP domain example.com."
                ],
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "http://zulip.testserver/")
            user_profile = UserProfile.objects.get(delivery_email=email)
            # Name comes from the POST request, not LDAP
            self.assertEqual(user_profile.full_name, "Non-LDAP Full Name")

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.EmailAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_signup_with_ldap_and_email_enabled_using_email_with_ldap_email_search(self) -> None:
        # If the user's email is inside the LDAP directory and we just
        # have a wrong password, then we refuse to create an account
        password = "nonldappassword"
        email = "newuser_email@zulip.com"  # belongs to user uid=newuser_with_email in the test directory
        subdomain = "zulip"

        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}

        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_EMAIL_ATTR="mail",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            result = self.submit_reg_form_for_user(
                email,
                password,
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            self.assertEqual(result.status_code, 200)

            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Non-LDAP Full Name",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            self.assertEqual(result.status_code, 302)
            # We get redirected back to the login page because password was wrong
            self.assertEqual(result["Location"], "/accounts/login/?email=newuser_email%40zulip.com")
            self.assertFalse(UserProfile.objects.filter(delivery_email=email).exists())

        # If the user's email is not in the LDAP directory, though, we
        # successfully create an account with a password in the Zulip
        # database.
        password = "nonldappassword"
        email = "nonexistent@zulip.com"
        subdomain = "zulip"

        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_EMAIL_ATTR="mail",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            with self.assertLogs(level="WARNING") as m:
                result = self.submit_reg_form_for_user(
                    email,
                    password,
                    from_confirmation="1",
                    # Pass HTTP_HOST for the target subdomain
                    HTTP_HOST=subdomain + ".testserver",
                )
                self.assertEqual(result.status_code, 200)
                self.assertEqual(
                    m.output,
                    [
                        "WARNING:root:New account email nonexistent@zulip.com could not be found in LDAP"
                    ],
                )

            with self.assertLogs("zulip.ldap", "DEBUG") as debug_log:
                result = self.submit_reg_form_for_user(
                    email,
                    password,
                    full_name="Non-LDAP Full Name",
                    # Pass HTTP_HOST for the target subdomain
                    HTTP_HOST=subdomain + ".testserver",
                )
            self.assertEqual(
                debug_log.output,
                [
                    "DEBUG:zulip.ldap:ZulipLDAPAuthBackend: No LDAP user matching django_to_ldap_username result: nonexistent@zulip.com. Input username: nonexistent@zulip.com"
                ],
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "http://zulip.testserver/")
            user_profile = UserProfile.objects.get(delivery_email=email)
            # Name comes from the POST request, not LDAP
            self.assertEqual(user_profile.full_name, "Non-LDAP Full Name")

    def ldap_invite_and_signup_as(
        self, invite_as: int, streams: Sequence[str] = ["Denmark"]
    ) -> None:
        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}

        subdomain = "zulip"
        email = "newuser@zulip.com"
        password = self.ldap_password("newuser")

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            with self.assertLogs("zulip.ldap", "DEBUG") as debug_log:
                # Invite user.
                self.login("iago")
            self.assertEqual(
                debug_log.output,
                [
                    "DEBUG:zulip.ldap:ZulipLDAPAuthBackend: No LDAP user matching django_to_ldap_username result: iago. Input username: iago@zulip.com"
                ],
            )
            stream_ids = [self.get_stream_id(stream_name) for stream_name in streams]
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client_post(
                    "/json/invites",
                    {
                        "invitee_emails": email,
                        "stream_ids": orjson.dumps(stream_ids).decode(),
                        "invite_as": invite_as,
                    },
                )
            self.assert_json_success(response)
            self.logout()
            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Ignore",
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            self.assertEqual(result.status_code, 200)

            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="Ignore",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            self.assertEqual(result.status_code, 302)

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.EmailAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_invite_user_as_admin(self) -> None:
        self.ldap_invite_and_signup_as(PreregistrationUser.INVITE_AS["REALM_ADMIN"])
        user_profile = UserProfile.objects.get(delivery_email=self.nonreg_email("newuser"))
        self.assertTrue(user_profile.is_realm_admin)

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.EmailAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_invite_user_as_guest(self) -> None:
        self.ldap_invite_and_signup_as(PreregistrationUser.INVITE_AS["GUEST_USER"])
        user_profile = UserProfile.objects.get(delivery_email=self.nonreg_email("newuser"))
        self.assertTrue(user_profile.is_guest)

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.EmailAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_ldap_invite_streams(self) -> None:
        stream_name = "Rome"
        realm = get_realm("zulip")
        stream = get_stream(stream_name, realm)
        default_stream_names = {
            stream["name"] for stream in get_default_streams_for_realm_as_dicts(realm.id)
        }
        self.assertNotIn(stream_name, default_stream_names)

        # Invite user.
        self.ldap_invite_and_signup_as(
            PreregistrationUser.INVITE_AS["REALM_ADMIN"], streams=[stream_name]
        )

        user_profile = UserProfile.objects.get(delivery_email=self.nonreg_email("newuser"))
        self.assertTrue(user_profile.is_realm_admin)
        sub = get_stream_subscriptions_for_user(user_profile).filter(recipient__type_id=stream.id)
        self.assert_length(sub, 1)

    def test_registration_when_name_changes_are_disabled(self) -> None:
        """
        Test `name_changes_disabled` when we are not running under LDAP.
        """
        password = self.ldap_password("newuser")
        email = "newuser@zulip.com"
        subdomain = "zulip"

        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        with patch("zerver.views.registration.name_changes_disabled", return_value=True):
            result = self.submit_reg_form_for_user(
                email,
                password,
                full_name="New Name",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            user_profile = UserProfile.objects.get(delivery_email=email)
            # 'New Name' comes from POST data; not from LDAP session.
            self.assertEqual(user_profile.full_name, "New Name")

    def test_realm_creation_through_ldap(self) -> None:
        password = self.ldap_password("newuser")
        email = "newuser@zulip.com"
        subdomain = "zulip"
        realm_name = "Zulip"

        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}

        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        # Visit the confirmation link.
        from django.core.mail import outbox

        for message in reversed(outbox):
            if email in message.to:
                match = re.search(settings.EXTERNAL_HOST + r"(\S+)>", str(message.body))
                assert match is not None
                [confirmation_url] = match.groups()
                break
        else:
            raise AssertionError("Couldn't find a confirmation email.")

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
            AUTHENTICATION_BACKENDS=("zproject.backends.ZulipLDAPAuthBackend",),
            TERMS_OF_SERVICE_VERSION=1.0,
        ):
            result = self.client_get(confirmation_url)
            self.assertEqual(result.status_code, 200)

            key = find_key_by_email(email)
            confirmation = Confirmation.objects.get(confirmation_key=key)
            prereg_user = confirmation.content_object
            assert prereg_user is not None
            prereg_user.realm_creation = True
            prereg_user.save()

            result = self.submit_reg_form_for_user(
                email,
                password,
                realm_name=realm_name,
                realm_subdomain=subdomain,
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
            self.assert_in_success_response(
                ["Enter your account details to complete registration.", "newuser@zulip.com"],
                result,
            )

    @patch(
        "DNS.dnslookup",
        return_value=[["sipbtest:*:20922:101:Fred Sipb,,,:/mit/sipbtest:/bin/athena/tcsh"]],
    )
    def test_registration_of_mirror_dummy_user(self, ignored: Any) -> None:
        password = "test"
        subdomain = "zephyr"
        user_profile = self.mit_user("sipbtest")
        email = user_profile.delivery_email
        user_profile.is_mirror_dummy = True
        user_profile.save()
        change_user_is_active(user_profile, False)

        result = self.client_post("/register/", {"email": email}, subdomain="zephyr")

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"], subdomain="zephyr")
        self.assert_in_response("check your email", result)
        # Visit the confirmation link.
        from django.core.mail import outbox

        for message in reversed(outbox):
            if email in message.to:
                match = re.search(settings.EXTERNAL_HOST + r"(\S+)>", str(message.body))
                assert match is not None
                [confirmation_url] = match.groups()
                break
        else:
            raise AssertionError("Couldn't find a confirmation email.")

        result = self.client_get(confirmation_url, subdomain="zephyr")
        self.assertEqual(result.status_code, 200)

        # If the mirror dummy user is already active, attempting to
        # submit the registration form should raise an AssertionError
        # (this is an invalid state, so it's a bug we got here):
        change_user_is_active(user_profile, True)

        with self.assertRaisesRegex(
            AssertionError, "Mirror dummy user is already active!"
        ), self.assertLogs("django.request", "ERROR") as error_log:
            result = self.submit_reg_form_for_user(
                email,
                password,
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver",
            )
        self.assertTrue(
            "ERROR:django.request:Internal Server Error: /accounts/register/" in error_log.output[0]
        )
        self.assertTrue(
            'raise AssertionError("Mirror dummy user is already active!' in error_log.output[0]
        )
        self.assertTrue(
            "AssertionError: Mirror dummy user is already active!" in error_log.output[0]
        )

        change_user_is_active(user_profile, False)

        result = self.submit_reg_form_for_user(
            email,
            password,
            from_confirmation="1",
            # Pass HTTP_HOST for the target subdomain
            HTTP_HOST=subdomain + ".testserver",
        )
        self.assertEqual(result.status_code, 200)
        result = self.submit_reg_form_for_user(
            email,
            password,
            # Pass HTTP_HOST for the target subdomain
            HTTP_HOST=subdomain + ".testserver",
        )
        self.assertEqual(result.status_code, 302)
        self.assert_logged_in_user_id(user_profile.id)

    @patch(
        "DNS.dnslookup",
        return_value=[["sipbtest:*:20922:101:Fred Sipb,,,:/mit/sipbtest:/bin/athena/tcsh"]],
    )
    def test_registration_of_active_mirror_dummy_user(self, ignored: Any) -> None:
        """
        Trying to activate an already-active mirror dummy user should
        raise an AssertionError.
        """
        user_profile = self.mit_user("sipbtest")
        email = user_profile.delivery_email
        user_profile.is_mirror_dummy = True
        user_profile.save()
        change_user_is_active(user_profile, True)

        with self.assertRaisesRegex(
            AssertionError, "Mirror dummy user is already active!"
        ), self.assertLogs("django.request", "ERROR") as error_log:
            self.client_post("/register/", {"email": email}, subdomain="zephyr")
        self.assertTrue(
            "ERROR:django.request:Internal Server Error: /register/" in error_log.output[0]
        )
        self.assertTrue(
            'raise AssertionError("Mirror dummy user is already active!' in error_log.output[0]
        )
        self.assertTrue(
            "AssertionError: Mirror dummy user is already active!" in error_log.output[0]
        )

    @override_settings(TERMS_OF_SERVICE_VERSION=None)
    def test_dev_user_registration(self) -> None:
        """Verify that /devtools/register_user creates a new user, logs them
        in, and redirects to the logged-in app."""
        count = UserProfile.objects.count()
        email = f"user-{count}@zulip.com"

        result = self.client_post("/devtools/register_user/")
        user_profile = UserProfile.objects.all().order_by("id").last()
        assert user_profile is not None

        self.assertEqual(result.status_code, 302)
        self.assertEqual(user_profile.delivery_email, email)
        self.assertEqual(result["Location"], "http://zulip.testserver/")
        self.assert_logged_in_user_id(user_profile.id)

    @override_settings(TERMS_OF_SERVICE_VERSION=None)
    def test_dev_user_registration_create_realm(self) -> None:
        count = UserProfile.objects.count()
        string_id = f"realm-{count}"

        result = self.client_post("/devtools/register_realm/")
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith(f"http://{string_id}.testserver/accounts/login/subdomain")
        )
        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"http://{string_id}.testserver")

        user_profile = UserProfile.objects.all().order_by("id").last()
        assert user_profile is not None
        self.assert_logged_in_user_id(user_profile.id)

    @override_settings(TERMS_OF_SERVICE_VERSION=None)
    def test_dev_user_registration_create_demo_realm(self) -> None:
        result = self.client_post("/devtools/register_demo_realm/")
        self.assertEqual(result.status_code, 302)

        realm = Realm.objects.latest("date_created")
        self.assertTrue(
            result["Location"].startswith(
                f"http://{realm.string_id}.testserver/accounts/login/subdomain"
            )
        )
        result = self.client_get(result["Location"], subdomain=realm.string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"http://{realm.string_id}.testserver")

        user_profile = UserProfile.objects.all().order_by("id").last()
        assert user_profile is not None
        self.assert_logged_in_user_id(user_profile.id)

        # Demo organizations are created without setting an email address for the owner.
        self.assertEqual(user_profile.delivery_email, "")
        scheduled_email = ScheduledEmail.objects.filter(users=user_profile).last()
        assert scheduled_email is None

        self.assertIn(realm.string_id, user_profile.email)
        self.assertEqual(
            user_profile.email_address_visibility, UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY
        )

        expected_deletion_date = realm.date_created + timedelta(
            days=settings.DEMO_ORG_DEADLINE_DAYS
        )
        self.assertEqual(realm.demo_organization_scheduled_deletion_date, expected_deletion_date)

    def test_get_default_language_for_new_user(self) -> None:
        realm = get_realm("zulip")
        req = HostRequestMock()
        req.META["HTTP_ACCEPT_LANGUAGE"] = "de,en"
        self.assertEqual(get_default_language_for_new_user(realm, request=req), "de")

        do_set_realm_property(realm, "default_language", "hi", acting_user=None)
        realm.refresh_from_db()
        req = HostRequestMock()
        req.META["HTTP_ACCEPT_LANGUAGE"] = "de,en"
        self.assertEqual(get_default_language_for_new_user(realm, request=req), "de")

        req = HostRequestMock()
        req.META["HTTP_ACCEPT_LANGUAGE"] = ""
        self.assertEqual(get_default_language_for_new_user(realm, request=req), "hi")

        # Test code path for users created via the API or LDAP
        self.assertEqual(get_default_language_for_new_user(realm, request=None), "hi")


class DeactivateUserTest(ZulipTestCase):
    def test_deactivate_user(self) -> None:
        user = self.example_user("hamlet")
        email = user.email
        self.login_user(user)
        self.assertTrue(user.is_active)
        result = self.client_delete("/json/users/me")
        self.assert_json_success(result)
        user = self.example_user("hamlet")
        self.assertFalse(user.is_active)
        password = initial_password(email)
        assert password is not None
        self.assert_login_failure(email, password=password)

    def test_do_not_deactivate_final_owner(self) -> None:
        user = self.example_user("desdemona")
        user_2 = self.example_user("iago")
        self.login_user(user)
        self.assertTrue(user.is_active)
        result = self.client_delete("/json/users/me")
        self.assert_json_error(result, "Cannot deactivate the only organization owner.")
        user = self.example_user("desdemona")
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_realm_owner)
        do_change_user_role(user_2, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        self.assertTrue(user_2.is_realm_owner)
        result = self.client_delete("/json/users/me")
        self.assert_json_success(result)
        do_change_user_role(user, UserProfile.ROLE_REALM_OWNER, acting_user=None)

    def test_do_not_deactivate_final_user(self) -> None:
        realm = get_realm("zulip")
        for user_profile in UserProfile.objects.filter(realm=realm).exclude(
            role=UserProfile.ROLE_REALM_OWNER
        ):
            do_deactivate_user(user_profile, acting_user=None)
        user = self.example_user("desdemona")
        self.login_user(user)
        result = self.client_delete("/json/users/me")
        self.assert_json_error(result, "Cannot deactivate the only user.")


class TestLoginPage(ZulipTestCase):
    @patch("django.http.HttpRequest.get_host")
    def test_login_page_redirects_for_root_alias(self, mock_get_host: MagicMock) -> None:
        mock_get_host.return_value = "www.testserver"
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "/accounts/go/")

            result = self.client_get("/en/login/", {"next": "/upgrade/"})
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "/accounts/go/?next=%2Fupgrade%2F")

    @patch("django.http.HttpRequest.get_host")
    def test_login_page_redirects_for_root_domain(self, mock_get_host: MagicMock) -> None:
        mock_get_host.return_value = "testserver"
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "/accounts/go/")

            result = self.client_get("/en/login/", {"next": "/upgrade/"})
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "/accounts/go/?next=%2Fupgrade%2F")

        mock_get_host.return_value = "www.zulip.example.com"
        with self.settings(
            ROOT_DOMAIN_LANDING_PAGE=True,
            EXTERNAL_HOST="www.zulip.example.com",
            ROOT_SUBDOMAIN_ALIASES=["test"],
        ):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "/accounts/go/")

            result = self.client_get("/en/login/", {"next": "/upgrade/"})
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "/accounts/go/?next=%2Fupgrade%2F")

    def test_login_page_redirects_using_next_when_already_authenticated(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")

        result = self.client_get("/login/", {"next": "/upgrade/"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{hamlet.realm.uri}/upgrade/")

    @patch("django.http.HttpRequest.get_host")
    def test_login_page_works_without_subdomains(self, mock_get_host: MagicMock) -> None:
        mock_get_host.return_value = "www.testserver"
        with self.settings(ROOT_SUBDOMAIN_ALIASES=["www"]):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 200)

        mock_get_host.return_value = "testserver"
        with self.settings(ROOT_SUBDOMAIN_ALIASES=["www"]):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 200)

    def test_login_page_registration_hint(self) -> None:
        response = self.client_get("/login/")
        self.assert_not_in_success_response(
            ["Don't have an account yet? You need to be invited to join this organization."],
            response,
        )

        realm = get_realm("zulip")
        realm.invite_required = True
        realm.save(update_fields=["invite_required"])
        response = self.client_get("/login/")
        self.assert_in_success_response(
            ["Don't have an account yet? You need to be invited to join this organization."],
            response,
        )

    @patch("django.http.HttpRequest.get_host", return_value="auth.testserver")
    def test_social_auth_subdomain_login_page(self, mock_get_host: MagicMock) -> None:
        result = self.client_get("http://auth.testserver/login/")
        self.assertEqual(result.status_code, 400)
        self.assert_in_response("Authentication subdomain", result)

        zulip_realm = get_realm("zulip")
        session = self.client.session
        session["subdomain"] = "zulip"
        session.save()
        result = self.client_get("http://auth.testserver/login/")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], zulip_realm.uri)

        session = self.client.session
        session["subdomain"] = "invalid"
        session.save()
        result = self.client_get("http://auth.testserver/login/")
        self.assertEqual(result.status_code, 400)
        self.assert_in_response("Authentication subdomain", result)

    def test_login_page_is_deactivated_validation(self) -> None:
        with patch("zerver.views.auth.logging.info") as mock_info:
            result = self.client_get("/login/?is_deactivated=invalid_email")
            mock_info.assert_called_once()
            self.assert_not_in_success_response(["invalid_email"], result)


class TestFindMyTeam(ZulipTestCase):
    def test_template(self) -> None:
        result = self.client_get("/accounts/find/")
        self.assertIn("Find your Zulip accounts", result.content.decode())

    def test_result(self) -> None:
        # We capitalize a letter in cordelia's email to test that the search is case-insensitive.
        result = self.client_post(
            "/accounts/find/", dict(emails="iago@zulip.com,cordeliA@zulip.com")
        )
        self.assertEqual(result.status_code, 200)
        content = result.content.decode()
        self.assertIn("Emails sent! The addresses entered on", content)
        self.assertIn("iago@zulip.com", content)
        self.assertIn("cordeliA@zulip.com", content)
        from django.core.mail import outbox

        self.assert_length(outbox, 2)
        iago_message = outbox[1]
        cordelia_message = outbox[0]
        self.assertIn("Zulip Dev", iago_message.body)
        self.assertNotIn("Lear & Co", iago_message.body)
        self.assertIn("Zulip Dev", cordelia_message.body)
        self.assertIn("Lear & Co", cordelia_message.body)

    def test_find_team_email_with_no_account(self) -> None:
        result = self.client_post("/accounts/find/", dict(emails="no_account_email@zulip.com"))
        self.assertEqual(result.status_code, 200)
        content = result.content.decode()
        self.assertIn("Emails sent! The addresses entered on", content)
        self.assertIn("no_account_email@", content)
        from django.core.mail import outbox

        self.assert_length(outbox, 1)
        message = outbox[0]
        self.assertIn("Unfortunately, no Zulip Cloud accounts", message.body)

    def test_find_team_reject_invalid_email(self) -> None:
        result = self.client_post("/accounts/find/", dict(emails="invalid_string"))
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Enter a valid email", result.content)
        from django.core.mail import outbox

        self.assert_length(outbox, 0)

        # Just for coverage on perhaps-unnecessary validation code.
        result = self.client_get("/accounts/find/", {"emails": "invalid"})
        self.assertEqual(result.status_code, 200)

    def test_find_team_zero_emails(self) -> None:
        data = {"emails": ""}
        result = self.client_post("/accounts/find/", data)
        self.assertIn("This field is required", result.content.decode())
        self.assertEqual(result.status_code, 200)
        from django.core.mail import outbox

        self.assert_length(outbox, 0)

    def test_find_team_one_email(self) -> None:
        data = {"emails": self.example_email("hamlet")}
        result = self.client_post("/accounts/find/", data)
        self.assertEqual(result.status_code, 200)
        from django.core.mail import outbox

        self.assert_length(outbox, 1)
        message = outbox[0]
        self.assertIn("Zulip Dev", message.body)

    def test_find_team_deactivated_user(self) -> None:
        do_deactivate_user(self.example_user("hamlet"), acting_user=None)
        data = {"emails": self.example_email("hamlet")}
        result = self.client_post("/accounts/find/", data)
        self.assertEqual(result.status_code, 200)
        from django.core.mail import outbox

        self.assert_length(outbox, 1)
        message = outbox[0]
        self.assertIn("Unfortunately, no Zulip Cloud accounts", message.body)

    def test_find_team_deactivated_realm(self) -> None:
        do_deactivate_realm(get_realm("zulip"), acting_user=None)
        data = {"emails": self.example_email("hamlet")}
        result = self.client_post("/accounts/find/", data)
        self.assertEqual(result.status_code, 200)
        from django.core.mail import outbox

        self.assert_length(outbox, 1)
        message = outbox[0]
        self.assertIn("Unfortunately, no Zulip Cloud accounts", message.body)

    def test_find_team_bot_email(self) -> None:
        data = {"emails": self.example_email("webhook_bot")}
        result = self.client_post("/accounts/find/", data)
        self.assertEqual(result.status_code, 200)
        from django.core.mail import outbox

        self.assert_length(outbox, 1)
        message = outbox[0]
        self.assertIn("Unfortunately, no Zulip Cloud accounts", message.body)

    def test_find_team_more_than_ten_emails(self) -> None:
        data = {"emails": ",".join(f"hamlet-{i}@zulip.com" for i in range(11))}
        result = self.client_post("/accounts/find/", data)
        self.assertEqual(result.status_code, 200)
        self.assertIn("Please enter at most 10", result.content.decode())
        from django.core.mail import outbox

        self.assert_length(outbox, 0)


class ConfirmationKeyTest(ZulipTestCase):
    def test_confirmation_key(self) -> None:
        request = MagicMock()
        request.session = {
            "confirmation_key": {"confirmation_key": "xyzzy"},
        }
        result = confirmation_key(request)
        self.assert_json_success(result)
        self.assert_in_response("xyzzy", result)


class MobileAuthOTPTest(ZulipTestCase):
    def test_xor_hex_strings(self) -> None:
        self.assertEqual(xor_hex_strings("1237c81ab", "18989fd12"), "0aaf57cb9")
        with self.assertRaises(AssertionError):
            xor_hex_strings("1", "31")

    def test_is_valid_otp(self) -> None:
        self.assertEqual(is_valid_otp("1234"), False)
        self.assertEqual(is_valid_otp("1234abcd" * 8), True)
        self.assertEqual(is_valid_otp("1234abcZ" * 8), False)

    def test_ascii_to_hex(self) -> None:
        self.assertEqual(ascii_to_hex("ZcdR1234"), "5a63645231323334")
        self.assertEqual(hex_to_ascii("5a63645231323334"), "ZcdR1234")

    def test_otp_encrypt_api_key(self) -> None:
        api_key = "12ac" * 8
        otp = "7be38894" * 8
        result = otp_encrypt_api_key(api_key, otp)
        self.assertEqual(result, "4ad1e9f7" * 8)

        decrypted = otp_decrypt_api_key(result, otp)
        self.assertEqual(decrypted, api_key)


class NoReplyEmailTest(ZulipTestCase):
    def test_noreply_email_address(self) -> None:
        self.assertTrue(
            re.search(self.TOKENIZED_NOREPLY_REGEX, FromAddress.tokenized_no_reply_address())
        )

        with self.settings(ADD_TOKENS_TO_NOREPLY_ADDRESS=False):
            self.assertEqual(FromAddress.tokenized_no_reply_address(), "noreply@testserver")


class TwoFactorAuthTest(ZulipTestCase):
    @patch("two_factor.plugins.phonenumber.models.totp")
    def test_two_factor_login(self, mock_totp: MagicMock) -> None:
        token = 123456
        email = self.example_email("hamlet")
        password = self.ldap_password("hamlet")

        user_profile = self.example_user("hamlet")
        user_profile.set_password(password)
        user_profile.save()
        self.create_default_device(user_profile)

        def totp(*args: Any, **kwargs: Any) -> int:
            return token

        mock_totp.side_effect = totp

        with self.settings(
            AUTHENTICATION_BACKENDS=("zproject.backends.EmailAuthBackend",),
            TWO_FACTOR_CALL_GATEWAY="two_factor.gateways.fake.Fake",
            TWO_FACTOR_SMS_GATEWAY="two_factor.gateways.fake.Fake",
            TWO_FACTOR_AUTHENTICATION_ENABLED=True,
        ):
            first_step_data = {
                "username": email,
                "password": password,
                "two_factor_login_view-current_step": "auth",
            }
            with self.assertLogs("two_factor.gateways.fake", "INFO") as info_logs:
                result = self.client_post("/accounts/login/", first_step_data)
            self.assertEqual(
                info_logs.output,
                ['INFO:two_factor.gateways.fake:Fake SMS to +12125550100: "Your token is: 123456"'],
            )
            self.assertEqual(result.status_code, 200)

            second_step_data = {
                "token-otp_token": str(token),
                "two_factor_login_view-current_step": "token",
            }
            result = self.client_post("/accounts/login/", second_step_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "http://zulip.testserver")

            # Going to login page should redirect to '/' if user is already
            # logged in.
            result = self.client_get("/accounts/login/")
            self.assertEqual(result["Location"], "http://zulip.testserver/")


class NameRestrictionsTest(ZulipTestCase):
    def test_whitelisted_disposable_domains(self) -> None:
        self.assertFalse(is_disposable_domain("OPayQ.com"))


class RealmRedirectTest(ZulipTestCase):
    def test_realm_redirect_without_next_param(self) -> None:
        result = self.client_get("/accounts/go/")
        self.assert_in_success_response(["Enter your organization's Zulip URL"], result)

        result = self.client_post("/accounts/go/", {"subdomain": "zephyr"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://zephyr.testserver/login/")

        result = self.client_post("/accounts/go/", {"subdomain": "invalid"})
        self.assert_in_success_response(["We couldn&#39;t find that Zulip organization."], result)

    def test_realm_redirect_with_next_param(self) -> None:
        result = self.client_get("/accounts/go/", {"next": "billing"})
        self.assert_in_success_response(
            ["Enter your organization's Zulip URL", 'action="/accounts/go/?next=billing"'], result
        )

        result = self.client_post("/accounts/go/?next=billing", {"subdomain": "lear"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://lear.testserver/login/?next=billing")
