from argparse import ArgumentParser
from typing import Any, cast

from typing_extensions import override

from zerver.actions.realm_settings import do_add_deactivated_redirect, do_deactivate_realm
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Script to deactivate a realm."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--redirect_url", metavar="<redirect_url>", help="URL to which the realm has moved"
        )
        parser.add_argument(
            "--deactivation_reason",
            metavar="<deactivation_reason>",
            help="Reason for deactivation",
            required=True,
        )
        parser.add_argument(
            "--email_owners",
            action="store_true",
            help="Whether to email organization owners about realm deactivation",
        )
        self.add_realm_args(parser, required=True)

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        deactivation_reason = options["deactivation_reason"]

        assert realm is not None  # Should be ensured by parser

        if options["redirect_url"]:
            print("Setting the redirect URL to", options["redirect_url"])
            do_add_deactivated_redirect(realm, options["redirect_url"])

        if realm.deactivated:
            print("The realm", options["realm_id"], "is already deactivated.")
            return

        send_realm_deactivation_email = options["email_owners"]
        print("Deactivating", options["realm_id"])
        do_deactivate_realm(
            realm,
            acting_user=None,
            deactivation_reason=cast(Any, deactivation_reason),
            email_owners=send_realm_deactivation_email,
        )
        print("Done!")
