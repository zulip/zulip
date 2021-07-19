import logging
from decimal import Decimal
from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode, urljoin, urlunsplit

import stripe
from django import forms
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from corporate.lib.stripe import (
    DEFAULT_INVOICE_DAYS_UNTIL_DUE,
    MIN_INVOICED_LICENSES,
    STRIPE_PUBLISHABLE_KEY,
    BillingError,
    cents_to_dollar_string,
    do_change_plan_status,
    do_replace_payment_source,
    downgrade_at_the_end_of_billing_cycle,
    downgrade_now_without_creating_additional_invoices,
    get_latest_seat_count,
    is_sponsored_realm,
    make_end_of_cycle_updates_if_needed,
    process_initial_upgrade,
    renewal_amount,
    sign_string,
    start_of_next_billing_cycle,
    stripe_get_customer,
    unsign_string,
    update_license_ledger_for_manual_plan,
    update_sponsorship_status,
    validate_licenses,
)
from corporate.models import (
    CustomerPlan,
    ZulipSponsorshipRequest,
    get_current_plan_by_customer,
    get_current_plan_by_realm,
    get_customer_by_realm,
)
from zerver.decorator import (
    require_billing_access,
    require_organization_member,
    zulip_login_required,
)
from zerver.lib.actions import do_make_user_billing_admin
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.validator import check_int, check_int_in, check_string_in
from zerver.models import Realm, UserProfile, get_org_type_display_name, get_realm

billing_logger = logging.getLogger("corporate.stripe")

VALID_BILLING_MODALITY_VALUES = ["send_invoice", "charge_automatically"]
VALID_BILLING_SCHEDULE_VALUES = ["annual", "monthly"]
VALID_LICENSE_MANAGEMENT_VALUES = ["automatic", "manual"]


def unsign_seat_count(signed_seat_count: str, salt: str) -> int:
    try:
        return int(unsign_string(signed_seat_count, salt))
    except signing.BadSignature:
        raise BillingError("tampered seat count")


def check_upgrade_parameters(
    billing_modality: str,
    schedule: str,
    license_management: Optional[str],
    licenses: Optional[int],
    has_stripe_token: bool,
    seat_count: int,
) -> None:
    if billing_modality not in VALID_BILLING_MODALITY_VALUES:  # nocoverage
        raise BillingError("unknown billing_modality")
    if schedule not in VALID_BILLING_SCHEDULE_VALUES:  # nocoverage
        raise BillingError("unknown schedule")
    if license_management not in VALID_LICENSE_MANAGEMENT_VALUES:  # nocoverage
        raise BillingError("unknown license_management")

    charge_automatically = False
    if billing_modality == "charge_automatically":
        charge_automatically = True
        if not has_stripe_token:
            raise BillingError("autopay with no card")

    validate_licenses(charge_automatically, licenses, seat_count)


# Should only be called if the customer is being charged automatically
def payment_method_string(stripe_customer: stripe.Customer) -> str:
    stripe_source: Optional[Union[stripe.Card, stripe.Source]] = stripe_customer.default_source
    # In case of e.g. an expired card
    if stripe_source is None:  # nocoverage
        return _("No payment method on file")
    if stripe_source.object == "card":
        assert isinstance(stripe_source, stripe.Card)
        return _("{brand} ending in {last4}").format(
            brand=stripe_source.brand,
            last4=stripe_source.last4,
        )
    # There might be one-off stuff we do for a particular customer that
    # would land them here. E.g. by default we don't support ACH for
    # automatic payments, but in theory we could add it for a customer via
    # the Stripe dashboard.
    return _("Unknown payment method. Please contact {email}.").format(
        email=settings.ZULIP_ADMINISTRATOR,
    )  # nocoverage


