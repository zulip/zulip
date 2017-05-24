from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand

from zerver.lib.actions import do_rename_stream
from zerver.lib.str_utils import force_text
from zerver.models import Realm, Service, UserProfile, get_realm

import sys

class Command(BaseCommand):
    help = """Given an existing bot, converts it into an outgoing webhook bot."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('string_id', metavar='<string_id>', type=str,
                            help='subdomain or string_id of bot')
        parser.add_argument('bot_email', metavar='<bot_email>', type=str,
                            help='email of bot')
        parser.add_argument('service_name', metavar='<service_name>', type=str,
                            help='name of Service object to create')
        parser.add_argument('base_url', metavar='<base_url>', type=str,
                            help='base url of outgoing webhook')
        # TODO: Add token and interface as arguments once OutgoingWebhookWorker
        # uses these fields on the Service object.

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None

        string_id = options['string_id']
        bot_email = options['bot_email']
        service_name = options['service_name']
        base_url = options['base_url']

        encoding = sys.getfilesystemencoding()
        realm = get_realm(force_text(string_id, encoding))
        if realm is None:
            print('Unknown subdomain or string_id %s' % (string_id,))
            exit(1)

        if not bot_email:
            print('Email of existing bot must be provided')
            exit(1)

        if not service_name:
            print('Name for Service object must be provided')
            exit(1)

        if not base_url:
            print('Base URL of outgoing webhook must be provided')
            exit(1)

        # TODO: Normalize email?
        bot_profile = UserProfile.objects.get(email=bot_email)
        if not bot_profile:
            print('User %s does not exist' % (bot_email,))
            exit(1)
        if not bot_profile.is_bot:
            print('User %s is not a bot' % (bot_email,))
            exit(1)
        if bot_profile.is_outgoing_webhook_bot:
            print('%s is already marked as an outgoing webhook bot' % (bot_email,))
            exit(1)

        Service.objects.create(name=service_name,
                               user_profile=bot_profile,
                               base_url=base_url,
                               token='',
                               interface=1)

        bot_profile.bot_type = UserProfile.OUTGOING_WEBHOOK_BOT
        bot_profile.save()

        print('Successfully converted %s into an outgoing webhook bot' % (bot_email,))
