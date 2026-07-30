import base64
from unittest import mock

import orjson
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from pybreaker import CircuitBreakerError
from requests import HTTPError
from requests.exceptions import ProxyError, Timeout

from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_response_from_error
from zerver.lib.test_classes import ZulipTestCase
from zerver.views.sentry import sentry_tunnel
from zerver.worker.sentry_events import SentryEventsWorker, open_circuit_for

TEST_USER_IP = "203.0.113.42"
# We make this valid by overriding SENTRY_FRONTEND_DSN in the test class below.
TEST_VALID_DSN = "https://abc123@o123456.ingest.sentry.io/789"
# Doesn't match TEST_VALID_DSN/SENTRY_FRONTEND_DSN, so view will reject.
TEST_INVALID_DSN = "https://other@o999999.ingest.sentry.io/000"


def build_envelope(
    dsn: str = TEST_VALID_DSN,
    item_type: str = "event",
    user_ip: str | None = None,
    explicit_length: bool = False,
    length_override: int | None = None,
) -> bytes:
    """
    Builds a minimal, valid Sentry envelope with a single item.
    See https://develop.sentry.dev/sdk/envelopes/ for the format:
    a header JSON line, then for each item: an item-header JSON line,
    then the item body.

    By default the item header omits "length", so the item body is
    delimited by a trailing newline (the length-less branch of the
    parser). Pass explicit_length=True to instead declare the body's
    exact byte length in the item header (the explicit-length branch),
    which is parsed differently: no trailing newline is required or
    consumed after the body.

    length_override lets a caller declare a length that doesn't match
    the actual body size, to exercise the parser's failure/fallback
    behavior on a corrupt envelope.
    """
    envelope_header = orjson.dumps({"dsn": dsn})

    item_body: dict[str, object] = {
        "message": "test event from baseline test",
    }
    if user_ip is not None:
        item_body["user"] = {"ip_address": user_ip}

    item_body_bytes = orjson.dumps(item_body)

    item_header_fields: dict[str, object] = {"type": item_type}
    if explicit_length:
        item_header_fields["length"] = (
            length_override if length_override is not None else len(item_body_bytes)
        )
    item_header = orjson.dumps(item_header_fields)

    if explicit_length:
        # No trailing newline: the parser slices exactly `length`
        # bytes for the body and treats whatever follows as the
        # start of the next item (or the end of input).
        return envelope_header + b"\n" + item_header + b"\n" + item_body_bytes
    else:
        return envelope_header + b"\n" + item_header + b"\n" + item_body_bytes + b"\n"


