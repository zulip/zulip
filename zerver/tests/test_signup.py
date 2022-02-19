import datetime
import re
import time
import urllib
from typing import Any, Dict, List, Optional, Sequence, Union
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import orjson
from django.conf import settings
from django.contrib.auth.views import PasswordResetConfirmView
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import Client, override_settings
from django.urls import reverse
from django.utils.timezone import now as timezone_now

from confirmation import settings as confirmation_settings
from confirmation.models import (
    Confirmation,
    ConfirmationKeyException,
    create_confirmation_link,
    get_object_from_key,
    one_click_unsubscribe_link,
)
from corporate.lib.stripe import get_latest_seat_count
from zerver.context_processors import common_context
from zerver.decorator import do_two_factor_login
from zerver.forms import HomepageForm, check_subdomain_available
from zerver.lib.actions import (
    add_new_user_history,
    change_user_is_active,
    do_add_default_stream,
    do_change_full_name,
    do_change_realm_subdomain,
    do_change_user_role,
    do_create_default_stream_group,
    do_create_multiuse_invite_link,
    do_create_realm,
    do_create_user,
    do_deactivate_realm,
    do_deactivate_user,
    do_get_invites_controlled_by_user,
    do_invite_users,
    do_set_realm_property,
    do_set_realm_user_default_setting,
    get_default_streams_for_realm,
)
from zerver.lib.email_notifications import enqueue_welcome_emails, followup_day2_email_delay
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
from zerver.lib.rate_limiter import add_ratelimit_rule, remove_ratelimit_rule
from zerver.lib.send_email import (
    EmailNotDeliveredException,
    FromAddress,
    deliver_scheduled_emails,
    send_future_email,
)
from zerver.lib.stream_subscription import get_stream_subscriptions_for_user
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.subdomains import is_root_domain_available
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    avatar_disk_path,
    cache_tries_captured,
    find_key_by_email,
    get_test_image_file,
    load_subdomain_token,
    message_stream_count,
    most_recent_message,
    most_recent_usermessage,
    queries_captured,
    reset_emails_in_zulip_realm,
)
from zerver.models import (
    CustomProfileField,
    CustomProfileFieldValue,
    DefaultStream,
    Message,
    MultiuseInvite,
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
    flush_per_request_caches,
    get_realm,
    get_stream,
    get_system_bot,
    get_user,
    get_user_by_delivery_email,
)
from zerver.views.auth import redirect_and_log_into_subdomain, start_two_factor_auth
from zerver.views.development.registration import confirmation_key
from zerver.views.invite import get_invitee_emails_set
from zproject.backends import ExternalAuthDataDict, ExternalAuthResult


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
            self.assertEqual(result.status_code, 302)
            self.assertIn("deactivated", result.url)

    def test_redirection_for_active_realm(self) -> None:
        for url in ("/register/", "/login/"):
            result = self.client_get(url)
            self.assertEqual(result.status_code, 200)

    def test_deactivation_notice_when_realm_is_active(self) -> None:
        result = self.client_get("/accounts/deactivated/")
        self.assertEqual(result.status_code, 302)
        self.assertIn("login", result.url)

    def test_deactivation_notice_when_deactivated(self) -> None:
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.client_get("/accounts/deactivated/")
        self.assertIn("Zulip Dev, has been deactivated.", result.content.decode())
        self.assertNotIn("It has moved to", result.content.decode())

    def test_deactivation_notice_when_deactivated_and_deactivated_redirect_is_set(self) -> None:
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.deactivated_redirect = "http://example.zulipchat.com"
        realm.save(update_fields=["deactivated", "deactivated_redirect"])

        result = self.client_get("/accounts/deactivated/")
        self.assertIn(
            'It has moved to <a href="http://example.zulipchat.com">http://example.zulipchat.com</a>.',
            result.content.decode(),
        )

    def test_deactivation_notice_when_realm_subdomain_is_changed(self) -> None:
        realm = get_realm("zulip")
        do_change_realm_subdomain(realm, "new-subdomain-name", acting_user=None)

        result = self.client_get("/accounts/deactivated/")
        self.assertIn(
            'It has moved to <a href="http://new-subdomain-name.testserver">http://new-subdomain-name.testserver</a>.',
            result.content.decode(),
        )

    def test_deactivated_redirect_field_of_placeholder_realms_are_modified_on_changing_subdomain_multiple_times(
        self,
    ) -> None:
        realm = get_realm("zulip")
        do_change_realm_subdomain(realm, "new-name-1", acting_user=None)

        result = self.client_get("/accounts/deactivated/")
        self.assertIn(
            'It has moved to <a href="http://new-name-1.testserver">http://new-name-1.testserver</a>.',
            result.content.decode(),
        )

        realm = get_realm("new-name-1")
        do_change_realm_subdomain(realm, "new-name-2", acting_user=None)
        result = self.client_get("/accounts/deactivated/")
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

        with patch("zerver.lib.actions.add_new_user_history"):
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

        # Overwrite ONBOARDING_UNREAD_MESSAGES to 2
        ONBOARDING_UNREAD_MESSAGES = 2
        with patch("zerver.lib.actions.ONBOARDING_UNREAD_MESSAGES", ONBOARDING_UNREAD_MESSAGES):
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

        # Verify that the ONBOARDING_UNREAD_MESSAGES latest messages
        # that weren't the race message are marked as unread.
        latest_messages = (
            UserMessage.objects.filter(
                user_profile=user_profile,
                message__recipient__type=Recipient.STREAM,
            )
            .exclude(message_id=race_message_id)
            .order_by("-message_id")[0:ONBOARDING_UNREAD_MESSAGES]
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
            .order_by("-message_id")[ONBOARDING_UNREAD_MESSAGES : ONBOARDING_UNREAD_MESSAGES + 1]
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

        with patch("zerver.models.get_display_recipient", return_value="recip"):
            self.assertEqual(
                str(message),
                "<Message: recip /  / "
                "<UserProfile: {} {}>>".format(user_profile.email, user_profile.realm),
            )

            user_message = most_recent_usermessage(user_profile)
            self.assertEqual(
                str(user_message),
                f"<UserMessage: recip / {user_profile.email} ([])>",
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
            rf"^Zulip Account Security <{self.TOKENIZED_NOREPLY_REGEX}>\Z",
        )
        self.assertIn(f"{subdomain}.testserver", message.extra_headers["List-Id"])

        return message.body

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
        self.assertTrue(result.url.endswith(f"/{PasswordResetConfirmView.reset_url_token}/"))

        final_reset_url = result.url
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
            self.assertEqual(result.url, "/accounts/go/?next=%2Faccounts%2Fpassword%2Freset%2F")

        mock_get_host.return_value = "www.testserver"
        with self.settings(
            ROOT_DOMAIN_LANDING_PAGE=True,
        ):
            result = self.client_get("/accounts/password/reset/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/accounts/go/?next=%2Faccounts%2Fpassword%2Freset%2F")

    @patch("django.http.HttpRequest.get_host")
    def test_password_reset_page_redirects_for_root_domain_when_root_domain_landing_page_is_enabled(
        self, mock_get_host: MagicMock
    ) -> None:
        mock_get_host.return_value = "testserver"
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/accounts/password/reset/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/accounts/go/?next=%2Faccounts%2Fpassword%2Freset%2F")

        mock_get_host.return_value = "www.testserver.com"
        with self.settings(
            ROOT_DOMAIN_LANDING_PAGE=True,
            EXTERNAL_HOST="www.testserver.com",
        ):
            result = self.client_get("/accounts/password/reset/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/accounts/go/?next=%2Faccounts%2Fpassword%2Freset%2F")

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

        mock_get_host.return_value = "www.testserver.com"
        with self.settings(EXTERNAL_HOST="www.testserver.com", ROOT_SUBDOMAIN_ALIASES=[]):
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

    @override_settings(RATE_LIMITING=True)
    def test_rate_limiting(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email
        from django.core.mail import outbox

        add_ratelimit_rule(10, 2, domain="password_reset_form_by_email")
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

        remove_ratelimit_rule(10, 2, domain="password_reset_form_by_email")

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
        self.assert_in_success_response(["We've reset your password!"], result)

        result = self.client_get("/accounts/send_confirm/alice@example.com")
        self.assert_in_success_response(["/accounts/home/"], result)

        result = self.client_get("/accounts/new/send_confirm/alice@example.com")
        self.assert_in_success_response(["/new/"], result)


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
    def test_login_bad_password_rate_limiter(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email
        add_ratelimit_rule(10, 2, domain="authenticate_by_username")

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

        remove_ratelimit_rule(10, 2, domain="authenticate_by_username")

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
        email = self.mit_email("sipbtest")
        with self.assertLogs(level="WARNING") as m:
            result = self.login_with_return(email, "xxx")
            self.assertEqual(
                m.output,
                [
                    "WARNING:root:User sipbtest@mit.edu attempted password login to wrong subdomain zulip"
                ],
            )
        self.assertEqual(result.status_code, 200)
        expected_error = (
            f"Your Zulip account {email} is not a member of the "
            + "organization associated with this subdomain."
        )
        self.assert_in_response(expected_error, result)
        self.assert_logged_in_user_id(None)

    def test_login_invalid_subdomain(self) -> None:
        result = self.login_with_return(self.example_email("hamlet"), "xxx", subdomain="invalid")
        self.assertEqual(result.status_code, 404)
        self.assert_in_response("There is no Zulip organization hosted at this subdomain.", result)
        self.assert_logged_in_user_id(None)

    def test_register(self) -> None:
        reset_emails_in_zulip_realm()

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

        # Clear all the caches.
        flush_per_request_caches()
        ContentType.objects.clear_cache()

        with queries_captured() as queries, cache_tries_captured() as cache_tries:
            self.register(self.nonreg_email("test"), "test")
        # Ensure the number of queries we make is not O(streams)
        self.assert_length(queries, 90)

        # We can probably avoid a couple cache hits here, but there doesn't
        # seem to be any O(N) behavior.  Some of the cache hits are related
        # to sending messages, such as getting the welcome bot, looking up
        # the alert words for a realm, etc.
        self.assert_length(cache_tries, 21)

        user_profile = self.nonreg_user("test")
        self.assert_logged_in_user_id(user_profile.id)
        self.assertFalse(user_profile.enable_stream_desktop_notifications)

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
        self.assertEqual("/accounts/deactivated/", result.url)

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
        self.assertNotIn("deactivated", result.url)

        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.submit_reg_form_for_user(email, "abcd1234", subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual("/accounts/deactivated/", result.url)

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
        self.assertEqual("/accounts/deactivated/", result.url)

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
        self.assertEqual(response["Location"], "http://zulip.testserver")

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
        self.assertEqual(response["Location"], "http://zulip.testserver")

    def test_start_two_factor_auth(self) -> None:
        request = MagicMock(POST={})
        with patch("zerver.views.auth.TwoFactorLoginView") as mock_view:
            mock_view.as_view.return_value = lambda *a, **k: HttpResponse()
            response = start_two_factor_auth(request)
            self.assertTrue(isinstance(response, HttpResponse))

    def test_do_two_factor_login(self) -> None:
        user_profile = self.example_user("hamlet")
        self.create_default_device(user_profile)
        request = MagicMock()
        with patch("zerver.decorator.django_otp.login") as mock_login:
            do_two_factor_login(request, user_profile)
            mock_login.assert_called_once()

    def test_zulip_default_context_does_not_load_inline_previews(self) -> None:
        realm = get_realm("zulip")
        description = "https://www.google.com/images/srpr/logo4w.png"
        realm.description = description
        realm.save(update_fields=["description"])
        response = self.client_get("/login/")
        expected_response = """<p><a href="https://www.google.com/images/srpr/logo4w.png">\
https://www.google.com/images/srpr/logo4w.png</a></p>"""
        self.assertEqual(response.context_data["realm_description"], expected_response)
        self.assertEqual(response.status_code, 200)


class InviteUserBase(ZulipTestCase):
    def check_sent_emails(self, correct_recipients: List[str]) -> None:
        from django.core.mail import outbox

        self.assert_length(outbox, len(correct_recipients))
        email_recipients = [email.recipients()[0] for email in outbox]
        self.assertEqual(sorted(email_recipients), sorted(correct_recipients))
        if len(outbox) == 0:
            return

        self.assertIn("Zulip", self.email_display_from(outbox[0]))

        self.assertEqual(self.email_envelope_from(outbox[0]), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertRegex(
            self.email_display_from(outbox[0]), rf" <{self.TOKENIZED_NOREPLY_REGEX}>\Z"
        )

        self.assertEqual(outbox[0].extra_headers["List-Id"], "Zulip Dev <zulip.testserver>")

    def invite(
        self,
        invitee_emails: str,
        stream_names: Sequence[str],
        invite_expires_in_days: int = settings.INVITATION_LINK_VALIDITY_DAYS,
        body: str = "",
        invite_as: int = PreregistrationUser.INVITE_AS["MEMBER"],
    ) -> HttpResponse:
        """
        Invites the specified users to Zulip with the specified streams.

        users should be a string containing the users to invite, comma or
            newline separated.

        streams should be a list of strings.
        """
        stream_ids = []
        for stream_name in stream_names:
            stream_ids.append(self.get_stream_id(stream_name))
        return self.client_post(
            "/json/invites",
            {
                "invitee_emails": invitee_emails,
                "invite_expires_in_days": invite_expires_in_days,
                "stream_ids": orjson.dumps(stream_ids).decode(),
                "invite_as": invite_as,
            },
        )


class InviteUserTest(InviteUserBase):
    def test_successful_invite_user(self) -> None:
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet")
        invitee = "alice-test@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee))
        self.check_sent_emails([invitee])

    def test_newbie_restrictions(self) -> None:
        user_profile = self.example_user("hamlet")
        invitee = "alice-test@zulip.com"
        stream_name = "Denmark"

        self.login_user(user_profile)

        result = self.invite(invitee, [stream_name])
        self.assert_json_success(result)

        user_profile.date_joined = timezone_now() - datetime.timedelta(days=10)
        user_profile.save()

        with self.settings(INVITES_MIN_USER_AGE_DAYS=5):
            result = self.invite(invitee, [stream_name])
            self.assert_json_success(result)

        with self.settings(INVITES_MIN_USER_AGE_DAYS=15):
            result = self.invite(invitee, [stream_name])
            self.assert_json_error_contains(result, "Your account is too new")

    def test_invite_limits(self) -> None:
        user_profile = self.example_user("hamlet")
        realm = user_profile.realm
        stream_name = "Denmark"

        # These constants only need to be in descending order
        # for this test to trigger an InvitationError based
        # on max daily counts.
        site_max = 50
        realm_max = 40
        num_invitees = 30
        max_daily_count = 20

        daily_counts = [(1, max_daily_count)]

        invite_emails = [f"foo-{i:02}@zulip.com" for i in range(num_invitees)]
        invitees = ",".join(invite_emails)

        self.login_user(user_profile)

        realm.max_invites = realm_max
        realm.date_created = timezone_now()
        realm.save()

        def try_invite() -> HttpResponse:
            with self.settings(
                OPEN_REALM_CREATION=True,
                INVITES_DEFAULT_REALM_DAILY_MAX=site_max,
                INVITES_NEW_REALM_LIMIT_DAYS=daily_counts,
            ):
                result = self.invite(invitees, [stream_name])
                return result

        result = try_invite()
        self.assert_json_error_contains(result, "reached the limit")

        # Next show that aggregate limits expire once the realm is old
        # enough.

        realm.date_created = timezone_now() - datetime.timedelta(days=8)
        realm.save()

        with queries_captured() as queries:
            with cache_tries_captured() as cache_tries:
                result = try_invite()

        self.assert_json_success(result)

        # TODO: Fix large query count here.
        #
        # TODO: There is some test OTHER than this one
        #       that is leaking some kind of state change
        #       that throws off the query count here.  It
        #       is hard to investigate currently (due to
        #       the large number of queries), so I just
        #       use an approximate equality check.
        actual_count = len(queries)
        expected_count = 251
        if abs(actual_count - expected_count) > 1:
            raise AssertionError(
                f"""
                Unexpected number of queries:

                expected query count: {expected_count}
                actual: {actual_count}
                """
            )

        # Almost all of these cache hits are to re-fetch each one of the
        # invitees.  These happen inside our queue processor for sending
        # confirmation emails, so they are somewhat difficult to avoid.
        #
        # TODO: Mock the call to queue_json_publish, so we can measure the
        # queue impact separately from the user-perceived impact.
        self.assert_length(cache_tries, 32)

        # Next get line coverage on bumping a realm's max_invites.
        realm.date_created = timezone_now()
        realm.max_invites = site_max + 10
        realm.save()

        result = try_invite()
        self.assert_json_success(result)

        # Finally get coverage on the case that OPEN_REALM_CREATION is False.

        with self.settings(OPEN_REALM_CREATION=False):
            result = self.invite(invitees, [stream_name])

        self.assert_json_success(result)

    def test_invite_user_to_realm_on_manual_license_plan(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        _, ledger = self.subscribe_realm_to_monthly_plan_on_manual_license_management(
            user.realm, 50, 50
        )

        with self.settings(BILLING_ENABLED=True):
            result = self.invite(self.nonreg_email("alice"), ["Denmark"])
        self.assert_json_success(result)

        ledger.licenses_at_next_renewal = 5
        ledger.save(update_fields=["licenses_at_next_renewal"])
        with self.settings(BILLING_ENABLED=True):
            result = self.invite(self.nonreg_email("bob"), ["Denmark"])
        self.assert_json_success(result)

        ledger.licenses = get_latest_seat_count(user.realm) + 1
        ledger.save(update_fields=["licenses"])
        with self.settings(BILLING_ENABLED=True):
            invitee_emails = self.nonreg_email("bob") + "," + self.nonreg_email("alice")
            result = self.invite(invitee_emails, ["Denmark"])
        self.assert_json_error_contains(
            result, "Your organization does not have enough unused Zulip licenses to invite 2 users"
        )

        ledger.licenses = get_latest_seat_count(user.realm)
        ledger.save(update_fields=["licenses"])
        with self.settings(BILLING_ENABLED=True):
            result = self.invite(self.nonreg_email("bob"), ["Denmark"])
        self.assert_json_error_contains(
            result, "All Zulip licenses for this organization are currently in use"
        )

    def test_cross_realm_bot(self) -> None:
        inviter = self.example_user("hamlet")
        self.login_user(inviter)

        cross_realm_bot_email = "emailgateway@zulip.com"
        legit_new_email = "fred@zulip.com"
        invitee_emails = ",".join([cross_realm_bot_email, legit_new_email])

        result = self.invite(invitee_emails, ["Denmark"])
        self.assert_json_error(
            result,
            "Some of those addresses are already using Zulip,"
            + " so we didn't send them an invitation."
            + " We did send invitations to everyone else!",
        )

    def test_invite_mirror_dummy_user(self) -> None:
        """
        A mirror dummy account is a temporary account
        that we keep in our system if we are mirroring
        data from something like Zephyr or IRC.

        We want users to eventually just sign up or
        register for Zulip, in which case we will just
        fully "activate" the account.

        Here we test that you can invite a person who
        has a mirror dummy account.
        """
        inviter = self.example_user("hamlet")
        self.login_user(inviter)

        mirror_user = self.example_user("cordelia")
        mirror_user.is_mirror_dummy = True
        mirror_user.save()
        change_user_is_active(mirror_user, False)

        self.assertEqual(
            PreregistrationUser.objects.filter(email=mirror_user.email).count(),
            0,
        )

        result = self.invite(mirror_user.email, ["Denmark"])
        self.assert_json_success(result)

        prereg_user = PreregistrationUser.objects.get(email=mirror_user.email)
        assert prereg_user.referred_by is not None and inviter is not None
        self.assertEqual(
            prereg_user.referred_by.email,
            inviter.email,
        )

    def test_invite_from_now_deactivated_user(self) -> None:
        """
        While accepting an invitation from a user,
        processing for a new user account will only
        be completed if the inviter is not deactivated
        after sending the invite.
        """
        inviter = self.example_user("hamlet")
        self.login_user(inviter)
        invitee = self.nonreg_email("alice")

        result = self.invite(invitee, ["Denmark"])
        self.assert_json_success(result)

        prereg_user = PreregistrationUser.objects.get(email=invitee)
        change_user_is_active(inviter, False)
        do_create_user(
            invitee,
            "password",
            inviter.realm,
            "full name",
            prereg_user=prereg_user,
            acting_user=None,
        )

    def test_successful_invite_user_as_owner_from_owner_account(self) -> None:
        self.login("desdemona")
        invitee = self.nonreg_email("alice")
        result = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_OWNER"]
        )
        self.assert_json_success(result)
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        self.assertTrue(invitee_profile.is_realm_owner)
        self.assertFalse(invitee_profile.is_guest)

    def test_invite_user_as_owner_from_admin_account(self) -> None:
        self.login("iago")
        invitee = self.nonreg_email("alice")
        response = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_OWNER"]
        )
        self.assert_json_error(response, "Must be an organization owner")

    def test_successful_invite_user_as_admin_from_admin_account(self) -> None:
        self.login("iago")
        invitee = self.nonreg_email("alice")
        result = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_ADMIN"]
        )
        self.assert_json_success(result)
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        self.assertTrue(invitee_profile.is_realm_admin)
        self.assertFalse(invitee_profile.is_realm_owner)
        self.assertFalse(invitee_profile.is_guest)

    def test_invite_user_as_admin_from_normal_account(self) -> None:
        self.login("hamlet")
        invitee = self.nonreg_email("alice")
        response = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_ADMIN"]
        )
        self.assert_json_error(response, "Must be an organization administrator")

    def test_successful_invite_user_as_moderator_from_admin_account(self) -> None:
        self.login("iago")
        invitee = self.nonreg_email("alice")
        result = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["MODERATOR"]
        )
        self.assert_json_success(result)
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        self.assertFalse(invitee_profile.is_realm_admin)
        self.assertTrue(invitee_profile.is_moderator)
        self.assertFalse(invitee_profile.is_guest)

    def test_invite_user_as_moderator_from_normal_account(self) -> None:
        self.login("hamlet")
        invitee = self.nonreg_email("alice")
        response = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["MODERATOR"]
        )
        self.assert_json_error(response, "Must be an organization administrator")

    def test_invite_user_as_moderator_from_moderator_account(self) -> None:
        self.login("shiva")
        invitee = self.nonreg_email("alice")
        response = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["MODERATOR"]
        )
        self.assert_json_error(response, "Must be an organization administrator")

    def test_invite_user_as_invalid_type(self) -> None:
        """
        Test inviting a user as invalid type of user i.e. type of invite_as
        is not in PreregistrationUser.INVITE_AS
        """
        self.login("iago")
        invitee = self.nonreg_email("alice")
        response = self.invite(invitee, ["Denmark"], invite_as=10)
        self.assert_json_error(response, "Must be invited as an valid type of user")

    def test_successful_invite_user_as_guest_from_normal_account(self) -> None:
        self.login("hamlet")
        invitee = self.nonreg_email("alice")
        self.assert_json_success(
            self.invite(invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["GUEST_USER"])
        )
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        self.assertFalse(invitee_profile.is_realm_admin)
        self.assertTrue(invitee_profile.is_guest)

    def test_successful_invite_user_as_guest_from_admin_account(self) -> None:
        self.login("iago")
        invitee = self.nonreg_email("alice")
        self.assert_json_success(
            self.invite(invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["GUEST_USER"])
        )
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        self.assertFalse(invitee_profile.is_realm_admin)
        self.assertTrue(invitee_profile.is_guest)

    def test_successful_invite_user_with_name(self) -> None:
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet")
        email = "alice-test@zulip.com"
        invitee = f"Alice Test <{email}>"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.check_sent_emails([email])

    def test_successful_invite_user_with_name_and_normal_one(self) -> None:
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet")
        email = "alice-test@zulip.com"
        email2 = "bob-test@zulip.com"
        invitee = f"Alice Test <{email}>, {email2}"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

    def test_can_invite_others_to_realm(self) -> None:
        def validation_func(user_profile: UserProfile) -> bool:
            user_profile.refresh_from_db()
            return user_profile.can_invite_others_to_realm()

        realm = get_realm("zulip")
        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_NOBODY, acting_user=None
        )
        desdemona = self.example_user("desdemona")
        self.assertFalse(validation_func(desdemona))

        self.check_has_permission_policies("invite_to_realm_policy", validation_func)

    def test_invite_others_to_realm_setting(self) -> None:
        """
        The invite_to_realm_policy realm setting works properly.
        """
        realm = get_realm("zulip")
        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_NOBODY, acting_user=None
        )
        self.login("desdemona")
        email = "alice-test@zulip.com"
        email2 = "bob-test@zulip.com"
        invitee = f"Alice Test <{email}>, {email2}"
        self.assert_json_error(
            self.invite(invitee, ["Denmark"]),
            "Insufficient permission",
        )

        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_ADMINS_ONLY, acting_user=None
        )

        self.login("shiva")
        self.assert_json_error(
            self.invite(invitee, ["Denmark"]),
            "Insufficient permission",
        )

        # Now verify an administrator can do it
        self.login("iago")
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))

        self.check_sent_emails([email, email2])

        from django.core import mail

        mail.outbox = []

        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_MODERATORS_ONLY, acting_user=None
        )
        self.login("hamlet")
        email = "carol-test@zulip.com"
        email2 = "earl-test@zulip.com"
        invitee = f"Carol Test <{email}>, {email2}"
        self.assert_json_error(
            self.invite(invitee, ["Denmark"]),
            "Insufficient permission",
        )

        self.login("shiva")
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

        mail.outbox = []

        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_MEMBERS_ONLY, acting_user=None
        )

        self.login("polonius")
        email = "dave-test@zulip.com"
        email2 = "mark-test@zulip.com"
        invitee = f"Dave Test <{email}>, {email2}"
        self.assert_json_error(self.invite(invitee, ["Denmark"]), "Not allowed for guest users")

        self.login("hamlet")
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

        mail.outbox = []

        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_FULL_MEMBERS_ONLY, acting_user=None
        )
        do_set_realm_property(realm, "waiting_period_threshold", 1000, acting_user=None)

        hamlet = self.example_user("hamlet")
        hamlet.date_joined = timezone_now() - datetime.timedelta(
            days=(realm.waiting_period_threshold - 1)
        )

        email = "issac-test@zulip.com"
        email2 = "steven-test@zulip.com"
        invitee = f"Issac Test <{email}>, {email2}"
        self.assert_json_error(
            self.invite(invitee, ["Denmark"]),
            "Insufficient permission",
        )

        do_set_realm_property(realm, "waiting_period_threshold", 0, acting_user=None)

        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

    def test_invite_user_signup_initial_history(self) -> None:
        """
        Test that a new user invited to a stream receives some initial
        history but only from public streams.
        """
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        private_stream_name = "Secret"
        self.make_stream(private_stream_name, invite_only=True)
        self.subscribe(user_profile, private_stream_name)
        public_msg_id = self.send_stream_message(
            self.example_user("hamlet"),
            "Denmark",
            topic_name="Public topic",
            content="Public message",
        )
        secret_msg_id = self.send_stream_message(
            self.example_user("hamlet"),
            private_stream_name,
            topic_name="Secret topic",
            content="Secret message",
        )
        invitee = self.nonreg_email("alice")
        self.assert_json_success(self.invite(invitee, [private_stream_name, "Denmark"]))
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        invitee_msg_ids = [
            um.message_id for um in UserMessage.objects.filter(user_profile=invitee_profile)
        ]
        self.assertTrue(public_msg_id in invitee_msg_ids)
        self.assertFalse(secret_msg_id in invitee_msg_ids)
        self.assertFalse(invitee_profile.is_realm_admin)

        invitee_msg, signups_stream_msg, inviter_msg, secret_msg = Message.objects.all().order_by(
            "-id"
        )[0:4]

        self.assertEqual(secret_msg.id, secret_msg_id)

        self.assertEqual(inviter_msg.sender.email, "notification-bot@zulip.com")
        self.assertTrue(
            inviter_msg.content.startswith(
                f"alice_zulip.com <`{invitee_profile.email}`> accepted your",
            )
        )

        self.assertEqual(signups_stream_msg.sender.email, "notification-bot@zulip.com")
        self.assertTrue(
            signups_stream_msg.content.startswith(
                f"@_**alice_zulip.com|{invitee_profile.id}** just signed up",
            )
        )

        self.assertEqual(invitee_msg.sender.email, "welcome-bot@zulip.com")
        self.assertTrue(invitee_msg.content.startswith("Hello, and welcome to Zulip!"))
        self.assertNotIn("demo organization", invitee_msg.content)

    def test_multi_user_invite(self) -> None:
        """
        Invites multiple users with a variety of delimiters.
        """
        self.login("hamlet")
        # Intentionally use a weird string.
        self.assert_json_success(
            self.invite(
                """bob-test@zulip.com,     carol-test@zulip.com,
            dave-test@zulip.com


earl-test@zulip.com""",
                ["Denmark"],
            )
        )
        for user in ("bob", "carol", "dave", "earl"):
            self.assertTrue(find_key_by_email(f"{user}-test@zulip.com"))
        self.check_sent_emails(
            [
                "bob-test@zulip.com",
                "carol-test@zulip.com",
                "dave-test@zulip.com",
                "earl-test@zulip.com",
            ]
        )

    def test_max_invites_model(self) -> None:
        realm = get_realm("zulip")
        self.assertEqual(realm.max_invites, settings.INVITES_DEFAULT_REALM_DAILY_MAX)
        realm.max_invites = 3
        realm.save()
        self.assertEqual(get_realm("zulip").max_invites, 3)
        realm.max_invites = settings.INVITES_DEFAULT_REALM_DAILY_MAX
        realm.save()

    def test_invite_too_many_users(self) -> None:
        # Only a light test of this pathway; e.g. doesn't test that
        # the limit gets reset after 24 hours
        self.login("iago")
        invitee_emails = "1@zulip.com, 2@zulip.com"
        self.invite(invitee_emails, ["Denmark"])
        invitee_emails = ", ".join(str(i) for i in range(get_realm("zulip").max_invites - 1))
        self.assert_json_error(
            self.invite(invitee_emails, ["Denmark"]),
            "To protect users, Zulip limits the number of invitations you can send in one day. Because you have reached the limit, no invitations were sent.",
        )

    def test_missing_or_invalid_params(self) -> None:
        """
        Tests inviting with various missing or invalid parameters.
        """
        realm = get_realm("zulip")
        do_set_realm_property(realm, "emails_restricted_to_domains", True, acting_user=None)

        self.login("hamlet")
        invitee_emails = "foo@zulip.com"
        self.assert_json_error(
            self.invite(invitee_emails, []),
            "You must specify at least one stream for invitees to join.",
        )

        for address in ("noatsign.com", "outsideyourdomain@example.net"):
            self.assert_json_error(
                self.invite(address, ["Denmark"]),
                "Some emails did not validate, so we didn't send any invitations.",
            )
        self.check_sent_emails([])

        self.assert_json_error(
            self.invite("", ["Denmark"]), "You must specify at least one email address."
        )
        self.check_sent_emails([])

    def test_guest_user_invitation(self) -> None:
        """
        Guest user can't invite new users
        """
        self.login("polonius")
        invitee = "alice-test@zulip.com"
        self.assert_json_error(self.invite(invitee, ["Denmark"]), "Not allowed for guest users")
        self.assertEqual(find_key_by_email(invitee), None)
        self.check_sent_emails([])

    def test_invalid_stream(self) -> None:
        """
        Tests inviting to a non-existent stream.
        """
        self.login("hamlet")
        self.assert_json_error(
            self.invite("iago-test@zulip.com", ["NotARealStream"]),
            f"Stream does not exist with id: {self.INVALID_STREAM_ID}. No invites were sent.",
        )
        self.check_sent_emails([])

    def test_invite_existing_user(self) -> None:
        """
        If you invite an address already using Zulip, no invitation is sent.
        """
        self.login("hamlet")

        hamlet_email = "hAmLeT@zUlIp.com"
        result = self.invite(hamlet_email, ["Denmark"])
        self.assert_json_error(result, "We weren't able to invite anyone.")

        self.assertFalse(
            PreregistrationUser.objects.filter(email__iexact=hamlet_email).exists(),
        )
        self.check_sent_emails([])

    def normalize_string(self, s: str) -> str:
        s = s.strip()
        return re.sub(r"\s+", " ", s)

    def test_invite_links_in_name(self) -> None:
        """
        If you invite an address already using Zulip, no invitation is sent.
        """
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        # Test we properly handle links in user full names
        do_change_full_name(hamlet, "</a> https://www.google.com", hamlet)

        result = self.invite("newuser@zulip.com", ["Denmark"])
        self.assert_json_success(result)
        self.check_sent_emails(["newuser@zulip.com"])
        from django.core.mail import outbox

        body = self.normalize_string(outbox[0].alternatives[0][0])

        # Verify that one can't get Zulip to send invitation emails
        # that third-party products will linkify using the full_name
        # field, because we've included that field inside the mailto:
        # link for the sender.
        self.assertIn(
            '<a href="mailto:hamlet@zulip.com" style="color:#5f5ec7; text-decoration:underline">&lt;/a&gt; https://www.google.com (hamlet@zulip.com)</a> wants',
            body,
        )

        # TODO: Ideally, this test would also test the Invitation
        # Reminder email generated, but the test setup for that is
        # annoying.

    def test_invite_some_existing_some_new(self) -> None:
        """
        If you invite a mix of already existing and new users, invitations are
        only sent to the new users.
        """
        self.login("hamlet")
        existing = [self.example_email("hamlet"), "othello@zulip.com"]
        new = ["foo-test@zulip.com", "bar-test@zulip.com"]
        invitee_emails = "\n".join(existing + new)
        self.assert_json_error(
            self.invite(invitee_emails, ["Denmark"]),
            "Some of those addresses are already using Zulip, \
so we didn't send them an invitation. We did send invitations to everyone else!",
        )

        # We only created accounts for the new users.
        for email in existing:
            self.assertRaises(
                PreregistrationUser.DoesNotExist,
                lambda: PreregistrationUser.objects.get(email=email),
            )
        for email in new:
            self.assertTrue(PreregistrationUser.objects.get(email=email))

        # We only sent emails to the new users.
        self.check_sent_emails(new)

        prereg_user = PreregistrationUser.objects.get(email="foo-test@zulip.com")
        self.assertEqual(prereg_user.email, "foo-test@zulip.com")

    def test_invite_outside_domain_in_closed_realm(self) -> None:
        """
        In a realm with `emails_restricted_to_domains = True`, you can't invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = True
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo@example.com"

        self.assert_json_error(
            self.invite(external_address, ["Denmark"]),
            "Some emails did not validate, so we didn't send any invitations.",
        )

    def test_invite_using_disposable_email(self) -> None:
        """
        In a realm with `disallow_disposable_email_addresses = True`, you can't invite
        people with a disposable domain.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.disallow_disposable_email_addresses = True
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo@mailnator.com"

        self.assert_json_error(
            self.invite(external_address, ["Denmark"]),
            "Some emails did not validate, so we didn't send any invitations.",
        )

    def test_invite_outside_domain_in_open_realm(self) -> None:
        """
        In a realm with `emails_restricted_to_domains = False`, you can invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo@example.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

    def test_invite_outside_domain_before_closing(self) -> None:
        """
        If you invite someone with a different domain from that of the realm
        when `emails_restricted_to_domains = False`, but `emails_restricted_to_domains` later
        changes to true, the invitation should succeed but the invitee's signup
        attempt should fail.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo@example.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

        zulip_realm.emails_restricted_to_domains = True
        zulip_realm.save()

        result = self.submit_reg_form_for_user("foo@example.com", "password")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("only allows users with email addresses", result)

    def test_disposable_emails_before_closing(self) -> None:
        """
        If you invite someone with a disposable email when
        `disallow_disposable_email_addresses = False`, but
        later changes to true, the invitation should succeed
        but the invitee's signup attempt should fail.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.disallow_disposable_email_addresses = False
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo@mailnator.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

        zulip_realm.disallow_disposable_email_addresses = True
        zulip_realm.save()

        result = self.submit_reg_form_for_user("foo@mailnator.com", "password")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Please sign up using a real email address.", result)

    def test_invite_with_email_containing_plus_before_closing(self) -> None:
        """
        If you invite someone with an email containing plus when
        `emails_restricted_to_domains = False`, but later change
        `emails_restricted_to_domains = True`, the invitation should
        succeed but the invitee's signup attempt should fail as
        users are not allowed to sign up using email containing +
        when the realm is restricted to domain.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo+label@zulip.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

        zulip_realm.emails_restricted_to_domains = True
        zulip_realm.save()

        result = self.submit_reg_form_for_user(external_address, "password")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response(
            "Zulip Dev, does not allow signups using emails\n        that contains +", result
        )

    def test_invalid_email_check_after_confirming_email(self) -> None:
        self.login("hamlet")
        email = "test@zulip.com"

        self.assert_json_success(self.invite(email, ["Denmark"]))

        obj = Confirmation.objects.get(confirmation_key=find_key_by_email(email))
        prereg_user = obj.content_object
        assert prereg_user is not None
        prereg_user.email = "invalid.email"
        prereg_user.save()

        result = self.submit_reg_form_for_user(email, "password")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response(
            "The email address you are trying to sign up with is not valid", result
        )

    def test_invite_with_non_ascii_streams(self) -> None:
        """
        Inviting someone to streams with non-ASCII characters succeeds.
        """
        self.login("hamlet")
        invitee = "alice-test@zulip.com"

        stream_name = "hÃ¼mbÃ¼Çµ"

        # Make sure we're subscribed before inviting someone.
        self.subscribe(self.example_user("hamlet"), stream_name)

        self.assert_json_success(self.invite(invitee, [stream_name]))

    def test_invitation_reminder_email(self) -> None:
        from django.core.mail import outbox

        # All users belong to zulip realm
        referrer_name = "hamlet"
        current_user = self.example_user(referrer_name)
        self.login_user(current_user)
        invitee_email = self.nonreg_email("alice")
        self.assert_json_success(self.invite(invitee_email, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee_email))
        self.check_sent_emails([invitee_email])

        data = {"email": invitee_email, "referrer_email": current_user.email}
        invitee = PreregistrationUser.objects.get(email=data["email"])
        referrer = self.example_user(referrer_name)
        validity_in_days = 2
        link = create_confirmation_link(
            invitee, Confirmation.INVITATION, validity_in_days=validity_in_days
        )
        context = common_context(referrer)
        context.update(
            activate_url=link,
            referrer_name=referrer.full_name,
            referrer_email=referrer.email,
            referrer_realm_name=referrer.realm.name,
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            email = data["email"]
            send_future_email(
                "zerver/emails/invitation_reminder",
                referrer.realm,
                to_emails=[email],
                from_address=FromAddress.no_reply_placeholder,
                context=context,
            )
        email_jobs_to_deliver = ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now()
        )
        self.assert_length(email_jobs_to_deliver, 1)
        email_count = len(outbox)
        for job in email_jobs_to_deliver:
            deliver_scheduled_emails(job)
        self.assert_length(outbox, email_count + 1)
        self.assertEqual(self.email_envelope_from(outbox[-1]), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertIn(FromAddress.NOREPLY, self.email_display_from(outbox[-1]))

        # Now verify that signing up clears invite_reminder emails
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            email = data["email"]
            send_future_email(
                "zerver/emails/invitation_reminder",
                referrer.realm,
                to_emails=[email],
                from_address=FromAddress.no_reply_placeholder,
                context=context,
            )

        email_jobs_to_deliver = ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now(), type=ScheduledEmail.INVITATION_REMINDER
        )
        self.assert_length(email_jobs_to_deliver, 1)

        self.register(invitee_email, "test")
        email_jobs_to_deliver = ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now(), type=ScheduledEmail.INVITATION_REMINDER
        )
        self.assert_length(email_jobs_to_deliver, 0)

    def test_no_invitation_reminder_when_link_expires_quickly(self) -> None:
        self.login("hamlet")
        # Check invitation reminder email is scheduled with 4 day link expiry
        self.invite("alice@zulip.com", ["Denmark"], invite_expires_in_days=4)
        self.assertEqual(
            ScheduledEmail.objects.filter(type=ScheduledEmail.INVITATION_REMINDER).count(), 1
        )
        # Check invitation reminder email is not scheduled with 3 day link expiry
        self.invite("bob@zulip.com", ["Denmark"], invite_expires_in_days=3)
        self.assertEqual(
            ScheduledEmail.objects.filter(type=ScheduledEmail.INVITATION_REMINDER).count(), 1
        )

    # make sure users can't take a valid confirmation key from another
    # pathway and use it with the invitation URL route
    def test_confirmation_key_of_wrong_type(self) -> None:
        email = self.nonreg_email("alice")
        realm = get_realm("zulip")
        inviter = self.example_user("iago")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        url = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = url.split("/")[-1]

        # Mainly a test of get_object_from_key, rather than of the invitation pathway
        with self.assertRaises(ConfirmationKeyException) as cm:
            get_object_from_key(registration_key, [Confirmation.INVITATION])
        self.assertEqual(cm.exception.error_type, ConfirmationKeyException.DOES_NOT_EXIST)

        # Verify that using the wrong type doesn't work in the main confirm code path
        email_change_url = create_confirmation_link(prereg_user, Confirmation.EMAIL_CHANGE)
        email_change_key = email_change_url.split("/")[-1]
        result = self.client_post("/accounts/register/", {"key": email_change_key})
        self.assertEqual(result.status_code, 404)
        self.assert_in_response(
            "Whoops. We couldn't find your confirmation link in the system.", result
        )

    def test_confirmation_expired(self) -> None:
        email = self.nonreg_email("alice")
        realm = get_realm("zulip")
        inviter = self.example_user("iago")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        date_sent = timezone_now() - datetime.timedelta(weeks=3)
        with patch("confirmation.models.timezone_now", return_value=date_sent):
            url = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)

        key = url.split("/")[-1]
        confirmation_link_path = "/" + url.split("/", 3)[3]
        # Both the confirmation link and submitting the key to the registration endpoint
        # directly will return the appropriate error.
        result = self.client_get(confirmation_link_path)
        self.assertEqual(result.status_code, 404)
        self.assert_in_response(
            "Whoops. The confirmation link has expired or been deactivated.", result
        )

        result = self.client_post("/accounts/register/", {"key": key})
        self.assertEqual(result.status_code, 404)
        self.assert_in_response(
            "Whoops. The confirmation link has expired or been deactivated.", result
        )

    def test_send_more_than_one_invite_to_same_user(self) -> None:
        self.user_profile = self.example_user("iago")
        streams = []
        for stream_name in ["Denmark", "Scotland"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        invite_expires_in_days = 2
        do_invite_users(
            self.user_profile,
            ["foo@zulip.com"],
            streams,
            invite_expires_in_days=invite_expires_in_days,
        )
        prereg_user = PreregistrationUser.objects.get(email="foo@zulip.com")
        do_invite_users(
            self.user_profile,
            ["foo@zulip.com"],
            streams,
            invite_expires_in_days=invite_expires_in_days,
        )
        do_invite_users(
            self.user_profile,
            ["foo@zulip.com"],
            streams,
            invite_expires_in_days=invite_expires_in_days,
        )

        # Also send an invite from a different realm.
        lear = get_realm("lear")
        lear_user = self.lear_user("cordelia")
        do_invite_users(
            lear_user, ["foo@zulip.com"], [], invite_expires_in_days=invite_expires_in_days
        )

        invites = PreregistrationUser.objects.filter(email__iexact="foo@zulip.com")
        self.assert_length(invites, 4)

        do_create_user(
            "foo@zulip.com",
            "password",
            self.user_profile.realm,
            "full name",
            prereg_user=prereg_user,
            acting_user=None,
        )

        accepted_invite = PreregistrationUser.objects.filter(
            email__iexact="foo@zulip.com", status=confirmation_settings.STATUS_ACTIVE
        )
        revoked_invites = PreregistrationUser.objects.filter(
            email__iexact="foo@zulip.com", status=confirmation_settings.STATUS_REVOKED
        )
        # If a user was invited more than once, when it accepts one invite and register
        # the others must be canceled.
        self.assert_length(accepted_invite, 1)
        self.assertEqual(accepted_invite[0].id, prereg_user.id)

        expected_revoked_invites = set(invites.exclude(id=prereg_user.id).exclude(realm=lear))
        self.assertEqual(set(revoked_invites), expected_revoked_invites)

        self.assertEqual(
            PreregistrationUser.objects.get(email__iexact="foo@zulip.com", realm=lear).status, 0
        )

    def test_confirmation_obj_not_exist_error(self) -> None:
        """Since the key is a param input by the user to the registration endpoint,
        if it inserts an invalid value, the confirmation object won't be found. This
        tests if, in that scenario, we handle the exception by redirecting the user to
        the link_expired page.
        """
        email = self.nonreg_email("alice")
        password = "password"
        realm = get_realm("zulip")
        inviter = self.example_user("iago")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)

        registration_key = "invalid_confirmation_key"
        url = "/accounts/register/"
        response = self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        self.assertEqual(response.status_code, 404)
        self.assert_in_response(
            "Whoops. We couldn't find your confirmation link in the system.", response
        )

        registration_key = confirmation_link.split("/")[-1]
        response = self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        self.assert_in_success_response(["We just need you to do one last thing."], response)
        response = self.submit_reg_form_for_user(email, password, key=registration_key)
        self.assertEqual(response.status_code, 302)

    def test_validate_email_not_already_in_realm(self) -> None:
        email = self.nonreg_email("alice")
        password = "password"
        realm = get_realm("zulip")
        inviter = self.example_user("iago")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )

        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = confirmation_link.split("/")[-1]

        url = "/accounts/register/"
        self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        self.submit_reg_form_for_user(email, password, key=registration_key)

        url = "/accounts/register/"
        response = self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("login") + "?" + urlencode({"email": email, "already_registered": 1}),
        )

    def test_confirmation_link_in_manual_license_plan(self) -> None:
        inviter = self.example_user("iago")
        realm = get_realm("zulip")

        email = self.nonreg_email("alice")
        realm = get_realm("zulip")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = confirmation_link.split("/")[-1]
        url = "/accounts/register/"
        self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        response = self.submit_reg_form_for_user(email, "password", key=registration_key)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "http://zulip.testserver/")

        self.subscribe_realm_to_monthly_plan_on_manual_license_management(realm, 5, 5)

        email = self.nonreg_email("bob")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = confirmation_link.split("/")[-1]
        url = "/accounts/register/"
        self.client_post(url, {"key": registration_key, "from_confirmation": 1, "full_name": "bob"})
        response = self.submit_reg_form_for_user(email, "password", key=registration_key)
        self.assert_in_success_response(
            ["New members cannot join this organization because all Zulip licenses are"], response
        )


