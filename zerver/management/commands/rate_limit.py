from __future__ import absolute_import

from zerver.models import UserProfile, get_user_profile_by_email
from zerver.lib.rate_limiter import block_user, unblock_user

from django.core.management.base import BaseCommand
from optparse import make_option

class Command(BaseCommand):
    help = """Manually block or unblock a user from accessing the API

    Usage: ./manage.py rate_limit [--all-bots] [--domain all] [--seconds 60] [--api-key bf4sds] [--email f@b.com] block/unblock"""

    option_list = BaseCommand.option_list + (
        make_option('-e', '--email',
                    dest='email',
                    help="Email account of user."),
        make_option('-a', '--api-key',
                    dest='api_key',
                    help="API key of user."),
        make_option('-s', '--seconds',
                    dest='seconds',
                    default=60,
                    type=int,
                    help="Seconds to block for."),
        make_option('-d', '--domain',
                    dest='domain',
                    default='all',
                    help="Rate-limiting domain. Defaults to 'all'."),
        make_option('-b', '--all-bots',
                    dest='bots',
                    action='store_true',
                    default=False,
                    help="Whether or not to also block all bots for this user."),
        )

    def handle(self, *args, **options):
        if len(args) == 0 or args[0] not in ('block', 'unblock'):
            print "Please pass either 'block' or 'unblock"
            exit(1)

        if (not options['api_key'] and not options['email']) or \
           (options['api_key'] and options['email']):
            print "Please enter either an email or API key to manage"
            exit(1)

        if options['email']:
            user_profile = get_user_profile_by_email(options['email'])
        else:
            try:
                user_profile = UserProfile.objects.get(api_key=options['api_key'])
            except:
                print "Unable to get user profile for api key %s" % (options['api_key'], )
                exit(1)

        users = [user_profile]
        if options['bots']:
            users.extend(bot for bot in UserProfile.objects.filter(is_bot=True,
                                                                   bot_owner=user_profile))

        operation = args[0]
        for user in users:
            print "Applying operation to User ID: %s: %s" % (user.id, operation)

            if operation == 'block':
                block_user(user, options['seconds'], options['domain'])
            elif operation == 'unblock':
                unblock_user(user, options['domain'])
