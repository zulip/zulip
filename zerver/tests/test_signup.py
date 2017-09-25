# -*- coding: utf-8 -*-
from __future__ import absolute_import
import datetime
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.utils.timezone import now as timezone_now

from mock import patch, MagicMock
from zerver.lib.test_helpers import MockLDAP

from confirmation.models import Confirmation, create_confirmation_link, MultiuseInvite, \
    generate_key, confirmation_url
from zilencer.models import Deployment

from zerver.forms import HomepageForm, WRONG_SUBDOMAIN_ERROR
from zerver.lib.actions import do_change_password, gather_subscriptions
from zerver.views.auth import login_or_register_remote_user
from zerver.views.invite import get_invitee_emails_set
from zerver.views.registration import confirmation_key, \
    redirect_and_log_into_subdomain, send_registration_completion_email

from zerver.models import (
    get_realm, get_prereg_user_by_email, get_user,
    get_unique_open_realm, get_unique_non_system_realm,
    completely_open, get_recipient,
    PreregistrationUser, Realm, RealmDomain, Recipient, Message,
    ScheduledEmail, UserProfile, UserMessage,
    Stream, Subscription, flush_per_request_caches
)
from zerver.lib.actions import (
    set_default_streams,
    do_change_is_admin,
    get_stream,
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
    one_click_unsubscribe_link
from zerver.lib.test_helpers import find_pattern_in_email, find_key_by_email, queries_captured, \
    HostRequestMock, unsign_subdomain_cookie
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_runner import slow
from zerver.lib.sessions import get_session_dict_user
from zerver.context_processors import common_context

from collections import defaultdict
import re
import smtplib
import ujson

from typing import Any, Dict, List, Optional, Set, Text

from six.moves import urllib, range, zip
import os

class RedirectAndLogIntoSubdomainTestCase(ZulipTestCase):
    def test_cookie_data(self):
        # type: () -> None
        realm = Realm.objects.all().first()
        name = 'Hamlet'
        email = self.example_email("hamlet")
        response = redirect_and_log_into_subdomain(realm, name, email)
        data = unsign_subdomain_cookie(response)
        self.assertDictEqual(data, {'name': name, 'email': email,
                                    'subdomain': realm.subdomain,
                                    'is_signup': False})

        response = redirect_and_log_into_subdomain(realm, name, email,
                                                   is_signup=True)
        data = unsign_subdomain_cookie(response)
        self.assertDictEqual(data, {'name': name, 'email': email,
                                    'subdomain': realm.subdomain,
                                    'is_signup': True})

class DeactivationNoticeTestCase(ZulipTestCase):
    def test_redirection_for_deactivated_realm(self):
        # type: () -> None
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            for url in ('/register/', '/login/'):
                result = self.client_get(url)
                self.assertEqual(result.status_code, 302)
                self.assertIn('deactivated', result.url)

    def test_redirection_for_active_realm(self):
        # type: () -> None
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            for url in ('/register/', '/login/'):
                result = self.client_get(url)
                self.assertEqual(result.status_code, 200)

    def test_deactivation_notice_when_realm_is_active(self):
        # type: () -> None
        result = self.client_get('/accounts/deactivated/')
        self.assertEqual(result.status_code, 302)
        self.assertIn('login', result.url)

    def test_deactivation_notice_when_deactivated(self):
        # type: () -> None
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            result = self.client_get('/accounts/deactivated/')
            self.assertIn("Zulip Dev, has been deactivated.", result.content.decode())

class AddNewUserHistoryTest(ZulipTestCase):
    def test_add_new_user_history_race(self):
        # type: () -> None
        """Sends a message during user creation"""
        # Create a user who hasn't had historical messages added
        stream_dict = {
            "Denmark": {"description": "A Scandinavian country", "invite_only": False},
            "Verona": {"description": "A city in Italy", "invite_only": False}
        }  # type: Dict[Text, Dict[Text, Any]]
        realm = get_realm('zulip')
        set_default_streams(realm, stream_dict)
        with patch("zerver.lib.actions.add_new_user_history"):
            self.register(self.nonreg_email('test'), "test")
        user_profile = self.nonreg_user('test')

        subs = Subscription.objects.select_related("recipient").filter(
            user_profile=user_profile, recipient__type=Recipient.STREAM)
        streams = Stream.objects.filter(id__in=[sub.recipient.type_id for sub in subs])
        self.send_message(self.example_email('hamlet'), streams[0].name, Recipient.STREAM, "test")
        add_new_user_history(user_profile, streams)

class PasswordResetTest(ZulipTestCase):
    """
    Log in, reset password, log out, log in with new password.
    """

    def test_password_reset(self):
        # type: () -> None
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

        self.assert_in_response("Check your email to finish the process.", result)

        # Check that the password reset email is from a noreply address.
        from django.core.mail import outbox
        from_email = outbox[0].from_email
        self.assertIn("Zulip Account Security", from_email)
        self.assertIn(FromAddress.NOREPLY, from_email)

        # Visit the password reset link.
        password_reset_url = self.get_confirmation_url_from_outbox(email, "(\S+)")
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

    def test_invalid_subdomain(self):
        # type: () -> None
        email = self.example_email("hamlet")
        string_id = 'hamlet'
        name = 'Hamlet'
        do_create_realm(
            string_id,
            name,
            restricted_to_domain=False,
            invite_required=False
        )

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            with patch('zerver.forms.get_subdomain', return_value=string_id):
                # start the password reset process by supplying an email address
                result = self.client_post(
                    '/accounts/password/reset/', {'email': email})

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email to finish the process.", result)

        from django.core.mail import outbox
        self.assertEqual(len(outbox), 1)
        message = outbox.pop()
        self.assertIn(FromAddress.NOREPLY, message.from_email)
        self.assertIn("hamlet@zulip.com does not\nhave an active account in http://",
                      message.body)

    def test_correct_subdomain(self):
        # type: () -> None
        email = self.example_email("hamlet")
        string_id = 'zulip'

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            with patch('zerver.forms.get_subdomain', return_value=string_id):
                # start the password reset process by supplying an email address
                result = self.client_post(
                    '/accounts/password/reset/', {'email': email})

        # check the redirect link telling you to check mail for password reset link
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
            "/accounts/password/reset/done/"))
        result = self.client_get(result["Location"])

        self.assert_in_response("Check your email to finish the process.", result)

        from django.core.mail import outbox
        self.assertEqual(len(outbox), 1)
        message = outbox.pop()
        self.assertIn("Zulip Account Security", message.from_email)
        self.assertIn(FromAddress.NOREPLY, message.from_email)
        self.assertIn("Psst. Word on the street is that you",
                      message.body)

    def test_redirect_endpoints(self):
        # type: () -> None
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
        self.assert_in_success_response(["Still no email?"], result)

