# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.conf import settings
from django.test import TestCase

from zilencer.models import Deployment

from zerver.models import (
    get_realm, get_user_profile_by_email,
    PreregistrationUser, Realm, Recipient, ScheduledJob, UserProfile, UserMessage,
)

from zerver.lib.actions import (
    create_stream_if_needed,
    do_add_subscription,
    set_default_streams,
)

from zerver.lib.digest import send_digest_email
from zerver.lib.notifications import enqueue_welcome_emails, one_click_unsubscribe_link
from zerver.lib.test_helpers import AuthedTestCase, find_key_by_email, queries_captured
from zerver.lib.test_runner import slow
from zerver.lib.session_user import get_session_dict_user

import re
import ujson

from urlparse import urlparse
from six.moves import range


class PublicURLTest(TestCase):
    """
    Account creation URLs are accessible even when not logged in. Authenticated
    URLs redirect to a page.
    """

    def fetch(self, method, urls, expected_status):
        for url in urls:
            if method == "get":
                response = self.client.get(url)
            else:
                response = self.client.post(url)
            self.assertEqual(response.status_code, expected_status,
                             msg="Expected %d, received %d for %s to %s" % (
                    expected_status, response.status_code, method, url))

    def test_public_urls(self):
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
                          ],
                }
        post_urls = {200: ["/accounts/login/"],
                     302: ["/accounts/logout/"],
                     401: ["/json/get_public_streams",
                           "/json/get_old_messages",
                           "/json/update_pointer",
                           "/json/send_message",
                           "/json/invite_users",
                           "/json/settings/change",
                           "/json/subscriptions/remove",
                           "/json/subscriptions/exists",
                           "/json/subscriptions/add",
                           "/json/subscriptions/property",
                           "/json/get_subscribers",
                           "/json/fetch_api_key",
                           "/api/v1/users/me/subscriptions",
                           ],
                     400: ["/api/v1/send_message",
                           "/api/v1/external/github",
                           "/api/v1/fetch_api_key",
                           ],
                }
        for status_code, url_set in get_urls.iteritems():
            self.fetch("get", url_set, status_code)
        for status_code, url_set in post_urls.iteritems():
            self.fetch("post", url_set, status_code)

    def test_get_gcid_when_not_configured(self):
        with self.settings(GOOGLE_CLIENT_ID=None):
            resp = self.client.get("/api/v1/fetch_google_client_id")
            self.assertEquals(400, resp.status_code,
                msg="Expected 400, received %d for GET /api/v1/fetch_google_client_id" % resp.status_code,
            )
            data = ujson.loads(resp.content)
            self.assertEqual('error', data['result'])

    def test_get_gcid_when_configured(self):
        with self.settings(GOOGLE_CLIENT_ID="ABCD"):
            resp = self.client.get("/api/v1/fetch_google_client_id")
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
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_bad_password(self):
        self.login("hamlet@zulip.com", "wrongpassword")
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_login_nonexist_user(self):
        result = self.login("xxx@zulip.com", "xxx")
        self.assertIn("Please enter a correct email and password", result.content)

    def test_register(self):
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
        """
        If you try to register for a deactivated realm, you get a clear error
        page.
        """
        realm = get_realm("zulip.com")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.register("test", "test")
        self.assertIn("has been deactivated", result.content.replace("\n", " "))

        with self.assertRaises(UserProfile.DoesNotExist):
            get_user_profile_by_email('test@zulip.com')

    def test_login_deactivated(self):
        """
        If you try to log in to a deactivated realm, you get a clear error page.
        """
        realm = get_realm("zulip.com")
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        result = self.login("hamlet@zulip.com")
        self.assertIn("has been deactivated", result.content.replace("\n", " "))

    def test_logout(self):
        self.login("hamlet@zulip.com")
        self.client.post('/accounts/logout/')
        self.assertIsNone(get_session_dict_user(self.client.session))

    def test_non_ascii_login(self):
        """
        You can log in even if your password contain non-ASCII characters.
        """
        email = "test@zulip.com"
        password = u"hÃ¼mbÃ¼Çµ"

        # Registering succeeds.
        self.register("test", password)
        user_profile = get_user_profile_by_email(email)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)
        self.client.post('/accounts/logout/')
        self.assertIsNone(get_session_dict_user(self.client.session))

        # Logging in succeeds.
        self.client.post('/accounts/logout/')
        self.login(email, password)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_register_first_user_with_invites(self):
        """
        The first user in a realm has a special step in their signup workflow
        for inviting coworkers. Do as realistic an end-to-end test as we can
        without Tornado running.
        """
        username = "user1"
        password = "test"
        domain = "test.com"
        email = "user1@test.com"

        # Create a new realm to ensure that we're the first user in it.
        Realm.objects.create(domain=domain, name="Test Inc.")

        # Start the signup process by supplying an email address.
        result = self.client.post('/accounts/home/', {'email': email})

        # Check the redirect telling you to check your mail for a confirmation
        # link.
        self.assertEquals(result.status_code, 302)
        self.assertTrue(result["Location"].endswith(
                "/accounts/send_confirm/%s@%s" % (username, domain)))
        result = self.client.get(result["Location"])
        self.assertIn("Check your email so we can get started.", result.content)

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

        result = self.client.get(confirmation_url)
        self.assertEquals(result.status_code, 200)

        # Pick a password and agree to the ToS.
        result = self.submit_reg_form_for_user(username, password, domain)
        self.assertEquals(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/invite/"))

        # Invite coworkers to join you.
        result = self.client.get(result["Location"])
        self.assertIn("You're the first one here!", result.content)

        # Reset the outbox for our invites.
        outbox.pop()

        invitees = ['alice@' + domain, 'bob@' + domain]
        params = {
            'invitee_emails': ujson.dumps(invitees)
        }
        result = self.client.post('/json/bulk_invite_users', params)
        self.assert_json_success(result)

        # We really did email these users, and they have PreregistrationUser
        # objects.
        email_recipients = [message.recipients()[0] for message in outbox]
        self.assertEqual(len(outbox), len(invitees))
        self.assertItemsEqual(email_recipients, invitees)

        user_profile = get_user_profile_by_email(email)
        self.assertEqual(len(invitees), PreregistrationUser.objects.filter(
                referred_by=user_profile).count())

        # After this we start manipulating browser information, so stop here.

class InviteUserTest(AuthedTestCase):

    def invite(self, users, streams):
        """
        Invites the specified users to Zulip with the specified streams.

        users should be a string containing the users to invite, comma or
            newline separated.

        streams should be a list of strings.
        """

        return self.client.post("/json/invite_users",
                {"invitee_emails": users,
                    "stream": streams})

    def check_sent_emails(self, correct_recipients):
        from django.core.mail import outbox
        self.assertEqual(len(outbox), len(correct_recipients))
        email_recipients = [email.recipients()[0] for email in outbox]
        self.assertItemsEqual(email_recipients, correct_recipients)

    def test_bulk_invite_users(self):
        # The bulk_invite_users code path is for the first user in a realm.
        self.login('hamlet@zulip.com')
        invitees = ['alice@zulip.com', 'bob@zulip.com']
        params = {
            'invitee_emails': ujson.dumps(invitees)
        }
        result = self.client.post('/json/bulk_invite_users', params)
        self.assert_json_success(result)
        self.check_sent_emails(invitees)

    def test_successful_invite_user(self):
        """
        A call to /json/invite_users with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet@zulip.com")
        invitee = "alice-test@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee))
        self.check_sent_emails([invitee])

    def test_invite_user_signup_initial_history(self):
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
            self.assertTrue(find_key_by_email("%s-test@zulip.com" % user))
        self.check_sent_emails(["bob-test@zulip.com", "carol-test@zulip.com",
                                "dave-test@zulip.com", "earl-test@zulip.com"])

    def test_missing_or_invalid_params(self):
        """
        Tests inviting with various missing or invalid parameters.
        """
        self.login("hamlet@zulip.com")
        self.assert_json_error(
            self.client.post("/json/invite_users", {"invitee_emails": "foo@zulip.com"}),
            "You must specify at least one stream for invitees to join.")

        for address in ("noatsign.com", "outsideyourdomain@example.net"):
            self.assert_json_error(
                self.invite(address, ["Denmark"]),
                "Some emails did not validate, so we didn't send any invitations.")
        self.check_sent_emails([])

    def test_invalid_stream(self):
        """
        Tests inviting to a non-existent stream.
        """
        self.login("hamlet@zulip.com")
        self.assert_json_error(self.invite("iago-test@zulip.com", ["NotARealStream"]),
                "Stream does not exist: NotARealStream. No invites were sent.")
        self.check_sent_emails([])

    def test_invite_existing_user(self):
        """
        If you invite an address already using Zulip, no invitation is sent.
        """
        self.login("hamlet@zulip.com")
        self.assert_json_error(
            self.client.post("/json/invite_users",
                             {"invitee_emails": "hamlet@zulip.com",
                              "stream": ["Denmark"]}),
            "We weren't able to invite anyone.")
        self.assertRaises(PreregistrationUser.DoesNotExist,
                          lambda: PreregistrationUser.objects.get(
                email="hamlet@zulip.com"))
        self.check_sent_emails([])

    def test_invite_some_existing_some_new(self):
        """
        If you invite a mix of already existing and new users, invitations are
        only sent to the new users.
        """
        self.login("hamlet@zulip.com")
        existing = ["hamlet@zulip.com", "othello@zulip.com"]
        new = ["foo-test@zulip.com", "bar-test@zulip.com"]

        result = self.client.post("/json/invite_users",
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

    @slow(0.20, 'inviting is slow')
    def test_invite_outside_domain_in_open_realm(self):
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

class EmailUnsubscribeTests(AuthedTestCase):
    def test_missedmessage_unsubscribe(self):
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
        result = self.client.get(urlparse(unsubscribe_link).path)

        self.assertEqual(result.status_code, 200)
        # Circumvent user_profile caching.
        user_profile = UserProfile.objects.get(email="hamlet@zulip.com")
        self.assertFalse(user_profile.enable_offline_email_notifications)

    def test_welcome_unsubscribe(self):
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
        result = self.client.get(urlparse(unsubscribe_link).path)

        # The welcome email jobs are no longer scheduled.
        self.assertEqual(result.status_code, 200)
        self.assertEqual(0, len(ScheduledJob.objects.filter(
                type=ScheduledJob.EMAIL, filter_string__iexact=email)))

    def test_digest_unsubscribe(self):
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
        result = self.client.get(urlparse(unsubscribe_link).path)

        # The setting is toggled off, and scheduled jobs have been removed.
        self.assertEqual(result.status_code, 200)
        # Circumvent user_profile caching.
        user_profile = UserProfile.objects.get(email="hamlet@zulip.com")
        self.assertFalse(user_profile.enable_digest_emails)
        self.assertEqual(0, len(ScheduledJob.objects.filter(
                type=ScheduledJob.EMAIL, filter_string__iexact=email)))

