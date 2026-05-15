"""Stripe billing class and test fixture generation

Record-and-replay fixture harness: ``mock_stripe`` intercepts every
``stripe.*`` call and either reads a saved JSON fixture (default,
offline) or hits the real Stripe test network (when
``--generate-stripe-fixtures`` is passed).

Fixtures live in ``corporate/tests/stripe_fixtures/``, one file
per call, named ``<test>--<Class>.<method>.<call_count>.json``
(e.g. ``upgrade_by_card--Customer.create.1.json``).

Two special cases keep ``Event.list`` fixture generation stable,
even though Stripe's view of "recent events" changes every run:

- ``StripeTestCase.pin_event_cursor`` returns the id of Stripe's
  most-recent event, used as the ``ending_before`` cursor for the
  next ``send_stripe_webhook_events`` poll. In regen, it bypasses the
  mock and calls Stripe directly (no fixture saved; the response is
  randomized). In replay it returns a sentinel id, and the mocked
  ``Event.list`` ignores ``ending_before``.
- ``send_stripe_webhook_events`` runs a cursor-stable polling loop in
  regen, accumulates the union of events seen across the run, keeps
  only ``HANDLED_STRIPE_EVENT_TYPES`` (matching the webhook view's
  dispatcher), and writes one canonical fixture per polling run.
  Replay reads that fixture once and delivers every event in it.

After each test, ``normalize_fixture_data`` rewrites every saved
fixture in place to collapse per-run variance (ids, timestamps, uuids,
etc.) so regenerating fixtures produces zero diff.  See
``FIXTURE_NORMALIZE_REAL_TIMESTAMP_RE`` for how Stripe-generated
timestamps are distinguished from test-supplied 2012 ones.

Prior-test events, that Stripe finalizes after our cursor pin, are
dropped during normalization: their ``data.object.customer`` matches
``cus_UNRECORDED`` (no recorded ``Customer.create``) while our test's
customer matches the fixture file name.

To regenerate fixtures for a single test::

    ./tools/test-backend --generate-stripe-fixtures \\
        corporate.tests.test_stripe.StripeTest.test_foo

Requires ``stripe_secret_key`` for a Stripe sandbox account set in
``zproject/dev-secrets.conf``.
"""

import json
import operator
import os
import re
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from time import monotonic, sleep
from typing import TYPE_CHECKING, Any, Literal, Optional, TypeVar, cast
from unittest import mock
from unittest.mock import Mock, patch

import orjson
import responses
import stripe
import time_machine
from django.conf import settings
from django.utils.crypto import get_random_string
from typing_extensions import ParamSpec, override

from corporate.lib.stripe import (
    STRIPE_API_VERSION,
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    get_latest_seat_count,
    is_free_trial_offer_enabled,
    sign_string,
    stripe_customer_has_credit_card_as_default_payment_method,
    stripe_get_customer,
)
from corporate.models.customers import Customer
from corporate.models.plans import CustomerPlan
from corporate.models.stripe_state import Invoice
from zerver.actions.users import do_deactivate_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.utils import assert_is_not_none
from zerver.models import UserProfile
from zerver.models.realms import get_realm

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

CallableT = TypeVar("CallableT", bound=Callable[..., Any])
ParamT = ParamSpec("ParamT")
ReturnT = TypeVar("ReturnT")

STRIPE_FIXTURES_DIR = "corporate/tests/stripe_fixtures"

# Match Unix timestamps in the 1500000000..1999999999 range (approximately
# 2017-07-14 through 2033-05-18) for Stripe "real-world" timestamps in
# fixtures we generate for tests.
FIXTURE_NORMALIZE_REAL_TIMESTAMP_RE = r": (1[5-9][0-9]{8})(?![0-9-])"


def stripe_fixture_path(
    decorated_function_name: str, mocked_function_name: str, call_count: int
) -> str:
    # Make the eventual filename a bit shorter, and also we conventionally
    # use test_* for the python test files
    decorated_function_name = decorated_function_name.removeprefix("test_")
    mocked_function_name = mocked_function_name.removeprefix("stripe.")
    return (
        f"{STRIPE_FIXTURES_DIR}/{decorated_function_name}--{mocked_function_name}.{call_count}.json"
    )


def fixture_files_for_function(decorated_function: CallableT) -> list[str]:  # nocoverage
    decorated_function_name = decorated_function.__name__
    decorated_function_name = decorated_function_name.removeprefix("test_")

    def call_order_key(filename: str) -> tuple[str, int]:
        # Filenames look like `upgrade_by_card--Customer.create.10.json`,
        # e.g., `<test>--<class>.<method>.<call_count>.json`. Split the
        # filename strings and sort such that a call_count of 2 comes
        # before 10, matching regen order.
        stem = filename[: -len(".json")]
        prefix, _, call_count = stem.rpartition(".")
        return (prefix, int(call_count))

    return [
        f"{STRIPE_FIXTURES_DIR}/{f}"
        for f in sorted(
            (
                f
                for f in os.listdir(STRIPE_FIXTURES_DIR)
                if f.startswith(decorated_function_name + "--")
            ),
            key=call_order_key,
        )
    ]


