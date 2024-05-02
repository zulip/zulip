import itertools
import json
import operator
import os
import re
import sys
import typing
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
from unittest import mock
from unittest.mock import MagicMock, Mock, patch

import orjson
import responses
import stripe
import time_machine
from django.conf import settings
from django.core import signing
from django.test import override_settings
from django.urls.resolvers import get_resolver
from django.utils.crypto import get_random_string
from django.utils.timezone import now as timezone_now
from typing_extensions import ParamSpec, override

from corporate.lib.activity import get_realms_with_default_discount_dict
from corporate.lib.stripe import (
    DEFAULT_INVOICE_DAYS_UNTIL_DUE,
    MAX_INVOICED_LICENSES,
    MIN_INVOICED_LICENSES,
    STRIPE_API_VERSION,
    AuditLogEventType,
    BillingError,
    BillingSessionAuditLogEventError,
    InitialUpgradeRequest,
    InvalidBillingScheduleError,
    InvalidTierError,
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    StripeCardError,
    SupportRequestError,
    SupportType,
    SupportViewRequest,
    add_months,
    catch_stripe_errors,
    compute_plan_parameters,
    customer_has_credit_card_as_default_payment_method,
    customer_has_last_n_invoices_open,
    do_deactivate_remote_server,
    do_reactivate_remote_server,
    downgrade_small_realms_behind_on_payments_as_needed,
    get_latest_seat_count,
    get_plan_renewal_or_end_date,
    get_price_per_license,
    invoice_plans_as_needed,
    is_free_trial_offer_enabled,
    is_realm_on_free_trial,
    next_month,
    sign_string,
    stripe_customer_has_credit_card_as_default_payment_method,
    stripe_get_customer,
    unsign_string,
)
from corporate.models import (
    Customer,
    CustomerPlan,
    CustomerPlanOffer,
    Event,
    Invoice,
    LicenseLedger,
    ZulipSponsorshipRequest,
    get_current_plan_by_customer,
    get_current_plan_by_realm,
    get_customer_by_realm,
    get_customer_by_remote_realm,
)
from corporate.tests.test_remote_billing import RemoteRealmBillingTestCase, RemoteServerTestCase
from corporate.views.remote_billing_page import generate_confirmation_link_for_server_deactivation
from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import (
    do_activate_mirror_dummy_user,
    do_create_user,
    do_reactivate_user,
)
from zerver.actions.realm_settings import do_deactivate_realm, do_reactivate_realm
from zerver.actions.users import do_deactivate_user
from zerver.lib.remote_server import send_server_data_to_push_bouncer
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.utils import assert_is_not_none
from zerver.models import Message, Realm, RealmAuditLog, Recipient, UserProfile
from zerver.models.realms import get_realm
from zerver.models.users import get_system_bot
from zilencer.lib.remote_counts import MissingDataError
from zilencer.models import (
    RemoteRealm,
    RemoteRealmAuditLog,
    RemoteRealmBillingUser,
    RemoteServerBillingUser,
    RemoteZulipServer,
    RemoteZulipServerAuditLog,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

CallableT = TypeVar("CallableT", bound=Callable[..., Any])
ParamT = ParamSpec("ParamT")
ReturnT = TypeVar("ReturnT")

STRIPE_FIXTURES_DIR = "corporate/tests/stripe_fixtures"


def stripe_fixture_path(
    decorated_function_name: str, mocked_function_name: str, call_count: int
) -> str:
    # Make the eventual filename a bit shorter, and also we conventionally
    # use test_* for the python test files
    if decorated_function_name[:5] == "test_":
        decorated_function_name = decorated_function_name[5:]
    return f"{STRIPE_FIXTURES_DIR}/{decorated_function_name}--{mocked_function_name[7:]}.{call_count}.json"


def fixture_files_for_function(decorated_function: CallableT) -> List[str]:  # nocoverage
    decorated_function_name = decorated_function.__name__
    if decorated_function_name[:5] == "test_":
        decorated_function_name = decorated_function_name[5:]
    return sorted(
        f"{STRIPE_FIXTURES_DIR}/{f}"
        for f in os.listdir(STRIPE_FIXTURES_DIR)
        if f.startswith(decorated_function_name + "--")
    )


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
                f.write(
                    json.dumps(error_dict, indent=2, separators=(",", ": "), sort_keys=True) + "\n"
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
                fixture["http_body"], fixture["http_status"], fixture["headers"]
            )
        return stripe.convert_to_stripe_object(fixture)

    return _read_stripe_fixture


def delete_fixture_data(decorated_function: CallableT) -> None:  # nocoverage
    for fixture_file in fixture_files_for_function(decorated_function):
        os.remove(fixture_file)


def normalize_fixture_data(
    decorated_function: CallableT, tested_timestamp_fields: Sequence[str] = []
) -> None:  # nocoverage
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
    ]
    # We'll replace cus_D7OT2jf5YAtZQ2 with something like cus_NORMALIZED0001
    pattern_translations = {
        rf"{prefix}_[A-Za-z0-9]{{{length}}}": f"{prefix}_NORMALIZED%0{length - 10}d"
        for prefix, length in id_lengths
    }
    # We'll replace "invoice_prefix": "A35BC4Q" with something like "invoice_prefix": "NORMA01"
    pattern_translations.update(
        {
            r'"invoice_prefix": "([A-Za-z0-9]{7,8})"': "NORMA%02d",
            r'"fingerprint": "([A-Za-z0-9]{16})"': "NORMALIZED%06d",
            r'"number": "([A-Za-z0-9]{7,8}-[A-Za-z0-9]{4})"': "NORMALI-%04d",
            r'"address": "([A-Za-z0-9]{9}-test_[A-Za-z0-9]{12})"': "000000000-test_NORMALIZED%02d",
            # Don't use (..) notation, since the matched strings may be small integers that will also match
            # elsewhere in the file
            r'"realm_id": "[0-9]+"': '"realm_id": "%d"',
            r'"account_name": "[\w\s]+"': '"account_name": "NORMALIZED-%d"',
        }
    )
    # Normalizing across all timestamps still causes a lot of variance run to run, which is
    # why we're doing something a bit more complicated
    for i, timestamp_field in enumerate(tested_timestamp_fields):
        # Don't use (..) notation, since the matched timestamp can easily appear in other fields
        pattern_translations[rf'"{timestamp_field}": 1[5-9][0-9]{{8}}(?![0-9-])'] = (
            f'"{timestamp_field}": 1{i + 1:02}%07d'
        )

    normalized_values: Dict[str, Dict[str, str]] = {pattern: {} for pattern in pattern_translations}
    for fixture_file in fixture_files_for_function(decorated_function):
        with open(fixture_file) as f:
            file_content = f.read()
        for pattern, translation in pattern_translations.items():
            for match in re.findall(pattern, file_content):
                if match not in normalized_values[pattern]:
                    normalized_values[pattern][match] = translation % (
                        len(normalized_values[pattern]) + 1,
                    )
                file_content = file_content.replace(match, normalized_values[pattern][match])
        file_content = re.sub(r'(?<="risk_score": )(\d+)', "0", file_content)
        file_content = re.sub(r'(?<="times_redeemed": )(\d+)', "0", file_content)
        file_content = re.sub(
            r'(?<="idempotency-key": )"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f-]*)"',
            '"00000000-0000-0000-0000-000000000000"',
            file_content,
        )
        # Dates
        file_content = re.sub(r'(?<="Date": )"(.* GMT)"', '"NORMALIZED DATETIME"', file_content)
        file_content = re.sub(r"[0-3]\d [A-Z][a-z]{2} 20[1-2]\d", "NORMALIZED DATE", file_content)
        # IP addresses
        file_content = re.sub(r'"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"', '"0.0.0.0"', file_content)
        # All timestamps not in tested_timestamp_fields
        file_content = re.sub(r": (1[5-9][0-9]{8})(?![0-9-])", ": 1000000000", file_content)

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
        "Invoice.upcoming",
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
    tested_timestamp_fields: Sequence[str] = [], generate: bool = settings.GENERATE_STRIPE_FIXTURES
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
                normalize_fixture_data(decorated_function, tested_timestamp_fields)
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
        # Choosing dates with corresponding timestamps below 1500000000 so that they are
        # not caught by our timestamp normalization regex in normalize_fixture_data
        self.now = datetime(2012, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        self.next_month = datetime(2012, 2, 2, 3, 4, 5, tzinfo=timezone.utc)
        self.next_year = datetime(2013, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

        # Make hamlet billing admin for testing.
        hamlet = self.example_user("hamlet")
        hamlet.is_billing_admin = True
        hamlet.save(update_fields=["is_billing_admin"])

        self.billing_session: Union[
            RealmBillingSession, RemoteRealmBillingSession, RemoteServerBillingSession
        ] = RealmBillingSession(user=hamlet, realm=realm)

    def get_signed_seat_count_from_response(self, response: "TestHttpResponse") -> Optional[str]:
        match = re.search(r"name=\"signed_seat_count\" value=\"(.+)\"", response.content.decode())
        return match.group(1) if match else None

    def get_salt_from_response(self, response: "TestHttpResponse") -> Optional[str]:
        match = re.search(r"name=\"salt\" value=\"(\w+)\"", response.content.decode())
        return match.group(1) if match else None

    def get_test_card_token(
        self,
        attaches_to_customer: bool,
        charge_succeeds: Optional[bool] = None,
        card_provider: Optional[str] = None,
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
        self, stripe_session_id: str, expected_details: Dict[str, Any]
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
        expected_details: Dict[str, Any],
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
        stripe_session_dict = orjson.loads(orjson.dumps(stripe_session))
        stripe_session_dict["setup_intent"] = stripe_setup_intent.id

        event_payload = {
            "id": f"evt_{get_random_string(24)}",
            "object": "event",
            "data": {"object": stripe_session_dict},
            "type": "checkout.session.completed",
            "api_version": STRIPE_API_VERSION,
        }

        response = self.client_post(
            "/stripe/webhook/", event_payload, content_type="application/json"
        )
        assert response.status_code == 200

    def send_stripe_webhook_event(self, event: stripe.Event) -> None:
        response = self.client_post(
            "/stripe/webhook/", orjson.loads(orjson.dumps(event)), content_type="application/json"
        )
        assert response.status_code == 200

    def send_stripe_webhook_events(self, most_recent_event: stripe.Event) -> None:
        while True:
            events_old_to_new = list(
                reversed(stripe.Event.list(ending_before=most_recent_event.id))
            )
            if len(events_old_to_new) == 0:
                break
            for event in events_old_to_new:
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
        params: Dict[str, Any] = {
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

        remote_server_plan_start_date = kwargs.get("remote_server_plan_start_date", None)
        if remote_server_plan_start_date:
            params.update(
                remote_server_plan_start_date=remote_server_plan_start_date,
            )

        params.update(kwargs)
        for key in del_args:
            if key in params:
                del params[key]

        if talk_to_stripe:
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
            # upgrade for legacy remote servers.
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
            # Mark the invoice as paid via stripe with the `invoice.paid` event.
            stripe.Invoice.pay(last_sent_invoice.stripe_invoice_id, paid_out_of_band=True)

        # Upgrade the organization.
        # TODO: Fix `invoice.paid` event not being present in the events list even thought the invoice was
        # paid. This is likely due to a latency between invoice being paid and the event being generated.
        self.send_stripe_webhook_events(last_event)
        return upgrade_json_response

    def add_card_and_upgrade(
        self, user: Optional[UserProfile] = None, **kwargs: Any
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
                CustomerPlan.TIER_CLOUD_STANDARD,
                licenses,
                automanage_licenses,
                billing_schedule,
                charge_automatically,
                free_trial,
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
            mocked["Invoice"].create.return_value = None
            mocked["Invoice"].finalize_invoice.return_value = None
            mocked["InvoiceItem"].create.return_value = None
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


class StripeTest(StripeTestCase):
    def test_catch_stripe_errors(self) -> None:
        @catch_stripe_errors
        def raise_invalid_request_error() -> None:
            raise stripe.InvalidRequestError("message", "param", "code", json_body={})

        with self.assertLogs("corporate.stripe", "ERROR") as error_log:
            with self.assertRaises(BillingError) as billing_context:
                raise_invalid_request_error()
            self.assertEqual("other stripe error", billing_context.exception.error_description)
            self.assertEqual(
                error_log.output, ["ERROR:corporate.stripe:Stripe error: None None None None"]
            )

        @catch_stripe_errors
        def raise_card_error() -> None:
            error_message = "The card number is not a valid credit card number."
            json_body = {"error": {"message": error_message}}
            raise stripe.CardError(error_message, "number", "invalid_number", json_body=json_body)

        with self.assertLogs("corporate.stripe", "INFO") as info_log:
            with self.assertRaises(StripeCardError) as card_context:
                raise_card_error()
            self.assertIn("not a valid credit card", str(card_context.exception))
            self.assertEqual("card error", card_context.exception.error_description)
            self.assertEqual(
                info_log.output, ["INFO:corporate.stripe:Stripe card error: None None None None"]
            )

    def test_billing_not_enabled(self) -> None:
        iago = self.example_user("iago")
        with self.settings(BILLING_ENABLED=False):
            self.login_user(iago)
            response = self.client_get("/upgrade/", follow=True)
            self.assertEqual(response.status_code, 404)

    @mock_stripe()
    def test_stripe_billing_portal_urls(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_to_customer_for_upgrade()

        response = self.client_get(f"/customer_portal/?tier={CustomerPlan.TIER_CLOUD_STANDARD}")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com"))

        self.upgrade(invoice=True)

        response = self.client_get("/customer_portal/?return_to_billing_page=true")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com"))

        response = self.client_get("/invoices/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com"))

    @mock_stripe()
    def test_upgrade_by_card_to_plus_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        response = self.client_get("/upgrade/?tier=2")
        self.assert_in_success_response(
            ["Your subscription will renew automatically", "Zulip Cloud Plus"], response
        )
        self.assertEqual(user.realm.plan_type, Realm.PLAN_TYPE_SELF_HOSTED)
        # This also means there is no card set as default payment method set for the user.
        self.assertFalse(Customer.objects.filter(realm=user.realm).exists())
        stripe_customer = self.add_card_and_upgrade(user, tier=CustomerPlan.TIER_CLOUD_PLUS)

        self.assertEqual(stripe_customer.description, "zulip (Zulip Dev)")
        self.assertEqual(stripe_customer.discount, None)
        self.assertEqual(stripe_customer.email, user.delivery_email)
        assert stripe_customer.metadata is not None
        metadata_dict = dict(stripe_customer.metadata)
        self.assertEqual(metadata_dict["realm_str"], "zulip")
        try:
            int(metadata_dict["realm_id"])
        except ValueError:  # nocoverage
            raise AssertionError("realm_id is not a number")

        # Check Charges in Stripe
        [charge] = iter(stripe.Charge.list(customer=stripe_customer.id))
        self.assertEqual(charge.amount, 12000 * self.seat_count)
        self.assertEqual(charge.description, "Payment for Invoice")
        self.assertEqual(charge.receipt_email, user.delivery_email)
        self.assertEqual(charge.statement_descriptor, "Zulip Cloud Plus")
        # Check Invoices in Stripe
        [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
        self.assertIsNotNone(invoice.status_transitions.finalized_at)
        invoice_params = {
            # auto_advance is False because the invoice has been paid
            "amount_due": 72000,
            "amount_paid": 72000,
            "auto_advance": False,
            "collection_method": "charge_automatically",
            "status": "paid",
            "total": 72000,
        }
        self.assertIsNotNone(invoice.charge)
        for key, value in invoice_params.items():
            self.assertEqual(invoice.get(key), value)
        # Check Line Items on Stripe Invoice
        [item0] = iter(invoice.lines)
        line_item_params = {
            "amount": 12000 * self.seat_count,
            "description": "Zulip Cloud Plus",
            "discountable": False,
            # There's no unit_amount on Line Items, probably because it doesn't show up on the
            # user-facing invoice. We could pull the Invoice Item instead and test unit_amount there,
            # but testing the amount and quantity seems sufficient.
            "plan": None,
            "proration": False,
            "quantity": self.seat_count,
            "period": {
                "start": datetime_to_timestamp(self.now),
                "end": datetime_to_timestamp(add_months(self.now, 12)),
            },
        }
        for key, value in line_item_params.items():
            self.assertEqual(item0.get(key), value)

        # Check that we correctly populated Customer, CustomerPlan, and LicenseLedger in Zulip
        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
        plan = CustomerPlan.objects.get(
            customer=customer,
            automanage_licenses=True,
            price_per_license=12000,
            fixed_price=None,
            discount=None,
            billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            invoiced_through=LicenseLedger.objects.first(),
            next_invoice_date=self.next_month,
            tier=CustomerPlan.TIER_CLOUD_PLUS,
            status=CustomerPlan.ACTIVE,
        )
        LicenseLedger.objects.get(
            plan=plan,
            is_renewal=True,
            event_time=self.now,
            licenses=self.seat_count,
            licenses_at_next_renewal=self.seat_count,
        )
        # Check RealmAuditLog
        audit_log_entries = list(
            RealmAuditLog.objects.filter(acting_user=user)
            .values_list("event_type", "event_time")
            .order_by("id")
        )
        self.assertEqual(
            audit_log_entries[:3],
            [
                (
                    RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                    timestamp_to_datetime(stripe_customer.created),
                ),
                (RealmAuditLog.STRIPE_CARD_CHANGED, self.now),
                (RealmAuditLog.CUSTOMER_PLAN_CREATED, self.now),
            ],
        )
        self.assertEqual(audit_log_entries[3][0], RealmAuditLog.REALM_PLAN_TYPE_CHANGED)
        first_audit_log_entry = (
            RealmAuditLog.objects.filter(event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED)
            .values_list("extra_data", flat=True)
            .first()
        )
        assert first_audit_log_entry is not None
        self.assertTrue(first_audit_log_entry["automanage_licenses"])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_PLUS)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("http://zulip.testserver/billing", response["Location"])

        # Check /billing/ has the correct information
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(["Pay annually"], response)
        for substring in [
            "Zulip Cloud Plus",
            str(self.seat_count),
            "Number of licenses",
            f"{ self.seat_count } (managed automatically)",
            "Your plan will automatically renew on",
            "January 2, 2013",
            f"${120 * self.seat_count}.00",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        self.assert_not_in_success_response(
            [
                "Number of licenses for current billing period",
                "You will receive an invoice for",
            ],
            response,
        )

    @mock_stripe()
    def test_upgrade_by_invoice_to_plus_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        # Click "Make payment" in Stripe Checkout
        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True, tier=CustomerPlan.TIER_CLOUD_PLUS)
        # Check that we correctly created a Customer in Stripe
        stripe_customer = stripe_get_customer(
            assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
        )
        self.assertFalse(stripe_customer_has_credit_card_as_default_payment_method(stripe_customer))

        # Check Charges in Stripe
        self.assertFalse(stripe.Charge.list(customer=stripe_customer.id))
        # Check Invoices in Stripe
        [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
        self.assertIsNotNone(invoice.due_date)
        self.assertIsNotNone(invoice.status_transitions.finalized_at)
        invoice_params = {
            "amount_due": 12000 * 123,
            "amount_paid": 0,
            "attempt_count": 0,
            "auto_advance": False,
            "collection_method": "send_invoice",
            "statement_descriptor": "Zulip Cloud Plus",
            "status": "paid",
            "total": 12000 * 123,
        }
        for key, value in invoice_params.items():
            self.assertEqual(invoice.get(key), value)
        # Check Line Items on Stripe Invoice
        [item] = iter(invoice.lines)
        line_item_params = {
            "amount": 12000 * 123,
            "description": "Zulip Cloud Plus",
            "discountable": False,
            "plan": None,
            "proration": False,
            "quantity": 123,
            "period": {
                "start": datetime_to_timestamp(self.now),
                "end": datetime_to_timestamp(add_months(self.now, 12)),
            },
        }
        for key, value in line_item_params.items():
            self.assertEqual(item.get(key), value)

        # Check that we correctly populated Customer, CustomerPlan and LicenseLedger in Zulip
        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
        plan = CustomerPlan.objects.get(
            customer=customer,
            automanage_licenses=False,
            charge_automatically=False,
            price_per_license=12000,
            fixed_price=None,
            discount=None,
            billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            invoiced_through=LicenseLedger.objects.first(),
            next_invoice_date=self.next_month,
            tier=CustomerPlan.TIER_CLOUD_PLUS,
            status=CustomerPlan.ACTIVE,
        )
        LicenseLedger.objects.get(
            plan=plan,
            is_renewal=True,
            event_time=self.now,
            licenses=123,
            licenses_at_next_renewal=123,
        )
        # Check RealmAuditLog
        audit_log_entries = list(
            RealmAuditLog.objects.filter(acting_user=user)
            .values_list("event_type", "event_time")
            .order_by("id")
        )
        self.assertEqual(
            audit_log_entries[:3],
            [
                (
                    RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                    timestamp_to_datetime(stripe_customer.created),
                ),
                (RealmAuditLog.CUSTOMER_PLAN_CREATED, self.now),
                (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, self.now),
            ],
        )
        self.assertEqual(audit_log_entries[2][0], RealmAuditLog.REALM_PLAN_TYPE_CHANGED)
        first_audit_log_entry = (
            RealmAuditLog.objects.filter(event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED)
            .values_list("extra_data", flat=True)
            .first()
        )
        assert first_audit_log_entry is not None
        self.assertFalse(first_audit_log_entry["automanage_licenses"])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_PLUS)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("http://zulip.testserver/billing", response["Location"])

        # Check /billing/ has the correct information
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(["Pay annually", "Update card"], response)
        for substring in [
            "Zulip Cloud Plus",
            str(123),
            "Number of licenses for current billing period",
            f"licenses ({self.seat_count} in use)",
            "You will receive an invoice for",
            "January 2, 2013",
            "$14,760.00",  # 14760 = 120 * 123
        ]:
            self.assert_in_response(substring, response)

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_upgrade_by_card(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        response = self.client_get("/upgrade/")
        self.assert_in_success_response(["Your subscription will renew automatically"], response)
        self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
        # This also means there is no card set as default payment method set for the user.
        self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

        # Click "Purchase Zulip Cloud Standard" without adding a card.
        with self.assertLogs("corporate.stripe", "WARNING"):
            response = self.upgrade()
        self.assert_json_error(response, "Please add a credit card before upgrading.")

        stripe_customer = self.add_card_and_upgrade(user)

        self.assertEqual(stripe_customer.description, "zulip (Zulip Dev)")
        self.assertEqual(stripe_customer.discount, None)
        self.assertEqual(stripe_customer.email, user.delivery_email)
        assert stripe_customer.metadata is not None
        metadata_dict = dict(stripe_customer.metadata)
        self.assertEqual(metadata_dict["realm_str"], "zulip")
        try:
            int(metadata_dict["realm_id"])
        except ValueError:  # nocoverage
            raise AssertionError("realm_id is not a number")

        # Check Charges in Stripe
        [charge] = iter(stripe.Charge.list(customer=stripe_customer.id))
        self.assertEqual(charge.amount, 8000 * self.seat_count)
        self.assertEqual(charge.description, "Payment for Invoice")
        self.assertEqual(charge.receipt_email, user.delivery_email)
        self.assertEqual(charge.statement_descriptor, "Zulip Cloud Standard")
        # Check Invoices in Stripe
        [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
        self.assertIsNotNone(invoice.status_transitions.finalized_at)
        invoice_params = {
            # auto_advance is False because the invoice has been paid
            "amount_due": 48000,
            "amount_paid": 48000,
            "auto_advance": False,
            "collection_method": "charge_automatically",
            "status": "paid",
            "total": 48000,
        }
        self.assertIsNotNone(invoice.charge)
        for key, value in invoice_params.items():
            self.assertEqual(invoice.get(key), value)
        # Check Line Items on Stripe Invoice
        [item0] = iter(invoice.lines)
        line_item_params = {
            "amount": 8000 * self.seat_count,
            "description": "Zulip Cloud Standard",
            "discountable": False,
            # There's no unit_amount on Line Items, probably because it doesn't show up on the
            # user-facing invoice. We could pull the Invoice Item instead and test unit_amount there,
            # but testing the amount and quantity seems sufficient.
            "plan": None,
            "proration": False,
            "quantity": self.seat_count,
            "period": {
                "start": datetime_to_timestamp(self.now),
                "end": datetime_to_timestamp(add_months(self.now, 12)),
            },
        }
        for key, value in line_item_params.items():
            self.assertEqual(item0.get(key), value)

        # Check that we correctly populated Customer, CustomerPlan, and LicenseLedger in Zulip
        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
        plan = CustomerPlan.objects.get(
            customer=customer,
            automanage_licenses=True,
            price_per_license=8000,
            fixed_price=None,
            discount=None,
            billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            invoiced_through=LicenseLedger.objects.first(),
            next_invoice_date=self.next_month,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            status=CustomerPlan.ACTIVE,
        )
        LicenseLedger.objects.get(
            plan=plan,
            is_renewal=True,
            event_time=self.now,
            licenses=self.seat_count,
            licenses_at_next_renewal=self.seat_count,
        )
        # Check RealmAuditLog
        audit_log_entries = list(
            RealmAuditLog.objects.filter(acting_user=user)
            .values_list("event_type", "event_time")
            .order_by("id")
        )
        self.assertEqual(
            audit_log_entries[:3],
            [
                (
                    RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                    timestamp_to_datetime(stripe_customer.created),
                ),
                (RealmAuditLog.STRIPE_CARD_CHANGED, self.now),
                (RealmAuditLog.CUSTOMER_PLAN_CREATED, self.now),
            ],
        )
        self.assertEqual(audit_log_entries[3][0], RealmAuditLog.REALM_PLAN_TYPE_CHANGED)
        first_audit_log_entry = (
            RealmAuditLog.objects.filter(event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED)
            .values_list("extra_data", flat=True)
            .first()
        )
        assert first_audit_log_entry is not None
        self.assertTrue(first_audit_log_entry["automanage_licenses"])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("http://zulip.testserver/billing", response["Location"])

        # Check /billing/ has the correct information
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(["Pay annually"], response)
        for substring in [
            "Zulip Cloud Standard",
            str(self.seat_count),
            "Number of licenses",
            f"{ self.seat_count } (managed automatically)",
            "Your plan will automatically renew on",
            "January 2, 2013",
            f"${80 * self.seat_count}.00",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        self.assert_not_in_success_response(
            [
                "Number of licenses for current billing period",
                "You will receive an invoice for",
            ],
            response,
        )

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_card_attached_to_customer_but_payment_fails(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_to_customer_for_upgrade(charge_succeeds=False)
        with self.assertLogs("corporate.stripe", "WARNING"):
            response = self.upgrade()
        self.assert_json_error_contains(response, "Your card was declined.")

        # Customer added a card which always requires authentication, we cannot
        # use these cards for automatic payments.
        # TODO: Add a test case for it here.

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_upgrade_by_invoice(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        # Click "Make payment" in Stripe Checkout
        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True)
        # Check that we correctly created a Customer in Stripe
        stripe_customer = stripe_get_customer(
            assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
        )
        self.assertFalse(stripe_customer_has_credit_card_as_default_payment_method(stripe_customer))

        # Check Charges in Stripe
        self.assertFalse(stripe.Charge.list(customer=stripe_customer.id))
        # Check Invoices in Stripe
        [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
        self.assertIsNotNone(invoice.due_date)
        self.assertIsNotNone(invoice.status_transitions.finalized_at)
        invoice_params = {
            "amount_due": 8000 * 123,
            "amount_paid": 0,
            "attempt_count": 0,
            "auto_advance": False,
            "collection_method": "send_invoice",
            "statement_descriptor": "Zulip Cloud Standard",
            "status": "paid",
            "total": 8000 * 123,
        }
        for key, value in invoice_params.items():
            self.assertEqual(invoice.get(key), value)
        # Check Line Items on Stripe Invoice
        [item] = iter(invoice.lines)
        line_item_params = {
            "amount": 8000 * 123,
            "description": "Zulip Cloud Standard",
            "discountable": False,
            "plan": None,
            "proration": False,
            "quantity": 123,
            "period": {
                "start": datetime_to_timestamp(self.now),
                "end": datetime_to_timestamp(add_months(self.now, 12)),
            },
        }
        for key, value in line_item_params.items():
            self.assertEqual(item.get(key), value)

        # Check that we correctly populated Customer, CustomerPlan and LicenseLedger in Zulip
        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
        plan = CustomerPlan.objects.get(
            customer=customer,
            automanage_licenses=False,
            charge_automatically=False,
            price_per_license=8000,
            fixed_price=None,
            discount=None,
            billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            invoiced_through=LicenseLedger.objects.first(),
            next_invoice_date=self.next_month,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            status=CustomerPlan.ACTIVE,
        )
        LicenseLedger.objects.get(
            plan=plan,
            is_renewal=True,
            event_time=self.now,
            licenses=123,
            licenses_at_next_renewal=123,
        )
        # Check RealmAuditLog
        audit_log_entries = list(
            RealmAuditLog.objects.filter(acting_user=user)
            .values_list("event_type", "event_time")
            .order_by("id")
        )
        self.assertEqual(
            audit_log_entries[:3],
            [
                (
                    RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                    timestamp_to_datetime(stripe_customer.created),
                ),
                (RealmAuditLog.CUSTOMER_PLAN_CREATED, self.now),
                (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, self.now),
            ],
        )
        self.assertEqual(audit_log_entries[2][0], RealmAuditLog.REALM_PLAN_TYPE_CHANGED)
        first_audit_log_entry = (
            RealmAuditLog.objects.filter(event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED)
            .values_list("extra_data", flat=True)
            .first()
        )
        assert first_audit_log_entry is not None
        self.assertFalse(first_audit_log_entry["automanage_licenses"])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("http://zulip.testserver/billing", response["Location"])

        # Check /billing/ has the correct information
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(["Pay annually", "Update card"], response)
        for substring in [
            "Zulip Cloud Standard",
            str(123),
            "Number of licenses for current billing period",
            f"licenses ({self.seat_count} in use)",
            "You will receive an invoice for",
            "January 2, 2013",
            "$9,840.00",  # 9840 = 80 * 123
        ]:
            self.assert_in_response(substring, response)

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_free_trial_upgrade_by_card(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            response = self.client_get("/upgrade/")
            free_trial_end_date = self.now + timedelta(days=60)

            self.assert_in_success_response(
                ["Your card will not be charged", "free trial", "60-day"], response
            )
            self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

            # Require free trial users to add a credit card.
            with time_machine.travel(self.now, tick=False):
                with self.assertLogs("corporate.stripe", "WARNING"):
                    response = self.upgrade()
            self.assert_json_error(
                response, "Please add a credit card before starting your free trial."
            )

            stripe_customer = self.add_card_and_upgrade(user)

            self.assertEqual(Invoice.objects.count(), 0)
            self.assertEqual(stripe_customer.description, "zulip (Zulip Dev)")
            self.assertEqual(stripe_customer.discount, None)
            self.assertEqual(stripe_customer.email, user.delivery_email)
            assert stripe_customer.metadata is not None
            metadata_dict = dict(stripe_customer.metadata)
            self.assertEqual(metadata_dict["realm_str"], "zulip")
            try:
                int(metadata_dict["realm_id"])
            except ValueError:  # nocoverage
                raise AssertionError("realm_id is not a number")

            self.assertFalse(stripe.Charge.list(customer=stripe_customer.id))

            self.assertFalse(stripe.Invoice.list(customer=stripe_customer.id))

            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
            plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=True,
                price_per_license=8000,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                invoiced_through=LicenseLedger.objects.first(),
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                # For payment through card.
                charge_automatically=True,
            )
            LicenseLedger.objects.get(
                plan=plan,
                is_renewal=True,
                event_time=self.now,
                licenses=self.seat_count,
                licenses_at_next_renewal=self.seat_count,
            )
            audit_log_entries = list(
                RealmAuditLog.objects.filter(acting_user=user)
                .values_list("event_type", "event_time")
                .order_by("id")
            )
            self.assertEqual(
                audit_log_entries[:4],
                [
                    (
                        RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                        timestamp_to_datetime(stripe_customer.created),
                    ),
                    (
                        RealmAuditLog.STRIPE_CARD_CHANGED,
                        self.now,
                    ),
                    (RealmAuditLog.CUSTOMER_PLAN_CREATED, self.now),
                    (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, self.now),
                ],
            )
            self.assertEqual(audit_log_entries[3][0], RealmAuditLog.REALM_PLAN_TYPE_CHANGED)
            first_audit_log_entry = (
                RealmAuditLog.objects.filter(event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED)
                .values_list("extra_data", flat=True)
                .first()
            )
            assert first_audit_log_entry is not None
            self.assertTrue(first_audit_log_entry["automanage_licenses"])

            realm = get_realm("zulip")
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")
            self.assert_not_in_success_response(["Pay annually"], response)
            for substring in [
                "Zulip Cloud Standard <i>(free trial)</i>",
                str(self.seat_count),
                "Number of licenses",
                f"{self.seat_count} (managed automatically)",
                "Your plan will automatically renew on",
                "March 2, 2012",
                f"${80 * self.seat_count}.00",
                "Visa ending in 4242",
                "Update card",
            ]:
                self.assert_in_response(substring, response)
            self.assert_not_in_success_response(["Go to your Zulip organization"], response)

            billing_session = RealmBillingSession(user=user, realm=realm)
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=12):
                billing_session.update_license_ledger_if_needed(self.now)
            self.assertEqual(
                LicenseLedger.objects.order_by("-id")
                .values_list("licenses", "licenses_at_next_renewal")
                .first(),
                (12, 12),
            )

            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=15):
                billing_session.update_license_ledger_if_needed(self.next_month)
            self.assertEqual(
                LicenseLedger.objects.order_by("-id")
                .values_list("licenses", "licenses_at_next_renewal")
                .first(),
                (15, 15),
            )

            invoice_plans_as_needed(self.next_month)
            self.assertFalse(stripe.Invoice.list(customer=stripe_customer.id))
            customer_plan = CustomerPlan.objects.get(customer=customer)
            self.assertEqual(customer_plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(customer_plan.next_invoice_date, free_trial_end_date)

            invoice_plans_as_needed(free_trial_end_date)
            customer_plan.refresh_from_db()
            realm.refresh_from_db()
            self.assertEqual(customer_plan.status, CustomerPlan.ACTIVE)
            self.assertEqual(customer_plan.next_invoice_date, add_months(free_trial_end_date, 1))
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
            invoice_params = {
                "amount_due": 15 * 80 * 100,
                "amount_paid": 0,
                "amount_remaining": 15 * 80 * 100,
                "auto_advance": True,
                "collection_method": "charge_automatically",
                "customer_email": self.example_email("hamlet"),
                "discount": None,
                "paid": False,
                "status": "open",
                "total": 15 * 80 * 100,
            }
            for key, value in invoice_params.items():
                self.assertEqual(invoice.get(key), value)
            [invoice_item] = iter(invoice.lines)
            invoice_item_params = {
                "amount": 15 * 80 * 100,
                "description": "Zulip Cloud Standard - renewal",
                "plan": None,
                "quantity": 15,
                "subscription": None,
                "discountable": False,
                "period": {
                    "start": datetime_to_timestamp(free_trial_end_date),
                    "end": datetime_to_timestamp(add_months(free_trial_end_date, 12)),
                },
            }
            for key, value in invoice_item_params.items():
                self.assertEqual(invoice_item[key], value)

            invoice_plans_as_needed(add_months(free_trial_end_date, 1))
            [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))

            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=19):
                billing_session.update_license_ledger_if_needed(add_months(free_trial_end_date, 10))
            self.assertEqual(
                LicenseLedger.objects.order_by("-id")
                .values_list("licenses", "licenses_at_next_renewal")
                .first(),
                (19, 19),
            )
            # Fast forward next_invoice_date to 10 months from the free_trial_end_date
            plan.next_invoice_date = add_months(free_trial_end_date, 10)
            plan.save(update_fields=["next_invoice_date"])
            invoice_plans_as_needed(add_months(free_trial_end_date, 10))
            [invoice0, invoice1] = iter(stripe.Invoice.list(customer=stripe_customer.id))
            invoice_params = {
                "amount_due": 5172,
                "auto_advance": True,
                "collection_method": "charge_automatically",
                "customer_email": "hamlet@zulip.com",
            }
            [invoice_item] = iter(invoice0.lines)
            invoice_item_params = {
                "amount": 5172,
                "description": "Additional license (Jan 2, 2013 - Mar 2, 2013)",
                "discountable": False,
                "quantity": 4,
                "period": {
                    "start": datetime_to_timestamp(add_months(free_trial_end_date, 10)),
                    "end": datetime_to_timestamp(add_months(free_trial_end_date, 12)),
                },
            }

            # Fast forward next_invoice_date to one year from the free_trial_end_date
            plan.next_invoice_date = add_months(free_trial_end_date, 12)
            plan.save(update_fields=["next_invoice_date"])
            invoice_plans_as_needed(add_months(free_trial_end_date, 12))
            [invoice0, invoice1, invoice2] = iter(stripe.Invoice.list(customer=stripe_customer.id))

        # Check /billing/ has correct information for fixed price customers.
        plan.fixed_price = 127
        plan.price_per_license = None
        plan.save(update_fields=["fixed_price", "price_per_license"])
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_in_success_response(["$1.27"], response)
        # Don't show price breakdown
        self.assert_not_in_success_response(["{self.seat_count} x"], response)

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_free_trial_upgrade_by_invoice(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            response = self.client_get("/upgrade/")

            self.assert_in_success_response(
                ["Your card will not be charged", "free trial", "60-day"], response
            )
            self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

            with time_machine.travel(self.now, tick=False):
                self.upgrade(invoice=True)

            stripe_customer = stripe_get_customer(
                assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
            )
            self.assertEqual(stripe_customer.discount, None)
            self.assertEqual(stripe_customer.email, user.delivery_email)
            assert stripe_customer.metadata is not None
            metadata_dict = dict(stripe_customer.metadata)
            self.assertEqual(metadata_dict["realm_str"], "zulip")
            try:
                int(metadata_dict["realm_id"])
            except ValueError:  # nocoverage
                raise AssertionError("realm_id is not a number")

            [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
            invoice_params = {
                "amount_due": 123 * 80 * 100,
                "amount_paid": 0,
                "amount_remaining": 123 * 80 * 100,
                "auto_advance": True,
                "collection_method": "send_invoice",
                "customer_email": self.example_email("hamlet"),
                "discount": None,
                "paid": False,
                "status": "open",
                "total": 123 * 80 * 100,
            }
            for key, value in invoice_params.items():
                self.assertEqual(invoice.get(key), value)

            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
            plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=False,
                price_per_license=8000,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                invoiced_through=LicenseLedger.objects.first(),
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                # For invoice billing.
                charge_automatically=False,
            )

            LicenseLedger.objects.get(
                plan=plan,
                is_renewal=True,
                event_time=self.now,
                licenses=123,
                licenses_at_next_renewal=123,
            )
            audit_log_entries = list(
                RealmAuditLog.objects.filter(acting_user=user)
                .values_list("event_type", "event_time")
                .order_by("id")
            )
            self.assertEqual(
                audit_log_entries[:3],
                [
                    (
                        RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                        timestamp_to_datetime(stripe_customer.created),
                    ),
                    (RealmAuditLog.CUSTOMER_PLAN_CREATED, self.now),
                    (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, self.now),
                ],
            )
            self.assertEqual(audit_log_entries[2][0], RealmAuditLog.REALM_PLAN_TYPE_CHANGED)
            first_audit_log_entry = (
                RealmAuditLog.objects.filter(event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED)
                .values_list("extra_data", flat=True)
                .first()
            )
            assert first_audit_log_entry is not None
            self.assertFalse(first_audit_log_entry["automanage_licenses"])

            realm = get_realm("zulip")
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")
            self.assert_not_in_success_response(["Pay annually"], response)
            for substring in [
                "Zulip Cloud Standard <i>(free trial)</i>",
                str(self.seat_count),
                "Number of licenses for next billing period",
                f"{self.seat_count} in use",
                "To ensure continuous access",
                "please pay",
                "before the end of your trial",
                "March 2, 2012",
                "Invoice",
            ]:
                self.assert_in_response(substring, response)

            [invoice_item] = iter(invoice.lines)
            invoice_item_params = {
                "amount": 123 * 80 * 100,
                "description": "Zulip Cloud Standard",
                "plan": None,
                "quantity": 123,
                "subscription": None,
                "discountable": False,
                "period": {
                    "start": datetime_to_timestamp(free_trial_end_date),
                    "end": datetime_to_timestamp(add_months(free_trial_end_date, 12)),
                },
            }
            for key, value in invoice_item_params.items():
                self.assertEqual(invoice_item[key], value)

            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_month)
            mocked.assert_not_called()
            mocked.reset_mock()
            customer_plan = CustomerPlan.objects.get(customer=customer)
            self.assertEqual(customer_plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(customer_plan.next_invoice_date, free_trial_end_date)

            [last_event] = iter(stripe.Event.list(limit=1))
            # Customer pays the invoice
            assert invoice.id is not None
            stripe.Invoice.pay(invoice.id, paid_out_of_band=True)
            self.send_stripe_webhook_events(last_event)

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")

            self.assert_in_success_response(["You have no outstanding invoices."], response)

            invoice_plans_as_needed(free_trial_end_date)
            customer_plan.refresh_from_db()
            realm.refresh_from_db()
            self.assertEqual(customer_plan.status, CustomerPlan.ACTIVE)
            self.assertEqual(customer_plan.next_invoice_date, add_months(free_trial_end_date, 1))
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)

    @mock_stripe()
    def test_free_trial_upgrade_by_invoice_customer_fails_to_pay(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            response = self.client_get("/upgrade/")

            self.assert_in_success_response(
                ["Your card will not be charged", "free trial", "60-day"], response
            )
            self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

            with time_machine.travel(self.now, tick=False):
                self.upgrade(invoice=True)

            stripe_customer = stripe_get_customer(
                assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
            )
            self.assertEqual(stripe_customer.discount, None)
            self.assertEqual(stripe_customer.email, user.delivery_email)
            assert stripe_customer.metadata is not None
            metadata_dict = dict(stripe_customer.metadata)
            self.assertEqual(metadata_dict["realm_str"], "zulip")
            try:
                int(metadata_dict["realm_id"])
            except ValueError:  # nocoverage
                raise AssertionError("realm_id is not a number")

            [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
            invoice_params = {
                "amount_due": 123 * 80 * 100,
                "amount_paid": 0,
                "amount_remaining": 123 * 80 * 100,
                "auto_advance": True,
                "collection_method": "send_invoice",
                "customer_email": self.example_email("hamlet"),
                "discount": None,
                "paid": False,
                "status": "open",
                "total": 123 * 80 * 100,
            }
            for key, value in invoice_params.items():
                self.assertEqual(invoice.get(key), value)

            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
            plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=False,
                price_per_license=8000,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                invoiced_through=LicenseLedger.objects.first(),
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                # For invoice billing.
                charge_automatically=False,
            )

            LicenseLedger.objects.get(
                plan=plan,
                is_renewal=True,
                event_time=self.now,
                licenses=123,
                licenses_at_next_renewal=123,
            )
            audit_log_entries = list(
                RealmAuditLog.objects.filter(acting_user=user)
                .values_list("event_type", "event_time")
                .order_by("id")
            )
            self.assertEqual(
                audit_log_entries[:3],
                [
                    (
                        RealmAuditLog.STRIPE_CUSTOMER_CREATED,
                        timestamp_to_datetime(stripe_customer.created),
                    ),
                    (RealmAuditLog.CUSTOMER_PLAN_CREATED, self.now),
                    (RealmAuditLog.REALM_PLAN_TYPE_CHANGED, self.now),
                ],
            )
            self.assertEqual(audit_log_entries[2][0], RealmAuditLog.REALM_PLAN_TYPE_CHANGED)
            first_audit_log_entry = (
                RealmAuditLog.objects.filter(event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED)
                .values_list("extra_data", flat=True)
                .first()
            )
            assert first_audit_log_entry is not None
            self.assertFalse(first_audit_log_entry["automanage_licenses"])

            realm = get_realm("zulip")
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")
            self.assert_not_in_success_response(["Pay annually"], response)
            for substring in [
                "Zulip Cloud Standard <i>(free trial)</i>",
                str(self.seat_count),
                "Number of licenses for next billing period",
                f"{self.seat_count} in use",
                "To ensure continuous access",
                "please pay",
                "before the end of your trial",
                "March 2, 2012",
                "Invoice",
            ]:
                self.assert_in_response(substring, response)

            [invoice_item] = iter(invoice.lines)
            invoice_item_params = {
                "amount": 123 * 80 * 100,
                "description": "Zulip Cloud Standard",
                "plan": None,
                "quantity": 123,
                "subscription": None,
                "discountable": False,
                "period": {
                    "start": datetime_to_timestamp(free_trial_end_date),
                    "end": datetime_to_timestamp(add_months(free_trial_end_date, 12)),
                },
            }
            for key, value in invoice_item_params.items():
                self.assertEqual(invoice_item[key], value)

            # We reached free trial end but customer didn't pay the invoice.
            invoice_plans_as_needed(free_trial_end_date)
            customer_plan = CustomerPlan.objects.get(customer=customer)
            self.assertEqual(customer_plan.status, CustomerPlan.ENDED)
            realm.refresh_from_db()
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_LIMITED)

            response = self.client_get("/upgrade/")
            self.assert_in_success_response(
                ["Your free trial", "has expired", "To reactivate", "please pay"], response
            )

            # Customer decides to pay later
            [last_event] = iter(stripe.Event.list(limit=1))
            assert invoice.id is not None
            stripe.Invoice.pay(invoice.id, paid_out_of_band=True)
            self.send_stripe_webhook_events(last_event)

            invoice_plans_as_needed(free_trial_end_date)
            CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
            realm.refresh_from_db()
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_upgrade_by_card_with_outdated_seat_count(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        new_seat_count = 23
        initial_upgrade_request = InitialUpgradeRequest(
            manual_license_management=False,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            billing_modality="charge_automatically",
        )
        billing_session = RealmBillingSession(hamlet)
        _, context_when_upgrade_page_is_rendered = billing_session.get_initial_upgrade_context(
            initial_upgrade_request
        )
        # Change the seat count while the user is going through the upgrade flow
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=new_seat_count):
            with patch(
                "corporate.lib.stripe.RealmBillingSession.get_initial_upgrade_context",
                return_value=(_, context_when_upgrade_page_is_rendered),
            ):
                self.add_card_and_upgrade(hamlet)

        customer = Customer.objects.first()
        assert customer is not None
        stripe_customer_id: str = assert_is_not_none(customer.stripe_customer_id)
        # Check that the Charge used the old quantity, not new_seat_count
        [charge] = iter(stripe.Charge.list(customer=stripe_customer_id))
        self.assertEqual(8000 * self.seat_count, charge.amount)
        # Check that the invoice has a credit for the old amount and a charge for the new one
        [additional_license_invoice, upgrade_invoice] = iter(
            stripe.Invoice.list(customer=stripe_customer_id)
        )
        self.assertEqual(
            [8000 * self.seat_count],
            [item.amount for item in upgrade_invoice.lines],
        )
        self.assertEqual(
            [8000 * (new_seat_count - self.seat_count)],
            [item.amount for item in additional_license_invoice.lines],
        )
        # Check LicenseLedger has the new amount
        ledger_entry = LicenseLedger.objects.last()
        assert ledger_entry is not None
        self.assertEqual(ledger_entry.licenses, new_seat_count)
        self.assertEqual(ledger_entry.licenses_at_next_renewal, new_seat_count)

    def test_upgrade_with_tampered_seat_count(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        with self.assertLogs("corporate.stripe", "WARNING"):
            response = self.upgrade(talk_to_stripe=False, salt="badsalt")
        self.assert_json_error_contains(response, "Something went wrong. Please contact")
        self.assertEqual(orjson.loads(response.content)["error_description"], "tampered seat count")

    @mock_stripe()
    def test_upgrade_race_condition_during_card_upgrade(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        self.login_user(othello)
        othello_upgrade_page_response = self.client_get("/upgrade/")

        self.login_user(hamlet)
        self.add_card_to_customer_for_upgrade()
        [stripe_event_before_upgrade] = iter(stripe.Event.list(limit=1))
        hamlet_upgrade_page_response = self.client_get("/upgrade/")
        self.client_billing_post(
            "/billing/upgrade",
            {
                "billing_modality": "charge_automatically",
                "schedule": "annual",
                "signed_seat_count": self.get_signed_seat_count_from_response(
                    hamlet_upgrade_page_response
                ),
                "salt": self.get_salt_from_response(hamlet_upgrade_page_response),
                "license_management": "automatic",
            },
        )

        # Get the last generated invoice for Hamlet
        customer = get_customer_by_realm(get_realm("zulip"))
        assert customer is not None
        assert customer.stripe_customer_id is not None
        [hamlet_invoice] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))

        self.login_user(othello)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            # Othello completed the upgrade while we were waiting on success payment event for Hamlet.
            # NOTE: Used free trial to avoid creating any stripe invoice events.
            self.client_billing_post(
                "/billing/upgrade",
                {
                    "billing_modality": "charge_automatically",
                    "schedule": "annual",
                    "signed_seat_count": self.get_signed_seat_count_from_response(
                        othello_upgrade_page_response
                    ),
                    "salt": self.get_salt_from_response(othello_upgrade_page_response),
                    "license_management": "automatic",
                },
            )

        with self.assertLogs("corporate.stripe", "WARNING"):
            self.send_stripe_webhook_events(stripe_event_before_upgrade)

        assert hamlet_invoice.id is not None
        self.assert_details_of_valid_invoice_payment_from_event_status_endpoint(
            hamlet_invoice.id,
            {
                "status": "paid",
                "event_handler": {
                    "status": "failed",
                    "error": {
                        "message": "The organization is already subscribed to a plan. Please reload the billing page.",
                        "description": "subscribing with existing subscription",
                    },
                },
            },
        )

        # Check that we informed the support team about the failure.
        from django.core.mail import outbox

        self.assert_length(outbox, 1)

        for message in outbox:
            self.assert_length(message.to, 1)
            self.assertEqual(message.to[0], "sales@zulip.com")
            self.assertEqual(message.subject, "Error processing paid customer invoice")
            self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)

    def test_upgrade_race_condition_during_invoice_upgrade(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        self.local_upgrade(self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False)
        with self.assertLogs("corporate.stripe", "WARNING") as m:
            with self.assertRaises(BillingError) as context:
                self.local_upgrade(
                    self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
                )
        self.assertEqual(
            "subscribing with existing subscription", context.exception.error_description
        )
        self.assertEqual(
            m.output[0],
            "WARNING:corporate.stripe:Upgrade of <Realm: zulip 2> (with stripe_customer_id: cus_123) failed because of existing active plan.",
        )
        self.assert_length(m.output, 1)

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_check_upgrade_parameters(self, *mocks: Mock) -> None:
        # Tests all the error paths except 'not enough licenses'
        def check_error(
            error_message: str,
            error_description: str,
            upgrade_params: Mapping[str, Any],
            del_args: Sequence[str] = [],
        ) -> None:
            self.add_card_to_customer_for_upgrade()
            if error_description:
                with self.assertLogs("corporate.stripe", "WARNING"):
                    response = self.upgrade(
                        talk_to_stripe=False, del_args=del_args, **upgrade_params
                    )
                    self.assertEqual(
                        orjson.loads(response.content)["error_description"], error_description
                    )
            else:
                response = self.upgrade(talk_to_stripe=False, del_args=del_args, **upgrade_params)
            self.assert_json_error_contains(response, error_message)

        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        check_error("Invalid billing_modality", "", {"billing_modality": "invalid"})
        check_error("Invalid schedule", "", {"schedule": "invalid"})
        check_error("Invalid license_management", "", {"license_management": "invalid"})

        check_error(
            "You must purchase licenses for all active users in your organization (minimum 30).",
            "not enough licenses",
            {"billing_modality": "send_invoice", "licenses": -1},
        )
        check_error(
            "You must purchase licenses for all active users in your organization (minimum 30).",
            "not enough licenses",
            {"billing_modality": "send_invoice"},
        )
        check_error(
            "You must purchase licenses for all active users in your organization (minimum 30).",
            "not enough licenses",
            {"billing_modality": "send_invoice", "licenses": 25},
        )
        check_error(
            "Invoices with more than 1000 licenses can't be processed from this page",
            "too many licenses",
            {"billing_modality": "send_invoice", "licenses": 10000},
        )

        check_error(
            "You must purchase licenses for all active users in your organization (minimum 6).",
            "not enough licenses",
            {"billing_modality": "charge_automatically", "license_management": "manual"},
        )

        check_error(
            "You must purchase licenses for all active users in your organization (minimum 6).",
            "not enough licenses",
            {
                "billing_modality": "charge_automatically",
                "license_management": "manual",
                "licenses": 3,
            },
        )

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_upgrade_license_counts(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        self.add_card_to_customer_for_upgrade()

        def check_min_licenses_error(
            invoice: bool,
            licenses: Optional[int],
            min_licenses_in_response: int,
            upgrade_params: Mapping[str, Any] = {},
        ) -> None:
            upgrade_params = dict(upgrade_params)
            if licenses is None:
                del_args = ["licenses"]
            else:
                del_args = []
                upgrade_params["licenses"] = licenses
            with self.assertLogs("corporate.stripe", "WARNING"):
                response = self.upgrade(
                    invoice=invoice, talk_to_stripe=False, del_args=del_args, **upgrade_params
                )
            self.assert_json_error_contains(response, f"minimum {min_licenses_in_response}")
            self.assertEqual(
                orjson.loads(response.content)["error_description"], "not enough licenses"
            )

        def check_max_licenses_error(licenses: int) -> None:
            with self.assertLogs("corporate.stripe", "WARNING"):
                response = self.upgrade(invoice=True, talk_to_stripe=False, licenses=licenses)
            self.assert_json_error_contains(
                response, f"with more than {MAX_INVOICED_LICENSES} licenses"
            )
            self.assertEqual(
                orjson.loads(response.content)["error_description"], "too many licenses"
            )

        def check_success(
            invoice: bool, licenses: Optional[int], upgrade_params: Mapping[str, Any] = {}
        ) -> None:
            upgrade_params = dict(upgrade_params)
            if licenses is None:
                del_args = ["licenses"]
            else:
                del_args = []
                upgrade_params["licenses"] = licenses
            with patch("corporate.lib.stripe.BillingSession.process_initial_upgrade"):
                with patch(
                    "corporate.lib.stripe.BillingSession.create_stripe_invoice_and_charge",
                    return_value="fake_stripe_invoice_id",
                ):
                    response = self.upgrade(
                        invoice=invoice, talk_to_stripe=False, del_args=del_args, **upgrade_params
                    )
            self.assert_json_success(response)

        # Autopay with licenses < seat count
        check_min_licenses_error(
            False, self.seat_count - 1, self.seat_count, {"license_management": "manual"}
        )
        # Autopay with not setting licenses
        check_min_licenses_error(False, None, self.seat_count, {"license_management": "manual"})
        # Invoice with licenses < MIN_INVOICED_LICENSES
        check_min_licenses_error(True, MIN_INVOICED_LICENSES - 1, MIN_INVOICED_LICENSES)
        # Invoice with licenses < seat count
        with patch("corporate.lib.stripe.MIN_INVOICED_LICENSES", 3):
            check_min_licenses_error(True, 4, self.seat_count)
        # Invoice with not setting licenses
        check_min_licenses_error(True, None, MIN_INVOICED_LICENSES)
        # Invoice exceeding max licenses
        check_max_licenses_error(MAX_INVOICED_LICENSES + 1)
        with patch(
            "corporate.lib.stripe.get_latest_seat_count", return_value=MAX_INVOICED_LICENSES + 5
        ):
            check_max_licenses_error(MAX_INVOICED_LICENSES + 5)

        # Autopay with automatic license_management
        check_success(False, None)
        # Autopay with automatic license_management, should just ignore the licenses entry
        check_success(False, self.seat_count)
        # Autopay
        check_success(False, self.seat_count, {"license_management": "manual"})
        # Autopay has no limit on max licenses
        check_success(False, MAX_INVOICED_LICENSES + 1, {"license_management": "manual"})
        # Invoice
        check_success(True, self.seat_count + MIN_INVOICED_LICENSES)
        # Invoice
        check_success(True, MAX_INVOICED_LICENSES)

        # By default, an organization on a "Pay by card" plan with Manual license
        # management cannot purchase less licenses than the current seat count.
        # If exempt_from_license_number_check is enabled, they should be able to though.
        customer = Customer.objects.get_or_create(realm=hamlet.realm)[0]
        customer.exempt_from_license_number_check = True
        customer.save()
        check_success(False, self.seat_count - 1, {"license_management": "manual"})

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_upgrade_with_uncaught_exception(self, *mock_args: Any) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        self.add_card_to_customer_for_upgrade()
        with patch(
            "corporate.lib.stripe.BillingSession.create_stripe_invoice_and_charge",
            side_effect=Exception,
        ), self.assertLogs("corporate.stripe", "WARNING") as m:
            response = self.upgrade(talk_to_stripe=False)
            self.assertIn("ERROR:corporate.stripe:Uncaught exception in billing", m.output[0])
            self.assertIn(m.records[0].stack_info, m.output[0])
        self.assert_json_error_contains(
            response, "Something went wrong. Please contact desdemona+admin@zulip.com."
        )
        self.assertEqual(
            orjson.loads(response.content)["error_description"], "uncaught exception during upgrade"
        )

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_invoice_payment_succeeded_event_with_uncaught_exception(self, *mock_args: Any) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        self.add_card_to_customer_for_upgrade()

        with patch(
            "corporate.lib.stripe.BillingSession.process_initial_upgrade", side_effect=Exception
        ), self.assertLogs("corporate.stripe", "WARNING"):
            response = self.upgrade()

        response_dict = self.assert_json_success(response)

        self.assert_details_of_valid_invoice_payment_from_event_status_endpoint(
            response_dict["stripe_invoice_id"],
            {
                "status": "paid",
                "event_handler": {
                    "status": "failed",
                    "error": {
                        "message": "Something went wrong. Please contact desdemona+admin@zulip.com.",
                        "description": "uncaught exception in invoice.paid event handler",
                    },
                },
            },
        )

    def test_request_sponsorship_form_with_invalid_url(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        data = {
            "organization_type": Realm.ORG_TYPES["opensource"]["id"],
            "website": "invalid-url",
            "description": "Infinispan is a distributed in-memory key/value data store with optional schema.",
            "expected_total_users": "10 users",
            "paid_users_count": "1 user",
            "paid_users_description": "We have 1 paid user.",
        }

        response = self.client_billing_post("/billing/sponsorship", data)

        self.assert_json_error(response, "Enter a valid URL.")

    def test_request_sponsorship_form_with_blank_url(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        data = {
            "organization_type": Realm.ORG_TYPES["opensource"]["id"],
            "website": "",
            "description": "Infinispan is a distributed in-memory key/value data store with optional schema.",
            "expected_total_users": "10 users",
            "paid_users_count": "1 user",
            "paid_users_description": "We have 1 paid user.",
        }

        response = self.client_billing_post("/billing/sponsorship", data)

        self.assert_json_success(response)

    @mock_stripe()
    def test_sponsorship_access_for_realms_on_paid_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_and_upgrade(user)
        response = self.client_get("/sponsorship/")
        self.assert_in_success_response(
            [
                "How many paid staff does your organization have?",
            ],
            response,
        )

    def test_demo_request(self) -> None:
        result = self.client_get("/request-demo/")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Request a demo"], result)

        data = {
            "full_name": "King Hamlet",
            "email": "test@zulip.com",
            "role": "Manager",
            "organization_name": "Zulip",
            "organization_type": "Business",
            "organization_website": "https://example.com",
            "expected_user_count": "10 (2 unpaid members)",
            "message": "Need help!",
        }
        result = self.client_post("/request-demo/", data)
        self.assert_in_success_response(["Thanks for contacting us!"], result)

        from django.core.mail import outbox

        self.assert_length(outbox, 1)

        for message in outbox:
            self.assert_length(message.to, 1)
            self.assertEqual(message.to[0], "sales@zulip.com")
            self.assertEqual(message.subject, "Demo request for Zulip")
            self.assertEqual(message.reply_to, ["test@zulip.com"])
            self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)
            self.assertIn("Zulip demo request <noreply-", self.email_display_from(message))
            self.assertIn("Full name: King Hamlet", message.body)

    def test_support_request(self) -> None:
        user = self.example_user("hamlet")
        self.assertIsNone(get_customer_by_realm(user.realm))

        self.login_user(user)

        result = self.client_get("/support/")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Contact support"], result)

        data = {
            "request_subject": "Not getting messages.",
            "request_message": "Running into this weird issue.",
        }
        result = self.client_post("/support/", data)
        self.assert_in_success_response(["Thanks for contacting us!"], result)

        from django.core.mail import outbox

        self.assert_length(outbox, 1)

        for message in outbox:
            self.assert_length(message.to, 1)
            self.assertEqual(message.to[0], "desdemona+admin@zulip.com")
            self.assertEqual(message.subject, "Support request for zulip")
            self.assertEqual(message.reply_to, ["hamlet@zulip.com"])
            self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)
            self.assertIn("Zulip support request <noreply-", self.email_display_from(message))
            self.assertIn("Requested by: King Hamlet (Member)", message.body)
            self.assertIn(
                "Support URL: http://zulip.testserver/activity/support?q=zulip", message.body
            )
            self.assertIn("Subject: Not getting messages.", message.body)
            self.assertIn("Message:\nRunning into this weird issue", message.body)

    def test_request_sponsorship(self) -> None:
        user = self.example_user("hamlet")
        self.assertIsNone(get_customer_by_realm(user.realm))

        self.login_user(user)

        data = {
            "organization_type": Realm.ORG_TYPES["opensource"]["id"],
            "website": "https://infinispan.org/",
            "description": "Infinispan is a distributed in-memory key/value data store with optional schema.",
            "expected_total_users": "10 users",
            "paid_users_count": "1 user",
            "paid_users_description": "We have 1 paid user.",
        }
        response = self.client_billing_post("/billing/sponsorship", data)
        self.assert_json_success(response)

        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        sponsorship_request = ZulipSponsorshipRequest.objects.filter(
            customer=customer, requested_by=user
        ).first()
        assert sponsorship_request is not None
        self.assertEqual(sponsorship_request.org_website, data["website"])
        self.assertEqual(sponsorship_request.org_description, data["description"])
        self.assertEqual(
            sponsorship_request.org_type,
            Realm.ORG_TYPES["opensource"]["id"],
        )

        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        self.assertEqual(customer.sponsorship_pending, True)
        from django.core.mail import outbox

        self.assert_length(outbox, 1)

        for message in outbox:
            self.assert_length(message.to, 1)
            self.assertEqual(message.to[0], "sales@zulip.com")
            self.assertEqual(message.subject, "Sponsorship request for zulip")
            self.assertEqual(message.reply_to, ["hamlet@zulip.com"])
            self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)
            self.assertIn("Zulip sponsorship request <noreply-", self.email_display_from(message))
            self.assertIn("Requested by: King Hamlet (Member)", message.body)
            self.assertIn(
                "Support URL: http://zulip.testserver/activity/support?q=zulip", message.body
            )
            self.assertIn("Website: https://infinispan.org", message.body)
            self.assertIn("Organization type: Open-source", message.body)
            self.assertIn("Description:\nInfinispan is a distributed in-memory", message.body)

        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://zulip.testserver/sponsorship")

        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/sponsorship/")

        response = self.client_get("/sponsorship/")
        self.assert_in_success_response(
            [
                "This organization has requested sponsorship for a",
                '<a href="/plans/">Zulip Cloud Standard</a>',
                'plan.<br/><a href="mailto:support@zulip.com">Contact Zulip support</a> with any questions or updates.',
            ],
            response,
        )

        self.login_user(self.example_user("othello"))
        response = self.client_get("/billing/")
        self.assert_in_success_response(
            ["You must be an organization owner or a billing administrator to view this page."],
            response,
        )

        response = self.client_get("/invoices/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/billing/")

        response = self.client_get("/customer_portal/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/billing/")

        user.realm.plan_type = Realm.PLAN_TYPE_PLUS
        user.realm.save()
        response = self.client_get("/sponsorship/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/billing/")

        user.realm.plan_type = Realm.PLAN_TYPE_STANDARD_FREE
        user.realm.save()
        self.login_user(self.example_user("hamlet"))
        response = self.client_get("/sponsorship/")
        self.assert_in_success_response(
            [
                'Zulip is sponsoring a free <a href="/plans/">Zulip Cloud Standard</a> plan for this organization. 🎉'
            ],
            response,
        )

    def test_redirect_for_billing_page(self) -> None:
        user = self.example_user("iago")
        self.login_user(user)
        response = self.client_get("/billing/")
        not_admin_message = (
            "You must be an organization owner or a billing administrator to view this page."
        )
        self.assert_in_success_response([not_admin_message], response)

        user.realm.plan_type = Realm.PLAN_TYPE_STANDARD_FREE
        user.realm.save()
        response = self.client_get("/billing/")
        self.assert_in_success_response([not_admin_message], response)

        # Billing page redirects to sponsorship page for standard free admins.
        user = self.example_user("hamlet")
        self.login_user(user)
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/sponsorship/", response["Location"])

        user.realm.plan_type = Realm.PLAN_TYPE_LIMITED
        user.realm.save()
        customer = Customer.objects.create(realm=user.realm, stripe_customer_id="cus_123")
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/plans/", response["Location"])

        # Check redirects for sponsorship pending
        customer.sponsorship_pending = True
        customer.save()
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/sponsorship/", response["Location"])

        # Don't redirect to sponsorship for paid plans.
        user.realm.plan_type = Realm.PLAN_TYPE_STANDARD
        user.realm.save()
        response = self.client_get("/billing/")
        self.assertNotEqual("/sponsorship/", response["Location"])

        user.realm.plan_type = Realm.PLAN_TYPE_PLUS
        user.realm.save()
        response = self.client_get("/billing/")
        self.assertNotEqual("/sponsorship/", response["Location"])

    @mock_stripe(tested_timestamp_fields=["created"])
    def test_redirect_for_billing_page_downgrade_at_free_trial_end(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        with self.settings(CLOUD_FREE_TRIAL_DAYS=30):
            response = self.client_get("/upgrade/")
            free_trial_end_date = self.now + timedelta(days=30)

            self.assert_in_success_response(
                ["Your card will not be charged", "free trial", "30-day"], response
            )
            self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

            stripe_customer = self.add_card_and_upgrade(user)
            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
            plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=True,
                price_per_license=8000,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                invoiced_through=LicenseLedger.objects.first(),
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                # For payment through card.
                charge_automatically=True,
            )
            LicenseLedger.objects.get(
                plan=plan,
                is_renewal=True,
                event_time=self.now,
                licenses=self.seat_count,
                licenses_at_next_renewal=self.seat_count,
            )

            realm = get_realm("zulip")
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")
            self.assert_not_in_success_response(["Pay annually"], response)
            for substring in [
                "Zulip Cloud Standard <i>(free trial)</i>",
                "Your plan will automatically renew on",
                "February 1, 2012",
                "Visa ending in 4242",
                "Update card",
            ]:
                self.assert_in_response(substring, response)

            # schedule downgrade
            with time_machine.travel(self.now + timedelta(days=3), tick=False), self.assertLogs(
                "corporate.stripe", "INFO"
            ) as m:
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL},
                )
                self.assert_json_success(response)
                plan.refresh_from_db()
                self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL)
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL}"
                self.assertEqual(m.output[0], expected_log)

            # Visit /billing on free-trial end date before the invoice cron runs.
            with time_machine.travel(free_trial_end_date, tick=False):
                response = self.client_get("/billing/")
                self.assertEqual(response.status_code, 302)
                self.assertEqual("/plans/", response["Location"])

    def test_upgrade_page_for_demo_organizations(self) -> None:
        user = self.example_user("hamlet")
        user.realm.demo_organization_scheduled_deletion_date = timezone_now() + timedelta(days=30)
        user.realm.save()
        self.login_user(user)

        response = self.client_get("/billing/", follow=True)
        self.assert_in_success_response(["cannot be directly upgraded"], response)

    def test_redirect_for_upgrade_page(self) -> None:
        user = self.example_user("iago")
        self.login_user(user)

        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 200)

        user.realm.plan_type = Realm.PLAN_TYPE_STANDARD_FREE
        user.realm.save()
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://zulip.testserver/sponsorship")

        # Avoid contacting stripe as we only want to check redirects here.
        with patch(
            "corporate.lib.stripe.customer_has_credit_card_as_default_payment_method",
            return_value=False,
        ):
            user.realm.plan_type = Realm.PLAN_TYPE_LIMITED
            user.realm.save()
            customer = Customer.objects.create(realm=user.realm, stripe_customer_id="cus_123")
            response = self.client_get("/upgrade/")
            self.assertEqual(response.status_code, 200)

            CustomerPlan.objects.create(
                customer=customer,
                billing_cycle_anchor=timezone_now(),
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
            )
            response = self.client_get("/upgrade/")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], "http://zulip.testserver/billing")

            with self.settings(CLOUD_FREE_TRIAL_DAYS=30):
                response = self.client_get("/upgrade/")
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], "http://zulip.testserver/billing")

    def test_get_latest_seat_count(self) -> None:
        realm = get_realm("zulip")
        initial_count = get_latest_seat_count(realm)
        user1 = UserProfile.objects.create(
            realm=realm, email="user1@zulip.com", delivery_email="user1@zulip.com"
        )
        user2 = UserProfile.objects.create(
            realm=realm, email="user2@zulip.com", delivery_email="user2@zulip.com"
        )
        self.assertEqual(get_latest_seat_count(realm), initial_count + 2)

        # Test that bots aren't counted
        user1.is_bot = True
        user1.save(update_fields=["is_bot"])
        self.assertEqual(get_latest_seat_count(realm), initial_count + 1)

        # Test that inactive users aren't counted
        do_deactivate_user(user2, acting_user=None)
        self.assertEqual(get_latest_seat_count(realm), initial_count)

        # Test guests
        # Adding a guest to a realm with a lot of members shouldn't change anything
        UserProfile.objects.create(
            realm=realm,
            email="user3@zulip.com",
            delivery_email="user3@zulip.com",
            role=UserProfile.ROLE_GUEST,
        )
        self.assertEqual(get_latest_seat_count(realm), initial_count)
        # Test 1 member and 5 guests
        realm = do_create_realm(string_id="second", name="second")
        UserProfile.objects.create(
            realm=realm, email="member@second.com", delivery_email="member@second.com"
        )
        for i in range(5):
            UserProfile.objects.create(
                realm=realm,
                email=f"guest{i}@second.com",
                delivery_email=f"guest{i}@second.com",
                role=UserProfile.ROLE_GUEST,
            )
        self.assertEqual(get_latest_seat_count(realm), 1)
        # Test 1 member and 6 guests
        UserProfile.objects.create(
            realm=realm,
            email="guest5@second.com",
            delivery_email="guest5@second.com",
            role=UserProfile.ROLE_GUEST,
        )
        self.assertEqual(get_latest_seat_count(realm), 2)

    def test_sign_string(self) -> None:
        string = "abc"
        signed_string, salt = sign_string(string)
        self.assertEqual(string, unsign_string(signed_string, salt))

        with self.assertRaises(signing.BadSignature):
            unsign_string(signed_string, "randomsalt")

    @mock_stripe()
    def test_payment_method_string(self, *mocks: Mock) -> None:
        # If you pay by invoice, your payment method should be
        # "Invoice", even if you have a card on file.
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(user)
        billing_session.create_stripe_customer()
        self.login_user(user)
        self.add_card_to_customer_for_upgrade()
        self.upgrade(invoice=True)
        response = self.client_get("/billing/")
        self.assert_not_in_success_response(["Visa ending in"], response)
        self.assert_in_success_response(["Invoice", "You will receive an invoice for"], response)

    @mock_stripe()
    def test_replace_payment_method(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_and_upgrade(user)
        # Create an open invoice
        customer = Customer.objects.first()
        assert customer is not None
        stripe_customer_id = customer.stripe_customer_id
        assert stripe_customer_id is not None
        stripe.InvoiceItem.create(amount=5000, currency="usd", customer=stripe_customer_id)
        stripe_invoice = stripe.Invoice.create(customer=stripe_customer_id)
        stripe.Invoice.finalize_invoice(stripe_invoice)
        RealmAuditLog.objects.filter(event_type=RealmAuditLog.STRIPE_CARD_CHANGED).delete()

        start_session_json_response = self.client_billing_post(
            "/billing/session/start_card_update_session"
        )
        response_dict = self.assert_json_success(start_session_json_response)
        self.assert_details_of_valid_session_from_event_status_endpoint(
            response_dict["stripe_session_id"],
            {
                "type": "card_update_from_billing_page",
                "status": "created",
                "is_manual_license_management_upgrade_session": False,
                "tier": None,
            },
        )
        with self.assertRaises(stripe.CardError):
            # We don't have to handle this since the Stripe Checkout page would
            # ask Customer to enter a valid card number. trigger_stripe_checkout_session_completed_webhook
            # emulates what happens in the Stripe Checkout page. Adding this check mostly for coverage of
            # create_payment_method.
            self.trigger_stripe_checkout_session_completed_webhook(
                self.get_test_card_token(attaches_to_customer=False)
            )

        start_session_json_response = self.client_billing_post(
            "/billing/session/start_card_update_session"
        )
        response_dict = self.assert_json_success(start_session_json_response)
        self.assert_details_of_valid_session_from_event_status_endpoint(
            response_dict["stripe_session_id"],
            {
                "type": "card_update_from_billing_page",
                "status": "created",
                "is_manual_license_management_upgrade_session": False,
                "tier": None,
            },
        )
        with self.assertLogs("corporate.stripe", "INFO") as m:
            self.trigger_stripe_checkout_session_completed_webhook(
                self.get_test_card_token(attaches_to_customer=True, charge_succeeds=False)
            )
            self.assertEqual(
                m.output[0],
                "INFO:corporate.stripe:Stripe card error: 402 card_error card_declined None",
            )
        response_dict = self.assert_json_success(start_session_json_response)
        self.assert_details_of_valid_session_from_event_status_endpoint(
            response_dict["stripe_session_id"],
            {
                "type": "card_update_from_billing_page",
                "status": "completed",
                "is_manual_license_management_upgrade_session": False,
                "tier": None,
                "event_handler": {
                    "status": "failed",
                    "error": {"message": "Your card was declined.", "description": "card error"},
                },
            },
        )

        response = self.client_get("/billing/")
        self.assert_in_success_response(["Visa ending in 0341"], response)
        assert RealmAuditLog.objects.filter(event_type=RealmAuditLog.STRIPE_CARD_CHANGED).exists()
        stripe_payment_methods = stripe.PaymentMethod.list(customer=stripe_customer_id, type="card")
        self.assert_length(stripe_payment_methods, 2)

        for stripe_payment_method in stripe_payment_methods:
            stripe.PaymentMethod.detach(stripe_payment_method.id)
        response = self.client_get("/billing/")
        self.assert_in_success_response(["No payment method on file."], response)

        start_session_json_response = self.client_billing_post(
            "/billing/session/start_card_update_session"
        )
        self.assert_json_success(start_session_json_response)
        self.trigger_stripe_checkout_session_completed_webhook(
            self.get_test_card_token(
                attaches_to_customer=True, charge_succeeds=True, card_provider="mastercard"
            )
        )
        response_dict = self.assert_json_success(start_session_json_response)
        self.assert_details_of_valid_session_from_event_status_endpoint(
            response_dict["stripe_session_id"],
            {
                "type": "card_update_from_billing_page",
                "status": "completed",
                "is_manual_license_management_upgrade_session": False,
                "tier": None,
                "event_handler": {"status": "succeeded"},
            },
        )

        self.login_user(self.example_user("iago"))
        response = self.client_billing_get(
            "/billing/event/status",
            {"stripe_session_id": response_dict["stripe_session_id"]},
        )
        self.assert_json_error_contains(
            response, "Must be a billing administrator or an organization owner"
        )

        self.login_user(self.example_user("hamlet"))
        response = self.client_get("/billing/")
        self.assert_in_success_response(["Mastercard ending in 4444"], response)
        self.assert_length(stripe.PaymentMethod.list(customer=stripe_customer_id, type="card"), 1)
        # Ideally we'd also test that we don't pay invoices with collection_method=='send_invoice'
        for stripe_invoice in stripe.Invoice.list(customer=stripe_customer_id):
            self.assertEqual(stripe_invoice.status, "paid")
        self.assertEqual(
            2, RealmAuditLog.objects.filter(event_type=RealmAuditLog.STRIPE_CARD_CHANGED).count()
        )

        # Test if manual license management upgrade session is created and is successfully recovered.
        start_session_json_response = self.client_billing_post(
            "/upgrade/session/start_card_update_session",
            {
                "manual_license_management": "true",
                "tier": 1,
            },
        )
        response_dict = self.assert_json_success(start_session_json_response)
        self.assert_details_of_valid_session_from_event_status_endpoint(
            response_dict["stripe_session_id"],
            {
                "type": "card_update_from_upgrade_page",
                "status": "created",
                "is_manual_license_management_upgrade_session": True,
                "tier": 1,
            },
        )

    def test_downgrade(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        plan = get_current_plan_by_realm(user.realm)
        assert plan is not None
        self.assertEqual(plan.licenses(), self.seat_count)
        self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
                )
                stripe_customer_id = Customer.objects.get(realm=user.realm).id
                new_plan = get_current_plan_by_realm(user.realm)
                assert new_plan is not None
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
                self.assertEqual(m.output[0], expected_log)
                self.assert_json_success(response)
        plan.refresh_from_db()
        self.assertEqual(plan.licenses(), self.seat_count)
        self.assertEqual(plan.licenses_at_next_renewal(), None)

        with time_machine.travel(self.now, tick=False):
            mock_customer = Mock(email=user.delivery_email)
            mock_customer.invoice_settings.default_payment_method = Mock(
                spec=stripe.PaymentMethod, type=Mock()
            )
            with patch("corporate.lib.stripe.stripe_get_customer", return_value=mock_customer):
                response = self.client_get("/billing/")
                self.assert_in_success_response(
                    [
                        "Your organization will be downgraded to <strong>Zulip Cloud Free</strong> at the end of the current billing",
                        "<strong>January 2, 2013</strong>",
                        "Reactivate subscription",
                    ],
                    response,
                )

        # Verify that we still write LicenseLedger rows during the remaining
        # part of the cycle
        billing_session = RealmBillingSession(user=user, realm=user.realm)
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
            billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(
            LicenseLedger.objects.order_by("-id")
            .values_list("licenses", "licenses_at_next_renewal")
            .first(),
            (20, 20),
        )

        # Verify that we invoice them for the additional users
        mocked = self.setup_mocked_stripe(invoice_plans_as_needed, self.next_month)
        mocked["InvoiceItem"].create.assert_called_once()
        mocked["Invoice"].finalize_invoice.assert_called_once()
        mocked["Invoice"].create.assert_called_once()

        # Check that we downgrade properly if the cycle is over
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=30):
            billing_session.update_license_ledger_if_needed(self.next_year)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_LIMITED)
        self.assertEqual(plan.status, CustomerPlan.ENDED)
        self.assertEqual(
            LicenseLedger.objects.order_by("-id")
            .values_list("licenses", "licenses_at_next_renewal")
            .first(),
            (20, 20),
        )
        realm_audit_log = RealmAuditLog.objects.latest("id")
        self.assertEqual(realm_audit_log.event_type, RealmAuditLog.REALM_PLAN_TYPE_CHANGED)
        self.assertEqual(realm_audit_log.acting_user, None)

        # Verify that we don't write LicenseLedger rows once we've downgraded
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=40):
            billing_session.update_license_ledger_if_needed(self.next_year)
        self.assertEqual(
            LicenseLedger.objects.order_by("-id")
            .values_list("licenses", "licenses_at_next_renewal")
            .first(),
            (20, 20),
        )

        # Verify that we call invoice_plan once more after cycle end but
        # don't invoice them for users added after the cycle end
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertIsNotNone(plan.next_invoice_date)

        mocked = self.setup_mocked_stripe(
            invoice_plans_as_needed, self.next_year + timedelta(days=32)
        )
        mocked["InvoiceItem"].create.assert_not_called()
        mocked["Invoice"].finalize_invoice.assert_not_called()
        mocked["Invoice"].create.assert_not_called()

        # Check that we updated next_invoice_date in invoice_plan
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertIsNone(plan.next_invoice_date)

        # Check that we don't call invoice_plan after that final call
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=50):
            billing_session.update_license_ledger_if_needed(self.next_year + timedelta(days=80))

        mocked = self.setup_mocked_stripe(
            invoice_plans_as_needed, self.next_year + timedelta(days=400)
        )
        mocked["InvoiceItem"].create.assert_not_called()
        mocked["Invoice"].finalize_invoice.assert_not_called()
        mocked["Invoice"].create.assert_not_called()

    @mock_stripe()
    def test_switch_from_monthly_plan_to_annual_plan_for_automatic_license_management(
        self, *mocks: Mock
    ) -> None:
        user = self.example_user("hamlet")

        self.login_user(user)
        self.add_card_and_upgrade(user, schedule="monthly")
        monthly_plan = get_current_plan_by_realm(user.realm)
        assert monthly_plan is not None
        self.assertEqual(monthly_plan.automanage_licenses, True)
        self.assertEqual(monthly_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_MONTHLY)

        stripe_customer_id = Customer.objects.get(realm=user.realm).id
        new_plan = get_current_plan_by_realm(user.realm)
        assert new_plan is not None

        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE},
                )
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE}"
                self.assertEqual(m.output[0], expected_log)
                self.assert_json_success(response)
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.status, CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE)
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_in_success_response(
            ["Your plan will switch to annual billing on February 2, 2012"], response
        )

        billing_session = RealmBillingSession(user=user, realm=user.realm)
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
            billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(LicenseLedger.objects.filter(plan=monthly_plan).count(), 2)
        self.assertEqual(
            LicenseLedger.objects.order_by("-id")
            .values_list("licenses", "licenses_at_next_renewal")
            .first(),
            (20, 20),
        )

        with time_machine.travel(self.next_month, tick=False):
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=25):
                billing_session.update_license_ledger_if_needed(self.next_month)
        self.assertEqual(LicenseLedger.objects.filter(plan=monthly_plan).count(), 2)
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        self.assertEqual(CustomerPlan.objects.filter(customer=customer).count(), 2)
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.status, CustomerPlan.ENDED)
        self.assertEqual(monthly_plan.next_invoice_date, self.next_month)
        annual_plan = get_current_plan_by_realm(user.realm)
        assert annual_plan is not None
        self.assertEqual(annual_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(annual_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_ANNUAL)
        self.assertEqual(
            annual_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )
        self.assertEqual(annual_plan.billing_cycle_anchor, self.next_month)
        self.assertEqual(annual_plan.next_invoice_date, self.next_month)
        self.assertEqual(annual_plan.invoiced_through, None)
        annual_ledger_entries = LicenseLedger.objects.filter(plan=annual_plan).order_by("id")
        self.assert_length(annual_ledger_entries, 2)
        self.assertEqual(annual_ledger_entries[0].is_renewal, True)
        self.assertEqual(
            annual_ledger_entries.values_list("licenses", "licenses_at_next_renewal")[0], (20, 20)
        )
        self.assertEqual(annual_ledger_entries[1].is_renewal, False)
        self.assertEqual(
            annual_ledger_entries.values_list("licenses", "licenses_at_next_renewal")[1], (25, 25)
        )
        audit_log = RealmAuditLog.objects.get(
            event_type=RealmAuditLog.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN
        )
        self.assertEqual(audit_log.realm, user.realm)
        self.assertEqual(audit_log.extra_data["monthly_plan_id"], monthly_plan.id)
        self.assertEqual(audit_log.extra_data["annual_plan_id"], annual_plan.id)

        invoice_plans_as_needed(self.next_month)

        annual_ledger_entries = LicenseLedger.objects.filter(plan=annual_plan).order_by("id")
        self.assert_length(annual_ledger_entries, 2)
        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)
        self.assertEqual(annual_plan.invoiced_through, annual_ledger_entries[1])
        self.assertEqual(annual_plan.billing_cycle_anchor, self.next_month)
        self.assertEqual(annual_plan.next_invoice_date, add_months(self.next_month, 1))
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.next_invoice_date, None)

        assert customer.stripe_customer_id
        [invoice0, invoice1, invoice2] = iter(
            stripe.Invoice.list(customer=customer.stripe_customer_id)
        )

        [invoice_item0, invoice_item1] = iter(invoice0.lines)
        annual_plan_invoice_item_params = {
            "amount": 5 * 80 * 100,
            "description": "Additional license (Feb 2, 2012 - Feb 2, 2013)",
            "plan": None,
            "quantity": 5,
            "subscription": None,
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.next_month),
                "end": datetime_to_timestamp(add_months(self.next_month, 12)),
            },
        }
        for key, value in annual_plan_invoice_item_params.items():
            self.assertEqual(invoice_item0[key], value)

        annual_plan_invoice_item_params = {
            "amount": 20 * 80 * 100,
            "description": "Zulip Cloud Standard - renewal",
            "plan": None,
            "quantity": 20,
            "subscription": None,
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.next_month),
                "end": datetime_to_timestamp(add_months(self.next_month, 12)),
            },
        }
        for key, value in annual_plan_invoice_item_params.items():
            self.assertEqual(invoice_item1[key], value)

        [monthly_plan_invoice_item] = iter(invoice1.lines)
        monthly_plan_invoice_item_params = {
            "amount": 14 * 8 * 100,
            "description": "Additional license (Jan 2, 2012 - Feb 2, 2012)",
            "plan": None,
            "quantity": 14,
            "subscription": None,
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.now),
                "end": datetime_to_timestamp(self.next_month),
            },
        }
        for key, value in monthly_plan_invoice_item_params.items():
            self.assertEqual(monthly_plan_invoice_item[key], value)

        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=30):
            billing_session.update_license_ledger_if_needed(add_months(self.next_month, 1))
        invoice_plans_as_needed(add_months(self.next_month, 1))

        [invoice0, invoice1, invoice2, invoice3] = iter(
            stripe.Invoice.list(customer=customer.stripe_customer_id)
        )

        [monthly_plan_invoice_item] = iter(invoice0.lines)
        monthly_plan_invoice_item_params = {
            "amount": 5 * 7366,
            "description": "Additional license (Mar 2, 2012 - Feb 2, 2013)",
            "plan": None,
            "quantity": 5,
            "subscription": None,
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(add_months(self.next_month, 1)),
                "end": datetime_to_timestamp(add_months(self.next_month, 12)),
            },
        }
        for key, value in monthly_plan_invoice_item_params.items():
            self.assertEqual(monthly_plan_invoice_item[key], value)

        # Fast forward next_invoice_date to one year from the day we switched to annual plan.
        annual_plan.next_invoice_date = add_months(self.now, 13)
        annual_plan.save(update_fields=["next_invoice_date"])
        invoice_plans_as_needed(add_months(self.now, 13))

        [invoice0, invoice1, invoice2, invoice3, invoice4] = iter(
            stripe.Invoice.list(customer=customer.stripe_customer_id)
        )

        [invoice_item] = iter(invoice0.lines)
        annual_plan_invoice_item_params = {
            "amount": 30 * 80 * 100,
            "description": "Zulip Cloud Standard - renewal",
            "plan": None,
            "quantity": 30,
            "subscription": None,
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(add_months(self.next_month, 12)),
                "end": datetime_to_timestamp(add_months(self.next_month, 24)),
            },
        }
        for key, value in annual_plan_invoice_item_params.items():
            self.assertEqual(invoice_item[key], value)

    @mock_stripe()
    def test_switch_from_monthly_plan_to_annual_plan_for_manual_license_management(
        self, *mocks: Mock
    ) -> None:
        user = self.example_user("hamlet")
        num_licenses = 35

        self.login_user(user)
        self.add_card_and_upgrade(
            user, schedule="monthly", license_management="manual", licenses=num_licenses
        )
        monthly_plan = get_current_plan_by_realm(user.realm)
        assert monthly_plan is not None
        self.assertEqual(monthly_plan.automanage_licenses, False)
        self.assertEqual(monthly_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_MONTHLY)
        stripe_customer_id = Customer.objects.get(realm=user.realm).id
        new_plan = get_current_plan_by_realm(user.realm)
        assert new_plan is not None
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE},
                )
                self.assertEqual(
                    m.output[0],
                    f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE}",
                )
                self.assert_json_success(response)
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.status, CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE)
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_in_success_response(
            ["Your plan will switch to annual billing on February 2, 2012"], response
        )

        invoice_plans_as_needed(self.next_month)

        self.assertEqual(LicenseLedger.objects.filter(plan=monthly_plan).count(), 1)
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        self.assertEqual(CustomerPlan.objects.filter(customer=customer).count(), 2)
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.status, CustomerPlan.ENDED)
        self.assertEqual(monthly_plan.next_invoice_date, None)
        annual_plan = get_current_plan_by_realm(user.realm)
        assert annual_plan is not None
        self.assertEqual(annual_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(annual_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_ANNUAL)
        self.assertEqual(
            annual_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )
        self.assertEqual(annual_plan.billing_cycle_anchor, self.next_month)
        self.assertEqual(annual_plan.next_invoice_date, self.next_month)
        annual_ledger_entries = LicenseLedger.objects.filter(plan=annual_plan).order_by("id")
        self.assert_length(annual_ledger_entries, 1)
        self.assertEqual(annual_ledger_entries[0].is_renewal, True)
        self.assertEqual(
            annual_ledger_entries.values_list("licenses", "licenses_at_next_renewal")[0],
            (num_licenses, num_licenses),
        )
        self.assertEqual(annual_plan.invoiced_through, None)

        # First call of invoice_plans_as_needed creates the new plan. Second call
        # calls invoice_plan on the newly created plan.
        invoice_plans_as_needed(self.next_month + timedelta(days=1))

        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.invoiced_through, annual_ledger_entries[0])
        self.assertEqual(annual_plan.next_invoice_date, add_months(self.next_month, 1))
        self.assertEqual(annual_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)

        assert customer.stripe_customer_id
        [invoice0, invoice1] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))

        [invoice_item] = iter(invoice0.lines)
        annual_plan_invoice_item_params = {
            "amount": num_licenses * 80 * 100,
            "description": "Zulip Cloud Standard - renewal",
            "plan": None,
            "quantity": num_licenses,
            "subscription": None,
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.next_month),
                "end": datetime_to_timestamp(add_months(self.next_month, 12)),
            },
        }
        for key, value in annual_plan_invoice_item_params.items():
            self.assertEqual(invoice_item[key], value)

        invoice_plans_as_needed(add_months(self.now, 13))

        [invoice0, invoice1, invoice2] = iter(
            stripe.Invoice.list(customer=customer.stripe_customer_id)
        )

        [invoice_item] = iter(invoice0.lines)
        annual_plan_invoice_item_params = {
            "amount": num_licenses * 80 * 100,
            "description": "Zulip Cloud Standard - renewal",
            "plan": None,
            "quantity": num_licenses,
            "subscription": None,
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(add_months(self.next_month, 12)),
                "end": datetime_to_timestamp(add_months(self.next_month, 24)),
            },
        }
        for key, value in annual_plan_invoice_item_params.items():
            self.assertEqual(invoice_item[key], value)

    @mock_stripe()
    def test_switch_from_annual_plan_to_monthly_plan_for_automatic_license_management(
        self, *mocks: Mock
    ) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_and_upgrade(user, schedule="annual")
        annual_plan = get_current_plan_by_realm(user.realm)
        assert annual_plan is not None
        self.assertEqual(annual_plan.automanage_licenses, True)
        self.assertEqual(annual_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_ANNUAL)

        stripe_customer_id = Customer.objects.get(realm=user.realm).id
        new_plan = get_current_plan_by_realm(user.realm)
        assert new_plan is not None

        assert self.now is not None
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE},
                )
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE}"
                self.assertEqual(m.output[0], expected_log)
                self.assert_json_success(response)
        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.status, CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE)
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_in_success_response(
            ["Your plan will switch to monthly billing on January 2, 2013"], response
        )

        billing_session = RealmBillingSession(user=user, realm=user.realm)
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
            billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(LicenseLedger.objects.filter(plan=annual_plan).count(), 2)
        self.assertEqual(
            LicenseLedger.objects.order_by("-id")
            .values_list("licenses", "licenses_at_next_renewal")
            .first(),
            (20, 20),
        )

        # Check that we don't switch to monthly plan at next invoice date (which is used to charge user for
        # additional licenses) but at the end of current billing cycle.
        self.assertEqual(annual_plan.next_invoice_date, self.next_month)
        assert annual_plan.next_invoice_date is not None
        with time_machine.travel(annual_plan.next_invoice_date, tick=False):
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=25):
                billing_session.update_license_ledger_if_needed(annual_plan.next_invoice_date)

        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.status, CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE)
        self.assertEqual(annual_plan.next_invoice_date, self.next_month)
        self.assertEqual(annual_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_ANNUAL)
        self.assertEqual(LicenseLedger.objects.filter(plan=annual_plan).count(), 3)

        invoice_plans_as_needed(self.next_month + timedelta(days=1))

        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.next_invoice_date, add_months(self.next_month, 1))
        self.assertEqual(annual_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)
        self.assertEqual(LicenseLedger.objects.filter(plan=annual_plan).count(), 3)

        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        assert customer.stripe_customer_id
        [invoice0, invoice1] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))
        [invoice_item1, invoice_item2] = iter(invoice0.lines)
        annual_plan_invoice_item_params = {
            "amount": 7322 * 5,
            "description": "Additional license (Feb 2, 2012 - Jan 2, 2013)",
            "plan": None,
            "quantity": 5,
            "subscription": None,
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.next_month),
                "end": datetime_to_timestamp(self.next_year),
            },
        }

        for key, value in annual_plan_invoice_item_params.items():
            self.assertEqual(invoice_item1[key], value)

        annual_plan_invoice_item_params = {
            "amount": 14 * 80 * 1 * 100,
            "description": "Additional license (Jan 2, 2012 - Jan 2, 2013)",
            "plan": None,
            "quantity": 14,
            "subscription": None,
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.now),
                "end": datetime_to_timestamp(self.next_year),
            },
        }

        for key, value in annual_plan_invoice_item_params.items():
            self.assertEqual(invoice_item2[key], value)

        # Check that we switch to monthly plan at the end of current billing cycle.
        with time_machine.travel(self.next_year, tick=False):
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=25):
                billing_session.update_license_ledger_if_needed(self.next_year)
        self.assertEqual(LicenseLedger.objects.filter(plan=annual_plan).count(), 3)
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.status, CustomerPlan.ENDED)
        self.assertEqual(annual_plan.next_invoice_date, add_months(self.next_month, 1))
        monthly_plan = get_current_plan_by_realm(user.realm)
        assert monthly_plan is not None
        self.assertEqual(monthly_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(monthly_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_MONTHLY)
        self.assertEqual(
            monthly_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )
        self.assertEqual(monthly_plan.billing_cycle_anchor, self.next_year)
        self.assertEqual(monthly_plan.next_invoice_date, self.next_year)
        self.assertEqual(monthly_plan.invoiced_through, None)
        monthly_ledger_entries = LicenseLedger.objects.filter(plan=monthly_plan).order_by("id")
        self.assert_length(monthly_ledger_entries, 2)
        self.assertEqual(monthly_ledger_entries[0].is_renewal, True)
        self.assertEqual(
            monthly_ledger_entries.values_list("licenses", "licenses_at_next_renewal")[0], (25, 25)
        )
        self.assertEqual(monthly_ledger_entries[1].is_renewal, False)
        self.assertEqual(
            monthly_ledger_entries.values_list("licenses", "licenses_at_next_renewal")[1], (25, 25)
        )
        audit_log = RealmAuditLog.objects.get(
            event_type=RealmAuditLog.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN
        )
        self.assertEqual(audit_log.realm, user.realm)
        self.assertEqual(audit_log.extra_data["annual_plan_id"], annual_plan.id)
        self.assertEqual(audit_log.extra_data["monthly_plan_id"], monthly_plan.id)

        invoice_plans_as_needed(self.next_year)

        monthly_ledger_entries = LicenseLedger.objects.filter(plan=monthly_plan).order_by("id")
        self.assert_length(monthly_ledger_entries, 2)
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)
        self.assertEqual(monthly_plan.invoiced_through, monthly_ledger_entries[1])
        self.assertEqual(monthly_plan.billing_cycle_anchor, self.next_year)
        self.assertEqual(monthly_plan.next_invoice_date, add_months(self.next_year, 1))
        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.next_invoice_date, None)

        assert customer.stripe_customer_id
        [invoice0, invoice1, invoice2] = iter(
            stripe.Invoice.list(customer=customer.stripe_customer_id)
        )

        [invoice_item0] = iter(invoice0.lines)

        monthly_plan_invoice_item_params = {
            "amount": 25 * 8 * 100,
            "description": "Zulip Cloud Standard - renewal",
            "plan": None,
            "quantity": 25,
            "subscription": None,
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.next_year),
                "end": datetime_to_timestamp(add_months(self.next_year, 1)),
            },
        }
        for key, value in monthly_plan_invoice_item_params.items():
            self.assertEqual(invoice_item0[key], value)

        with time_machine.travel(self.next_year, tick=False):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(
            ["Your plan will switch to annual billing on February 2, 2012"], response
        )

    def test_reupgrade_after_plan_status_changed_to_downgrade_at_end_of_cycle(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
                )
                stripe_customer_id = Customer.objects.get(realm=user.realm).id
                new_plan = get_current_plan_by_realm(user.realm)
                assert new_plan is not None
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
                self.assertEqual(m.output[0], expected_log)
                self.assert_json_success(response)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE)
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.ACTIVE},
                )
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.ACTIVE}"
                self.assertEqual(m.output[0], expected_log)
                self.assert_json_success(response)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.status, CustomerPlan.ACTIVE)

    @patch("stripe.Invoice.create")
    @patch("stripe.Invoice.finalize_invoice")
    @patch("stripe.InvoiceItem.create")
    def test_downgrade_during_invoicing(self, *mocks: Mock) -> None:
        # The difference between this test and test_downgrade is that
        # CustomerPlan.status is DOWNGRADE_AT_END_OF_CYCLE rather than ENDED
        # when we call invoice_plans_as_needed
        # This test is essentially checking that we call make_end_of_cycle_updates_if_needed
        # during the invoicing process.
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        with self.assertLogs("corporate.stripe", "INFO") as m:
            stripe_customer_id = Customer.objects.get(realm=user.realm).id
            new_plan = get_current_plan_by_realm(user.realm)
            assert new_plan is not None
            with time_machine.travel(self.now, tick=False):
                self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
                )
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)

        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertIsNotNone(plan.next_invoice_date)
        self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE)
        # Fast forward the next_invoice_date to next year.
        plan.next_invoice_date = self.next_year
        plan.save(update_fields=["next_invoice_date"])
        invoice_plans_as_needed(self.next_year)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertIsNone(plan.next_invoice_date)
        self.assertEqual(plan.status, CustomerPlan.ENDED)

    @mock_stripe()
    def test_switch_now_free_trial_from_monthly_to_annual(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(user, schedule="monthly")
                plan = CustomerPlan.objects.get()
                self.assertEqual(plan.next_invoice_date, free_trial_end_date)
                self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
                self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)

                customer = get_customer_by_realm(user.realm)
                assert customer is not None
                result = self.client_billing_patch(
                    "/billing/plan",
                    {
                        "status": CustomerPlan.FREE_TRIAL,
                        "schedule": CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    },
                )
                self.assert_json_success(result)

                plan.refresh_from_db()
                self.assertEqual(plan.status, CustomerPlan.ENDED)
                self.assertIsNone(plan.next_invoice_date)

                new_plan = CustomerPlan.objects.get(
                    customer=customer,
                    automanage_licenses=True,
                    price_per_license=8000,
                    fixed_price=None,
                    discount=None,
                    billing_cycle_anchor=self.now,
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    next_invoice_date=free_trial_end_date,
                    tier=CustomerPlan.TIER_CLOUD_STANDARD,
                    status=CustomerPlan.FREE_TRIAL,
                    charge_automatically=True,
                )
                ledger_entry = LicenseLedger.objects.get(
                    plan=new_plan,
                    is_renewal=True,
                    event_time=self.now,
                    licenses=self.seat_count,
                    licenses_at_next_renewal=self.seat_count,
                )
                self.assertEqual(new_plan.invoiced_through, ledger_entry)

                realm_audit_log = RealmAuditLog.objects.filter(
                    event_type=RealmAuditLog.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN
                ).last()
                assert realm_audit_log is not None

    @mock_stripe()
    def test_switch_now_free_trial_from_annual_to_monthly(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(user, schedule="annual")
                plan = CustomerPlan.objects.get()
                self.assertEqual(plan.next_invoice_date, free_trial_end_date)
                self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
                self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)

                customer = get_customer_by_realm(user.realm)
                assert customer is not None
                result = self.client_billing_patch(
                    "/billing/plan",
                    {
                        "status": CustomerPlan.FREE_TRIAL,
                        "schedule": CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    },
                )
                self.assert_json_success(result)
                plan.refresh_from_db()
                self.assertEqual(plan.status, CustomerPlan.ENDED)
                self.assertIsNone(plan.next_invoice_date)

                new_plan = CustomerPlan.objects.get(
                    customer=customer,
                    automanage_licenses=True,
                    price_per_license=800,
                    fixed_price=None,
                    discount=None,
                    billing_cycle_anchor=self.now,
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    next_invoice_date=free_trial_end_date,
                    tier=CustomerPlan.TIER_CLOUD_STANDARD,
                    status=CustomerPlan.FREE_TRIAL,
                    charge_automatically=True,
                )
                ledger_entry = LicenseLedger.objects.get(
                    plan=new_plan,
                    is_renewal=True,
                    event_time=self.now,
                    licenses=self.seat_count,
                    licenses_at_next_renewal=self.seat_count,
                )
                self.assertEqual(new_plan.invoiced_through, ledger_entry)

                realm_audit_log = RealmAuditLog.objects.filter(
                    event_type=RealmAuditLog.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN
                ).last()
                assert realm_audit_log is not None

    @mock_stripe()
    def test_end_free_trial(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(user, schedule="annual")

            plan = CustomerPlan.objects.get()
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)

            # Add some extra users before the realm is deactivated
            billing_session = RealmBillingSession(user=user, realm=user.realm)
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=21):
                billing_session.update_license_ledger_if_needed(self.now)

            last_ledger_entry = LicenseLedger.objects.order_by("id").last()
            assert last_ledger_entry is not None
            self.assertEqual(last_ledger_entry.licenses, 21)
            self.assertEqual(last_ledger_entry.licenses_at_next_renewal, 21)

            self.login_user(user)

            with time_machine.travel(self.now, tick=False):
                self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.ENDED},
                )

            plan.refresh_from_db()
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_LIMITED)
            self.assertEqual(plan.status, CustomerPlan.ENDED)
            self.assertEqual(plan.invoiced_through, last_ledger_entry)
            self.assertIsNone(plan.next_invoice_date)

            self.login_user(user)
            response = self.client_get("/billing/")
            self.assertEqual(response.status_code, 302)
            self.assertEqual("/plans/", response["Location"])

            # The extra users added in the final month are not charged
            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_month)
            mocked.assert_not_called()

            # The plan is not renewed after an year
            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_year)
            mocked.assert_not_called()

    @mock_stripe()
    def test_downgrade_at_end_of_free_trial(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(user, schedule="annual")
            plan = get_current_plan_by_realm(user.realm)
            assert plan is not None
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(plan.licenses(), self.seat_count)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)

            # Schedule downgrade
            with self.assertLogs("corporate.stripe", "INFO") as m:
                with time_machine.travel(self.now, tick=False):
                    response = self.client_billing_patch(
                        "/billing/plan",
                        {"status": CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL},
                    )
                    stripe_customer_id = Customer.objects.get(realm=user.realm).id
                    new_plan = get_current_plan_by_realm(user.realm)
                    assert new_plan is not None
                    expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL}"
                    self.assertEqual(m.output[0], expected_log)
                    self.assert_json_success(response)
            plan.refresh_from_db()
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL)
            self.assertEqual(plan.licenses(), self.seat_count)
            self.assertEqual(plan.licenses_at_next_renewal(), None)

            with time_machine.travel(self.now, tick=False):
                mock_customer = Mock(email=user.delivery_email)
                mock_customer.invoice_settings.default_payment_method = Mock(
                    spec=stripe.PaymentMethod, type=Mock()
                )
                with patch("corporate.lib.stripe.stripe_get_customer", return_value=mock_customer):
                    response = self.client_get("/billing/")
                    self.assert_in_success_response(
                        [
                            "Your organization will be downgraded to <strong>Zulip Cloud Free</strong> at the end of the free trial",
                            "<strong>March 2, 2012</strong>",
                        ],
                        response,
                    )

            billing_session = RealmBillingSession(user=user, realm=user.realm)
            # Verify that we still write LicenseLedger rows during the remaining
            # part of the cycle
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
                billing_session.update_license_ledger_if_needed(self.now)
            self.assertEqual(
                LicenseLedger.objects.order_by("-id")
                .values_list("licenses", "licenses_at_next_renewal")
                .first(),
                (20, 20),
            )

            # Verify that we don't invoice them for the additional users during free trial.
            mocked = self.setup_mocked_stripe(invoice_plans_as_needed, self.next_month)
            mocked["InvoiceItem"].create.assert_not_called()
            mocked["Invoice"].finalize_invoice.assert_not_called()
            mocked["Invoice"].create.assert_not_called()

            # Check that we downgrade properly if the cycle is over
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=30):
                billing_session.update_license_ledger_if_needed(free_trial_end_date)
            plan = CustomerPlan.objects.first()
            assert plan is not None
            self.assertIsNone(plan.next_invoice_date)
            self.assertEqual(plan.status, CustomerPlan.ENDED)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_LIMITED)
            self.assertEqual(
                LicenseLedger.objects.order_by("-id")
                .values_list("licenses", "licenses_at_next_renewal")
                .first(),
                (20, 20),
            )

            # Verify that we don't write LicenseLedger rows once we've downgraded
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=40):
                billing_session.update_license_ledger_if_needed(self.next_year)
            self.assertEqual(
                LicenseLedger.objects.order_by("-id")
                .values_list("licenses", "licenses_at_next_renewal")
                .first(),
                (20, 20),
            )

            self.login_user(user)
            response = self.client_get("/billing/")
            self.assertEqual(response.status_code, 302)
            self.assertEqual("/plans/", response["Location"])

            # The extra users added in the final month are not charged
            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_month)
            mocked.assert_not_called()

            # The plan is not renewed after an year
            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_year)
            mocked.assert_not_called()

    @mock_stripe()
    def test_cancel_downgrade_at_end_of_free_trial(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(user, schedule="annual")
            plan = get_current_plan_by_realm(user.realm)
            assert plan is not None
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(plan.licenses(), self.seat_count)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)

            # Schedule downgrade
            with self.assertLogs("corporate.stripe", "INFO") as m:
                with time_machine.travel(self.now, tick=False):
                    response = self.client_billing_patch(
                        "/billing/plan",
                        {"status": CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL},
                    )
                    stripe_customer_id = Customer.objects.get(realm=user.realm).id
                    new_plan = get_current_plan_by_realm(user.realm)
                    assert new_plan is not None
                    expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL}"
                    self.assertEqual(m.output[0], expected_log)
                    self.assert_json_success(response)
            plan.refresh_from_db()
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL)
            self.assertEqual(plan.licenses(), self.seat_count)
            self.assertEqual(plan.licenses_at_next_renewal(), None)

            # Cancel downgrade
            with self.assertLogs("corporate.stripe", "INFO") as m:
                with time_machine.travel(self.now, tick=False):
                    response = self.client_billing_patch(
                        "/billing/plan",
                        {"status": CustomerPlan.FREE_TRIAL},
                    )
                    stripe_customer_id = Customer.objects.get(realm=user.realm).id
                    new_plan = get_current_plan_by_realm(user.realm)
                    assert new_plan is not None
                    expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.FREE_TRIAL}"
                    self.assertEqual(m.output[0], expected_log)
                    self.assert_json_success(response)
            plan.refresh_from_db()
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(plan.licenses(), self.seat_count)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)

    def test_reupgrade_by_billing_admin_after_downgrade(self) -> None:
        user = self.example_user("hamlet")

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        self.login_user(user)
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
                )
            stripe_customer_id = Customer.objects.get(realm=user.realm).id
            new_plan = get_current_plan_by_realm(user.realm)
            assert new_plan is not None
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {stripe_customer_id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)

        with self.assertRaises(BillingError) as context, self.assertLogs(
            "corporate.stripe", "WARNING"
        ) as m:
            with time_machine.travel(self.now, tick=False):
                self.local_upgrade(
                    self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
                )
        self.assertEqual(
            m.output[0],
            "WARNING:corporate.stripe:Upgrade of <Realm: zulip 2> (with stripe_customer_id: cus_123) failed because of existing active plan.",
        )
        self.assertEqual(
            context.exception.error_description, "subscribing with existing subscription"
        )

        # Fast forward the next_invoice_date to next year.
        new_plan.next_invoice_date = self.next_year
        new_plan.save(update_fields=["next_invoice_date"])
        invoice_plans_as_needed(self.next_year)

        with time_machine.travel(self.next_year, tick=False):
            response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/plans/", response["Location"])

        with time_machine.travel(self.next_year, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(CustomerPlan.objects.count(), 2)

        current_plan = CustomerPlan.objects.all().order_by("id").last()
        assert current_plan is not None
        next_invoice_date = add_months(self.next_year, 1)
        self.assertEqual(current_plan.next_invoice_date, next_invoice_date)
        self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
        self.assertEqual(current_plan.status, CustomerPlan.ACTIVE)

        old_plan = CustomerPlan.objects.all().order_by("id").first()
        assert old_plan is not None
        self.assertEqual(old_plan.next_invoice_date, None)
        self.assertEqual(old_plan.status, CustomerPlan.ENDED)

    @mock_stripe()
    def test_update_licenses_of_manual_plan_from_billing_page(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True, licenses=100)

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch("/billing/plan", {"licenses": 100})
            self.assert_json_error_contains(
                result, "Your plan is already on 100 licenses in the current billing period."
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": 100},
            )
            self.assert_json_error_contains(
                result, "Your plan is already scheduled to renew with 100 licenses."
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch("/billing/plan", {"licenses": 50})
            self.assert_json_error_contains(
                result, "You cannot decrease the licenses in the current billing period."
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": 25},
            )
            self.assert_json_error_contains(
                result,
                "You must purchase licenses for all active users in your organization (minimum 30).",
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch("/billing/plan", {"licenses": 2000})
            self.assert_json_error_contains(
                result, "Invoices with more than 1000 licenses can't be processed from this page."
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch("/billing/plan", {"licenses": 150})
            self.assert_json_success(result)
        invoice_plans_as_needed(self.next_year)
        stripe_customer = stripe_get_customer(
            assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
        )

        [renewal_invoice, additional_licenses_invoice, _old_renewal_invoice] = iter(
            stripe.Invoice.list(customer=stripe_customer.id)
        )

        invoice_params = {
            "amount_due": 8000 * 150,
            "amount_paid": 0,
            "attempt_count": 0,
            "auto_advance": True,
            "collection_method": "send_invoice",
            "statement_descriptor": "Zulip Cloud Standard",
            "status": "open",
            "total": 8000 * 150,
        }
        for key, value in invoice_params.items():
            self.assertEqual(renewal_invoice.get(key), value)
        [renewal_item] = iter(renewal_invoice.lines)

        line_item_params = {
            "amount": 8000 * 150,
            "description": "Zulip Cloud Standard - renewal",
            "discountable": False,
            "period": {
                "end": datetime_to_timestamp(self.next_year + timedelta(days=365)),
                "start": datetime_to_timestamp(self.next_year),
            },
            "plan": None,
            "proration": False,
            "quantity": 150,
        }
        for key, value in line_item_params.items():
            self.assertEqual(renewal_item.get(key), value)

        invoice_params = {
            "amount_due": 8000 * 50,
            "amount_paid": 0,
            "attempt_count": 0,
            "auto_advance": True,
            "collection_method": "send_invoice",
            "statement_descriptor": "Zulip Cloud Standard",
            "status": "open",
            "total": 8000 * 50,
        }
        for key, value in invoice_params.items():
            self.assertEqual(additional_licenses_invoice.get(key), value)
        [extra_license_item] = iter(additional_licenses_invoice.lines)

        line_item_params = {
            "amount": 8000 * 50,
            "description": "Additional license (Jan 2, 2012 - Jan 2, 2013)",
            "discountable": False,
            "period": {
                "end": datetime_to_timestamp(self.next_year),
                "start": datetime_to_timestamp(self.now),
            },
            "plan": None,
            "proration": False,
            "quantity": 50,
        }
        for key, value in line_item_params.items():
            self.assertEqual(extra_license_item.get(key), value)

        with time_machine.travel(self.next_year, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": 120},
            )
            self.assert_json_success(result)
        invoice_plans_as_needed(self.next_year + timedelta(days=365))
        [renewal_invoice, _, _, _] = iter(stripe.Invoice.list(customer=stripe_customer.id))

        invoice_params = {
            "amount_due": 8000 * 120,
            "amount_paid": 0,
            "attempt_count": 0,
            "auto_advance": True,
            "collection_method": "send_invoice",
            "statement_descriptor": "Zulip Cloud Standard",
            "status": "open",
            "total": 8000 * 120,
        }
        for key, value in invoice_params.items():
            self.assertEqual(renewal_invoice.get(key), value)
        [renewal_item] = iter(renewal_invoice.lines)

        line_item_params = {
            "amount": 8000 * 120,
            "description": "Zulip Cloud Standard - renewal",
            "discountable": False,
            "period": {
                "end": datetime_to_timestamp(self.next_year + timedelta(days=2 * 365)),
                "start": datetime_to_timestamp(self.next_year + timedelta(days=365)),
            },
            "plan": None,
            "proration": False,
            "quantity": 120,
        }
        for key, value in line_item_params.items():
            self.assertEqual(renewal_item.get(key), value)

    def test_update_licenses_of_manual_plan_from_billing_page_exempt_from_license_number_check(
        self,
    ) -> None:
        """
        Verifies that an organization exempt from the license number check can reduce their number
        of licenses.
        """
        user = self.example_user("hamlet")
        self.login_user(user)

        customer = Customer.objects.get_or_create(realm=user.realm)[0]
        customer.exempt_from_license_number_check = True
        customer.save()

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(100, False, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False)

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": get_latest_seat_count(user.realm) - 2},
            )

        self.assert_json_success(result)
        latest_license_ledger = LicenseLedger.objects.last()
        assert latest_license_ledger is not None
        self.assertEqual(
            latest_license_ledger.licenses_at_next_renewal, get_latest_seat_count(user.realm) - 2
        )

    def test_upgrade_exempt_from_license_number_check_realm_less_licenses_than_seat_count(
        self,
    ) -> None:
        """
        Verifies that an organization exempt from the license number check can upgrade their plan,
        specifying a number of licenses less than their current number of licenses and be charged
        for the number of licenses specified. Tests against a former bug, where the organization
        was charged for the current seat count, despite specifying a lower number of licenses.
        """
        user = self.example_user("hamlet")
        self.login_user(user)

        customer = Customer.objects.get_or_create(realm=user.realm)[0]
        customer.exempt_from_license_number_check = True
        customer.save()

        reduced_seat_count = get_latest_seat_count(user.realm) - 2

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                reduced_seat_count, False, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        latest_license_ledger = LicenseLedger.objects.last()
        assert latest_license_ledger is not None
        self.assertEqual(latest_license_ledger.licenses_at_next_renewal, reduced_seat_count)
        self.assertEqual(latest_license_ledger.licenses, reduced_seat_count)

    def test_update_licenses_of_automatic_plan_from_billing_page(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch("/billing/plan", {"licenses": 100})
            self.assert_json_error_contains(result, "Your plan is on automatic license management.")

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": 100},
            )
            self.assert_json_error_contains(result, "Your plan is on automatic license management.")

    def test_update_plan_with_invalid_status(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        self.login_user(self.example_user("hamlet"))

        response = self.client_billing_patch(
            "/billing/plan",
            {"status": CustomerPlan.NEVER_STARTED},
        )
        self.assert_json_error_contains(response, "Invalid status")

    def test_update_plan_without_any_params(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        self.login_user(self.example_user("hamlet"))
        with time_machine.travel(self.now, tick=False):
            response = self.client_billing_patch("/billing/plan", {})
        self.assert_json_error_contains(response, "Nothing to change")

    def test_update_plan_that_which_is_due_for_expiry(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        self.login_user(self.example_user("hamlet"))
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                result = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
                )
                self.assert_json_success(result)
                self.assertRegex(
                    m.output[0],
                    r"INFO:corporate.stripe:Change plan status: Customer.id: \d*, CustomerPlan.id: \d*, status: 2",
                )

        with time_machine.travel(self.next_year, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.ACTIVE},
            )
            self.assert_json_error_contains(
                result, "Unable to update the plan. The plan has ended."
            )

    def test_update_plan_that_which_is_due_for_replacement(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_MONTHLY, True, False
            )

        self.login_user(self.example_user("hamlet"))
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                result = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE},
                )
                self.assert_json_success(result)
                self.assertRegex(
                    m.output[0],
                    r"INFO:corporate.stripe:Change plan status: Customer.id: \d*, CustomerPlan.id: \d*, status: 4",
                )

        with time_machine.travel(self.next_month, tick=False):
            result = self.client_billing_patch("/billing/plan", {})
            self.assert_json_error_contains(
                result,
                "Unable to update the plan. The plan has been expired and replaced with a new plan.",
            )

    @patch("corporate.lib.stripe.billing_logger.info")
    def test_deactivate_realm(self, mock_: Mock) -> None:
        user = self.example_user("hamlet")
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        plan = CustomerPlan.objects.get()
        self.assertEqual(plan.next_invoice_date, self.next_month)
        self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
        self.assertEqual(plan.status, CustomerPlan.ACTIVE)

        # Add some extra users before the realm is deactivated
        billing_session = RealmBillingSession(user=user, realm=user.realm)
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
            billing_session.update_license_ledger_if_needed(self.now)

        last_ledger_entry = LicenseLedger.objects.order_by("id").last()
        assert last_ledger_entry is not None
        self.assertEqual(last_ledger_entry.licenses, 20)
        self.assertEqual(last_ledger_entry.licenses_at_next_renewal, 20)

        do_deactivate_realm(get_realm("zulip"), acting_user=None)

        plan.refresh_from_db()
        self.assertTrue(get_realm("zulip").deactivated)
        self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_LIMITED)
        self.assertEqual(plan.status, CustomerPlan.ENDED)
        self.assertEqual(plan.invoiced_through, last_ledger_entry)
        self.assertIsNone(plan.next_invoice_date)

        do_reactivate_realm(get_realm("zulip"))

        self.login_user(user)
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/plans/", response["Location"])

        # The extra users added in the final month are not charged
        with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
            invoice_plans_as_needed(self.next_month)
        mocked.assert_not_called()

        # The plan is not renewed after an year
        with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
            invoice_plans_as_needed(self.next_year)
        mocked.assert_not_called()

    def test_reupgrade_by_billing_admin_after_realm_deactivation(self) -> None:
        user = self.example_user("hamlet")

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        do_deactivate_realm(get_realm("zulip"), acting_user=None)
        self.assertTrue(get_realm("zulip").deactivated)
        do_reactivate_realm(get_realm("zulip"))

        self.login_user(user)
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/plans/", response["Location"])

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        self.assertEqual(Customer.objects.count(), 1)

        self.assertEqual(CustomerPlan.objects.count(), 2)

        current_plan = CustomerPlan.objects.all().order_by("id").last()
        assert current_plan is not None
        self.assertEqual(current_plan.next_invoice_date, self.next_month)
        self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
        self.assertEqual(current_plan.status, CustomerPlan.ACTIVE)

        old_plan = CustomerPlan.objects.all().order_by("id").first()
        assert old_plan is not None
        self.assertEqual(old_plan.next_invoice_date, None)
        self.assertEqual(old_plan.status, CustomerPlan.ENDED)

    @mock_stripe()
    def test_void_all_open_invoices(self, *mock: Mock) -> None:
        iago = self.example_user("iago")
        king = self.lear_user("king")

        voided_invoice_count = RealmBillingSession(
            user=None, realm=iago.realm
        ).void_all_open_invoices()
        self.assertEqual(voided_invoice_count, 0)

        zulip_customer = RealmBillingSession(iago).update_or_create_stripe_customer()
        lear_customer = RealmBillingSession(king).update_or_create_stripe_customer()

        assert zulip_customer.stripe_customer_id
        stripe.InvoiceItem.create(
            currency="usd",
            customer=zulip_customer.stripe_customer_id,
            description="Zulip Cloud Standard upgrade",
            discountable=False,
            unit_amount=800,
            quantity=8,
        )
        stripe_invoice = stripe.Invoice.create(
            auto_advance=True,
            collection_method="send_invoice",
            customer=zulip_customer.stripe_customer_id,
            days_until_due=30,
            statement_descriptor="Zulip Cloud Standard",
        )
        stripe.Invoice.finalize_invoice(stripe_invoice)

        assert lear_customer.stripe_customer_id
        stripe.InvoiceItem.create(
            currency="usd",
            customer=lear_customer.stripe_customer_id,
            description="Zulip Cloud Standard upgrade",
            discountable=False,
            unit_amount=800,
            quantity=8,
        )
        stripe_invoice = stripe.Invoice.create(
            auto_advance=True,
            collection_method="send_invoice",
            customer=lear_customer.stripe_customer_id,
            days_until_due=30,
            statement_descriptor="Zulip Cloud Standard",
        )
        stripe.Invoice.finalize_invoice(stripe_invoice)

        voided_invoice_count = RealmBillingSession(
            user=None, realm=iago.realm
        ).void_all_open_invoices()
        self.assertEqual(voided_invoice_count, 1)
        invoices = stripe.Invoice.list(customer=zulip_customer.stripe_customer_id)
        self.assert_length(invoices, 1)
        for invoice in invoices:
            self.assertEqual(invoice.status, "void")

        lear_stripe_customer_id = lear_customer.stripe_customer_id
        lear_customer.stripe_customer_id = None
        lear_customer.save(update_fields=["stripe_customer_id"])
        voided_invoice_count = RealmBillingSession(
            user=None, realm=king.realm
        ).void_all_open_invoices()
        self.assertEqual(voided_invoice_count, 0)

        lear_customer.stripe_customer_id = lear_stripe_customer_id
        lear_customer.save(update_fields=["stripe_customer_id"])
        voided_invoice_count = RealmBillingSession(
            user=None, realm=king.realm
        ).void_all_open_invoices()
        self.assertEqual(voided_invoice_count, 1)
        invoices = stripe.Invoice.list(customer=lear_customer.stripe_customer_id)
        self.assert_length(invoices, 1)
        for invoice in invoices:
            self.assertEqual(invoice.status, "void")

    def create_invoices(self, customer: Customer, num_invoices: int) -> List[stripe.Invoice]:
        invoices = []
        assert customer.stripe_customer_id is not None
        for _ in range(num_invoices):
            stripe.InvoiceItem.create(
                amount=10000,
                currency="usd",
                customer=customer.stripe_customer_id,
                description="Zulip Cloud Standard",
                discountable=False,
            )
            invoice = stripe.Invoice.create(
                auto_advance=True,
                collection_method="send_invoice",
                customer=customer.stripe_customer_id,
                days_until_due=DEFAULT_INVOICE_DAYS_UNTIL_DUE,
                statement_descriptor="Zulip Cloud Standard",
            )
            stripe.Invoice.finalize_invoice(invoice)
            invoices.append(invoice)
        return invoices

    @mock_stripe()
    def test_downgrade_small_realms_behind_on_payments_as_needed(self, *mock: Mock) -> None:
        test_realm_count = 0

        def create_realm(
            users_to_create: int,
            create_stripe_customer: bool,
            create_plan: bool,
            num_invoices: Optional[int] = None,
        ) -> Tuple[Realm, Optional[CustomerPlan], List[stripe.Invoice]]:
            nonlocal test_realm_count
            test_realm_count += 1
            realm_string_id = "test-realm-" + str(test_realm_count)
            realm = do_create_realm(
                string_id=realm_string_id,
                name=realm_string_id,
                plan_type=Realm.PLAN_TYPE_SELF_HOSTED,
            )
            users = []
            for i in range(users_to_create):
                user = UserProfile.objects.create(
                    delivery_email=f"user-{i}-{realm_string_id}@zulip.com",
                    email=f"user-{i}-{realm_string_id}@zulip.com",
                    realm=realm,
                )
                users.append(user)

            customer = None
            if create_stripe_customer:
                billing_session = RealmBillingSession(users[0])
                customer = billing_session.create_stripe_customer()
            plan = None
            if create_plan:
                plan, _ = self.subscribe_realm_to_monthly_plan_on_manual_license_management(
                    realm, users_to_create, users_to_create
                )
            invoices = []
            if num_invoices is not None:
                assert customer is not None
                invoices = self.create_invoices(customer, num_invoices)
            return realm, plan, invoices

        @dataclass
        class Row:
            realm: Realm
            expected_plan_type: int
            plan: Optional[CustomerPlan]
            expected_plan_status: Optional[int]
            expected_invoice_count: int
            email_expected_to_be_sent: bool

        rows: List[Row] = []

        # no stripe customer ID (excluded from query)
        realm, _, _ = create_realm(
            users_to_create=1, create_stripe_customer=False, create_plan=False
        )
        billing_session = RealmBillingSession(
            user=self.example_user("iago"), realm=realm, support_session=True
        )
        billing_session.set_required_plan_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        billing_session.attach_discount_to_customer(Decimal(20))
        rows.append(Row(realm, Realm.PLAN_TYPE_SELF_HOSTED, None, None, 0, False))

        # no active paid plan or invoices (no action)
        realm, _, _ = create_realm(
            users_to_create=1, create_stripe_customer=True, create_plan=False
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_SELF_HOSTED, None, None, 0, False))

        # no active plan, one unpaid invoice (will be voided, no downgrade or email)
        realm, _, _ = create_realm(
            users_to_create=1, create_stripe_customer=True, create_plan=False, num_invoices=1
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_SELF_HOSTED, None, None, 0, False))

        # active plan, no invoices (no action)
        realm, plan, _ = create_realm(
            users_to_create=1, create_stripe_customer=True, create_plan=True
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_STANDARD, plan, CustomerPlan.ACTIVE, 0, False))

        # active plan, only one unpaid invoice (not downgraded or voided)
        realm, plan, _ = create_realm(
            users_to_create=1, create_stripe_customer=True, create_plan=True, num_invoices=1
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_STANDARD, plan, CustomerPlan.ACTIVE, 1, False))

        # active plan, two unpaid invoices (will be downgraded, voided and emailed)
        realm, plan, _ = create_realm(
            users_to_create=3, create_stripe_customer=True, create_plan=True, num_invoices=2
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_LIMITED, plan, CustomerPlan.ENDED, 0, True))

        # active plan, two paid invoices (not downgraded)
        realm, plan, invoices = create_realm(
            users_to_create=1, create_stripe_customer=True, create_plan=True, num_invoices=2
        )
        for invoice in invoices:
            stripe.Invoice.pay(invoice, paid_out_of_band=True)
        rows.append(Row(realm, Realm.PLAN_TYPE_STANDARD, plan, CustomerPlan.ACTIVE, 0, False))

        # not a small realm, two unpaid invoices (not downgraded or voided)
        realm, plan, _ = create_realm(
            users_to_create=20, create_stripe_customer=True, create_plan=True, num_invoices=2
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_STANDARD, plan, CustomerPlan.ACTIVE, 2, False))

        # Customer objects without a realm should be excluded from query.
        remote_server = RemoteZulipServer.objects.create(
            uuid=str(uuid.uuid4()),
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        Customer.objects.create(remote_server=remote_server, stripe_customer_id="cus_xxx")

        downgrade_small_realms_behind_on_payments_as_needed()

        from django.core.mail import outbox

        for row in rows:
            row.realm.refresh_from_db()
            self.assertEqual(row.realm.plan_type, row.expected_plan_type)
            if row.plan is not None:
                row.plan.refresh_from_db()
                self.assertEqual(row.plan.status, row.expected_plan_status)
                customer = get_customer_by_realm(row.realm)
                if customer is not None and customer.stripe_customer_id is not None:
                    open_invoices = customer_has_last_n_invoices_open(
                        customer, row.expected_invoice_count
                    )
                    self.assertTrue(open_invoices)

            email_found = False
            for email in outbox:
                recipient = UserProfile.objects.get(email=email.to[0])
                if recipient.realm == row.realm:
                    self.assertIn(
                        f"Your organization, http://{row.realm.string_id}.testserver, has been downgraded",
                        outbox[0].body,
                    )
                    self.assert_length(email.to, 1)
                    self.assertTrue(recipient.is_billing_admin)
                    email_found = True
            self.assertEqual(row.email_expected_to_be_sent, email_found)

    @mock_stripe()
    def test_upgrade_pay_by_invoice(self, *mock: Mock) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        response = self.client_get("/upgrade/?setup_payment_by_invoice=true")
        self.assert_in_success_response(["pay by card", "Send invoice"], response)

        # Send invoice
        response = self.client_billing_post(
            "/billing/upgrade",
            {
                "billing_modality": "send_invoice",
                "schedule": "annual",
                "signed_seat_count": self.get_signed_seat_count_from_response(response),
                "salt": self.get_salt_from_response(response),
                "license_management": "manual",
                "licenses": 40,
            },
        )
        self.assert_json_success(response)

        response = self.client_get("/upgrade/?setup_payment_by_invoice=true")
        self.assert_in_success_response(["An invoice", "has been sent"], response)

    @mock_stripe()
    def test_change_plan_tier_from_standard_to_plus(self, *mock: Mock) -> None:
        iago = self.example_user("iago")
        realm = iago.realm
        iago_billing_session = RealmBillingSession(iago)
        iago_billing_session.update_or_create_customer()

        # Test upgrading to Plus when realm has no active subscription
        with self.assertRaises(BillingError) as billing_context:
            iago_billing_session.do_change_plan_to_new_tier(CustomerPlan.TIER_CLOUD_PLUS)
        self.assertEqual(
            "Organization does not have an active plan",
            billing_context.exception.error_description,
        )

        plan, ledger = self.subscribe_realm_to_manual_license_management_plan(
            realm, 9, 9, CustomerPlan.BILLING_SCHEDULE_MONTHLY
        )
        # Test upgrading to Plus when realm has no stripe_customer_id
        with self.assertRaises(BillingError) as billing_context:
            iago_billing_session.do_change_plan_to_new_tier(CustomerPlan.TIER_CLOUD_PLUS)
        self.assertEqual(
            "Organization missing Stripe customer.", billing_context.exception.error_description
        )

        king = self.lear_user("king")
        realm = king.realm
        king_billing_session = RealmBillingSession(king)
        customer = king_billing_session.update_or_create_stripe_customer()
        plan = CustomerPlan.objects.create(
            customer=customer,
            automanage_licenses=True,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        ledger = LicenseLedger.objects.create(
            plan=plan,
            is_renewal=True,
            event_time=timezone_now(),
            licenses=9,
            licenses_at_next_renewal=9,
        )
        realm.plan_type = Realm.PLAN_TYPE_STANDARD
        realm.save(update_fields=["plan_type"])
        plan.invoiced_through = ledger
        plan.price_per_license = get_price_per_license(
            CustomerPlan.TIER_CLOUD_STANDARD, CustomerPlan.BILLING_SCHEDULE_MONTHLY
        )
        plan.save(update_fields=["invoiced_through", "price_per_license"])

        with self.assertRaises(BillingError) as billing_context:
            king_billing_session.do_change_plan_to_new_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        self.assertEqual(
            "Invalid change of customer plan tier.", billing_context.exception.error_description
        )

        king_billing_session.do_change_plan_to_new_tier(CustomerPlan.TIER_CLOUD_PLUS)

        plan.refresh_from_db()
        self.assertEqual(plan.status, CustomerPlan.ENDED)
        plus_plan = get_current_plan_by_realm(realm)
        assert plus_plan is not None
        self.assertEqual(plus_plan.tier, CustomerPlan.TIER_CLOUD_PLUS)
        self.assertEqual(LicenseLedger.objects.filter(plan=plus_plan).count(), 1)

        realm.refresh_from_db()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_PLUS)

        # There are 9 licenses and the realm is on the Standard monthly plan.
        # Therefore, the customer has already paid 800 * 9 = 7200 = $72 for
        # the month. Once they upgrade to Plus, the new price for their 9
        # licenses will be 1200 * 9 = 10800 = $108. Since the customer has
        # already paid $72 for a month, -7200 = -$72 will be credited to the
        # customer's balance.
        stripe_customer_id = customer.stripe_customer_id
        assert stripe_customer_id is not None
        _, cb_txn = iter(stripe.Customer.list_balance_transactions(stripe_customer_id))
        self.assertEqual(cb_txn.amount, -7200)
        self.assertEqual(
            cb_txn.description,
            "Credit from early termination of active plan",
        )
        self.assertEqual(cb_txn.type, "adjustment")

        # The customer now only pays the difference 10800 - 7200 = 3600 = $36,
        # since the unused proration is for the whole month.
        (invoice,) = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual(invoice.amount_due, 3600)

    @mock_stripe()
    def test_customer_has_credit_card_as_default_payment_method(self, *mocks: Mock) -> None:
        iago = self.example_user("iago")
        customer = Customer.objects.create(realm=iago.realm)
        self.assertFalse(customer_has_credit_card_as_default_payment_method(customer))

        billing_session = RealmBillingSession(iago)
        customer = billing_session.update_or_create_stripe_customer()
        self.assertFalse(customer_has_credit_card_as_default_payment_method(customer))

        self.login_user(iago)
        self.add_card_and_upgrade(iago)
        self.assertTrue(customer_has_credit_card_as_default_payment_method(customer))


class StripeWebhookEndpointTest(ZulipTestCase):
    def test_stripe_webhook_with_invalid_data(self) -> None:
        result = self.client_post(
            "/stripe/webhook/",
            '["dsdsds"]',
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 400)

    def test_stripe_webhook_endpoint_invalid_api_version(self) -> None:
        event_data = {
            "id": "stripe_event_id",
            "api_version": "1991-02-20",
            "type": "event_type",
            "data": {"object": {"object": "checkout.session", "id": "stripe_session_id"}},
        }

        expected_error_message = rf"Mismatch between billing system Stripe API version({STRIPE_API_VERSION}) and Stripe webhook event API version(1991-02-20)."
        with self.assertLogs("corporate.stripe", "ERROR") as error_log:
            self.client_post(
                "/stripe/webhook/",
                event_data,
                content_type="application/json",
            )
            self.assertEqual(error_log.output, [f"ERROR:corporate.stripe:{expected_error_message}"])

    def test_stripe_webhook_for_session_completed_event(self) -> None:
        # We don't process sessions for which we don't have a `Session` entry.
        valid_session_event_data = {
            "id": "stripe_event_id",
            "api_version": STRIPE_API_VERSION,
            "type": "checkout.session.completed",
            "data": {"object": {"object": "checkout.session", "id": "stripe_session_id"}},
        }
        with patch("corporate.views.webhook.handle_checkout_session_completed_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_session_event_data,
                content_type="application/json",
            )
        self.assert_length(Event.objects.all(), 0)
        self.assertEqual(result.status_code, 200)
        m.assert_not_called()

    def test_stripe_webhook_for_invoice_payment_events(self) -> None:
        customer = Customer.objects.create(realm=get_realm("zulip"))

        stripe_event_id = "stripe_event_id"
        stripe_invoice_id = "stripe_invoice_id"
        valid_session_event_data = {
            "id": stripe_event_id,
            "type": "invoice.paid",
            "api_version": STRIPE_API_VERSION,
            "data": {"object": {"object": "invoice", "id": stripe_invoice_id}},
        }

        with patch("corporate.views.webhook.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_session_event_data,
                content_type="application/json",
            )
        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 0)
        self.assertEqual(result.status_code, 200)
        m.assert_not_called()

        Invoice.objects.create(
            stripe_invoice_id=stripe_invoice_id,
            customer=customer,
            status=Invoice.SENT,
        )

        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 0)
        with patch("corporate.views.webhook.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_session_event_data,
                content_type="application/json",
            )
        [event] = Event.objects.filter(stripe_event_id=stripe_event_id)
        self.assertEqual(result.status_code, 200)
        strip_event = stripe.Event.construct_from(valid_session_event_data, stripe.api_key)
        m.assert_called_once_with(strip_event.data.object, event)

        with patch("corporate.views.webhook.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_session_event_data,
                content_type="application/json",
            )
        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 1)
        self.assertEqual(result.status_code, 200)
        m.assert_not_called()

    def test_stripe_webhook_for_invoice_paid_events(self) -> None:
        customer = Customer.objects.create(realm=get_realm("zulip"))

        stripe_event_id = "stripe_event_id"
        stripe_invoice_id = "stripe_invoice_id"
        valid_invoice_paid_event_data = {
            "id": stripe_event_id,
            "type": "invoice.paid",
            "api_version": STRIPE_API_VERSION,
            "data": {"object": {"object": "invoice", "id": stripe_invoice_id}},
        }

        with patch("corporate.views.webhook.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_invoice_paid_event_data,
                content_type="application/json",
            )
        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 0)
        self.assertEqual(result.status_code, 200)
        m.assert_not_called()

        Invoice.objects.create(
            stripe_invoice_id=stripe_invoice_id,
            customer=customer,
            status=Invoice.SENT,
        )

        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 0)
        with patch("corporate.views.webhook.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_invoice_paid_event_data,
                content_type="application/json",
            )
        [event] = Event.objects.filter(stripe_event_id=stripe_event_id)
        self.assertEqual(result.status_code, 200)
        strip_event = stripe.Event.construct_from(valid_invoice_paid_event_data, stripe.api_key)
        m.assert_called_once_with(strip_event.data.object, event)

        with patch("corporate.views.webhook.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_invoice_paid_event_data,
                content_type="application/json",
            )
        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 1)
        self.assertEqual(result.status_code, 200)
        m.assert_not_called()


