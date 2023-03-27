import urllib

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from zerver.lib.exceptions import JsonableError
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.validator import (
    check_url,
    to_wild_value,
)


class SentryTunnelSession(OutgoingSession):
    def __init__(self) -> None:
        super().__init__(role="sentry_tunnel", timeout=5)


@csrf_exempt
def sentry_tunnel(
    request: HttpRequest,
) -> HttpResponse:
    try:
        envelope = request.body
        header = to_wild_value("envelope", envelope.split(b"\n")[0].decode("utf-8"))
        dsn = urllib.parse.urlparse(header["dsn"].tame(check_url))
    except Exception:
        raise JsonableError(_("Invalid request format"))

    if dsn.geturl() != settings.SENTRY_FRONTEND_DSN:
        raise JsonableError(_("Invalid DSN"))

    assert dsn.hostname
    project_id = dsn.path.strip("/")
    url = dsn._replace(netloc=dsn.hostname, path=f"/api/{project_id}/envelope/").geturl()
    SentryTunnelSession().post(
        url=url, data=envelope, headers={"Content-Type": "application/x-sentry-envelope"}
    ).raise_for_status()
    return HttpResponse(status=200)
