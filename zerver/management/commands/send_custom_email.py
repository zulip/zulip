from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.send_email import send_custom_email
from zerver.models import Realm, UserProfile


class Command(ZulipBaseCommand):
    help = """
    Send a custom email with Zulip branding to the specified users.

    Useful to send a notice to all users of a realm or server.

    The From and Subject headers can be provided in the body of the Markdown
    document used to generate the email, or on the command line."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--entire-server", action="store_true", help="Send to every user on the server."
        )
        parser.add_argument(
            "--all-sponsored-org-admins",
            action="store_true",
            help="Send to all organization administrators of sponsored organizations.",
        )
        parser.add_argument(
            "--marketing",
            action="store_true",
            help="Send to active users and realm owners with the enable_marketing_emails setting enabled.",
        )
        parser.add_argument(
            "--markdown-template-path",
            "--path",
            required=True,
            help="Path to a Markdown-format body for the email.",
        )
        parser.add_argument(
            "--subject",
            help="Subject for the email. It can be declared in Markdown file in headers",
        )
        parser.add_argument(
            "--from-name",
            help="From line for the email. It can be declared in Markdown file in headers",
        )
        parser.add_argument("--reply-to", help="Optional reply-to line for the email")
        parser.add_argument(
            "--admins-only", help="Send only to organization administrators", action="store_true"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Prints emails of the recipients and text of the email.",
        )

        self.add_user_list_args(
            parser,
            help="Email addresses of user(s) to send emails to.",
            all_users_help="Send to every user on the realm.",
        )
        self.add_realm_args(parser)

    def handle(self, *args: Any, **options: str) -> None:
        if options["entire_server"]:
            users = UserProfile.objects.filter(
                is_active=True, is_bot=False, is_mirror_dummy=False, realm__deactivated=False
            )
        elif options["marketing"]:
            # Marketing email sent at most once to each email address for users
            # who are recently active (!long_term_idle) users of the product.
            users = UserProfile.objects.filter(
                is_active=True,
                is_bot=False,
                is_mirror_dummy=False,
                realm__deactivated=False,
                enable_marketing_emails=True,
                long_term_idle=False,
            ).distinct("delivery_email")
        elif options["all_sponsored_org_admins"]:
            # Sends at most one copy to each email address, even if it
            # is an administrator in several organizations.
            sponsored_realms = Realm.objects.filter(
                plan_type=Realm.PLAN_TYPE_STANDARD_FREE, deactivated=False
            )
            admin_roles = [UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_REALM_OWNER]
            users = UserProfile.objects.filter(
                is_active=True,
                is_bot=False,
                is_mirror_dummy=False,
                role__in=admin_roles,
                realm__deactivated=False,
                realm__in=sponsored_realms,
            ).distinct("delivery_email")
        else:
            realm = self.get_realm(options)
            try:
                users = self.get_users(options, realm, is_bot=False)
            except CommandError as error:
                if str(error) == "You have to pass either -u/--users or -a/--all-users.":
                    raise CommandError(
                        "You have to pass -u/--users or -a/--all-users or --entire-server."
                    )
                raise error

        # Only email users who've agreed to the terms of service.
        if settings.TOS_VERSION is not None:
            # We need to do a new query because the `get_users` path
            # passes us a list rather than a QuerySet.
            users = (
                UserProfile.objects.select_related()
                .filter(id__in=[u.id for u in users])
                .exclude(tos_version=None)
            )
        send_custom_email(users, options)

        if options["dry_run"]:
            print("Would send the above email to:")
            for user in users:
                print(f"  {user.delivery_email} ({user.realm.string_id})")
