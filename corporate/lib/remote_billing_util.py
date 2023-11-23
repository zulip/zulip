import logging
from typing import Optional, TypedDict

from django.http import HttpRequest
from django.utils.translation import gettext as _

billing_logger = logging.getLogger("corporate.stripe")


class RemoteBillingIdentityDict(TypedDict):
    user_uuid: str
    user_email: str
    user_full_name: str
    remote_server_uuid: str
    remote_realm_uuid: str


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