def generate_and_save_stripe_fixture(
    decorated_function_name: str, mocked_function_name: str, mocked_function: CallableT
) -> Callable[[Any, Any], Any]:  # nocoverage
    def _generate_and_save_stripe_fixture(*args: Any, **kwargs: Any) -> Any:
        # Note that mock is not the same as mocked_function, even though their
        # definitions look the same
        mock = operator.attrgetter(mocked_function_name)(sys.modules[__name__])
        fixture_path = stripe_fixture_path(
            decorated_function_name, mocked_function_name, mock.call_count
        )
        try:
            with _allow_stripe_api_passthru():
                # Talk to Stripe
                stripe_object = mocked_function(*args, **kwargs)
        except stripe.StripeError as e:
            with open(fixture_path, "w") as f:
                assert e.headers is not None
                error_dict = {**vars(e), "headers": dict(e.headers)}
                # Add http_body to the error_dict, since it's not included in the vars(e) output.
                # It should be same as e.json_body, but we include it since stripe expects it.
                if e.http_body is None:
                    assert e.json_body is not None
                    # Convert e.json_body to be a JSON string, since that's what stripe expects.
                    error_dict["http_body"] = json.dumps(e.json_body)
                # vars(e) includes a stripe.ErrorObject, which is a StripeObject subclass that
                # json.dumps doesn't know how to serialize. Since read_stripe_fixture only
                # consumes http_body, http_status and headers for StripeError test fixtures,
                # coercing the rest to strings via `default=str` is safe.
                f.write(
                    json.dumps(
                        error_dict,
                        indent=2,
                        separators=(",", ": "),
                        sort_keys=True,
                        default=str,
                    )
                    + "\n"
                )
            raise
        with open(fixture_path, "w") as f:
            if stripe_object is not None:
                f.write(str(stripe_object) + "\n")
            else:
                f.write("{}\n")
        return stripe_object

    return _generate_and_save_stripe_fixture


def read_stripe_fixture(
    decorated_function_name: str, mocked_function_name: str
) -> Callable[[Any, Any], Any]:
    def _read_stripe_fixture(*args: Any, **kwargs: Any) -> Any:
        mock = operator.attrgetter(mocked_function_name)(sys.modules[__name__])
        fixture_path = stripe_fixture_path(
            decorated_function_name, mocked_function_name, mock.call_count
        )
        with open(fixture_path, "rb") as f:
            fixture = orjson.loads(f.read())
        # Check for StripeError fixtures
        if "json_body" in fixture:
            requester = stripe._api_requestor._APIRequestor()
            # This function will raise the relevant StripeError according to the fixture
            requester._interpret_response(
                fixture["http_body"], fixture["http_status"], fixture["headers"], "V1"
            )
        return stripe.convert_to_stripe_object(fixture)

    return _read_stripe_fixture


def delete_fixture_data(decorated_function: CallableT) -> None:  # nocoverage
    for fixture_file in fixture_files_for_function(decorated_function):
        os.remove(fixture_file)


