# -*- coding: utf-8 -*-
from __future__ import absolute_import

import datetime
from typing import Any

import django
import mock
from django.conf import settings
from django.core import mail
from django.http import HttpResponse
from django.urls import reverse
from django.utils.timezone import now

from confirmation.models import EmailChangeConfirmation, generate_key
from zerver.lib.actions import do_start_email_change_process, do_set_realm_property
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import get_user_profile_by_email, EmailChangeStatus, Realm


class EmailChangeTestCase(ZulipTestCase):
    def test_confirm_email_change_with_non_existent_key(self):
        # type: () -> None
        self.login('hamlet@zulip.com')
        key = generate_key()
        with self.assertRaises(EmailChangeConfirmation.DoesNotExist):
            url = EmailChangeConfirmation.objects.get_activation_url(key)

        url = EmailChangeConfirmation.objects.get_activation_url(
            key, 'testserver')
        response = self.client_get(url)
        self.assert_in_success_response(["Whoops"], response)

    def test_confirm_email_change_with_invalid_key(self):
        # type: () -> None
        self.login('hamlet@zulip.com')
        key = 'invalid key'
        with self.assertRaises(EmailChangeConfirmation.DoesNotExist):
            url = EmailChangeConfirmation.objects.get_activation_url(key)

        url = EmailChangeConfirmation.objects.get_activation_url(
            key, 'testserver')
        response = self.client_get(url)
        self.assert_in_success_response(["Whoops"], response)

    def test_email_change_when_not_logging_in(self):
        # type: () -> None
        key = generate_key()
        with self.assertRaises(EmailChangeConfirmation.DoesNotExist):
            url = EmailChangeConfirmation.objects.get_activation_url(key)

        url = EmailChangeConfirmation.objects.get_activation_url(
            key, 'testserver')
        response = self.client_get(url)
        self.assertEqual(response.status_code, 302)

    def test_confirm_email_change_when_time_exceeded(self):
        # type: () -> None
        old_email = 'hamlet@zulip.com'
        new_email = 'hamlet-new@zulip.com'
        self.login('hamlet@zulip.com')
        user_profile = get_user_profile_by_email(old_email)
        obj = EmailChangeStatus.objects.create(new_email=new_email,
                                               old_email=old_email,
                                               user_profile=user_profile,
                                               realm=user_profile.realm)
        key = generate_key()
        date_sent = now() - datetime.timedelta(days=2)
        EmailChangeConfirmation.objects.create(content_object=obj,
                                               date_sent=date_sent,
                                               confirmation_key=key)
        url = EmailChangeConfirmation.objects.get_activation_url(key)
        response = self.client_get(url)
        self.assert_in_success_response(["Whoops"], response)

    def test_confirm_email_change(self):
        # type: () -> None
        old_email = 'hamlet@zulip.com'
        new_email = 'hamlet-new@zulip.com'
        self.login('hamlet@zulip.com')
        user_profile = get_user_profile_by_email(old_email)
        obj = EmailChangeStatus.objects.create(new_email=new_email,
                                               old_email=old_email,
                                               user_profile=user_profile,
                                               realm=user_profile.realm)
        key = generate_key()
        EmailChangeConfirmation.objects.create(content_object=obj,
                                               date_sent=now(),
                                               confirmation_key=key)
        url = EmailChangeConfirmation.objects.get_activation_url(key)
        response = self.client_get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_in_success_response(["This confirms that the email address for your Zulip"],
                                        response)
        user_profile = get_user_profile_by_email(new_email)
        self.assertTrue(bool(user_profile))
        obj.refresh_from_db()
        self.assertEqual(obj.status, 1)

    def test_start_email_change_process(self):
        # type: () -> None
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        do_start_email_change_process(user_profile, 'hamlet-new@zulip.com')
        self.assertEqual(EmailChangeStatus.objects.count(), 1)

    def test_end_to_end_flow(self):
        # type: () -> None
        data = {'email': 'hamlet-new@zulip.com'}
        email = 'hamlet@zulip.com'
        self.login(email)
        url = '/json/settings/change'
        self.assertEqual(len(mail.outbox), 0)
        result = self.client_post(url, data)
        self.assertEqual(len(mail.outbox), 1)
        self.assert_in_success_response(['We have sent you an email'], result)
        email_message = mail.outbox[0]
        self.assertEqual(
            email_message.subject,
            '[Zulip] Confirm your new email address for Zulip Dev'
        )
        body = email_message.body
        self.assertIn('We received a request to change the email', body)

        activation_url = [s for s in body.split('\n') if s][4]
        response = self.client_get(activation_url)

        self.assert_in_success_response(["This confirms that the email address"],
                                        response)

    def test_unauthorized_email_change(self):
        # type: () -> None
        data = {'email': 'hamlet-new@zulip.com'}
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        do_set_realm_property(user_profile.realm, 'email_changes_disabled', True)
        url = '/json/settings/change'
        result = self.client_post(url, data)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(result.status_code, 400)
        self.assert_in_response("Email address changes are disabled in this organization.",
                                result)

    def test_unauthorized_email_change_from_email_confirmation_link(self):
        # type: () -> None
        data = {'email': 'hamlet-new@zulip.com'}
        email = 'hamlet@zulip.com'
        self.login(email)
        url = '/json/settings/change'
        self.assertEqual(len(mail.outbox), 0)
        result = self.client_post(url, data)
        self.assertEqual(len(mail.outbox), 1)
        self.assert_in_success_response(['We have sent you an email'], result)
        email_message = mail.outbox[0]
        self.assertEqual(
            email_message.subject,
            '[Zulip] Confirm your new email address for Zulip Dev'
        )
        body = email_message.body
        self.assertIn('We received a request to change the email', body)

        user_profile = get_user_profile_by_email(email)
        do_set_realm_property(user_profile.realm, 'email_changes_disabled', True)

        activation_url = [s for s in body.split('\n') if s][4]
        response = self.client_get(activation_url)

        self.assertEqual(response.status_code, 400)
        self.assert_in_response("Email address changes are disabled in this organization.",
                                response)

    def test_post_invalid_email(self):
        # type: () -> None
        data = {'email': 'hamlet-new'}
        email = 'hamlet@zulip.com'
        self.login(email)
        url = '/json/settings/change'
        result = self.client_post(url, data)
        self.assert_in_response('Invalid address', result)

    def test_post_same_email(self):
        # type: () -> None
        data = {'email': 'hamlet@zulip.com'}
        email = 'hamlet@zulip.com'
        self.login(email)
        url = '/json/settings/change'
        result = self.client_post(url, data)
        self.assertEqual('success', result.json()['result'])
        self.assertEqual('', result.json()['msg'])
