#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template import loader, TemplateDoesNotExist

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
        'realm_uri': realm.uri,
        'server_uri': settings.SERVER_URI,
        'old_email': 'old_address@acme.com',
        'new_email': 'new_address@acme.com',
        'activate_url': '%s/accounts/do_confirm/5348720e4af7d2e8f296cbbd04d439489917ddc0' % (settings.SERVER_URI,),
        'support_email': 'support@' + settings.EXTERNAL_HOST,
        'zulip_support': 'support@' + settings.EXTERNAL_HOST,
        'unsubscribe_link': '%s/accounts/unsubscribe/<type>/cf88931365ef1b0f12eae8d488bbc7af3563d7f0' % (settings.SERVER_URI,),
    }

    # Do not render these templates,
    # as they are currently unsupported
    ignore = [
        'digest',
        'missed_message',
        'password_reset',
    ]

    files = os.listdir(os.path.join(ZULIP_PATH, 'templates', 'zerver', 'emails'))
    templates = []  # type: List[str]
    data = []  # type: List[Dict[str, Any]]

    for f in files:
        template = f.split('.')[0]
        if template not in templates and template not in ignore:
            templates.append(template)
            try:
                data.append(render_email(template, test_context))
            except Exception as e:  # nocoverage
                data.append({'template': template, 'failed': True, 'reason': e})
    return render(request, 'zerver/test_emails.html', {'emails': data})

def render_email(template_prefix, context):
    # type: (str, Dict[str, Any]) -> Dict[str, Any]
    email = {}  # type: Dict[str, Any]
    email['template'] = template_prefix
    email['subject'] = loader.render_to_string('zerver/emails/' + template_prefix + '.subject', context).strip()
    message = loader.render_to_string('zerver/emails/' + template_prefix + '.txt', context)

    try:
        html_message = loader.render_to_string('/zerver/emails/' + template_prefix + '.html', context)
    except TemplateDoesNotExist:
        html_message = None

    if html_message is not None:
        email['body'] = html_message
        email['text'] = False
    else:
        email['body'] = message
        email['text'] = True

    return email