def normalize_fixture_data(decorated_function: CallableT) -> None:  # nocoverage
    # stripe ids are all of the form cus_D7OT2jf5YAtZQ2
    id_lengths = [
        ("test", 12),
        ("cus", 14),
        ("prod", 14),
        ("req", 14),
        ("si", 14),
        ("sli", 14),
        ("sub", 14),
        ("acct", 16),
        ("card", 24),
        ("ch", 24),
        ("ii", 24),
        ("il", 24),
        ("in", 24),
        ("pi", 24),
        ("price", 24),
        ("src", 24),
        ("src_client_secret", 24),
        ("tok", 24),
        ("txn", 24),
        ("invst", 26),
        ("rcpt", 31),
        ("seti", 24),
        ("pm", 24),
        ("setatt", 24),
        ("bpc", 24),
        ("bps", 24),
    ]

    # We'll replace "invoice_prefix": "A35BC4Q" with something like "invoice_prefix": "NORMA01"
    # For patterns whose matches can be too generic like `[0-9]+`, include matching field in the translation
    # to avoid it replacing other occurrences of the pattern. See `exp_month` for example.
    pattern_translations = {
        r'"exp_month": [0-9]+': '"exp_month": 1',
        r'"exp_year": [0-9]+': '"exp_year": 9999',
        r'"postal_code": "[0-9]+"': '"postal_code": "12345"',
        r'"invoice_prefix": "[A-Za-z0-9]{7,8}"': '"invoice_prefix": "NORMALIZED"',
        r'"fingerprint": "[A-Za-z0-9]{16}"': '"fingerprint": "NORMALIZED"',
        r'"number": "[A-Za-z0-9]{7,8}-[A-Za-z0-9]{4}"': '"number": "NORMALIZED"',
        r'"address": "[A-Za-z0-9]{9}-test_[A-Za-z0-9]{12}"': '"address": "000000000-test_NORMALIZED"',
        r'"url": "https://billing.stripe.com/p/session/test_([\w]+)"': "NORMALIZED",
        r'"url": "https://checkout.stripe.com/c/pay/cs_test_([\w#%]+)"': "NORMALIZED",
        r'"receipt_url": "https://pay.stripe.com/receipts/invoices/([\w-]+)\?s=[\w]+"': "NORMALIZED",
        r'"hosted_invoice_url": "https://invoice.stripe.com/i/acct_[\w]+/test_[\w,]+\?s=[\w]+"': '"hosted_invoice_url": "https://invoice.stripe.com/i/acct_NORMALIZED/test_NORMALIZED?s=ap"',
        r'"invoice_pdf": "https://pay.stripe.com/invoice/acct_[\w]+/test_[\w,]+/pdf\?s=[\w]+"': '"invoice_pdf": "https://pay.stripe.com/invoice/acct_NORMALIZED/test_NORMALIZED/pdf?s=ap"',
        r'"id": "([\w]+)"': "FILE_NAME",  # Replace with file name later.
        # Don't use (..) notation, since the matched strings may be small integers that will also match
        # elsewhere in the file
        r'"realm_id": "[0-9]+"': '"realm_id": "1"',
        r'"account_name": "[^"]+"': '"account_name": "NORMALIZED"',
    }

    # Customer IDs whose ``Customer.create`` we never recorded get the
    # ``cus_UNRECORDED`` suffix as the ``Event.list`` check below uses
    # that exact suffix to filter prior-test customers' webhook events.
    # Other ID placeholders use a generic ``<prefix>_NORMALIZED``, as
    # there's no load-bearing meaning and just a "this ID was redacted"
    # marker is sufficient. Customer IDs we did record are re-replaced
    # with their fixture filename by the ``"id":`` pass below.
    pattern_translations.update(
        {
            rf"{prefix}_[A-Za-z0-9]{{{length}}}": (
                f"{prefix}_UNRECORDED" if prefix == "cus" else f"{prefix}_NORMALIZED"
            )
            for prefix, length in id_lengths
        }
    )
    normalized_values: dict[str, dict[str, str]] = {pattern: {} for pattern in pattern_translations}
    for fixture_file in fixture_files_for_function(decorated_function):
        with open(fixture_file) as f:
            file_content = f.read()
        for pattern, translation in pattern_translations.items():
            for match in re.findall(pattern, file_content):
                if match not in normalized_values[pattern]:
                    if pattern.startswith('"id": "'):
                        # Set file name as ID.
                        normalized_values[pattern][match] = fixture_file.split("/")[-1]
                    else:
                        normalized_values[pattern][match] = translation
            # Stripe IDs leak across files: ``cus_XYZ`` is an ``"id"`` value in
            # ``Customer.create`` and a ``"customer"`` value in every event
            # referencing it. Sweep every mapping this pattern has accumulated so
            # far, including ones registered while normalizing an earlier fixture,
            # not just the matches ``findall`` returned for this file.
            for original, normalized in normalized_values[pattern].items():
                file_content = file_content.replace(original, normalized)
        file_content = re.sub(r'(?<="risk_score": )(\d+)', "0", file_content)
        file_content = re.sub(r'(?<="times_redeemed": )(\d+)', "0", file_content)
        file_content = re.sub(
            r'"authorization_code": "[0-9]+"', '"authorization_code": "000000"', file_content
        )
        file_content = re.sub(
            r'"network_transaction_id": "[0-9]+"',
            '"network_transaction_id": "000000000000000"',
            file_content,
        )
        # Idempotency keys appear as a lowercase JSON field ("idempotency_key") and
        # as a response-header field ("Idempotency-Key"). Stripe assigns a fresh
        # uuid for both on every call.
        file_content = re.sub(
            r'(?<=")(idempotency_key|Idempotency-Key)": "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"',
            r'\1": "00000000-0000-0000-0000-000000000000"',
            file_content,
        )
        # client_secret fields appear both at the JSON top-level of fixtures and
        # inside doubly-escaped strings in error fixtures. Match both forms.
        file_content = re.sub(
            r'(\\?")client_secret(\\?": \\?")[^"\\]+(\\?")',
            r"\1client_secret\2NORMALIZED\3",
            file_content,
        )
        # Stripe's CSP / Reporting headers carry a per-response random
        # ``?q=<token>`` that's unrelated to anything we test.
        file_content = re.sub(r"\?q=[\w-]+", "?q=NORMALIZED", file_content)
        # The ``webhooks_delivered_at`` field is null or a Unix timestamp,
        # depending on when Stripe finishes delivering webhooks. We handle
        # this race in fixture generation by normalizing on null.
        file_content = re.sub(
            r'"webhooks_delivered_at": [0-9]+', '"webhooks_delivered_at": null', file_content
        )
        # The ``pending_webhooks`` field ticks down as Stripe delivers
        # webhooks. We handle this inconsistency in fixture generation by
        # normalizing on 0.
        file_content = re.sub(r'"pending_webhooks": [0-9]+', '"pending_webhooks": 0', file_content)
        # Dates
        file_content = re.sub(r'(?<="Date": )"(.* GMT)"', '"NORMALIZED DATETIME"', file_content)
        file_content = re.sub(r"[0-3]\d [A-Z][a-z]{2} 20[1-2]\d", "NORMALIZED DATE", file_content)
        # IP addresses
        file_content = re.sub(r'"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"', '"0.0.0.0"', file_content)
        # Unix timestamps
        file_content = re.sub(FIXTURE_NORMALIZE_REAL_TIMESTAMP_RE, ": 1000000000", file_content)

        # Stripe returns events with the same ``created`` second in
        # non-deterministic order across runs. Sort the ``data`` array
        # by normalized-event content so the fixture is byte-stable.
        # Drop any event whose ``data.object.customer`` is
        # ``cus_UNRECORDED`` (i.e., the placeholder for any customer
        # we never recorded a ``Customer.create`` for), which for
        # ``Event.list`` means a prior-test customer that Stripe
        # finalized a webhook for after we anchored our cursor (and the
        # count of such leaked events varies regen to regen). The
        # current test's customer is re-replaced with the file-name
        # test string, so the check unambiguously distinguishes the two.
        if re.search(r"--Event\.list\.\d+\.json$", fixture_file):
            fixture_data = json.loads(file_content)
            fixture_data["data"] = sorted(
                (
                    e
                    for e in fixture_data["data"]
                    if not (e.get("data", {}).get("object") or {})
                    .get("customer", "")
                    .endswith("_UNRECORDED")
                ),
                key=lambda e: json.dumps(e, sort_keys=True),
            )
            file_content = json.dumps(fixture_data, indent=2, sort_keys=True) + "\n"

        with open(fixture_file, "w") as f:
            f.write(file_content)