@require_organization_member
@has_request_variables
def upgrade(
    request: HttpRequest,
    user: UserProfile,
    billing_modality: str = REQ(str_validator=check_string_in(VALID_BILLING_MODALITY_VALUES)),
    schedule: str = REQ(str_validator=check_string_in(VALID_BILLING_SCHEDULE_VALUES)),
    signed_seat_count: str = REQ(),
    salt: str = REQ(),
    license_management: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_LICENSE_MANAGEMENT_VALUES)
    ),
    licenses: Optional[int] = REQ(json_validator=check_int, default=None),
    stripe_token: Optional[str] = REQ(default=None),
) -> HttpResponse:

    try:
        seat_count = unsign_seat_count(signed_seat_count, salt)
        if billing_modality == "charge_automatically" and license_management == "automatic":
            licenses = seat_count
        if billing_modality == "send_invoice":
            schedule = "annual"
            license_management = "manual"
        check_upgrade_parameters(
            billing_modality,
            schedule,
            license_management,
            licenses,
            stripe_token is not None,
            seat_count,
        )
        assert licenses is not None
        automanage_licenses = license_management == "automatic"

        billing_schedule = {"annual": CustomerPlan.ANNUAL, "monthly": CustomerPlan.MONTHLY}[
            schedule
        ]
        process_initial_upgrade(user, licenses, automanage_licenses, billing_schedule, stripe_token)
    except BillingError as e:
        if not settings.TEST_SUITE:  # nocoverage
            billing_logger.warning(
                "BillingError during upgrade: %s. user=%s, realm=%s (%s), billing_modality=%s, "
                "schedule=%s, license_management=%s, licenses=%s, has stripe_token: %s",
                e.error_description,
                user.id,
                user.realm.id,
                user.realm.string_id,
                billing_modality,
                schedule,
                license_management,
                licenses,
                stripe_token is not None,
            )
        raise
    except Exception:
        billing_logger.exception("Uncaught exception in billing:", stack_info=True)
        error_message = BillingError.CONTACT_SUPPORT.format(email=settings.ZULIP_ADMINISTRATOR)
        error_description = "uncaught exception during upgrade"
        raise BillingError(error_description, error_message)
    else:
        return json_success()


@zulip_login_required
def initial_upgrade(request: HttpRequest) -> HttpResponse:
    user = request.user

    if not settings.BILLING_ENABLED or user.is_guest:
        return render(request, "404.html", status=404)

    billing_page_url = reverse(billing_home)

    customer = get_customer_by_realm(user.realm)
    if customer is not None and (
        get_current_plan_by_customer(customer) is not None or customer.sponsorship_pending
    ):
        if request.GET.get("onboarding") is not None:
            billing_page_url = f"{billing_page_url}?onboarding=true"
        return HttpResponseRedirect(billing_page_url)

    if is_sponsored_realm(user.realm):
        return HttpResponseRedirect(billing_page_url)

    percent_off = Decimal(0)
    if customer is not None and customer.default_discount is not None:
        percent_off = customer.default_discount

    seat_count = get_latest_seat_count(user.realm)
    signed_seat_count, salt = sign_string(str(seat_count))
    context: Dict[str, Any] = {
        "realm": user.realm,
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "email": user.delivery_email,
        "seat_count": seat_count,
        "signed_seat_count": signed_seat_count,
        "salt": salt,
        "min_invoiced_licenses": max(seat_count, MIN_INVOICED_LICENSES),
        "default_invoice_days_until_due": DEFAULT_INVOICE_DAYS_UNTIL_DUE,
        "plan": "Zulip Standard",
        "free_trial_days": settings.FREE_TRIAL_DAYS,
        "onboarding": request.GET.get("onboarding") is not None,
        "page_params": {
            "seat_count": seat_count,
            "annual_price": 8000,
            "monthly_price": 800,
            "percent_off": float(percent_off),
        },
        "realm_org_type": user.realm.org_type,
        "sorted_org_types": sorted(
            [
                [org_type_name, org_type]
                for (org_type_name, org_type) in Realm.ORG_TYPES.items()
                if not org_type.get("hidden")
            ],
            key=lambda d: d[1]["display_order"],
        ),
    }
    response = render(request, "corporate/upgrade.html", context=context)
    return response


class SponsorshipRequestForm(forms.Form):
    website = forms.URLField(max_length=ZulipSponsorshipRequest.MAX_ORG_URL_LENGTH)
    organization_type = forms.IntegerField()
    description = forms.CharField(widget=forms.Textarea)


