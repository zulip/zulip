
import argparse
from datetime import datetime
from typing import Any

import requests
import ujson
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from zerver.models import UserProfile

class Command(BaseCommand):
    help = """Add users to a MailChimp mailing list."""

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument('--api-key',
                            dest='api_key',
                            type=str,
                            help='MailChimp API key.')
        parser.add_argument('--list-id',
                            dest='list_id',
                            type=str,
                            help='List ID of the MailChimp mailing list.')
        parser.add_argument('--optin-time',
                            dest='optin_time',
                            type=str,
                            default=datetime.isoformat(timezone_now().replace(microsecond=0)),
                            help='Opt-in time of the users.')

    def handle(self, *args: Any, **options: str) -> None:
        if options['api_key'] is None:
            try:
                if settings.MAILCHIMP_API_KEY is None:
                    print('MAILCHIMP_API_KEY is None. Check your server settings file.')
                    exit(1)
                options['api_key'] = settings.MAILCHIMP_API_KEY
            except AttributeError:
                print('Please supply a MailChimp API key to --api-key, or add a '
                      'MAILCHIMP_API_KEY to your server settings file.')
                exit(1)

        if options['list_id'] is None:
            try:
                if settings.ZULIP_FRIENDS_LIST_ID is None:
                    print('ZULIP_FRIENDS_LIST_ID is None. Check your server settings file.')
                    exit(1)
                options['list_id'] = settings.ZULIP_FRIENDS_LIST_ID
            except AttributeError:
                print('Please supply a MailChimp List ID to --list-id, or add a '
                      'ZULIP_FRIENDS_LIST_ID to your server settings file.')
                exit(1)

        endpoint = "https://%s.api.mailchimp.com/3.0/lists/%s/members" % \
                   (options['api_key'].split('-')[1], options['list_id'])

        for user in UserProfile.objects.filter(is_bot=False, is_active=True) \
                                       .values('email', 'full_name', 'realm_id'):
            data = {
                'email_address': user['email'],
                'list_id': options['list_id'],
                'status': 'subscribed',
                'merge_fields': {
                    'NAME': user['full_name'],
                    'REALM_ID': user['realm_id'],
                    'OPTIN_TIME': options['optin_time'],
                },
            }
            r = requests.post(endpoint, auth=('apikey', options['api_key']), json=data, timeout=10)
            if r.status_code == 400 and ujson.loads(r.text)['title'] == 'Member Exists':
                print("%s is already a part of the list." % (data['email_address'],))
            elif r.status_code >= 400:
                print(r.text)
