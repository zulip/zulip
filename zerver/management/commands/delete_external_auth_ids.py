from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError
from django.db.models import Count
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.models.users import ExternalAuthID


class Command(ZulipBaseCommand):
    help = """Delete the ExternalAuthIDs linking Zulip accounts to users in an LDAP
directory or a SAML or OIDC identity provider.

This is necessary when changing which attribute `unique_account_id` (LDAP) or
`attr_user_permanent_id` (SAML) refers to, or when an identity provider starts
sending different identifiers for existing users. Users are linked again via
their email address the next time they log in or, for LDAP, the next time
manage.py sync_ldap_user_data runs, whichever comes first.

Examples:
  ./manage.py delete_external_auth_ids --auth-method ldap --all-realms
  ./manage.py delete_external_auth_ids --auth-method saml:okta -r zulip
"""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--auth-method",
            required=True,
            help="The authentication method to delete ExternalAuthIDs for, e.g. ldap.",
        )
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument(
            "--all-realms", action="store_true", help="Delete ExternalAuthIDs in all realms."
        )
        self.add_realm_args(target, help="Delete ExternalAuthIDs in the specified realm.")

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        external_auth_ids = ExternalAuthID.objects.all()
        if realm is not None:
            external_auth_ids = external_auth_ids.filter(realm=realm)

        auth_method = options["auth_method"]
        to_delete = external_auth_ids.filter(external_auth_method_name=auth_method)
        if not to_delete.exists():
            counts = (
                external_auth_ids.values_list("external_auth_method_name")
                .annotate(Count("id"))
                .order_by("external_auth_method_name")
            )
            present = "".join(f"\n  {name} ({count})" for name, count in counts)
            raise CommandError(
                f"No ExternalAuthIDs for {auth_method!r}. Present:{present or ' none'}"
            )

        deleted_count, _ = to_delete.delete()
        print(f"Deleted {deleted_count} ExternalAuthIDs for {auth_method}.")