MOCKED_STRIPE_FUNCTION_NAMES = [
    f"stripe.{name}"
    for name in [
        "billing_portal.Configuration.create",
        "billing_portal.Session.create",
        "checkout.Session.create",
        "checkout.Session.list",
        "Charge.create",
        "Charge.list",
        "Coupon.create",
        "Customer.create",
        "Customer.create_balance_transaction",
        "Customer.list_balance_transactions",
        "Customer.retrieve",
        "Customer.save",
        "Customer.list",
        "Customer.modify",
        "Event.list",
        "Invoice.create",
        "Invoice.finalize_invoice",
        "Invoice.list",
        "Invoice.pay",
        "Invoice.refresh",
        "Invoice.retrieve",
        "Invoice.void_invoice",
        "InvoiceItem.create",
        "InvoiceItem.list",
        "PaymentMethod.attach",
        "PaymentMethod.create",
        "PaymentMethod.detach",
        "PaymentMethod.list",
        "Plan.create",
        "Product.create",
        "SetupIntent.create",
        "SetupIntent.list",
        "SetupIntent.retrieve",
        "Subscription.create",
        "Subscription.delete",
        "Subscription.retrieve",
        "Subscription.save",
        "Token.create",
    ]
]


def mock_stripe(
    generate: bool = settings.GENERATE_STRIPE_FIXTURES,
) -> Callable[[Callable[ParamT, ReturnT]], Callable[ParamT, ReturnT]]:
    def _mock_stripe(decorated_function: Callable[ParamT, ReturnT]) -> Callable[ParamT, ReturnT]:
        generate_fixture = generate
        if generate_fixture:  # nocoverage
            assert stripe.api_key
        for mocked_function_name in MOCKED_STRIPE_FUNCTION_NAMES:
            mocked_function = operator.attrgetter(mocked_function_name)(sys.modules[__name__])
            if generate_fixture:
                side_effect = generate_and_save_stripe_fixture(
                    decorated_function.__name__, mocked_function_name, mocked_function
                )  # nocoverage
            else:
                side_effect = read_stripe_fixture(decorated_function.__name__, mocked_function_name)
            decorated_function = patch(
                mocked_function_name,
                side_effect=side_effect,
                autospec=mocked_function_name.endswith(".refresh"),
            )(decorated_function)

        @wraps(decorated_function)
        def wrapped(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
            if generate_fixture:  # nocoverage
                delete_fixture_data(decorated_function)
                val = decorated_function(*args, **kwargs)
                normalize_fixture_data(decorated_function)
                return val
            else:
                return decorated_function(*args, **kwargs)

        return wrapped

    return _mock_stripe


# Stripe event types that ``corporate/views/webhook.py`` actually
# dispatches on. Everything else is a 200-no-op for the webhook view,
# and the per-event cardinality of those unhandled types
# (``invoice.updated`` in particular) drifts regen to regen as Stripe's
# internal invoice state machine churns, which means including them in
# fixtures would make ``Event.list`` non-byte-stable.
HANDLED_STRIPE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "checkout.session.completed",
        "invoice.paid",
    }
)


# Captured at module load before ``mock_stripe`` installs any patch, so
# ``pin_event_cursor`` and the regen polling loop can call the real
# ``Event.list`` without advancing the per-call fixture count.
_REAL_STRIPE_EVENT_LIST = stripe.Event.list


