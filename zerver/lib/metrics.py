"""Prometheus metrics backing the SLIs for sending and delivering messages.

In the Docker image, the entrypoint sets PROMETHEUS_MULTIPROC_DIR
before starting supervisord, so every uWSGI worker and Tornado process
writes its samples there; scripts/zulip-metrics-server aggregates and
serves them.  Without that variable, prometheus_client keeps the
samples in this process only, which is what tests and development use.
"""

from prometheus_client import Counter, Histogram

http_requests = Counter(
    "zulip_http_requests",
    "HTTP requests, by view function, method, and response status code.",
    ["endpoint", "method", "status"],
)

# The 2.5 bucket matches the delivery latency SLO, so the share of
# deliveries within the SLO can be read directly from that bucket.
event_delivery_latency_seconds = Histogram(
    "zulip_event_delivery_latency_seconds",
    "Time from Django sending an event to Tornado, right after the database "
    "commit, until Tornado hands it to a client waiting on GET /events.",
    ["event_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)


def endpoint_label(query: str | None) -> str:
    """The view function name, without the conventional _backend
    suffix (send_message_backend -> send_message).  Views reached
    outside rest_dispatch have no recorded name."""
    if query is None:
        return "other"
    return query.removesuffix("_backend")