class EventStatusTest(StripeTestCase):
    def test_event_status_json_endpoint_errors(self) -> None:
        self.login_user(self.example_user("iago"))

        response = self.client_get("/json/billing/event/status")
        self.assert_json_error_contains(response, "No customer for this organization!")

        Customer.objects.create(realm=get_realm("zulip"), stripe_customer_id="cus_123")
        response = self.client_get(
            "/json/billing/event/status", {"stripe_session_id": "invalid_session_id"}
        )
        self.assert_json_error_contains(response, "Session not found")

        response = self.client_get(
            "/json/billing/event/status", {"stripe_invoice_id": "invalid_invoice_id"}
        )
        self.assert_json_error_contains(response, "Payment intent not found")

        response = self.client_get(
            "/json/billing/event/status",
        )
        self.assert_json_error_contains(response, "Pass stripe_session_id or stripe_invoice_id")

    def test_event_status_page(self) -> None:
        self.login_user(self.example_user("polonius"))

        stripe_session_id = "cs_test_9QCz62mPTJQUwvhcwZHBpJMHmMZiLU512AQHU9g5znkx6NweU3j7kJvY"
        response = self.client_get(
            "/billing/event_status/", {"stripe_session_id": stripe_session_id}
        )
        self.assert_in_success_response([f'data-stripe-session-id="{stripe_session_id}"'], response)

        stripe_invoice_id = "pi_1JGLpnA4KHR4JzRvUfkF9Tn7"
        response = self.client_get(
            "/billing/event_status/", {"stripe_invoice_id": stripe_invoice_id}
        )
        self.assert_in_success_response([f'data-stripe-invoice-id="{stripe_invoice_id}"'], response)


