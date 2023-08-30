from argparse import ArgumentParser
from typing import Any, Callable, Dict, List, Optional

import orjson
from django.conf import settings
from django.db.models import Q, QuerySet

from confirmation.models import one_click_unsubscribe_link
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
        targets = parser.add_mutually_exclusive_group(required=True)
        targets.add_argument(
            "--entire-server", action="store_true", help="Send to every user on the server."
        )
        targets.add_argument(
            "--marketing",
            action="store_true",
            help="Send to active users and realm owners with the enable_marketing_emails setting enabled.",
        )
        targets.add_argument(
            "--remote-servers",
            action="store_true",
            help="Send to registered contact email addresses for remote Zulip servers.",
        )
        targets.add_argument(
            "--all-sponsored-org-admins",
            action="store_true",
            help="Send to all organization administrators of sponsored organizations.",
        )
        targets.add_argument(
            "--json-file",
            help="Load the JSON file, and send to the users whose ids are the keys in that dict; "
            "the context for each email will be extended by each value in the dict.",
        )
        self.add_user_list_args(
            targets,
            help="Email addresses of user(s) to send emails to.",
            all_users_help="Send to every user on the realm.",
        )
        # Realm is only required for --users and --all-users, so it is
        # not mutually exclusive with the rest of the above.
        self.add_realm_args(parser)

        # This is an additional filter which is composed with the above
        parser.add_argument(
            "--admins-only",
            help="Filter recipients selected via other options to to only organization administrators",
            action="store_true",
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
            "--dry-run",
            action="store_true",
            help="Prints emails of the recipients and text of the email.",
        )

    def handle(self, *args: Any, **options: str) -> None:
        target_emails: List[str] = []
        users: QuerySet[UserProfile] = UserProfile.objects.none()
        add_context: Optional[Callable[[Dict[str, object], UserProfile], None]] = None

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

            def add_marketing_unsubscribe(context: Dict[str, object], user: UserProfile) -> None:
                context["unsubscribe_link"] = one_click_unsubscribe_link(user, "marketing")

            add_context = add_marketing_unsubscribe
        elif options["remote_servers"]:
            from zilencer.models import RemoteZulipServer

            target_emails = list(
                set(
                    RemoteZulipServer.objects.filter(deactivated=False).values_list(
                        "contact_email", flat=True
                    )
                )
            )
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
        elif options["json_file"]:
            with open(options["json_file"]) as f:
                user_data: Dict[str, Dict[str, object]] = orjson.loads(f.read())
            users = UserProfile.objects.filter(id__in=[int(user_id) for user_id in user_data])

            def add_context_from_dict(context: Dict[str, object], user: UserProfile) -> None:
                context.update(user_data.get(str(user.id), {}))

            add_context = add_context_from_dict

        else:
            realm = self.get_realm(options)
            users = self.get_users(options, realm, is_bot=False)

        # Only email users who've agreed to the terms of service.
        if settings.TERMS_OF_SERVICE_VERSION is not None:
            users = users.exclude(
                Q(tos_version=None) | Q(tos_version=UserProfile.TOS_VERSION_BEFORE_FIRST_LOGIN)
            )
        send_custom_email(
            users, target_emails=target_emails, options=options, add_context=add_context
        )

        if options["dry_run"]:
            print("Would send the above email to:")
            for user in users:
                print(f"  {user.delivery_email} ({user.realm.string_id})")
            for email in target_emails:
                print(f"  {email}")