class InvitationsTestCase(InviteUserBase):
    def test_do_get_invites_controlled_by_user(self) -> None:
        user_profile = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        streams = []
        for stream_name in ["Denmark", "Scotland"]:
            streams.append(get_stream(stream_name, user_profile.realm))

        invite_expires_in_days = 2
        do_invite_users(
            user_profile,
            ["TestOne@zulip.com"],
            streams,
            invite_expires_in_days=invite_expires_in_days,
        )
        do_invite_users(
            user_profile,
            ["TestTwo@zulip.com"],
            streams,
            invite_expires_in_days=invite_expires_in_days,
        )
        do_invite_users(
            hamlet, ["TestThree@zulip.com"], streams, invite_expires_in_days=invite_expires_in_days
        )
        do_invite_users(
            othello, ["TestFour@zulip.com"], streams, invite_expires_in_days=invite_expires_in_days
        )
        do_invite_users(
            self.mit_user("sipbtest"),
            ["TestOne@mit.edu"],
            [],
            invite_expires_in_days=invite_expires_in_days,
        )
        do_create_multiuse_invite_link(
            user_profile, PreregistrationUser.INVITE_AS["MEMBER"], invite_expires_in_days
        )
        self.assert_length(do_get_invites_controlled_by_user(user_profile), 5)
        self.assert_length(do_get_invites_controlled_by_user(hamlet), 1)
        self.assert_length(do_get_invites_controlled_by_user(othello), 1)

    def test_successful_get_open_invitations(self) -> None:
        """
        A GET call to /json/invites returns all unexpired invitations.
        """
        active_value = getattr(confirmation_settings, "STATUS_ACTIVE", "Wrong")
        self.assertNotEqual(active_value, "Wrong")

        self.login("iago")
        user_profile = self.example_user("iago")
        self.login_user(user_profile)

        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        streams = []
        for stream_name in ["Denmark", "Scotland"]:
            streams.append(get_stream(stream_name, user_profile.realm))

        invite_expires_in_days = 2
        do_invite_users(
            user_profile,
            ["TestOne@zulip.com"],
            streams,
            invite_expires_in_days=invite_expires_in_days,
        )

        with patch(
            "confirmation.models.timezone_now",
            return_value=timezone_now() - datetime.timedelta(days=invite_expires_in_days + 1),
        ):
            do_invite_users(
                user_profile,
                ["TestTwo@zulip.com"],
                streams,
                invite_expires_in_days=invite_expires_in_days,
            )
            do_create_multiuse_invite_link(
                othello, PreregistrationUser.INVITE_AS["MEMBER"], invite_expires_in_days
            )

        prereg_user_three = PreregistrationUser(
            email="TestThree@zulip.com", referred_by=user_profile, status=active_value
        )
        prereg_user_three.save()
        create_confirmation_link(
            prereg_user_three, Confirmation.INVITATION, validity_in_days=invite_expires_in_days
        )

        do_create_multiuse_invite_link(
            hamlet, PreregistrationUser.INVITE_AS["MEMBER"], invite_expires_in_days
        )

        result = self.client_get("/json/invites")
        self.assertEqual(result.status_code, 200)
        invites = orjson.loads(result.content)["invites"]
        self.assert_length(invites, 2)

        self.assertFalse(invites[0]["is_multiuse"])
        self.assertEqual(invites[0]["email"], "TestOne@zulip.com")
        self.assertTrue(invites[1]["is_multiuse"])
        self.assertEqual(invites[1]["invited_by_user_id"], hamlet.id)

    def test_successful_delete_invitation(self) -> None:
        """
        A DELETE call to /json/invites/<ID> should delete the invite and
        any scheduled invitation reminder emails.
        """
        self.login("iago")

        invitee = "DeleteMe@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        prereg_user = PreregistrationUser.objects.get(email=invitee)

        # Verify that the scheduled email exists.
        ScheduledEmail.objects.get(address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER)

        result = self.client_delete("/json/invites/" + str(prereg_user.id))
        self.assertEqual(result.status_code, 200)
        error_result = self.client_delete("/json/invites/" + str(prereg_user.id))
        self.assert_json_error(error_result, "No such invitation")

        self.assertRaises(
            ScheduledEmail.DoesNotExist,
            lambda: ScheduledEmail.objects.get(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ),
        )

    def test_successful_member_delete_invitation(self) -> None:
        """
        A DELETE call from member account to /json/invites/<ID> should delete the invite and
        any scheduled invitation reminder emails.
        """
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        invitee = "DeleteMe@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))

        # Verify that the scheduled email exists.
        prereg_user = PreregistrationUser.objects.get(email=invitee, referred_by=user_profile)
        ScheduledEmail.objects.get(address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER)

        # Verify another non-admin can't delete
        result = self.api_delete(
            self.example_user("othello"), "/api/v1/invites/" + str(prereg_user.id)
        )
        self.assert_json_error(result, "Must be an organization administrator")

        # Verify that the scheduled email still exists.
        prereg_user = PreregistrationUser.objects.get(email=invitee, referred_by=user_profile)
        ScheduledEmail.objects.get(address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER)

        # Verify deletion works.
        result = self.api_delete(user_profile, "/api/v1/invites/" + str(prereg_user.id))
        self.assertEqual(result.status_code, 200)

        result = self.api_delete(user_profile, "/api/v1/invites/" + str(prereg_user.id))
        self.assert_json_error(result, "No such invitation")

        self.assertRaises(
            ScheduledEmail.DoesNotExist,
            lambda: ScheduledEmail.objects.get(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ),
        )

    def test_delete_owner_invitation(self) -> None:
        self.login("desdemona")
        owner = self.example_user("desdemona")

        invitee = "DeleteMe@zulip.com"
        self.assert_json_success(
            self.invite(
                invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_OWNER"]
            )
        )
        prereg_user = PreregistrationUser.objects.get(email=invitee)
        result = self.api_delete(
            self.example_user("iago"), "/api/v1/invites/" + str(prereg_user.id)
        )
        self.assert_json_error(result, "Must be an organization owner")

        result = self.api_delete(owner, "/api/v1/invites/" + str(prereg_user.id))
        self.assert_json_success(result)
        result = self.api_delete(owner, "/api/v1/invites/" + str(prereg_user.id))
        self.assert_json_error(result, "No such invitation")
        self.assertRaises(
            ScheduledEmail.DoesNotExist,
            lambda: ScheduledEmail.objects.get(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ),
        )

    def test_delete_multiuse_invite(self) -> None:
        """
        A DELETE call to /json/invites/multiuse<ID> should delete the
        multiuse_invite.
        """
        self.login("iago")

        zulip_realm = get_realm("zulip")
        multiuse_invite = MultiuseInvite.objects.create(
            referred_by=self.example_user("hamlet"), realm=zulip_realm
        )
        validity_in_days = 2
        create_confirmation_link(
            multiuse_invite, Confirmation.MULTIUSE_INVITE, validity_in_days=validity_in_days
        )
        result = self.client_delete("/json/invites/multiuse/" + str(multiuse_invite.id))
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(MultiuseInvite.objects.filter(id=multiuse_invite.id).first())
        # Test that trying to double-delete fails
        error_result = self.client_delete("/json/invites/multiuse/" + str(multiuse_invite.id))
        self.assert_json_error(error_result, "No such invitation")

        # Test deleting owner mutiuse_invite.
        multiuse_invite = MultiuseInvite.objects.create(
            referred_by=self.example_user("desdemona"),
            realm=zulip_realm,
            invited_as=PreregistrationUser.INVITE_AS["REALM_OWNER"],
        )
        validity_in_days = 2
        create_confirmation_link(
            multiuse_invite, Confirmation.MULTIUSE_INVITE, validity_in_days=validity_in_days
        )
        error_result = self.client_delete("/json/invites/multiuse/" + str(multiuse_invite.id))
        self.assert_json_error(error_result, "Must be an organization owner")

        self.login("desdemona")
        result = self.client_delete("/json/invites/multiuse/" + str(multiuse_invite.id))
        self.assert_json_success(result)
        self.assertIsNone(MultiuseInvite.objects.filter(id=multiuse_invite.id).first())

        # Test deleting multiuse invite from another realm
        mit_realm = get_realm("zephyr")
        multiuse_invite_in_mit = MultiuseInvite.objects.create(
            referred_by=self.mit_user("sipbtest"), realm=mit_realm
        )
        validity_in_days = 2
        create_confirmation_link(
            multiuse_invite_in_mit, Confirmation.MULTIUSE_INVITE, validity_in_days=validity_in_days
        )
        error_result = self.client_delete(
            "/json/invites/multiuse/" + str(multiuse_invite_in_mit.id)
        )
        self.assert_json_error(error_result, "No such invitation")

    def test_successful_resend_invitation(self) -> None:
        """
        A POST call to /json/invites/<ID>/resend should send an invitation reminder email
        and delete any scheduled invitation reminder email.
        """
        self.login("iago")
        invitee = "resend_me@zulip.com"

        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        prereg_user = PreregistrationUser.objects.get(email=invitee)

        # Verify and then clear from the outbox the original invite email
        self.check_sent_emails([invitee])
        from django.core.mail import outbox

        outbox.pop()

        # Verify that the scheduled email exists.
        scheduledemail_filter = ScheduledEmail.objects.filter(
            address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
        )
        self.assertEqual(scheduledemail_filter.count(), 1)
        original_timestamp = scheduledemail_filter.values_list("scheduled_timestamp", flat=True)

        # Resend invite
        result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assertEqual(
            ScheduledEmail.objects.filter(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ).count(),
            1,
        )

        # Check that we have exactly one scheduled email, and that it is different
        self.assertEqual(scheduledemail_filter.count(), 1)
        self.assertNotEqual(
            original_timestamp, scheduledemail_filter.values_list("scheduled_timestamp", flat=True)
        )

        self.assertEqual(result.status_code, 200)
        error_result = self.client_post("/json/invites/" + str(9999) + "/resend")
        self.assert_json_error(error_result, "No such invitation")

        self.check_sent_emails([invitee])

    def test_successful_member_resend_invitation(self) -> None:
        """A POST call from member a account to /json/invites/<ID>/resend
        should send an invitation reminder email and delete any
        scheduled invitation reminder email if they send the invite.
        """
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        invitee = "resend_me@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        # Verify hamlet has only one invitation (Member can resend invitations only sent by him).
        invitation = PreregistrationUser.objects.filter(referred_by=user_profile)
        self.assert_length(invitation, 1)
        prereg_user = PreregistrationUser.objects.get(email=invitee)

        # Verify and then clear from the outbox the original invite email
        self.check_sent_emails([invitee])
        from django.core.mail import outbox

        outbox.pop()

        # Verify that the scheduled email exists.
        scheduledemail_filter = ScheduledEmail.objects.filter(
            address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
        )
        self.assertEqual(scheduledemail_filter.count(), 1)
        original_timestamp = scheduledemail_filter.values_list("scheduled_timestamp", flat=True)

        # Resend invite
        result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assertEqual(
            ScheduledEmail.objects.filter(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ).count(),
            1,
        )

        # Check that we have exactly one scheduled email, and that it is different
        self.assertEqual(scheduledemail_filter.count(), 1)
        self.assertNotEqual(
            original_timestamp, scheduledemail_filter.values_list("scheduled_timestamp", flat=True)
        )

        self.assertEqual(result.status_code, 200)
        error_result = self.client_post("/json/invites/" + str(9999) + "/resend")
        self.assert_json_error(error_result, "No such invitation")

        self.check_sent_emails([invitee])

        self.logout()
        self.login("othello")
        invitee = "TestOne@zulip.com"
        prereg_user_one = PreregistrationUser(email=invitee, referred_by=user_profile)
        prereg_user_one.save()
        prereg_user = PreregistrationUser.objects.get(email=invitee)
        error_result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assert_json_error(error_result, "Must be an organization administrator")

    def test_resend_owner_invitation(self) -> None:
        self.login("desdemona")

        invitee = "resend_owner@zulip.com"
        self.assert_json_success(
            self.invite(
                invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_OWNER"]
            )
        )
        self.check_sent_emails([invitee])
        scheduledemail_filter = ScheduledEmail.objects.filter(
            address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
        )
        self.assertEqual(scheduledemail_filter.count(), 1)
        original_timestamp = scheduledemail_filter.values_list("scheduled_timestamp", flat=True)

        # Test only organization owners can resend owner invitation.
        self.login("iago")
        prereg_user = PreregistrationUser.objects.get(email=invitee)
        error_result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assert_json_error(error_result, "Must be an organization owner")

        self.login("desdemona")
        result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assert_json_success(result)

        self.assertEqual(
            ScheduledEmail.objects.filter(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ).count(),
            1,
        )

        # Check that we have exactly one scheduled email, and that it is different
        self.assertEqual(scheduledemail_filter.count(), 1)
        self.assertNotEqual(
            original_timestamp, scheduledemail_filter.values_list("scheduled_timestamp", flat=True)
        )

    def test_accessing_invites_in_another_realm(self) -> None:
        inviter = UserProfile.objects.exclude(realm=get_realm("zulip")).first()
        assert inviter is not None
        prereg_user = PreregistrationUser.objects.create(
            email="email", referred_by=inviter, realm=inviter.realm
        )
        self.login("iago")
        error_result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assert_json_error(error_result, "No such invitation")
        error_result = self.client_delete("/json/invites/" + str(prereg_user.id))
        self.assert_json_error(error_result, "No such invitation")

    def test_prereg_user_status(self) -> None:
        email = self.nonreg_email("alice")
        password = "password"
        realm = get_realm("zulip")

        inviter = UserProfile.objects.filter(realm=realm).first()
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )

        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = confirmation_link.split("/")[-1]

        result = self.client_post(
            "/accounts/register/",
            {"key": registration_key, "from_confirmation": "1", "full_name": "alice"},
        )
        self.assertEqual(result.status_code, 200)
        confirmation = Confirmation.objects.get(confirmation_key=registration_key)
        assert confirmation.content_object is not None
        prereg_user = confirmation.content_object
        self.assertEqual(prereg_user.status, 0)

        result = self.submit_reg_form_for_user(email, password, key=registration_key)
        self.assertEqual(result.status_code, 302)
        prereg_user = PreregistrationUser.objects.get(email=email, referred_by=inviter, realm=realm)
        self.assertEqual(prereg_user.status, confirmation_settings.STATUS_ACTIVE)
        user = get_user_by_delivery_email(email, realm)
        self.assertIsNotNone(user)
        self.assertEqual(user.delivery_email, email)