@contextmanager
def _allow_stripe_api_passthru() -> Iterator[None]:  # nocoverage
    """Zulip's test harness blocks outgoing HTTP by default; allow the
    Stripe API through for the regen-time calls that bypass the mock."""
    with responses.RequestsMock() as request_mock:
        request_mock.add_passthru("https://api.stripe.com")
        yield


class StripeTestCase(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        # Per-test counter so each ``send_stripe_webhook_events`` run
        # writes its canonical fixture at a predictable ``Event.list``
        # call count (run 1 at .1, run 2 at .2, etc.).
        self._stripe_polling_runs = 0
        realm = get_realm("zulip")

        # Explicitly limit our active users to 6 regular users,
        # to make seat_count less prone to changes in our test data.
        # We also keep a guest user and a bot to make the data
        # slightly realistic.
        active_emails = [
            self.example_email("AARON"),
            self.example_email("cordelia"),
            self.example_email("hamlet"),
            self.example_email("iago"),
            self.example_email("othello"),
            self.example_email("desdemona"),
            self.example_email("polonius"),  # guest
            self.example_email("default_bot"),  # bot
        ]

        # Deactivate all users in our realm that aren't in our whitelist.
        for user_profile in UserProfile.objects.filter(realm_id=realm.id).exclude(
            delivery_email__in=active_emails
        ):
            do_deactivate_user(user_profile, acting_user=None)

        # sanity check our 8 expected users are active
        self.assertEqual(
            UserProfile.objects.filter(realm=realm, is_active=True).count(),
            8,
        )

        # Make sure we have active users outside our realm (to make
        # sure relevant queries restrict on realm).
        self.assertEqual(
            UserProfile.objects.exclude(realm=realm).filter(is_active=True).count(),
            10,
        )

        # Our seat count excludes our guest user and bot, and
        # we want this to be predictable for certain tests with
        # arithmetic calculations.
        self.assertEqual(get_latest_seat_count(realm), 6)
        self.seat_count = 6
        self.signed_seat_count, self.salt = sign_string(str(self.seat_count))

        # Test dates are deliberately set in 2012 so their Unix timestamps
        # stay below 1.5e9; see FIXTURE_NORMALIZE_REAL_TIMESTAMP_RE.
        self.now = datetime(2012, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        self.next_month = datetime(2012, 2, 2, 3, 4, 5, tzinfo=timezone.utc)
        self.next_year = datetime(2013, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

        # Add hamlet in `can_manage_billing_group` for testing.
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        self.set_user_role(hamlet, UserProfile.ROLE_REALM_OWNER)
        self.set_user_role(iago, UserProfile.ROLE_REALM_OWNER)

        self.billing_session: (
            RealmBillingSession | RemoteRealmBillingSession | RemoteServerBillingSession
        ) = RealmBillingSession(user=hamlet, realm=realm)

    def get_signed_seat_count_from_response(self, response: "TestHttpResponse") -> str | None:
        match = re.search(r"name=\"signed_seat_count\" value=\"(.+)\"", response.content.decode())
        return match.group(1) if match else None

    def get_salt_from_response(self, response: "TestHttpResponse") -> str | None:
        match = re.search(r"name=\"salt\" value=\"(\w+)\"", response.content.decode())
        return match.group(1) if match else None

    def get_test_card_token(
        self,
        attaches_to_customer: bool,
        charge_succeeds: bool | None = None,
        card_provider: str | None = None,
    ) -> str:
        if attaches_to_customer:
            assert charge_succeeds is not None
            if charge_succeeds:
                if card_provider == "visa":
                    return "tok_visa"
                if card_provider == "mastercard":
                    return "tok_mastercard"
                raise AssertionError("Unreachable code path")
            else:
                return "tok_chargeCustomerFail"
        else:
            return "tok_visa_chargeDeclined"

    def assert_details_of_valid_session_from_event_status_endpoint(
        self, stripe_session_id: str, expected_details: dict[str, Any]
    ) -> None:
        json_response = self.client_billing_get(
            "/billing/event/status",
            {
                "stripe_session_id": stripe_session_id,
            },
        )
        response_dict = self.assert_json_success(json_response)
        self.assertEqual(response_dict["session"], expected_details)

    def assert_details_of_valid_invoice_payment_from_event_status_endpoint(
        self,
        stripe_invoice_id: str,
        expected_details: dict[str, Any],
    ) -> None:
        json_response = self.client_billing_get(
            "/billing/event/status",
            {
                "stripe_invoice_id": stripe_invoice_id,
            },
        )
        response_dict = self.assert_json_success(json_response)
        self.assertEqual(response_dict["stripe_invoice"], expected_details)

    def trigger_stripe_checkout_session_completed_webhook(
        self,
        token: str,
    ) -> None:
        customer = self.billing_session.get_customer()
        assert customer is not None
        customer_stripe_id = customer.stripe_customer_id
        assert customer_stripe_id is not None
        [checkout_setup_intent] = iter(
            stripe.SetupIntent.list(customer=customer_stripe_id, limit=1)
        )

        # Create a PaymentMethod using the token
        payment_method = stripe.PaymentMethod.create(
            type="card",
            card={
                "token": token,
            },
            billing_details={
                "name": "John Doe",
                "address": {
                    "line1": "123 Main St",
                    "city": "San Francisco",
                    "state": "CA",
                    "postal_code": "94105",
                    "country": "US",
                },
            },
        )
        assert isinstance(checkout_setup_intent.customer, str)
        assert checkout_setup_intent.metadata is not None
        assert checkout_setup_intent.usage in {"off_session", "on_session"}
        usage = cast(
            Literal["off_session", "on_session"], checkout_setup_intent.usage
        )  # https://github.com/python/mypy/issues/12535
        stripe_setup_intent = stripe.SetupIntent.create(
            payment_method=payment_method.id,
            confirm=True,
            payment_method_types=checkout_setup_intent.payment_method_types,
            customer=checkout_setup_intent.customer,
            metadata=checkout_setup_intent.metadata,
            usage=usage,
        )
        [stripe_session] = iter(stripe.checkout.Session.list(customer=customer_stripe_id, limit=1))
        stripe_session_dict = stripe_session.to_dict(for_json=True)
        stripe_session_dict["setup_intent"] = stripe_setup_intent.id

        event_payload = {
            "id": f"evt_{get_random_string(24)}",
            "object": "event",
            "data": {"object": stripe_session_dict},
            "type": "checkout.session.completed",
            "api_version": STRIPE_API_VERSION,
        }

        self._post_webhook_event(event_payload, event_label="checkout.session.completed")

    def send_stripe_webhook_event(self, event: stripe.Event) -> None:
        self._post_webhook_event(event.to_dict(for_json=True), event_label=event.type)

    def _post_webhook_event(self, payload: dict[str, Any], event_label: str) -> None:
        response = self.client_post("/stripe/webhook/", payload, content_type="application/json")
        assert response.status_code == 200, (
            f"/stripe/webhook/ returned {response.status_code} for {event_label} "
            f"event {payload.get('id')!r}: {response.content.decode(errors='replace')!r}"
        )

    def pin_event_cursor(self) -> str:
        """Return the id of Stripe's most-recent event, anchoring the
        next ``send_stripe_webhook_events`` poll.

        In regen this hits the real ``Event.list``; in replay the
        returned id is inert because the mocked ``Event.list`` ignores
        ``ending_before``."""
        if not settings.GENERATE_STRIPE_FIXTURES:
            return "evt_normalized_cursor_lookup"
        with _allow_stripe_api_passthru():  # nocoverage
            [event] = _REAL_STRIPE_EVENT_LIST(limit=1)
            return event.id

    def send_stripe_webhook_events(self, cursor: str, must_have_event: str | None = None) -> None:
        # Stripe's ``Event.list`` is eventually consistent, but a freshly-created
        # event may not appear under an ``ending_before=cursor`` query right away.
        # Pin the cursor and dedupe locally so late arrivals still surface on a
        # subsequent poll. Regen and replay of fixtures need different termination
        # strategies.
        assert must_have_event is None or must_have_event in HANDLED_STRIPE_EVENT_TYPES, (
            f"Test waits on {must_have_event}, which is not in HANDLED_STRIPE_EVENT_TYPES"
        )
        if settings.GENERATE_STRIPE_FIXTURES:
            self._poll_stripe_events_for_regen(cursor, must_have_event)  # nocoverage
        else:
            self._replay_stripe_events_from_fixtures(cursor, must_have_event)

    def _poll_stripe_events_for_regen(
        self, cursor: str, must_have_event: str | None
    ) -> None:  # nocoverage
        # Bypass the ``Event.list`` mock during polling, because we don't want a
        # fixture per HTTP call (the grace-period loop produces many nearly
        # identical ones that just churn between regens). Instead, we accumulate
        # the union of events seen across the run and write one canonical fixture
        # at the end.  Stripe's ``ending_before=cursor`` already excludes events
        # older than the pin, and ``normalize_fixture_data`` drops prior-test
        # events that leak through.
        deadline_seconds = 60.0
        grace_period_seconds = 3.0
        poll_interval_seconds = 0.2

        found_must_have_event = must_have_event is None
        hard_deadline = monotonic() + deadline_seconds
        last_progress = monotonic()
        seen_event_ids: set[str] = set()
        events_in_order: list[stripe.Event] = []
        while True:
            if monotonic() >= hard_deadline:
                if not found_must_have_event:
                    raise AssertionError(
                        f"Did not find expected event {must_have_event} within {deadline_seconds}s"
                    )
                break
            if found_must_have_event and monotonic() - last_progress >= grace_period_seconds:
                break

            with _allow_stripe_api_passthru():
                events_old_to_new = [
                    e
                    for e in reversed(_REAL_STRIPE_EVENT_LIST(ending_before=cursor, limit=100))
                    if e.type in HANDLED_STRIPE_EVENT_TYPES
                ]
            new_events = [e for e in events_old_to_new if e.id not in seen_event_ids]

            if not new_events:
                sleep(poll_interval_seconds)
                continue

            last_progress = monotonic()
            for event in new_events:
                seen_event_ids.add(event.id)
                events_in_order.append(event)
                if event.type == must_have_event:
                    found_must_have_event = True
                self.send_stripe_webhook_event(event)

        self._write_polling_run_fixtures(events_in_order)

    def _write_polling_run_fixtures(self, events: list[stripe.Event]) -> None:  # nocoverage
        """Persist the union of events for replay.  See
        ``_poll_stripe_events_for_regen`` for why we bypass the per-call
        mock."""
        self._stripe_polling_runs += 1
        path = stripe_fixture_path(
            self._testMethodName, "stripe.Event.list", self._stripe_polling_runs
        )
        with open(path, "w") as f:
            f.write(
                json.dumps(
                    {
                        "data": [json.loads(str(e)) for e in events],
                        "has_more": False,
                        "object": "list",
                        "url": "/v1/events",
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )

    def _replay_stripe_events_from_fixtures(self, cursor: str, must_have_event: str | None) -> None:
        # One ``Event.list`` call returns the next recorded canonical fixture,
        # and we deliver every event in it. The mock ignores ``ending_before``
        # and ``limit``. There is no unstable-event filter here, as the fixture
        # was already filtered during regen. Don't reverse because the fixture's
        # ``data`` array is in dispatch order (i.e., the order that
        # ``_poll_stripe_events_for_regen`` accumulated events), not Stripe's
        # newest-first API convention.
        events = list(stripe.Event.list(ending_before=cursor, limit=100))
        for event in events:
            self.send_stripe_webhook_event(event)
        if must_have_event is not None:
            assert any(e.type == must_have_event for e in events), (
                f"Replay fixture missing expected event {must_have_event}"
            )

    def add_card_to_customer_for_upgrade(self, charge_succeeds: bool = True) -> None:
        start_session_json_response = self.client_billing_post(
            "/upgrade/session/start_card_update_session",
            {
                "tier": 1,
            },
        )
        response_dict = self.assert_json_success(start_session_json_response)
        stripe_session_id = response_dict["stripe_session_id"]
        self.assert_details_of_valid_session_from_event_status_endpoint(
            stripe_session_id,
            {
                "type": "card_update_from_upgrade_page",
                "status": "created",
                "is_manual_license_management_upgrade_session": False,
                "tier": 1,
            },
        )
        self.trigger_stripe_checkout_session_completed_webhook(
            self.get_test_card_token(
                attaches_to_customer=True,
                charge_succeeds=charge_succeeds,
                card_provider="visa",
            )
        )
        self.assert_details_of_valid_session_from_event_status_endpoint(
            stripe_session_id,
            {
                "type": "card_update_from_upgrade_page",
                "status": "completed",
                "is_manual_license_management_upgrade_session": False,
                "tier": 1,
                "event_handler": {"status": "succeeded"},
            },
        )

    def upgrade(
        self,
        invoice: bool = False,
        talk_to_stripe: bool = True,
        upgrade_page_response: Optional["TestHttpResponse"] = None,
        del_args: Sequence[str] = [],
        dont_confirm_payment: bool = False,
        **kwargs: Any,
    ) -> "TestHttpResponse":
        if upgrade_page_response is None:
            tier = kwargs.get("tier")
            upgrade_url = f"{self.billing_session.billing_base_url}/upgrade/"
            if tier:
                upgrade_url += f"?tier={tier}"
            if self.billing_session.billing_base_url:
                upgrade_page_response = self.client_get(upgrade_url, {}, subdomain="selfhosting")
            else:
                upgrade_page_response = self.client_get(upgrade_url, {})
        params: dict[str, Any] = {
            "schedule": "annual",
            "signed_seat_count": self.get_signed_seat_count_from_response(upgrade_page_response),
            "salt": self.get_salt_from_response(upgrade_page_response),
        }
        if invoice:  # send_invoice
            params.update(
                billing_modality="send_invoice",
                licenses=kwargs.get("licenses", 123),
            )
        else:  # charge_automatically
            params.update(
                billing_modality="charge_automatically",
                license_management="automatic",
            )

        remote_server_plan_start_date = kwargs.get("remote_server_plan_start_date")
        if remote_server_plan_start_date:
            params.update(
                remote_server_plan_start_date=remote_server_plan_start_date,
            )

        params.update(kwargs)
        for key in del_args:
            params.pop(key, None)

        if talk_to_stripe:
            # Anchor a cursor here so we can replay all subsequent events
            # (from the upgrade flow and the invoice paid webhook).
            cursor = self.pin_event_cursor()

        existing_customer = self.billing_session.customer_plan_exists()
        upgrade_json_response = self.client_billing_post("/billing/upgrade", params)

        if upgrade_json_response.status_code != 200 or dont_confirm_payment:
            # Return early if the upgrade request failed.
            return upgrade_json_response

        is_self_hosted_billing = not isinstance(self.billing_session, RealmBillingSession)
        customer = self.billing_session.get_customer()
        assert customer is not None
        if not talk_to_stripe or (
            is_free_trial_offer_enabled(is_self_hosted_billing)
            and
            # Free trial is not applicable for existing customers.
            not existing_customer
        ):
            # Upgrade already happened for free trial, invoice realms or schedule
            # upgrade for customers on complimentary access plan.
            return upgrade_json_response

        last_sent_invoice = Invoice.objects.last()
        assert last_sent_invoice is not None

        response_dict = self.assert_json_success(upgrade_json_response)
        self.assertEqual(
            response_dict["stripe_invoice_id"],
            last_sent_invoice.stripe_invoice_id,
        )

        # Verify that the Invoice was sent.
        # Invoice is only marked as paid in our db after we receive `invoice.paid` event.
        self.assert_details_of_valid_invoice_payment_from_event_status_endpoint(
            last_sent_invoice.stripe_invoice_id,
            {"status": "sent"},
        )

        if invoice:
            assert talk_to_stripe is True
            # Mark the invoice as paid via stripe with the `invoice.paid` event.
            stripe.Invoice.pay(last_sent_invoice.stripe_invoice_id, paid_out_of_band=True)

        self.send_stripe_webhook_events(
            cursor,
            must_have_event="invoice.paid" if invoice else None,
        )
        return upgrade_json_response

    def add_card_and_upgrade(
        self, user: UserProfile | None = None, **kwargs: Any
    ) -> stripe.Customer:
        # Add card
        with time_machine.travel(self.now, tick=False):
            self.add_card_to_customer_for_upgrade()

        # Check that we correctly created a Customer object in Stripe
        if user is not None:
            stripe_customer = stripe_get_customer(
                assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
            )
        else:
            customer = self.billing_session.get_customer()
            assert customer is not None
            stripe_customer = stripe_get_customer(assert_is_not_none(customer.stripe_customer_id))
        self.assertTrue(stripe_customer_has_credit_card_as_default_payment_method(stripe_customer))

        with time_machine.travel(self.now, tick=False):
            response = self.upgrade(**kwargs)
        self.assert_json_success(response)

        return stripe_customer

    # Upgrade without talking to Stripe
    def local_upgrade(
        self,
        licenses: int,
        automanage_licenses: bool,
        billing_schedule: int,
        charge_automatically: bool,
        free_trial: bool,
        stripe_invoice_paid: bool = False,
    ) -> None:
        class StripeMock(Mock):
            def __init__(self, depth: int = 1) -> None:
                super().__init__(spec=stripe.Card)
                self.id = "cus_123"
                self.created = "1000"
                self.last4 = "4242"

        def upgrade_func(
            licenses: int,
            automanage_licenses: bool,
            billing_schedule: int,
            charge_automatically: bool,
            free_trial: bool,
            stripe_invoice_paid: bool,
            *mock_args: Any,
        ) -> Any:
            hamlet = self.example_user("hamlet")
            billing_session = RealmBillingSession(hamlet)
            return billing_session.process_initial_upgrade(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                licenses=licenses,
                automanage_licenses=automanage_licenses,
                billing_schedule=billing_schedule,
                charge_automatically=charge_automatically,
                free_trial=free_trial,
                stripe_invoice_paid=stripe_invoice_paid,
            )

        for mocked_function_name in MOCKED_STRIPE_FUNCTION_NAMES:
            upgrade_func = patch(mocked_function_name, return_value=StripeMock())(upgrade_func)
        upgrade_func(
            licenses,
            automanage_licenses,
            billing_schedule,
            charge_automatically,
            free_trial,
            stripe_invoice_paid,
        )

    def setup_mocked_stripe(self, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> Mock:
        with patch.multiple("stripe", Invoice=mock.DEFAULT, InvoiceItem=mock.DEFAULT) as mocked:
            mocked["Invoice"].create.return_value = mock.Mock()
            mocked["Invoice"].finalize_invoice.return_value = mock.Mock()
            mocked["InvoiceItem"].create.return_value = mock.Mock()
            callback(*args, **kwargs)
            return mocked

    def client_billing_get(self, url_suffix: str, info: Mapping[str, Any] = {}) -> Any:
        url = f"/json{self.billing_session.billing_base_url}" + url_suffix
        if self.billing_session.billing_base_url:
            response = self.client_get(url, info, subdomain="selfhosting")
        else:
            response = self.client_get(url, info)
        return response

    def client_billing_post(self, url_suffix: str, info: Mapping[str, Any] = {}) -> Any:
        url = f"/json{self.billing_session.billing_base_url}" + url_suffix
        if self.billing_session.billing_base_url:
            response = self.client_post(url, info, subdomain="selfhosting")
        else:
            response = self.client_post(url, info)
        return response

    def client_billing_patch(self, url_suffix: str, info: Mapping[str, Any] = {}) -> Any:
        url = f"/json{self.billing_session.billing_base_url}" + url_suffix
        if self.billing_session.billing_base_url:
            response = self.client_patch(url, info, subdomain="selfhosting")
        else:
            response = self.client_patch(url, info)
        return response