class RequiresBillingAccessTest(StripeTestCase):
    @override
    def setUp(self, *mocks: Mock) -> None:
        super().setUp()
        desdemona = self.example_user("desdemona")
        desdemona.role = UserProfile.ROLE_REALM_OWNER
        desdemona.save(update_fields=["role"])

    def test_json_endpoints_permissions(self) -> None:
        guest = self.example_user("polonius")
        member = self.example_user("othello")
        realm_admin = self.example_user("iago")

        billing_admin = self.example_user("hamlet")
        billing_admin.is_billing_admin = True
        billing_admin.save(update_fields=["is_billing_admin"])

        tested_endpoints = set()

        def check_users_cant_access(
            users: List[UserProfile],
            error_message: str,
            url: str,
            method: str,
            data: Dict[str, Any],
        ) -> None:
            tested_endpoints.add(url)
            for user in users:
                self.login_user(user)
                if method == "POST":
                    client_func: Any = self.client_post
                elif method == "GET":
                    client_func = self.client_get
                else:
                    client_func = self.client_patch
                result = client_func(
                    url,
                    data,
                    content_type="application/json",
                )
                self.assert_json_error_contains(result, error_message)

        check_users_cant_access(
            [guest],
            "Must be an organization member",
            "/json/billing/upgrade",
            "POST",
            {},
        )

        check_users_cant_access(
            [guest],
            "Must be an organization member",
            "/json/billing/sponsorship",
            "POST",
            {},
        )

        check_users_cant_access(
            [guest, member, realm_admin],
            "Must be a billing administrator or an organization owner",
            "/json/billing/plan",
            "PATCH",
            {},
        )

        check_users_cant_access(
            [guest, member, realm_admin],
            "Must be a billing administrator or an organization owner",
            "/json/billing/session/start_card_update_session",
            "POST",
            {},
        )

        check_users_cant_access(
            [guest],
            "Must be an organization member",
            "/json/upgrade/session/start_card_update_session",
            "POST",
            {},
        )

        check_users_cant_access(
            [guest],
            "Must be an organization member",
            "/json/billing/event/status",
            "GET",
            {},
        )

        # Make sure that we are testing all the JSON endpoints
        # Quite a hack, but probably fine for now
        reverse_dict = get_resolver("corporate.urls").reverse_dict
        json_endpoints = {
            pat
            for name in reverse_dict
            for matches, pat, defaults, converters in reverse_dict.getlist(name)
            if pat.startswith("json/") and not (pat.startswith(("json/realm/", "json/server/")))
        }
        self.assert_length(json_endpoints, len(tested_endpoints))

    @mock_stripe()
    def test_billing_page_permissions(self, *mocks: Mock) -> None:
        # Guest users can't access /upgrade/ page
        self.login_user(self.example_user("polonius"))
        response = self.client_get("/upgrade/", follow=True)
        self.assertEqual(response.status_code, 404)

        non_owner_non_billing_admin = self.example_user("othello")
        self.login_user(non_owner_non_billing_admin)
        response = self.client_get("/billing/")
        self.assert_in_success_response(
            ["You must be an organization owner or a billing administrator to view this page."],
            response,
        )
        # Check that non-admins can sign up and pay
        self.add_card_and_upgrade(non_owner_non_billing_admin)
        # Check that the non-admin othello can still access /billing
        response = self.client_get("/billing/")
        self.assert_in_success_response(["Zulip Cloud Standard"], response)
        self.assert_not_in_success_response(
            ["You must be an organization owner or a billing administrator to view this page."],
            response,
        )

        # Check realm owners can access billing, even though they are not a billing admin
        desdemona = self.example_user("desdemona")
        desdemona.role = UserProfile.ROLE_REALM_OWNER
        desdemona.save(update_fields=["role"])
        self.login_user(self.example_user("desdemona"))
        response = self.client_get("/billing/")
        self.assert_in_success_response(["Zulip Cloud Standard"], response)

        # Check that member who is not a billing admin does not have access
        self.login_user(self.example_user("cordelia"))
        response = self.client_get("/billing/")
        self.assert_in_success_response(
            ["You must be an organization owner or a billing administrator"], response
        )