class InviteeEmailsParserTests(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.email1 = "email1@zulip.com"
        self.email2 = "email2@zulip.com"
        self.email3 = "email3@zulip.com"

    def test_if_emails_separated_by_commas_are_parsed_and_striped_correctly(self) -> None:
        emails_raw = f"{self.email1} ,{self.email2}, {self.email3}"
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_separated_by_newlines_are_parsed_and_striped_correctly(self) -> None:
        emails_raw = f"{self.email1}\n {self.email2}\n {self.email3} "
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_from_email_client_separated_by_newlines_are_parsed_correctly(self) -> None:
        emails_raw = (
            f"Email One <{self.email1}>\nEmailTwo<{self.email2}>\nEmail Three<{self.email3}>"
        )
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_in_mixed_style_are_parsed_correctly(self) -> None:
        emails_raw = f"Email One <{self.email1}>,EmailTwo<{self.email2}>\n{self.email3}"
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)


class MultiuseInviteTest(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")
        self.realm.invite_required = True
        self.realm.save()

    def generate_multiuse_invite_link(
        self, streams: Optional[List[Stream]] = None, date_sent: Optional[datetime.datetime] = None
    ) -> str:
        invite = MultiuseInvite(realm=self.realm, referred_by=self.example_user("iago"))
        invite.save()

        if streams is not None:
            invite.streams.set(streams)

        if date_sent is None:
            date_sent = timezone_now()
        validity_in_days = 2
        with patch("confirmation.models.timezone_now", return_value=date_sent):
            return create_confirmation_link(
                invite, Confirmation.MULTIUSE_INVITE, validity_in_days=validity_in_days
            )

    def check_user_able_to_register(self, email: str, invite_link: str) -> None:
        password = "password"

        result = self.client_post(invite_link, {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(email, password)
        self.assertEqual(result.status_code, 302)

        from django.core.mail import outbox

        outbox.pop()

    def test_valid_multiuse_link(self) -> None:
        email1 = self.nonreg_email("test")
        email2 = self.nonreg_email("test1")
        email3 = self.nonreg_email("alice")

        validity_in_days = 2
        date_sent = timezone_now() - datetime.timedelta(days=validity_in_days - 1)
        invite_link = self.generate_multiuse_invite_link(date_sent=date_sent)

        self.check_user_able_to_register(email1, invite_link)
        self.check_user_able_to_register(email2, invite_link)
        self.check_user_able_to_register(email3, invite_link)

    def test_expired_multiuse_link(self) -> None:
        email = self.nonreg_email("newuser")
        date_sent = timezone_now() - datetime.timedelta(
            days=settings.INVITATION_LINK_VALIDITY_DAYS + 1
        )
        invite_link = self.generate_multiuse_invite_link(date_sent=date_sent)
        result = self.client_post(invite_link, {"email": email})

        self.assertEqual(result.status_code, 404)
        self.assert_in_response("The confirmation link has expired or been deactivated.", result)

    def test_invalid_multiuse_link(self) -> None:
        email = self.nonreg_email("newuser")
        invite_link = "/join/invalid_key/"
        result = self.client_post(invite_link, {"email": email})

        self.assertEqual(result.status_code, 404)
        self.assert_in_response("Whoops. The confirmation link is malformed.", result)

    def test_invalid_multiuse_link_in_open_realm(self) -> None:
        self.realm.invite_required = False
        self.realm.save()

        email = self.nonreg_email("newuser")
        invite_link = "/join/invalid_key/"

        with patch("zerver.views.registration.get_realm_from_request", return_value=self.realm):
            with patch("zerver.views.registration.get_realm", return_value=self.realm):
                self.check_user_able_to_register(email, invite_link)

    def test_multiuse_link_with_specified_streams(self) -> None:
        name1 = "newuser"
        name2 = "bob"
        email1 = self.nonreg_email(name1)
        email2 = self.nonreg_email(name2)

        stream_names = ["Rome", "Scotland", "Venice"]
        streams = [get_stream(stream_name, self.realm) for stream_name in stream_names]
        invite_link = self.generate_multiuse_invite_link(streams=streams)
        self.check_user_able_to_register(email1, invite_link)
        self.check_user_subscribed_only_to_streams(name1, streams)

        stream_names = ["Rome", "Verona"]
        streams = [get_stream(stream_name, self.realm) for stream_name in stream_names]
        invite_link = self.generate_multiuse_invite_link(streams=streams)
        self.check_user_able_to_register(email2, invite_link)
        self.check_user_subscribed_only_to_streams(name2, streams)

    def test_create_multiuse_link_api_call(self) -> None:
        self.login("iago")

        result = self.client_post("/json/invites/multiuse", {"invite_expires_in_days": 2})
        self.assert_json_success(result)

        invite_link = result.json()["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)

    def test_create_multiuse_link_with_specified_streams_api_call(self) -> None:
        self.login("iago")
        stream_names = ["Rome", "Scotland", "Venice"]
        streams = [get_stream(stream_name, self.realm) for stream_name in stream_names]
        stream_ids = [stream.id for stream in streams]

        result = self.client_post(
            "/json/invites/multiuse",
            {"stream_ids": orjson.dumps(stream_ids).decode(), "invite_expires_in_days": 2},
        )
        self.assert_json_success(result)

        invite_link = result.json()["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)
        self.check_user_subscribed_only_to_streams("test", streams)

    def test_only_admin_can_create_multiuse_link_api_call(self) -> None:
        self.login("iago")
        # Only admins should be able to create multiuse invites even if
        # invite_to_realm_policy is set to Realm.POLICY_MEMBERS_ONLY.
        self.realm.invite_to_realm_policy = Realm.POLICY_MEMBERS_ONLY
        self.realm.save()

        result = self.client_post("/json/invites/multiuse", {"invite_expires_in_days": 2})
        self.assert_json_success(result)

        invite_link = result.json()["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)

        self.login("hamlet")
        result = self.client_post("/json/invites/multiuse")
        self.assert_json_error(result, "Must be an organization administrator")

    def test_multiuse_link_for_inviting_as_owner(self) -> None:
        self.login("iago")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "invite_as": orjson.dumps(PreregistrationUser.INVITE_AS["REALM_OWNER"]).decode(),
                "invite_expires_in_days": 2,
            },
        )
        self.assert_json_error(result, "Must be an organization owner")

        self.login("desdemona")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "invite_as": orjson.dumps(PreregistrationUser.INVITE_AS["REALM_OWNER"]).decode(),
                "invite_expires_in_days": 2,
            },
        )
        self.assert_json_success(result)

        invite_link = result.json()["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)

    def test_create_multiuse_link_invalid_stream_api_call(self) -> None:
        self.login("iago")
        result = self.client_post(
            "/json/invites/multiuse",
            {"stream_ids": orjson.dumps([54321]).decode(), "invite_expires_in_days": 2},
        )
        self.assert_json_error(result, "Invalid stream id 54321. No invites were sent.")


class EmailUnsubscribeTests(ZulipTestCase):
    def test_error_unsubscribe(self) -> None:

        # An invalid unsubscribe token "test123" produces an error.
        result = self.client_get("/accounts/unsubscribe/missed_messages/test123")
        self.assert_in_response("Unknown email unsubscribe request", result)

        # An unknown message type "fake" produces an error.
        user_profile = self.example_user("hamlet")
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "fake")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)
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
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

        self.assertEqual(result.status_code, 200)

        user_profile.refresh_from_db()
        self.assertFalse(user_profile.enable_offline_email_notifications)

    def test_welcome_unsubscribe(self) -> None:
        """
        We provide one-click unsubscribe links in welcome e-mails that you can
        click even when logged out to stop receiving them.
        """
        user_profile = self.example_user("hamlet")
        # Simulate a new user signing up, which enqueues 2 welcome e-mails.
        enqueue_welcome_emails(user_profile)
        self.assertEqual(2, ScheduledEmail.objects.filter(users=user_profile).count())

        # Simulate unsubscribing from the welcome e-mails.
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "welcome")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

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
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

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
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

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
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)
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
        result = client.post(
            urllib.parse.urlparse(unsubscribe_link).path, {"List-Unsubscribe": "One-Click"}
        )
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

        string_id = "zuliptest"
        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.client_post("/new/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/new/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Check confirmation email has the correct subject and body, extract
        # confirmation link and visit it
        confirmation_url = self.get_confirmation_url_from_outbox(
            email,
            email_subject_contains="Create your Zulip organization",
            email_body_contains="You have requested a new Zulip organization",
        )
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(email, password, realm_subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith("http://zuliptest.testserver/accounts/login/subdomain/")
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
        self.assertEqual(realm.emails_restricted_to_domains, False)
        self.assertEqual(realm.invite_required, True)

        # Check welcome messages
        for stream_name, text, message_count in [
            (Realm.DEFAULT_NOTIFICATION_STREAM_NAME, "with the topic", 3),
            (Realm.INITIAL_PRIVATE_STREAM_NAME, "private stream", 1),
        ]:
            stream = get_stream(stream_name, realm)
            recipient = stream.recipient
            messages = Message.objects.filter(recipient=recipient).order_by("date_sent")
            self.assert_length(messages, message_count)
            self.assertIn(text, messages[0].content)

        # Check signup messages
        recipient = signups_stream.recipient
        messages = Message.objects.filter(recipient=recipient).order_by("id")
        self.assert_length(messages, 2)
        self.assertIn("Signups enabled", messages[0].content)
        self.assertIn("signed up", messages[1].content)
        self.assertEqual("zuliptest", messages[1].topic_name())

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
        result = self.client_post("/new/", {"email": "notification-bot@zulip.com"})
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
            result = self.client_post("/new/", {"email": email})
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("New organization creation disabled", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_subdomain(self) -> None:
        password = "test"
        string_id = "zuliptest"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.client_post("/new/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/new/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result.url, subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "http://zuliptest.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        self.assertEqual(get_user(email, realm).realm, realm)

        self.assertEqual(realm.name, realm_name)
        self.assertEqual(realm.subdomain, string_id)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_marketing_emails_enabled(self) -> None:
        password = "test"
        string_id = "zuliptest"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.client_post("/new/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/new/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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

        result = self.client_get(result.url, subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "http://zuliptest.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)
        self.assertTrue(user.enable_marketing_emails)

    @override_settings(OPEN_REALM_CREATION=True, CORPORATE_ENABLED=False)
    def test_create_realm_without_prompting_for_marketing_emails(self) -> None:
        password = "test"
        string_id = "zuliptest"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.client_post("/new/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/new/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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
        result = self.client_post("/accounts/register/", payload)
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

        result = self.client_get(result.url, subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "http://zuliptest.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)
        self.assertFalse(user.enable_marketing_emails)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_marketing_emails_disabled(self) -> None:
        password = "test"
        string_id = "zuliptest"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.client_post("/new/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/new/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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

        result = self.client_get(result.url, subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "http://zuliptest.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)
        self.assertFalse(user.enable_marketing_emails)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_regular_realm_welcome_bot_pm(self) -> None:
        password = "test"
        string_id = "zuliptest"
        email = "user1@test.com"
        realm_name = "Test"

        # Create new realm with the email
        result = self.client_post("/new/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/new/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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

        # Make sure the correct Welcome Bot PM is sent
        welcome_msg = Message.objects.filter(
            sender__email="welcome-bot@zulip.com", recipient__type=Recipient.PERSONAL
        ).latest("id")
        self.assertTrue(welcome_msg.content.startswith("Hello, and welcome to Zulip!"))
        self.assertNotIn("demo organization", welcome_msg.content)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_demo_realm_welcome_bot_pm(self) -> None:
        password = "test"
        string_id = "zuliptest"
        email = "user1@test.com"
        realm_name = "Test"

        # Create new realm with the email
        result = self.client_post("/new/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/new/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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
            is_demo_organization=True,
        )
        self.assertEqual(result.status_code, 302)

        # Make sure the correct Welcome Bot PM is sent
        welcome_msg = Message.objects.filter(
            sender__email="welcome-bot@zulip.com", recipient__type=Recipient.PERSONAL
        ).latest("id")
        self.assertTrue(welcome_msg.content.startswith("Hello, and welcome to Zulip!"))
        self.assertIn("demo organization", welcome_msg.content)

    @override_settings(OPEN_REALM_CREATION=True, FREE_TRIAL_DAYS=30)
    def test_create_realm_during_free_trial(self) -> None:
        password = "test"
        string_id = "zuliptest"
        email = "user1@test.com"
        realm_name = "Test"

        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        result = self.client_post("/new/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/new/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result.url, subdomain=string_id)
        self.assertEqual(result.url, "http://zuliptest.testserver/upgrade/?onboarding=true")

        result = self.client_get(result.url, subdomain=string_id)
        self.assert_in_success_response(["Not ready to start your trial?"], result)

        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        self.assertEqual(get_user(email, realm).realm, realm)

        self.assertEqual(realm.name, realm_name)
        self.assertEqual(realm.subdomain, string_id)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_two_realms(self) -> None:
        """
        Verify correct behavior and PreregistrationUser handling when using
        two pre-generated realm creation links to create two different realms.
        """
        password = "test"
        first_string_id = "zuliptest"
        second_string_id = "zuliptest2"
        email = "user1@test.com"
        first_realm_name = "Test"
        second_realm_name = "Test"

        # Make sure the realms do not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(first_string_id)
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(second_string_id)

        # Now we pre-generate two realm creation links
        result = self.client_post("/new/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/new/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)
        first_confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.assertEqual(PreregistrationUser.objects.filter(email=email, status=0).count(), 1)

        # Get a second realm creation link.
        result = self.client_post("/new/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/new/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)
        second_confirmation_url = self.get_confirmation_url_from_outbox(email)

        self.assertNotEqual(first_confirmation_url, second_confirmation_url)
        self.assertEqual(PreregistrationUser.objects.filter(email=email, status=0).count(), 2)

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

        # One of the PreregistrationUsers should have been used up:
        self.assertEqual(PreregistrationUser.objects.filter(email=email, status=0).count(), 1)

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

        # The remaining PreregistrationUser should have been used up:
        self.assertEqual(PreregistrationUser.objects.filter(email=email, status=0).count(), 0)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_mailinator_signup(self) -> None:
        result = self.client_post("/new/", {"email": "hi@mailinator.com"})
        self.assert_in_response("Please use your real email address.", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        result = self.client_post("/new/", {"email": email})
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        errors = {
            "id": "length 3 or greater",
            "-id": "cannot start or end with a",
            "string-ID": "lowercase letters",
            "string_id": "lowercase letters",
            "stream": "unavailable",
            "streams": "unavailable",
            "about": "unavailable",
            "abouts": "unavailable",
            "zephyr": "unavailable",
        }
        for string_id, error_msg in errors.items():
            result = self.submit_reg_form_for_user(
                email, password, realm_subdomain=string_id, realm_name=realm_name
            )
            self.assert_in_response(error_msg, result)

        # test valid subdomain
        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain="a-0", realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result.url.startswith("http://a-0.testserver/accounts/login/subdomain/"))

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_using_old_subdomain_of_a_realm(self) -> None:
        realm = get_realm("zulip")
        do_change_realm_subdomain(realm, "new-name", acting_user=None)

        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        result = self.client_post("/new/", {"email": email})
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)
        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain="zulip", realm_name=realm_name
        )
        self.assert_in_response("Subdomain unavailable. Please choose a different one.", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions_root_domain(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        result = self.client_post("/new/", {"email": email})
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        # test root domain will fail with ROOT_DOMAIN_LANDING_PAGE
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.submit_reg_form_for_user(
                email, password, realm_subdomain="", realm_name=realm_name
            )
            self.assert_in_response("unavailable", result)

        # test valid use of root domain
        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain="", realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result.url.startswith("http://testserver/accounts/login/subdomain/"))

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions_root_domain_option(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        result = self.client_post("/new/", {"email": email})
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        # test root domain will fail with ROOT_DOMAIN_LANDING_PAGE
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.submit_reg_form_for_user(
                email,
                password,
                realm_subdomain="abcdef",
                realm_in_root_domain="true",
                realm_name=realm_name,
            )
            self.assert_in_response("unavailable", result)

        # test valid use of root domain
        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain="abcdef",
            realm_in_root_domain="true",
            realm_name=realm_name,
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result.url.startswith("http://testserver/accounts/login/subdomain/"))

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
            ["Subdomain unavailable. Please choose a different one."], result
        )

        result = self.client_get("/json/realm/subdomain/zu_lip")
        self.assert_in_success_response(
            ["Subdomain can only have lowercase letters, numbers, and '-'s."], result
        )

        with self.settings(SOCIAL_AUTH_SUBDOMAIN="zulipauth"):
            result = self.client_get("/json/realm/subdomain/zulipauth")
            self.assert_in_success_response(
                ["Subdomain unavailable. Please choose a different one."], result
            )

        result = self.client_get("/json/realm/subdomain/hufflepuff")
        self.assert_in_success_response(["available"], result)
        self.assert_not_in_success_response(["unavailable"], result)

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


class UserSignUpTest(InviteUserBase):
    def _assert_redirected_to(self, result: HttpResponse, url: str) -> None:
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["LOCATION"], url)

    def verify_signup(
        self,
        *,
        email: str = "newguy@zulip.com",
        password: Optional[str] = "newpassword",
        full_name: str = "New user's name",
        realm: Optional[Realm] = None,
        subdomain: Optional[str] = None,
    ) -> Union[UserProfile, HttpResponse]:
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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"], **client_kwargs)
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
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

    def test_bad_email_configuration_for_accounts_home(self) -> None:
        """
        Make sure we redirect for EmailNotDeliveredException.
        """
        email = self.nonreg_email("newguy")

        smtp_mock = patch(
            "zerver.views.registration.send_confirm_registration_email",
            side_effect=EmailNotDeliveredException,
        )

        with smtp_mock, self.assertLogs(level="ERROR") as m:
            result = self.client_post("/accounts/home/", {"email": email})

        self._assert_redirected_to(result, "/config-error/smtp")
        self.assertEqual(m.output, ["ERROR:root:Error in accounts_home"])

    def test_bad_email_configuration_for_create_realm(self) -> None:
        """
        Make sure we redirect for EmailNotDeliveredException.
        """
        email = self.nonreg_email("newguy")

        smtp_mock = patch(
            "zerver.views.registration.send_confirm_registration_email",
            side_effect=EmailNotDeliveredException,
        )

        with smtp_mock, self.assertLogs(level="ERROR") as m:
            result = self.client_post("/new/", {"email": email})

        self._assert_redirected_to(result, "/config-error/smtp")
        self.assertEqual(m.output, ["ERROR:root:Error in create_realm"])

    def test_user_default_language_and_timezone(self) -> None:
        """
        Check if the default language of new user is the default language
        of the realm.
        """
        email = self.nonreg_email("newguy")
        password = "newpassword"
        timezone = "America/Denver"
        realm = get_realm("zulip")
        do_set_realm_property(realm, "default_language", "de", acting_user=None)

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        # Pick a password and agree to the ToS.
        result = self.submit_reg_form_for_user(email, password, timezone=timezone)
        self.assertEqual(result.status_code, 302)

        user_profile = self.nonreg_user("newguy")
        self.assertEqual(user_profile.default_language, realm.default_language)
        self.assertEqual(user_profile.timezone, timezone)
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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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

    def test_signup_already_active(self) -> None:
        """
        Check if signing up with an active email redirects to a login page.
        """
        email = self.example_email("hamlet")
        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertIn("login", result["Location"])
        result = self.client_get(result.url)
        self.assert_in_response("You've already registered", result)

    def test_signup_system_bot(self) -> None:
        email = "notification-bot@zulip.com"
        result = self.client_post("/accounts/home/", {"email": email}, subdomain="lear")
        self.assertEqual(result.status_code, 302)
        self.assertIn("login", result["Location"])
        result = self.client_get(result.url)

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
        self.assert_in_success_response(["Invalid characters in name!"], result)

        # Verify that the user is asked for name and password
        self.assert_in_success_response(["id_password", "id_full_name"], result)

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
        self.assert_in_success_response(["We just need you to do one last thing."], result)

        # Verify that the user is asked for name and password
        self.assert_in_success_response(["id_password", "id_full_name"], result)

    def test_signup_email_message_contains_org_header(self) -> None:
        email = "newguy@zulip.com"

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        from django.core.mail import outbox

        self.assertEqual(outbox[0].extra_headers["List-Id"], "Zulip Dev <zulip.testserver>")

    def test_signup_with_full_name(self) -> None:
        """
        Check if signing up without a full name redirects to a registration
        form.
        """
        email = "newguy@zulip.com"
        password = "newpassword"

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.client_post(
            "/accounts/register/",
            {
                "password": password,
                "key": find_key_by_email(email),
                "terms": True,
                "full_name": "New Guy",
                "from_confirmation": "1",
            },
        )
        self.assert_in_success_response(["We just need you to do one last thing."], result)

    def test_signup_with_weak_password(self) -> None:
        """
        Check if signing up without a full name redirects to a registration
        form.
        """
        email = "newguy@zulip.com"

        result = self.client_post("/accounts/home/", {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        with self.settings(PASSWORD_MIN_LENGTH=6, PASSWORD_MIN_GUESSES=1000):
            result = self.client_post(
                "/accounts/register/",
                {
                    "password": "easy",
                    "key": find_key_by_email(email),
                    "terms": True,
                    "full_name": "New Guy",
                    "from_confirmation": "1",
                },
            )
            self.assert_in_success_response(["We just need you to do one last thing."], result)

            result = self.submit_reg_form_for_user(email, "easy", full_name="New Guy")
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
            ["We just need you to do one last thing.", "New Guy", email], result
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
        hamlet_in_zulip.save()

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
                "selected >\n                            Zulip Dev",
                "We just need you to do one last thing.",
            ],
            result,
        )

        result = self.submit_reg_form_for_user(
            email,
            password,
            source_realm_id=str(hamlet_in_zulip.realm.id),
            HTTP_HOST=subdomain + ".testserver",
        )

        hamlet_in_lear = get_user(email, lear_realm)
        self.assertEqual(hamlet_in_lear.left_side_userlist, True)
        self.assertEqual(hamlet_in_lear.default_language, "de")
        self.assertEqual(hamlet_in_lear.emojiset, "twitter")
        self.assertEqual(hamlet_in_lear.high_contrast_mode, True)
        self.assertEqual(hamlet_in_lear.enter_sends, True)
        self.assertEqual(hamlet_in_lear.enable_stream_audible_notifications, False)
        self.assertEqual(hamlet_in_lear.tutorial_status, UserProfile.TUTORIAL_FINISHED)

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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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

        password = "test"
        email = self.example_email("iago")
        realm_name = "Test"

        result = self.client_post("/new/", {"email": email})
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)
        result = self.submit_reg_form_for_user(
            email,
            password,
            # Subdomain is already used, by construction.
            realm_subdomain=realm.string_id,
            realm_name=realm_name,
            source_realm_id=str(realm.id),
        )
        self.assert_in_success_response(
            [
                "Subdomain unavailable. Please choose a different one.",
                "Zulip Dev\n",
                'value="test"',
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
        denmark_stream = get_stream("Denmark", realm)
        realm.signup_notifications_stream = denmark_stream
        realm.save(update_fields=["signup_notifications_stream"])

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
            self.assertEqual(last_message.recipient.type_id, denmark_stream.id)

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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)
        # Visit the confirmation link.
        from django.core.mail import outbox

        for message in reversed(outbox):
            if email in message.to:
                match = re.search(settings.EXTERNAL_HOST + r"(\S+)>", message.body)
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
                    "We just need you to do one last thing.",
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
                ["We just need you to do one last thing.", "newuser@zulip.com"], result
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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)
        # Visit the confirmation link.
        from django.core.mail import outbox

        for message in reversed(outbox):
            if email in message.to:
                match = re.search(settings.EXTERNAL_HOST + r"(\S+)>", message.body)
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
                    "We just need you to do one last thing.",
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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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
                ["We just need you to do one last thing.", full_name, "newuser@zulip.com"], result
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
            self.assertEqual(result.url, "/accounts/login/?email=newuser%40zulip.com")

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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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
            self.assertEqual(result.url, "/accounts/login/?email=newuser%40zulip.com")
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
            self.assertEqual(result.url, "/accounts/login/?email=newuser%40zulip.com")
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
            self.assertEqual(result.url, "http://zulip.testserver/")
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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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
            self.assertEqual(result.url, "/accounts/login/?email=newuser_email%40zulip.com")
            self.assertFalse(UserProfile.objects.filter(delivery_email=email).exists())

        # If the user's email is not in the LDAP directory , though, we
        # successfully create an account with a password in the Zulip
        # database.
        password = "nonldappassword"
        email = "nonexistent@zulip.com"
        subdomain = "zulip"

        with patch("zerver.views.registration.get_subdomain", return_value=subdomain):
            result = self.client_post("/register/", {"email": email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)
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
            self.assertEqual(result.url, "http://zulip.testserver/")
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
            response = self.invite(
                invitee_emails="newuser@zulip.com", stream_names=streams, invite_as=invite_as
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
        )
    )
    def test_ldap_invite_streams(self) -> None:
        stream_name = "Rome"
        realm = get_realm("zulip")
        stream = get_stream(stream_name, realm)
        default_streams = get_default_streams_for_realm(realm.id)
        default_streams_name = [stream.name for stream in default_streams]
        self.assertNotIn(stream_name, default_streams_name)

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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)
        # Visit the confirmation link.
        from django.core.mail import outbox

        for message in reversed(outbox):
            if email in message.to:
                match = re.search(settings.EXTERNAL_HOST + r"(\S+)>", message.body)
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
                ["We just need you to do one last thing.", "newuser@zulip.com"], result
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
        self.assertTrue(result["Location"].endswith(f"/accounts/send_confirm/{email}"))
        result = self.client_get(result["Location"], subdomain="zephyr")
        self.assert_in_response("Check your email so we can get started.", result)
        # Visit the confirmation link.
        from django.core.mail import outbox

        for message in reversed(outbox):
            if email in message.to:
                match = re.search(settings.EXTERNAL_HOST + r"(\S+)>", message.body)
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

        expected_deletion_date = realm.date_created + datetime.timedelta(
            days=settings.DEMO_ORG_DEADLINE_DAYS
        )
        self.assertEqual(realm.demo_organization_scheduled_deletion_date, expected_deletion_date)


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
            self.assertEqual(result.url, "/accounts/go/")

            result = self.client_get("/en/login/", {"next": "/upgrade/"})
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/accounts/go/?next=%2Fupgrade%2F")

    @patch("django.http.HttpRequest.get_host")
    def test_login_page_redirects_for_root_domain(self, mock_get_host: MagicMock) -> None:
        mock_get_host.return_value = "testserver"
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/accounts/go/")

            result = self.client_get("/en/login/", {"next": "/upgrade/"})
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/accounts/go/?next=%2Fupgrade%2F")

        mock_get_host.return_value = "www.testserver.com"
        with self.settings(
            ROOT_DOMAIN_LANDING_PAGE=True,
            EXTERNAL_HOST="www.testserver.com",
            ROOT_SUBDOMAIN_ALIASES=["test"],
        ):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/accounts/go/")

            result = self.client_get("/en/login/", {"next": "/upgrade/"})
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/accounts/go/?next=%2Fupgrade%2F")

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
        self.assertEqual(result.url, zulip_realm.uri)

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
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result.url, "/accounts/find/?emails=iago%40zulip.com%2CcordeliA%40zulip.com"
        )
        result = self.client_get(result.url)
        content = result.content.decode()
        self.assertIn("Emails sent! You will only receive emails", content)
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

    def test_find_team_ignore_invalid_email(self) -> None:
        result = self.client_post(
            "/accounts/find/", dict(emails="iago@zulip.com,invalid_email@zulip.com")
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result.url, "/accounts/find/?emails=iago%40zulip.com%2Cinvalid_email%40zulip.com"
        )
        result = self.client_get(result.url)
        content = result.content.decode()
        self.assertIn("Emails sent! You will only receive emails", content)
        self.assertIn(self.example_email("iago"), content)
        self.assertIn("invalid_email@", content)
        from django.core.mail import outbox

        self.assert_length(outbox, 1)

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
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/accounts/find/?emails=hamlet%40zulip.com")
        from django.core.mail import outbox

        self.assert_length(outbox, 1)

    def test_find_team_deactivated_user(self) -> None:
        do_deactivate_user(self.example_user("hamlet"), acting_user=None)
        data = {"emails": self.example_email("hamlet")}
        result = self.client_post("/accounts/find/", data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/accounts/find/?emails=hamlet%40zulip.com")
        from django.core.mail import outbox

        self.assert_length(outbox, 0)

    def test_find_team_deactivated_realm(self) -> None:
        do_deactivate_realm(get_realm("zulip"), acting_user=None)
        data = {"emails": self.example_email("hamlet")}
        result = self.client_post("/accounts/find/", data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/accounts/find/?emails=hamlet%40zulip.com")
        from django.core.mail import outbox

        self.assert_length(outbox, 0)

    def test_find_team_bot_email(self) -> None:
        data = {"emails": self.example_email("webhook_bot")}
        result = self.client_post("/accounts/find/", data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/accounts/find/?emails=webhook-bot%40zulip.com")
        from django.core.mail import outbox

        self.assert_length(outbox, 0)

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

        decryped = otp_decrypt_api_key(result, otp)
        self.assertEqual(decryped, api_key)


class FollowupEmailTest(ZulipTestCase):
    def test_followup_day2_email(self) -> None:
        user_profile = self.example_user("hamlet")
        # Test date_joined == Sunday
        user_profile.date_joined = datetime.datetime(
            2018, 1, 7, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
        )
        self.assertEqual(
            followup_day2_email_delay(user_profile), datetime.timedelta(days=2, hours=-1)
        )
        # Test date_joined == Tuesday
        user_profile.date_joined = datetime.datetime(
            2018, 1, 2, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
        )
        self.assertEqual(
            followup_day2_email_delay(user_profile), datetime.timedelta(days=2, hours=-1)
        )
        # Test date_joined == Thursday
        user_profile.date_joined = datetime.datetime(
            2018, 1, 4, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
        )
        self.assertEqual(
            followup_day2_email_delay(user_profile), datetime.timedelta(days=1, hours=-1)
        )
        # Test date_joined == Friday
        user_profile.date_joined = datetime.datetime(
            2018, 1, 5, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
        )
        self.assertEqual(
            followup_day2_email_delay(user_profile), datetime.timedelta(days=3, hours=-1)
        )

        # Time offset of America/Phoenix is -07:00
        user_profile.timezone = "America/Phoenix"
        # Test date_joined == Friday in UTC, but Thursday in the user's timezone
        user_profile.date_joined = datetime.datetime(
            2018, 1, 5, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
        )
        self.assertEqual(
            followup_day2_email_delay(user_profile), datetime.timedelta(days=1, hours=-1)
        )


class NoReplyEmailTest(ZulipTestCase):
    def test_noreply_email_address(self) -> None:
        self.assertTrue(
            re.search(self.TOKENIZED_NOREPLY_REGEX, FromAddress.tokenized_no_reply_address())
        )

        with self.settings(ADD_TOKENS_TO_NOREPLY_ADDRESS=False):
            self.assertEqual(FromAddress.tokenized_no_reply_address(), "noreply@testserver")


class TwoFactorAuthTest(ZulipTestCase):
    @patch("two_factor.models.totp")
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
            self.assertEqual(result["Location"], "http://zulip.testserver")


class NameRestrictionsTest(ZulipTestCase):
    def test_whitelisted_disposable_domains(self) -> None:
        self.assertFalse(is_disposable_domain("OPayQ.com"))


class RealmRedirectTest(ZulipTestCase):
    def test_realm_redirect_without_next_param(self) -> None:
        result = self.client_get("/accounts/go/")
        self.assert_in_success_response(["Enter your organization's Zulip URL"], result)

        result = self.client_post("/accounts/go/", {"subdomain": "zephyr"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://zephyr.testserver")

        result = self.client_post("/accounts/go/", {"subdomain": "invalid"})
        self.assert_in_success_response(["We couldn&#39;t find that Zulip organization."], result)

    def test_realm_redirect_with_next_param(self) -> None:
        result = self.client_get("/accounts/go/", {"next": "billing"})
        self.assert_in_success_response(
            ["Enter your organization's Zulip URL", 'action="/accounts/go/?next=billing"'], result
        )

        result = self.client_post("/accounts/go/?next=billing", {"subdomain": "lear"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://lear.testserver/billing")
