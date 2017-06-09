#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import os
from typing import List, Dict, Any
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template import loader, TemplateDoesNotExist

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../')

def email_page(request):
    # type: (HttpRequest) -> HttpResponse
    # write fake data for all variables
    test_context = {
        'user_profile': {
            'full_name': 'Zooly Zulipson',
            'email': 'zooly@zulip.org',
            'realm': {
                'uri': 'https://chat.zulip.org',
                'name': 'Zulip Community',
            },
        },
        'realm': {
            'uri': 'https://chat.zulip.org',
            'name': 'Zulip Community',
        },
        'device_info': {
            'login_time': "12/12/12, 12:12:12",
            'device_browser': "Firefox",
            'device_os': "ZulipOS",
            'device_ip': '127.0.0.1',
        },
        'referrer': {
            'full_name': 'Zooly Zulipson',
            'email': 'zooly@zulip.org',
        },
        'user': {
            'full_name': 'Zooly Zulipson',
            'email': 'zooly@zulip.org',
        },
        'referrer_name': 'Zooly Zulipson',
        'referrer_email': 'Zooly Zulipson',
        'realm_uri': 'https://chat.zulip.org',
        'server_uri': 'https://chat.zulip.org',
        'old_email': 'oldmail@zulip.org',
        'new_email': 'newmail@zulip.org',
        'activate_url': 'https://test.zulip.org',
        'support_email': 'admin@zulip.org',
        'zulip_support': 'admin@zulip.org',
        'unsubscribe_link': 'https://unsub.zulip.org',
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