class BillingHelpersTest(ZulipTestCase):
    def test_next_month(self) -> None:
        anchor = datetime(2019, 12, 31, 1, 2, 3, tzinfo=timezone.utc)
        period_boundaries = [
            anchor,
            datetime(2020, 1, 31, 1, 2, 3, tzinfo=timezone.utc),
            # Test that this is the 28th even during leap years
            datetime(2020, 2, 28, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 3, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 4, 30, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 5, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 6, 30, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 7, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 8, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 9, 30, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 10, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 11, 30, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 12, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2021, 1, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2021, 2, 28, 1, 2, 3, tzinfo=timezone.utc),
        ]
        with self.assertRaises(AssertionError):
            add_months(anchor, -1)
        # Explicitly test add_months for each value of MAX_DAY_FOR_MONTH and
        # for crossing a year boundary
        for i, boundary in enumerate(period_boundaries):
            self.assertEqual(add_months(anchor, i), boundary)
        # Test next_month for small values
        for last, next_ in itertools.pairwise(period_boundaries):
            self.assertEqual(next_month(anchor, last), next_)
        # Test next_month for large values
        period_boundaries = [dt.replace(year=dt.year + 100) for dt in period_boundaries]
        for last, next_ in itertools.pairwise(period_boundaries):
            self.assertEqual(next_month(anchor, last), next_)

    def test_compute_plan_parameters(self) -> None:
        # TODO: test rounding down microseconds
        anchor = datetime(2019, 12, 31, 1, 2, 3, tzinfo=timezone.utc)
        month_later = datetime(2020, 1, 31, 1, 2, 3, tzinfo=timezone.utc)
        year_later = datetime(2020, 12, 31, 1, 2, 3, tzinfo=timezone.utc)
        test_cases = [
            # test all possibilities, since there aren't that many
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    None,
                ),
                (anchor, month_later, year_later, 8000),
            ),
            (
                (CustomerPlan.TIER_CLOUD_STANDARD, CustomerPlan.BILLING_SCHEDULE_ANNUAL, 85),
                (anchor, month_later, year_later, 1200),
            ),
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    None,
                ),
                (anchor, month_later, month_later, 800),
            ),
            (
                (CustomerPlan.TIER_CLOUD_STANDARD, CustomerPlan.BILLING_SCHEDULE_MONTHLY, 85),
                (anchor, month_later, month_later, 120),
            ),
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    None,
                ),
                (anchor, month_later, year_later, 8000),
            ),
            (
                (CustomerPlan.TIER_CLOUD_STANDARD, CustomerPlan.BILLING_SCHEDULE_ANNUAL, 85),
                (anchor, month_later, year_later, 1200),
            ),
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    None,
                ),
                (anchor, month_later, month_later, 800),
            ),
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    85,
                ),
                (anchor, month_later, month_later, 120),
            ),
            # test exact math of Decimals; 800 * (1 - 87.25) = 101.9999999..
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    87.25,
                ),
                (anchor, month_later, month_later, 102),
            ),
            # test dropping of fractional cents; without the int it's 102.8
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    87.15,
                ),
                (anchor, month_later, month_later, 102),
            ),
        ]
        with time_machine.travel(anchor, tick=False):
            for (tier, billing_schedule, discount), output in test_cases:
                output_ = compute_plan_parameters(
                    tier,
                    billing_schedule,
                    None if discount is None else Decimal(discount),
                )
                self.assertEqual(output_, output)

    def test_get_price_per_license(self) -> None:
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_STANDARD, CustomerPlan.BILLING_SCHEDULE_ANNUAL
            ),
            8000,
        )
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_STANDARD, CustomerPlan.BILLING_SCHEDULE_MONTHLY
            ),
            800,
        )
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_STANDARD,
                CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                discount=Decimal(50),
            ),
            400,
        )

        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_PLUS, CustomerPlan.BILLING_SCHEDULE_ANNUAL
            ),
            12000,
        )
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_PLUS, CustomerPlan.BILLING_SCHEDULE_MONTHLY
            ),
            1200,
        )
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_PLUS,
                CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                discount=Decimal(50),
            ),
            600,
        )

        with self.assertRaisesRegex(InvalidBillingScheduleError, "Unknown billing_schedule: 1000"):
            get_price_per_license(CustomerPlan.TIER_CLOUD_STANDARD, 1000)

        with self.assertRaisesRegex(InvalidTierError, "Unknown tier: 4"):
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_ENTERPRISE, CustomerPlan.BILLING_SCHEDULE_ANNUAL
            )

    def test_get_plan_renewal_or_end_date(self) -> None:
        realm = get_realm("zulip")
        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")
        billing_cycle_anchor = timezone_now()
        plan = CustomerPlan.objects.create(
            customer=customer,
            status=CustomerPlan.ACTIVE,
            billing_cycle_anchor=billing_cycle_anchor,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        renewal_date = get_plan_renewal_or_end_date(plan, billing_cycle_anchor)
        self.assertEqual(renewal_date, add_months(billing_cycle_anchor, 1))

        # When the plan ends 2 days before the start of the next billing cycle,
        # the function should return the end_date.
        plan_end_date = add_months(billing_cycle_anchor, 1) - timedelta(days=2)
        plan.end_date = plan_end_date
        plan.save(update_fields=["end_date"])
        renewal_date = get_plan_renewal_or_end_date(plan, billing_cycle_anchor)
        self.assertEqual(renewal_date, plan_end_date)

    def test_update_or_create_stripe_customer_logic(self) -> None:
        user = self.example_user("hamlet")
        # No existing Customer object
        with patch(
            "corporate.lib.stripe.BillingSession.create_stripe_customer", return_value="returned"
        ) as mocked1:
            billing_session = RealmBillingSession(user)
            returned = billing_session.update_or_create_stripe_customer()
        mocked1.assert_called_once()
        self.assertEqual(returned, "returned")

        customer = Customer.objects.create(realm=get_realm("zulip"))
        # Customer exists but stripe_customer_id is None
        with patch(
            "corporate.lib.stripe.BillingSession.create_stripe_customer", return_value="returned"
        ) as mocked2:
            billing_session = RealmBillingSession(user)
            returned = billing_session.update_or_create_stripe_customer()
        mocked2.assert_called_once()
        self.assertEqual(returned, "returned")

        customer.stripe_customer_id = "cus_12345"
        customer.save()
        # Customer exists, replace payment source
        with patch("corporate.lib.stripe.BillingSession.replace_payment_method") as mocked3:
            billing_session = RealmBillingSession(user)
            returned_customer = billing_session.update_or_create_stripe_customer("pm_card_visa")
        mocked3.assert_called_once()
        self.assertEqual(returned_customer, customer)

        # Customer exists, do nothing
        with patch("corporate.lib.stripe.BillingSession.replace_payment_method") as mocked4:
            billing_session = RealmBillingSession(user)
            returned_customer = billing_session.update_or_create_stripe_customer(None)
        mocked4.assert_not_called()
        self.assertEqual(returned_customer, customer)

    def test_get_customer_by_realm(self) -> None:
        realm = get_realm("zulip")

        self.assertEqual(get_customer_by_realm(realm), None)

        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")
        self.assertEqual(get_customer_by_realm(realm), customer)

    def test_get_current_plan_by_customer(self) -> None:
        realm = get_realm("zulip")
        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")

        self.assertEqual(get_current_plan_by_customer(customer), None)

        plan = CustomerPlan.objects.create(
            customer=customer,
            status=CustomerPlan.ACTIVE,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        self.assertEqual(get_current_plan_by_customer(customer), plan)

        plan.status = CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
        plan.save(update_fields=["status"])
        self.assertEqual(get_current_plan_by_customer(customer), plan)

        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["status"])
        self.assertEqual(get_current_plan_by_customer(customer), None)

        plan.status = CustomerPlan.NEVER_STARTED
        plan.save(update_fields=["status"])
        self.assertEqual(get_current_plan_by_customer(customer), None)

    def test_get_current_plan_by_realm(self) -> None:
        realm = get_realm("zulip")

        self.assertEqual(get_current_plan_by_realm(realm), None)

        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")
        self.assertEqual(get_current_plan_by_realm(realm), None)

        plan = CustomerPlan.objects.create(
            customer=customer,
            status=CustomerPlan.ACTIVE,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        self.assertEqual(get_current_plan_by_realm(realm), plan)

    def test_is_realm_on_free_trial(self) -> None:
        realm = get_realm("zulip")
        self.assertFalse(is_realm_on_free_trial(realm))

        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")
        plan = CustomerPlan.objects.create(
            customer=customer,
            status=CustomerPlan.ACTIVE,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        self.assertFalse(is_realm_on_free_trial(realm))

        plan.status = CustomerPlan.FREE_TRIAL
        plan.save(update_fields=["status"])
        self.assertTrue(is_realm_on_free_trial(realm))

    def test_deactivate_reactivate_remote_server(self) -> None:
        server_uuid = str(uuid.uuid4())
        remote_server = RemoteZulipServer.objects.create(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        self.assertFalse(remote_server.deactivated)

        billing_session = RemoteServerBillingSession(remote_server)
        do_deactivate_remote_server(remote_server, billing_session)

        remote_server = RemoteZulipServer.objects.get(uuid=server_uuid)
        remote_realm_audit_log = RemoteZulipServerAuditLog.objects.filter(
            event_type=RealmAuditLog.REMOTE_SERVER_DEACTIVATED
        ).last()
        assert remote_realm_audit_log is not None
        self.assertTrue(remote_server.deactivated)

        # Try to deactivate a remote server that is already deactivated
        with self.assertLogs("corporate.stripe", "WARN") as warning_log:
            do_deactivate_remote_server(remote_server, billing_session)
            self.assertEqual(
                warning_log.output,
                [
                    "WARNING:corporate.stripe:Cannot deactivate remote server with ID "
                    f"{remote_server.id}, server has already been deactivated."
                ],
            )

        do_reactivate_remote_server(remote_server)
        remote_server.refresh_from_db()
        self.assertFalse(remote_server.deactivated)
        remote_realm_audit_log = RemoteZulipServerAuditLog.objects.latest("id")
        self.assertEqual(remote_realm_audit_log.event_type, RealmAuditLog.REMOTE_SERVER_REACTIVATED)
        self.assertEqual(remote_realm_audit_log.server, remote_server)

        with self.assertLogs("corporate.stripe", "WARN") as warning_log:
            do_reactivate_remote_server(remote_server)
            self.assertEqual(
                warning_log.output,
                [
                    "WARNING:corporate.stripe:Cannot reactivate remote server with ID "
                    f"{remote_server.id}, server is already active."
                ],
            )


class AnalyticsHelpersTest(ZulipTestCase):
    def test_get_realms_to_default_discount_dict(self) -> None:
        Customer.objects.create(realm=get_realm("zulip"), stripe_customer_id="cus_1")
        lear_customer = Customer.objects.create(realm=get_realm("lear"), stripe_customer_id="cus_2")
        lear_customer.default_discount = Decimal(30)
        lear_customer.save(update_fields=["default_discount"])
        zephyr_customer = Customer.objects.create(
            realm=get_realm("zephyr"), stripe_customer_id="cus_3"
        )
        zephyr_customer.default_discount = Decimal(0)
        zephyr_customer.save(update_fields=["default_discount"])
        remote_server = RemoteZulipServer.objects.create(
            uuid=str(uuid.uuid4()),
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        remote_customer = Customer.objects.create(
            remote_server=remote_server, stripe_customer_id="cus_4"
        )
        remote_customer.default_discount = Decimal(50)
        remote_customer.save(update_fields=["default_discount"])

        self.assertEqual(
            get_realms_with_default_discount_dict(),
            {
                "lear": Decimal("30.0000"),
            },
        )


class LicenseLedgerTest(StripeTestCase):
    def test_add_plan_renewal_if_needed(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        self.assertEqual(LicenseLedger.objects.count(), 1)
        plan = CustomerPlan.objects.get()
        # Plan hasn't renewed yet
        realm = plan.customer.realm
        billing_session = RealmBillingSession(user=None, realm=realm)
        billing_session.make_end_of_cycle_updates_if_needed(
            plan, self.next_year - timedelta(days=1)
        )
        self.assertEqual(LicenseLedger.objects.count(), 1)
        # Plan needs to renew
        # TODO: do_deactivate_user for a user, so that licenses_at_next_renewal != licenses
        new_plan, ledger_entry = billing_session.make_end_of_cycle_updates_if_needed(
            plan, self.next_year
        )
        self.assertIsNone(new_plan)
        self.assertEqual(LicenseLedger.objects.count(), 2)
        ledger_params = {
            "plan": plan,
            "is_renewal": True,
            "event_time": self.next_year,
            "licenses": self.seat_count,
            "licenses_at_next_renewal": self.seat_count,
        }
        for key, value in ledger_params.items():
            self.assertEqual(getattr(ledger_entry, key), value)
        # Plan needs to renew, but we already added the plan_renewal ledger entry
        billing_session.make_end_of_cycle_updates_if_needed(
            plan, self.next_year + timedelta(days=1)
        )
        self.assertEqual(LicenseLedger.objects.count(), 2)

    def test_update_license_ledger_if_needed(self) -> None:
        realm = get_realm("zulip")
        billing_session = RealmBillingSession(user=None, realm=realm)
        # Test no Customer
        billing_session.update_license_ledger_if_needed(self.now)
        self.assertFalse(LicenseLedger.objects.exists())
        # Test plan not automanaged
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count + 1, False, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        plan = CustomerPlan.objects.get()
        self.assertEqual(LicenseLedger.objects.count(), 1)
        self.assertEqual(plan.licenses(), self.seat_count + 1)
        self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count + 1)
        billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(LicenseLedger.objects.count(), 1)
        # Test no active plan
        plan.automanage_licenses = True
        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["automanage_licenses", "status"])
        billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(LicenseLedger.objects.count(), 1)
        # Test update needed
        plan.status = CustomerPlan.ACTIVE
        plan.save(update_fields=["status"])
        billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(LicenseLedger.objects.count(), 2)

    def test_update_license_ledger_for_automanaged_plan(self) -> None:
        realm = get_realm("zulip")
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.licenses(), self.seat_count)
        self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)

        billing_session = RealmBillingSession(user=None, realm=realm)
        # Simple increase
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=23):
            billing_session.update_license_ledger_for_automanaged_plan(plan, self.now)
            self.assertEqual(plan.licenses(), 23)
            self.assertEqual(plan.licenses_at_next_renewal(), 23)
        # Decrease
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
            billing_session.update_license_ledger_for_automanaged_plan(plan, self.now)
            self.assertEqual(plan.licenses(), 23)
            self.assertEqual(plan.licenses_at_next_renewal(), 20)
        # Increase, but not past high watermark
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=21):
            billing_session.update_license_ledger_for_automanaged_plan(plan, self.now)
            self.assertEqual(plan.licenses(), 23)
            self.assertEqual(plan.licenses_at_next_renewal(), 21)
        # Increase, but after renewal date, and below last year's high watermark
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=22):
            billing_session.update_license_ledger_for_automanaged_plan(
                plan, self.next_year + timedelta(seconds=1)
            )
            self.assertEqual(plan.licenses(), 22)
            self.assertEqual(plan.licenses_at_next_renewal(), 22)

        ledger_entries = list(
            LicenseLedger.objects.values_list(
                "is_renewal", "event_time", "licenses", "licenses_at_next_renewal"
            ).order_by("id")
        )
        self.assertEqual(
            ledger_entries,
            [
                (True, self.now, self.seat_count, self.seat_count),
                (False, self.now, 23, 23),
                (False, self.now, 23, 20),
                (False, self.now, 23, 21),
                (True, self.next_year, 21, 21),
                (False, self.next_year + timedelta(seconds=1), 22, 22),
            ],
        )

    def test_update_license_ledger_for_manual_plan(self) -> None:
        realm = get_realm("zulip")

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count + 1, False, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        billing_session = RealmBillingSession(user=None, realm=realm)
        plan = get_current_plan_by_realm(realm)
        assert plan is not None

        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count):
            billing_session.update_license_ledger_for_manual_plan(
                plan, self.now, licenses=self.seat_count + 3
            )
            self.assertEqual(plan.licenses(), self.seat_count + 3)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count + 3)

        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count):
            with self.assertRaises(AssertionError):
                billing_session.update_license_ledger_for_manual_plan(
                    plan, self.now, licenses=self.seat_count
                )

        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count):
            billing_session.update_license_ledger_for_manual_plan(
                plan, self.now, licenses_at_next_renewal=self.seat_count
            )
            self.assertEqual(plan.licenses(), self.seat_count + 3)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)

        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count):
            with self.assertRaises(AssertionError):
                billing_session.update_license_ledger_for_manual_plan(
                    plan, self.now, licenses_at_next_renewal=self.seat_count - 1
                )

        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count):
            billing_session.update_license_ledger_for_manual_plan(
                plan, self.now, licenses=self.seat_count + 10
            )
            self.assertEqual(plan.licenses(), self.seat_count + 10)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count + 10)

        billing_session.make_end_of_cycle_updates_if_needed(plan, self.next_year)
        self.assertEqual(plan.licenses(), self.seat_count + 10)

        ledger_entries = list(
            LicenseLedger.objects.values_list(
                "is_renewal", "event_time", "licenses", "licenses_at_next_renewal"
            ).order_by("id")
        )

        self.assertEqual(
            ledger_entries,
            [
                (True, self.now, self.seat_count + 1, self.seat_count + 1),
                (False, self.now, self.seat_count + 3, self.seat_count + 3),
                (False, self.now, self.seat_count + 3, self.seat_count),
                (False, self.now, self.seat_count + 10, self.seat_count + 10),
                (True, self.next_year, self.seat_count + 10, self.seat_count + 10),
            ],
        )

        with self.assertRaises(AssertionError):
            billing_session.update_license_ledger_for_manual_plan(plan, self.now)

    def test_user_changes(self) -> None:
        self.local_upgrade(self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False)
        user = do_create_user("email", "password", get_realm("zulip"), "name", acting_user=None)
        do_deactivate_user(user, acting_user=None)
        do_reactivate_user(user, acting_user=None)
        # Not a proper use of do_activate_mirror_dummy_user, but fine for this test
        do_activate_mirror_dummy_user(user, acting_user=None)
        ledger_entries = list(
            LicenseLedger.objects.values_list(
                "is_renewal", "licenses", "licenses_at_next_renewal"
            ).order_by("id")
        )
        self.assertEqual(
            ledger_entries,
            [
                (True, self.seat_count, self.seat_count),
                (False, self.seat_count + 1, self.seat_count + 1),
                (False, self.seat_count + 1, self.seat_count),
                (False, self.seat_count + 1, self.seat_count + 1),
                (False, self.seat_count + 1, self.seat_count + 1),
            ],
        )