@require_organization_member
@has_request_variables
def sponsorship(
    request: HttpRequest,
    user: UserProfile,
    organization_type: str = REQ("organization-type"),
    website: str = REQ(),
    description: str = REQ(),
) -> HttpResponse:
    realm = user.realm

    requested_by = user.full_name
    user_role = user.get_role_name()

    support_realm_uri = get_realm(settings.STAFF_SUBDOMAIN).uri
    support_url = urljoin(
        support_realm_uri,
        urlunsplit(("", "", reverse("support"), urlencode({"q": realm.string_id}), "")),
    )

    post_data = request.POST.copy()
    # We need to do this because the field name in the template
    # for organization type contains a hyphen and the form expects
    # an underscore.
    post_data.update(organization_type=organization_type)
    form = SponsorshipRequestForm(post_data)

    with transaction.atomic():
        if form.is_valid():
            sponsorship_request = ZulipSponsorshipRequest(
                realm=realm,
                requested_by=user,
                org_website=form.cleaned_data["website"],
                org_description=form.cleaned_data["description"],
                org_type=form.cleaned_data["organization_type"],
            )
            sponsorship_request.save()

            org_type = form.cleaned_data["organization_type"]
            if realm.org_type != org_type:
                realm.org_type = org_type
                realm.save(update_fields=["org_type"])

        update_sponsorship_status(realm, True, acting_user=user)
        do_make_user_billing_admin(user)

    org_type_display_name = get_org_type_display_name(org_type)

    context = {
        "requested_by": requested_by,
        "user_role": user_role,
        "string_id": realm.string_id,
        "support_url": support_url,
        "organization_type": org_type_display_name,
        "website": website,
        "description": description,
    }
    send_email(
        "zerver/emails/sponsorship_request",
        to_emails=[FromAddress.SUPPORT],
        from_name="Zulip sponsorship",
        from_address=FromAddress.tokenized_no_reply_address(),
        reply_to_email=user.delivery_email,
        context=context,
    )

    return json_success()


@zulip_login_required
def billing_home(request: HttpRequest) -> HttpResponse:
    user = request.user
    customer = get_customer_by_realm(user.realm)
    context: Dict[str, Any] = {
        "admin_access": user.has_billing_access,
        "has_active_plan": False,
    }

    if user.realm.plan_type == user.realm.STANDARD_FREE:
        context["is_sponsored"] = True
        return render(request, "corporate/billing.html", context=context)

    if customer is None:
        return HttpResponseRedirect(reverse(initial_upgrade))

    if customer.sponsorship_pending:
        context["sponsorship_pending"] = True
        return render(request, "corporate/billing.html", context=context)

    if not CustomerPlan.objects.filter(customer=customer).exists():
        return HttpResponseRedirect(reverse(initial_upgrade))

    if not user.has_billing_access:
        return render(request, "corporate/billing.html", context=context)

    plan = get_current_plan_by_customer(customer)
    if plan is not None:
        now = timezone_now()
        new_plan, last_ledger_entry = make_end_of_cycle_updates_if_needed(plan, now)
        if last_ledger_entry is not None:
            if new_plan is not None:  # nocoverage
                plan = new_plan
            assert plan is not None  # for mypy
            downgrade_at_end_of_cycle = plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
            switch_to_annual_at_end_of_cycle = (
                plan.status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE
            )
            licenses = last_ledger_entry.licenses
            licenses_at_next_renewal = last_ledger_entry.licenses_at_next_renewal
            seat_count = get_latest_seat_count(user.realm)

            # Should do this in javascript, using the user's timezone
            renewal_date = "{dt:%B} {dt.day}, {dt.year}".format(
                dt=start_of_next_billing_cycle(plan, now)
            )
            renewal_cents = renewal_amount(plan, now)
            charge_automatically = plan.charge_automatically
            assert customer.stripe_customer_id is not None  # for mypy
            stripe_customer = stripe_get_customer(customer.stripe_customer_id)
            if charge_automatically:
                payment_method = payment_method_string(stripe_customer)
            else:
                payment_method = "Billed by invoice"

            context.update(
                plan_name=plan.name,
                has_active_plan=True,
                free_trial=plan.is_free_trial(),
                downgrade_at_end_of_cycle=downgrade_at_end_of_cycle,
                automanage_licenses=plan.automanage_licenses,
                switch_to_annual_at_end_of_cycle=switch_to_annual_at_end_of_cycle,
                licenses=licenses,
                licenses_at_next_renewal=licenses_at_next_renewal,
                seat_count=seat_count,
                renewal_date=renewal_date,
                renewal_amount=cents_to_dollar_string(renewal_cents),
                payment_method=payment_method,
                charge_automatically=charge_automatically,
                publishable_key=STRIPE_PUBLISHABLE_KEY,
                stripe_email=stripe_customer.email,
                CustomerPlan=CustomerPlan,
                onboarding=request.GET.get("onboarding") is not None,
            )

    return render(request, "corporate/billing.html", context=context)