@override_settings(SENTRY_FRONTEND_DSN=TEST_VALID_DSN)
class SentryTunnelTest(ZulipTestCase):
    """
    Tests for the sentry_tunnel view. The view validates the envelope,
    injects the client IP, and publishes to the sentry_events queue;
    the actual HTTP forwarding to Sentry happens in SentryEventsWorker.
    Tests mock queue_event_on_commit to keep tests hermetic and assert
    on exactly what gets enqueued.
    """

    def _post_envelope(
        self,
        envelope: bytes,
        remote_addr: str = TEST_USER_IP,
    ) -> HttpResponse:
        request = RequestFactory().post(
            "/error_tracing",
            data=envelope,
            content_type="application/x-sentry-envelope",
            REMOTE_ADDR=remote_addr,
        )
        try:
            return sentry_tunnel(request)
        except JsonableError as e:
            return json_response_from_error(e)

    def test_valid_envelope_is_enqueued(self) -> None:
        envelope = build_envelope()

        with mock.patch("zerver.views.sentry.queue_event_on_commit") as mock_queue:
            response = self._post_envelope(envelope)

        self.assertEqual(response.status_code, 200)
        mock_queue.assert_called_once()
        queue_name, event = mock_queue.call_args[0]
        self.assertEqual(queue_name, "sentry_events")
        self.assertIn("/api/789/envelope/", event["url"])

    def test_invalid_dsn_is_rejected(self) -> None:
        envelope = build_envelope(dsn=TEST_INVALID_DSN)

        with mock.patch("zerver.views.sentry.queue_event_on_commit") as mock_queue:
            response = self._post_envelope(envelope)

        self.assert_json_error(response, "Invalid DSN", 400)
        mock_queue.assert_not_called()

    def test_malformed_envelope_is_rejected(self) -> None:
        # No newline at all -- the initial `request.body.split(b"\n", 1)`
        # will fail to produce two parts.
        malformed_envelope = b"not a real envelope"

        with mock.patch("zerver.views.sentry.queue_event_on_commit") as mock_queue:
            response = self._post_envelope(malformed_envelope)

        self.assert_json_error(response, "Invalid request format", 400)
        mock_queue.assert_not_called()

    def test_ip_address_is_injected_into_user_payload(self) -> None:
        envelope = build_envelope(user_ip="should-be-overwritten")

        with mock.patch("zerver.views.sentry.queue_event_on_commit") as mock_queue:
            response = self._post_envelope(envelope, remote_addr=TEST_USER_IP)

        self.assertEqual(response.status_code, 200)
        mock_queue.assert_called_once()
        _, event = mock_queue.call_args[0]
        called_body = base64.b64decode(event["body"])
        # The body is: header\n, item_header\n, item_body\n
        _header_line, rest = called_body.split(b"\n", 1)
        _item_header_line, item_body_and_rest = rest.split(b"\n", 1)
        item_body = item_body_and_rest.split(b"\n", 1)[0]
        payload = orjson.loads(item_body)
        self.assertEqual(payload["user"]["ip_address"], TEST_USER_IP)

    def test_ip_address_is_injected_via_explicit_length(self) -> None:
        # Same as test_ip_address_is_injected_into_user_payload,
        # but via the explicit-length parsing branch.
        envelope = build_envelope(user_ip="should-be-overwritten", explicit_length=True)

        with mock.patch("zerver.views.sentry.queue_event_on_commit") as mock_queue:
            response = self._post_envelope(envelope, remote_addr=TEST_USER_IP)

        self.assertEqual(response.status_code, 200)
        mock_queue.assert_called_once()
        _, event = mock_queue.call_args[0]
        called_body = base64.b64decode(event["body"])
        _header_line, rest = called_body.split(b"\n", 1)
        item_header_line, item_body_and_rest = rest.split(b"\n", 1)
        item_header = orjson.loads(item_header_line)
        length = item_header["length"]
        item_body = item_body_and_rest[:length]
        payload = orjson.loads(item_body)
        self.assertEqual(payload["user"]["ip_address"], TEST_USER_IP)

    def test_explicit_length_handles_multibyte_utf8(self) -> None:
        # "café" -- the "é" character is 2 bytes in UTF-8 but only
        # 1 character, so a length computed from character count
        # rather than byte count would mis-slice this body.
        test_message = "café \u2603"  # also include a snowman (3 bytes in UTF-8)

        envelope_header = orjson.dumps({"dsn": TEST_VALID_DSN})
        item_body_bytes = orjson.dumps({"message": test_message})

        # Sanity check our own test data: confirm this body actually
        # has more bytes than characters, so the test would catch a
        # char-count-vs-byte-count bug if one existed.
        decoded_for_sanity_check = orjson.loads(item_body_bytes)
        self.assertGreater(len(item_body_bytes), len(decoded_for_sanity_check["message"]))

        item_header = orjson.dumps({"type": "event", "length": len(item_body_bytes)})
        envelope = envelope_header + b"\n" + item_header + b"\n" + item_body_bytes

        with mock.patch("zerver.views.sentry.queue_event_on_commit") as mock_queue:
            response = self._post_envelope(envelope)

        self.assertEqual(response.status_code, 200)
        mock_queue.assert_called_once()
        _, event = mock_queue.call_args[0]
        called_body = base64.b64decode(event["body"])
        _header_line, rest = called_body.split(b"\n", 1)
        item_header_line, item_body_and_rest = rest.split(b"\n", 1)
        parsed_header = orjson.loads(item_header_line)
        length = parsed_header["length"]
        item_body = item_body_and_rest[:length]
        payload = orjson.loads(item_body)
        self.assertEqual(payload["message"], test_message)

    def test_non_event_item_type_skips_ip_injection(self) -> None:
        # IP injection only applies to "transaction" and "event" items;
        # other item types (e.g. "attachment") should pass through
        # completely unmodified, with no attempt to parse/mutate the body.
        envelope_header = orjson.dumps({"dsn": TEST_VALID_DSN})
        item_header = orjson.dumps({"type": "attachment"})
        item_body = b"arbitrary binary-ish payload, not even valid JSON"
        envelope = envelope_header + b"\n" + item_header + b"\n" + item_body + b"\n"

        with mock.patch("zerver.views.sentry.queue_event_on_commit") as mock_queue:
            response = self._post_envelope(envelope, remote_addr=TEST_USER_IP)

        self.assertEqual(response.status_code, 200)
        mock_queue.assert_called_once()
        _, event = mock_queue.call_args[0]
        called_body = base64.b64decode(event["body"])
        # Forwarded exactly as-is -- no parsing/mutation attempted for this item type.
        self.assertEqual(called_body, envelope)

    def test_ip_address_is_injected_before_enqueueing(self) -> None:
        # Verifies that the view enqueues via queue_event_on_commit
        # rather than calling sentry_request directly, and that IP
        # injection happens before enqueueing.
        envelope = build_envelope(user_ip="should-be-overwritten")

        with mock.patch("zerver.views.sentry.queue_event_on_commit") as mock_queue:
            response = self._post_envelope(envelope, remote_addr=TEST_USER_IP)

        self.assertEqual(response.status_code, 200)
        mock_queue.assert_called_once()
        queue_name, event = mock_queue.call_args[0]
        self.assertEqual(queue_name, "sentry_events")
        self.assertIn("/api/789/envelope/", event["url"])

        # Confirm IP injection happened before enqueueing.
        decoded_body = base64.b64decode(event["body"])
        _header_line, rest = decoded_body.split(b"\n", 1)
        _item_header_line, item_body_and_rest = rest.split(b"\n", 1)
        item_body = item_body_and_rest.split(b"\n", 1)[0]
        payload = orjson.loads(item_body)
        self.assertEqual(payload["user"]["ip_address"], TEST_USER_IP)

    def test_unparseable_item_body_is_forwarded_unmodified(self) -> None:
        # This is a valid DSN and header, but the payload is not a valid
        # JSON object, so the `orjson.loads(item_body)` call inside the
        # IP-injection block will raise, and `suppress(Exception)` should
        # cause the view to fall back to forwarding the original,
        # unmutated envelope bytes rather than dropping the report.
        garbage = (
            orjson.dumps({"dsn": TEST_VALID_DSN})
            + b"\n"
            + b'{"type": "event"}\n'
            + b"not valid JSON\n"
        )

        with mock.patch("zerver.views.sentry.queue_event_on_commit") as mock_queue:
            response = self._post_envelope(garbage)

        self.assertEqual(response.status_code, 200)
        mock_queue.assert_called_once()
        _, event = mock_queue.call_args[0]
        called_body = base64.b64decode(event["body"])
        # The key assertion: the fallback forwards the *original* body
        # byte-for-byte, not a partially-mutated or truncated version.
        self.assertEqual(called_body, garbage)

    def test_incorrect_length_falls_back_to_original_envelope(self) -> None:
        # Declares a "length" shorter than the actual body, so the
        # parser slices mid-JSON-object; orjson.loads should fail to
        # parse the truncated bytes, triggering the suppress(Exception)
        # fallback that forwards the original envelope unmodified.
        envelope = build_envelope(
            user_ip=TEST_USER_IP,
            explicit_length=True,
            length_override=5,
        )

        with mock.patch("zerver.views.sentry.queue_event_on_commit") as mock_queue:
            response = self._post_envelope(envelope)

        self.assertEqual(response.status_code, 200)
        mock_queue.assert_called_once()
        _, event = mock_queue.call_args[0]
        called_body = base64.b64decode(event["body"])
        self.assertEqual(called_body, envelope)