class InvoiceTest(StripeTestCase):
    def test_invoicing_status_is_started(self) -> None:
        # local_upgrade uses hamlet as user, therefore realm is zulip.
        self.local_upgrade(self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        plan.invoicing_status = CustomerPlan.INVOICING_STATUS_STARTED
        plan.save(update_fields=["invoicing_status"])
        with self.assertRaises(NotImplementedError):
            billing_session = RealmBillingSession(realm=get_realm("zulip"))
            billing_session.invoice_plan(assert_is_not_none(CustomerPlan.objects.first()), self.now)

    def test_invoice_plan_without_stripe_customer(self) -> None:
        # local_upgrade uses hamlet as user, therefore realm is zulip.
        realm = get_realm("zulip")
        self.local_upgrade(
            self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, False, False
        )
        plan = get_current_plan_by_realm(realm)
        assert plan is not None
        plan.customer.stripe_customer_id = None
        plan.customer.save(update_fields=["stripe_customer_id"])
        with self.assertRaises(BillingError) as context:
            billing_session = RealmBillingSession(realm=realm)
            billing_session.invoice_plan(plan, timezone_now())
        self.assertRegex(
            context.exception.error_description,
            "Customer has a paid plan without a Stripe customer ID:",
        )

    @mock_stripe()
    def test_invoice_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(user)
        realm = get_realm("zulip")
        billing_session = RealmBillingSession(user=user, realm=realm)
        # Increase
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count + 3):
            billing_session.update_license_ledger_if_needed(self.now + timedelta(days=100))
        # Decrease
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count):
            billing_session.update_license_ledger_if_needed(self.now + timedelta(days=200))
        # Increase, but not past high watermark
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count + 1):
            billing_session.update_license_ledger_if_needed(self.now + timedelta(days=300))
        # Increase, but after renewal date, and below last year's high watermark
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count + 2):
            billing_session.update_license_ledger_if_needed(self.now + timedelta(days=400))
        # Increase, but after event_time
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count + 3):
            billing_session.update_license_ledger_if_needed(self.now + timedelta(days=500))
        plan = CustomerPlan.objects.first()
        assert plan is not None
        billing_session.invoice_plan(plan, self.now + timedelta(days=400))
        stripe_customer_id = plan.customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice0, invoice1] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertIsNotNone(invoice0.status_transitions.finalized_at)
        [item0, item1, item2] = iter(invoice0.lines)
        line_item_params = {
            "amount": int(8000 * (1 - ((400 - 366) / 365)) + 0.5),
            "description": "Additional license (Feb 5, 2013 - Jan 2, 2014)",
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.now + timedelta(days=400)),
                "end": datetime_to_timestamp(self.now + timedelta(days=2 * 365 + 1)),
            },
            "quantity": 1,
        }
        for key, value in line_item_params.items():
            self.assertEqual(item0.get(key), value)
        line_item_params = {
            "amount": 8000 * (self.seat_count + 1),
            "description": "Zulip Cloud Standard - renewal",
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.now + timedelta(days=366)),
                "end": datetime_to_timestamp(self.now + timedelta(days=2 * 365 + 1)),
            },
            "quantity": self.seat_count + 1,
        }
        for key, value in line_item_params.items():
            self.assertEqual(item1.get(key), value)
        line_item_params = {
            "amount": 3 * int(8000 * (366 - 100) / 366 + 0.5),
            "description": "Additional license (Apr 11, 2012 - Jan 2, 2013)",
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.now + timedelta(days=100)),
                "end": datetime_to_timestamp(self.now + timedelta(days=366)),
            },
            "quantity": 3,
        }
        for key, value in line_item_params.items():
            self.assertEqual(item2.get(key), value)

    @mock_stripe()
    def test_fixed_price_plans(self, *mocks: Mock) -> None:
        # Also tests charge_automatically=False
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        plan.fixed_price = 100
        plan.price_per_license = 0
        plan.save(update_fields=["fixed_price", "price_per_license"])
        user.realm.refresh_from_db()
        billing_session = RealmBillingSession(realm=user.realm)
        billing_session.invoice_plan(plan, self.next_year)
        stripe_customer_id = plan.customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice0, invoice1] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual(invoice0.collection_method, "send_invoice")
        [item] = iter(invoice0.lines)
        line_item_params = {
            "amount": 100,
            "description": "Zulip Cloud Standard - renewal",
            "discountable": False,
            "period": {
                "start": datetime_to_timestamp(self.next_year),
                "end": datetime_to_timestamp(self.next_year + timedelta(days=365)),
            },
            "quantity": 1,
        }
        for key, value in line_item_params.items():
            self.assertEqual(item.get(key), value)

    def test_no_invoice_needed(self) -> None:
        # local_upgrade uses hamlet as user, therefore realm is zulip.
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.next_invoice_date, self.next_month)
        # Test this doesn't make any calls to stripe.Invoice or stripe.InvoiceItem
        assert plan.customer.realm is not None
        billing_session = RealmBillingSession(realm=plan.customer.realm)
        billing_session.invoice_plan(plan, self.next_month)
        plan = CustomerPlan.objects.first()
        # Test that we still update next_invoice_date
        assert plan is not None
        self.assertEqual(plan.next_invoice_date, self.next_month + timedelta(days=29))

    def test_invoice_plans_as_needed(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.next_invoice_date, self.next_month)
        # Test nothing needed to be done
        with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
            invoice_plans_as_needed(self.next_month - timedelta(days=1))
        mocked.assert_not_called()
        # Test something needing to be done
        invoice_plans_as_needed(self.next_month)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.next_invoice_date, self.next_month + timedelta(days=29))


