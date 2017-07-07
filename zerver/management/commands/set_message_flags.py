from __future__ import absolute_import
from __future__ import print_function

from typing import Any, Iterable

from optparse import make_option
import logging
import sys

from django.core.management.base import BaseCommand, CommandParser

from zerver.lib import utils
from zerver.models import UserMessage, get_user_for_mgmt, get_realm
from django.db import models


class Command(BaseCommand):
    help = """Sets user message flags. Used internally by actions.py. Marks all
    Expects a comma-delimited list of user message ids via stdin, and an EOF to terminate."""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('-r', '--realm', nargs='?', default=None,
                            dest='string_id',
                            type=str,
                            help='The name of the realm in which you are setting message flags.')

        parser.add_argument('-f', '--for-real',
                            dest='for_real',
                            action='store_true',
                            default=False,
                            help="Actually change message flags. Default is a dry run.")

        parser.add_argument('-flag', nargs='+',
                            type=str,
                            help="The flag to add or remove")

        parser.add_argument('-op', nargs='+',
                            type=str,
                            help="The operation to do: 'add' or 'remove'")

        parser.add_argument('-u', '--until',
                            dest='all_until',
                            type=str,
                            help="Mark all messages <= specific usermessage id")

        parser.add_argument('-email', nargs='+',
                            type=str,
                            help="Email to set messages for")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        if not options["flag"] or not options["op"] or not options["email"]:
            print("Please specify an operation, a flag and an email")
            exit(1)

        op = options['op']
        flag = getattr(UserMessage.flags, options['flag'])
        all_until = options['all_until']
        email = options['email']
        realm = get_realm(options["string_id"])
        if options["string_id"] is not None and realm is None:
            print("The realm %s does not exist. Aborting." % options["string_id"])
            exit(1)

        user_profile = get_user_for_mgmt(email, realm)

        if all_until:
            filt = models.Q(id__lte=all_until)
        else:
            filt = models.Q(message__id__in=[mid.strip() for mid in sys.stdin.read().split(',')])
        mids = [m.id for m in
                UserMessage.objects.filter(filt, user_profile=user_profile).order_by('-id')]

        if options["for_real"]:
            sys.stdin.close()
            sys.stdout.close()
            sys.stderr.close()

        def do_update(batch):
            # type: (Iterable[int]) -> None
            msgs = UserMessage.objects.filter(id__in=batch)
            if op == 'add':
                msgs.update(flags=models.F('flags').bitor(flag))
            elif op == 'remove':
                msgs.update(flags=models.F('flags').bitand(~flag))

        if not options["for_real"]:
            logging.info("Updating %s by %s %s" % (mids, op, flag))
            logging.info("Dry run completed. Run with --for-real to change message flags.")
            exit(1)

        utils.run_in_batches(mids, 400, do_update, sleep_time=3)
        exit(0)
