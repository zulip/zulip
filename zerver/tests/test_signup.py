# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.conf import settings
from django.http import HttpResponse
from django.test import TestCase

from zilencer.models import Deployment

from zerver.views import get_invitee_emails_set
from zerver.models import (
    get_realm, get_user_profile_by_email,
    PreregistrationUser, Realm, Recipient, ScheduledJob, UserProfile, UserMessage,
)

from zerver.lib.actions import (
    create_stream_if_needed,
    do_add_subscription,
    set_default_streams,
)

from zerver.lib.actions import do_set_realm_default_language
from zerver.lib.digest import send_digest_email
from zerver.lib.notifications import enqueue_welcome_emails, one_click_unsubscribe_link
from zerver.lib.test_helpers import AuthedTestCase, find_key_by_email, queries_captured
from zerver.lib.test_runner import slow
from zerver.lib.session_user import get_session_dict_user

import re
import ujson

from six.moves import urllib
from six.moves import range
import six
from six import text_type

class PublicURLTest(AuthedTestCase):
    """
    Account creation URLs are accessible even when not logged in. Authenticated
    URLs redirect to a page.
    """

    def fetch(self, method, urls, expected_status):
        # type: (str, List[str], int) -> None
        for url in urls:
            response = getattr(self.client, method)(url) # e.g. self.client_post(url) if method is "post"
            self.assertEqual(response.status_code, expected_status,
                             msg="Expected %d, received %d for %s to %s" % (
                    expected_status, response.status_code, method, url))

    def test_public_urls(self):
        # type: () -> None
        """
        Test which views are accessible when not logged in.
        """
        # FIXME: We should also test the Tornado URLs -- this codepath
        # can't do so because this Django test mechanism doesn't go
        # through Tornado.
        get_urls = {200: ["/accounts/home/", "/accounts/login/"],
                    302: ["/"],
                    401: ["/api/v1/streams/Denmark/members",
                          "/api/v1/users/me/subscriptions",
                          "/api/v1/messages",
                          "/json/messages",
                          "/json/streams",
                          ],
                }
        post_urls = {200: ["/accounts/login/"],
                     302: ["/accounts/logout/"],
                     401: ["/json/messages",
                           "/json/invite_users",
                           "/json/settings/change",
                           "/json/subscriptions/remove",
                           "/json/subscriptions/exists",
                           "/json/subscriptions/property",
                           "/json/get_subscribers",
                           "/json/fetch_api_key",
                           "/json/users/me/subscriptions",
                           "/api/v1/users/me/subscriptions",
                           ],
                     400: ["/api/v1/send_message",
                           "/api/v1/external/github",
                           "/api/v1/fetch_api_key",
                           ],
                }
        put_urls = {401: ["/json/users/me/pointer"],
                }
        for status_code, url_set in six.iteritems(get_urls):
            self.fetch("get", url_set, status_code)
        for status_code, url_set in six.iteritems(post_urls):
            self.fetch("post", url_set, status_code)
        for status_code, url_set in six.iteritems(put_urls):
            self.fetch("put", url_set, status_code)

    def test_get_gcid_when_not_configured(self):
        # type: () -> None
        with self.settings(GOOGLE_CLIENT_ID=None):
            resp = self.client_get("/api/v1/fetch_google_client_id")
            self.assertEquals(400, resp.status_code,
                msg="Expected 400, received %d for GET /api/v1/fetch_google_client_id" % resp.status_code,
            )
            data = ujson.loads(resp.content)
            self.assertEqual('error', data['result'])

    def test_get_gcid_when_configured(self):
        # type: () -> None
        with self.settings(GOOGLE_CLIENT_ID="ABCD"):
            resp = self.client_get("/api/v1/fetch_google_client_id")
            self.assertEquals(200, resp.status_code,
                msg="Expected 200, received %d for GET /api/v1/fetch_google_client_id" % resp.status_code,
            )
            data = ujson.loads(resp.content)
            self.assertEqual('success', data['result'])
            self.assertEqual('ABCD', data['google_client_id'])