class TestTestClasses(ZulipTestCase):
    def test_subscribe_realm_to_manual_license_management_plan(self) -> None:
        realm = get_realm("zulip")
        plan, ledger = self.subscribe_realm_to_manual_license_management_plan(
            realm, 50, 60, CustomerPlan.BILLING_SCHEDULE_ANNUAL
        )

        plan.refresh_from_db()
        self.assertEqual(plan.automanage_licenses, False)
        self.assertEqual(plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_ANNUAL)
        self.assertEqual(plan.tier, CustomerPlan.TIER_CLOUD_STANDARD)
        self.assertEqual(plan.licenses(), 50)
        self.assertEqual(plan.licenses_at_next_renewal(), 60)

        ledger.refresh_from_db()
        self.assertEqual(ledger.plan, plan)
        self.assertEqual(ledger.licenses, 50)
        self.assertEqual(ledger.licenses_at_next_renewal, 60)

        realm.refresh_from_db()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)

    def test_subscribe_realm_to_monthly_plan_on_manual_license_management(self) -> None:
        realm = get_realm("zulip")
        plan, ledger = self.subscribe_realm_to_monthly_plan_on_manual_license_management(
            realm, 20, 30
        )

        plan.refresh_from_db()
        self.assertEqual(plan.automanage_licenses, False)
        self.assertEqual(plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_MONTHLY)
        self.assertEqual(plan.tier, CustomerPlan.TIER_CLOUD_STANDARD)
        self.assertEqual(plan.licenses(), 20)
        self.assertEqual(plan.licenses_at_next_renewal(), 30)

        ledger.refresh_from_db()
        self.assertEqual(ledger.plan, plan)
        self.assertEqual(ledger.licenses, 20)
        self.assertEqual(ledger.licenses_at_next_renewal, 30)

        realm.refresh_from_db()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)


class TestRealmBillingSession(StripeTestCase):
    def test_get_audit_log_error(self) -> None:
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(user)
        fake_audit_log = typing.cast(AuditLogEventType, 0)
        with self.assertRaisesRegex(
            BillingSessionAuditLogEventError, "Unknown audit log event type: 0"
        ):
            billing_session.get_audit_log_event(event_type=fake_audit_log)

    def test_get_customer(self) -> None:
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(user)
        customer = billing_session.get_customer()
        self.assertEqual(customer, None)

        customer = Customer.objects.create(realm=user.realm, stripe_customer_id="cus_12345")
        self.assertEqual(billing_session.get_customer(), customer)


class TestRemoteRealmBillingSession(StripeTestCase):
    def test_current_count_for_billed_licenses(self) -> None:
        server_uuid = str(uuid.uuid4())
        remote_server = RemoteZulipServer.objects.create(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        realm_uuid = str(uuid.uuid4())
        remote_realm = RemoteRealm.objects.create(
            server=remote_server,
            uuid=realm_uuid,
            uuid_owner_secret="dummy-owner-secret",
            host="dummy-hostname",
            realm_date_created=timezone_now(),
        )
        billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)

        # remote server never uploaded statistics. 'last_audit_log_update' is None.
        with self.assertRaises(MissingDataError):
            billing_session.current_count_for_billed_licenses()

        # Available statistics is stale.
        remote_server.last_audit_log_update = timezone_now() - timedelta(days=5)
        remote_server.save()
        with self.assertRaises(MissingDataError):
            billing_session.current_count_for_billed_licenses()

        # Available statistics is not stale.
        event_time = timezone_now() - timedelta(days=1)
        data_list = [
            {
                "server": remote_server,
                "remote_realm": remote_realm,
                "event_type": RemoteRealmAuditLog.USER_CREATED,
                "event_time": event_time,
                "extra_data": {
                    RemoteRealmAuditLog.ROLE_COUNT: {
                        RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                            UserProfile.ROLE_REALM_ADMINISTRATOR: 10,
                            UserProfile.ROLE_REALM_OWNER: 10,
                            UserProfile.ROLE_MODERATOR: 10,
                            UserProfile.ROLE_MEMBER: 10,
                            UserProfile.ROLE_GUEST: 10,
                        }
                    }
                },
            },
            {
                "server": remote_server,
                "remote_realm": remote_realm,
                "event_type": RemoteRealmAuditLog.USER_ROLE_CHANGED,
                "event_time": event_time,
                "extra_data": {
                    RemoteRealmAuditLog.ROLE_COUNT: {
                        RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                            UserProfile.ROLE_REALM_ADMINISTRATOR: 20,
                            UserProfile.ROLE_REALM_OWNER: 10,
                            UserProfile.ROLE_MODERATOR: 0,
                            UserProfile.ROLE_MEMBER: 30,
                            UserProfile.ROLE_GUEST: 10,
                        }
                    }
                },
            },
        ]
        RemoteRealmAuditLog.objects.bulk_create([RemoteRealmAuditLog(**data) for data in data_list])
        remote_server.last_audit_log_update = timezone_now() - timedelta(days=1)
        remote_server.save()

        self.assertEqual(billing_session.current_count_for_billed_licenses(), 70)


class TestRemoteServerBillingSession(StripeTestCase):
    def test_get_audit_log_error(self) -> None:
        server_uuid = str(uuid.uuid4())
        remote_server = RemoteZulipServer.objects.create(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        billing_session = RemoteServerBillingSession(remote_server)
        fake_audit_log = typing.cast(AuditLogEventType, 0)
        with self.assertRaisesRegex(
            BillingSessionAuditLogEventError, "Unknown audit log event type: 0"
        ):
            billing_session.get_audit_log_event(event_type=fake_audit_log)

    def test_get_customer(self) -> None:
        server_uuid = str(uuid.uuid4())
        remote_server = RemoteZulipServer.objects.create(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        billing_session = RemoteServerBillingSession(remote_server)
        customer = billing_session.get_customer()
        self.assertEqual(customer, None)

        customer = Customer.objects.create(
            remote_server=remote_server, stripe_customer_id="cus_12345"
        )
        self.assertEqual(billing_session.get_customer(), customer)

    # @mock_stripe
    # def test_update_or_create_stripe_customer(self) -> None:
    #     server_uuid = str(uuid.uuid4())
    #     remote_server = RemoteZulipServer.objects.create(
    #         uuid=server_uuid,
    #         api_key="magic_secret_api_key",
    #         hostname="demo.example.com",
    #         contact_email="email@example.com",
    #     )
    #     billing_session = RemoteServerBillingSession(remote_server)
    #     # We need to generate stripe fixture for this type of test.
    #     customer = billing_session.update_or_create_stripe_customer()
    #     assert customer.stripe_customer_id
    #     # Confirm audit log, etc.


class TestSupportBillingHelpers(StripeTestCase):
    @mock_stripe()
    def test_attach_discount_to_realm(self, *mocks: Mock) -> None:
        # Attach discount before Stripe customer exists
        support_admin = self.example_user("iago")
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(support_admin, realm=user.realm, support_session=True)

        # Cannot attach discount without a required_plan_tier set.
        with self.assertRaises(AssertionError):
            billing_session.attach_discount_to_customer(Decimal(85))
        billing_session.update_or_create_customer()

        with self.assertRaises(AssertionError):
            billing_session.attach_discount_to_customer(Decimal(85))

        billing_session.set_required_plan_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        billing_session.attach_discount_to_customer(Decimal(85))
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_DISCOUNT_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {"old_discount": None, "new_discount": str(Decimal("85"))}
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)
        self.login_user(user)
        # Check that the discount appears in page_params
        self.assert_in_success_response(["85"], self.client_get("/upgrade/"))
        # Check that the customer was charged the discounted amount
        self.add_card_and_upgrade(user)
        customer = Customer.objects.first()
        assert customer is not None
        assert customer.stripe_customer_id is not None
        [charge] = iter(stripe.Charge.list(customer=customer.stripe_customer_id))
        self.assertEqual(1200 * self.seat_count, charge.amount)
        stripe_customer_id = customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual(
            [1200 * self.seat_count],
            [item.amount for item in invoice.lines],
        )
        # Check CustomerPlan reflects the discount
        plan = CustomerPlan.objects.get(price_per_license=1200, discount=Decimal(85))

        # Attach discount to existing Stripe customer
        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["status"])
        billing_session = RealmBillingSession(support_admin, realm=user.realm, support_session=True)
        billing_session.set_required_plan_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        billing_session.attach_discount_to_customer(Decimal(25))
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(
                user, license_management="automatic", billing_modality="charge_automatically"
            )
        [charge, _] = iter(stripe.Charge.list(customer=customer.stripe_customer_id))
        self.assertEqual(6000 * self.seat_count, charge.amount)
        stripe_customer_id = customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice, _] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual(
            [6000 * self.seat_count],
            [item.amount for item in invoice.lines],
        )
        plan = CustomerPlan.objects.get(price_per_license=6000, discount=Decimal(25))

        billing_session = RealmBillingSession(support_admin, realm=user.realm, support_session=True)
        billing_session.attach_discount_to_customer(Decimal(50))
        plan.refresh_from_db()
        self.assertEqual(plan.price_per_license, 4000)
        self.assertEqual(plan.discount, 50)
        customer.refresh_from_db()
        self.assertEqual(customer.default_discount, 50)
        # Fast forward the next_invoice_date to next year.
        plan.next_invoice_date = self.next_year
        plan.save(update_fields=["next_invoice_date"])
        invoice_plans_as_needed(self.next_year + timedelta(days=10))
        stripe_customer_id = customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice, _, _] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual([4000 * self.seat_count], [item.amount for item in invoice.lines])
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_DISCOUNT_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            "old_discount": str(Decimal("25.0000")),
            "new_discount": str(Decimal("50")),
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)
        self.assertEqual(realm_audit_log.acting_user, support_admin)

        # Confirm that once a plan has been purchased and is active,
        # approving a full sponsorship (our version of 100% discount) fails.
        with self.assertRaisesRegex(
            SupportRequestError,
            "Customer on plan Zulip Cloud Standard. Please end current plan before approving sponsorship!",
        ):
            billing_session.approve_sponsorship()

    @mock_stripe()
    def test_add_minimum_licenses(self, *mocks: Mock) -> None:
        min_licenses = 25
        support_view_request = SupportViewRequest(
            support_type=SupportType.update_minimum_licenses, minimum_licenses=min_licenses
        )
        support_admin = self.example_user("iago")
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(support_admin, realm=user.realm, support_session=True)

        billing_session.update_or_create_customer()
        with self.assertRaisesRegex(
            SupportRequestError,
            "Discount for zulip must be updated before setting a minimum number of licenses.",
        ):
            billing_session.process_support_view_request(support_view_request)

        billing_session.set_required_plan_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        billing_session.attach_discount_to_customer(Decimal(50))
        message = billing_session.process_support_view_request(support_view_request)
        self.assertEqual("Minimum licenses for zulip changed to 25 from 0.", message)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.CUSTOMER_PROPERTY_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {"old_value": None, "new_value": 25, "property": "minimum_licenses"}
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        self.login_user(user)
        self.add_card_and_upgrade(user)
        customer = billing_session.get_customer()
        assert customer is not None
        assert customer.stripe_customer_id is not None
        [charge] = iter(stripe.Charge.list(customer=customer.stripe_customer_id))
        self.assertEqual(4000 * min_licenses, charge.amount)

        min_licenses = 50
        support_view_request = SupportViewRequest(
            support_type=SupportType.update_minimum_licenses, minimum_licenses=min_licenses
        )
        with self.assertRaisesRegex(
            SupportRequestError,
            "Cannot set minimum licenses; active plan already exists for zulip.",
        ):
            billing_session.process_support_view_request(support_view_request)

    def test_set_required_plan_tier(self) -> None:
        valid_plan_tier = CustomerPlan.TIER_CLOUD_STANDARD
        support_view_request = SupportViewRequest(
            support_type=SupportType.update_required_plan_tier,
            required_plan_tier=valid_plan_tier,
        )
        support_admin = self.example_user("iago")
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(support_admin, realm=user.realm, support_session=True)
        customer = billing_session.get_customer()
        assert customer is None

        # Set valid plan tier - creates Customer object
        message = billing_session.process_support_view_request(support_view_request)
        self.assertEqual("Required plan tier for zulip set to Zulip Cloud Standard.", message)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.CUSTOMER_PROPERTY_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            "old_value": None,
            "new_value": valid_plan_tier,
            "property": "required_plan_tier",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)
        customer = billing_session.get_customer()
        assert customer is not None
        self.assertEqual(customer.required_plan_tier, valid_plan_tier)
        self.assertEqual(customer.default_discount, None)

        # Check that discount is only applied to set plan tier
        billing_session.attach_discount_to_customer(Decimal(50))
        customer.refresh_from_db()
        self.assertEqual(customer.default_discount, Decimal(50))
        discount_for_standard_plan = customer.get_discount_for_plan_tier(valid_plan_tier)
        self.assertEqual(discount_for_standard_plan, customer.default_discount)
        discount_for_plus_plan = customer.get_discount_for_plan_tier(CustomerPlan.TIER_CLOUD_PLUS)
        self.assertEqual(discount_for_plus_plan, None)

        # Try to set invalid plan tier
        invalid_plan_tier = CustomerPlan.TIER_SELF_HOSTED_BASE
        support_view_request = SupportViewRequest(
            support_type=SupportType.update_required_plan_tier,
            required_plan_tier=invalid_plan_tier,
        )
        with self.assertRaisesRegex(SupportRequestError, "Invalid plan tier for zulip."):
            billing_session.process_support_view_request(support_view_request)

        # Cannot set required plan tier to None before setting discount to 0.
        support_view_request = SupportViewRequest(
            support_type=SupportType.update_required_plan_tier, required_plan_tier=0
        )
        with self.assertRaisesRegex(
            SupportRequestError,
            "Discount for zulip must be 0 before setting required plan tier to None.",
        ):
            billing_session.process_support_view_request(support_view_request)

        billing_session.attach_discount_to_customer(Decimal(0))
        message = billing_session.process_support_view_request(support_view_request)
        self.assertEqual("Required plan tier for zulip set to None.", message)
        customer.refresh_from_db()
        self.assertIsNone(customer.required_plan_tier)
        discount_for_standard_plan = customer.get_discount_for_plan_tier(valid_plan_tier)
        self.assertEqual(discount_for_standard_plan, customer.default_discount)
        discount_for_plus_plan = customer.get_discount_for_plan_tier(CustomerPlan.TIER_CLOUD_PLUS)
        self.assertEqual(discount_for_plus_plan, customer.default_discount)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.CUSTOMER_PROPERTY_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            "old_value": valid_plan_tier,
            "new_value": None,
            "property": "required_plan_tier",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

    def test_approve_realm_sponsorship(self) -> None:
        realm = get_realm("zulip")
        self.assertNotEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD_FREE)

        support_admin = self.example_user("iago")
        billing_session = RealmBillingSession(user=support_admin, realm=realm, support_session=True)
        billing_session.approve_sponsorship()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD_FREE)

        expected_message = (
            "Your organization's request for sponsored hosting has been approved! You have been upgraded to Zulip Cloud Standard, free of charge. :tada:"
            "\n\nIf you could [list Zulip as a sponsor on your website](/help/linking-to-zulip-website), we would really appreciate it!"
        )
        sender = get_system_bot(settings.NOTIFICATION_BOT, realm.id)

        # Organization owners get the notification bot message
        desdemona_recipient = self.example_user("desdemona").recipient
        message_to_owner = Message.objects.filter(
            realm_id=realm.id, sender=sender.id, recipient=desdemona_recipient
        ).first()
        assert message_to_owner is not None
        self.assertEqual(message_to_owner.content, expected_message)
        self.assertEqual(message_to_owner.recipient.type, Recipient.PERSONAL)

        # Organization billing admins get the notification bot message
        hamlet_recipient = self.example_user("hamlet").recipient
        message_to_billing_admin = Message.objects.filter(
            realm_id=realm.id, sender=sender.id, recipient=hamlet_recipient
        ).first()
        assert message_to_billing_admin is not None
        self.assertEqual(message_to_billing_admin.content, expected_message)
        self.assertEqual(message_to_billing_admin.recipient.type, Recipient.PERSONAL)

    def test_update_realm_sponsorship_status(self) -> None:
        lear = get_realm("lear")
        iago = self.example_user("iago")
        billing_session = RealmBillingSession(user=iago, realm=lear, support_session=True)
        billing_session.update_customer_sponsorship_status(True)
        customer = get_customer_by_realm(realm=lear)
        assert customer is not None
        self.assertTrue(customer.sponsorship_pending)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_SPONSORSHIP_PENDING_STATUS_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {"sponsorship_pending": True}
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)
        self.assertEqual(realm_audit_log.acting_user, iago)

    def test_update_realm_billing_modality(self) -> None:
        realm = get_realm("zulip")
        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")
        plan = CustomerPlan.objects.create(
            customer=customer,
            status=CustomerPlan.ACTIVE,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        self.assertEqual(plan.charge_automatically, False)

        support_admin = self.example_user("iago")
        billing_session = RealmBillingSession(user=support_admin, realm=realm, support_session=True)
        billing_session.update_billing_modality_of_current_plan(True)
        plan.refresh_from_db()
        self.assertEqual(plan.charge_automatically, True)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_BILLING_MODALITY_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {"charge_automatically": plan.charge_automatically}
        self.assertEqual(realm_audit_log.acting_user, support_admin)
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        billing_session.update_billing_modality_of_current_plan(False)
        plan.refresh_from_db()
        self.assertEqual(plan.charge_automatically, False)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_BILLING_MODALITY_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {"charge_automatically": plan.charge_automatically}
        self.assertEqual(realm_audit_log.acting_user, support_admin)
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

    @mock_stripe()
    def test_switch_realm_from_standard_to_plus_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_and_upgrade(user)
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        original_plan = get_current_plan_by_customer(customer)
        assert original_plan is not None
        self.assertEqual(original_plan.tier, CustomerPlan.TIER_CLOUD_STANDARD)

        support_admin = self.example_user("iago")
        billing_session = RealmBillingSession(
            user=support_admin, realm=user.realm, support_session=True
        )
        support_request = SupportViewRequest(
            support_type=SupportType.modify_plan,
            plan_modification="upgrade_plan_tier",
            new_plan_tier=CustomerPlan.TIER_CLOUD_PLUS,
        )
        success_message = billing_session.process_support_view_request(support_request)
        self.assertEqual(success_message, "zulip upgraded to Zulip Cloud Plus")
        customer.refresh_from_db()
        new_plan = get_current_plan_by_customer(customer)
        assert new_plan is not None
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_CLOUD_PLUS)

    @mock_stripe()
    def test_downgrade_realm_and_void_open_invoices(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True)
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        original_plan = get_current_plan_by_customer(customer)
        assert original_plan is not None
        self.assertEqual(original_plan.status, CustomerPlan.ACTIVE)

        support_admin = self.example_user("iago")
        billing_session = RealmBillingSession(
            user=support_admin, realm=user.realm, support_session=True
        )

        # Send renewal invoice.
        invoice_plans_as_needed(self.now + timedelta(days=367))

        support_request = SupportViewRequest(
            support_type=SupportType.modify_plan,
            plan_modification="downgrade_now_void_open_invoices",
        )
        success_message = billing_session.process_support_view_request(support_request)
        self.assertEqual(success_message, "zulip downgraded and voided 1 open invoices")
        original_plan.refresh_from_db()
        self.assertEqual(original_plan.status, CustomerPlan.ENDED)


