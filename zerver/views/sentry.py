import logging
from contextlib import suppress
from urllib.parse import urlsplit

import orjson
from circuitbreaker import CircuitBreakerError, circuit
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from requests.exceptions import HTTPError, ProxyError, RequestException, Timeout
from sentry_sdk.integrations.logging import ignore_logger

from zerver.lib.exceptions import JsonableError
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.validator import check_url, to_wild_value

# In order to not overload Sentry if it's having a bad day, we tell
# Sentry to ignore exceptions that we have when talking to Sentry.
logger = logging.getLogger(__name__)
ignore_logger(logger.name)


class SentryTunnelSession(OutgoingSession):
    def __init__(self) -> None:
        super().__init__(role="sentry_tunnel", timeout=1)


@csrf_exempt
def sentry_tunnel(
    request: HttpRequest,
) -> HttpResponse:
    try:
        envelope_header_line, envelope_items = request.body.split(b"\n", 1)
        envelope_header = to_wild_value("envelope_header", envelope_header_line.decode("utf-8"))
        dsn = urlsplit(envelope_header["dsn"].tame(check_url))
    except Exception:
        raise JsonableError(_("Invalid request format"))

    if dsn.geturl() != settings.SENTRY_FRONTEND_DSN:
        raise JsonableError(_("Invalid DSN"))

    assert dsn.hostname
    project_id = dsn.path.strip("/")
    url = dsn._replace(netloc=dsn.hostname, path=f"/api/{project_id}/envelope/").geturl()

    # Adjust the payload to explicitly contain the IP address of the
    # user we see.  If left blank, Sentry will assume the IP it
    # received the request from, which is Zulip's, which can make
    # debugging more complicated.
    updated_body = request.body
    # If we fail to update the body for any reason, leave it as-is; it
    # is better to misreport the IP than to drop the report entirely.
    with suppress(Exception):
        # This parses the Sentry ingestion format, known as an
        # Envelope.  See https://develop.sentry.dev/sdk/envelopes/ for
        # spec.
        parts = [envelope_header_line, b"\n"]
        while envelope_items != b"":
            item_header_line, rest = envelope_items.split(b"\n", 1)
            parts.append(item_header_line)
            parts.append(b"\n")
            item_header = orjson.loads(item_header_line.decode("utf-8"))
            length = item_header.get("length")
            if length is None:
                item_body, envelope_items = [*rest.split(b"\n", 1), b""][:2]
            else:
                item_body, envelope_items = rest[0:length], rest[length:]
            if item_header.get("type") in ("transaction", "event"):
                # Event schema:
                # https://develop.sentry.dev/sdk/event-payloads/#core-interfaces
                # https://develop.sentry.dev/sdk/event-payloads/user/
                #
                # Transaction schema:
                # https://develop.sentry.dev/sdk/event-payloads/transaction/#anatomy
                # Note that "Transactions are Events enriched with Span data."
                payload_data = orjson.loads(item_body)
                if "user" in payload_data:
                    payload_data["user"]["ip_address"] = request.META.get("REMOTE_ADDR")
                    item_body = orjson.dumps(payload_data)
            parts.append(item_body)
            if length is None:
                parts.append(b"\n")
        updated_body = b"".join(parts)

    try:
        sentry_request(url, updated_body)
    except CircuitBreakerError:
        logger.warning("Dropped a client exception due to circuit-breaking")
    except RequestException as e:
        # This logger has been configured, above, to not report to Sentry
        logger.exception(e)
    return HttpResponse(status=200)


# Circuit-break and temporarily stop trying to report to
# Sentry if it keeps timing out.  We include ProxyError in
# here because we are likely making our requests through
# Smokescreen as a CONNECT proxy, so failures from Smokescreen
# failing to connect at the TCP level will report as
# ProxyErrors.
def open_circuit_for(exc_type: type[Exception], exc_value: Exception) -> bool:
    if issubclass(exc_type, ProxyError | Timeout):
        return True
    if isinstance(exc_value, HTTPError):
        response = exc_value.response
        if response.status_code == 429 or response.status_code >= 500:
            return True
    return False


# Open the circuit after 2 failures, and leave it open for 30s.
@circuit(
    failure_threshold=2,
    recovery_timeout=30,
    name="Sentry tunnel",
    expected_exception=open_circuit_for,
)
def sentry_request(url: str, data: bytes) -> None:
    SentryTunnelSession().post(
        url=url,
        data=data,
        headers={"Content-Type": "application/x-sentry-envelope"},
    ).raise_for_status()
