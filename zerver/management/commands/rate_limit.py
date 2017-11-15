
from argparse import ArgumentParser
from typing import Any

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.rate_limiter import RateLimitedUser, \
    block_access, unblock_access
from zerver.models import UserProfile, get_user_profile_by_api_key

class Command(ZulipBaseCommand):
    help = """Manually block or unblock a user from accessing the API"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('-e', '--email',
                            dest='email',
                            help="Email account of user.")
        parser.add_argument('-a', '--api-key',
                            dest='api_key',
                            help="API key of user.")
        parser.add_argument('-s', '--seconds',
                            dest='seconds',
                            default=60,
                            type=int,
                            help="Seconds to block for.")
        parser.add_argument('-d', '--domain',
                            dest='domain',
                            default='all',
                            help="Rate-limiting domain. Defaults to 'all'.")
        parser.add_argument('-b', '--all-bots',
                            dest='bots',
                            action='store_true',
                            default=False,
                            help="Whether or not to also block all bots for this user.")
        parser.add_argument('operation', metavar='<operation>', type=str, choices=['block', 'unblock'],
                            help="operation to perform (block or unblock)")
        self.add_realm_args(parser)

    def handle(self, *args: Any, **options: Any) -> None:
        if (not options['api_key'] and not options['email']) or \
           (options['api_key'] and options['email']):
            print("Please enter either an email or API key to manage")
            exit(1)

        realm = self.get_realm(options)
        if options['email']:
            user_profile = self.get_user(options['email'], realm)
        else:
            try:
                user_profile = get_user_profile_by_api_key(options['api_key'])
            except UserProfile.DoesNotExist:
                print("Unable to get user profile for api key %s" % (options['api_key'],))
                exit(1)

        users = [user_profile]
        if options['bots']:
            users.extend(bot for bot in UserProfile.objects.filter(is_bot=True,
                                                                   bot_owner=user_profile))

        operation = options['operation']
        for user in users:
            print("Applying operation to User ID: %s: %s" % (user.id, operation))

            if operation == 'block':
                block_access(RateLimitedUser(user, domain=options['domain']),
                             options['seconds'])
            elif operation == 'unblock':
                unblock_access(RateLimitedUser(user, domain=options['domain']))
