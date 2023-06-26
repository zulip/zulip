from typing import Any, Dict, Optional, Union

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import CASCADE, Q

from zerver.models import Realm, UserProfile
from zilencer.models import RemoteZulipServer


class Customer(models.Model):
    """
    This model primarily serves to connect a Realm with
    the corresponding Stripe customer object for payment purposes
    and the active plan, if any.
    """

    realm = models.OneToOneField(Realm, on_delete=CASCADE, null=True)
    remote_server = models.OneToOneField(RemoteZulipServer, on_delete=CASCADE, null=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, unique=True)
    sponsorship_pending = models.BooleanField(default=False)
    # A percentage, like 85.
    default_discount = models.DecimalField(decimal_places=4, max_digits=7, null=True)
    # Some non-profit organizations on manual license management pay
    # only for their paid employees.  We don't prevent these
    # organizations from adding more users than the number of licenses
    # they purchased.
    exempt_from_license_number_check = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(realm__isnull=False) ^ Q(remote_server__isnull=False),
                name="cloud_xor_self_hosted",
            )
        ]

    def __str__(self) -> str:
        return f"{self.realm!r} {self.stripe_customer_id}"


def get_customer_by_realm(realm: Realm) -> Optional[Customer]:
    return Customer.objects.filter(realm=realm).first()


class Event(models.Model):
    stripe_event_id = models.CharField(max_length=255)

    type = models.CharField(max_length=255)

    RECEIVED = 1
    EVENT_HANDLER_STARTED = 30
    EVENT_HANDLER_FAILED = 40
    EVENT_HANDLER_SUCCEEDED = 50
    status = models.SmallIntegerField(default=RECEIVED)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")

    handler_error = models.JSONField(default=None, null=True)

    def get_event_handler_details_as_dict(self) -> Dict[str, Any]:
        details_dict = {}
        details_dict["status"] = {
            Event.RECEIVED: "not_started",
            Event.EVENT_HANDLER_STARTED: "started",
            Event.EVENT_HANDLER_FAILED: "failed",
            Event.EVENT_HANDLER_SUCCEEDED: "succeeded",
        }[self.status]
        if self.handler_error:
            details_dict["error"] = self.handler_error
        return details_dict


def get_last_associated_event_by_type(
    content_object: Union["PaymentIntent", "Session"], event_type: str
) -> Optional[Event]:
    content_type = ContentType.objects.get_for_model(type(content_object))
    return Event.objects.filter(
        content_type=content_type, object_id=content_object.id, type=event_type
    ).last()


class Session(models.Model):
    customer = models.ForeignKey(Customer, on_delete=CASCADE)
    stripe_session_id = models.CharField(max_length=255, unique=True)
    payment_intent = models.ForeignKey("PaymentIntent", null=True, on_delete=CASCADE)

    UPGRADE_FROM_BILLING_PAGE = 1
    RETRY_UPGRADE_WITH_ANOTHER_PAYMENT_METHOD = 10
    FREE_TRIAL_UPGRADE_FROM_BILLING_PAGE = 20
    FREE_TRIAL_UPGRADE_FROM_ONBOARDING_PAGE = 30
    CARD_UPDATE_FROM_BILLING_PAGE = 40
    type = models.SmallIntegerField()

    CREATED = 1
    COMPLETED = 10
    status = models.SmallIntegerField(default=CREATED)

    def get_status_as_string(self) -> str:
        return {Session.CREATED: "created", Session.COMPLETED: "completed"}[self.status]

    def get_type_as_string(self) -> str:
        return {
            Session.UPGRADE_FROM_BILLING_PAGE: "upgrade_from_billing_page",
            Session.RETRY_UPGRADE_WITH_ANOTHER_PAYMENT_METHOD: "retry_upgrade_with_another_payment_method",
            Session.FREE_TRIAL_UPGRADE_FROM_BILLING_PAGE: "free_trial_upgrade_from_billing_page",
            Session.FREE_TRIAL_UPGRADE_FROM_ONBOARDING_PAGE: "free_trial_upgrade_from_onboarding_page",
            Session.CARD_UPDATE_FROM_BILLING_PAGE: "card_update_from_billing_page",
        }[self.type]

    def to_dict(self) -> Dict[str, Any]:
        session_dict: Dict[str, Any] = {}

        session_dict["status"] = self.get_status_as_string()
        session_dict["type"] = self.get_type_as_string()
        if self.payment_intent:
            session_dict["stripe_payment_intent_id"] = self.payment_intent.stripe_payment_intent_id
        event = self.get_last_associated_event()
        if event is not None:
            session_dict["event_handler"] = event.get_event_handler_details_as_dict()
        return session_dict

    def get_last_associated_event(self) -> Optional[Event]:
        if self.status == Session.CREATED:
            return None
        return get_last_associated_event_by_type(self, "checkout.session.completed")


