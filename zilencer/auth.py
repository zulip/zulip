from django.http import HttpRequest
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext as _

from zerver.decorator import process_client
from zerver.lib.exceptions import ErrorCode, JsonableError, RemoteServerDeactivatedError
from zerver.lib.request import RequestNotes
from zerver.lib.subdomains import get_subdomain
from zerver.models import Realm
from zilencer.models import RemoteZulipServer, get_remote_server_by_uuid


class InvalidZulipServerError(JsonableError):
    code = ErrorCode.INVALID_ZULIP_SERVER
    data_fields = ["role"]

    def __init__(self, role: str) -> None:
        self.role: str = role

    @staticmethod
    def msg_format() -> str:
        return "Zulip server auth failure: {role} is not registered -- did you run `manage.py register_server`?"


class InvalidZulipServerKeyError(InvalidZulipServerError):
    @staticmethod
    def msg_format() -> str:
        return "Zulip server auth failure: key does not match role {role}"


def validate_remote_server(
    request: HttpRequest,
    role: str,
    api_key: str,
) -> RemoteZulipServer:
    try:
        remote_server = get_remote_server_by_uuid(role)
    except RemoteZulipServer.DoesNotExist:
        raise InvalidZulipServerError(role)
    if not constant_time_compare(api_key, remote_server.api_key):
        raise InvalidZulipServerKeyError(role)

    if remote_server.deactivated:
        raise RemoteServerDeactivatedError()

    if get_subdomain(request) != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
        raise JsonableError(_("Invalid subdomain for push notifications bouncer"))
    RequestNotes.get_notes(request).remote_server = remote_server
    process_client(request)
    return remote_server
