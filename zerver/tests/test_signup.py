# -*- coding: utf-8 -*-
import datetime
from email.utils import parseaddr

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.utils.timezone import now as timezone_now
from django.core.exceptions import ValidationError

from mock import patch, MagicMock
from zerver.lib.test_helpers import get_test_image_file, avatar_disk_path

from confirmation.models import Confirmation, create_confirmation_link, MultiuseInvite, \
    generate_key, confirmation_url, get_object_from_key, ConfirmationKeyException, \
    one_click_unsubscribe_link
from confirmation import settings as confirmation_settings

from zerver.forms import HomepageForm, WRONG_SUBDOMAIN_ERROR, check_subdomain_available
from zerver.lib.actions import get_default_streams_for_realm
from zerver.lib.dev_ldap_directory import init_fakeldap
from zerver.decorator import do_two_factor_login
from zerver.views.auth import \
    redirect_and_log_into_subdomain, start_two_factor_auth
from zerver.views.invite import get_invitee_emails_set
from zerver.views.development.registration import confirmation_key

from zerver.models import (
    get_realm, get_user, get_realm_stream, get_stream_recipient,
    CustomProfileField, CustomProfileFieldValue, PreregistrationUser,
    Realm, Recipient, Message, ScheduledEmail, UserProfile, UserMessage,
    Stream, Subscription, flush_per_request_caches
)
from zerver.lib.actions import (
    set_default_streams,
    do_change_is_admin,
    get_stream,
    do_create_default_stream_group,
    do_add_default_stream,
    do_create_realm,
)
from zerver.lib.send_email import send_email, send_future_email, FromAddress
from zerver.lib.initial_password import initial_password
from zerver.lib.actions import (
    do_deactivate_realm,
    do_deactivate_user,
    do_set_realm_property,
    add_new_user_history,
)
from zerver.lib.mobile_auth_otp import xor_hex_strings, ascii_to_hex, \
    otp_encrypt_api_key, is_valid_otp, hex_to_ascii, otp_decrypt_api_key
from zerver.lib.notifications import enqueue_welcome_emails, \
    followup_day2_email_delay
from zerver.lib.subdomains import is_root_domain_available
from zerver.lib.stream_subscription import get_stream_subscriptions_for_user
from zerver.lib.test_helpers import find_key_by_email, queries_captured, \
    HostRequestMock, load_subdomain_token
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.sessions import get_session_dict_user
from zerver.lib.name_restrictions import is_disposable_domain
from zerver.context_processors import common_context

import re
import smtplib
import ujson

from typing import Any, Dict, List, Optional

import urllib
import pytz

class RedirectAndLogIntoSubdomainTestCase(ZulipTestCase):
    def test_cookie_data(self) -> None:
        realm = Realm.objects.all().first()
        name = 'Hamlet'
        email = self.example_email("hamlet")
        response = redirect_and_log_into_subdomain(realm, name, email)
        data = load_subdomain_token(response)
        self.assertDictEqual(data, {'name': name, 'next': '',
                                    'email': email,
                                    'subdomain': realm.subdomain,
                                    'is_signup': False,
                                    'multiuse_object_key': ''})

        response = redirect_and_log_into_subdomain(realm, name, email,
                                                   is_signup=True,
                                                   multiuse_object_key='key')
        data = load_subdomain_token(response)
        self.assertDictEqual(data, {'name': name, 'next': '',
                                    'email': email,
                                    'subdomain': realm.subdomain,
                                    'is_signup': True,
                                    'multiuse_object_key': 'key'
                                    })

class DeactivationNoticeTestCase(ZulipTestCase):
    def test_redirection_for_deactivated_realm(self) -> None:
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        for url in ('/register/', '/login/'):
            result = self.client_get(url)
            self.assertEqual(result.status_code, 302)
            self.assertIn('deactivated', result.url)

    def test_redirection_for_active_realm(self) -> None:
        for url in ('/register/', '/login/'):
            result = self.client_get(url)
            self.assertEqual(result.status_code, 200)

    def test_deactivation_notice_when_realm_is_active(self) -> None:
        result = self.client_get('/accounts/deactivated/')
        self.assertEqual(result.status_code, 302)
        self.assertIn('login', result.url)

    def test_deactivation_notice_when_deactivated(self) -> None:
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.client_get('/accounts/deactivated/')
        self.assertIn("Zulip Dev, has been deactivated.", result.content.decode())

class AddNewUserHistoryTest(ZulipTestCase):
    def test_add_new_user_history_race(self) -> None:
        """Sends a message during user creation"""
        # Create a user who hasn't had historical messages added
        stream_dict = {
            "Denmark": {"description": "A Scandinavian country", "invite_only": False},
            "Verona": {"description": "A city in Italy", "invite_only": False}
        }  # type: Dict[str, Dict[str, Any]]
        realm = get_realm('zulip')
        set_default_streams(realm, stream_dict)
        with patch("zerver.lib.actions.add_new_user_history"):
            self.register(self.nonreg_email('test'), "test")
        user_profile = self.nonreg_user('test')

        subs = Subscription.objects.select_related("recipient").filter(
            user_profile=user_profile, recipient__type=Recipient.STREAM)
        streams = Stream.objects.filter(id__in=[sub.recipient.type_id for sub in subs])
        self.send_stream_message(self.example_email('hamlet'), streams[0].name, "test")
        add_new_user_history(user_profile, streams)

class InitialPasswordTest(ZulipTestCase):
    def test_none_initial_password_salt(self) -> None:
        with self.settings(INITIAL_PASSWORD_SALT=None):
            self.assertIsNone(initial_password('test@test.com'))