class PaymentIntent(models.Model):
    customer = models.ForeignKey(Customer, on_delete=CASCADE)
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True)

    REQUIRES_PAYMENT_METHOD = 1
    REQUIRES_CONFIRMATION = 20
    REQUIRES_ACTION = 30
    PROCESSING = 40
    REQUIRES_CAPTURE = 50
    CANCELLED = 60
    SUCCEEDED = 70

    status = models.SmallIntegerField()
    last_payment_error = models.JSONField(default=None, null=True)

    @classmethod
    def get_status_integer_from_status_text(cls, status_text: str) -> int:
        return getattr(cls, status_text.upper())

    def get_status_as_string(self) -> str:
        return {
            PaymentIntent.REQUIRES_PAYMENT_METHOD: "requires_payment_method",
            PaymentIntent.REQUIRES_CONFIRMATION: "requires_confirmation",
            PaymentIntent.REQUIRES_ACTION: "requires_action",
            PaymentIntent.PROCESSING: "processing",
            PaymentIntent.REQUIRES_CAPTURE: "requires_capture",
            PaymentIntent.CANCELLED: "cancelled",
            PaymentIntent.SUCCEEDED: "succeeded",
        }[self.status]

    def get_last_associated_event(self) -> Optional[Event]:
        if self.status == PaymentIntent.SUCCEEDED:
            event_type = "payment_intent.succeeded"
        elif self.status == PaymentIntent.REQUIRES_PAYMENT_METHOD:
            event_type = "payment_intent.payment_failed"
        else:
            return None
        return get_last_associated_event_by_type(self, event_type)

    def to_dict(self) -> Dict[str, Any]:
        payment_intent_dict: Dict[str, Any] = {}
        payment_intent_dict["status"] = self.get_status_as_string()
        event = self.get_last_associated_event()
        if self.last_payment_error:
            payment_intent_dict["last_payment_error"] = self.last_payment_error
        if event is not None:
            payment_intent_dict["event_handler"] = event.get_event_handler_details_as_dict()
        return payment_intent_dict


