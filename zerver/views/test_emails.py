#!/usr/bin/env python3
from __future__ import absolute_import
from __future__ import print_function

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template import loader, TemplateDoesNotExist

from zerver.lib.send_email import build_email
from zerver.models import get_realm

import os
from typing import List, Dict, Any

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../')

def email_page(request):
    # type: (HttpRequest) -> HttpResponse
    # write fake data for all variables
    realm = get_realm('zulip')
    test_context = {
        'user_profile': {
            'full_name': 'Wile E. Coyote',
            'email': 'coyote@acme.com',
            'realm': {
                'uri': realm.uri,
                'name': 'Acme Corporation',
            },
        },
        'realm': {
            'uri': realm.uri,
            'name': 'Acme Corporation',
        },
        'device_info': {
            'login_time': "12/12/12, 12:12:12",
            'device_browser': "Firefox",
            'device_os': "ZulipOS",
            'device_ip': '3.14.15.92',
        },
        'referrer': {
            'full_name': 'Road Runner',
            'email': 'runner@acme.com',
        },
        'user': {
            'full_name': 'Wile E. Coyote',
            'email': 'coyote@acme.com',
        },
        'referrer_name': 'Road Runner',
        'referrer_email': 'runner@acme.com',
        'referrer_realm_name': 'Acme Corporation',
        'realm_uri': realm.uri,
        'root_domain_uri': settings.ROOT_DOMAIN_URI,
        'old_email': 'old_address@acme.com',
        'new_email': 'new_address@acme.com',
        'is_realm_admin': True,
        'activate_url': '%s/accounts/do_confirm/5348720e4af7d2e8f296cbbd04d439489917ddc0' % (settings.ROOT_DOMAIN_URI,),
        'unsubscribe_link': '%s/accounts/unsubscribe/<type>/cf88931365ef1b0f12eae8d488bbc7af3563d7f0' % (settings.ROOT_DOMAIN_URI,),
        'organization_setup_advice_link': '%s/help/getting-your-organization-started-with-zulip' % (settings.ROOT_DOMAIN_URI,),
    }

    templates = [
        'confirm_registration', 'invitation', 'invitation_reminder', 'followup_day1',
        'followup_day2', 'missed_message', 'digest', 'find_team', 'password_reset',
        'confirm_new_email', 'notify_change_in_email', 'notify_new_login']

    for f in os.listdir(os.path.join(ZULIP_PATH, 'templates', 'zerver', 'emails')):
        template = f.split('.')[0]
        if template not in templates:
            templates.append(template)

    # Do not render these templates,
    # as they are currently unsupported
    ignore = [
        'email_base_default',
        'email_base_messages',
        'digest',
        'missed_message',
        'password_reset',
    ]

    data = []  # type: List[Dict[str, Any]]
    for template in templates:
        if template not in ignore:
            try:
                email = build_email('zerver/emails/' + template, to_email='recipient@acme.com',
                                    context=test_context)
                email_data = {
                    'template': template,
                    'subject': email.subject,
                    'body': email.body,
                    'html_message': email.alternatives[0][0] if len(email.alternatives) > 0 else 'Missing HTML message'}
                data.append(email_data)
            except Exception as e:  # nocoverage
                data.append({'template': template, 'failed': True, 'reason': e})
    return render(request, 'zerver/test_emails.html', {'emails': data})
