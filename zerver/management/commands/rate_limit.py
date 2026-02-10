from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.rate_limiter import RateLimitedUser
from zerver.models import UserProfile
from zerver.models.users import get_user_profile_by_api_key


class Command(ZulipBaseCommand):
    help = """Manually block or unblock a user from accessing the API"""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("-e", "--email", help="Email account of user.")
        parser.add_argument("-a", "--api-key", help="API key of user.")
        parser.add_argument("-s", "--seconds", default=60, type=int, help="Seconds to block for.")
        parser.add_argument(
            "-d",
            "--domain",
            default="api_by_user",
            help="Rate-limiting domain. Defaults to 'api_by_user'.",
        )
        parser.add_argument(
            "-b",
            "--all-bots",
            dest="bots",
            action="store_true",
            help="Whether or not to also block all bots for this user.",
        )
        parser.add_argument(
            "operation",
            metavar="<operation>",
            choices=["block", "unblock"],
            help="operation to perform (block or unblock)",
        )
        self.add_realm_args(parser)

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if (not options["api_key"] and not options["email"]) or (
            options["api_key"] and options["email"]
        ):
            raise CommandError("Please enter either an email or API key to manage")

        realm = self.get_realm(options)
        if options["email"]:
            user_profile = self.get_user(options["email"], realm)
        else:
            try:
                user_profile = get_user_profile_by_api_key(options["api_key"])
            except UserProfile.DoesNotExist:
                raise CommandError(
                    "Unable to get user profile for API key {}".format(options["api_key"])
                )

        users = [user_profile]
        if options["bots"]:
            users.extend(
                bot for bot in UserProfile.objects.filter(is_bot=True, bot_owner=user_profile)
            )

        operation = options["operation"]
        for user in users:
            print(f"Applying operation to User ID: {user.id}: {operation}")

            if operation == "block":
                RateLimitedUser(user, domain=options["domain"]).block_access(options["seconds"])
            elif operation == "unblock":
                RateLimitedUser(user, domain=options["domain"]).unblock_access()