class LoginTest(AuthedTestCase):
    """
    Logging in, registration, and logging out.
    """

    def test_login(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_bad_password(self):
        # type: () -> None
        self.login("hamlet@zulip.com", password="wrongpassword", fails=True)
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_login_nonexist_user(self):
        # type: () -> None
        result = self.login_with_return("xxx@zulip.com", "xxx")
        self.assert_in_response("Please enter a correct email and password", result)

    def test_register(self):
        # type: () -> None
        realm = get_realm("zulip.com")
        streams = ["stream_%s" % i for i in range(40)]
        for stream in streams:
            create_stream_if_needed(realm, stream)

        set_default_streams(realm, streams)
        with queries_captured() as queries:
            self.register("test", "test")
        # Ensure the number of queries we make is not O(streams)
        self.assert_length(queries, 67)
        user_profile = get_user_profile_by_email('test@zulip.com')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_register_deactivated(self):
        # type: () -> None
        """
        If you try to register for a deactivated realm, you get a clear error
        page.
        """
        realm = get_realm("zulip.com")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.register("test", "test")
        self.assert_in_response("has been deactivated", result)

        with self.assertRaises(UserProfile.DoesNotExist):
            get_user_profile_by_email('test@zulip.com')

    def test_login_deactivated(self):
        # type: () -> None
        """
        If you try to log in to a deactivated realm, you get a clear error page.
        """
        realm = get_realm("zulip.com")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.login_with_return("hamlet@zulip.com")
        self.assert_in_response("has been deactivated", result)

    def test_logout(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.client_post('/accounts/logout/')
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_non_ascii_login(self):
        # type: () -> None
        """
        You can log in even if your password contain non-ASCII characters.
        """
        email = "test@zulip.com"
        password = u"hÃ¼mbÃ¼Çµ"

        # Registering succeeds.
        self.register("test", password)
        user_profile = get_user_profile_by_email(email)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)
        self.client_post('/accounts/logout/')
        self.assertIsNone(get_session_dict_user(self.client.session))

        # Logging in succeeds.
        self.client_post('/accounts/logout/')
        self.login(email, password)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_register_first_user_with_invites(self):
        # type: () -> None
        """
        The first user in a realm has a special step in their signup workflow
        for inviting other users. Do as realistic an end-to-end test as we can
        without Tornado running.
        """
        username = "user1"
        password = "test"
        domain = "test.com"
        email = "user1@test.com"

        # Create a new realm to ensure that we're the first user in it.
        Realm.objects.create(domain=domain, name="Test Inc.")

        # Start the signup process by supplying an email address.
        result = self.client_post('/accounts/home/', {'email': email})

        # Check the redirect telling you to check your mail for a confirmation
        # link.
        self.assertEquals(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
                "/accounts/send_confirm/%s@%s" % (username, domain)))
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
            raise ValueError("Couldn't find a confirmation email.")

        result = self.client_get(confirmation_url)
        self.assertEquals(result.status_code, 200)

        # Pick a password and agree to the ToS.
        result = self.submit_reg_form_for_user(username, password, domain)
        self.assertEquals(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/invite/"))

        # Invite other users to join you.
        result = self.client_get(result["Location"])
        self.assert_in_response("You're the first one here!", result)

        # Reset the outbox for our invites.
        outbox.pop()

        invitees = ['alice@' + domain, 'bob@' + domain]
        params = {
            'invitee_emails': ujson.dumps(invitees)
        }
        result = self.client_post('/json/bulk_invite_users', params)
        self.assert_json_success(result)

        # We really did email these users, and they have PreregistrationUser
        # objects.
        email_recipients = [message.recipients()[0] for message in outbox]
        self.assertEqual(len(outbox), len(invitees))
        self.assertEqual(sorted(email_recipients), sorted(invitees))

        user_profile = get_user_profile_by_email(email)
        self.assertEqual(len(invitees), PreregistrationUser.objects.filter(
                referred_by=user_profile).count())

        # After this we start manipulating browser information, so stop here.

class InviteUserTest(AuthedTestCase):

    def invite(self, users, streams):
        # type: (str, List[text_type]) -> HttpResponse
        """
        Invites the specified users to Zulip with the specified streams.

        users should be a string containing the users to invite, comma or
            newline separated.

        streams should be a list of strings.
        """

        return self.client_post("/json/invite_users",
                {"invitee_emails": users,
                    "stream": streams})

    def check_sent_emails(self, correct_recipients):
        # type: (List[str]) -> None
        from django.core.mail import outbox
        self.assertEqual(len(outbox), len(correct_recipients))
        email_recipients = [email.recipients()[0] for email in outbox]
        self.assertEqual(sorted(email_recipients), sorted(correct_recipients))

    def test_bulk_invite_users(self):
        # type: () -> None
        """The bulk_invite_users code path is for the first user in a realm."""
        self.login('hamlet@zulip.com')
        invitees = ['alice@zulip.com', 'bob@zulip.com']
        params = {
            'invitee_emails': ujson.dumps(invitees)
        }
        result = self.client_post('/json/bulk_invite_users', params)
        self.assert_json_success(result)
        self.check_sent_emails(invitees)

    def test_successful_invite_user(self):
        # type: () -> None
        """
        A call to /json/invite_users with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet@zulip.com")
        invitee = "alice-test@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee))
        self.check_sent_emails([invitee])

    def test_successful_invite_user_with_name(self):
        # type: () -> None
        """
        A call to /json/invite_users with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet@zulip.com")
        email = "alice-test@zulip.com"
        invitee = "Alice Test <{}>".format(email)
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.check_sent_emails([email])

    def test_successful_invite_user_with_name_and_normal_one(self):
        # type: () -> None
        """
        A call to /json/invite_users with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet@zulip.com")
        email = "alice-test@zulip.com"
        email2 = "bob-test@zulip.com"
        invitee = "Alice Test <{}>, {}".format(email, email2)
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

    def test_invite_user_signup_initial_history(self):
        # type: () -> None
        """
        Test that a new user invited to a stream receives some initial
        history but only from public streams.
        """
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        private_stream_name = "Secret"
        (stream, _) = create_stream_if_needed(user_profile.realm, private_stream_name, invite_only=True)
        do_add_subscription(user_profile, stream)
        public_msg_id = self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM,
                                          "Public topic", "Public message")
        secret_msg_id = self.send_message("hamlet@zulip.com", private_stream_name, Recipient.STREAM,
                                          "Secret topic", "Secret message")
        invitee = "alice-test@zulip.com"
        self.assert_json_success(self.invite(invitee, [private_stream_name, "Denmark"]))
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user("alice-test", "password")
        invitee_profile = get_user_profile_by_email(invitee)
        invitee_msg_ids = [um.message_id for um in
                           UserMessage.objects.filter(user_profile=invitee_profile)]
        self.assertTrue(public_msg_id in invitee_msg_ids)
        self.assertFalse(secret_msg_id in invitee_msg_ids)

    def test_multi_user_invite(self):
        # type: () -> None
        """
        Invites multiple users with a variety of delimiters.
        """
        self.login("hamlet@zulip.com")
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
        self.login("hamlet@zulip.com")
        self.assert_json_error(
            self.client_post("/json/invite_users", {"invitee_emails": "foo@zulip.com"}),
            "You must specify at least one stream for invitees to join.")

        for address in ("noatsign.com", "outsideyourdomain@example.net"):
            self.assert_json_error(
                self.invite(address, ["Denmark"]),
                "Some emails did not validate, so we didn't send any invitations.")
        self.check_sent_emails([])

    def test_invalid_stream(self):
        # type: () -> None
        """
        Tests inviting to a non-existent stream.
        """
        self.login("hamlet@zulip.com")
        self.assert_json_error(self.invite("iago-test@zulip.com", ["NotARealStream"]),
                "Stream does not exist: NotARealStream. No invites were sent.")
        self.check_sent_emails([])

    def test_invite_existing_user(self):
        # type: () -> None
        """
        If you invite an address already using Zulip, no invitation is sent.
        """
        self.login("hamlet@zulip.com")
        self.assert_json_error(
            self.client_post("/json/invite_users",
                             {"invitee_emails": "hamlet@zulip.com",
                              "stream": ["Denmark"]}),
            "We weren't able to invite anyone.")
        self.assertRaises(PreregistrationUser.DoesNotExist,
                          lambda: PreregistrationUser.objects.get(
                email="hamlet@zulip.com"))
        self.check_sent_emails([])

    def test_invite_some_existing_some_new(self):
        # type: () -> None
        """
        If you invite a mix of already existing and new users, invitations are
        only sent to the new users.
        """
        self.login("hamlet@zulip.com")
        existing = ["hamlet@zulip.com", "othello@zulip.com"]
        new = ["foo-test@zulip.com", "bar-test@zulip.com"]

        result = self.client_post("/json/invite_users",
                                  {"invitee_emails": "\n".join(existing + new),
                                   "stream": ["Denmark"]})
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

    def test_invite_outside_domain_in_closed_realm(self):
        # type: () -> None
        """
        In a realm with `restricted_to_domain = True`, you can't invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = get_realm("zulip.com")
        zulip_realm.restricted_to_domain = True
        zulip_realm.save()

        self.login("hamlet@zulip.com")
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
        zulip_realm = get_realm("zulip.com")
        zulip_realm.restricted_to_domain = False
        zulip_realm.save()

        self.login("hamlet@zulip.com")
        external_address = "foo@example.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

    def test_invite_with_non_ascii_streams(self):
        # type: () -> None
        """
        Inviting someone to streams with non-ASCII characters succeeds.
        """
        self.login("hamlet@zulip.com")
        invitee = "alice-test@zulip.com"

        stream_name = u"hÃ¼mbÃ¼Çµ"
        realm = get_realm("zulip.com")
        stream, _ = create_stream_if_needed(realm, stream_name)

        # Make sure we're subscribed before inviting someone.
        do_add_subscription(
            get_user_profile_by_email("hamlet@zulip.com"),
            stream, no_log=True)

        self.assert_json_success(self.invite(invitee, [stream_name]))

class InviteeEmailsParserTests(TestCase):
    def setUp(self):
        self.email1 = "email1@zulip.com"
        self.email2 = "email2@zulip.com"
        self.email3 = "email3@zulip.com"

    def test_if_emails_separated_by_commas_are_parsed_and_striped_correctly(self):
        emails_raw = "{} ,{}, {}".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_separated_by_newlines_are_parsed_and_striped_correctly(self):
        emails_raw = "{}\n {}\n {} ".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_from_email_client_separated_by_newlines_are_parsed_correctly(self):
        emails_raw = "Email One <{}>\nEmailTwo<{}>\nEmail Three<{}>".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_in_mixed_style_are_parsed_correctly(self):
        emails_raw = "Email One <{}>,EmailTwo<{}>\n{}".format(self.email1, self.email2, self.email3)
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)


