"""Distributed tracing with OpenTelemetry.

Tracing is enabled only when OTEL_EXPORTER_OTLP_ENDPOINT is set, which
the Kubernetes deployment does; spans then go over OTLP/HTTP to an
OpenTelemetry Collector, which exports them to Cloud Trace.  Without
that variable, the tracer used here is a no-op, which is what tests
and development use.

Each Django and Tornado request is a span, with child spans for its
SQL queries, Redis commands, and outgoing HTTP requests.  Events sent
to Tornado through RabbitMQ carry the sending request's trace context,
so delivering a message to clients shows up in the same trace as the
POST /messages that sent it.
"""

import os
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from opentelemetry import propagate, trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace.sampling import Decision, Sampler, SamplingResult
from opentelemetry.util.types import Attributes
from typing_extensions import override

if TYPE_CHECKING:
    from django.db.backends.base.base import BaseDatabaseWrapper

tracer = trace.get_tracer("zulip")

# Long-polling GET /events requests stay open for up to a minute
# waiting for events, so their spans would only measure idle time.
EXCLUDED_URLS = "/json/events$,/api/v1/events$,/health$"


class NoOrphanClientSpansSampler(Sampler):
    """Drops SQL, Redis, and HTTP client spans that have no parent, so
    that the queries of excluded URLs, like the health check run by
    Kubernetes every few seconds, don't each start a trace."""

    def __init__(self, delegate: Sampler) -> None:
        self.delegate = delegate

    @override
    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: trace.SpanKind | None = None,
        attributes: Attributes = None,
        links: Sequence[trace.Link] | None = None,
        trace_state: trace.TraceState | None = None,
    ) -> SamplingResult:
        parent = trace.get_current_span(parent_context).get_span_context()
        if kind == trace.SpanKind.CLIENT and not parent.is_valid:
            return SamplingResult(Decision.DROP)
        return self.delegate.should_sample(
            parent_context, trace_id, name, kind, attributes, links, trace_state
        )

    @override
    def get_description(self) -> str:
        return f"NoOrphanClientSpansSampler({self.delegate.get_description()})"


def setup_tracing(service_name: str) -> None:  # nocoverage
    """Must run before Django loads its middleware, since the Django
    instrumentation adds its own to settings.MIDDLEWARE."""
    if "OTEL_EXPORTER_OTLP_ENDPOINT" not in os.environ:
        return

    import requests
    from django.conf import settings
    from django.db.backends.signals import connection_created
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    # Supervisor sets HTTP_proxy to Smokescreen in every Zulip process,
    # and Smokescreen rejects private IP addresses like the Collector's.
    session = requests.Session()
    session.trust_env = False

    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name}),
        sampler=NoOrphanClientSpansSampler(
            ParentBased(TraceIdRatioBased(float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "1"))))
        ),
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(session=session)))
    trace.set_tracer_provider(provider)

    # The Django instrumentation reads the request's host, which raises
    # for hosts not in ALLOWED_HOSTS; placing its middleware after
    # LogRequests keeps those requests logged and counted.
    os.environ["OTEL_PYTHON_DJANGO_MIDDLEWARE_POSITION"] = str(
        settings.MIDDLEWARE.index("zerver.middleware.LogRequests") + 1
    )
    DjangoInstrumentor().instrument(excluded_urls=EXCLUDED_URLS)
    RedisInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    connection_created.connect(add_sql_tracing, weak=False)


def add_sql_tracing(connection: "BaseDatabaseWrapper", **kwargs: object) -> None:
    # Django reuses the connection wrapper when it reconnects.
    if trace_sql not in connection.execute_wrappers:
        connection.execute_wrappers.append(trace_sql)


# The signature Django gives execute wrappers; Any because the wrapper
# passes the cursor's result through without looking at it.
def trace_sql(
    execute: Callable[..., Any],
    sql: object,
    params: object,
    many: bool,
    context: Mapping[str, Any],
) -> Any:
    # Queries built with psycopg2.sql are Composed objects, which only
    # render to text with a database connection; leave those unnamed.
    attributes = {"db.system.name": "postgresql"}
    operation = "SQL"
    if isinstance(sql, str) and sql.strip():
        operation = sql.split(maxsplit=1)[0].upper()
        attributes["db.operation.name"] = operation
        attributes["db.query.text"] = sql
    with tracer.start_as_current_span(operation, kind=trace.SpanKind.CLIENT, attributes=attributes):
        return execute(sql, params, many, context)


def get_trace_context() -> dict[str, str]:
    """The current trace context, as W3C Trace Context headers, for
    passing to another process through a queue.  Empty when tracing
    is disabled."""
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier


@contextmanager
def continue_trace(
    span_name: str, trace_context: Mapping[str, str] | None, attributes: Mapping[str, str]
) -> Iterator[None]:
    """Run the block as a span in the trace that trace_context came
    from.  Work that no traced request started is not traced, so that
    events from queue workers and cron jobs don't each start a trace."""
    if not trace_context:
        yield
        return
    with tracer.start_as_current_span(
        span_name,
        context=propagate.extract(trace_context),
        kind=trace.SpanKind.CONSUMER,
        attributes=attributes,
    ):
        yield
