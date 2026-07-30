# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import base64
import logging
from typing import Any

from pybreaker import CircuitBreaker, CircuitBreakerError
from requests.exceptions import HTTPError, ProxyError, RequestException, Timeout
from sentry_sdk.integrations.logging import ignore_logger
from typing_extensions import override

from zerver.lib.outgoing_http import OutgoingSession
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)
ignore_logger(logger.name)


class SentryTunnelSession(OutgoingSession):
    def __init__(self) -> None:  # nocoverage
        super().__init__(role="sentry_tunnel", timeout=1)


# Circuit-break and temporarily stop trying to report to
# Sentry if it keeps timing out.  We include ProxyError in
# here because we are likely making our requests through
# Smokescreen as a CONNECT proxy, so failures from Smokescreen
# failing to connect at the TCP level will report as
# ProxyErrors.
def open_circuit_for(exc_value: Exception) -> bool:
    if isinstance(exc_value, ProxyError | Timeout):
        return True
    if isinstance(exc_value, HTTPError):
        response = exc_value.response
        if response.status_code == 429 or response.status_code >= 500:
            return True
    return False


# Open the circuit after 2 failures, and leave it open for 30s.
@CircuitBreaker(
    fail_max=2,
    reset_timeout=30,
    name="Sentry tunnel",
    exclude=(open_circuit_for,),
)
def sentry_request(url: str, data: bytes) -> None:  # nocoverage
    SentryTunnelSession().post(
        url=url,
        data=data,
        headers={"Content-Type": "application/x-sentry-envelope"},
    ).raise_for_status()


@assign_queue("sentry_events")
class SentryEventsWorker(QueueProcessingWorker):
    """Forwards browser-submitted Sentry error reports to Sentry's API."""

    @override
    def consume(self, event: dict[str, Any]) -> None:
        try:
            sentry_request(
                event["url"],
                base64.b64decode(event["body"]),
            )
        except CircuitBreakerError:
            logger.warning("Dropped a client exception due to circuit-breaking")
        except RequestException as e:
            logger.exception(e)
