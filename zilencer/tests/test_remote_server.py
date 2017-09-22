# -*- coding: utf-8 -*-
from __future__ import absolute_import

import uuid
import mock
from django.conf import settings
from django.core import mail
from django.urls import reverse
from django.utils.timezone import now

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from confirmation.models import Confirmation, generate_key, confirmation_url, \
    create_confirmation_link
from zilencer.models import RemoteServerRegistrationStatus, RemoteZulipServer

class ConfirmTestCase(ZulipTestCase):
    def test_non_existing_key(self):
        # type: () -> None
        key = generate_key()
        url = confirmation_url(key, 'testserver', Confirmation.SERVER_REGISTRATION)
        response = self.client_get(url)
        self.assert_in_success_response(
            ["Whoops", settings.ZULIP_ADMINISTRATOR], response)

    def test_confirm(self):
        # type: () -> None
        email = self.example_email('hamlet')
        obj = RemoteServerRegistrationStatus.objects.create(email=email)
        url = create_confirmation_link(obj, 'acme.com',
                                       Confirmation.SERVER_REGISTRATION)
        data = {
            'hostname': 'https://acme.com',
            'zulip_org_id': str(uuid.uuid1()),
            'zulip_org_key': '1234',
            'terms': 'true',
        }
        response = self.client_post(url, info=data)
        self.assert_in_success_response(
            ["Your remote server, https://acme.com, has successfully registered"],
            response
        )

class RegisterRemoteServerTestCase(ZulipTestCase):
    def test_register_remote_server(self):
        # type: () -> None
        url = reverse('zilencer.views.register_remote_server')
        response = self.client_get(url)
        self.assert_in_success_response(["Register remote server"], response)

class RemoteServerTestCase(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.uuid = str(uuid.uuid1())

    def test_end_to_end_flow(self):
        # type: () -> None
        self.assertEqual(len(mail.outbox), 0)
        url = reverse('zilencer.views.register_remote_server')
        data = {
            'email': 'hamlet-new@zulip.com',
        }
        result = self.client_post(url, data)
        self.assertEqual(result.status_code, 302)  # send the email
        result = self.client_get(result.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assert_in_success_response(
            ['Check your email for a verification link.'], result)
        email_message = mail.outbox[0]
        self.assertEqual(
            email_message.subject,
            '[Zulip] Confirm your remote server registration'
        )
        body = email_message.body
        self.assertIn('We received a request to register a remote server', body)

        activation_url = [s for s in body.split('\n') if s][3]
        activation_url = activation_url.strip().strip('<').strip('>')
        response = self.client_get(activation_url)
        self.assertEqual(response.status_code, 200)
        data = {
            'hostname': 'https://acme.com',
            'zulip_org_id': self.uuid,
            'zulip_org_key': '1234',
            'terms': 'true',
        }
        response = self.client_post(activation_url, info=data)
        self.assert_in_success_response(
            ["Your remote server, https://acme.com, has successfully registered"],
            response)

    def test_zulip_org_id_exists(self):
        # type: () -> None
        email = self.example_email('hamlet')
        RemoteZulipServer.objects.create(uuid=self.uuid,
                                         api_key='1234',
                                         hostname='https://acme.com',
                                         contact_email=email)

        status_obj = RemoteServerRegistrationStatus.objects.create(email=email)
        activation_url = create_confirmation_link(status_obj,
                                                  'acme.com',
                                                  Confirmation.SERVER_REGISTRATION)
        data = {
            'email': 'hamlet-new@zulip.com',
            'hostname': 'https://acme.com',
            'zulip_org_id': self.uuid,
            'zulip_org_key': '1234',
            'terms': 'true',
        }
        response = self.client_post(activation_url, data)
        self.assert_in_success_response(
            ["Zulip organization id already exists.",
             "https://acme.com has already been registered."],
            response)

    def test_invalid_uuid(self):
        # type: () -> None
        email = self.example_email('hamlet')
        status_obj = RemoteServerRegistrationStatus.objects.create(email=email)
        activation_url = create_confirmation_link(status_obj,
                                                  'acme.com',
                                                  Confirmation.SERVER_REGISTRATION)
        data = {
            'email': 'hamlet-new@zulip.com',
            'hostname': 'https://acme.com',
            'zulip_org_id': '1234',
            'zulip_org_key': '1234',
            'terms': 'true',
        }
        response = self.client_post(activation_url, info=data)
        self.assert_in_success_response(
            ["Enter a valid UUID."],
            response)