class CustomerPlan(models.Model):
    """
    This is for storing most of the fiddly details
    of the customer's plan.
    """

    # A customer can only have one ACTIVE plan, but old, inactive plans
    # are preserved to allow auditing - so there can be multiple
    # CustomerPlan objects pointing to one Customer.
    customer = models.ForeignKey(Customer, on_delete=CASCADE)

    automanage_licenses = models.BooleanField(default=False)
    charge_automatically = models.BooleanField(default=False)

    # Both of these are in cents. Exactly one of price_per_license or
    # fixed_price should be set. fixed_price is only for manual deals, and
    # can't be set via the self-serve billing system.
    price_per_license = models.IntegerField(null=True)
    fixed_price = models.IntegerField(null=True)

    # Discount that was applied. For display purposes only.
    discount = models.DecimalField(decimal_places=4, max_digits=6, null=True)

    # Initialized with the time of plan creation. Used for calculating
    # start of next billing cycle, next invoice date etc. This value
    # should never be modified. The only exception is when we change
    # the status of the plan from free trial to active and reset the
    # billing_cycle_anchor.
    billing_cycle_anchor = models.DateTimeField()

    ANNUAL = 1
    MONTHLY = 2
    billing_schedule = models.SmallIntegerField()

    # The next date the billing system should go through ledger
    # entries and create invoices for additional users or plan
    # renewal. Since we use a daily cron job for invoicing, the
    # invoice will be generated the first time the cron job runs after
    # next_invoice_date.
    next_invoice_date = models.DateTimeField(db_index=True, null=True)

    # On next_invoice_date, we go through ledger entries that were
    # created after invoiced_through and process them by generating
    # invoices for any additional users and/or plan renewal. Once the
    # invoice is generated, we update the value of invoiced_through
    # and set it to the last ledger entry we processed.
    invoiced_through = models.ForeignKey(
        "LicenseLedger", null=True, on_delete=CASCADE, related_name="+"
    )
    end_date = models.DateTimeField(null=True)

    DONE = 1
    STARTED = 2
    INITIAL_INVOICE_TO_BE_SENT = 3
    # This status field helps ensure any errors encountered during the
    # invoicing process do not leave our invoicing system in a broken
    # state.
    invoicing_status = models.SmallIntegerField(default=DONE)

    STANDARD = 1
    PLUS = 2  # not available through self-serve signup
    ENTERPRISE = 10
    tier = models.SmallIntegerField()

    ACTIVE = 1
    DOWNGRADE_AT_END_OF_CYCLE = 2
    FREE_TRIAL = 3
    SWITCH_TO_ANNUAL_AT_END_OF_CYCLE = 4
    SWITCH_NOW_FROM_STANDARD_TO_PLUS = 5
    # "Live" plans should have a value < LIVE_STATUS_THRESHOLD.
    # There should be at most one live plan per customer.
    LIVE_STATUS_THRESHOLD = 10
    ENDED = 11
    NEVER_STARTED = 12
    status = models.SmallIntegerField(default=ACTIVE)

    # TODO maybe override setattr to ensure billing_cycle_anchor, etc
    # are immutable.

    @property
    def name(self) -> str:
        return {
            CustomerPlan.STANDARD: "Zulip Cloud Standard",
            CustomerPlan.PLUS: "Zulip Plus",
            CustomerPlan.ENTERPRISE: "Zulip Enterprise",
        }[self.tier]

    def get_plan_status_as_text(self) -> str:
        return {
            self.ACTIVE: "Active",
            self.DOWNGRADE_AT_END_OF_CYCLE: "Scheduled for downgrade at end of cycle",
            self.FREE_TRIAL: "Free trial",
            self.ENDED: "Ended",
            self.NEVER_STARTED: "Never started",
        }[self.status]

    def licenses(self) -> int:
        ledger_entry = LicenseLedger.objects.filter(plan=self).order_by("id").last()
        assert ledger_entry is not None
        return ledger_entry.licenses

    def licenses_at_next_renewal(self) -> Optional[int]:
        if self.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE:
            return None
        ledger_entry = LicenseLedger.objects.filter(plan=self).order_by("id").last()
        assert ledger_entry is not None
        return ledger_entry.licenses_at_next_renewal

    def is_free_trial(self) -> bool:
        return self.status == CustomerPlan.FREE_TRIAL


def get_current_plan_by_customer(customer: Customer) -> Optional[CustomerPlan]:
    return CustomerPlan.objects.filter(
        customer=customer, status__lt=CustomerPlan.LIVE_STATUS_THRESHOLD
    ).first()


def get_current_plan_by_realm(realm: Realm) -> Optional[CustomerPlan]:
    customer = get_customer_by_realm(realm)
    if customer is None:
        return None
    return get_current_plan_by_customer(customer)


class LicenseLedger(models.Model):
    """
    This table's purpose is to store the current, and historical,
    count of "seats" purchased by the organization.

    Because we want to keep historical data, when the purchased
    seat count changes, a new LicenseLedger object is created,
    instead of updating the old one. This lets us preserve
    the entire history of how the seat count changes, which is
    important for analytics as well as auditing and debugging
    in case of issues.
    """

    plan = models.ForeignKey(CustomerPlan, on_delete=CASCADE)

    # Also True for the initial upgrade.
    is_renewal = models.BooleanField(default=False)

    event_time = models.DateTimeField()

    # The number of licenses ("seats") purchased by the the organization at the time of ledger
    # entry creation. Normally, to add a user the organization needs at least one spare license.
    # Once a license is purchased, it is valid till the end of the billing period, irrespective
    # of whether the license is used or not. So the value of licenses will never decrease for
    # subsequent LicenseLedger entries in the same billing period.
    licenses = models.IntegerField()

    # The number of licenses the organization needs in the next billing cycle. The value of
    # licenses_at_next_renewal can increase or decrease for subsequent LicenseLedger entries in
    # the same billing period. For plans on automatic license management this value is usually
    # equal to the number of activated users in the organization.
    licenses_at_next_renewal = models.IntegerField(null=True)


class ZulipSponsorshipRequest(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    requested_by = models.ForeignKey(UserProfile, on_delete=CASCADE)

    org_type = models.PositiveSmallIntegerField(
        default=Realm.ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
    )

    MAX_ORG_URL_LENGTH: int = 200
    org_website = models.URLField(max_length=MAX_ORG_URL_LENGTH, blank=True, null=True)

    org_description = models.TextField(default="")
