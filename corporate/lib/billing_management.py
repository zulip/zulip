from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError

from zerver.lib.management import ZulipBaseCommand
from zerver.models.realms import Realm
from zilencer.models import RemoteRealm, RemoteZulipServer

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import (
        BillingSession,
        RealmBillingSession,
        RemoteRealmBillingSession,
        RemoteServerBillingSession,
    )


class BillingSessionCommand(ZulipBaseCommand):
    def add_billing_entity_args(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--remote-server",
            dest="remote_server_uuid",
            required=False,
            help="The UUID of the registered remote Zulip server to modify.",
        )
        parser.add_argument(
            "--remote-realm",
            dest="remote_realm_uuid",
            required=False,
            help="The UUID of the remote realm to modify.",
        )
        self.add_realm_args(parser)

    def get_billing_session_from_args(self, options: dict[str, Any]) -> BillingSession:
        realm: Realm | None = None
        remote_realm: RemoteRealm | None = None
        remote_server: RemoteZulipServer | None = None
        billing_session: BillingSession | None = None
        if options["realm_id"]:
            realm = self.get_realm(options)
            if realm is None:
                raise CommandError("No realm found.")
            billing_session = RealmBillingSession(user=None, realm=realm)
        elif options["remote_realm_uuid"]:
            remote_realm_uuid = options["remote_realm_uuid"]
            try:
                remote_realm = RemoteRealm.objects.get(uuid=remote_realm_uuid)
                billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)
            except RemoteRealm.DoesNotExist:
                raise CommandError(
                    "There is no remote realm with uuid '{}'. Aborting.".format(
                        options["remote_realm_uuid"]
                    )
                )
        elif options["remote_server_uuid"]:
            remote_server_uuid = options["remote_server_uuid"]
            try:
                remote_server = RemoteZulipServer.objects.get(uuid=remote_server_uuid)
                billing_session = RemoteServerBillingSession(remote_server=remote_server)
            except RemoteZulipServer.DoesNotExist:
                raise CommandError(
                    "There is no remote server with uuid '{}'. Aborting.".format(
                        options["remote_server_uuid"]
                    )
                )

        if realm is None and remote_realm is None and remote_server is None:
            raise CommandError(
                "No billing entity (Realm, RemoteRealm or RemoteZulipServer) specified."
            )

        assert billing_session is not None
        return billing_session
