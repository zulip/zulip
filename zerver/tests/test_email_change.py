# -*- coding: utf-8 -*-

import datetime
from email.utils import parseaddr
import re

from django.core import mail
from django.utils.timezone import now

from confirmation.models import Confirmation, generate_key, confirmation_url
from zerver.lib.actions import do_start_email_change_process, do_set_realm_property
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import get_user_by_delivery_email, EmailChangeStatus, get_realm, \
    Realm, UserProfile, get_user, get_user_profile_by_id


class EmailChangeTestCase(ZulipTestCase):
    def test_confirm_email_change_with_non_existent_key(self) -> None:
        self.login(self.example_email("hamlet"))
        key = generate_key()
        url = confirmation_url(key, 'testserver', Confirmation.EMAIL_CHANGE)
        response = self.client_get(url)
        self.assert_in_success_response(["Whoops. We couldn't find your confirmation link in the system."], response)

    def test_confirm_email_change_with_invalid_key(self) -> None:
        self.login(self.example_email("hamlet"))
        key = 'invalid key'
        url = confirmation_url(key, 'testserver', Confirmation.EMAIL_CHANGE)
        response = self.client_get(url)
        self.assert_in_success_response(["Whoops. The confirmation link is malformed."], response)

    def test_confirm_email_change_when_time_exceeded(self) -> None:
        user_profile = self.example_user('hamlet')
        old_email = user_profile.email
        new_email = 'hamlet-new@zulip.com'
        self.login(self.example_email("hamlet"))
        obj = EmailChangeStatus.objects.create(new_email=new_email,
                                               old_email=old_email,
                                               user_profile=user_profile,
                                               realm=user_profile.realm)
        key = generate_key()
        date_sent = now() - datetime.timedelta(days=2)
        Confirmation.objects.create(content_object=obj,
                                    date_sent=date_sent,
                                    confirmation_key=key,
                                    type=Confirmation.EMAIL_CHANGE)
        url = confirmation_url(key, user_profile.realm.host, Confirmation.EMAIL_CHANGE)
        response = self.client_get(url)
        self.assert_in_success_response(["The confirmation link has expired or been deactivated."], response)

    def test_confirm_email_change(self) -> None:
        user_profile = self.example_user('hamlet')
        old_email = user_profile.email
        new_email = 'hamlet-new@zulip.com'
        new_realm = get_realm('zulip')
        self.login(self.example_email('hamlet'))
        obj = EmailChangeStatus.objects.create(new_email=new_email,
                                               old_email=old_email,
                                               user_profile=user_profile,
                                               realm=user_profile.realm)
        key = generate_key()
        Confirmation.objects.create(content_object=obj,
                                    date_sent=now(),
                                    confirmation_key=key,
                                    type=Confirmation.EMAIL_CHANGE)
        url = confirmation_url(key, user_profile.realm.host, Confirmation.EMAIL_CHANGE)
        response = self.client_get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_in_success_response(["This confirms that the email address for your Zulip"],
                                        response)
        user_profile = get_user_by_delivery_email(new_email, new_realm)
        self.assertTrue(bool(user_profile))
        obj.refresh_from_db()
        self.assertEqual(obj.status, 1)

    def test_start_email_change_process(self) -> None:
        user_profile = self.example_user('hamlet')
        do_start_email_change_process(user_profile, 'hamlet-new@zulip.com')
        self.assertEqual(EmailChangeStatus.objects.count(), 1)

    def test_end_to_end_flow(self) -> None:
        data = {'email': 'hamlet-new@zulip.com'}
        email = self.example_email("hamlet")
        self.login(email)
        url = '/json/settings'
        self.assertEqual(len(mail.outbox), 0)
        result = self.client_patch(url, data)
        self.assertEqual(len(mail.outbox), 1)
        self.assert_in_success_response(['Check your email for a confirmation link.'], result)
        email_message = mail.outbox[0]
        self.assertEqual(
            email_message.subject,
            'Verify your new email address'
        )
        body = email_message.body
        from_email = email_message.from_email
        self.assertIn('We received a request to change the email', body)
        self.assertIn('Zulip Account Security', from_email)
        tokenized_no_reply_email = parseaddr(email_message.from_email)[1]
        self.assertTrue(re.search(self.TOKENIZED_NOREPLY_REGEX, tokenized_no_reply_email))

        activation_url = [s for s in body.split('\n') if s][2]
        response = self.client_get(activation_url)

        self.assert_in_success_response(["This confirms that the email address"],
                                        response)

        # Now confirm trying to change your email back doesn't throw an immediate error
        result = self.client_patch(url, {"email": "hamlet@zulip.com"})
        self.assert_in_success_response(['Check your email for a confirmation link.'], result)

    def test_unauthorized_email_change(self) -> None:
        data = {'email': 'hamlet-new@zulip.com'}
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        do_set_realm_property(user_profile.realm, 'email_changes_disabled', True)
        url = '/json/settings'
        result = self.client_patch(url, data)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(result.status_code, 400)
        self.assert_in_response("Email address changes are disabled in this organization.",
                                result)
        # Realm admins can change their email address even setting is disabled.
        data = {'email': 'iago-new@zulip.com'}
        self.login(self.example_email("iago"))
        url = '/json/settings'
        result = self.client_patch(url, data)
        self.assert_in_success_response(['Check your email for a confirmation link.'], result)

    def test_email_change_already_taken(self) -> None:
        data = {'email': 'cordelia@zulip.com'}
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)

        url = '/json/settings'
        result = self.client_patch(url, data)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(result.status_code, 400)
        self.assert_in_response("Already has an account",
                                result)

    def test_unauthorized_email_change_from_email_confirmation_link(self) -> None:
        data = {'email': 'hamlet-new@zulip.com'}
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        url = '/json/settings'
        self.assertEqual(len(mail.outbox), 0)
        result = self.client_patch(url, data)
        self.assertEqual(len(mail.outbox), 1)
        self.assert_in_success_response(['Check your email for a confirmation link.'], result)
        email_message = mail.outbox[0]
        self.assertEqual(
            email_message.subject,
            'Verify your new email address'
        )
        body = email_message.body
        self.assertIn('We received a request to change the email', body)

        do_set_realm_property(user_profile.realm, 'email_changes_disabled', True)

        activation_url = [s for s in body.split('\n') if s][2]
        response = self.client_get(activation_url)

        self.assertEqual(response.status_code, 400)
        self.assert_in_response("Email address changes are disabled in this organization.",
                                response)

    def test_post_invalid_email(self) -> None:
        data = {'email': 'hamlet-new'}
        email = self.example_email("hamlet")
        self.login(email)
        url = '/json/settings'
        result = self.client_patch(url, data)
        self.assert_in_response('Invalid address', result)

    def test_post_same_email(self) -> None:
        data = {'email': self.example_email("hamlet")}
        email = self.example_email("hamlet")
        self.login(email)
        url = '/json/settings'
        result = self.client_patch(url, data)
        self.assertEqual('success', result.json()['result'])
        self.assertEqual('', result.json()['msg'])

    def test_change_delivery_email_end_to_end_with_admins_visibility(self) -> None:
        user_profile = self.example_user('hamlet')
        do_set_realm_property(user_profile.realm, 'email_address_visibility',
                              Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS)

        old_email = user_profile.email
        new_email = 'hamlet-new@zulip.com'
        self.login(self.example_email('hamlet'))
        obj = EmailChangeStatus.objects.create(new_email=new_email,
                                               old_email=old_email,
                                               user_profile=user_profile,
                                               realm=user_profile.realm)
        key = generate_key()
        Confirmation.objects.create(content_object=obj,
                                    date_sent=now(),
                                    confirmation_key=key,
                                    type=Confirmation.EMAIL_CHANGE)
        url = confirmation_url(key, user_profile.realm.host, Confirmation.EMAIL_CHANGE)
        response = self.client_get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_in_success_response(["This confirms that the email address for your Zulip"],
                                        response)
        user_profile = get_user_profile_by_id(user_profile.id)
        self.assertEqual(user_profile.delivery_email, new_email)
        self.assertEqual(user_profile.email, "user4@zulip.testserver")
        obj.refresh_from_db()
        self.assertEqual(obj.status, 1)
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user(old_email, user_profile.realm)
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user_by_delivery_email(old_email, user_profile.realm)
        self.assertEqual(get_user_by_delivery_email(new_email, user_profile.realm), user_profile)
