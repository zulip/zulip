from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

from django.db import connection
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from psycopg2.sql import SQL

from zerver.lib import tracing
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.tracing import (
    NoOrphanClientSpansSampler,
    add_sql_tracing,
    continue_trace,
    get_trace_context,
    trace_sql,
)


class TracingTest(ZulipTestCase):
    @contextmanager
    def capture_spans(self) -> Iterator[InMemorySpanExporter]:
        # The global tracer provider can only be set once per process,
        # so the tests swap in a tracer from a provider of their own.
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        with patch("zerver.lib.tracing.tracer", provider.get_tracer("test")):
            yield exporter

    def test_sql_spans(self) -> None:
        with (
            self.capture_spans() as exporter,
            connection.execute_wrapper(trace_sql),
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT 1")
            cursor.execute(SQL("SELECT 2"))

        [plain, composed] = exporter.get_finished_spans()
        self.assertEqual(plain.name, "SELECT")
        assert plain.attributes is not None
        self.assertEqual(plain.attributes["db.query.text"], "SELECT 1")
        self.assertEqual(plain.attributes["db.operation.name"], "SELECT")
        self.assertEqual(composed.name, "SQL")
        assert composed.attributes is not None
        self.assertNotIn("db.query.text", composed.attributes)

    def test_add_sql_tracing_once(self) -> None:
        with patch.object(connection, "execute_wrappers", []):
            add_sql_tracing(connection)
            add_sql_tracing(connection)
            self.assertEqual(connection.execute_wrappers, [trace_sql])

    def test_orphan_client_spans_are_dropped(self) -> None:
        sampler = NoOrphanClientSpansSampler(ALWAYS_ON)
        self.assertIn("NoOrphanClientSpansSampler", sampler.get_description())
        exporter = InMemorySpanExporter()
        provider = TracerProvider(sampler=sampler)
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("SELECT", kind=trace.SpanKind.CLIENT):
            pass
        self.assertEqual(exporter.get_finished_spans(), ())

        with (
            tracer.start_as_current_span("POST /messages", kind=trace.SpanKind.SERVER),
            tracer.start_as_current_span("SELECT", kind=trace.SpanKind.CLIENT),
        ):
            pass
        self.assertEqual(
            [span.name for span in exporter.get_finished_spans()], ["SELECT", "POST /messages"]
        )

    def test_untraced_notification(self) -> None:
        self.assertEqual(get_trace_context(), {})

        with (
            self.capture_spans() as exporter,
            continue_trace("process_notification", {}, {"zulip.event.type": "message"}),
        ):
            pass

        self.assertEqual(exporter.get_finished_spans(), ())

    def test_notification_continues_request_trace(self) -> None:
        with self.capture_spans() as exporter:
            with tracing.tracer.start_as_current_span("POST /messages"):
                trace_context = get_trace_context()
            self.assertIn("traceparent", trace_context)

            with continue_trace(
                "process_notification", trace_context, {"zulip.event.type": "message"}
            ):
                pass

        [request, notification] = exporter.get_finished_spans()
        self.assertEqual(notification.name, "process_notification")
        self.assertEqual(notification.kind, trace.SpanKind.CONSUMER)
        assert notification.attributes is not None
        self.assertEqual(notification.attributes["zulip.event.type"], "message")
        assert notification.parent is not None
        assert request.context is not None and notification.context is not None
        self.assertEqual(notification.parent.span_id, request.context.span_id)
        self.assertEqual(notification.context.trace_id, request.context.trace_id)