@require_billing_access
@has_request_variables
def update_plan(
    request: HttpRequest,
    user: UserProfile,
    status: Optional[int] = REQ(
        "status",
        json_validator=check_int_in(
            [
                CustomerPlan.ACTIVE,
                CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
                CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE,
                CustomerPlan.ENDED,
            ]
        ),
        default=None,
    ),
    licenses: Optional[int] = REQ("licenses", json_validator=check_int, default=None),
    licenses_at_next_renewal: Optional[int] = REQ(
        "licenses_at_next_renewal", json_validator=check_int, default=None
    ),
) -> HttpResponse:
    plan = get_current_plan_by_realm(user.realm)
    assert plan is not None  # for mypy

    new_plan, last_ledger_entry = make_end_of_cycle_updates_if_needed(plan, timezone_now())
    if new_plan is not None:
        raise JsonableError(
            _("Unable to update the plan. The plan has been expired and replaced with a new plan.")
        )

    if last_ledger_entry is None:
        raise JsonableError(_("Unable to update the plan. The plan has ended."))

    if status is not None:
        if status == CustomerPlan.ACTIVE:
            assert plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
            do_change_plan_status(plan, status)
        elif status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE:
            assert plan.status == CustomerPlan.ACTIVE
            downgrade_at_the_end_of_billing_cycle(user.realm)
        elif status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE:
            assert plan.billing_schedule == CustomerPlan.MONTHLY
            assert plan.status == CustomerPlan.ACTIVE
            assert plan.fixed_price is None
            do_change_plan_status(plan, status)
        elif status == CustomerPlan.ENDED:
            assert plan.is_free_trial()
            downgrade_now_without_creating_additional_invoices(user.realm)
        return json_success()

    if licenses is not None:
        if plan.automanage_licenses:
            raise JsonableError(
                _(
                    "Unable to update licenses manually. Your plan is on automatic license management."
                )
            )
        if last_ledger_entry.licenses == licenses:
            raise JsonableError(
                _(
                    "Your plan is already on {licenses} licenses in the current billing period."
                ).format(licenses=licenses)
            )
        if last_ledger_entry.licenses > licenses:
            raise JsonableError(
                _("You cannot decrease the licenses in the current billing period.").format(
                    licenses=licenses
                )
            )
        validate_licenses(plan.charge_automatically, licenses, get_latest_seat_count(user.realm))
        update_license_ledger_for_manual_plan(plan, timezone_now(), licenses=licenses)
        return json_success()

    if licenses_at_next_renewal is not None:
        if plan.automanage_licenses:
            raise JsonableError(
                _(
                    "Unable to update licenses manually. Your plan is on automatic license management."
                )
            )
        if last_ledger_entry.licenses_at_next_renewal == licenses_at_next_renewal:
            raise JsonableError(
                _(
                    "Your plan is already scheduled to renew with {licenses_at_next_renewal} licenses."
                ).format(licenses_at_next_renewal=licenses_at_next_renewal)
            )
        validate_licenses(
            plan.charge_automatically,
            licenses_at_next_renewal,
            get_latest_seat_count(user.realm),
        )
        update_license_ledger_for_manual_plan(
            plan, timezone_now(), licenses_at_next_renewal=licenses_at_next_renewal
        )
        return json_success()

    raise JsonableError(_("Nothing to change."))


@require_billing_access
@has_request_variables
def replace_payment_source(
    request: HttpRequest,
    user: UserProfile,
    stripe_token: str = REQ(),
) -> HttpResponse:
    do_replace_payment_source(user, stripe_token, pay_invoices=True)
    return json_success()
