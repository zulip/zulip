import contextlib
from dataclasses import dataclass
from typing import Any, Optional

import stripe
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from corporate.lib.stripe import RealmBillingSession, add_months
from corporate.models import Customer, CustomerPlan, LicenseLedger
from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import do_create_user
from zerver.actions.streams import bulk_add_subscriptions
from zerver.apps import flush_cache
from zerver.lib.streams import create_stream_if_needed
from zerver.models import Realm, UserProfile, get_realm
from zproject.config import get_secret


@dataclass
class CustomerProfile:
    unique_id: str
    billing_schedule: int = CustomerPlan.ANNUAL
    tier: Optional[int] = None
    automanage_licenses: bool = False
    status: int = CustomerPlan.ACTIVE
    sponsorship_pending: bool = False
    is_sponsored: bool = False
    card: str = ""
    charge_automatically: bool = True


class Command(BaseCommand):
    help = "Populate database with different types of realms that can exist."

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        # Create a realm for each plan type

        customer_profiles = [
            # NOTE: The unique_id has to be less than 40 characters.
            CustomerProfile(unique_id="sponsorship-pending", sponsorship_pending=True),
            CustomerProfile(
                unique_id="annual-free",
                billing_schedule=CustomerPlan.ANNUAL,
            ),
            CustomerProfile(
                unique_id="annual-standard",
                billing_schedule=CustomerPlan.ANNUAL,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
            ),
            CustomerProfile(
                unique_id="annual-plus",
                billing_schedule=CustomerPlan.ANNUAL,
                tier=CustomerPlan.TIER_CLOUD_PLUS,
            ),
            CustomerProfile(
                unique_id="monthly-free",
                billing_schedule=CustomerPlan.MONTHLY,
            ),
            CustomerProfile(
                unique_id="monthly-standard",
                billing_schedule=CustomerPlan.MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
            ),
            CustomerProfile(
                unique_id="monthly-plus",
                billing_schedule=CustomerPlan.MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_PLUS,
            ),
            CustomerProfile(
                unique_id="downgrade-end-of-cycle",
                billing_schedule=CustomerPlan.MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
            ),
            CustomerProfile(
                unique_id="standard-automanage-licenses",
                billing_schedule=CustomerPlan.MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                automanage_licenses=True,
            ),
            CustomerProfile(
                unique_id="standard-automatic-card",
                billing_schedule=CustomerPlan.MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                card="pm_card_visa",
            ),
            CustomerProfile(
                unique_id="standard-invoice-payment",
                billing_schedule=CustomerPlan.MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                charge_automatically=False,
            ),
            CustomerProfile(
                unique_id="standard-switch-to-annual-eoc",
                billing_schedule=CustomerPlan.MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE,
            ),
            CustomerProfile(
                unique_id="sponsored",
                is_sponsored=True,
                billing_schedule=CustomerPlan.MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
            ),
            CustomerProfile(
                unique_id="free-trial",
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
            ),
        ]

        # Create a realm for each customer profile
        for customer_profile in customer_profiles:
            unique_id = customer_profile.unique_id
            if customer_profile.tier is None:
                plan_type = Realm.PLAN_TYPE_LIMITED
            elif (
                customer_profile.tier == CustomerPlan.TIER_CLOUD_STANDARD
                and customer_profile.is_sponsored
            ):
                plan_type = Realm.PLAN_TYPE_STANDARD_FREE
            elif customer_profile.tier == CustomerPlan.TIER_CLOUD_STANDARD:
                plan_type = Realm.PLAN_TYPE_STANDARD
            elif customer_profile.tier == CustomerPlan.TIER_CLOUD_PLUS:
                plan_type = Realm.PLAN_TYPE_PLUS
            else:
                raise AssertionError("Unexpected tier!")
            plan_name = Realm.ALL_PLAN_TYPES[plan_type]

            # Delete existing realm with this name
            with contextlib.suppress(Realm.DoesNotExist):
                get_realm(unique_id).delete()
                # Because we just deleted a bunch of objects in the database
                # directly (rather than deleting individual objects in Django,
                # in which case our post_save hooks would have flushed the
                # individual objects from memcached for us), we need to flush
                # memcached in order to ensure deleted objects aren't still
                # present in the memcached cache.
                flush_cache(None)

            realm = do_create_realm(
                string_id=unique_id,
                name=unique_id,
                description=unique_id,
                plan_type=plan_type,
            )

            # Create a user with billing access
            full_name = f"{plan_name}-admin"
            email = f"{full_name}@zulip.com"
            user = do_create_user(
                email,
                full_name,
                realm,
                full_name,
                role=UserProfile.ROLE_REALM_OWNER,
                acting_user=None,
            )

            stream, _ = create_stream_if_needed(
                realm,
                "all",
            )

            bulk_add_subscriptions(realm, [stream], [user], acting_user=None)

            if customer_profile.sponsorship_pending:
                customer = Customer.objects.create(
                    realm=realm,
                    sponsorship_pending=customer_profile.sponsorship_pending,
                )
                continue

            if customer_profile.tier is None:
                continue

            billing_session = RealmBillingSession(user)
            customer = billing_session.update_or_create_stripe_customer()
            assert customer.stripe_customer_id is not None

            # Add a test card to the customer.
            if customer_profile.card:
                # Set the Stripe API key
                stripe.api_key = get_secret("stripe_secret_key")

                # Create a card payment method and attach it to the customer
                payment_method = stripe.PaymentMethod.create(
                    type="card",
                    card={"token": "tok_visa"},
                )

                # Attach the payment method to the customer
                stripe.PaymentMethod.attach(payment_method.id, customer=customer.stripe_customer_id)

                # Set the default payment method for the customer
                stripe.Customer.modify(
                    customer.stripe_customer_id,
                    invoice_settings={"default_payment_method": payment_method.id},
                )

            months = 12
            if customer_profile.billing_schedule == CustomerPlan.MONTHLY:
                months = 1
            next_invoice_date = add_months(timezone_now(), months)

            customer_plan = CustomerPlan.objects.create(
                customer=customer,
                billing_cycle_anchor=timezone_now(),
                billing_schedule=customer_profile.billing_schedule,
                tier=customer_profile.tier,
                price_per_license=1200,
                automanage_licenses=customer_profile.automanage_licenses,
                status=customer_profile.status,
                charge_automatically=customer_profile.charge_automatically,
                next_invoice_date=next_invoice_date,
            )

            LicenseLedger.objects.create(
                licenses=10,
                licenses_at_next_renewal=10,
                event_time=timezone_now(),
                is_renewal=True,
                plan=customer_plan,
            )