class PasswordResetTest(ZulipTestCase):
    """
    Log in, reset password, log out, log in with new password.
    """

    def test_password_reset(self) -> None:
        email = self.example_email("hamlet")
        old_password = initial_password(email)

        self.login(email)

        # test password reset template
        result = self.client_get('/accounts/password/reset/')
        self.assert_in_response('Reset your password', result)

        # start the password reset process by supplying an email address
        result = self.client_post('/accounts/password/reset/', {'email': email})

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        # Check that the password reset email is from a noreply address.
        from django.core.mail import outbox
        from_email = outbox[0].from_email
        self.assertIn("Zulip Account Security", from_email)
        tokenized_no_reply_email = parseaddr(from_email)[1]
        self.assertTrue(re.search(self.TOKENIZED_NOREPLY_REGEX, tokenized_no_reply_email))
        self.assertIn("reset your password", outbox[0].body)

        # Visit the password reset link.
        password_reset_url = self.get_confirmation_url_from_outbox(
            email, url_pattern=settings.EXTERNAL_HOST + r"(\S\S+)")
        result = self.client_get(password_reset_url)
        self.assertEqual(result.status_code, 200)

        # Reset your password
        result = self.client_post(password_reset_url,
                                  {'new_password1': 'new_password',
                                   'new_password2': 'new_password'})

        # password reset succeeded
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/password/done/"))

        # log back in with new password
        self.login(email, password='new_password')
        user_profile = self.example_user('hamlet')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

        # make sure old password no longer works
        self.login(email, password=old_password, fails=True)

    def test_password_reset_for_non_existent_user(self) -> None:
        email = 'nonexisting@mars.com'

        # start the password reset process by supplying an email address
        result = self.client_post('/accounts/password/reset/', {'email': email})

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        # Check that the password reset email is from a noreply address.
        from django.core.mail import outbox
        from_email = outbox[0].from_email
        self.assertIn("Zulip Account Security", from_email)
        tokenized_no_reply_email = parseaddr(from_email)[1]
        self.assertTrue(re.search(self.TOKENIZED_NOREPLY_REGEX, tokenized_no_reply_email))
        self.assertIn('Somebody (possibly you) requested a new password', outbox[0].body)
        self.assertIn('You do not have an account', outbox[0].body)
        self.assertIn('safely ignore', outbox[0].body)
        self.assertNotIn('reset your password', outbox[0].body)
        self.assertNotIn('deactivated', outbox[0].body)

    def test_password_reset_for_deactivated_user(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.email
        do_deactivate_user(user_profile)

        # start the password reset process by supplying an email address
        result = self.client_post('/accounts/password/reset/', {'email': email})

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        # Check that the password reset email is from a noreply address.
        from django.core.mail import outbox
        from_email = outbox[0].from_email
        self.assertIn("Zulip Account Security", from_email)
        tokenized_no_reply_email = parseaddr(from_email)[1]
        self.assertTrue(re.search(self.TOKENIZED_NOREPLY_REGEX, tokenized_no_reply_email))
        self.assertIn('Somebody (possibly you) requested a new password', outbox[0].body)
        self.assertIn('has been deactivated', outbox[0].body)
        self.assertIn('safely ignore', outbox[0].body)
        self.assertNotIn('reset your password', outbox[0].body)
        self.assertNotIn('not have an account', outbox[0].body)

    def test_password_reset_with_deactivated_realm(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.email
        do_deactivate_realm(user_profile.realm)

        # start the password reset process by supplying an email address
        with patch('logging.info') as mock_logging:
            result = self.client_post('/accounts/password/reset/', {'email': email})
            mock_logging.assert_called_once()

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        # Check that the password reset email is from a noreply address.
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    def test_wrong_subdomain(self) -> None:
        email = self.example_email("hamlet")

        # start the password reset process by supplying an email address
        result = self.client_post(
            '/accounts/password/reset/', {'email': email},
            subdomain="zephyr")

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        from django.core.mail import outbox
        self.assertEqual(len(outbox), 1)
        tokenized_no_reply_email = parseaddr(outbox[0].from_email)[1]
        self.assertTrue(re.search(self.TOKENIZED_NOREPLY_REGEX, tokenized_no_reply_email))
        self.assertIn('Somebody (possibly you) requested a new password', outbox[0].body)
        self.assertIn('You do not have an account', outbox[0].body)
        self.assertIn("active accounts in the following organization(s).\nhttp://zulip.testserver",
                      outbox[0].body)
        self.assertIn('safely ignore', outbox[0].body)
        self.assertNotIn('reset your password', outbox[0].body)
        self.assertNotIn('deactivated', outbox[0].body)

    def test_invalid_subdomain(self) -> None:
        email = self.example_email("hamlet")

        # start the password reset process by supplying an email address
        result = self.client_post(
            '/accounts/password/reset/', {'email': email},
            subdomain="invalid")

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["There is no Zulip organization hosted at this subdomain."],
                                        result)

        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_ldap_auth_only(self) -> None:
        """If the email auth backend is not enabled, password reset should do nothing"""
        email = self.example_email("hamlet")
        with patch('logging.info') as mock_logging:
            result = self.client_post('/accounts/password/reset/', {'email': email})
            mock_logging.assert_called_once()

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email in a few minutes to finish the process.", result)

        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.EmailAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_ldap_and_email_auth(self) -> None:
        """If both email and ldap auth backends are enabled, limit password
           reset to users outside the LDAP domain"""
        # If the domain matches, we don't generate an email
        with self.settings(LDAP_APPEND_DOMAIN="zulip.com"):
            email = self.example_email("hamlet")
            with patch('logging.info') as mock_logging:
                result = self.client_post('/accounts/password/reset/', {'email': email})
                mock_logging.assert_called_once_with("Password reset not allowed for user in LDAP domain")
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

        # If the domain doesn't match, we do generate an email
        with self.settings(LDAP_APPEND_DOMAIN="example.com"):
            email = self.example_email("hamlet")
            with patch('logging.info') as mock_logging:
                result = self.client_post('/accounts/password/reset/', {'email': email})
                self.assertEqual(result.status_code, 302)
                self.assertTrue(result["Location"].endswith(
                    "/accounts/password/reset/done/"))
                result = self.client_get(result["Location"])

        self.assertEqual(len(outbox), 1)
        message = outbox.pop()
        tokenized_no_reply_email = parseaddr(message.from_email)[1]
        self.assertTrue(re.search(self.TOKENIZED_NOREPLY_REGEX, tokenized_no_reply_email))
        self.assertIn('reset your password',
                      message.body)

    def test_redirect_endpoints(self) -> None:
        '''
        These tests are mostly designed to give us 100% URL coverage
        in our URL coverage reports.  Our mechanism for finding URL
        coverage doesn't handle redirects, so we just have a few quick
        tests here.
        '''
        result = self.client_get('/accounts/password/reset/done/')
        self.assert_in_success_response(["Check your email"], result)

        result = self.client_get('/accounts/password/done/')
        self.assert_in_success_response(["We've reset your password!"], result)

        result = self.client_get('/accounts/send_confirm/alice@example.com')
        self.assert_in_success_response(["/accounts/home/"], result)

        result = self.client_get('/accounts/new/send_confirm/alice@example.com')
        self.assert_in_success_response(["/new/"], result)

class LoginTest(ZulipTestCase):
    """
    Logging in, registration, and logging out.
    """

    def test_login(self) -> None:
        self.login(self.example_email("hamlet"))
        user_profile = self.example_user('hamlet')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_deactivated_user(self) -> None:
        user_profile = self.example_user('hamlet')
        do_deactivate_user(user_profile)
        result = self.login_with_return(self.example_email("hamlet"), "xxx")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Your account is no longer active.", result)
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_login_bad_password(self) -> None:
        email = self.example_email("hamlet")
        result = self.login_with_return(email, password="wrongpassword")
        self.assert_in_success_response([email], result)
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_login_nonexist_user(self) -> None:
        result = self.login_with_return("xxx@zulip.com", "xxx")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Please enter a correct email and password", result)
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_login_wrong_subdomain(self) -> None:
        with patch("logging.warning") as mock_warning:
            result = self.login_with_return(self.mit_email("sipbtest"), "xxx")
            mock_warning.assert_called_once()
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Your Zulip account is not a member of the "
                                "organization associated with this subdomain.", result)
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_login_invalid_subdomain(self) -> None:
        result = self.login_with_return(self.example_email("hamlet"), "xxx",
                                        subdomain="invalid")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("There is no Zulip organization hosted at this subdomain.", result)
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_register(self) -> None:
        realm = get_realm("zulip")
        stream_dict = {"stream_"+str(i): {"description": "stream_%s_description" % i, "invite_only": False}
                       for i in range(40)}  # type: Dict[str, Dict[str, Any]]
        for stream_name in stream_dict.keys():
            self.make_stream(stream_name, realm=realm)

        set_default_streams(realm, stream_dict)
        # Clear all the caches.
        flush_per_request_caches()
        ContentType.objects.clear_cache()

        with queries_captured() as queries:
            self.register(self.nonreg_email('test'), "test")
        # Ensure the number of queries we make is not O(streams)
        self.assert_length(queries, 74)
        user_profile = self.nonreg_user('test')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)
        self.assertFalse(user_profile.enable_stream_desktop_notifications)

    def test_register_deactivated(self) -> None:
        """
        If you try to register for a deactivated realm, you get a clear error
        page.
        """
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.client_post('/accounts/home/', {'email': self.nonreg_email('test')},
                                  subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual('/accounts/deactivated/', result.url)

        with self.assertRaises(UserProfile.DoesNotExist):
            self.nonreg_user('test')

    def test_register_deactivated_partway_through(self) -> None:
        """
        If you try to register for a deactivated realm, you get a clear error
        page.
        """
        email = self.nonreg_email('test')
        result = self.client_post('/accounts/home/', {'email': email},
                                  subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertNotIn('deactivated', result.url)

        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.submit_reg_form_for_user(email, "abcd1234", subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual('/accounts/deactivated/', result.url)

        with self.assertRaises(UserProfile.DoesNotExist):
            self.nonreg_user('test')

    def test_login_deactivated_realm(self) -> None:
        """
        If you try to log in to a deactivated realm, you get a clear error page.
        """
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.login_with_return(self.example_email("hamlet"), subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual('/accounts/deactivated/', result.url)

    def test_logout(self) -> None:
        self.login(self.example_email("hamlet"))
        # We use the logout API, not self.logout, to make sure we test
        # the actual logout code path.
        self.client_post('/accounts/logout/')
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_non_ascii_login(self) -> None:
        """
        You can log in even if your password contain non-ASCII characters.
        """
        email = self.nonreg_email('test')
        password = u"hÃ¼mbÃ¼Çµ"

        # Registering succeeds.
        self.register(email, password)
        user_profile = self.nonreg_user('test')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)
        self.logout()
        self.assertIsNone(get_session_dict_user(self.client.session))

        # Logging in succeeds.
        self.logout()
        self.login(email, password)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    @override_settings(TWO_FACTOR_AUTHENTICATION_ENABLED=False)
    def test_login_page_redirects_logged_in_user(self) -> None:
        """You will be redirected to the app's main page if you land on the
        login page when already logged in.
        """
        self.login(self.example_email("cordelia"))
        response = self.client_get("/login/")
        self.assertEqual(response["Location"], "http://zulip.testserver")

    def test_options_request_to_login_page(self) -> None:
        response = self.client_options('/login/')
        self.assertEqual(response.status_code, 200)

    @override_settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True)
    def test_login_page_redirects_logged_in_user_under_2fa(self) -> None:
        """You will be redirected to the app's main page if you land on the
        login page when already logged in.
        """
        user_profile = self.example_user("cordelia")
        self.create_default_device(user_profile)

        self.login(self.example_email("cordelia"))
        self.login_2fa(user_profile)

        response = self.client_get("/login/")
        self.assertEqual(response["Location"], "http://zulip.testserver")

    def test_start_two_factor_auth(self) -> None:
        request = MagicMock(POST=dict())
        with patch('zerver.views.auth.TwoFactorLoginView') as mock_view:
            mock_view.as_view.return_value = lambda *a, **k: HttpResponse()
            response = start_two_factor_auth(request)
            self.assertTrue(isinstance(response, HttpResponse))

    def test_do_two_factor_login(self) -> None:
        user_profile = self.example_user('hamlet')
        self.create_default_device(user_profile)
        request = MagicMock()
        with patch('zerver.decorator.django_otp.login') as mock_login:
            do_two_factor_login(request, user_profile)
            mock_login.assert_called_once()

class InviteUserBase(ZulipTestCase):
    def check_sent_emails(self, correct_recipients: List[str],
                          custom_from_name: Optional[str]=None) -> None:
        from django.core.mail import outbox
        self.assertEqual(len(outbox), len(correct_recipients))
        email_recipients = [email.recipients()[0] for email in outbox]
        self.assertEqual(sorted(email_recipients), sorted(correct_recipients))
        if len(outbox) == 0:
            return

        if custom_from_name is not None:
            self.assertIn(custom_from_name, outbox[0].from_email)

        tokenized_no_reply_email = parseaddr(outbox[0].from_email)[1]
        self.assertTrue(re.search(self.TOKENIZED_NOREPLY_REGEX, tokenized_no_reply_email))

    INVALID_STREAM_ID = 9999

    def get_stream_id(self, name: str, realm: Optional[Realm]=None) -> int:
        if not realm:
            realm = get_realm('zulip')
        try:
            stream = get_realm_stream(name, realm.id)
        except Stream.DoesNotExist:
            return self.INVALID_STREAM_ID
        return stream.id

    def invite(self, invitee_emails: str, stream_names: List[str], body: str='',
               invite_as: int=1) -> HttpResponse:
        """
        Invites the specified users to Zulip with the specified streams.

        users should be a string containing the users to invite, comma or
            newline separated.

        streams should be a list of strings.
        """
        stream_ids = []
        for stream_name in stream_names:
            stream_ids.append(self.get_stream_id(stream_name))
        return self.client_post("/json/invites",
                                {"invitee_emails": invitee_emails,
                                 "stream_ids": ujson.dumps(stream_ids),
                                 "invite_as": invite_as})

class InviteUserTest(InviteUserBase):
    def test_successful_invite_user(self) -> None:
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login(self.example_email("hamlet"))
        invitee = "alice-test@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee))
        self.check_sent_emails([invitee], custom_from_name="Hamlet")

    def test_newbie_restrictions(self) -> None:
        user_profile = self.example_user('hamlet')
        invitee = "alice-test@zulip.com"
        stream_name = 'Denmark'

        self.login(user_profile.email)

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
        user_profile = self.example_user('hamlet')
        realm = user_profile.realm
        stream_name = 'Denmark'

        # These constants only need to be in descending order
        # for this test to trigger an InvitationError based
        # on max daily counts.
        site_max = 50
        realm_max = 40
        num_invitees = 30
        max_daily_count = 20

        daily_counts = [(1, max_daily_count)]

        invite_emails = [
            'foo-%02d@zulip.com' % (i,)
            for i in range(num_invitees)
        ]
        invitees = ','.join(invite_emails)

        self.login(user_profile.email)

        realm.max_invites = realm_max
        realm.date_created = timezone_now()
        realm.save()

        def try_invite() -> HttpResponse:
            with self.settings(OPEN_REALM_CREATION=True,
                               INVITES_DEFAULT_REALM_DAILY_MAX=site_max,
                               INVITES_NEW_REALM_LIMIT_DAYS=daily_counts):
                result = self.invite(invitees, [stream_name])
                return result

        result = try_invite()
        self.assert_json_error_contains(result, 'enough remaining invites')

        # Next show that aggregate limits expire once the realm is old
        # enough.

        realm.date_created = timezone_now() - datetime.timedelta(days=8)
        realm.save()

        result = try_invite()
        self.assert_json_success(result)

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

    def test_successful_invite_user_as_admin_from_admin_account(self) -> None:
        """
        Test that a new user invited to a stream receives some initial
        history but only from public streams.
        """
        self.login(self.example_email('iago'))
        invitee = self.nonreg_email('alice')
        result = self.invite(invitee, ["Denmark"],
                             invite_as=PreregistrationUser.INVITE_AS['REALM_ADMIN'])
        self.assert_json_success(result)
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user('alice')
        self.assertTrue(invitee_profile.is_realm_admin)
        self.assertFalse(invitee_profile.is_guest)

    def test_invite_user_as_admin_from_normal_account(self) -> None:
        """
        Test that a new user invited to a stream receives some initial
        history but only from public streams.
        """
        self.login(self.example_email('hamlet'))
        invitee = self.nonreg_email('alice')
        response = self.invite(invitee, ["Denmark"],
                               invite_as=PreregistrationUser.INVITE_AS['REALM_ADMIN'])
        self.assert_json_error(response, "Must be an organization administrator")

    def test_invite_user_as_invalid_type(self) -> None:
        """
        Test inviting a user as invalid type of user i.e. type of invite_as
        is not in PreregistrationUser.INVITE_AS
        """
        self.login(self.example_email('iago'))
        invitee = self.nonreg_email('alice')
        response = self.invite(invitee, ["Denmark"], invite_as=100)
        self.assert_json_error(response, "Must be invited as an valid type of user")

    def test_successful_invite_user_as_guest_from_normal_account(self) -> None:
        self.login(self.example_email('hamlet'))
        invitee = self.nonreg_email('alice')
        self.assert_json_success(self.invite(invitee, ["Denmark"],
                                             invite_as=PreregistrationUser.INVITE_AS['GUEST_USER']))
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user('alice')
        self.assertFalse(invitee_profile.is_realm_admin)
        self.assertTrue(invitee_profile.is_guest)

    def test_successful_invite_user_as_guest_from_admin_account(self) -> None:
        self.login(self.example_email('iago'))
        invitee = self.nonreg_email('alice')
        self.assert_json_success(self.invite(invitee, ["Denmark"],
                                             invite_as=PreregistrationUser.INVITE_AS['GUEST_USER']))
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user('alice')
        self.assertFalse(invitee_profile.is_realm_admin)
        self.assertTrue(invitee_profile.is_guest)

    def test_successful_invite_user_with_name(self) -> None:
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login(self.example_email("hamlet"))
        email = "alice-test@zulip.com"
        invitee = "Alice Test <{}>".format(email)
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.check_sent_emails([email], custom_from_name="Hamlet")

    def test_successful_invite_user_with_name_and_normal_one(self) -> None:
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login(self.example_email("hamlet"))
        email = "alice-test@zulip.com"
        email2 = "bob-test@zulip.com"
        invitee = "Alice Test <{}>, {}".format(email, email2)
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2], custom_from_name="Hamlet")

    def test_require_realm_admin(self) -> None:
        """
        The invite_by_admins_only realm setting works properly.
        """
        realm = get_realm('zulip')
        realm.invite_by_admins_only = True
        realm.save()

        self.login("hamlet@zulip.com")
        email = "alice-test@zulip.com"
        email2 = "bob-test@zulip.com"
        invitee = "Alice Test <{}>, {}".format(email, email2)
        self.assert_json_error(self.invite(invitee, ["Denmark"]),
                               "Must be an organization administrator")

        # Now verify an administrator can do it
        self.login("iago@zulip.com")
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

    def test_successful_invite_user_with_notifications_stream(self) -> None:
        """
        A call to /json/invites with valid parameters unconditionally
        subscribes the invitee to the notifications stream if it exists and is
        public.
        """
        realm = get_realm('zulip')
        notifications_stream = get_stream('Verona', realm)
        realm.notifications_stream_id = notifications_stream.id
        realm.save()

        self.login(self.example_email("hamlet"))
        invitee = 'alice-test@zulip.com'
        self.assert_json_success(self.invite(invitee, ['Denmark']))
        self.assertTrue(find_key_by_email(invitee))
        self.check_sent_emails([invitee])

        prereg_user = PreregistrationUser.objects.get(email=invitee)
        stream_ids = [stream.id for stream in prereg_user.streams.all()]
        self.assertTrue(notifications_stream.id in stream_ids)

    def test_invite_user_signup_initial_history(self) -> None:
        """
        Test that a new user invited to a stream receives some initial
        history but only from public streams.
        """
        self.login(self.example_email('hamlet'))
        user_profile = self.example_user('hamlet')
        private_stream_name = "Secret"
        self.make_stream(private_stream_name, invite_only=True)
        self.subscribe(user_profile, private_stream_name)
        public_msg_id = self.send_stream_message(
            self.example_email("hamlet"),
            "Denmark",
            topic_name="Public topic",
            content="Public message",
        )
        secret_msg_id = self.send_stream_message(
            self.example_email("hamlet"),
            private_stream_name,
            topic_name="Secret topic",
            content="Secret message",
        )
        invitee = self.nonreg_email('alice')
        self.assert_json_success(self.invite(invitee, [private_stream_name, "Denmark"]))
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user('alice')
        invitee_msg_ids = [um.message_id for um in
                           UserMessage.objects.filter(user_profile=invitee_profile)]
        self.assertTrue(public_msg_id in invitee_msg_ids)
        self.assertFalse(secret_msg_id in invitee_msg_ids)
        self.assertFalse(invitee_profile.is_realm_admin)
        # Test that exactly 2 new Zulip messages were sent, both notifications.
        last_3_messages = list(reversed(list(Message.objects.all().order_by("-id")[0:3])))
        first_msg = last_3_messages[0]
        self.assertEqual(first_msg.id, secret_msg_id)

        # The first, from notification-bot to the user who invited the new user.
        second_msg = last_3_messages[1]
        self.assertEqual(second_msg.sender.email, "notification-bot@zulip.com")
        self.assertTrue(second_msg.content.startswith("alice_zulip.com <`alice@zulip.com`> accepted your"))

        # The second, from welcome-bot to the user who was invited.
        third_msg = last_3_messages[2]
        self.assertEqual(third_msg.sender.email, "welcome-bot@zulip.com")
        self.assertTrue(third_msg.content.startswith("Hello, and welcome to Zulip!"))

    def test_multi_user_invite(self) -> None:
        """
        Invites multiple users with a variety of delimiters.
        """
        self.login(self.example_email("hamlet"))
        # Intentionally use a weird string.
        self.assert_json_success(self.invite(
            """bob-test@zulip.com,     carol-test@zulip.com,
            dave-test@zulip.com


earl-test@zulip.com""", ["Denmark"]))
        for user in ("bob", "carol", "dave", "earl"):
            self.assertTrue(find_key_by_email("%s-test@zulip.com" % (user,)))
        self.check_sent_emails(["bob-test@zulip.com", "carol-test@zulip.com",
                                "dave-test@zulip.com", "earl-test@zulip.com"])

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
        self.login(self.example_email("iago"))
        invitee_emails = "1@zulip.com, 2@zulip.com"
        self.invite(invitee_emails, ["Denmark"])
        invitee_emails = ", ".join([str(i) for i in range(get_realm("zulip").max_invites - 1)])
        self.assert_json_error(self.invite(invitee_emails, ["Denmark"]),
                               "You do not have enough remaining invites. "
                               "Please contact zulip-admin@example.com to have your limit raised. "
                               "No invitations were sent.")

    def test_missing_or_invalid_params(self) -> None:
        """
        Tests inviting with various missing or invalid parameters.
        """
        self.login(self.example_email("hamlet"))
        invitee_emails = "foo@zulip.com"
        self.assert_json_error(self.invite(invitee_emails, []),
                               "You must specify at least one stream for invitees to join.")

        for address in ("noatsign.com", "outsideyourdomain@example.net"):
            self.assert_json_error(
                self.invite(address, ["Denmark"]),
                "Some emails did not validate, so we didn't send any invitations.")
        self.check_sent_emails([])

        self.assert_json_error(
            self.invite("", ["Denmark"]),
            "You must specify at least one email address.")
        self.check_sent_emails([])

    def test_guest_user_invitation(self) -> None:
        """
        Guest user can't invite new users
        """
        self.login(self.example_email("polonius"))
        invitee = "alice-test@zulip.com"
        self.assert_json_error(self.invite(invitee, ["Denmark"]), "Not allowed for guest users")
        self.assertEqual(find_key_by_email(invitee), None)
        self.check_sent_emails([])

    def test_invalid_stream(self) -> None:
        """
        Tests inviting to a non-existent stream.
        """
        self.login(self.example_email("hamlet"))
        self.assert_json_error(self.invite("iago-test@zulip.com", ["NotARealStream"]),
                               "Stream does not exist with id: {}. No invites were sent.".format(self.INVALID_STREAM_ID))
        self.check_sent_emails([])

    def test_invite_existing_user(self) -> None:
        """
        If you invite an address already using Zulip, no invitation is sent.
        """
        self.login(self.example_email("hamlet"))
        self.assert_json_error(self.invite(self.example_email("hamlet"), ["Denmark"]),
                               "We weren't able to invite anyone.")
        self.assertRaises(PreregistrationUser.DoesNotExist,
                          lambda: PreregistrationUser.objects.get(
                              email=self.example_email("hamlet")))
        self.check_sent_emails([])

    def test_invite_some_existing_some_new(self) -> None:
        """
        If you invite a mix of already existing and new users, invitations are
        only sent to the new users.
        """
        self.login(self.example_email("hamlet"))
        existing = [self.example_email("hamlet"), u"othello@zulip.com"]
        new = [u"foo-test@zulip.com", u"bar-test@zulip.com"]
        invitee_emails = "\n".join(existing + new)
        self.assert_json_error(self.invite(invitee_emails, ["Denmark"]),
                               "Some of those addresses are already using Zulip, \
so we didn't send them an invitation. We did send invitations to everyone else!")

        # We only created accounts for the new users.
        for email in existing:
            self.assertRaises(PreregistrationUser.DoesNotExist,
                              lambda: PreregistrationUser.objects.get(
                                  email=email))
        for email in new:
            self.assertTrue(PreregistrationUser.objects.get(email=email))

        # We only sent emails to the new users.
        self.check_sent_emails(new)

        prereg_user = PreregistrationUser.objects.get(email='foo-test@zulip.com')
        self.assertEqual(prereg_user.email, 'foo-test@zulip.com')

    def test_invite_outside_domain_in_closed_realm(self) -> None:
        """
        In a realm with `emails_restricted_to_domains = True`, you can't invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = True
        zulip_realm.save()

        self.login(self.example_email("hamlet"))
        external_address = "foo@example.com"

        self.assert_json_error(
            self.invite(external_address, ["Denmark"]),
            "Some emails did not validate, so we didn't send any invitations.")

    def test_invite_using_disposable_email(self) -> None:
        """
        In a realm with `disallow_disposable_email_addresses = True`, you can't invite
        people with a disposable domain.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.disallow_disposable_email_addresses = True
        zulip_realm.save()

        self.login(self.example_email("hamlet"))
        external_address = "foo@mailnator.com"

        self.assert_json_error(
            self.invite(external_address, ["Denmark"]),
            "Some emails did not validate, so we didn't send any invitations.")

    def test_invite_outside_domain_in_open_realm(self) -> None:
        """
        In a realm with `emails_restricted_to_domains = False`, you can invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.save()

        self.login(self.example_email("hamlet"))
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

        self.login(self.example_email("hamlet"))
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

        self.login(self.example_email("hamlet"))
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
        users are not allowed to signup using email containing +
        when the realm is restricted to domain.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.save()

        self.login(self.example_email("hamlet"))
        external_address = "foo+label@zulip.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

        zulip_realm.emails_restricted_to_domains = True
        zulip_realm.save()

        result = self.submit_reg_form_for_user(external_address, "password")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Zulip Dev, does not allow signups using emails\n        that contains +", result)

    def test_invalid_email_check_after_confirming_email(self) -> None:
        self.login(self.example_email("hamlet"))
        email = "test@zulip.com"

        self.assert_json_success(self.invite(email, ["Denmark"]))

        obj = Confirmation.objects.get(confirmation_key=find_key_by_email(email))
        prereg_user = obj.content_object
        prereg_user.email = "invalid.email"
        prereg_user.save()

        result = self.submit_reg_form_for_user(email, "password")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("The email address you are trying to sign up with is not valid", result)

    def test_invite_with_non_ascii_streams(self) -> None:
        """
        Inviting someone to streams with non-ASCII characters succeeds.
        """
        self.login(self.example_email("hamlet"))
        invitee = "alice-test@zulip.com"

        stream_name = u"hÃ¼mbÃ¼Çµ"

        # Make sure we're subscribed before inviting someone.
        self.subscribe(self.example_user("hamlet"), stream_name)

        self.assert_json_success(self.invite(invitee, [stream_name]))

    def test_invitation_reminder_email(self) -> None:
        from django.core.mail import outbox

        # All users belong to zulip realm
        referrer_user = 'hamlet'
        current_user_email = self.example_email(referrer_user)
        self.login(current_user_email)
        invitee_email = self.nonreg_email('alice')
        self.assert_json_success(self.invite(invitee_email, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee_email))
        self.check_sent_emails([invitee_email])

        data = {"email": invitee_email, "referrer_email": current_user_email}
        invitee = PreregistrationUser.objects.get(email=data["email"])
        referrer = self.example_user(referrer_user)
        link = create_confirmation_link(invitee, referrer.realm.host, Confirmation.INVITATION)
        context = common_context(referrer)
        context.update({
            'activate_url': link,
            'referrer_name': referrer.full_name,
            'referrer_email': referrer.email,
            'referrer_realm_name': referrer.realm.name,
        })
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'):
            email = data["email"]
            send_future_email(
                "zerver/emails/invitation_reminder", referrer.realm, to_emails=[email],
                from_address=FromAddress.NOREPLY, context=context)
        email_jobs_to_deliver = ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now())
        self.assertEqual(len(email_jobs_to_deliver), 1)
        email_count = len(outbox)
        for job in email_jobs_to_deliver:
            send_email(**ujson.loads(job.data))
        self.assertEqual(len(outbox), email_count + 1)
        self.assertIn(FromAddress.NOREPLY, outbox[-1].from_email)

        # Now verify that signing up clears invite_reminder emails
        email_jobs_to_deliver = ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now(), type=ScheduledEmail.INVITATION_REMINDER)
        self.assertEqual(len(email_jobs_to_deliver), 1)

        self.register(invitee_email, "test")
        email_jobs_to_deliver = ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now(), type=ScheduledEmail.INVITATION_REMINDER)
        self.assertEqual(len(email_jobs_to_deliver), 0)

    # make sure users can't take a valid confirmation key from another
    # pathway and use it with the invitation url route
    def test_confirmation_key_of_wrong_type(self) -> None:
        user = self.example_user('hamlet')
        url = create_confirmation_link(user, 'host', Confirmation.USER_REGISTRATION)
        registration_key = url.split('/')[-1]

        # Mainly a test of get_object_from_key, rather than of the invitation pathway
        with self.assertRaises(ConfirmationKeyException) as cm:
            get_object_from_key(registration_key, Confirmation.INVITATION)
        self.assertEqual(cm.exception.error_type, ConfirmationKeyException.DOES_NOT_EXIST)

        # Verify that using the wrong type doesn't work in the main confirm code path
        email_change_url = create_confirmation_link(user, 'host', Confirmation.EMAIL_CHANGE)
        email_change_key = email_change_url.split('/')[-1]
        url = '/accounts/do_confirm/' + email_change_key
        result = self.client_get(url)
        self.assert_in_success_response(["Whoops. We couldn't find your "
                                         "confirmation link in the system."], result)

    def test_confirmation_expired(self) -> None:
        user = self.example_user('hamlet')
        url = create_confirmation_link(user, 'host', Confirmation.USER_REGISTRATION)
        registration_key = url.split('/')[-1]

        conf = Confirmation.objects.filter(confirmation_key=registration_key).first()
        conf.date_sent -= datetime.timedelta(weeks=3)
        conf.save()

        target_url = '/' + url.split('/', 3)[3]
        result = self.client_get(target_url)
        self.assert_in_success_response(["Whoops. The confirmation link has expired "
                                         "or been deactivated."], result)

class InvitationsTestCase(InviteUserBase):
    def test_successful_get_open_invitations(self) -> None:
        """
        A GET call to /json/invites returns all unexpired invitations.
        """
        realm = get_realm("zulip")
        days_to_activate = getattr(settings, 'INVITATION_LINK_VALIDITY_DAYS', "Wrong")
        active_value = getattr(confirmation_settings, 'STATUS_ACTIVE', "Wrong")
        self.assertNotEqual(days_to_activate, "Wrong")
        self.assertNotEqual(active_value, "Wrong")

        self.login(self.example_email("iago"))
        user_profile = self.example_user("iago")

        prereg_user_one = PreregistrationUser(email="TestOne@zulip.com", referred_by=user_profile)
        prereg_user_one.save()
        expired_datetime = timezone_now() - datetime.timedelta(days=(days_to_activate+1))
        prereg_user_two = PreregistrationUser(email="TestTwo@zulip.com", referred_by=user_profile)
        prereg_user_two.save()
        PreregistrationUser.objects.filter(id=prereg_user_two.id).update(invited_at=expired_datetime)
        prereg_user_three = PreregistrationUser(email="TestThree@zulip.com",
                                                referred_by=user_profile, status=active_value)
        prereg_user_three.save()

        multiuse_invite_one = MultiuseInvite.objects.create(referred_by=self.example_user("hamlet"), realm=realm)
        create_confirmation_link(multiuse_invite_one, realm.host, Confirmation.MULTIUSE_INVITE)

        multiuse_invite_two = MultiuseInvite.objects.create(referred_by=self.example_user("othello"), realm=realm)
        create_confirmation_link(multiuse_invite_two, realm.host, Confirmation.MULTIUSE_INVITE)
        confirmation = Confirmation.objects.last()
        confirmation.date_sent = expired_datetime
        confirmation.save()

        result = self.client_get("/json/invites")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["TestOne@zulip.com", "hamlet@zulip.com"], result)
        self.assert_not_in_success_response(["TestTwo@zulip.com", "TestThree@zulip.com", "othello@zulip.com"], result)

    def test_successful_delete_invitation(self) -> None:
        """
        A DELETE call to /json/invites/<ID> should delete the invite and
        any scheduled invitation reminder emails.
        """
        self.login(self.example_email("iago"))

        invitee = "DeleteMe@zulip.com"
        self.assert_json_success(self.invite(invitee, ['Denmark']))
        prereg_user = PreregistrationUser.objects.get(email=invitee)

        # Verify that the scheduled email exists.
        ScheduledEmail.objects.get(address__iexact=invitee,
                                   type=ScheduledEmail.INVITATION_REMINDER)

        result = self.client_delete('/json/invites/' + str(prereg_user.id))
        self.assertEqual(result.status_code, 200)
        error_result = self.client_delete('/json/invites/' + str(prereg_user.id))
        self.assert_json_error(error_result, "No such invitation")

        self.assertRaises(ScheduledEmail.DoesNotExist,
                          lambda: ScheduledEmail.objects.get(address__iexact=invitee,
                                                             type=ScheduledEmail.INVITATION_REMINDER))

    def test_delete_multiuse_invite(self) -> None:
        """
        A DELETE call to /json/invites/multiuse<ID> should delete the
        multiuse_invite.
        """
        self.login(self.example_email("iago"))

        zulip_realm = get_realm("zulip")
        multiuse_invite = MultiuseInvite.objects.create(referred_by=self.example_user("hamlet"), realm=zulip_realm)
        create_confirmation_link(multiuse_invite, zulip_realm.host, Confirmation.MULTIUSE_INVITE)
        result = self.client_delete('/json/invites/multiuse/' + str(multiuse_invite.id))
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(MultiuseInvite.objects.filter(id=multiuse_invite.id).first())
        # Test that trying to double-delete fails
        error_result = self.client_delete('/json/invites/multiuse/' + str(multiuse_invite.id))
        self.assert_json_error(error_result, "No such invitation")

        # Test deleting multiuse invite from another realm
        mit_realm = get_realm("zephyr")
        multiuse_invite_in_mit = MultiuseInvite.objects.create(referred_by=self.mit_user("sipbtest"), realm=mit_realm)
        create_confirmation_link(multiuse_invite_in_mit, mit_realm.host, Confirmation.MULTIUSE_INVITE)
        error_result = self.client_delete('/json/invites/multiuse/' + str(multiuse_invite_in_mit.id))
        self.assert_json_error(error_result, "No such invitation")

    def test_successful_resend_invitation(self) -> None:
        """
        A POST call to /json/invites/<ID>/resend should send an invitation reminder email
        and delete any scheduled invitation reminder email.
        """
        self.login(self.example_email("iago"))
        invitee = "resend_me@zulip.com"

        self.assert_json_success(self.invite(invitee, ['Denmark']))
        prereg_user = PreregistrationUser.objects.get(email=invitee)

        # Verify and then clear from the outbox the original invite email
        self.check_sent_emails([invitee], custom_from_name="Zulip")
        from django.core.mail import outbox
        outbox.pop()

        # Verify that the scheduled email exists.
        scheduledemail_filter = ScheduledEmail.objects.filter(
            address=invitee, type=ScheduledEmail.INVITATION_REMINDER)
        self.assertEqual(scheduledemail_filter.count(), 1)
        original_timestamp = scheduledemail_filter.values_list('scheduled_timestamp', flat=True)

        # Resend invite
        result = self.client_post('/json/invites/' + str(prereg_user.id) + '/resend')
        self.assertEqual(ScheduledEmail.objects.filter(
            address=invitee, type=ScheduledEmail.INVITATION_REMINDER).count(), 1)

        # Check that we have exactly one scheduled email, and that it is different
        self.assertEqual(scheduledemail_filter.count(), 1)
        self.assertNotEqual(original_timestamp,
                            scheduledemail_filter.values_list('scheduled_timestamp', flat=True))

        self.assertEqual(result.status_code, 200)
        error_result = self.client_post('/json/invites/' + str(9999) + '/resend')
        self.assert_json_error(error_result, "No such invitation")

        self.check_sent_emails([invitee], custom_from_name="Zulip")

    def test_accessing_invites_in_another_realm(self) -> None:
        invitor = UserProfile.objects.exclude(realm=get_realm('zulip')).first()
        prereg_user = PreregistrationUser.objects.create(
            email='email', referred_by=invitor, realm=invitor.realm)
        self.login(self.example_email("iago"))
        error_result = self.client_post('/json/invites/' + str(prereg_user.id) + '/resend')
        self.assert_json_error(error_result, "No such invitation")
        error_result = self.client_delete('/json/invites/' + str(prereg_user.id))
        self.assert_json_error(error_result, "No such invitation")

class InviteeEmailsParserTests(TestCase):
    def setUp(self) -> None:
        self.email1 = "email1@zulip.com"
        self.email2 = "email2@zulip.com"
        self.email3 = "email3@zulip.com"

    def test_if_emails_separated_by_commas_are_parsed_and_striped_correctly(self) -> None:
        emails_raw = "{} ,{}, {}".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_separated_by_newlines_are_parsed_and_striped_correctly(self) -> None:
        emails_raw = "{}\n {}\n {} ".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_from_email_client_separated_by_newlines_are_parsed_correctly(self) -> None:
        emails_raw = "Email One <{}>\nEmailTwo<{}>\nEmail Three<{}>".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_in_mixed_style_are_parsed_correctly(self) -> None:
        emails_raw = "Email One <{}>,EmailTwo<{}>\n{}".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

class MultiuseInviteTest(ZulipTestCase):
    def setUp(self) -> None:
        self.realm = get_realm('zulip')
        self.realm.invite_required = True
        self.realm.save()

    def generate_multiuse_invite_link(self, streams: List[Stream]=None,
                                      date_sent: Optional[datetime.datetime]=None) -> str:
        invite = MultiuseInvite(realm=self.realm, referred_by=self.example_user("iago"))
        invite.save()

        if streams is not None:
            invite.streams.set(streams)

        if date_sent is None:
            date_sent = timezone_now()
        key = generate_key()
        Confirmation.objects.create(content_object=invite, date_sent=date_sent,
                                    confirmation_key=key, type=Confirmation.MULTIUSE_INVITE)

        return confirmation_url(key, self.realm.host, Confirmation.MULTIUSE_INVITE)

    def check_user_able_to_register(self, email: str, invite_link: str) -> None:
        password = "password"

        result = self.client_post(invite_link, {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
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

        date_sent = timezone_now() - datetime.timedelta(days=settings.INVITATION_LINK_VALIDITY_DAYS - 1)
        invite_link = self.generate_multiuse_invite_link(date_sent=date_sent)

        self.check_user_able_to_register(email1, invite_link)
        self.check_user_able_to_register(email2, invite_link)
        self.check_user_able_to_register(email3, invite_link)

    def test_expired_multiuse_link(self) -> None:
        email = self.nonreg_email('newuser')
        date_sent = timezone_now() - datetime.timedelta(days=settings.INVITATION_LINK_VALIDITY_DAYS)
        invite_link = self.generate_multiuse_invite_link(date_sent=date_sent)
        result = self.client_post(invite_link, {'email': email})

        self.assertEqual(result.status_code, 200)
        self.assert_in_response("The confirmation link has expired or been deactivated.", result)

    def test_invalid_multiuse_link(self) -> None:
        email = self.nonreg_email('newuser')
        invite_link = "/join/invalid_key/"
        result = self.client_post(invite_link, {'email': email})

        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Whoops. The confirmation link is malformed.", result)

    def test_invalid_multiuse_link_in_open_realm(self) -> None:
        self.realm.invite_required = False
        self.realm.save()

        email = self.nonreg_email('newuser')
        invite_link = "/join/invalid_key/"

        with patch('zerver.views.registration.get_realm_from_request', return_value=self.realm):
            with patch('zerver.views.registration.get_realm', return_value=self.realm):
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
        self.login(self.example_email('iago'))

        result = self.client_post('/json/invites/multiuse')
        self.assert_json_success(result)

        invite_link = result.json()["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)

    def test_create_multiuse_link_with_specified_streams_api_call(self) -> None:
        self.login(self.example_email('iago'))
        stream_names = ["Rome", "Scotland", "Venice"]
        streams = [get_stream(stream_name, self.realm) for stream_name in stream_names]
        stream_ids = [stream.id for stream in streams]

        result = self.client_post('/json/invites/multiuse',
                                  {"stream_ids": ujson.dumps(stream_ids)})
        self.assert_json_success(result)

        invite_link = result.json()["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)
        self.check_user_subscribed_only_to_streams("test", streams)

    def test_only_admin_can_create_multiuse_link_api_call(self) -> None:
        self.login(self.example_email('iago'))
        # Only admins should be able to create multiuse invites even if
        # invite_by_admins_only is set to False.
        self.realm.invite_by_admins_only = False
        self.realm.save()

        result = self.client_post('/json/invites/multiuse')
        self.assert_json_success(result)

        invite_link = result.json()["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)

        self.login(self.example_email('hamlet'))
        result = self.client_post('/json/invites/multiuse')
        self.assert_json_error(result, "Must be an organization administrator")

    def test_create_multiuse_link_invalid_stream_api_call(self) -> None:
        self.login(self.example_email('iago'))
        result = self.client_post('/json/invites/multiuse',
                                  {"stream_ids": ujson.dumps([54321])})
        self.assert_json_error(result, "Invalid stream id 54321. No invites were sent.")

class EmailUnsubscribeTests(ZulipTestCase):
    def test_error_unsubscribe(self) -> None:

        # An invalid unsubscribe token "test123" produces an error.
        result = self.client_get('/accounts/unsubscribe/missed_messages/test123')
        self.assert_in_response('Unknown email unsubscribe request', result)

        # An unknown message type "fake" produces an error.
        user_profile = self.example_user('hamlet')
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "fake")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)
        self.assert_in_response('Unknown email unsubscribe request', result)

    def test_missedmessage_unsubscribe(self) -> None:
        """
        We provide one-click unsubscribe links in missed message
        e-mails that you can click even when logged out to update your
        email notification settings.
        """
        user_profile = self.example_user('hamlet')
        user_profile.enable_offline_email_notifications = True
        user_profile.save()

        unsubscribe_link = one_click_unsubscribe_link(user_profile,
                                                      "missed_messages")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

        self.assertEqual(result.status_code, 200)

        user_profile.refresh_from_db()
        self.assertFalse(user_profile.enable_offline_email_notifications)

    def test_welcome_unsubscribe(self) -> None:
        """
        We provide one-click unsubscribe links in welcome e-mails that you can
        click even when logged out to stop receiving them.
        """
        user_profile = self.example_user('hamlet')
        # Simulate a new user signing up, which enqueues 2 welcome e-mails.
        enqueue_welcome_emails(user_profile)
        self.assertEqual(2, ScheduledEmail.objects.filter(user=user_profile).count())

        # Simulate unsubscribing from the welcome e-mails.
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "welcome")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

        # The welcome email jobs are no longer scheduled.
        self.assertEqual(result.status_code, 200)
        self.assertEqual(0, ScheduledEmail.objects.filter(user=user_profile).count())

    def test_digest_unsubscribe(self) -> None:
        """
        We provide one-click unsubscribe links in digest e-mails that you can
        click even when logged out to stop receiving them.

        Unsubscribing from these emails also dequeues any digest email jobs that
        have been queued.
        """
        user_profile = self.example_user('hamlet')
        self.assertTrue(user_profile.enable_digest_emails)

        # Enqueue a fake digest email.
        context = {'name': '', 'realm_uri': '', 'unread_pms': [], 'hot_conversations': [],
                   'new_users': [], 'new_streams': {'plain': []}, 'unsubscribe_link': ''}
        send_future_email('zerver/emails/digest', user_profile.realm,
                          to_user_ids=[user_profile.id], context=context)

        self.assertEqual(1, ScheduledEmail.objects.filter(user=user_profile).count())

        # Simulate unsubscribing from digest e-mails.
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "digest")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

        # The setting is toggled off, and scheduled jobs have been removed.
        self.assertEqual(result.status_code, 200)
        # Circumvent user_profile caching.

        user_profile.refresh_from_db()
        self.assertFalse(user_profile.enable_digest_emails)
        self.assertEqual(0, ScheduledEmail.objects.filter(user=user_profile).count())

    def test_login_unsubscribe(self) -> None:
        """
        We provide one-click unsubscribe links in login
        e-mails that you can click even when logged out to update your
        email notification settings.
        """
        user_profile = self.example_user('hamlet')
        user_profile.enable_login_emails = True
        user_profile.save()

        unsubscribe_link = one_click_unsubscribe_link(user_profile, "login")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

        self.assertEqual(result.status_code, 200)

        user_profile.refresh_from_db()
        self.assertFalse(user_profile.enable_login_emails)

class RealmCreationTest(ZulipTestCase):
    @override_settings(OPEN_REALM_CREATION=True)
    def check_able_to_create_realm(self, email: str) -> None:
        password = "test"
        string_id = "zuliptest"
        realm = get_realm(string_id)
        # Make sure the realm does not exist
        self.assertIsNone(realm)

        # Create new realm with the email
        result = self.client_post('/new/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/new/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(email, password, realm_subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].startswith('http://zuliptest.testserver/accounts/login/subdomain/'))

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertIsNotNone(realm)
        self.assertEqual(realm.string_id, string_id)
        self.assertEqual(get_user(email, realm).realm, realm)

        # Check defaults
        self.assertEqual(realm.org_type, Realm.CORPORATE)
        self.assertEqual(realm.emails_restricted_to_domains, False)
        self.assertEqual(realm.invite_required, True)

        # Check welcome messages
        for stream_name, text, message_count in [
                ('announce', 'This is', 1),
                (Realm.INITIAL_PRIVATE_STREAM_NAME, 'This is', 1),
                ('general', 'Welcome to', 1),
                ('new members', 'stream is', 1),
                ('zulip', 'Here is', 3)]:
            stream = get_stream(stream_name, realm)
            recipient = get_stream_recipient(stream.id)
            messages = Message.objects.filter(recipient=recipient).order_by('pub_date')
            self.assertEqual(len(messages), message_count)
            self.assertIn(text, messages[0].content)

    def test_create_realm_non_existing_email(self) -> None:
        self.check_able_to_create_realm("user1@test.com")

    def test_create_realm_existing_email(self) -> None:
        self.check_able_to_create_realm("hamlet@zulip.com")

    def test_create_realm_as_system_bot(self) -> None:
        result = self.client_post('/new/', {'email': 'notification-bot@zulip.com'})
        self.assertEqual(result.status_code, 200)
        self.assert_in_response('notification-bot@zulip.com is an email address reserved', result)

    def test_create_realm_no_creation_key(self) -> None:
        """
        Trying to create a realm without a creation_key should fail when
        OPEN_REALM_CREATION is false.
        """
        email = "user1@test.com"

        with self.settings(OPEN_REALM_CREATION=False):
            # Create new realm with the email, but no creation key.
            result = self.client_post('/new/', {'email': email})
            self.assertEqual(result.status_code, 200)
            self.assert_in_response('New organization creation disabled', result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_subdomain(self) -> None:
        password = "test"
        string_id = "zuliptest"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        self.assertIsNone(get_realm(string_id))

        # Create new realm with the email
        result = self.client_post('/new/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/new/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(email, password,
                                               realm_subdomain = string_id,
                                               realm_name=realm_name,
                                               # Pass HTTP_HOST for the target subdomain
                                               HTTP_HOST=string_id + ".testserver")
        self.assertEqual(result.status_code, 302)

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertIsNotNone(realm)
        self.assertEqual(realm.string_id, string_id)
        self.assertEqual(get_user(email, realm).realm, realm)

        self.assertEqual(realm.name, realm_name)
        self.assertEqual(realm.subdomain, string_id)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_mailinator_signup(self) -> None:
        result = self.client_post('/new/', {'email': "hi@mailinator.com"})
        self.assert_in_response('Please use your real email address.', result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        result = self.client_post('/new/', {'email': email})
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        errors = {'id': "length 3 or greater",
                  '-id': "cannot start or end with a",
                  'string-ID': "lowercase letters",
                  'string_id': "lowercase letters",
                  'stream': "unavailable",
                  'streams': "unavailable",
                  'about': "unavailable",
                  'abouts': "unavailable",
                  'zephyr': "unavailable"}
        for string_id, error_msg in errors.items():
            result = self.submit_reg_form_for_user(email, password,
                                                   realm_subdomain = string_id,
                                                   realm_name = realm_name)
            self.assert_in_response(error_msg, result)

        # test valid subdomain
        result = self.submit_reg_form_for_user(email, password,
                                               realm_subdomain = 'a-0',
                                               realm_name = realm_name)
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result.url.startswith('http://a-0.testserver/accounts/login/subdomain/'))

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions_root_domain(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        result = self.client_post('/new/', {'email': email})
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        # test root domain will fail with ROOT_DOMAIN_LANDING_PAGE
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.submit_reg_form_for_user(email, password,
                                                   realm_subdomain = '',
                                                   realm_name = realm_name)
            self.assert_in_response('unavailable', result)

        # test valid use of root domain
        result = self.submit_reg_form_for_user(email, password,
                                               realm_subdomain = '',
                                               realm_name = realm_name)
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result.url.startswith('http://testserver/accounts/login/subdomain/'))

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions_root_domain_option(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        result = self.client_post('/new/', {'email': email})
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        # test root domain will fail with ROOT_DOMAIN_LANDING_PAGE
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.submit_reg_form_for_user(email, password,
                                                   realm_subdomain = 'abcdef',
                                                   realm_in_root_domain = 'true',
                                                   realm_name = realm_name)
            self.assert_in_response('unavailable', result)

        # test valid use of root domain
        result = self.submit_reg_form_for_user(email, password,
                                               realm_subdomain = 'abcdef',
                                               realm_in_root_domain = 'true',
                                               realm_name = realm_name)
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result.url.startswith('http://testserver/accounts/login/subdomain/'))

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
        self.assert_in_success_response(["Subdomain unavailable. Please choose a different one."], result)

        result = self.client_get("/json/realm/subdomain/zu_lip")
        self.assert_in_success_response(["Subdomain can only have lowercase letters, numbers, and \'-\'s."], result)

        result = self.client_get("/json/realm/subdomain/hufflepuff")
        self.assert_in_success_response(["available"], result)
        self.assert_not_in_success_response(["unavailable"], result)

    def test_subdomain_check_management_command(self) -> None:
        # Short names should work
        check_subdomain_available('aa', from_management_command=True)
        # So should reserved ones
        check_subdomain_available('zulip', from_management_command=True)
        # malformed names should still not
        with self.assertRaises(ValidationError):
            check_subdomain_available('-ba_d-', from_management_command=True)

class UserSignUpTest(InviteUserBase):

    def _assert_redirected_to(self, result: HttpResponse, url: str) -> None:
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result['LOCATION'], url)

    def test_bad_email_configuration_for_accounts_home(self) -> None:
        """
        Make sure we redirect for SMTP errors.
        """
        email = self.nonreg_email('newguy')

        smtp_mock = patch(
            'zerver.views.registration.send_confirm_registration_email',
            side_effect=smtplib.SMTPException('uh oh')
        )

        error_mock = patch('logging.error')

        with smtp_mock, error_mock as err:
            result = self.client_post('/accounts/home/', {'email': email})

        self._assert_redirected_to(result, '/config-error/smtp')

        self.assertEqual(
            err.call_args_list[0][0][0],
            'Error in accounts_home: uh oh'
        )

    def test_bad_email_configuration_for_create_realm(self) -> None:
        """
        Make sure we redirect for SMTP errors.
        """
        email = self.nonreg_email('newguy')

        smtp_mock = patch(
            'zerver.views.registration.send_confirm_registration_email',
            side_effect=smtplib.SMTPException('uh oh')
        )

        error_mock = patch('logging.error')

        with smtp_mock, error_mock as err:
            result = self.client_post('/new/', {'email': email})

        self._assert_redirected_to(result, '/config-error/smtp')

        self.assertEqual(
            err.call_args_list[0][0][0],
            'Error in create_realm: uh oh'
        )

    def test_user_default_language_and_timezone(self) -> None:
        """
        Check if the default language of new user is the default language
        of the realm.
        """
        email = self.nonreg_email('newguy')
        password = "newpassword"
        timezone = "US/Mountain"
        realm = get_realm('zulip')
        do_set_realm_property(realm, 'default_language', u"de")

        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        # Pick a password and agree to the ToS.
        result = self.submit_reg_form_for_user(email, password, timezone=timezone)
        self.assertEqual(result.status_code, 302)

        user_profile = self.nonreg_user('newguy')
        self.assertEqual(user_profile.default_language, realm.default_language)
        self.assertEqual(user_profile.timezone, timezone)
        from django.core.mail import outbox
        outbox.pop()

    def test_default_twenty_four_hour_time(self) -> None:
        """
        Check if the default twenty_four_hour_time setting of new user
        is the default twenty_four_hour_time of the realm.
        """
        email = self.nonreg_email('newguy')
        password = "newpassword"
        realm = get_realm('zulip')
        do_set_realm_property(realm, 'default_twenty_four_hour_time', True)

        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(email, password)
        self.assertEqual(result.status_code, 302)

        user_profile = self.nonreg_user('newguy')
        self.assertEqual(user_profile.twenty_four_hour_time, realm.default_twenty_four_hour_time)

    def test_signup_already_active(self) -> None:
        """
        Check if signing up with an active email redirects to a login page.
        """
        email = self.example_email("hamlet")
        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertIn('login', result['Location'])
        result = self.client_get(result.url)
        self.assert_in_response("You've already registered", result)

    def test_signup_system_bot(self) -> None:
        email = "notification-bot@zulip.com"
        result = self.client_post('/accounts/home/', {'email': email}, subdomain="lear")
        self.assertEqual(result.status_code, 302)
        self.assertIn('login', result['Location'])
        result = self.client_get(result.url)

        # This is not really the right error message, but at least it's an error.
        self.assert_in_response("You've already registered", result)

    def test_signup_existing_email(self) -> None:
        """
        Check if signing up with an email used in another realm succeeds.
        """
        email = self.example_email('hamlet')
        password = "newpassword"
        realm = get_realm('lear')

        result = self.client_post('/accounts/home/', {'email': email}, subdomain="lear")
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"], subdomain="lear")

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url, subdomain="lear")
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(email, password, subdomain="lear")
        self.assertEqual(result.status_code, 302)

        get_user(email, realm)
        self.assertEqual(UserProfile.objects.filter(email=email).count(), 2)

    def test_signup_invalid_name(self) -> None:
        """
        Check if an invalid name during signup is handled properly.
        """
        email = "newguy@zulip.com"
        password = "newpassword"

        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        # Pick a password and agree to the ToS.
        result = self.submit_reg_form_for_user(email, password, full_name="<invalid>")
        self.assert_in_success_response(["Invalid characters in name!"], result)

        # Verify that the user is asked for name and password
        self.assert_in_success_response(['id_password', 'id_full_name'], result)

    def test_signup_without_password(self) -> None:
        """
        Check if signing up without a password works properly when
        password_auth_enabled is False.
        """

        email = self.nonreg_email('newuser')

        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        with patch('zerver.views.registration.password_auth_enabled', return_value=False):
            result = self.client_post(
                '/accounts/register/',
                {'full_name': 'New User',
                 'key': find_key_by_email(email),
                 'terms': True})

        # User should now be logged in.
        self.assertEqual(result.status_code, 302)
        user_profile = self.nonreg_user('newuser')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_signup_without_full_name(self) -> None:
        """
        Check if signing up without a full name redirects to a registration
        form.
        """
        email = "newguy@zulip.com"
        password = "newpassword"

        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.client_post(
            '/accounts/register/',
            {'password': password,
             'key': find_key_by_email(email),
             'terms': True,
             'from_confirmation': '1'})
        self.assert_in_success_response(["We just need you to do one last thing."], result)

        # Verify that the user is asked for name and password
        self.assert_in_success_response(['id_password', 'id_full_name'], result)

    def test_signup_with_full_name(self) -> None:
        """
        Check if signing up without a full name redirects to a registration
        form.
        """
        email = "newguy@zulip.com"
        password = "newpassword"

        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.client_post(
            '/accounts/register/',
            {'password': password,
             'key': find_key_by_email(email),
             'terms': True,
             'full_name': "New Guy",
             'from_confirmation': '1'})
        self.assert_in_success_response(["We just need you to do one last thing."], result)

    def test_signup_with_default_stream_group(self) -> None:
        # Check if user is subscribed to the streams of default
        # stream group as well as default streams.
        email = self.nonreg_email('newguy')
        password = "newpassword"
        realm = get_realm("zulip")

        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"])

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

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

        result = self.submit_reg_form_for_user(email, password, default_stream_groups=["group 1"])
        self.check_user_subscribed_only_to_streams("newguy", default_streams + group1_streams)

    def test_signup_with_multiple_default_stream_groups(self) -> None:
        # Check if user is subscribed to the streams of default
        # stream groups as well as default streams.
        email = self.nonreg_email('newguy')
        password = "newpassword"
        realm = get_realm("zulip")

        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"])

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

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

        result = self.submit_reg_form_for_user(email, password,
                                               default_stream_groups=["group 1", "group 2"])
        self.check_user_subscribed_only_to_streams(
            "newguy", list(set(default_streams + group1_streams + group2_streams)))

    def test_signup_without_user_settings_from_another_realm(self) -> None:
        email = self.example_email('hamlet')
        password = "newpassword"
        subdomain = "lear"
        realm = get_realm("lear")

        # Make an account in the Zulip realm, but we're not copying from there.
        hamlet_in_zulip = get_user(self.example_email("hamlet"), get_realm("zulip"))
        hamlet_in_zulip.left_side_userlist = True
        hamlet_in_zulip.default_language = "de"
        hamlet_in_zulip.emojiset = "twitter"
        hamlet_in_zulip.high_contrast_mode = True
        hamlet_in_zulip.enter_sends = True
        hamlet_in_zulip.tutorial_status = UserProfile.TUTORIAL_FINISHED
        hamlet_in_zulip.save()

        result = self.client_post('/accounts/home/', {'email': email}, subdomain=subdomain)
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"], subdomain=subdomain)

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url, subdomain=subdomain)
        self.assertEqual(result.status_code, 200)
        result = self.submit_reg_form_for_user(email, password, source_realm="on",
                                               HTTP_HOST=subdomain + ".testserver")

        hamlet = get_user(self.example_email("hamlet"), realm)
        self.assertEqual(hamlet.left_side_userlist, False)
        self.assertEqual(hamlet.default_language, "en")
        self.assertEqual(hamlet.emojiset, "google-blob")
        self.assertEqual(hamlet.high_contrast_mode, False)
        self.assertEqual(hamlet.enable_stream_sounds, False)
        self.assertEqual(hamlet.enter_sends, False)
        self.assertEqual(hamlet.tutorial_status, UserProfile.TUTORIAL_WAITING)

    def test_signup_with_user_settings_from_another_realm(self) -> None:
        email = self.example_email('hamlet')
        password = "newpassword"
        subdomain = "lear"
        lear_realm = get_realm("lear")
        zulip_realm = get_realm("zulip")

        self.login(self.example_email("hamlet"))
        with get_test_image_file('img.png') as image_file:
            self.client_post("/json/users/me/avatar", {'file': image_file})
        hamlet_in_zulip = get_user(self.example_email("hamlet"), zulip_realm)
        hamlet_in_zulip.left_side_userlist = True
        hamlet_in_zulip.default_language = "de"
        hamlet_in_zulip.emojiset = "twitter"
        hamlet_in_zulip.high_contrast_mode = True
        hamlet_in_zulip.enter_sends = True
        hamlet_in_zulip.tutorial_status = UserProfile.TUTORIAL_FINISHED
        hamlet_in_zulip.save()

        result = self.client_post('/accounts/home/', {'email': email}, subdomain=subdomain)
        self.assertEqual(result.status_code, 302)
        result = self.client_get(result["Location"], subdomain=subdomain)

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url, subdomain=subdomain)
        self.assertEqual(result.status_code, 200)

        result = self.client_post(
            '/accounts/register/',
            {'password': password,
             'key': find_key_by_email(email),
             'from_confirmation': '1'},
            subdomain=subdomain)
        self.assert_in_success_response(["Import settings from existing Zulip account",
                                         "selected >\n                            Zulip Dev",
                                         "We just need you to do one last thing."], result)

        result = self.submit_reg_form_for_user(email, password, source_realm="zulip",
                                               HTTP_HOST=subdomain + ".testserver")

        hamlet_in_lear = get_user(self.example_email("hamlet"), lear_realm)
        self.assertEqual(hamlet_in_lear.left_side_userlist, True)
        self.assertEqual(hamlet_in_lear.default_language, "de")
        self.assertEqual(hamlet_in_lear.emojiset, "twitter")
        self.assertEqual(hamlet_in_lear.high_contrast_mode, True)
        self.assertEqual(hamlet_in_lear.enter_sends, True)
        self.assertEqual(hamlet_in_lear.enable_stream_sounds, False)
        self.assertEqual(hamlet_in_lear.tutorial_status, UserProfile.TUTORIAL_FINISHED)
        zulip_path_id = avatar_disk_path(hamlet_in_zulip)
        hamlet_path_id = avatar_disk_path(hamlet_in_zulip)
        self.assertEqual(open(zulip_path_id, "rb").read(), open(hamlet_path_id, "rb").read())

    def test_signup_invalid_subdomain(self) -> None:
        """
        Check if attempting to authenticate to the wrong subdomain logs an
        error and redirects.
        """
        email = "newuser@zulip.com"
        password = "newpassword"

        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        def invalid_subdomain(**kwargs: Any) -> Any:
            return_data = kwargs.get('return_data', {})
            return_data['invalid_subdomain'] = True

        with patch('zerver.views.registration.authenticate', side_effect=invalid_subdomain):
            with patch('logging.error') as mock_error:
                result = self.client_post(
                    '/accounts/register/',
                    {'password': password,
                     'full_name': 'New User',
                     'key': find_key_by_email(email),
                     'terms': True})
        mock_error.assert_called_once()
        self.assertEqual(result.status_code, 302)

    def test_replace_subdomain_in_confirmation_link(self) -> None:
        """
        Check that manually changing the subdomain in a registration
        confirmation link doesn't allow you to register to a different realm.
        """
        email = "newuser@zulip.com"
        self.client_post('/accounts/home/', {'email': email})
        result = self.client_post(
            '/accounts/register/',
            {'password': "password",
             'key': find_key_by_email(email),
             'terms': True,
             'full_name': "New User",
             'from_confirmation': '1'},  subdomain="zephyr")
        self.assert_in_success_response(["We couldn't find your confirmation link"], result)

    def test_failed_signup_due_to_restricted_domain(self) -> None:
        realm = get_realm('zulip')
        realm.invite_required = False
        realm.save()

        request = HostRequestMock(host = realm.host)
        request.session = {}  # type: ignore
        email = 'user@acme.com'
        form = HomepageForm({'email': email}, realm=realm)
        self.assertIn("Your email address, {}, is not in one of the domains".format(email),
                      form.errors['email'][0])

    def test_failed_signup_due_to_disposable_email(self) -> None:
        realm = get_realm('zulip')
        realm.emails_restricted_to_domains = False
        realm.disallow_disposable_email_addresses = True
        realm.save()

        request = HostRequestMock(host = realm.host)
        request.session = {}  # type: ignore
        email = 'abc@mailnator.com'
        form = HomepageForm({'email': email}, realm=realm)
        self.assertIn("Please use your real email address", form.errors['email'][0])

    def test_failed_signup_due_to_email_containing_plus(self) -> None:
        realm = get_realm('zulip')
        realm.emails_restricted_to_domains = True
        realm.save()

        request = HostRequestMock(host = realm.host)
        request.session = {}  # type: ignore
        email = 'iago+label@zulip.com'
        form = HomepageForm({'email': email}, realm=realm)
        self.assertIn("Email addresses containing + are not allowed in this organization.", form.errors['email'][0])

    def test_failed_signup_due_to_invite_required(self) -> None:
        realm = get_realm('zulip')
        realm.invite_required = True
        realm.save()
        request = HostRequestMock(host = realm.host)
        request.session = {}  # type: ignore
        email = 'user@zulip.com'
        form = HomepageForm({'email': email}, realm=realm)
        self.assertIn("Please request an invite for {} from".format(email),
                      form.errors['email'][0])

    def test_failed_signup_due_to_nonexistent_realm(self) -> None:
        request = HostRequestMock(host = 'acme.' + settings.EXTERNAL_HOST)
        request.session = {}  # type: ignore
        email = 'user@acme.com'
        form = HomepageForm({'email': email}, realm=None)
        self.assertIn("organization you are trying to join using {} does "
                      "not exist".format(email), form.errors['email'][0])

    def test_access_signup_page_in_root_domain_without_realm(self) -> None:
        result = self.client_get('/register', subdomain="", follow=True)
        self.assert_in_success_response(["Find your Zulip accounts"], result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_ldap_registration_from_confirmation(self) -> None:
        password = "testing"
        email = "newuser@zulip.com"
        subdomain = "zulip"
        ldap_user_attr_map = {'full_name': 'fn'}
        mock_directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing', ],
                'fn': ['New LDAP fullname']
            }
        }
        init_fakeldap(mock_directory)

        with patch('zerver.views.registration.get_subdomain', return_value=subdomain):
            result = self.client_post('/register/', {'email': email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)
        # Visit the confirmation link.
        from django.core.mail import outbox
        for message in reversed(outbox):
            if email in message.to:
                confirmation_link_pattern = re.compile(settings.EXTERNAL_HOST + r"(\S+)>")
                confirmation_url = confirmation_link_pattern.search(
                    message.body).groups()[0]
                break
        else:
            raise AssertionError("Couldn't find a confirmation email.")

        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            result = self.client_get(confirmation_url)
            self.assertEqual(result.status_code, 200)

            # Full name should be set from LDAP
            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name="Ignore",
                                                   from_confirmation="1",
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")

            self.assert_in_success_response(["We just need you to do one last thing.",
                                             "New LDAP fullname",
                                             "newuser@zulip.com"],
                                            result)

            # Verify that the user is asked for name
            self.assert_in_success_response(['id_full_name'], result)
            # Verify that user is asked for its LDAP/Active Directory password.
            self.assert_in_success_response(['Enter your LDAP/Active Directory password.',
                                             'ldap-password'], result)
            self.assert_not_in_success_response(['id_password'], result)

            # Test the TypeError exception handler
            mock_directory = {
                'uid=newuser,ou=users,dc=zulip,dc=com': {
                    'userPassword': ['testing', ],
                    'fn': None  # This will raise TypeError
                }
            }
            init_fakeldap(mock_directory)
            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   from_confirmation='1',
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            self.assert_in_success_response(["We just need you to do one last thing.",
                                             "newuser@zulip.com"],
                                            result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_ldap_registration_end_to_end(self) -> None:
        password = "testing"
        email = "newuser@zulip.com"
        subdomain = "zulip"

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}
        full_name = 'New LDAP fullname'
        mock_directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing', ],
                'fn': [full_name],
                'sn': ['shortname'],
            }
        }
        init_fakeldap(mock_directory)

        with patch('zerver.views.registration.get_subdomain', return_value=subdomain):
            result = self.client_post('/register/', {'email': email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):

            # Click confirmation link
            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name="Ignore",
                                                   from_confirmation="1",
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")

            # Full name should be set from LDAP
            self.assert_in_success_response(["We just need you to do one last thing.",
                                             full_name,
                                             "newuser@zulip.com"],
                                            result)

            # Submit the final form with the wrong password.
            result = self.submit_reg_form_for_user(email,
                                                   'wrongpassword',
                                                   full_name=full_name,
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            # Didn't create an account
            with self.assertRaises(UserProfile.DoesNotExist):
                user_profile = UserProfile.objects.get(email=email)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/accounts/login/?email=newuser%40zulip.com")

            # Submit the final form with the correct password.
            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name=full_name,
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            user_profile = UserProfile.objects.get(email=email)
            # Name comes from form which was set by LDAP.
            self.assertEqual(user_profile.full_name, full_name)
            # Short name comes from LDAP.
            self.assertEqual(user_profile.short_name, "shortname")

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_ldap_split_full_name_mapping(self) -> None:
        ldap_user_attr_map = {'first_name': 'fn', 'last_name': 'ln'}
        mock_directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing', ],
                'fn': ['First'],
                'ln': ['Last'],
            }
        }
        init_fakeldap(mock_directory)

        subdomain = 'zulip'
        email = 'newuser@zulip.com'
        password = 'testing'
        with patch('zerver.views.registration.get_subdomain', return_value=subdomain):
            result = self.client_post('/register/', {'email': email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):

            # Click confirmation link
            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name="Ignore",
                                                   from_confirmation="1",
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")

            # Test split name mapping.
            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name="Ignore",
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            user_profile = UserProfile.objects.get(email=email)
            # Name comes from form which was set by LDAP.
            self.assertEqual(user_profile.full_name, "First Last")
            # Short name comes from LDAP.
            self.assertEqual(user_profile.short_name, "First")

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_ldap_auto_registration_on_login(self) -> None:
        """The most common way for LDAP authentication to be used is with a
        server that doesn't have a terms-of-service required, in which
        case we offer a complete single-sign-on experience (where the
        user just enters their LDAP username and password, and their
        account is created if it doesn't already exist).

        This test verifies that flow.
        """
        password = "testing"
        email = "newuser@zulip.com"
        subdomain = "zulip"

        ldap_user_attr_map = {
            'full_name': 'fn',
            'short_name': 'sn',
            'custom_profile_field__phone_number': 'phoneNumber',
            'custom_profile_field__birthday': 'birthDate',
        }
        full_name = 'New LDAP fullname'
        mock_directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing', ],
                'fn': [full_name],
                'sn': ['shortname'],
                'phoneNumber': ['a-new-number', ],
                'birthDate': ['1990-12-19', ],
            }
        }
        init_fakeldap(mock_directory)

        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):

            self.login_with_return(email, password,
                                   HTTP_HOST=subdomain + ".testserver")

            user_profile = UserProfile.objects.get(email=email)
            # Name comes from form which was set by LDAP.
            self.assertEqual(user_profile.full_name, full_name)
            self.assertEqual(user_profile.short_name, 'shortname')

            # Test custom profile fields are properly synced.
            birthday_field = CustomProfileField.objects.get(realm=user_profile.realm, name='Birthday')
            phone_number_field = CustomProfileField.objects.get(realm=user_profile.realm, name='Phone number')
            birthday_field_value = CustomProfileFieldValue.objects.get(user_profile=user_profile,
                                                                       field=birthday_field)
            phone_number_field_value = CustomProfileFieldValue.objects.get(user_profile=user_profile,
                                                                           field=phone_number_field)
            self.assertEqual(birthday_field_value.value, '1990-12-19')
            self.assertEqual(phone_number_field_value.value, 'a-new-number')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_registration_multiple_realms(self) -> None:
        password = "testing"
        email = "newuser@zulip.com"

        ldap_user_attr_map = {
            'full_name': 'fn',
            'short_name': 'sn',
        }
        full_name = 'New LDAP fullname'
        mock_directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing', ],
                'fn': [full_name],
                'sn': ['shortname'],
            }
        }
        init_fakeldap(mock_directory)
        do_create_realm('test', 'test', False)

        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):

            subdomain = "zulip"
            self.login_with_return(email, password,
                                   HTTP_HOST=subdomain + ".testserver")

            user_profile = UserProfile.objects.get(email=email, realm=get_realm('zulip'))
            self.assertEqual(user_profile.email, email)
            self.logout()

            # Test registration in another realm works.
            subdomain = "test"
            self.login_with_return(email, password,
                                   HTTP_HOST=subdomain + ".testserver")

            user_profile = UserProfile.objects.get(email=email, realm=get_realm('test'))
            self.assertEqual(user_profile.email, email)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_ldap_registration_when_names_changes_are_disabled(self) -> None:
        password = "testing"
        email = "newuser@zulip.com"
        subdomain = "zulip"

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}
        mock_directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing', ],
                'fn': ['New LDAP fullname'],
                'sn': ['New LDAP shortname'],
            }
        }
        init_fakeldap(mock_directory)

        with patch('zerver.views.registration.get_subdomain', return_value=subdomain):
            result = self.client_post('/register/', {'email': email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):

            # Click confirmation link. This will 'authenticated_full_name'
            # session variable which will be used to set the fullname of
            # the user.
            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name="Ignore",
                                                   from_confirmation="1",
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")

            with patch('zerver.views.registration.name_changes_disabled', return_value=True):
                result = self.submit_reg_form_for_user(email,
                                                       password,
                                                       # Pass HTTP_HOST for the target subdomain
                                                       HTTP_HOST=subdomain + ".testserver")
            user_profile = UserProfile.objects.get(email=email)
            # Name comes from LDAP session.
            self.assertEqual(user_profile.full_name, 'New LDAP fullname')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.EmailAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_signup_with_ldap_and_email_enabled_using_email(self) -> None:
        password = "mynewpassword"
        email = "newuser@zulip.com"
        subdomain = "zulip"

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}
        mock_directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing', ],
                'fn': ['New LDAP fullname'],
                'sn': ['New LDAP shortname'],
            }
        }
        init_fakeldap(mock_directory)

        with patch('zerver.views.registration.get_subdomain', return_value=subdomain):
            result = self.client_post('/register/', {'email': email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        # If the user's email is inside the LDAP domain and we just
        # have a wrong password, then we refuse to create an account
        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                # Important: This doesn't match the new user
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):

            result = self.submit_reg_form_for_user(
                email,
                password,
                from_confirmation="1",
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver")
            self.assertEqual(result.status_code, 200)

            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name="Non-LDAP Full Name",
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            self.assertEqual(result.status_code, 302)
            # We get redirected back to the login page because password was wrong
            self.assertEqual(result.url, "/accounts/login/?email=newuser%40zulip.com")
            self.assertFalse(UserProfile.objects.filter(email=email).exists())

        # If the user's email is outside the LDAP domain, though, we
        # successfully create an account with a password in the Zulip
        # database.
        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                # Important: This doesn't match the new user
                LDAP_APPEND_DOMAIN='example.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):

            with patch('zerver.views.registration.logging.warning') as mock_warning:
                result = self.submit_reg_form_for_user(
                    email,
                    password,
                    from_confirmation="1",
                    # Pass HTTP_HOST for the target subdomain
                    HTTP_HOST=subdomain + ".testserver")
                self.assertEqual(result.status_code, 200)
                mock_warning.assert_called_once_with("New account email newuser@zulip.com could not be found in LDAP")

            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name="Non-LDAP Full Name",
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "http://zulip.testserver/")
            user_profile = UserProfile.objects.get(email=email)
            # Name comes from the POST request, not LDAP
            self.assertEqual(user_profile.full_name, 'Non-LDAP Full Name')

    def ldap_invite_and_signup_as(self, invite_as: int, streams: List[str]=['Denmark']) -> None:
        ldap_user_attr_map = {'full_name': 'fn'}
        mock_directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing'],
                'fn': ['LDAP Name'],
            }
        }
        init_fakeldap(mock_directory)

        subdomain = 'zulip'
        email = self.nonreg_email('newuser')
        password = 'testing'

        # Invite user.
        self.login(self.example_email('iago'))
        response = self.invite(invitee_emails=self.nonreg_email('newuser'),
                               stream_names=streams,
                               invite_as=invite_as)
        self.assert_json_success(response)
        self.logout()

        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):

            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name="Ignore",
                                                   from_confirmation="1",
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            self.assertEqual(result.status_code, 200)

            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name="Ignore",
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            self.assertEqual(result.status_code, 302)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.EmailAuthBackend'))
    def test_ldap_invite_user_as_admin(self) -> None:
        self.ldap_invite_and_signup_as(PreregistrationUser.INVITE_AS['REALM_ADMIN'])
        user_profile = UserProfile.objects.get(email=self.nonreg_email('newuser'))
        self.assertTrue(user_profile.is_realm_admin)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.EmailAuthBackend'))
    def test_ldap_invite_user_as_guest(self) -> None:
        self.ldap_invite_and_signup_as(PreregistrationUser.INVITE_AS['GUEST_USER'])
        user_profile = UserProfile.objects.get(email=self.nonreg_email('newuser'))
        self.assertTrue(user_profile.is_guest)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.EmailAuthBackend'))
    def test_ldap_invite_streams(self) -> None:
        stream_name = 'Rome'
        realm = get_realm('zulip')
        stream = get_stream(stream_name, realm)
        default_streams = get_default_streams_for_realm(realm)
        default_streams_name = [stream.name for stream in default_streams]
        self.assertNotIn(stream_name, default_streams_name)

        # Invite user.
        self.ldap_invite_and_signup_as(PreregistrationUser.INVITE_AS['REALM_ADMIN'], streams=[stream_name])

        user_profile = UserProfile.objects.get(email=self.nonreg_email('newuser'))
        self.assertTrue(user_profile.is_realm_admin)
        sub = get_stream_subscriptions_for_user(user_profile).filter(recipient__type_id=stream.id)
        self.assertEqual(len(sub), 1)

    def test_registration_when_name_changes_are_disabled(self) -> None:
        """
        Test `name_changes_disabled` when we are not running under LDAP.
        """
        password = "testing"
        email = "newuser@zulip.com"
        subdomain = "zulip"

        with patch('zerver.views.registration.get_subdomain', return_value=subdomain):
            result = self.client_post('/register/', {'email': email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)

        with patch('zerver.views.registration.name_changes_disabled', return_value=True):
            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   full_name="New Name",
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            user_profile = UserProfile.objects.get(email=email)
            # 'New Name' comes from POST data; not from LDAP session.
            self.assertEqual(user_profile.full_name, 'New Name')

    def test_realm_creation_through_ldap(self) -> None:
        password = "testing"
        email = "newuser@zulip.com"
        subdomain = "zulip"
        realm_name = "Zulip"
        ldap_user_attr_map = {'full_name': 'fn'}
        mock_directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing', ],
                'fn': ['New User Name']
            }
        }
        init_fakeldap(mock_directory)

        with patch('zerver.views.registration.get_subdomain', return_value=subdomain):
            result = self.client_post('/register/', {'email': email})

        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started.", result)
        # Visit the confirmation link.
        from django.core.mail import outbox
        for message in reversed(outbox):
            if email in message.to:
                confirmation_link_pattern = re.compile(settings.EXTERNAL_HOST + r"(\S+)>")
                confirmation_url = confirmation_link_pattern.search(
                    message.body).groups()[0]
                break
        else:
            raise AssertionError("Couldn't find a confirmation email.")

        with self.settings(
            POPULATE_PROFILE_VIA_LDAP=True,
            LDAP_APPEND_DOMAIN='zulip.com',
            AUTH_LDAP_BIND_PASSWORD='',
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
            AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',),
            AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com',
            TERMS_OF_SERVICE=False,
        ):
            result = self.client_get(confirmation_url)
            self.assertEqual(result.status_code, 200)

            key = find_key_by_email(email),
            confirmation = Confirmation.objects.get(confirmation_key=key[0])
            prereg_user = confirmation.content_object
            prereg_user.realm_creation = True
            prereg_user.save()

            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   realm_name=realm_name,
                                                   realm_subdomain=subdomain,
                                                   from_confirmation='1',
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            self.assert_in_success_response(["We just need you to do one last thing.",
                                             "newuser@zulip.com"],
                                            result)

    @patch('DNS.dnslookup', return_value=[['sipbtest:*:20922:101:Fred Sipb,,,:/mit/sipbtest:/bin/athena/tcsh']])
    def test_registration_of_mirror_dummy_user(self, ignored: Any) -> None:
        password = "test"
        subdomain = "zephyr"
        user_profile = self.mit_user("sipbtest")
        email = user_profile.email
        user_profile.is_mirror_dummy = True
        user_profile.is_active = False
        user_profile.save()

        result = self.client_post('/register/', {'email': email}, subdomain="zephyr")

        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/send_confirm/%s" % (email,)))
        result = self.client_get(result["Location"], subdomain="zephyr")
        self.assert_in_response("Check your email so we can get started.", result)
        # Visit the confirmation link.
        from django.core.mail import outbox
        for message in reversed(outbox):
            if email in message.to:
                confirmation_link_pattern = re.compile(settings.EXTERNAL_HOST + r"(\S+)>")
                confirmation_url = confirmation_link_pattern.search(
                    message.body).groups()[0]
                break
        else:
            raise AssertionError("Couldn't find a confirmation email.")

        result = self.client_get(confirmation_url, subdomain="zephyr")
        self.assertEqual(result.status_code, 200)

        # If the mirror dummy user is already active, attempting to
        # submit the registration form should raise an AssertionError
        # (this is an invalid state, so it's a bug we got here):
        user_profile.is_active = True
        user_profile.save()
        with self.assertRaisesRegex(AssertionError, "Mirror dummy user is already active!"):
            result = self.submit_reg_form_for_user(
                email,
                password,
                from_confirmation='1',
                # Pass HTTP_HOST for the target subdomain
                HTTP_HOST=subdomain + ".testserver")

        user_profile.is_active = False
        user_profile.save()

        result = self.submit_reg_form_for_user(email,
                                               password,
                                               from_confirmation='1',
                                               # Pass HTTP_HOST for the target subdomain
                                               HTTP_HOST=subdomain + ".testserver")
        self.assertEqual(result.status_code, 200)
        result = self.submit_reg_form_for_user(email,
                                               password,
                                               # Pass HTTP_HOST for the target subdomain
                                               HTTP_HOST=subdomain + ".testserver")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_registration_of_active_mirror_dummy_user(self) -> None:
        """
        Trying to activate an already-active mirror dummy user should
        raise an AssertionError.
        """
        user_profile = self.mit_user("sipbtest")
        email = user_profile.email
        user_profile.is_mirror_dummy = True
        user_profile.is_active = True
        user_profile.save()

        with self.assertRaisesRegex(AssertionError, "Mirror dummy user is already active!"):
            self.client_post('/register/', {'email': email}, subdomain="zephyr")

class DeactivateUserTest(ZulipTestCase):

    def test_deactivate_user(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)
        user = self.example_user('hamlet')
        self.assertTrue(user.is_active)
        result = self.client_delete('/json/users/me')
        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertFalse(user.is_active)
        self.login(email, fails=True)

    def test_do_not_deactivate_final_admin(self) -> None:
        email = self.example_email("iago")
        self.login(email)
        user = self.example_user('iago')
        self.assertTrue(user.is_active)
        result = self.client_delete('/json/users/me')
        self.assert_json_error(result, "Cannot deactivate the only organization administrator.")
        user = self.example_user('iago')
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_realm_admin)
        email = self.example_email("hamlet")
        user_2 = self.example_user('hamlet')
        do_change_is_admin(user_2, True)
        self.assertTrue(user_2.is_realm_admin)
        result = self.client_delete('/json/users/me')
        self.assert_json_success(result)
        do_change_is_admin(user, True)

    def test_do_not_deactivate_final_user(self) -> None:
        realm = get_realm('zulip')
        UserProfile.objects.filter(realm=realm, is_realm_admin=False).update(is_active=False)
        email = self.example_email("iago")
        self.login(email)
        result = self.client_delete('/json/users/me')
        self.assert_json_error(result, "Cannot deactivate the only user.")

class TestLoginPage(ZulipTestCase):
    def test_login_page_wrong_subdomain_error(self) -> None:
        result = self.client_get("/login/?subdomain=1")
        self.assertIn(WRONG_SUBDOMAIN_ERROR, result.content.decode('utf8'))

    @patch('django.http.HttpRequest.get_host')
    def test_login_page_redirects_for_root_alias(self, mock_get_host: MagicMock) -> None:
        mock_get_host.return_value = 'www.testserver'
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/accounts/go/')

            result = self.client_get("/en/login/?next=/upgrade/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/accounts/go/?next=%2Fupgrade%2F')

    @patch('django.http.HttpRequest.get_host')
    def test_login_page_redirects_for_root_domain(self, mock_get_host: MagicMock) -> None:
        mock_get_host.return_value = 'testserver'
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/accounts/go/')

            result = self.client_get("/en/login/?next=/upgrade/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/accounts/go/?next=%2Fupgrade%2F')

        mock_get_host.return_value = 'www.testserver.com'
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True,
                           EXTERNAL_HOST='www.testserver.com',
                           ROOT_SUBDOMAIN_ALIASES=['test']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/accounts/go/')

            result = self.client_get("/en/login/?next=/upgrade/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/accounts/go/?next=%2Fupgrade%2F')

    @patch('django.http.HttpRequest.get_host')
    def test_login_page_works_without_subdomains(self, mock_get_host: MagicMock) -> None:
        mock_get_host.return_value = 'www.testserver'
        with self.settings(ROOT_SUBDOMAIN_ALIASES=['www']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 200)

        mock_get_host.return_value = 'testserver'
        with self.settings(ROOT_SUBDOMAIN_ALIASES=['www']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 200)

class TestFindMyTeam(ZulipTestCase):
    def test_template(self) -> None:
        result = self.client_get('/accounts/find/')
        self.assertIn("Find your Zulip accounts", result.content.decode('utf8'))

    def test_result(self) -> None:
        result = self.client_post('/accounts/find/',
                                  dict(emails="iago@zulip.com,cordelia@zulip.com"))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/accounts/find/?emails=iago%40zulip.com%2Ccordelia%40zulip.com")
        result = self.client_get(result.url)
        content = result.content.decode('utf8')
        self.assertIn("Emails sent! You will only receive emails", content)
        self.assertIn(self.example_email("iago"), content)
        self.assertIn(self.example_email("cordelia"), content)
        from django.core.mail import outbox
        # 3 = 1 + 2 -- Cordelia gets an email each for the "zulip" and "lear" realms.
        self.assertEqual(len(outbox), 3)

    def test_find_team_ignore_invalid_email(self) -> None:
        result = self.client_post('/accounts/find/',
                                  dict(emails="iago@zulip.com,invalid_email@zulip.com"))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/accounts/find/?emails=iago%40zulip.com%2Cinvalid_email%40zulip.com")
        result = self.client_get(result.url)
        content = result.content.decode('utf8')
        self.assertIn("Emails sent! You will only receive emails", content)
        self.assertIn(self.example_email("iago"), content)
        self.assertIn("invalid_email@", content)
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 1)

    def test_find_team_reject_invalid_email(self) -> None:
        result = self.client_post('/accounts/find/',
                                  dict(emails="invalid_string"))
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Enter a valid email", result.content)
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

        # Just for coverage on perhaps-unnecessary validation code.
        result = self.client_get('/accounts/find/?emails=invalid')
        self.assertEqual(result.status_code, 200)

    def test_find_team_zero_emails(self) -> None:
        data = {'emails': ''}
        result = self.client_post('/accounts/find/', data)
        self.assertIn('This field is required', result.content.decode('utf8'))
        self.assertEqual(result.status_code, 200)
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    def test_find_team_one_email(self) -> None:
        data = {'emails': self.example_email("hamlet")}
        result = self.client_post('/accounts/find/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/accounts/find/?emails=hamlet%40zulip.com')
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 1)

    def test_find_team_deactivated_user(self) -> None:
        do_deactivate_user(self.example_user("hamlet"))
        data = {'emails': self.example_email("hamlet")}
        result = self.client_post('/accounts/find/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/accounts/find/?emails=hamlet%40zulip.com')
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    def test_find_team_deactivated_realm(self) -> None:
        do_deactivate_realm(get_realm("zulip"))
        data = {'emails': self.example_email("hamlet")}
        result = self.client_post('/accounts/find/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/accounts/find/?emails=hamlet%40zulip.com')
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    def test_find_team_bot_email(self) -> None:
        data = {'emails': self.example_email("webhook_bot")}
        result = self.client_post('/accounts/find/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/accounts/find/?emails=webhook-bot%40zulip.com')
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    def test_find_team_more_than_ten_emails(self) -> None:
        data = {'emails': ','.join(['hamlet-{}@zulip.com'.format(i) for i in range(11)])}
        result = self.client_post('/accounts/find/', data)
        self.assertEqual(result.status_code, 200)
        self.assertIn("Please enter at most 10", result.content.decode('utf8'))
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

class ConfirmationKeyTest(ZulipTestCase):
    def test_confirmation_key(self) -> None:
        request = MagicMock()
        request.session = {
            'confirmation_key': {'confirmation_key': 'xyzzy'}
        }
        result = confirmation_key(request)
        self.assert_json_success(result)
        self.assert_in_response('xyzzy', result)

class MobileAuthOTPTest(ZulipTestCase):
    def test_xor_hex_strings(self) -> None:
        self.assertEqual(xor_hex_strings('1237c81ab', '18989fd12'), '0aaf57cb9')
        with self.assertRaises(AssertionError):
            xor_hex_strings('1', '31')

    def test_is_valid_otp(self) -> None:
        self.assertEqual(is_valid_otp('1234'), False)
        self.assertEqual(is_valid_otp('1234abcd' * 8), True)
        self.assertEqual(is_valid_otp('1234abcZ' * 8), False)

    def test_ascii_to_hex(self) -> None:
        self.assertEqual(ascii_to_hex('ZcdR1234'), '5a63645231323334')
        self.assertEqual(hex_to_ascii('5a63645231323334'), 'ZcdR1234')

    def test_otp_encrypt_api_key(self) -> None:
        api_key = '12ac' * 8
        otp = '7be38894' * 8
        result = otp_encrypt_api_key(api_key, otp)
        self.assertEqual(result, '4ad1e9f7' * 8)

        decryped = otp_decrypt_api_key(result, otp)
        self.assertEqual(decryped, api_key)

class FollowupEmailTest(ZulipTestCase):
    def test_followup_day2_email(self) -> None:
        user_profile = self.example_user('hamlet')
        # Test date_joined == Sunday
        user_profile.date_joined = datetime.datetime(2018, 1, 7, 1, 0, 0, 0, pytz.UTC)
        self.assertEqual(followup_day2_email_delay(user_profile), datetime.timedelta(days=2, hours=-1))
        # Test date_joined == Tuesday
        user_profile.date_joined = datetime.datetime(2018, 1, 2, 1, 0, 0, 0, pytz.UTC)
        self.assertEqual(followup_day2_email_delay(user_profile), datetime.timedelta(days=2, hours=-1))
        # Test date_joined == Thursday
        user_profile.date_joined = datetime.datetime(2018, 1, 4, 1, 0, 0, 0, pytz.UTC)
        self.assertEqual(followup_day2_email_delay(user_profile), datetime.timedelta(days=1, hours=-1))
        # Test date_joined == Friday
        user_profile.date_joined = datetime.datetime(2018, 1, 5, 1, 0, 0, 0, pytz.UTC)
        self.assertEqual(followup_day2_email_delay(user_profile), datetime.timedelta(days=3, hours=-1))

        # Time offset of America/Phoenix is -07:00
        user_profile.timezone = 'America/Phoenix'
        # Test date_joined == Friday in UTC, but Thursday in the user's timezone
        user_profile.date_joined = datetime.datetime(2018, 1, 5, 1, 0, 0, 0, pytz.UTC)
        self.assertEqual(followup_day2_email_delay(user_profile), datetime.timedelta(days=1, hours=-1))

class NoReplyEmailTest(ZulipTestCase):
    def test_noreply_email_address(self) -> None:
        self.assertTrue(re.search(self.TOKENIZED_NOREPLY_REGEX, FromAddress.tokenized_no_reply_address()))

        with self.settings(ADD_TOKENS_TO_NOREPLY_ADDRESS=False):
            self.assertEqual(FromAddress.tokenized_no_reply_address(), "noreply@testserver")

class TwoFactorAuthTest(ZulipTestCase):
    @patch('two_factor.models.totp')
    def test_two_factor_login(self, mock_totp):
        # type: (MagicMock) -> None
        token = 123456
        email = self.example_email('hamlet')
        password = 'testing'

        user_profile = self.example_user('hamlet')
        user_profile.set_password(password)
        user_profile.save()
        self.create_default_device(user_profile)

        def totp(*args, **kwargs):
            # type: (*Any, **Any) -> int
            return token

        mock_totp.side_effect = totp

        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',),
                           TWO_FACTOR_CALL_GATEWAY='two_factor.gateways.fake.Fake',
                           TWO_FACTOR_SMS_GATEWAY='two_factor.gateways.fake.Fake',
                           TWO_FACTOR_AUTHENTICATION_ENABLED=True):

            first_step_data = {"username": email,
                               "password": password,
                               "two_factor_login_view-current_step": "auth"}
            result = self.client_post("/accounts/login/", first_step_data)
            self.assertEqual(result.status_code, 200)

            second_step_data = {"token-otp_token": str(token),
                                "two_factor_login_view-current_step": "token"}
            result = self.client_post("/accounts/login/", second_step_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "http://zulip.testserver")

            # Going to login page should redirect to '/' if user is already
            # logged in.
            result = self.client_get('/accounts/login/')
            self.assertEqual(result["Location"], "http://zulip.testserver")

class NameRestrictionsTest(ZulipTestCase):
    def test_whitelisted_disposable_domains(self) -> None:
        self.assertFalse(is_disposable_domain('OPayQ.com'))

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
        result = self.client_get("/accounts/go/?next=billing")
        self.assert_in_success_response(["Enter your organization's Zulip URL", 'action="/accounts/go/?next=billing"'], result)

        result = self.client_post("/accounts/go/?next=billing", {"subdomain": "lear"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://lear.testserver/billing")