class EmailUnsubscribeTests(AuthedTestCase):
    def test_missedmessage_unsubscribe(self):
        # type: () -> None
        """
        We provide one-click unsubscribe links in missed message
        e-mails that you can click even when logged out to update your
        email notification settings.
        """
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        user_profile.enable_offline_email_notifications = True
        user_profile.save()

        unsubscribe_link = one_click_unsubscribe_link(user_profile,
                                                      "missed_messages")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

        self.assertEqual(result.status_code, 200)
        # Circumvent user_profile caching.
        user_profile = UserProfile.objects.get(email="hamlet@zulip.com")
        self.assertFalse(user_profile.enable_offline_email_notifications)

    def test_welcome_unsubscribe(self):
        # type: () -> None
        """
        We provide one-click unsubscribe links in welcome e-mails that you can
        click even when logged out to stop receiving them.
        """
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email("hamlet@zulip.com")

        # Simulate a new user signing up, which enqueues 2 welcome e-mails.
        enqueue_welcome_emails(email, "King Hamlet")
        self.assertEqual(2, len(ScheduledJob.objects.filter(
                type=ScheduledJob.EMAIL, filter_string__iexact=email)))

        # Simulate unsubscribing from the welcome e-mails.
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "welcome")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

        # The welcome email jobs are no longer scheduled.
        self.assertEqual(result.status_code, 200)
        self.assertEqual(0, len(ScheduledJob.objects.filter(
                type=ScheduledJob.EMAIL, filter_string__iexact=email)))

    def test_digest_unsubscribe(self):
        # type: () -> None
        """
        We provide one-click unsubscribe links in digest e-mails that you can
        click even when logged out to stop receiving them.

        Unsubscribing from these emails also dequeues any digest email jobs that
        have been queued.
        """
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.assertTrue(user_profile.enable_digest_emails)

        # Enqueue a fake digest email.
        send_digest_email(user_profile, "", "")
        self.assertEqual(1, len(ScheduledJob.objects.filter(
                    type=ScheduledJob.EMAIL, filter_string__iexact=email)))

        # Simulate unsubscribing from digest e-mails.
        unsubscribe_link = one_click_unsubscribe_link(user_profile, "digest")
        result = self.client_get(urllib.parse.urlparse(unsubscribe_link).path)

        # The setting is toggled off, and scheduled jobs have been removed.
        self.assertEqual(result.status_code, 200)
        # Circumvent user_profile caching.
        user_profile = UserProfile.objects.get(email="hamlet@zulip.com")
        self.assertFalse(user_profile.enable_digest_emails)
        self.assertEqual(0, len(ScheduledJob.objects.filter(
                type=ScheduledJob.EMAIL, filter_string__iexact=email)))

