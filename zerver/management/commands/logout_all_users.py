from __future__ import absolute_import

from typing import Any
from optparse import make_option

from django.core.management.base import BaseCommand

from zerver.lib.actions import delete_all_user_sessions, \
    delete_realm_user_sessions, delete_all_deactivated_user_sessions
from zerver.models import get_realm

class Command(BaseCommand):
    help = "Log out all users."

    option_list = BaseCommand.option_list + (
        make_option('--realm',
                    dest='realm',
                    action='store',
                    default=None,
                    help="Only logout all users in a particular realm"),
        make_option('--deactivated-only',
                    action='store_true',
                    default=False,
                    help="Only logout all users who are deactivated"),
        )

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        if options["realm"]:
            realm = get_realm(options["realm"])
            delete_realm_user_sessions(realm)
        elif options["deactivated_only"]:
            delete_all_deactivated_user_sessions()
        else:
            delete_all_user_sessions()