class TestRemoteBillingWriteAuditLog(StripeTestCase):
    def test_write_audit_log(self) -> None:
        support_admin = self.example_user("iago")
        server_uuid = str(uuid.uuid4())
        remote_server = RemoteZulipServer.objects.create(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        realm_uuid = str(uuid.uuid4())
        remote_realm = RemoteRealm.objects.create(
            server=remote_server,
            uuid=realm_uuid,
            uuid_owner_secret="dummy-owner-secret",
            host="dummy-hostname",
            realm_date_created=timezone_now(),
        )
        remote_realm_billing_user = RemoteRealmBillingUser.objects.create(
            remote_realm=remote_realm, email="admin@example.com", user_uuid=uuid.uuid4()
        )
        remote_server_billing_user = RemoteServerBillingUser.objects.create(
            remote_server=remote_server, email="admin@example.com"
        )
        event_time = timezone_now()

        def assert_audit_log(
            audit_log: Union[RemoteRealmAuditLog, RemoteZulipServerAuditLog],
            acting_remote_user: Optional[Union[RemoteRealmBillingUser, RemoteServerBillingUser]],
            acting_support_user: Optional[UserProfile],
            event_type: int,
            event_time: datetime,
        ) -> None:
            self.assertEqual(audit_log.event_type, event_type)
            self.assertEqual(audit_log.event_time, event_time)
            self.assertEqual(audit_log.acting_remote_user, acting_remote_user)
            self.assertEqual(audit_log.acting_support_user, acting_support_user)

        for session_class, audit_log_class, remote_object, remote_user in [
            (
                RemoteRealmBillingSession,
                RemoteRealmAuditLog,
                remote_realm,
                remote_realm_billing_user,
            ),
            (
                RemoteServerBillingSession,
                RemoteZulipServerAuditLog,
                remote_server,
                remote_server_billing_user,
            ),
        ]:
            # Necessary cast or mypy doesn't understand that we can use Django's
            # model .objects. style queries on this.
            audit_log_model = cast(
                Union[Type[RemoteRealmAuditLog], Type[RemoteZulipServerAuditLog]], audit_log_class
            )
            assert isinstance(remote_user, (RemoteRealmBillingUser, RemoteServerBillingUser))
            # No acting user:
            session = session_class(remote_object)
            session.write_to_audit_log(
                # This "ordinary billing" event type value gets translated by write_to_audit_log
                # into a RemoteRealmBillingSession.CUSTOMER_PLAN_CREATED or
                # RemoteServerBillingSession.CUSTOMER_PLAN_CREATED value.
                event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED,
                event_time=event_time,
            )
            audit_log = audit_log_model.objects.latest("id")
            assert_audit_log(
                audit_log, None, None, audit_log_class.CUSTOMER_PLAN_CREATED, event_time
            )

            session = session_class(remote_object, remote_billing_user=remote_user)
            session.write_to_audit_log(
                event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED,
                event_time=event_time,
            )
            audit_log = audit_log_model.objects.latest("id")
            assert_audit_log(
                audit_log, remote_user, None, audit_log_class.CUSTOMER_PLAN_CREATED, event_time
            )

            session = session_class(
                remote_object, remote_billing_user=None, support_staff=support_admin
            )
            session.write_to_audit_log(
                event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED,
                event_time=event_time,
            )
            audit_log = audit_log_model.objects.latest("id")
            assert_audit_log(
                audit_log, None, support_admin, audit_log_class.CUSTOMER_PLAN_CREATED, event_time
            )


@override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
class TestRemoteRealmBillingFlow(StripeTestCase, RemoteRealmBillingTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()

        # Reset already created audit logs for this test as they have
        # event_time=timezone_now() that will affects the LicenseLedger
        # queries as their event_time would be more recent than other
        # operations we perform in this test.
        zulip_realm = get_realm("zulip")
        RealmAuditLog.objects.filter(
            realm=zulip_realm, event_type__in=RealmAuditLog.SYNCED_BILLING_EVENTS
        ).delete()
        with time_machine.travel(self.now, tick=False):
            for count in range(4):
                do_create_user(
                    f"email {count}",
                    f"password {count}",
                    zulip_realm,
                    "name",
                    acting_user=None,
                )

        self.remote_realm = RemoteRealm.objects.get(uuid=zulip_realm.uuid)
        self.billing_session = RemoteRealmBillingSession(remote_realm=self.remote_realm)

    @responses.activate
    @mock_stripe()
    def test_upgrade_user_to_business_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        realm_user_count = UserProfile.objects.filter(
            realm=hamlet.realm, is_bot=False, is_active=True
        ).count()
        self.assertEqual(realm_user_count, 11)

        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        result = self.execute_remote_billing_authentication_flow(hamlet)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

        # upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/", subdomain="selfhosting"
            )
        self.assertEqual(result.status_code, 200)

        # Min licenses used since org has less users.
        min_licenses = self.billing_session.min_licenses_for_plan(
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS
        )
        self.assertEqual(min_licenses, 25)
        flat_discount, flat_discounted_months = self.billing_session.get_flat_discount_info()
        self.assertEqual(flat_discounted_months, 12)

        self.assert_in_success_response(
            [
                "Minimum purchase for",
                f"{min_licenses} licenses",
                "Add card",
                "Purchase Zulip Business",
            ],
            result,
        )

        # Same result even with free trial enabled for self hosted customers since we don't
        # offer free trial for business plan.
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/", subdomain="selfhosting"
                )

        self.assert_in_success_response(
            [
                "Minimum purchase for",
                f"{min_licenses} licenses",
                "Add card",
                "Purchase Zulip Business",
            ],
            result,
        )

        # Check that cloud free trials don't affect self hosted customers.
        with self.settings(CLOUD_FREE_TRIAL_DAYS=30):
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/", subdomain="selfhosting"
                )

        self.assert_in_success_response(
            [
                "Minimum purchase for",
                f"{min_licenses} licenses",
                "Add card",
                "Purchase Zulip Business",
            ],
            result,
        )

        self.assertFalse(Customer.objects.exists())
        self.assertFalse(CustomerPlan.objects.exists())
        self.assertFalse(LicenseLedger.objects.exists())

        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade()

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        LicenseLedger.objects.get(plan=plan)

        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Business",
            "Number of licenses",
            f"{min_licenses} (managed automatically)",
            "January 2, 2013",
            "Your plan will automatically renew on",
            f"${80 * min_licenses:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Verify that change in user count updates LicenseLedger.
        audit_log_count = RemoteRealmAuditLog.objects.count()
        self.assertEqual(LicenseLedger.objects.count(), 1)

        with time_machine.travel(self.now + timedelta(days=2), tick=False):
            for count in range(realm_user_count, min_licenses + 10):
                do_create_user(
                    f"email {count}",
                    f"password {count}",
                    hamlet.realm,
                    "name",
                    role=UserProfile.ROLE_MEMBER,
                    acting_user=None,
                )

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertEqual(
            RemoteRealmAuditLog.objects.count(),
            min_licenses + 10 - realm_user_count + audit_log_count,
        )
        latest_ledger = LicenseLedger.objects.last()
        assert latest_ledger is not None
        self.assertEqual(latest_ledger.licenses, min_licenses + 10)

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )

        self.assertEqual(latest_ledger.licenses, 35)
        for substring in [
            "Zulip Business",
            "Number of licenses",
            f"{latest_ledger.licenses} (managed automatically)",
            "January 2, 2013",
            "Your plan will automatically renew on",
            f"${80 * latest_ledger.licenses:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

    @responses.activate
    @mock_stripe()
    def test_stripe_billing_portal_urls_for_remote_realm(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet)
        self.add_card_and_upgrade()

        response = self.client_get(
            f"{self.billing_session.billing_base_url}/invoices/", subdomain="selfhosting"
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com"))

        response = self.client_get(
            f"{self.billing_session.billing_base_url}/customer_portal/?return_to_billing_page=true",
            subdomain="selfhosting",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com"))

    @responses.activate
    @mock_stripe()
    def test_upgrade_user_to_basic_plan_free_trial_fails_special_case(self, *mocks: Mock) -> None:
        # Here we test if server had a legacy plan but never it ended before we could ever migrate
        # it to remote realm resulting in the upgrade for remote realm creating a new customer which
        # doesn't have any legacy plan associated with it. In this case, free trail should not be offered.
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()
            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            result = self.execute_remote_billing_authentication_flow(hamlet)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

            # Test under normal circumstances it will show free trial.
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )

            self.assert_in_success_response(
                [
                    "Start free trial",
                    "Zulip Basic",
                    "Start 30-day free trial",
                ],
                result,
            )

            # Add ended legacy plan for remote realm server.
            new_server_customer = Customer.objects.create(remote_server=self.remote_realm.server)
            CustomerPlan.objects.create(
                customer=new_server_customer,
                status=CustomerPlan.ENDED,
                tier=CustomerPlan.TIER_SELF_HOSTED_LEGACY,
                billing_cycle_anchor=timezone_now(),
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            )

            # No longer eligible for free trial
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )

            self.assert_not_in_success_response(
                [
                    "Start free trial",
                    "Start 30-day free trial",
                ],
                result,
            )

            self.assert_in_success_response(
                [
                    "Purchase Zulip Basic",
                ],
                result,
            )

            result = self.client_get(
                f"{self.billing_session.billing_base_url}/plans/",
                subdomain="selfhosting",
            )

            self.assert_not_in_success_response(
                [
                    "Start 30-day free trial",
                ],
                result,
            )

    @responses.activate
    @mock_stripe()
    def test_upgrade_user_to_basic_plan_free_trial(self, *mocks: Mock) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()
            realm_user_count = UserProfile.objects.filter(
                realm=hamlet.realm, is_bot=False, is_active=True
            ).count()
            self.assertEqual(realm_user_count, 11)

            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            result = self.execute_remote_billing_authentication_flow(hamlet)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

            # upgrade to basic plan
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )
            self.assertEqual(result.status_code, 200)

            min_licenses = self.billing_session.min_licenses_for_plan(
                CustomerPlan.TIER_SELF_HOSTED_BASIC
            )
            self.assertEqual(min_licenses, 6)
            flat_discount, flat_discounted_months = self.billing_session.get_flat_discount_info()
            self.assertEqual(flat_discounted_months, 12)

            self.assert_in_success_response(
                [
                    "Start free trial",
                    "Zulip Basic",
                    "Due",
                    "on February 1, 2012",
                    f"{min_licenses}",
                    "Add card",
                    "Start 30-day free trial",
                ],
                result,
            )

            self.assertFalse(Customer.objects.exists())
            self.assertFalse(CustomerPlan.objects.exists())
            self.assertFalse(LicenseLedger.objects.exists())

            with time_machine.travel(self.now, tick=False):
                stripe_customer = self.add_card_and_upgrade(
                    tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
                )

            self.assertEqual(Invoice.objects.count(), 0)
            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
            plan = CustomerPlan.objects.get(customer=customer)
            LicenseLedger.objects.get(plan=plan)

            with time_machine.travel(self.now + timedelta(days=1), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
            for substring in [
                "Zulip Basic",
                "(free trial)",
                "Number of licenses",
                f"{realm_user_count} (managed automatically)",
                "February 1, 2012",
                "Your plan will automatically renew on",
                f"${3.5 * realm_user_count - flat_discount // 100 * 1:,.2f}",
                "Visa ending in 4242",
                "Update card",
            ]:
                self.assert_in_response(substring, response)

            # Verify that change in user count updates LicenseLedger.
            audit_log_count = RemoteRealmAuditLog.objects.count()
            self.assertEqual(LicenseLedger.objects.count(), 1)

            with time_machine.travel(self.now + timedelta(days=2), tick=False):
                for count in range(realm_user_count, min_licenses + 10):
                    do_create_user(
                        f"email {count}",
                        f"password {count}",
                        hamlet.realm,
                        "name",
                        role=UserProfile.ROLE_MEMBER,
                        acting_user=None,
                    )

            with time_machine.travel(self.now + timedelta(days=3), tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            self.assertEqual(
                RemoteRealmAuditLog.objects.count(),
                min_licenses + 10 - realm_user_count + audit_log_count,
            )
            latest_ledger = LicenseLedger.objects.last()
            assert latest_ledger is not None
            self.assertEqual(latest_ledger.licenses, min_licenses + 10)

            with time_machine.travel(self.now + timedelta(days=3), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )

            self.assertEqual(latest_ledger.licenses, min_licenses + 10)
            for substring in [
                "Zulip Basic",
                "Number of licenses",
                f"{latest_ledger.licenses} (managed automatically)",
                "February 1, 2012",
                "Your plan will automatically renew on",
                f"${3.5 * latest_ledger.licenses - flat_discount // 100 * 1:,.2f}",
                "Visa ending in 4242",
                "Update card",
            ]:
                self.assert_in_response(substring, response)

            # Check minimum licenses is 0 after flat discounted months is over.
            customer.flat_discounted_months = 0
            customer.save(update_fields=["flat_discounted_months"])
            self.assertEqual(
                self.billing_session.min_licenses_for_plan(CustomerPlan.TIER_SELF_HOSTED_BASIC), 1
            )

            # TODO: Add test for invoice generation once that's implemented.

    @responses.activate
    @mock_stripe()
    def test_redirect_for_remote_realm_billing_page_downgrade_at_free_trial_end(
        self, *mocks: Mock
    ) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()
            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            result = self.execute_remote_billing_authentication_flow(hamlet)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

            # upgrade to basic plan
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )
            self.assertEqual(result.status_code, 200)

            self.assert_in_success_response(
                [
                    "Start free trial",
                    "Zulip Basic",
                    "Due",
                    "on February 1, 2012",
                    "Add card",
                    "Start 30-day free trial",
                ],
                result,
            )

            self.assertFalse(Customer.objects.exists())
            self.assertFalse(CustomerPlan.objects.exists())
            self.assertFalse(LicenseLedger.objects.exists())

            with time_machine.travel(self.now, tick=False):
                stripe_customer = self.add_card_and_upgrade(
                    tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
                )

            self.assertEqual(Invoice.objects.count(), 0)
            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
            plan = CustomerPlan.objects.get(customer=customer)
            LicenseLedger.objects.get(plan=plan)

            with time_machine.travel(self.now + timedelta(days=1), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
            for substring in [
                "Zulip Basic",
                "(free trial)",
                "Your plan will automatically renew on",
                "February 1, 2012",
            ]:
                self.assert_in_response(substring, response)

            # schedule downgrade
            with time_machine.travel(self.now + timedelta(days=3), tick=False), self.assertLogs(
                "corporate.stripe", "INFO"
            ) as m:
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL},
                )
                self.assert_json_success(response)
                plan.refresh_from_db()
                self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL)
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL}"
                self.assertEqual(m.output[0], expected_log)

            # Visit /billing on free-trial end date before the invoice cron runs.
            with time_machine.travel(self.now + timedelta(days=30), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    f"{self.billing_session.billing_base_url}/plans/", response["Location"]
                )

    @responses.activate
    @mock_stripe()
    def test_upgrade_remote_realm_user_to_monthly_basic_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        realm_user_count = UserProfile.objects.filter(
            realm=hamlet.realm, is_bot=False, is_active=True
        ).count()
        self.assertEqual(realm_user_count, 11)

        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        result = self.execute_remote_billing_authentication_flow(hamlet)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

        # upgrade to basic plan
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                subdomain="selfhosting",
            )
        self.assertEqual(result.status_code, 200)

        min_licenses = self.billing_session.min_licenses_for_plan(
            CustomerPlan.TIER_SELF_HOSTED_BASIC
        )
        self.assertEqual(min_licenses, 6)
        flat_discount, flat_discounted_months = self.billing_session.get_flat_discount_info()
        self.assertEqual(flat_discounted_months, 12)

        self.assert_in_success_response(
            [f"{realm_user_count}", "Add card", "Purchase Zulip Basic"], result
        )

        self.assertFalse(Customer.objects.exists())
        self.assertFalse(CustomerPlan.objects.exists())
        self.assertFalse(LicenseLedger.objects.exists())

        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        LicenseLedger.objects.get(plan=plan)

        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Basic",
            "Number of licenses",
            f"{realm_user_count} (managed automatically)",
            "February 2, 2012",
            "Your plan will automatically renew on",
            f"${3.5 * realm_user_count - flat_discount // 100 * 1:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Verify that change in user count updates LicenseLedger.
        audit_log_count = RemoteRealmAuditLog.objects.count()
        self.assertEqual(LicenseLedger.objects.count(), 1)

        with time_machine.travel(self.now + timedelta(days=2), tick=False):
            for count in range(realm_user_count, min_licenses + 10):
                do_create_user(
                    f"email {count}",
                    f"password {count}",
                    hamlet.realm,
                    "name",
                    role=UserProfile.ROLE_MEMBER,
                    acting_user=None,
                )

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertEqual(
            RemoteRealmAuditLog.objects.count(),
            min_licenses + 10 - realm_user_count + audit_log_count,
        )
        latest_ledger = LicenseLedger.objects.last()
        assert latest_ledger is not None
        self.assertEqual(latest_ledger.licenses, min_licenses + 10)

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )

        self.assertEqual(latest_ledger.licenses, min_licenses + 10)
        for substring in [
            "Zulip Basic",
            "Number of licenses",
            f"{latest_ledger.licenses} (managed automatically)",
            "February 2, 2012",
            "Your plan will automatically renew on",
            f"${3.5 * latest_ledger.licenses - flat_discount // 100 * 1:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Check minimum licenses is 0 after flat discounted months is over.
        customer.flat_discounted_months = 0
        customer.save(update_fields=["flat_discounted_months"])
        self.assertEqual(
            self.billing_session.min_licenses_for_plan(CustomerPlan.TIER_SELF_HOSTED_BASIC), 1
        )

    @responses.activate
    @mock_stripe()
    def test_upgrade_user_to_fixed_price_monthly_basic_plan(self, *mocks: Mock) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Set fixed_price without configuring required_plan_tier.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(["Required plan tier should not be set to None"], result)

        # Configure required_plan_tier and fixed_price.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Basic."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )
        fixed_price_plan_offer = CustomerPlanOffer.objects.filter(
            status=CustomerPlanOffer.CONFIGURED
        ).first()
        assert fixed_price_plan_offer is not None
        self.assertEqual(fixed_price_plan_offer.tier, CustomerPlanOffer.TIER_SELF_HOSTED_BASIC)
        self.assertEqual(fixed_price_plan_offer.fixed_price, annual_fixed_price * 100)
        self.assertEqual(fixed_price_plan_offer.get_plan_status_as_text(), "Configured")

        result = self.client_get("/activity/remote/support", {"q": "example.com"})
        self.assert_in_success_response(
            ["Next plan information:", "Zulip Basic", "Configured", "Plan has a fixed price."],
            result,
        )

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Visit /upgrade
        self.execute_remote_billing_authentication_flow(hamlet)
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                subdomain="selfhosting",
            )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["Add card", "Purchase Zulip Basic", "This is a fixed-price plan."], result
        )

        self.assertFalse(CustomerPlan.objects.filter(status=CustomerPlan.ACTIVE).exists())

        # Upgrade to fixed-price Zulip Basic plan.
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertIsNotNone(current_plan.fixed_price)
        self.assertIsNone(current_plan.price_per_license)
        fixed_price_plan_offer.refresh_from_db()
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.PROCESSED)

        # Visit /billing
        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Basic",
            "Monthly",
            "February 2, 2012",
            "This is a fixed-price plan",
            "Your plan will automatically renew on",
            f"${int(annual_fixed_price / 12)}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

    @responses.activate
    @mock_stripe()
    def test_delete_configured_fixed_price_plan_offer(self, *mocks: Mock) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())

        annual_fixed_price = 1200
        # Configure required_plan_tier and fixed_price.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Basic."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )
        fixed_price_plan_offer = CustomerPlanOffer.objects.filter(
            status=CustomerPlanOffer.CONFIGURED
        ).first()
        assert fixed_price_plan_offer is not None
        self.assertEqual(fixed_price_plan_offer.tier, CustomerPlanOffer.TIER_SELF_HOSTED_BASIC)
        self.assertEqual(fixed_price_plan_offer.fixed_price, annual_fixed_price * 100)
        self.assertEqual(fixed_price_plan_offer.get_plan_status_as_text(), "Configured")

        result = self.client_get("/activity/remote/support", {"q": "example.com"})
        self.assert_in_success_response(
            ["Next plan information:", "Zulip Basic", "Configured", "Plan has a fixed price."],
            result,
        )

        billing_session = RemoteRealmBillingSession(remote_realm=self.remote_realm)
        support_request = SupportViewRequest(
            support_type=SupportType.delete_fixed_price_next_plan,
        )
        success_message = billing_session.process_support_view_request(support_request)
        self.assertEqual(success_message, "Fixed price offer deleted")
        result = self.client_get("/activity/remote/support", {"q": "example.com"})
        self.assert_not_in_success_response(["Next plan information:"], result)
        self.assert_in_success_response(["Fixed price", "Annual amount in dollars"], result)

    @responses.activate
    @mock_stripe()
    def test_upgrade_user_to_fixed_price_plan_pay_by_invoice(self, *mocks: Mock) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Basic."], result
        )

        # Configure fixed-price plan with ID of manually sent invoice.
        # Invalid 'sent_invoice_id' entered.
        annual_fixed_price = 1200
        with mock.patch("stripe.Invoice.retrieve", side_effect=Exception):
            result = self.client_post(
                "/activity/remote/support",
                {
                    "remote_realm_id": f"{self.remote_realm.id}",
                    "fixed_price": annual_fixed_price,
                    "sent_invoice_id": "invalid_sent_invoice_id",
                },
            )
        self.assert_not_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )

        # Invoice status is not 'open'.
        mock_invoice = MagicMock()
        mock_invoice.status = "paid"
        mock_invoice.sent_invoice_id = "paid_invoice_id"
        with mock.patch("stripe.Invoice.retrieve", return_value=mock_invoice):
            result = self.client_post(
                "/activity/remote/support",
                {
                    "remote_realm_id": f"{self.remote_realm.id}",
                    "fixed_price": annual_fixed_price,
                    "sent_invoice_id": mock_invoice.sent_invoice_id,
                },
            )
        self.assert_in_success_response(
            ["Invoice status should be open. Please verify sent_invoice_id."], result
        )

        sent_invoice_id = "test_sent_invoice_id"
        mock_invoice = MagicMock()
        mock_invoice.status = "open"
        mock_invoice.sent_invoice_id = sent_invoice_id
        with mock.patch("stripe.Invoice.retrieve", return_value=mock_invoice):
            result = self.client_post(
                "/activity/remote/support",
                {
                    "remote_realm_id": f"{self.remote_realm.id}",
                    "fixed_price": annual_fixed_price,
                    "sent_invoice_id": sent_invoice_id,
                },
            )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )
        fixed_price_plan_offer = CustomerPlanOffer.objects.filter(
            status=CustomerPlanOffer.CONFIGURED
        ).first()
        assert fixed_price_plan_offer is not None
        self.assertEqual(fixed_price_plan_offer.tier, CustomerPlanOffer.TIER_SELF_HOSTED_BASIC)
        self.assertEqual(fixed_price_plan_offer.fixed_price, annual_fixed_price * 100)
        self.assertEqual(fixed_price_plan_offer.sent_invoice_id, sent_invoice_id)
        self.assertEqual(fixed_price_plan_offer.get_plan_status_as_text(), "Configured")

        invoice = Invoice.objects.get(stripe_invoice_id=sent_invoice_id)
        self.assertEqual(invoice.status, Invoice.SENT)

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Customer don't need to visit /upgrade to buy plan.
        # In case they visit, we inform them about the mail to which
        # invoice was sent and also display the link for payment.
        self.execute_remote_billing_authentication_flow(hamlet)
        mock_invoice = MagicMock()
        mock_invoice.hosted_invoice_url = "payments_page_url"
        with time_machine.travel(self.now, tick=False), mock.patch(
            "stripe.Invoice.retrieve", return_value=mock_invoice
        ):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                subdomain="selfhosting",
            )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["payments_page_url", hamlet.delivery_email], result)

        # When customer makes a payment, 'stripe_webhook' handles 'invoice.paid' event.
        stripe_event_id = "stripe_event_id"
        valid_invoice_paid_event_data = {
            "id": stripe_event_id,
            "type": "invoice.paid",
            "api_version": STRIPE_API_VERSION,
            "data": {
                "object": {
                    "object": "invoice",
                    "id": sent_invoice_id,
                    "collection_method": "send_invoice",
                }
            },
        }
        with time_machine.travel(self.now, tick=False):
            result = self.client_post(
                "/stripe/webhook/",
                valid_invoice_paid_event_data,
                content_type="application/json",
            )
            self.assertEqual(result.status_code, 200)

        # Verify that the customer is upgraded after payment.
        customer = self.billing_session.get_customer()
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertEqual(current_plan.fixed_price, annual_fixed_price * 100)
        self.assertIsNone(current_plan.price_per_license)

        invoice.refresh_from_db()
        fixed_price_plan_offer.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.PAID)
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.PROCESSED)

    @responses.activate
    @mock_stripe()
    def test_schedule_upgrade_to_fixed_price_annual_business_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Upgrade to fixed-price Zulip Basic plan.
        self.execute_remote_billing_authentication_flow(hamlet)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertEqual(current_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BASIC)
        self.assertIsNone(current_plan.fixed_price)
        self.assertIsNotNone(current_plan.price_per_license)

        self.logout()
        self.login("iago")

        # Schedule a fixed-price business plan at current plan end_date.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Business."], result
        )

        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            [
                f"Configure {self.billing_session.billing_entity_display_name} current plan end-date, before scheduling a new plan."
            ],
            result,
        )

        current_plan_end_date = add_months(self.now, 2)
        current_plan.end_date = current_plan_end_date
        current_plan.save(update_fields=["end_date"])

        self.assertFalse(CustomerPlan.objects.filter(fixed_price__isnull=False).exists())

        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            [
                f"Fixed price Zulip Business plan scheduled to start on {current_plan_end_date.date()}."
            ],
            result,
        )
        current_plan.refresh_from_db()
        self.assertEqual(current_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        self.assertEqual(current_plan.next_invoice_date, current_plan_end_date)
        new_plan = CustomerPlan.objects.filter(fixed_price__isnull=False).first()
        assert new_plan is not None
        self.assertEqual(new_plan.next_invoice_date, current_plan_end_date)
        self.assertEqual(
            new_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )

        # Invoice cron runs and switches plan to BUSINESS
        with time_machine.travel(current_plan_end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()

        current_plan.refresh_from_db()
        self.assertEqual(current_plan.status, CustomerPlan.ENDED)
        self.assertEqual(current_plan.next_invoice_date, None)

        new_plan.refresh_from_db()
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertIsNotNone(new_plan.fixed_price)
        self.assertIsNone(new_plan.price_per_license)

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Visit /billing
        self.execute_remote_billing_authentication_flow(
            hamlet, expect_tos=False, first_time_login=False
        )
        with time_machine.travel(current_plan_end_date + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Business",
            "Annual",
            "March 2, 2013",
            "This is a fixed-price plan",
            "Your plan ends on <strong>March 2, 2013</strong>",
            "You will be contacted by Zulip Sales",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

    @responses.activate
    @mock_stripe()
    def test_schedule_legacy_plan_upgrade_to_fixed_price_plan(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")

        remote_realm = RemoteRealm.objects.get(uuid=hamlet.realm.uuid)
        remote_realm_billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)

        # Migrate realm to legacy plan.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            remote_realm_billing_session.migrate_customer_to_legacy_plan(start_date, end_date)

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        customer = Customer.objects.get(remote_realm=self.remote_realm)
        legacy_plan = get_current_plan_by_customer(customer)
        assert legacy_plan is not None
        self.assertEqual(legacy_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(legacy_plan.next_invoice_date, end_date)

        self.login("iago")

        # Schedule a fixed-price business plan at current plan end_date.
        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Business."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Business plan."],
            result,
        )
        fixed_price_plan_offer = CustomerPlanOffer.objects.get(customer=customer)
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.CONFIGURED)
        self.assertEqual(fixed_price_plan_offer.tier, CustomerPlanOffer.TIER_SELF_HOSTED_BUSINESS)

        self.logout()
        self.login("hamlet")
        self.execute_remote_billing_authentication_flow(
            hamlet, expect_tos=False, confirm_tos=True, first_time_login=True
        )

        # Schedule upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(
                remote_server_plan_start_date="billing_cycle_end_date", talk_to_stripe=False
            )

        legacy_plan.refresh_from_db()
        self.assertEqual(legacy_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        fixed_price_plan_offer.refresh_from_db()
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.PROCESSED)

        # Invoice cron runs and switches plan to BUSINESS
        with time_machine.travel(end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()

        legacy_plan.refresh_from_db()
        current_plan = get_current_plan_by_customer(customer)
        assert current_plan is not None
        self.assertEqual(current_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertIsNotNone(current_plan.fixed_price)
        self.assertIsNone(current_plan.price_per_license)
        self.assertEqual(current_plan.next_invoice_date, add_months(end_date, 1))
        self.assertEqual(legacy_plan.status, CustomerPlan.ENDED)
        self.assertEqual(legacy_plan.next_invoice_date, None)

    @responses.activate
    @mock_stripe()
    def test_schedule_fixed_price_plan_upgrade_to_another_fixed_price_plan(
        self, *mocks: Mock
    ) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Upgrade to fixed-price Zulip Basic plan with monthly billing_schedule.
        self.execute_remote_billing_authentication_flow(hamlet)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        end_date = add_months(self.now, 12)
        self.assertIsNotNone(current_plan.fixed_price)
        self.assertEqual(current_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_MONTHLY)
        self.assertEqual(current_plan.end_date, end_date)

        # Invoice for february to october
        for invoice_count in range(1, 10):
            with time_machine.travel(add_months(self.now, invoice_count), tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)
                invoice_plans_as_needed()

        billing_entity = self.billing_session.billing_entity_display_name

        # Cron runs 60 days before the end date (november) & sends a reminder email.
        self.assertFalse(current_plan.reminder_to_review_plan_email_sent)
        with time_machine.travel(add_months(self.now, 10), tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()
        current_plan.refresh_from_db()
        self.assertTrue(current_plan.reminder_to_review_plan_email_sent)

        from django.core.mail import outbox

        messages_count = len(outbox)
        message = outbox[-1]
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "sales@zulip.com")
        self.assertIn(
            f"Support URL: {self.billing_session.support_url()}",
            message.body,
        )
        self.assertIn(
            f"Internal billing notice for {self.billing_session.billing_entity_display_name}.",
            message.body,
        )
        self.assertIn(
            "Reminder to re-evaluate the pricing and configure a new fixed-price plan accordingly.",
            message.body,
        )
        self.assertEqual(
            f"Fixed-price plan for {billing_entity} ends on {end_date.strftime('%Y-%m-%d')}",
            message.subject,
        )

        self.logout()
        self.login("iago")

        # Verify that we can't schedule a new fixed-price plan until invoice for 12th month is processed.
        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price + 200},
        )
        self.assert_in_success_response(
            [
                f"New plan for {billing_entity} can not be scheduled until all the invoices of the current plan are processed."
            ],
            result,
        )

        # Customer is charged for the last month of current plan.
        with time_machine.travel(add_months(self.now, 11), tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()

        # Verify that we don't send another email to Zulip team.
        self.assert_length(outbox, messages_count)

        # All the monthly invoices are processed, now we can schedule a plan.
        updated_annual_fixed_price = annual_fixed_price + 500
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "fixed_price": updated_annual_fixed_price,
            },
        )
        self.assert_in_success_response(
            [f"Fixed price Zulip Basic plan scheduled to start on {end_date.date()}."],
            result,
        )

        # Cron runs on end_date and customer switches to the new plan
        with time_machine.travel(end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()
        current_plan.refresh_from_db()
        self.assertEqual(current_plan.status, CustomerPlan.ENDED)
        new_plan = get_current_plan_by_customer(customer)
        assert new_plan is not None
        self.assertEqual(new_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(new_plan.fixed_price, updated_annual_fixed_price * 100)

    @responses.activate
    def test_request_sponsorship(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)
        remote_realm = RemoteRealm.objects.get(uuid=hamlet.realm.uuid)
        billing_base_url = self.billing_session.billing_base_url

        self.assertEqual(remote_realm.plan_type, RemoteRealm.PLAN_TYPE_SELF_MANAGED)
        self.assertIsNone(self.billing_session.get_customer())
        result = self.execute_remote_billing_authentication_flow(hamlet)

        # User has no plan, so we redirect to /plans by default.
        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/plans/")

        # Check strings on plans page.
        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_not_in_success_response(["Sponsorship pending"], result)

        # Navigate to request sponsorship page.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(
            ["Description of your organization", "Requested plan"], result
        )

        # Submit form data.
        data = {
            "organization_type": Realm.ORG_TYPES["opensource"]["id"],
            "website": "https://infinispan.org/",
            "description": "Infinispan is a distributed in-memory key/value data store with optional schema.",
            "expected_total_users": "10 users",
            "paid_users_count": "1 user",
            "paid_users_description": "We have 1 paid user.",
            "requested_plan": "Community",
        }
        response = self.client_billing_post("/billing/sponsorship", data)
        self.assert_json_success(response)

        customer = self.billing_session.get_customer()
        assert customer is not None

        sponsorship_request = ZulipSponsorshipRequest.objects.get(customer=customer)
        self.assertEqual(sponsorship_request.requested_plan, data["requested_plan"])
        self.assertEqual(sponsorship_request.org_website, data["website"])
        self.assertEqual(sponsorship_request.org_description, data["description"])
        self.assertEqual(
            sponsorship_request.org_type,
            Realm.ORG_TYPES["opensource"]["id"],
        )

        from django.core.mail import outbox

        # First email is remote user email confirmation, second email is for sponsorship
        message = outbox[1]
        self.assert_length(outbox, 2)
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "sales@zulip.com")
        self.assertEqual(message.subject, "Sponsorship request for Zulip Dev")
        self.assertEqual(message.reply_to, ["hamlet@zulip.com"])
        self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertIn("Zulip sponsorship request <noreply-", self.email_display_from(message))
        self.assertIn(
            f"Support URL: http://zulip.testserver/activity/remote/support?q={remote_realm.uuid!s}",
            message.body,
        )
        self.assertIn("Website: https://infinispan.org", message.body)
        self.assertIn("Organization type: Open-source", message.body)
        self.assertIn("Description:\nInfinispan is a distributed in-memory", message.body)

        # Check /billing redirects you to sponsorship page.
        response = self.client_get(f"{billing_base_url}/billing/", subdomain="selfhosting")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/realm/{realm.uuid!s}/sponsorship/")

        # Check sponsorship page shows sponsorship pending banner.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(
            ["This organization has requested sponsorship for a", "Community"], result
        )

        # Approve sponsorship
        billing_session = RemoteRealmBillingSession(
            remote_realm=remote_realm, support_staff=self.example_user("iago")
        )
        billing_session.approve_sponsorship()
        remote_realm.refresh_from_db()
        self.assertEqual(remote_realm.plan_type, RemoteRealm.PLAN_TYPE_COMMUNITY)
        # Assert such a plan exists
        CustomerPlan.objects.get(
            customer=customer,
            tier=CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
            status=CustomerPlan.ACTIVE,
            next_invoice_date=None,
            price_per_license=0,
        )

        # Check email sent.
        expected_message = (
            "Your request for Zulip sponsorship has been approved! Your organization has been upgraded to the Zulip Community plan."
            "\n\nIf you could list Zulip as a sponsor on your website, we would really appreciate it!"
        )
        self.assert_length(outbox, 3)
        message = outbox[2]
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "hamlet@zulip.com")
        self.assertEqual(message.subject, "Community plan sponsorship approved for Zulip Dev!")
        self.assertEqual(message.from_email, "noreply@testserver")
        self.assertIn(expected_message[0], message.body)
        self.assertIn(expected_message[1], message.body)

        # Check sponsorship approved banner.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(["Zulip is sponsoring a free", "Community"], result)

    @responses.activate
    @mock_stripe()
    def test_migrate_customer_server_to_realms_and_upgrade(self, *mocks: Mock) -> None:
        remote_server = RemoteZulipServer.objects.get(hostname="demo.example.com")
        server_billing_session = RemoteServerBillingSession(remote_server=remote_server)

        # Migrate server to legacy plan.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            server_billing_session.migrate_customer_to_legacy_plan(start_date, end_date)

        server_customer = server_billing_session.get_customer()
        assert server_customer is not None
        server_customer_plan = get_current_plan_by_customer(server_customer)
        assert server_customer_plan is not None
        self.assertEqual(server_customer_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(server_customer_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY)

        # The plan gets migrated if there's only a single human realm.
        Realm.objects.exclude(string_id__in=["zulip", "zulipinternal"]).delete()

        # First, set a sponsorship as pending.
        # TODO: Ideally, we'd submit a proper sponsorship request.
        server_customer.sponsorship_pending = True
        server_customer.save()

        # Upload data.
        with time_machine.travel(self.now, tick=False):
            self.add_mock_response()
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        billing_base_url = self.billing_session.billing_base_url

        # Login. The server has a pending sponsorship, in which case migrating
        # can't be done, as that'd be a fairly confusing process.
        result = self.execute_remote_billing_authentication_flow(hamlet, return_from_auth_url=True)

        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Plan management not available", result)
        # Server's plan should not have been migrated yet.
        self.server.refresh_from_db()
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY)

        # Now clear the pending sponsorship state, which will allow login
        # and migration to proceed.
        # TODO: Ideally, this would approve the sponsorship and then be testing
        # the migration of the Community plan.
        server_customer.sponsorship_pending = False
        server_customer.save()

        # Login. Performs customer migration from server to realm.
        result = self.execute_remote_billing_authentication_flow(hamlet)

        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/plans/")

        remote_server.refresh_from_db()
        remote_realm = RemoteRealm.objects.get(uuid=hamlet.realm.uuid)
        # The customer object was moved, together with the plan, from server to realm.
        customer = get_customer_by_remote_realm(remote_realm)
        assert customer is not None
        self.assertEqual(server_customer, customer)
        self.assertEqual(remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED)
        self.assertEqual(remote_realm.plan_type, RemoteRealm.PLAN_TYPE_SELF_MANAGED_LEGACY)

        customer_plan = get_current_plan_by_customer(customer)
        assert customer_plan is not None
        self.assertEqual(customer_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(customer_plan.status, CustomerPlan.ACTIVE)

        # upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(f"{billing_base_url}/upgrade/", subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Add card", "Purchase Zulip Business"], result)

        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade()

        self.assertEqual(customer, Customer.objects.get(stripe_customer_id=stripe_customer.id))
        business_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertEqual(business_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)

        realm_user_count = UserProfile.objects.filter(
            realm=hamlet.realm, is_bot=False, is_active=True
        ).count()
        licenses = max(
            realm_user_count, self.billing_session.min_licenses_for_plan(business_plan.tier)
        )
        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(f"{billing_base_url}/billing/", subdomain="selfhosting")
        for substring in [
            "Zulip Business",
            "Number of licenses",
            f"{licenses} (managed automatically)",
            "Your plan will automatically renew on",
            "January 2, 2013",
            f"${80 * licenses:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Login again
        result = self.execute_remote_billing_authentication_flow(
            hamlet, first_time_login=False, expect_tos=False, confirm_tos=False
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/billing/")

        # Downgrade
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now + timedelta(days=7), tick=False):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
                )
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {business_plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
                self.assertEqual(m.output[0], expected_log)
                self.assert_json_success(response)
        business_plan.refresh_from_db()
        self.assertEqual(business_plan.licenses_at_next_renewal(), None)

    @responses.activate
    @mock_stripe()
    def test_invoice_initial_remote_realm_upgrade(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        realm_user_count = UserProfile.objects.filter(
            realm=hamlet.realm, is_bot=False, is_active=True
        ).count()

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        [invoice0] = iter(stripe.Invoice.list(customer=stripe_customer.id))

        [invoice_item0, invoice_item1] = iter(invoice0.lines)
        invoice_item_params = {
            "amount": -2000,
            "description": "$20.00/month new customer discount",
            "quantity": 1,
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item0[key], value)

        invoice_item_params = {
            "amount": realm_user_count * 3.5 * 100,
            "description": "Zulip Basic",
            "quantity": realm_user_count,
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item1[key], value)

    @responses.activate
    @mock_stripe()
    def test_invoice_plans_as_needed(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        assert plan.customer.remote_realm is not None
        self.assertEqual(plan.next_invoice_date, self.next_month)

        with time_machine.travel(self.now + timedelta(days=2), tick=False):
            for count in range(5):
                do_create_user(
                    f"email - {count}",
                    f"password {count}",
                    hamlet.realm,
                    "name",
                    role=UserProfile.ROLE_MEMBER,
                    acting_user=None,
                )

        # Data upload was 25 days before the invoice date.
        last_audit_log_update = self.now + timedelta(days=5)
        with time_machine.travel(last_audit_log_update, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        invoice_plans_as_needed(self.next_month)
        plan.refresh_from_db()
        self.assertEqual(plan.next_invoice_date, self.next_month)
        self.assertTrue(plan.invoice_overdue_email_sent)

        from django.core.mail import outbox

        messages_count = len(outbox)
        message = outbox[-1]
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "sales@zulip.com")
        self.assertEqual(
            message.subject,
            f"Invoice overdue for {self.billing_session.billing_entity_display_name} due to stale data",
        )
        self.assertIn(
            f"Support URL: {self.billing_session.support_url()}",
            message.body,
        )
        self.assertIn(
            f"Internal billing notice for {self.billing_session.billing_entity_display_name}.",
            message.body,
        )
        self.assertIn("Recent invoice is overdue for payment.", message.body)
        self.assertIn(
            f"Last data upload: {last_audit_log_update.strftime('%Y-%m-%d')}", message.body
        )

        # Cron runs again, don't send another email to Zulip team.
        invoice_plans_as_needed(self.next_month + timedelta(days=1))
        self.assert_length(outbox, messages_count)

        # Ledger is up-to-date. Plan invoiced.
        with time_machine.travel(self.next_month, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        invoice_plans_as_needed(self.next_month)
        plan.refresh_from_db()
        self.assertEqual(plan.next_invoice_date, add_months(self.next_month, 1))
        self.assertFalse(plan.invoice_overdue_email_sent)

        assert customer.stripe_customer_id
        [invoice0, invoice1] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))

        [invoice_item0, invoice_item1, invoice_item2] = iter(invoice0.lines)
        invoice_item_params = {
            "amount": 16 * 3.5 * 100,
            "description": "Zulip Basic - renewal",
            "quantity": 16,
            "period": {
                "start": datetime_to_timestamp(self.next_month),
                "end": datetime_to_timestamp(add_months(self.next_month, 1)),
            },
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item1[key], value)

        invoice_item_params = {
            "description": "Additional license (Jan 4, 2012 - Feb 2, 2012)",
            "quantity": 5,
            "period": {
                "start": datetime_to_timestamp(self.now + timedelta(days=2)),
                "end": datetime_to_timestamp(self.next_month),
            },
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item2[key], value)

        # Verify Zulip team receives mail for the next cycle.
        invoice_plans_as_needed(add_months(self.next_month, 1))
        self.assert_length(outbox, messages_count + 1)

    @responses.activate
    @mock_stripe()
    def test_invoice_scheduled_upgrade_realm_legacy_plan(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")

        remote_realm = RemoteRealm.objects.get(uuid=hamlet.realm.uuid)
        remote_realm_billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)

        # Migrate realm to legacy plan.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            remote_realm_billing_session.migrate_customer_to_legacy_plan(start_date, end_date)

        # Upload data.
        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.login("hamlet")

        # Login.
        self.execute_remote_billing_authentication_flow(hamlet)

        # Schedule upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                remote_server_plan_start_date="billing_cycle_end_date", talk_to_stripe=False
            )

        zulip_realm_customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        assert zulip_realm_customer is not None
        realm_legacy_plan = get_current_plan_by_customer(zulip_realm_customer)
        assert realm_legacy_plan is not None
        self.assertEqual(realm_legacy_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(realm_legacy_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        self.assertEqual(realm_legacy_plan.next_invoice_date, end_date)

        new_plan = self.billing_session.get_next_plan(realm_legacy_plan)
        assert new_plan is not None
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertEqual(new_plan.status, CustomerPlan.NEVER_STARTED)
        self.assertEqual(
            new_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )
        self.assertEqual(new_plan.next_invoice_date, end_date)
        self.assertEqual(new_plan.billing_cycle_anchor, end_date)

        realm_user_count = UserProfile.objects.filter(
            realm=hamlet.realm, is_bot=False, is_active=True
        ).count()
        licenses = max(
            realm_user_count,
            self.billing_session.min_licenses_for_plan(CustomerPlan.TIER_SELF_HOSTED_BUSINESS),
        )

        with time_machine.travel(end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()
            # 'invoice_plan()' is called with both legacy & new plan, but
            # invoice is created only for new plan. The legacy plan only goes
            # through the end of cycle updates.

        realm_legacy_plan.refresh_from_db()
        new_plan.refresh_from_db()
        self.assertEqual(realm_legacy_plan.status, CustomerPlan.ENDED)
        self.assertEqual(realm_legacy_plan.next_invoice_date, None)
        self.assertEqual(new_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(new_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)
        self.assertEqual(new_plan.next_invoice_date, add_months(end_date, 1))

        [invoice0] = iter(stripe.Invoice.list(customer=stripe_customer.id))

        [invoice_item0, invoice_item1] = iter(invoice0.lines)
        invoice_item_params = {
            "amount": -2000 * 12,
            "description": "$20.00/month new customer discount",
            "quantity": 1,
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item0[key], value)

        invoice_item_params = {
            "amount": licenses * 80 * 100,
            "description": "Zulip Business - renewal",
            "quantity": licenses,
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item1[key], value)


@override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
class TestRemoteServerBillingFlow(StripeTestCase, RemoteServerTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()

        # Reset already created audit logs for this test as they have
        # event_time=timezone_now() that will affects the LicenseLedger
        # queries as their event_time would be more recent than other
        # operations we perform in this test.
        RealmAuditLog.objects.filter(event_type__in=RealmAuditLog.SYNCED_BILLING_EVENTS).delete()
        zulip_realm = get_realm("zulip")
        lear_realm = get_realm("lear")
        zephyr_realm = get_realm("zephyr")
        with time_machine.travel(self.now, tick=False):
            for count in range(2):
                for realm in [zulip_realm, zephyr_realm, lear_realm]:
                    do_create_user(
                        f"email {count}",
                        f"password {count}",
                        realm,
                        "name",
                        acting_user=None,
                    )

        self.remote_server = RemoteZulipServer.objects.get(hostname="demo.example.com")
        self.billing_session = RemoteServerBillingSession(remote_server=self.remote_server)

    @responses.activate
    @mock_stripe()
    def test_non_sponsorship_billing(self, *mocks: Mock) -> None:
        server_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()

        # Upload data
        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        billing_base_url = self.billing_session.billing_base_url

        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=True, confirm_tos=True
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/plans/")

        # upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(f"{billing_base_url}/upgrade/", subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Add card", "Purchase Zulip Business"], result)

        # Same result even with free trial enabled for self hosted customers since we don't
        # offer free trial for business plan.
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(f"{billing_base_url}/upgrade/", subdomain="selfhosting")

        self.assert_in_success_response(["Add card", "Purchase Zulip Business"], result)

        self.assertFalse(Customer.objects.exists())
        self.assertFalse(CustomerPlan.objects.exists())
        self.assertFalse(LicenseLedger.objects.exists())

        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade()

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        LicenseLedger.objects.get(plan=plan)

        # Visit billing page
        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(f"{billing_base_url}/billing/", subdomain="selfhosting")
        for substring in [
            "Zulip Business",
            "Number of licenses",
            f"{25} (managed automatically)",
            "Your plan will automatically renew on",
            "January 2, 2013",
            f"${80 * 25:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Verify that change in user count of any realm collectively updates LicenseLedger.
        audit_log_count = RemoteRealmAuditLog.objects.count()
        self.assertEqual(LicenseLedger.objects.count(), 1)

        with time_machine.travel(self.now + timedelta(days=2), tick=False):
            # Create 4 new users in each lear and zulip realm.
            for count in range(2, 6):
                for realm in [get_realm("lear"), get_realm("zulip")]:
                    do_create_user(
                        f"email {count}",
                        f"password {count}",
                        realm,
                        "name",
                        acting_user=None,
                    )

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertEqual(
            RemoteRealmAuditLog.objects.count(),
            audit_log_count + 8,
        )
        latest_ledger = LicenseLedger.objects.last()
        assert latest_ledger is not None
        self.assertEqual(latest_ledger.licenses, server_user_count + 8)

        # Login again
        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=False, confirm_tos=False
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/billing/")

        # Downgrade
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now + timedelta(days=7), tick=False):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
                )
                customer = Customer.objects.get(remote_server=self.remote_server)
                new_plan = get_current_plan_by_customer(customer)
                assert new_plan is not None
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {new_plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
                self.assertEqual(m.output[0], expected_log)
                self.assert_json_success(response)
        self.assertEqual(new_plan.licenses_at_next_renewal(), None)

    @responses.activate
    def test_request_sponsorship(self) -> None:
        hamlet = self.example_user("hamlet")
        now = timezone_now()
        with time_machine.travel(now, tick=False):
            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name, expect_tos=True, confirm_tos=True
            )

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)
        billing_base_url = self.billing_session.billing_base_url

        self.assertEqual(self.remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED)
        self.assertIsNone(self.billing_session.get_customer())

        # User has no plan, so we redirect to /plans by default.
        self.assertEqual(result["Location"], f"/server/{self.remote_server.uuid!s}/plans/")

        # Check strings on plans page.
        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_not_in_success_response(["Sponsorship pending"], result)

        # Navigate to request sponsorship page.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(
            ["Description of your organization", "Requested plan"], result
        )

        # Submit form data.
        data = {
            "organization_type": Realm.ORG_TYPES["opensource"]["id"],
            "website": "https://infinispan.org/",
            "description": "Infinispan is a distributed in-memory key/value data store with optional schema.",
            "expected_total_users": "10 users",
            "paid_users_count": "1 user",
            "paid_users_description": "We have 1 paid user.",
            "requested_plan": "Community",
        }
        response = self.client_billing_post("/billing/sponsorship", data)
        self.assert_json_success(response)

        customer = self.billing_session.get_customer()
        assert customer is not None

        sponsorship_request = ZulipSponsorshipRequest.objects.get(customer=customer)
        self.assertEqual(sponsorship_request.requested_plan, data["requested_plan"])
        self.assertEqual(sponsorship_request.org_website, data["website"])
        self.assertEqual(sponsorship_request.org_description, data["description"])
        self.assertEqual(
            sponsorship_request.org_type,
            Realm.ORG_TYPES["opensource"]["id"],
        )

        from django.core.mail import outbox

        # First email is remote user email confirmation, second email is for sponsorship
        message = outbox[1]
        self.assert_length(outbox, 2)
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "sales@zulip.com")
        self.assertEqual(message.subject, "Sponsorship request for demo.example.com")
        self.assertEqual(message.reply_to, ["hamlet@zulip.com"])
        self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertIn("Zulip sponsorship request <noreply-", self.email_display_from(message))
        self.assertIn(
            f"Support URL: http://zulip.testserver/activity/remote/support?q={self.remote_server.uuid!s}",
            message.body,
        )
        self.assertIn("Website: https://infinispan.org", message.body)
        self.assertIn("Organization type: Open-source", message.body)
        self.assertIn("Description:\nInfinispan is a distributed in-memory", message.body)

        # Check /billing redirects you to sponsorship page.
        response = self.client_get(f"{billing_base_url}/billing/", subdomain="selfhosting")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/server/{self.remote_server.uuid!s}/sponsorship/")

        # Check sponsorship page shows sponsorship pending banner.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(
            ["This organization has requested sponsorship for a", "Community"], result
        )

        # Approve sponsorship
        billing_session = RemoteServerBillingSession(
            remote_server=self.remote_server, support_staff=self.example_user("iago")
        )
        billing_session.approve_sponsorship()
        self.remote_server.refresh_from_db()
        self.assertEqual(self.remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_COMMUNITY)
        # Assert such a plan exists
        CustomerPlan.objects.get(
            customer=customer,
            tier=CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
            status=CustomerPlan.ACTIVE,
            next_invoice_date=None,
            price_per_license=0,
        )

        # Check email sent.
        expected_message = (
            "Your request for Zulip sponsorship has been approved! Your organization has been upgraded to the Zulip Community plan."
            "\n\nIf you could list Zulip as a sponsor on your website, we would really appreciate it!"
        )
        self.assert_length(outbox, 3)
        message = outbox[2]
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "hamlet@zulip.com")
        self.assertEqual(
            message.subject, "Community plan sponsorship approved for demo.example.com!"
        )
        self.assertEqual(message.from_email, "noreply@testserver")
        self.assertIn(expected_message[0], message.body)
        self.assertIn(expected_message[1], message.body)

        # Check sponsorship approved banner.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(["Zulip is sponsoring a free", "Community"], result)

    @responses.activate
    @mock_stripe()
    def test_upgrade_legacy_plan(self, *mocks: Mock) -> None:
        # Upload data
        with time_machine.travel(self.now, tick=False):
            self.add_mock_response()
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Migrate server to legacy plan.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            self.billing_session.migrate_customer_to_legacy_plan(start_date, end_date)

        customer = self.billing_session.get_customer()
        assert customer is not None
        customer_plan = get_current_plan_by_customer(customer)
        assert customer_plan is not None
        self.assertEqual(customer_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(customer_plan.status, CustomerPlan.ACTIVE)

        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        billing_base_url = self.billing_session.billing_base_url

        # Login
        with time_machine.travel(self.now, tick=False):
            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name, expect_tos=True, confirm_tos=True
            )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/plans/")

        # Visit '/upgrade'
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(f"{billing_base_url}/upgrade/", subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Add card", "Schedule upgrade to Zulip Business"], result)

        # Add card and schedule upgrade
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(
                remote_server_plan_start_date="billing_cycle_end_date", talk_to_stripe=False
            )
        customer_plan.refresh_from_db()
        self.assertEqual(customer_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        self.assertEqual(customer_plan.end_date, end_date)
        new_customer_plan = self.billing_session.get_next_plan(customer_plan)
        assert new_customer_plan is not None
        self.assertEqual(new_customer_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertEqual(new_customer_plan.status, CustomerPlan.NEVER_STARTED)
        self.assertEqual(new_customer_plan.billing_cycle_anchor, end_date)

        # Visit billing page
        with time_machine.travel(self.now, tick=False):
            response = self.client_get(f"{billing_base_url}/billing/", subdomain="selfhosting")
        for substring in [
            "(legacy plan)",
            f"This is a legacy plan that ends on {end_date.strftime('%B %d, %Y')}",
            f"Your plan will automatically upgrade to Zulip Business on {end_date.strftime('%B %d, %Y')}",
            "Expected next charge",
            f"${80 * 25 - 20 * 12:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Login again
        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=False, confirm_tos=False
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/billing/")

        # Downgrade
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now + timedelta(days=7), tick=False):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.ACTIVE},
                )
                self.assert_json_success(response)
                self.assertEqual(
                    m.output[0],
                    f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {new_customer_plan.id}, status: {CustomerPlan.ENDED}",
                )
                self.assertEqual(
                    m.output[1],
                    f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {customer_plan.id}, status: {CustomerPlan.ACTIVE}",
                )

    @responses.activate
    @mock_stripe()
    def test_free_trial_not_available_for_active_legacy_customer(self, *mocks: Mock) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()

            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)
                # Test that free trial is not available for customers with active legacy plan.
                end_date = add_months(self.now, months=3)
                self.billing_session.migrate_customer_to_legacy_plan(self.now, end_date)

            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")
            with time_machine.travel(self.now, tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/plans/", subdomain="selfhosting"
                )
                self.assert_not_in_success_response(["free trial"], response)

            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )
                self.assert_not_in_success_response(["free trial"], response)

            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(
                    tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
                )

            with time_machine.travel(self.now + timedelta(days=1), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
                self.assert_not_in_success_response(["(free trial)"], response)

    @responses.activate
    @mock_stripe()
    def test_free_trial_not_available_for_ended_legacy_customer(self, *mocks: Mock) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()

            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)
                # Test that free trial is not available for customers with active legacy plan.
                end_date = add_months(self.now, months=3)
                self.billing_session.migrate_customer_to_legacy_plan(self.now, end_date)
                CustomerPlan.objects.filter(customer__remote_server=self.remote_server).update(
                    status=CustomerPlan.ENDED
                )

            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")
            with time_machine.travel(self.now, tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/plans/", subdomain="selfhosting"
                )
                self.assert_not_in_success_response(["free trial"], response)

            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )
                self.assert_not_in_success_response(["free trial"], response)

            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(
                    tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
                )

            with time_machine.travel(self.now + timedelta(days=1), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
                self.assert_not_in_success_response(["(free trial)"], response)

    @responses.activate
    @mock_stripe()
    def test_upgrade_user_to_basic_plan_free_trial_remote_server(self, *mocks: Mock) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()
            realm_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()
            self.assertEqual(realm_user_count, 18)

            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

            # upgrade to basic plan
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )
            self.assertEqual(result.status_code, 200)

            min_licenses = self.billing_session.min_licenses_for_plan(
                CustomerPlan.TIER_SELF_HOSTED_BASIC
            )
            self.assertEqual(min_licenses, 6)
            flat_discount, flat_discounted_months = self.billing_session.get_flat_discount_info()
            self.assertEqual(flat_discounted_months, 12)

            self.assert_in_success_response(
                [
                    "Start free trial",
                    "Zulip Basic",
                    "Due",
                    "on February 1, 2012",
                    f"{min_licenses}",
                    "Add card",
                    "Start 30-day free trial",
                ],
                result,
            )

            self.assertFalse(Customer.objects.exists())
            self.assertFalse(CustomerPlan.objects.exists())
            self.assertFalse(LicenseLedger.objects.exists())

            with time_machine.travel(self.now, tick=False):
                stripe_customer = self.add_card_and_upgrade(
                    tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
                )
            self.assertEqual(Invoice.objects.count(), 0)

            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
            plan = CustomerPlan.objects.get(customer=customer)
            LicenseLedger.objects.get(plan=plan)

            with time_machine.travel(self.now + timedelta(days=1), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
            for substring in [
                "Zulip Basic",
                "(free trial)",
                "Number of licenses",
                f"{realm_user_count} (managed automatically)",
                "February 1, 2012",
                "Your plan will automatically renew on",
                f"${3.5 * realm_user_count - flat_discount // 100 * 1:,.2f}",
                "Visa ending in 4242",
                "Update card",
            ]:
                self.assert_in_response(substring, response)

            # Verify that change in user count updates LicenseLedger.
            audit_log_count = RemoteRealmAuditLog.objects.count()
            self.assertEqual(LicenseLedger.objects.count(), 1)

            with time_machine.travel(self.now + timedelta(days=2), tick=False):
                for count in range(realm_user_count, realm_user_count + 10):
                    do_create_user(
                        f"email {count}",
                        f"password {count}",
                        hamlet.realm,
                        "name",
                        role=UserProfile.ROLE_MEMBER,
                        acting_user=None,
                    )

            with time_machine.travel(self.now + timedelta(days=3), tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            self.assertEqual(
                RemoteRealmAuditLog.objects.count(),
                audit_log_count + 10,
            )
            latest_ledger = LicenseLedger.objects.last()
            assert latest_ledger is not None
            self.assertEqual(latest_ledger.licenses, 28)

            with time_machine.travel(self.now + timedelta(days=3), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )

            self.assertEqual(latest_ledger.licenses, 28)
            for substring in [
                "Zulip Basic",
                "Number of licenses",
                f"{latest_ledger.licenses} (managed automatically)",
                "February 1, 2012",
                "Your plan will automatically renew on",
                f"${3.5 * latest_ledger.licenses - flat_discount // 100 * 1:,.2f}",
                "Visa ending in 4242",
                "Update card",
            ]:
                self.assert_in_response(substring, response)

            # Check minimum licenses is 0 after flat discounted months is over.
            customer.flat_discounted_months = 0
            customer.save(update_fields=["flat_discounted_months"])
            self.assertEqual(
                self.billing_session.min_licenses_for_plan(CustomerPlan.TIER_SELF_HOSTED_BASIC), 1
            )

            # TODO: Add test for invoice generation once that's implemented.

    @responses.activate
    @mock_stripe()
    def test_redirect_for_remote_server_billing_page_downgrade_at_free_trial_end(
        self, *mocks: Mock
    ) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()
            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

            # upgrade to basic plan
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )
            self.assertEqual(result.status_code, 200)

            self.assert_in_success_response(
                [
                    "Start free trial",
                    "Zulip Basic",
                    "Due",
                    "on February 1, 2012",
                    "Add card",
                    "Start 30-day free trial",
                ],
                result,
            )

            self.assertFalse(Customer.objects.exists())
            self.assertFalse(CustomerPlan.objects.exists())
            self.assertFalse(LicenseLedger.objects.exists())

            with time_machine.travel(self.now, tick=False):
                stripe_customer = self.add_card_and_upgrade(
                    tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
                )

            self.assertEqual(Invoice.objects.count(), 0)
            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
            plan = CustomerPlan.objects.get(customer=customer)
            LicenseLedger.objects.get(plan=plan)

            with time_machine.travel(self.now + timedelta(days=1), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
            for substring in [
                "Zulip Basic",
                "(free trial)",
                "Your plan will automatically renew on",
                "February 1, 2012",
            ]:
                self.assert_in_response(substring, response)

            # schedule downgrade
            with time_machine.travel(self.now + timedelta(days=3), tick=False), self.assertLogs(
                "corporate.stripe", "INFO"
            ) as m:
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL},
                )
                self.assert_json_success(response)
                plan.refresh_from_db()
                self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL)
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL}"
                self.assertEqual(m.output[0], expected_log)

            # Visit /billing on free-trial end date before the invoice cron runs.
            with time_machine.travel(self.now + timedelta(days=30), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    f"{self.billing_session.billing_base_url}/plans/", response["Location"]
                )

    @responses.activate
    @mock_stripe()
    def test_upgrade_server_user_to_monthly_basic_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        server_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()
        self.assertEqual(server_user_count, 18)

        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

        # upgrade to basic plan
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                subdomain="selfhosting",
            )
        self.assertEqual(result.status_code, 200)

        min_licenses = self.billing_session.min_licenses_for_plan(
            CustomerPlan.TIER_SELF_HOSTED_BASIC
        )
        self.assertEqual(min_licenses, 6)
        flat_discount, flat_discounted_months = self.billing_session.get_flat_discount_info()
        self.assertEqual(flat_discounted_months, 12)

        self.assert_in_success_response(
            [f"{min_licenses}", "Add card", "Purchase Zulip Basic"], result
        )

        self.assertFalse(Customer.objects.exists())
        self.assertFalse(CustomerPlan.objects.exists())
        self.assertFalse(LicenseLedger.objects.exists())

        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        LicenseLedger.objects.get(plan=plan)

        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Basic",
            "Number of licenses",
            f"{server_user_count} (managed automatically)",
            "February 2, 2012",
            "Your plan will automatically renew on",
            f"${3.5 * server_user_count - flat_discount // 100 * 1:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Verify that change in user count updates LicenseLedger.
        audit_log_count = RemoteRealmAuditLog.objects.count()
        self.assertEqual(LicenseLedger.objects.count(), 1)

        with time_machine.travel(self.now + timedelta(days=2), tick=False):
            for count in range(server_user_count, server_user_count + 10):
                do_create_user(
                    f"email {count}",
                    f"password {count}",
                    hamlet.realm,
                    "name",
                    role=UserProfile.ROLE_MEMBER,
                    acting_user=None,
                )

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertEqual(
            RemoteRealmAuditLog.objects.count(),
            audit_log_count + 10,
        )
        latest_ledger = LicenseLedger.objects.last()
        assert latest_ledger is not None
        self.assertEqual(latest_ledger.licenses, 28)

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )

        self.assertEqual(latest_ledger.licenses, 28)
        for substring in [
            "Zulip Basic",
            "Number of licenses",
            f"{latest_ledger.licenses} (managed automatically)",
            "February 2, 2012",
            "Your plan will automatically renew on",
            f"${3.5 * latest_ledger.licenses - flat_discount // 100 * 1:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Check minimum licenses is 0 after flat discounted months is over.
        customer.flat_discounted_months = 0
        customer.save(update_fields=["flat_discounted_months"])
        self.assertEqual(
            self.billing_session.min_licenses_for_plan(CustomerPlan.TIER_SELF_HOSTED_BASIC), 1
        )

    @responses.activate
    @mock_stripe()
    def test_stripe_billing_portal_urls_for_remote_server(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        self.add_card_and_upgrade()

        response = self.client_get(
            f"{self.billing_session.billing_base_url}/invoices/", subdomain="selfhosting"
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com"))

        response = self.client_get(
            f"{self.billing_session.billing_base_url}/customer_portal/?return_to_billing_page=true",
            subdomain="selfhosting",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com"))

    @responses.activate
    @mock_stripe()
    def test_upgrade_server_to_fixed_price_monthly_basic_plan(self, *mocks: Mock) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_server_id": f"{self.remote_server.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for demo.example.com set to Zulip Basic."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_server_id": f"{self.remote_server.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )
        fixed_price_plan_offer = CustomerPlanOffer.objects.filter(
            status=CustomerPlanOffer.CONFIGURED
        ).first()
        assert fixed_price_plan_offer is not None
        self.assertEqual(fixed_price_plan_offer.tier, CustomerPlanOffer.TIER_SELF_HOSTED_BASIC)
        self.assertEqual(fixed_price_plan_offer.fixed_price, annual_fixed_price * 100)

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Visit /upgrade
        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                subdomain="selfhosting",
            )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["Add card", "Purchase Zulip Basic", "This is a fixed-price plan."], result
        )

        self.assertFalse(CustomerPlan.objects.filter(status=CustomerPlan.ACTIVE).exists())

        # Upgrade to fixed-price Zulip Basic plan.
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertIsNotNone(current_plan.fixed_price)
        self.assertIsNone(current_plan.price_per_license)
        fixed_price_plan_offer.refresh_from_db()
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.PROCESSED)

        # Visit /billing
        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Basic",
            "Monthly",
            "February 2, 2012",
            "This is a fixed-price plan",
            "Your plan will automatically renew on",
            f"${int(annual_fixed_price / 12)}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

    @responses.activate
    @mock_stripe()
    def test_upgrade_server_to_fixed_price_plan_pay_by_invoice(self, *mocks: Mock) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_server_id": f"{self.remote_server.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for demo.example.com set to Zulip Basic."], result
        )

        # Configure fixed-price plan with ID of manually sent invoice.
        sent_invoice_id = "test_sent_invoice_id"
        annual_fixed_price = 1200
        mock_invoice = MagicMock()
        mock_invoice.status = "open"
        mock_invoice.sent_invoice_id = sent_invoice_id
        with mock.patch("stripe.Invoice.retrieve", return_value=mock_invoice):
            result = self.client_post(
                "/activity/remote/support",
                {
                    "remote_server_id": f"{self.remote_server.id}",
                    "fixed_price": annual_fixed_price,
                    "sent_invoice_id": sent_invoice_id,
                },
            )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )
        fixed_price_plan_offer = CustomerPlanOffer.objects.filter(
            status=CustomerPlanOffer.CONFIGURED
        ).first()
        assert fixed_price_plan_offer is not None
        self.assertEqual(fixed_price_plan_offer.tier, CustomerPlanOffer.TIER_SELF_HOSTED_BASIC)
        self.assertEqual(fixed_price_plan_offer.fixed_price, annual_fixed_price * 100)
        self.assertEqual(fixed_price_plan_offer.sent_invoice_id, sent_invoice_id)
        self.assertEqual(fixed_price_plan_offer.get_plan_status_as_text(), "Configured")

        invoice = Invoice.objects.get(stripe_invoice_id=sent_invoice_id)
        self.assertEqual(invoice.status, Invoice.SENT)

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Customer don't need to visit /upgrade to buy plan.
        # In case they visit, we inform them about the mail to which
        # invoice was sent and also display the link for payment.
        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        mock_invoice = MagicMock()
        mock_invoice.hosted_invoice_url = "payments_page_url"
        with time_machine.travel(self.now, tick=False), mock.patch(
            "stripe.Invoice.retrieve", return_value=mock_invoice
        ):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                subdomain="selfhosting",
            )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["payments_page_url", hamlet.delivery_email], result)

        # When customer makes a payment, 'stripe_webhook' handles 'invoice.paid' event.
        stripe_event_id = "stripe_event_id"
        valid_invoice_paid_event_data = {
            "id": stripe_event_id,
            "type": "invoice.paid",
            "api_version": STRIPE_API_VERSION,
            "data": {
                "object": {
                    "object": "invoice",
                    "id": sent_invoice_id,
                    "collection_method": "send_invoice",
                }
            },
        }
        with time_machine.travel(self.now, tick=False):
            result = self.client_post(
                "/stripe/webhook/",
                valid_invoice_paid_event_data,
                content_type="application/json",
            )
            self.assertEqual(result.status_code, 200)

        # Verify that the customer is upgraded after payment.
        customer = self.billing_session.get_customer()
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertEqual(current_plan.fixed_price, annual_fixed_price * 100)
        self.assertIsNone(current_plan.price_per_license)

        invoice.refresh_from_db()
        fixed_price_plan_offer.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.PAID)
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.PROCESSED)

    @responses.activate
    @mock_stripe()
    def test_schedule_server_upgrade_to_fixed_price_business_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Upgrade to fixed-price Zulip Basic plan.
        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertEqual(current_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BASIC)
        self.assertIsNone(current_plan.fixed_price)
        self.assertIsNotNone(current_plan.price_per_license)

        self.logout()
        self.login("iago")

        # Schedule a fixed-price business plan at current plan end_date.
        current_plan_end_date = add_months(self.now, 2)
        current_plan.end_date = current_plan_end_date
        current_plan.save(update_fields=["end_date"])

        self.assertFalse(CustomerPlan.objects.filter(fixed_price__isnull=False).exists())

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_server_id": f"{self.remote_server.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for demo.example.com set to Zulip Business."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_server_id": f"{self.remote_server.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            [
                f"Fixed price Zulip Business plan scheduled to start on {current_plan_end_date.date()}."
            ],
            result,
        )
        current_plan.refresh_from_db()
        self.assertEqual(current_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        self.assertEqual(current_plan.next_invoice_date, current_plan_end_date)
        new_plan = CustomerPlan.objects.filter(fixed_price__isnull=False).first()
        assert new_plan is not None
        self.assertEqual(new_plan.next_invoice_date, current_plan_end_date)
        self.assertEqual(
            new_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )

        # Invoice cron runs and switches plan to BUSINESS
        with time_machine.travel(current_plan_end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()

        current_plan.refresh_from_db()
        self.assertEqual(current_plan.status, CustomerPlan.ENDED)
        self.assertEqual(current_plan.next_invoice_date, None)

        new_plan.refresh_from_db()
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertIsNotNone(new_plan.fixed_price)
        self.assertIsNone(new_plan.price_per_license)

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Visit /billing
        self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=False, confirm_tos=False
        )
        with time_machine.travel(current_plan_end_date + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Business",
            "Annual",
            "March 2, 2013",
            "This is a fixed-price plan",
            "Your plan ends on <strong>March 2, 2013</strong>",
            "You will be contacted by Zulip Sales",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

    @responses.activate
    @mock_stripe()
    def test_schedule_server_legacy_plan_upgrade_to_fixed_price_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Migrate server to legacy plan.
        end_date = add_months(self.now, months=3)
        self.billing_session.migrate_customer_to_legacy_plan(self.now, end_date)

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        customer = self.billing_session.get_customer()
        assert customer is not None
        legacy_plan = get_current_plan_by_customer(customer)
        assert legacy_plan is not None
        self.assertEqual(legacy_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(legacy_plan.next_invoice_date, end_date)

        self.logout()
        self.login("iago")

        # Schedule a fixed-price business plan at current plan end_date.
        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_server_id": f"{self.remote_server.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for demo.example.com set to Zulip Business."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_server_id": f"{self.remote_server.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Business plan."],
            result,
        )
        fixed_price_plan_offer = CustomerPlanOffer.objects.get(customer=customer)
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.CONFIGURED)
        self.assertEqual(fixed_price_plan_offer.tier, CustomerPlanOffer.TIER_SELF_HOSTED_BUSINESS)

        self.logout()
        self.login("hamlet")
        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)

        # Schedule upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(
                remote_server_plan_start_date="billing_cycle_end_date", talk_to_stripe=False
            )

        legacy_plan.refresh_from_db()
        self.assertEqual(legacy_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        fixed_price_plan_offer.refresh_from_db()
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.PROCESSED)

        # Invoice cron runs and switches plan to BUSINESS
        with time_machine.travel(end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()

        legacy_plan.refresh_from_db()
        current_plan = get_current_plan_by_customer(customer)
        assert current_plan is not None
        self.assertEqual(current_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertIsNotNone(current_plan.fixed_price)
        self.assertIsNone(current_plan.price_per_license)
        self.assertEqual(current_plan.next_invoice_date, add_months(end_date, 1))
        self.assertEqual(legacy_plan.status, CustomerPlan.ENDED)
        self.assertEqual(legacy_plan.next_invoice_date, None)

    def test_deactivate_registration_with_push_notification_service(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        billing_base_url = self.billing_session.billing_base_url

        # Get server deactivation confirmation link
        with self.settings(EXTERNAL_HOST="zulipdev.com:9991"):
            confirmation_link = generate_confirmation_link_for_server_deactivation(
                self.remote_server, 10
            )

        # confirmation link takes user to login page
        result = self.client_get(confirmation_link, subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Log in to deactivate registration for"], result)

        # Login redirects to '/deactivate'
        result = self.client_post(
            confirmation_link,
            {"full_name": hamlet.full_name, "tos_consent": "true"},
            subdomain="selfhosting",
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/deactivate/")

        # Deactivate via UI
        result = self.client_get(f"{billing_base_url}/deactivate/", subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["Deactivate registration for", "Deactivate registration"], result
        )

        result = self.client_post(
            f"{billing_base_url}/deactivate/", {"confirmed": "true"}, subdomain="selfhosting"
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["Registration deactivated for", "Your server's registration has been deactivated."],
            result,
        )

        # Verify login fails
        payload = {
            "zulip_org_id": self.remote_server.uuid,
            "zulip_org_key": self.remote_server.api_key,
        }
        result = self.client_post("/serverlogin/", payload, subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Your server registration has been deactivated."], result)

    @responses.activate
    @mock_stripe()
    def test_invoice_initial_remote_server_upgrade(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        server_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        [invoice0] = iter(stripe.Invoice.list(customer=stripe_customer.id))

        [invoice_item0, invoice_item1] = iter(invoice0.lines)
        invoice_item_params = {
            "amount": -2000,
            "description": "$20.00/month new customer discount",
            "quantity": 1,
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item0[key], value)

        invoice_item_params = {
            "amount": server_user_count * 3.5 * 100,
            "description": "Zulip Basic",
            "quantity": server_user_count,
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item1[key], value)

        self.assertEqual(invoice0.total, server_user_count * 3.5 * 100 - 2000)
        self.assertEqual(invoice0.status, "paid")

    @responses.activate
    @mock_stripe()
    def test_invoice_plans_as_needed_server(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        server_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        assert plan.customer.remote_server is not None
        self.assertEqual(plan.next_invoice_date, self.next_month)

        with time_machine.travel(self.now + timedelta(days=2), tick=False):
            for count in range(5):
                do_create_user(
                    f"email - {count}",
                    f"password {count}",
                    hamlet.realm,
                    "name",
                    role=UserProfile.ROLE_MEMBER,
                    acting_user=None,
                )
            server_user_count += 5

        # Data upload was 25 days before the invoice date.
        last_audit_log_upload = self.now + timedelta(days=5)
        with time_machine.travel(last_audit_log_upload, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        invoice_plans_as_needed(self.next_month)
        plan.refresh_from_db()
        self.assertEqual(plan.next_invoice_date, self.next_month)
        self.assertTrue(plan.invoice_overdue_email_sent)

        from django.core.mail import outbox

        messages_count = len(outbox)
        message = outbox[-1]
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "sales@zulip.com")
        self.assertEqual(
            message.subject,
            f"Invoice overdue for {self.billing_session.billing_entity_display_name} due to stale data",
        )
        self.assertIn(
            f"Support URL: {self.billing_session.support_url()}",
            message.body,
        )
        self.assertIn(
            f"Internal billing notice for {self.billing_session.billing_entity_display_name}.",
            message.body,
        )
        self.assertIn("Recent invoice is overdue for payment.", message.body)
        self.assertIn(
            f"Last data upload: {last_audit_log_upload.strftime('%Y-%m-%d')}", message.body
        )

        # Cron runs again, don't send another email to Zulip team.
        invoice_plans_as_needed(self.next_month + timedelta(days=1))
        self.assert_length(outbox, messages_count)

        # Ledger is up-to-date
        with time_machine.travel(self.next_month, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        invoice_plans_as_needed(self.next_month)
        plan.refresh_from_db()
        self.assertEqual(plan.next_invoice_date, add_months(self.next_month, 1))
        self.assertFalse(plan.invoice_overdue_email_sent)

        assert customer.stripe_customer_id
        [invoice0, invoice1] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))

        [invoice_item0, invoice_item1, invoice_item2] = iter(invoice0.lines)
        invoice_item_params = {
            "amount": server_user_count * 3.5 * 100,
            "description": "Zulip Basic - renewal",
            "quantity": server_user_count,
            "period": {
                "start": datetime_to_timestamp(self.next_month),
                "end": datetime_to_timestamp(add_months(self.next_month, 1)),
            },
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item1[key], value)

        invoice_item_params = {
            "description": "Additional license (Jan 4, 2012 - Feb 2, 2012)",
            "quantity": 5,
            "period": {
                "start": datetime_to_timestamp(self.now + timedelta(days=2)),
                "end": datetime_to_timestamp(self.next_month),
            },
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item2[key], value)

        # Verify Zulip team receives mail for the next cycle.
        invoice_plans_as_needed(add_months(self.next_month, 1))
        self.assert_length(outbox, messages_count + 1)

    @responses.activate
    @mock_stripe()
    def test_legacy_plan_ends_on_plan_end_date(self, *mocks: Mock) -> None:
        self.login("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        plan_end_date = add_months(self.now, 3)
        self.billing_session.migrate_customer_to_legacy_plan(self.now, plan_end_date)

        # Legacy plan ends on plan end date.
        customer = self.billing_session.get_customer()
        assert customer is not None
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.assertEqual(plan.end_date, plan_end_date)
        self.assertEqual(plan.next_invoice_date, plan_end_date)
        self.assertEqual(plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(
            self.remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY
        )

        with mock.patch("stripe.Invoice.create") as invoice_create, mock.patch(
            "corporate.lib.stripe.send_email"
        ) as send_email, time_machine.travel(plan_end_date, tick=False):
            invoice_plans_as_needed()
            # Verify that for legacy plan with no next plan scheduled,
            # invoice overdue email is not sent even if the last audit log
            # update was 3 months ago.
            send_email.assert_not_called()
            # The legacy plan is downgraded, no invoice created.
            invoice_create.assert_not_called()

        plan.refresh_from_db()
        self.remote_server.refresh_from_db()
        self.assertEqual(self.remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED)
        self.assertEqual(plan.next_invoice_date, None)
        self.assertEqual(plan.status, CustomerPlan.ENDED)

    @responses.activate
    @mock_stripe()
    def test_invoice_scheduled_upgrade_server_legacy_plan(self, *mocks: Mock) -> None:
        # Upload data
        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Migrate server to legacy plan.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            self.billing_session.migrate_customer_to_legacy_plan(start_date, end_date)

        customer = self.billing_session.get_customer()
        assert customer is not None
        legacy_plan = get_current_plan_by_customer(customer)
        assert legacy_plan is not None
        self.assertEqual(legacy_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(legacy_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(legacy_plan.next_invoice_date, end_date)

        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        # Add card and schedule upgrade
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                remote_server_plan_start_date="billing_cycle_end_date", talk_to_stripe=False
            )
        legacy_plan.refresh_from_db()
        self.assertEqual(legacy_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        new_plan = self.billing_session.get_next_plan(legacy_plan)
        assert new_plan is not None
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertEqual(new_plan.status, CustomerPlan.NEVER_STARTED)
        self.assertEqual(
            new_plan.invoicing_status,
            CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT,
        )
        self.assertEqual(new_plan.next_invoice_date, end_date)
        self.assertEqual(new_plan.billing_cycle_anchor, end_date)

        server_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()
        min_licenses = self.billing_session.min_licenses_for_plan(
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS
        )
        licenses = max(min_licenses, server_user_count)

        with mock.patch("stripe.Invoice.finalize_invoice") as invoice_create, mock.patch(
            "corporate.lib.stripe.send_email"
        ) as send_email, time_machine.travel(end_date, tick=False):
            invoice_plans_as_needed()
            # Verify that for legacy plan with next plan scheduled, invoice
            # overdue email is sent if the last audit log is stale.
            send_email.assert_called()
            invoice_create.assert_not_called()

        with time_machine.travel(end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()
            # 'invoice_plan()' is called with both legacy & new plan, but
            # invoice is created only for new plan. The legacy plan only
            # goes through the end of cycle updates.

        legacy_plan.refresh_from_db()
        new_plan.refresh_from_db()
        self.assertEqual(legacy_plan.status, CustomerPlan.ENDED)
        self.assertEqual(legacy_plan.next_invoice_date, None)
        self.assertEqual(new_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(new_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)
        self.assertEqual(new_plan.next_invoice_date, add_months(end_date, 1))

        [invoice0] = iter(stripe.Invoice.list(customer=stripe_customer.id))

        [invoice_item0, invoice_item1] = iter(invoice0.lines)
        invoice_item_params = {
            "amount": -2000 * 12,
            "description": "$20.00/month new customer discount",
            "quantity": 1,
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item0[key], value)

        invoice_item_params = {
            "amount": licenses * 80 * 100,
            "description": "Zulip Business - renewal",
            "quantity": licenses,
        }
        for key, value in invoice_item_params.items():
            self.assertEqual(invoice_item1[key], value)