class LoginTest(ZulipTestCase):
    """
    Logging in, registration, and logging out.
    """

    def test_login(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        user_profile = self.example_user('hamlet')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_bad_password(self):
        # type: () -> None
        self.login(self.example_email("hamlet"), password="wrongpassword", fails=True)
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_login_nonexist_user(self):
        # type: () -> None
        result = self.login_with_return("xxx@zulip.com", "xxx")
        self.assert_in_response("Please enter a correct email and password", result)

    def test_register(self):
        # type: () -> None
        realm = get_realm("zulip")
        stream_dict = {"stream_"+str(i): {"description": "stream_%s_description" % i, "invite_only": False}
                       for i in range(40)}  # type: Dict[Text, Dict[Text, Any]]
        for stream_name in stream_dict.keys():
            self.make_stream(stream_name, realm=realm)

        set_default_streams(realm, stream_dict)
        # Clear all the caches.
        flush_per_request_caches()
        ContentType.objects.clear_cache()
        Site.objects.clear_cache()

        with queries_captured() as queries:
            self.register(self.nonreg_email('test'), "test")
        # Ensure the number of queries we make is not O(streams)
        self.assert_length(queries, 67)
        user_profile = self.nonreg_user('test')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)
        self.assertFalse(user_profile.enable_stream_desktop_notifications)

    def test_register_deactivated(self):
        # type: () -> None
        """
        If you try to register for a deactivated realm, you get a clear error
        page.
        """
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.register(self.nonreg_email('test'), "test")
        self.assertEqual(result.status_code, 302)
        self.assertIn('deactivated', result.url)

        with self.assertRaises(UserProfile.DoesNotExist):
            self.nonreg_user('test')

    def test_login_deactivated(self):
        # type: () -> None
        """
        If you try to log in to a deactivated realm, you get a clear error page.
        """
        realm = get_realm("zulip")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.login_with_return(self.example_email("hamlet"))
        self.assert_in_response("has been deactivated", result)

    def test_logout(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        # We use the logout API, not self.logout, to make sure we test
        # the actual logout code path.
        self.client_post('/accounts/logout/')
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_non_ascii_login(self):
        # type: () -> None
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

    def test_login_page_redirects_logged_in_user(self):
        # type: () -> None
        """You will be redirected to the app's main page if you land on the
        login page when already logged in.
        """
        self.login(self.example_email("cordelia"))
        response = self.client_get("/login/")
        self.assertEqual(response["Location"], "/")

class InviteUserTest(ZulipTestCase):

    def invite(self, users, streams, body=''):
        # type: (Text, List[Text], str) -> HttpResponse
        """
        Invites the specified users to Zulip with the specified streams.

        users should be a string containing the users to invite, comma or
            newline separated.

        streams should be a list of strings.
        """

        return self.client_post("/json/invites",
                                {"invitee_emails": users,
                                 "stream": streams,
                                 "custom_body": body})

    def check_sent_emails(self, correct_recipients, custom_body=None, custom_from_name=None):
        # type: (List[Text], Optional[str], Optional[str]) -> None
        from django.core.mail import outbox
        self.assertEqual(len(outbox), len(correct_recipients))
        email_recipients = [email.recipients()[0] for email in outbox]
        self.assertEqual(sorted(email_recipients), sorted(correct_recipients))
        if len(outbox) == 0:
            return

        if custom_body is None:
            self.assertNotIn("Message from", outbox[0].body)
        else:
            self.assertIn("Message from ", outbox[0].body)
            self.assertIn(custom_body, outbox[0].body)

        if custom_from_name is not None:
            self.assertIn(custom_from_name, outbox[0].from_email)

        self.assertIn(FromAddress.NOREPLY, outbox[0].from_email)

    def test_successful_invite_user(self):
        # type: () -> None
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login(self.example_email("hamlet"))
        invitee = "alice-test@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee))
        self.check_sent_emails([invitee], custom_from_name="Hamlet")

    def test_successful_invite_user_with_custom_body(self):
        # type: () -> None
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login(self.example_email("hamlet"))
        invitee = "alice-test@zulip.com"
        body = "Custom Text."
        self.assert_json_success(self.invite(invitee, ["Denmark"], body))
        self.assertTrue(find_pattern_in_email(invitee, body))
        self.check_sent_emails([invitee], custom_body=body, custom_from_name="Hamlet")

    def test_successful_invite_user_with_name(self):
        # type: () -> None
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

    def test_successful_invite_user_with_name_and_normal_one(self):
        # type: () -> None
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

    def test_require_realm_admin(self):
        # type: () -> None
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
                               "Must be a realm administrator")

        # Now verify an administrator can do it
        self.login("iago@zulip.com")
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

    def test_successful_invite_user_with_notifications_stream(self):
        # type: () -> None
        """
        A call to /json/invites with valid parameters unconditionally
        subscribes the invitee to the notifications stream if it exists and is
        public.
        """
        realm = get_realm('zulip')
        notifications_stream = get_stream('Verona', realm)
        realm.notifications_stream = notifications_stream
        realm.save()

        self.login(self.example_email("hamlet"))
        invitee = 'alice-test@zulip.com'
        self.assert_json_success(self.invite(invitee, ['Denmark']))
        self.assertTrue(find_key_by_email(invitee))
        self.check_sent_emails([invitee])

        prereg_user = get_prereg_user_by_email(invitee)
        streams = list(prereg_user.streams.all())
        self.assertTrue(notifications_stream in streams)

    def test_invite_user_signup_initial_history(self):
        # type: () -> None
        """
        Test that a new user invited to a stream receives some initial
        history but only from public streams.
        """
        self.login(self.example_email('hamlet'))
        user_profile = self.example_user('hamlet')
        private_stream_name = "Secret"
        self.make_stream(private_stream_name, invite_only=True)
        self.subscribe(user_profile, private_stream_name)
        public_msg_id = self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM,
                                          "Public topic", "Public message")
        secret_msg_id = self.send_message(self.example_email("hamlet"), private_stream_name, Recipient.STREAM,
                                          "Secret topic", "Secret message")
        invitee = self.nonreg_email('alice')
        self.assert_json_success(self.invite(invitee, [private_stream_name, "Denmark"]))
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user('alice')
        invitee_msg_ids = [um.message_id for um in
                           UserMessage.objects.filter(user_profile=invitee_profile)]
        self.assertTrue(public_msg_id in invitee_msg_ids)
        self.assertFalse(secret_msg_id in invitee_msg_ids)

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

    def test_multi_user_invite(self):
        # type: () -> None
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

    def test_missing_or_invalid_params(self):
        # type: () -> None
        """
        Tests inviting with various missing or invalid parameters.
        """
        self.login(self.example_email("hamlet"))
        self.assert_json_error(
            self.client_post("/json/invites",
                             {"invitee_emails": "foo@zulip.com",
                              "custom_body": ''}),
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

    def test_invalid_stream(self):
        # type: () -> None
        """
        Tests inviting to a non-existent stream.
        """
        self.login(self.example_email("hamlet"))
        self.assert_json_error(self.invite("iago-test@zulip.com", ["NotARealStream"]),
                               "Stream does not exist: NotARealStream. No invites were sent.")
        self.check_sent_emails([])

    def test_invite_existing_user(self):
        # type: () -> None
        """
        If you invite an address already using Zulip, no invitation is sent.
        """
        self.login(self.example_email("hamlet"))
        self.assert_json_error(
            self.client_post("/json/invites",
                             {"invitee_emails": self.example_email("hamlet"),
                              "stream": ["Denmark"],
                              "custom_body": ''}),
            "We weren't able to invite anyone.")
        self.assertRaises(PreregistrationUser.DoesNotExist,
                          lambda: PreregistrationUser.objects.get(
                              email=self.example_email("hamlet")))
        self.check_sent_emails([])

    def test_invite_some_existing_some_new(self):
        # type: () -> None
        """
        If you invite a mix of already existing and new users, invitations are
        only sent to the new users.
        """
        self.login(self.example_email("hamlet"))
        existing = [self.example_email("hamlet"), u"othello@zulip.com"]
        new = [u"foo-test@zulip.com", u"bar-test@zulip.com"]

        result = self.client_post("/json/invites",
                                  {"invitee_emails": "\n".join(existing + new),
                                   "stream": ["Denmark"],
                                   "custom_body": ''})
        self.assert_json_error(result,
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

        prereg_user = get_prereg_user_by_email('foo-test@zulip.com')
        self.assertEqual(prereg_user.email, 'foo-test@zulip.com')

    def test_invite_outside_domain_in_closed_realm(self):
        # type: () -> None
        """
        In a realm with `restricted_to_domain = True`, you can't invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.restricted_to_domain = True
        zulip_realm.save()

        self.login(self.example_email("hamlet"))
        external_address = "foo@example.com"

        self.assert_json_error(
            self.invite(external_address, ["Denmark"]),
            "Some emails did not validate, so we didn't send any invitations.")

    def test_invite_outside_domain_in_open_realm(self):
        # type: () -> None
        """
        In a realm with `restricted_to_domain = False`, you can invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.restricted_to_domain = False
        zulip_realm.save()

        self.login(self.example_email("hamlet"))
        external_address = "foo@example.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

    def test_invite_outside_domain_before_closing(self):
        # type: () -> None
        """
        If you invite someone with a different domain from that of the realm
        when `restricted_to_domain = False`, but `restricted_to_domain` later
        changes to true, the invitation should succeed but the invitee's signup
        attempt should fail.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.restricted_to_domain = False
        zulip_realm.save()

        self.login(self.example_email("hamlet"))
        external_address = "foo@example.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

        zulip_realm.restricted_to_domain = True
        zulip_realm.save()

        result = self.submit_reg_form_for_user("foo@example.com", "password")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("only allows users with e-mail", result)

    def test_invite_with_non_ascii_streams(self):
        # type: () -> None
        """
        Inviting someone to streams with non-ASCII characters succeeds.
        """
        self.login(self.example_email("hamlet"))
        invitee = "alice-test@zulip.com"

        stream_name = u"hÃ¼mbÃ¼Çµ"

        # Make sure we're subscribed before inviting someone.
        self.subscribe(self.example_user("hamlet"), stream_name)

        self.assert_json_success(self.invite(invitee, [stream_name]))

    def test_invitation_reminder_email(self):
        # type: () -> None
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
        invitee = get_prereg_user_by_email(data["email"])
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
            send_future_email(
                "zerver/emails/invitation_reminder", to_email=data["email"],
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
            scheduled_timestamp__lte=timezone_now())
        self.assertEqual(len(email_jobs_to_deliver), 1)

        self.register(invitee_email, "test")
        email_jobs_to_deliver = ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now())
        self.assertEqual(len(email_jobs_to_deliver), 0)

class InviteeEmailsParserTests(TestCase):
    def setUp(self):
        # type: () -> None
        self.email1 = "email1@zulip.com"
        self.email2 = "email2@zulip.com"
        self.email3 = "email3@zulip.com"

    def test_if_emails_separated_by_commas_are_parsed_and_striped_correctly(self):
        # type: () -> None
        emails_raw = "{} ,{}, {}".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_separated_by_newlines_are_parsed_and_striped_correctly(self):
        # type: () -> None
        emails_raw = "{}\n {}\n {} ".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_from_email_client_separated_by_newlines_are_parsed_correctly(self):
        # type: () -> None
        emails_raw = "Email One <{}>\nEmailTwo<{}>\nEmail Three<{}>".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_in_mixed_style_are_parsed_correctly(self):
        # type: () -> None
        emails_raw = "Email One <{}>,EmailTwo<{}>\n{}".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

class MultiuseInviteTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.realm = get_realm('zulip')
        self.realm.invite_required = True
        self.realm.save()

    def generate_multiuse_invite_link(self, streams=None, date_sent=None):
        # type: (List[Stream], Optional[datetime.datetime]) -> Text
        invite = MultiuseInvite(realm=self.realm, referred_by=self.example_user("iago"))
        invite.save()

        if streams is not None:
            invite.streams = streams
            invite.save()

        if date_sent is None:
            date_sent = timezone_now()
        key = generate_key()
        Confirmation.objects.create(content_object=invite, date_sent=date_sent,
                                    confirmation_key=key, type=Confirmation.MULTIUSE_INVITE)

        return confirmation_url(key, self.realm.host, Confirmation.MULTIUSE_INVITE)

    def check_user_able_to_register(self, email, invite_link):
        # type: (Text, Text) -> None
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

    def check_user_subscribed_only_to_streams(self, user_name, streams):
        # type: (str, List[Stream]) -> None
        sorted(streams, key=lambda x: x.name)
        subscribed_streams = gather_subscriptions(self.nonreg_user(user_name))[0]

        self.assertEqual(len(subscribed_streams), len(streams))

        for x, y in zip(subscribed_streams, streams):
            self.assertEqual(x["name"], y.name)

    def test_valid_multiuse_link(self):
        # type: () -> None
        email1 = self.nonreg_email("test")
        email2 = self.nonreg_email("test1")
        email3 = self.nonreg_email("alice")

        date_sent = timezone_now() - datetime.timedelta(days=settings.INVITATION_LINK_VALIDITY_DAYS - 1)
        invite_link = self.generate_multiuse_invite_link(date_sent=date_sent)

        self.check_user_able_to_register(email1, invite_link)
        self.check_user_able_to_register(email2, invite_link)
        self.check_user_able_to_register(email3, invite_link)

    def test_expired_multiuse_link(self):
        # type: () -> None
        email = self.nonreg_email('newuser')
        date_sent = timezone_now() - datetime.timedelta(days=settings.INVITATION_LINK_VALIDITY_DAYS)
        invite_link = self.generate_multiuse_invite_link(date_sent=date_sent)
        result = self.client_post(invite_link, {'email': email})

        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Whoops. The confirmation link has expired.", result)

    def test_invalid_multiuse_link(self):
        # type: () -> None
        email = self.nonreg_email('newuser')
        invite_link = "/join/invalid_key/"
        result = self.client_post(invite_link, {'email': email})

        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Whoops. The confirmation link is malformed.", result)

    def test_invalid_multiuse_link_in_open_realm(self):
        # type: () -> None
        self.realm.invite_required = False
        self.realm.save()

        email = self.nonreg_email('newuser')
        invite_link = "/join/invalid_key/"

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            with patch('zerver.views.registration.get_realm_from_request', return_value=self.realm):
                with patch('zerver.views.registration.get_realm', return_value=self.realm):
                    self.check_user_able_to_register(email, invite_link)

    def test_multiuse_link_with_specified_streams(self):
        # type: () -> None
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

class EmailUnsubscribeTests(ZulipTestCase):
    def test_error_unsubscribe(self):
        # type: () -> None

        # An invalid insubscribe token "test123" produces an error.
        result = self.client_get('/accounts/unsubscribe/missed_messages/test123')
        self.assert_in_response('Unknown email unsubscribe request', result)

        # An unknown message type "fake" produces an error.
        user_profile = self.example_user('hamlet')
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "fake")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)
        self.assert_in_response('Unknown email unsubscribe request', result)

    def test_missedmessage_unsubscribe(self):
        # type: () -> None
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

    def test_welcome_unsubscribe(self):
        # type: () -> None
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

    def test_digest_unsubscribe(self):
        # type: () -> None
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
        send_future_email('zerver/emails/digest', to_user_id=user_profile.id, context=context)

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

class RealmCreationTest(ZulipTestCase):

    def test_create_realm(self):
        # type: () -> None
        password = "test"
        string_id = "zuliptest"
        email = "user1@test.com"
        realm = get_realm('test')

        # Make sure the realm does not exist
        self.assertIsNone(realm)

        with self.settings(OPEN_REALM_CREATION=True):
            # Create new realm with the email
            result = self.client_post('/create_realm/', {'email': email})
            self.assertEqual(result.status_code, 302)
            self.assertTrue(result["Location"].endswith(
                "/accounts/send_confirm/%s" % (email,)))
            result = self.client_get(result["Location"])
            self.assert_in_response("Check your email so we can get started.", result)

            # Visit the confirmation link.
            confirmation_url = self.get_confirmation_url_from_outbox(email)
            result = self.client_get(confirmation_url)
            self.assertEqual(result.status_code, 200)

            result = self.submit_reg_form_for_user(email, password, realm_subdomain=string_id)
            self.assertEqual(result.status_code, 302)

            # Make sure the realm is created
            realm = get_realm(string_id)
            self.assertIsNotNone(realm)
            self.assertEqual(realm.string_id, string_id)
            self.assertEqual(get_user(email, realm).realm, realm)

            # Check defaults
            self.assertEqual(realm.org_type, Realm.CORPORATE)
            self.assertEqual(realm.restricted_to_domain, False)
            self.assertEqual(realm.invite_required, True)

            self.assertTrue(result["Location"].endswith("/"))

            # Check welcome messages
            for stream_name, text, message_count in [
                    ('announce', 'This is', 1),
                    ('core team', 'This is', 1),
                    ('general', 'Welcome to', 1),
                    ('new members', 'stream is', 1),
                    ('zulip', 'Here is', 3)]:
                stream = get_stream(stream_name, realm)
                recipient = get_recipient(Recipient.STREAM, stream.id)
                messages = Message.objects.filter(recipient=recipient).order_by('pub_date')
                self.assertEqual(len(messages), message_count)
                self.assertIn(text, messages[0].content)

    def test_create_realm_existing_email(self):
        # type: () -> None
        """
        Trying to create a realm with an existing email should just redirect to
        a login page.
        """
        with self.settings(OPEN_REALM_CREATION=True):
            email = self.example_email("hamlet")
            result = self.client_post('/create_realm/', {'email': email})
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result['Location'])

    def test_create_realm_no_creation_key(self):
        # type: () -> None
        """
        Trying to create a realm without a creation_key should fail when
        OPEN_REALM_CREATION is false.
        """
        email = "user1@test.com"
        realm = get_realm('test')

        # Make sure the realm does not exist
        self.assertIsNone(realm)

        with self.settings(OPEN_REALM_CREATION=False):
            # Create new realm with the email, but no creation key.
            result = self.client_post('/create_realm/', {'email': email})
            self.assertEqual(result.status_code, 200)
            self.assert_in_response('New organization creation disabled.', result)

    def test_create_realm_with_subdomain(self):
        # type: () -> None
        password = "test"
        string_id = "zuliptest"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        self.assertIsNone(get_realm('test'))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True), self.settings(OPEN_REALM_CREATION=True):
            # Create new realm with the email
            result = self.client_post('/create_realm/', {'email': email})
            self.assertEqual(result.status_code, 302)
            self.assertTrue(result["Location"].endswith(
                "/accounts/send_confirm/%s" % (email,)))
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

    def test_mailinator_signup(self):
        # type: () -> None
        with self.settings(OPEN_REALM_CREATION=True):
            result = self.client_post('/create_realm/', {'email': "hi@mailinator.com"})
            self.assert_in_response('Please use your real email address.', result)

    def test_subdomain_restrictions(self):
        # type: () -> None
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        with self.settings(REALMS_HAVE_SUBDOMAINS=False), self.settings(OPEN_REALM_CREATION=True):
            result = self.client_post('/create_realm/', {'email': email})
            self.client_get(result["Location"])
            confirmation_url = self.get_confirmation_url_from_outbox(email)
            self.client_get(confirmation_url)

            errors = {'id': "at least 3 characters",
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

class UserSignUpTest(ZulipTestCase):

    def _assert_redirected_to(self, result, url):
        # type: (HttpResponse, Text) -> None
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result['LOCATION'], url)

    def test_bad_email_configuration_for_accounts_home(self):
        # type: () -> None
        """
        Make sure we redirect for SMTP errors.
        """
        email = self.nonreg_email('newguy')

        smtp_mock = patch(
            'zerver.views.registration.send_registration_completion_email',
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

    def test_bad_email_configuration_for_create_realm(self):
        # type: () -> None
        """
        Make sure we redirect for SMTP errors.
        """
        email = self.nonreg_email('newguy')

        smtp_mock = patch(
            'zerver.views.registration.send_registration_completion_email',
            side_effect=smtplib.SMTPException('uh oh')
        )

        error_mock = patch('logging.error')

        with smtp_mock, error_mock as err:
            result = self.client_post('/create_realm/', {'email': email})

        self._assert_redirected_to(result, '/config-error/smtp')

        self.assertEqual(
            err.call_args_list[0][0][0],
            'Error in create_realm: uh oh'
        )

    def test_user_default_language_and_timezone(self):
        # type: () -> None
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

    def test_signup_already_active(self):
        # type: () -> None
        """
        Check if signing up with an active email redirects to a login page.
        """
        email = self.example_email("hamlet")
        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertIn('login', result['Location'])
        result = self.client_get(result.url)
        self.assert_in_response("You've already registered", result)

    def test_signup_invalid_name(self):
        # type: () -> None
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

    def test_signup_without_password(self):
        # type: () -> None
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

    def test_signup_without_full_name(self):
        # type: () -> None
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
        self.assert_in_success_response(["You're almost there."], result)

        # Verify that the user is asked for name and password
        self.assert_in_success_response(['id_password', 'id_full_name'], result)

    def test_signup_with_full_name(self):
        # type: () -> None
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
        self.assert_in_success_response(["You're almost there."], result)

    def test_signup_invalid_subdomain(self):
        # type: () -> None
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

        def invalid_subdomain(**kwargs):
            # type: (**Any) -> Any
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

    def test_unique_completely_open_domain(self):
        # type: () -> None
        password = "test"
        email = "user1@acme.com"
        subdomain = "zulip"

        realm = get_realm('zulip')
        realm.restricted_to_domain = False
        realm.invite_required = False
        realm.save()

        for string_id in ('simple', 'zephyr'):
            realm = get_realm(string_id)
            do_deactivate_realm(realm)
            realm.save()

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
                confirmation_link_pattern = re.compile(settings.EXTERNAL_HOST + "(\S+)>")
                confirmation_url = confirmation_link_pattern.search(
                    message.body).groups()[0]
                break
        else:
            raise AssertionError("Couldn't find a confirmation email.")

        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(email,
                                               password,
                                               from_confirmation="1",
                                               # Pass HTTP_HOST for the target subdomain
                                               HTTP_HOST=subdomain + ".testserver")
        self.assert_in_success_response(["You're almost there."], result)

    def test_failed_signup_due_to_restricted_domain(self):
        # type: () -> None
        realm = get_realm('zulip')
        realm.invite_required = False
        realm.save()
        with self.settings(REALMS_HAVE_SUBDOMAINS = True):
            request = HostRequestMock(host = realm.host)
            request.session = {}  # type: ignore
            email = 'user@acme.com'
            form = HomepageForm({'email': email}, realm=realm)
            self.assertIn("Your email address, {}, is not in one of the domains".format(email),
                          form.errors['email'][0])

    def test_failed_signup_due_to_invite_required(self):
        # type: () -> None
        realm = get_realm('zulip')
        realm.invite_required = True
        realm.save()
        request = HostRequestMock(host = realm.host)
        request.session = {}  # type: ignore
        email = 'user@zulip.com'
        form = HomepageForm({'email': email}, realm=realm)
        self.assertIn("Please request an invite for {} from".format(email),
                      form.errors['email'][0])

    def test_failed_signup_due_to_nonexistent_realm(self):
        # type: () -> None
        with self.settings(REALMS_HAVE_SUBDOMAINS = True):
            request = HostRequestMock(host = 'acme.' + settings.EXTERNAL_HOST)
            request.session = {}  # type: ignore
            email = 'user@acme.com'
            form = HomepageForm({'email': email}, realm=None)
            self.assertIn("organization you are trying to join using {} does "
                          "not exist".format(email), form.errors['email'][0])

    def test_registration_through_ldap(self):
        # type: () -> None
        password = "testing"
        email = "newuser@zulip.com"
        subdomain = "zulip"
        realm_name = "Zulip"
        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        ldap_patcher = patch('django_auth_ldap.config.ldap.initialize')
        mock_initialize = ldap_patcher.start()
        mock_ldap = MockLDAP()
        mock_initialize.return_value = mock_ldap

        mock_ldap.directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing',
                'fn': ['New User Name']
            }
        }

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
                confirmation_link_pattern = re.compile(settings.EXTERNAL_HOST + "(\S+)>")
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
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            result = self.client_get(confirmation_url)
            self.assertEqual(result.status_code, 200)

            # The full_name should not be overriden by the value from LDAP if
            # request.session['authenticated_full_name'] has not been set yet.
            with patch('zerver.views.registration.name_changes_disabled', return_value=True):
                result = self.submit_reg_form_for_user(email,
                                                       password,
                                                       full_name="Non LDAP Full Name",
                                                       realm_name=realm_name,
                                                       realm_subdomain=subdomain,
                                                       # Pass HTTP_HOST for the target subdomain
                                                       HTTP_HOST=subdomain + ".testserver")
            self.assert_in_success_response(["You're almost there.",
                                             "Non LDAP Full Name",
                                             "newuser@zulip.com"],
                                            result)

            # Verify that the user is asked for name
            self.assert_in_success_response(['id_full_name'], result)
            # TODO: Ideally, we wouldn't ask for a password if LDAP is
            # enabled, in which case this assert should be invertedq.
            self.assert_in_success_response(['id_password'], result)

            # Submitting the registration form with from_confirmation='1' sets
            # the value of request.session['authenticated_full_name'] from LDAP.
            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   realm_name=realm_name,
                                                   realm_subdomain=subdomain,
                                                   from_confirmation='1',
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            self.assert_in_success_response(["You're almost there.",
                                             "New User Name",
                                             "newuser@zulip.com"],
                                            result)

            # The full name be populated from the value of
            # request.session['authenticated_full_name'] from LDAP in the case
            # where from_confirmation and name_changes_disabled are both False.
            with patch('zerver.views.registration.name_changes_disabled', return_value=True):
                result = self.submit_reg_form_for_user(email,
                                                       password,
                                                       full_name="Non LDAP Full Name",
                                                       realm_name=realm_name,
                                                       realm_subdomain=subdomain,
                                                       # Pass HTTP_HOST for the target subdomain
                                                       HTTP_HOST=subdomain + ".testserver")
            self.assert_in_success_response(["You're almost there.",
                                             "New User Name",
                                             "newuser@zulip.com"],
                                            result)

            # Test the TypeError exception handler
            mock_ldap.directory = {
                'uid=newuser,ou=users,dc=zulip,dc=com': {
                    'userPassword': 'testing',
                    'fn': None  # This will raise TypeError
                }
            }
            result = self.submit_reg_form_for_user(email,
                                                   password,
                                                   realm_name=realm_name,
                                                   realm_subdomain=subdomain,
                                                   from_confirmation='1',
                                                   # Pass HTTP_HOST for the target subdomain
                                                   HTTP_HOST=subdomain + ".testserver")
            self.assert_in_success_response(["You're almost there.",
                                             "newuser@zulip.com"],
                                            result)

    def test_realm_creation_through_ldap(self):
        # type: () -> None
        password = "testing"
        email = "newuser@zulip.com"
        subdomain = "zulip"
        realm_name = "Zulip"
        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        ldap_patcher = patch('django_auth_ldap.config.ldap.initialize')
        mock_initialize = ldap_patcher.start()
        mock_ldap = MockLDAP()
        mock_initialize.return_value = mock_ldap

        mock_ldap.directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing',
                'fn': ['New User Name']
            }
        }

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
                confirmation_link_pattern = re.compile(settings.EXTERNAL_HOST + "(\S+)>")
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
            self.assert_in_success_response(["You're almost there.",
                                             "newuser@zulip.com"],
                                            result)

        mock_ldap.reset()
        mock_initialize.stop()

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    @patch('DNS.dnslookup', return_value=[['sipbtest:*:20922:101:Fred Sipb,,,:/mit/sipbtest:/bin/athena/tcsh']])
    def test_registration_of_mirror_dummy_user(self, ignored):
        # type: (Any) -> None
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
                confirmation_link_pattern = re.compile(settings.EXTERNAL_HOST + "(\S+)>")
                confirmation_url = confirmation_link_pattern.search(
                    message.body).groups()[0]
                break
        else:
            raise AssertionError("Couldn't find a confirmation email.")

        result = self.client_get(confirmation_url, subdomain="zephyr")
        self.assertEqual(result.status_code, 200)

        # If the mirror dummy user is already active, attempting to submit the
        # registration form should just redirect to a login page.
        user_profile.is_active = True
        user_profile.save()
        result = self.submit_reg_form_for_user(email,
                                               password,
                                               from_confirmation='1',
                                               # Pass HTTP_HOST for the target subdomain
                                               HTTP_HOST=subdomain + ".testserver")

        self.assertEqual(result.status_code, 302)
        self.assertIn('login', result['Location'])
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

    def test_registration_of_active_mirror_dummy_user(self):
        # type: (Any) -> None
        """
        Trying to activate an already-active mirror dummy user should just
        redirect to a login page.
        """
        user_profile = self.mit_user("sipbtest")
        email = user_profile.email
        user_profile.is_mirror_dummy = True
        user_profile.is_active = True
        user_profile.save()

        result = self.client_post('/register/', {'email': email})

        self.assertEqual(result.status_code, 302)
        self.assertIn('login', result['Location'])

class TestOpenRealms(ZulipTestCase):
    def test_open_realm_logic(self):
        # type: () -> None
        realm = get_realm('simple')
        do_deactivate_realm(realm)

        mit_realm = get_realm("zephyr")
        self.assertEqual(get_unique_open_realm(), None)
        mit_realm.restricted_to_domain = False
        mit_realm.save()
        self.assertTrue(completely_open(mit_realm))
        self.assertEqual(get_unique_open_realm(), None)
        with self.settings(SYSTEM_ONLY_REALMS={"zulip"}):
            self.assertEqual(get_unique_open_realm(), mit_realm)
        mit_realm.restricted_to_domain = True
        mit_realm.save()
        with self.settings(SYSTEM_ONLY_REALMS={"zulip"}):
            self.assertEqual(get_unique_open_realm(), None)
            self.assertEqual(get_unique_non_system_realm(), mit_realm)

class DeactivateUserTest(ZulipTestCase):

    def test_deactivate_user(self):
        # type: () -> None
        email = self.example_email("hamlet")
        self.login(email)
        user = self.example_user('hamlet')
        self.assertTrue(user.is_active)
        result = self.client_delete('/json/users/me')
        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertFalse(user.is_active)
        self.login(email, fails=True)

    def test_do_not_deactivate_final_admin(self):
        # type: () -> None
        email = self.example_email("iago")
        self.login(email)
        user = self.example_user('iago')
        self.assertTrue(user.is_active)
        result = self.client_delete('/json/users/me')
        self.assert_json_error(result, "Cannot deactivate the only organization administrator")
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

class TestLoginPage(ZulipTestCase):
    def test_login_page_wrong_subdomain_error(self):
        # type: () -> None
        result = self.client_get("/login/?subdomain=1")
        self.assertIn(WRONG_SUBDOMAIN_ERROR, result.content.decode('utf8'))

    @patch('django.http.HttpRequest.get_host')
    def test_login_page_redirects_for_root_alias(self, mock_get_host):
        # type: (MagicMock) -> None
        mock_get_host.return_value = 'www.testserver'
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           ROOT_DOMAIN_LANDING_PAGE=True,
                           ROOT_SUBDOMAIN_ALIASES=['www']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/accounts/find/')

    @patch('django.http.HttpRequest.get_host')
    def test_login_page_redirects_for_root_domain(self, mock_get_host):
        # type: (MagicMock) -> None
        mock_get_host.return_value = 'testserver'
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           ROOT_DOMAIN_LANDING_PAGE=True,
                           ROOT_SUBDOMAIN_ALIASES=['www']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/accounts/find/')

        mock_get_host.return_value = 'www.testserver.com'
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           ROOT_DOMAIN_LANDING_PAGE=True,
                           EXTERNAL_HOST='www.testserver.com',
                           ROOT_SUBDOMAIN_ALIASES=['test']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/accounts/find/')

    @patch('django.http.HttpRequest.get_host')
    def test_login_page_works_without_subdomains(self, mock_get_host):
        # type: (MagicMock) -> None
        mock_get_host.return_value = 'www.testserver'
        with self.settings(ROOT_SUBDOMAIN_ALIASES=['www']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 200)

        mock_get_host.return_value = 'testserver'
        with self.settings(ROOT_SUBDOMAIN_ALIASES=['www']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 200)

class TestFindMyTeam(ZulipTestCase):
    def test_template(self):
        # type: () -> None
        result = self.client_get('/accounts/find/')
        self.assertIn("Find your Zulip accounts", result.content.decode('utf8'))

    def test_result(self):
        # type: () -> None
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
        self.assertEqual(len(outbox), 2)

    def test_find_team_ignore_invalid_email(self):
        # type: () -> None
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

    def test_find_team_reject_invalid_email(self):
        # type: () -> None
        result = self.client_post('/accounts/find/',
                                  dict(emails="invalid_string"))
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Enter a valid email", result.content)
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

        # Just for coverage on perhaps-unnecessary validation code.
        result = self.client_get('/accounts/find/?emails=invalid')
        self.assertEqual(result.status_code, 200)

    def test_find_team_zero_emails(self):
        # type: () -> None
        data = {'emails': ''}
        result = self.client_post('/accounts/find/', data)
        self.assertIn('This field is required', result.content.decode('utf8'))
        self.assertEqual(result.status_code, 200)
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    def test_find_team_one_email(self):
        # type: () -> None
        data = {'emails': self.example_email("hamlet")}
        result = self.client_post('/accounts/find/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/accounts/find/?emails=hamlet%40zulip.com')
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 1)

    def test_find_team_deactivated_user(self):
        # type: () -> None
        do_deactivate_user(self.example_user("hamlet"))
        data = {'emails': self.example_email("hamlet")}
        result = self.client_post('/accounts/find/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/accounts/find/?emails=hamlet%40zulip.com')
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    def test_find_team_deactivated_realm(self):
        # type: () -> None
        do_deactivate_realm(get_realm("zulip"))
        data = {'emails': self.example_email("hamlet")}
        result = self.client_post('/accounts/find/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/accounts/find/?emails=hamlet%40zulip.com')
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    def test_find_team_bot_email(self):
        # type: () -> None
        data = {'emails': self.example_email("webhook_bot")}
        result = self.client_post('/accounts/find/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/accounts/find/?emails=webhook-bot%40zulip.com')
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

    def test_find_team_more_than_ten_emails(self):
        # type: () -> None
        data = {'emails': ','.join(['hamlet-{}@zulip.com'.format(i) for i in range(11)])}
        result = self.client_post('/accounts/find/', data)
        self.assertEqual(result.status_code, 200)
        self.assertIn("Please enter at most 10", result.content.decode('utf8'))
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 0)

class ConfirmationKeyTest(ZulipTestCase):
    def test_confirmation_key(self):
        # type: () -> None
        request = MagicMock()
        request.session = {
            'confirmation_key': {'confirmation_key': 'xyzzy'}
        }
        result = confirmation_key(request)
        self.assert_json_success(result)
        self.assert_in_response('xyzzy', result)

class MobileAuthOTPTest(ZulipTestCase):
    def test_xor_hex_strings(self):
        # type: () -> None
        self.assertEqual(xor_hex_strings('1237c81ab', '18989fd12'), '0aaf57cb9')
        with self.assertRaises(AssertionError):
            xor_hex_strings('1', '31')

    def test_is_valid_otp(self):
        # type: () -> None
        self.assertEqual(is_valid_otp('1234'), False)
        self.assertEqual(is_valid_otp('1234abcd' * 8), True)
        self.assertEqual(is_valid_otp('1234abcZ' * 8), False)

    def test_ascii_to_hex(self):
        # type: () -> None
        self.assertEqual(ascii_to_hex('ZcdR1234'), '5a63645231323334')
        self.assertEqual(hex_to_ascii('5a63645231323334'), 'ZcdR1234')

    def test_otp_encrypt_api_key(self):
        # type: () -> None
        hamlet = self.example_user('hamlet')
        hamlet.api_key = '12ac' * 8
        otp = '7be38894' * 8
        result = otp_encrypt_api_key(hamlet, otp)
        self.assertEqual(result, '4ad1e9f7' * 8)

        decryped = otp_decrypt_api_key(result, otp)
        self.assertEqual(decryped, hamlet.api_key)

class LoginOrAskForRegistrationTestCase(ZulipTestCase):
    def test_confirm(self):
        # type: () -> None
        request = HostRequestMock()
        email = 'new@zulip.com'
        user_profile = None  # type: Optional[UserProfile]
        full_name = 'New User'
        invalid_subdomain = False
        result = login_or_register_remote_user(
            request,
            email,
            user_profile,
            full_name=full_name,
            invalid_subdomain=invalid_subdomain)
        self.assert_in_response('No account found for',
                                result)
        self.assert_in_response('new@zulip.com. Would you like to register instead?',
                                result)

    def test_invalid_subdomain(self):
        # type: () -> None
        request = HostRequestMock()
        email = 'new@zulip.com'
        user_profile = None  # type: Optional[UserProfile]
        full_name = 'New User'
        invalid_subdomain = True
        response = login_or_register_remote_user(
            request,
            email,
            user_profile,
            full_name=full_name,
            invalid_subdomain=invalid_subdomain)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/?subdomain=1', response.url)

    def test_invalid_email(self):
        # type: () -> None
        request = HostRequestMock()
        email = None  # type: Optional[Text]
        user_profile = None  # type: Optional[UserProfile]
        full_name = 'New User'
        invalid_subdomain = False
        response = login_or_register_remote_user(
            request,
            email,
            user_profile,
            full_name=full_name,
            invalid_subdomain=invalid_subdomain)
        self.assert_in_response('Please click the following button if '
                                'you wish to register', response)

    def test_login_under_subdomains(self):
        # type: () -> None
        request = HostRequestMock()
        setattr(request, 'session', self.client.session)
        user_profile = self.example_user('hamlet')
        user_profile.backend = 'zproject.backends.GitHubAuthBackend'
        full_name = 'Hamlet'
        invalid_subdomain = False
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            response = login_or_register_remote_user(
                request,
                user_profile.email,
                user_profile,
                full_name=full_name,
                invalid_subdomain=invalid_subdomain)
            user_id = get_session_dict_user(getattr(request, 'session'))
            self.assertEqual(user_id, user_profile.id)
            self.assertEqual(response.status_code, 302)
            self.assertIn('http://zulip.testserver', response.url)

    def test_login_without_subdomains(self):
        # type: () -> None
        request = HostRequestMock(host="localhost")
        setattr(request, 'session', self.client.session)
        setattr(request, 'get_host', lambda: 'localhost')
        user_profile = self.example_user('hamlet')
        user_profile.backend = 'zproject.backends.GitHubAuthBackend'
        full_name = 'Hamlet'
        invalid_subdomain = False
        with self.settings(REALMS_HAVE_SUBDOMAINS=False):
            response = login_or_register_remote_user(
                request,
                user_profile.email,
                user_profile,
                full_name=full_name,
                invalid_subdomain=invalid_subdomain)
            user_id = get_session_dict_user(getattr(request, 'session'))
            self.assertEqual(user_id, user_profile.id)
            self.assertEqual(response.status_code, 302)
            self.assertIn('http://localhost', response.url)
