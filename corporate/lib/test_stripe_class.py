import json
import operator
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from functools import wraps
from time import sleep
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
            with responses.RequestsMock() as request_mock:
                request_mock.add_passthru("https://api.stripe.com")
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
        r'"client_secret": "[\w]+"': '"client_secret": "NORMALIZED"',
        r'"url": "https://billing.stripe.com/p/session/test_([\w]+)"': "NORMALIZED",
        r'"url": "https://checkout.stripe.com/c/pay/cs_test_([\w#%]+)"': "NORMALIZED",
        r'"receipt_url": "https://pay.stripe.com/receipts/invoices/([\w-]+)\?s=[\w]+"': "NORMALIZED",
        r'"hosted_invoice_url": "https://invoice.stripe.com/i/acct_[\w]+/test_[\w,]+\?s=[\w]+"': '"hosted_invoice_url": "https://invoice.stripe.com/i/acct_NORMALIZED/test_NORMALIZED?s=ap"',
        r'"invoice_pdf": "https://pay.stripe.com/invoice/acct_[\w]+/test_[\w,]+/pdf\?s=[\w]+"': '"invoice_pdf": "https://pay.stripe.com/invoice/acct_NORMALIZED/test_NORMALIZED/pdf?s=ap"',
        r'"id": "([\w]+)"': "FILE_NAME",  # Replace with file name later.
        # Don't use (..) notation, since the matched strings may be small integers that will also match
        # elsewhere in the file
        r'"realm_id": "[0-9]+"': '"realm_id": "1"',
        r'"account_name": "[\w\s]+"': '"account_name": "NORMALIZED"',
    }

    # We'll replace cus_D7OT2jf5YAtZQ2 with something like cus_NORMALIZED0001
    pattern_translations.update(
        {
            rf"{prefix}_[A-Za-z0-9]{{{length}}}": f"{prefix}_NORMALIZED"
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
                file_content = file_content.replace(match, normalized_values[pattern][match])
        file_content = re.sub(r'(?<="risk_score": )(\d+)', "0", file_content)
        file_content = re.sub(r'(?<="times_redeemed": )(\d+)', "0", file_content)
        file_content = re.sub(
            r'(?<="idempotency_key": )"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
            '"00000000-0000-0000-0000-000000000000"',
            file_content,
        )
        # Dates
        file_content = re.sub(r'(?<="Date": )"(.* GMT)"', '"NORMALIZED DATETIME"', file_content)
        file_content = re.sub(r"[0-3]\d [A-Z][a-z]{2} 20[1-2]\d", "NORMALIZED DATE", file_content)
        # IP addresses
        file_content = re.sub(r'"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"', '"0.0.0.0"', file_content)
        # Unix timestamps
        file_content = re.sub(FIXTURE_NORMALIZE_REAL_TIMESTAMP_RE, ": 1000000000", file_content)

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


class StripeTestCase(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
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

    def send_stripe_webhook_events(
        self, most_recent_event: stripe.Event, must_have_event: str | None = None
    ) -> None:  # nocoverage
        # Stripe can delay events showing up in the Event list, so we
        # keep looking until we find the must_have_event.
        found_must_have_event = must_have_event is None
        num_of_attempts_to_look_for_must_have_event = 10
        while True:
            events_old_to_new = list(
                reversed(stripe.Event.list(ending_before=most_recent_event.id))
            )

            if len(events_old_to_new) == 0:
                if found_must_have_event:
                    break
                else:
                    num_of_attempts_to_look_for_must_have_event -= 1
                    if num_of_attempts_to_look_for_must_have_event == 0:
                        raise AssertionError(
                            f"Did not find expected event {must_have_event} after looking for it multiple times"
                        )
                    sleep(0.2)
                    continue

            for event in events_old_to_new:
                if event.type == must_have_event:
                    found_must_have_event = True

                self.send_stripe_webhook_event(event)
            most_recent_event = events_old_to_new[-1]

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
            # Store the event after which we pay the invoice so that we can
            # process all the events from this event to the latest.
            [last_event] = iter(stripe.Event.list(limit=1))

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
            last_event,
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