class RealmCreationTest(AuthedTestCase):

    def test_create_realm(self):
        # type: () -> None
        username = "user1"
        password = "test"
        domain = "test.com"
        email = "user1@test.com"

        # Make sure the realm does not exist
        self.assertIsNone(get_realm("test.com"))

        with self.settings(OPEN_REALM_CREATION=True):
            # Create new realm with the email
            result = self.client_post('/create_realm/', {'email': email})
            self.assertEquals(result.status_code, 302)
            self.assertTrue(result["Location"].endswith(
                    "/accounts/send_confirm/%s@%s" % (username, domain)))
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
                raise ValueError("Couldn't find a confirmation email.")

            result = self.client_get(confirmation_url)
            self.assertEquals(result.status_code, 200)

            result = self.submit_reg_form_for_user(username, password, domain)
            self.assertEquals(result.status_code, 302)

            # Make sure the realm is created
            realm = get_realm("test.com")

            self.assertIsNotNone(realm)
            self.assertEqual(realm.domain, domain)
            self.assertEqual(get_user_profile_by_email(email).realm, realm)

            self.assertTrue(result["Location"].endswith("/invite/"))

            result = self.client_get(result["Location"])
            self.assert_in_response("You're the first one here!", result)

class UserSignUpTest(AuthedTestCase):

    def test_user_default_language(self):
        """
        Check if the default language of new user is the default language
        of the realm.
        """
        username = "newguy"
        email = "newguy@zulip.com"
        domain = "zulip.com"
        password = "newpassword"
        realm = get_realm(domain)
        do_set_realm_default_language(realm, "de")

        result = self.client_post('/accounts/home/', {'email': email})
        self.assertEquals(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
                "/accounts/send_confirm/%s@%s" % (username, domain)))
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
            raise ValueError("Couldn't find a confirmation email.")

        result = self.client_get(confirmation_url)
        self.assertEquals(result.status_code, 200)
        # Pick a password and agree to the ToS.
        result = self.submit_reg_form_for_user(username, password, domain)
        self.assertEquals(result.status_code, 302)

        user_profile = get_user_profile_by_email(email)
        self.assertEqual(user_profile.default_language, realm.default_language)
        outbox.pop()
