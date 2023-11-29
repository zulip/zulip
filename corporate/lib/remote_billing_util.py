import logging
from typing import Optional, TypedDict

from django.http import HttpRequest
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zilencer.models import RemoteRealm, RemoteZulipServer

billing_logger = logging.getLogger("corporate.stripe")


class RemoteBillingIdentityDict(TypedDict):
    user_uuid: str
    user_email: str
    user_full_name: str
    remote_server_uuid: str
    remote_realm_uuid: str


class LegacyServerIdentityDict(TypedDict):
    # Currently this has only one field. We can extend this
    # to add more information as appropriate.
    remote_server_uuid: str


def get_identity_dict_from_session(
    request: HttpRequest,
    realm_uuid: Optional[str],
    server_uuid: Optional[str],
) -> Optional[RemoteBillingIdentityDict]:
    authed_uuid = realm_uuid or server_uuid
    assert authed_uuid is not None

    identity_dicts = request.session.get("remote_billing_identities")
    if identity_dicts is not None:
        return identity_dicts.get(authed_uuid)

    return None


def get_remote_realm_from_session(
    request: HttpRequest,
    realm_uuid: Optional[str],
    server_uuid: Optional[str] = None,
) -> RemoteRealm:
    identity_dict = get_identity_dict_from_session(request, realm_uuid, server_uuid)

    if identity_dict is None:
        raise JsonableError(_("User not authenticated"))

    remote_server_uuid = identity_dict["remote_server_uuid"]
    remote_realm_uuid = identity_dict["remote_realm_uuid"]

    try:
        remote_realm = RemoteRealm.objects.get(
            uuid=remote_realm_uuid, server__uuid=remote_server_uuid
        )
    except RemoteRealm.DoesNotExist:
        raise AssertionError(
            "The remote realm is missing despite being in the RemoteBillingIdentityDict"
        )

    if (
        remote_realm.registration_deactivated
        or remote_realm.realm_deactivated
        or remote_realm.server.deactivated
    ):
        raise JsonableError(_("Registration is deactivated"))

    return remote_realm


def get_remote_server_from_session(
    request: HttpRequest,
    server_uuid: str,
) -> RemoteZulipServer:
    identity_dict = get_identity_dict_from_session(request, None, server_uuid)
    if identity_dict is None:
        raise JsonableError(_("User not authenticated"))

    remote_server_uuid = identity_dict["remote_server_uuid"]
    try:
        remote_server = RemoteZulipServer.objects.get(uuid=remote_server_uuid)
    except RemoteZulipServer.DoesNotExist:
        raise JsonableError(_("Invalid remote server."))

    if remote_server.deactivated:
        raise JsonableError(_("Registration is deactivated"))

    return remote_server