class SentryEventsWorkerTest(ZulipTestCase):
    """
    Tests for SentryEventsWorker.consume(), which decodes the queued
    event and forwards it to Sentry via sentry_request.
    """

    def test_consume_calls_sentry_request(self) -> None:
        worker = SentryEventsWorker()
        test_url = "https://o123456.ingest.sentry.io/api/789/envelope/"
        test_body = b"some envelope bytes"

        with mock.patch("zerver.worker.sentry_events.sentry_request") as mock_request:
            worker.consume(
                {
                    "url": test_url,
                    "body": base64.b64encode(test_body).decode("ascii"),
                }
            )

        mock_request.assert_called_once_with(test_url, test_body)

    def test_circuit_breaker_open_is_logged_and_swallowed(self) -> None:
        worker = SentryEventsWorker()

        with (
            mock.patch(
                "zerver.worker.sentry_events.sentry_request",
                side_effect=CircuitBreakerError("Sentry tunnel"),
            ),
            self.assertLogs(level="WARNING") as warning_logs,
        ):
            worker.consume(
                {
                    "url": "https://o123456.ingest.sentry.io/api/789/envelope/",
                    "body": base64.b64encode(b"test").decode("ascii"),
                }
            )

        self.assertIn(
            "WARNING:zerver.worker.sentry_events:Dropped a client exception due to circuit-breaking",
            warning_logs.output,
        )

    def test_request_exception_is_logged_and_swallowed(self) -> None:
        worker = SentryEventsWorker()

        with (
            mock.patch(
                "zerver.worker.sentry_events.sentry_request",
                side_effect=Timeout("simulated timeout"),
            ),
            self.assertLogs(level="ERROR") as error_logs,
        ):
            worker.consume(
                {
                    "url": "https://o123456.ingest.sentry.io/api/789/envelope/",
                    "body": base64.b64encode(b"test").decode("ascii"),
                }
            )

        self.assertIn(
            "ERROR:zerver.worker.sentry_events:simulated timeout",
            error_logs.output[0],
        )

    def test_open_circuit_for(self) -> None:
        self.assertTrue(open_circuit_for(ProxyError()))
        self.assertTrue(open_circuit_for(Timeout()))

        # 429 and 5xx trip the breaker
        for status_code in [429, 500, 503]:
            response = mock.MagicMock()
            response.status_code = status_code
            self.assertTrue(open_circuit_for(HTTPError(response=response)))

        # 4xx (other than 429) do not trip the breaker
        response = mock.MagicMock()
        response.status_code = 401
        self.assertFalse(open_circuit_for(HTTPError(response=response)))

        # Other exceptions do not trip the breaker
        self.assertFalse(open_circuit_for(ValueError()))
