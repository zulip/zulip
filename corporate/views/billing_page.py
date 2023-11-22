import logging
from typing import Any, Dict, Optional

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from corporate.lib.stripe import (
    RealmBillingSession,
    do_change_plan_status,
    downgrade_at_the_end_of_billing_cycle,
    downgrade_now_without_creating_additional_invoices,
    get_latest_seat_count,
    update_license_ledger_for_manual_plan,
    validate_licenses,
)
from corporate.models import CustomerPlan, get_current_plan_by_realm, get_customer_by_realm
from zerver.decorator import require_billing_access, zulip_login_required
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_int, check_int_in, check_string
from zerver.models import Realm, UserProfile

billing_logger = logging.getLogger("corporate.stripe")


def add_sponsorship_info_to_context(context: Dict[str, Any], user_profile: UserProfile) -> None:
    def key_helper(d: Any) -> int:
        return d[1]["display_order"]

    context.update(
        realm_org_type=user_profile.realm.org_type,
        sorted_org_types=sorted(
            (
                [org_type_name, org_type]
                for (org_type_name, org_type) in Realm.ORG_TYPES.items()
                if not org_type.get("hidden")
            ),
            key=key_helper,
        ),
    )


@zulip_login_required
@has_request_variables
def sponsorship_request(request: HttpRequest) -> HttpResponse:
    user = request.user
    assert user.is_authenticated
    context: Dict[str, Any] = {}

    customer = get_customer_by_realm(user.realm)
    if customer is not None and customer.sponsorship_pending:
        context["is_sponsorship_pending"] = True

    if user.realm.plan_type == user.realm.PLAN_TYPE_STANDARD_FREE:
        context["is_sponsored"] = True

    add_sponsorship_info_to_context(context, user)
    return render(request, "corporate/sponsorship.html", context=context)


@zulip_login_required
@has_request_variables
def billing_home(
    request: HttpRequest,
    success_message: str = REQ(default="", str_validator=check_string),
) -> HttpResponse:
    user = request.user
    assert user.is_authenticated

    context: Dict[str, Any] = {
        "admin_access": user.has_billing_access,
        "has_active_plan": False,
        "org_name": user.realm.name,
    }

    if not user.has_billing_access:
        return render(request, "corporate/billing.html", context=context)

    if user.realm.plan_type == user.realm.PLAN_TYPE_STANDARD_FREE:
        return HttpResponseRedirect(reverse("sponsorship_request"))

    PAID_PLANS = [
        Realm.PLAN_TYPE_STANDARD,
        Realm.PLAN_TYPE_PLUS,
    ]

    customer = get_customer_by_realm(user.realm)
    if customer is not None and customer.sponsorship_pending:
        # Don't redirect to sponsorship page if the realm is on a paid plan
        if user.realm.plan_type not in PAID_PLANS:
            return HttpResponseRedirect(reverse("sponsorship_request"))
        # If the realm is on a paid plan, show the sponsorship pending message
        # TODO: Add a sponsorship pending message to the billing page
        context["sponsorship_pending"] = True

    if user.realm.plan_type == user.realm.PLAN_TYPE_LIMITED:
        return HttpResponseRedirect(reverse("plans"))

    if customer is None:
        from corporate.views.upgrade import initial_upgrade

        return HttpResponseRedirect(reverse(initial_upgrade))

    if not CustomerPlan.objects.filter(customer=customer).exists():
        from corporate.views.upgrade import initial_upgrade

        return HttpResponseRedirect(reverse(initial_upgrade))

    billing_session = RealmBillingSession(user=None, realm=user.realm)
    main_context = billing_session.get_billing_page_context()
    if main_context:
        context.update(main_context)
        context["success_message"] = success_message

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
                CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE,
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

    realm = plan.customer.realm
    billing_session = RealmBillingSession(user=None, realm=realm)
    new_plan, last_ledger_entry = billing_session.make_end_of_cycle_updates_if_needed(
        plan, timezone_now()
    )
    if new_plan is not None:
        raise JsonableError(
            _("Unable to update the plan. The plan has been expired and replaced with a new plan.")
        )

    if last_ledger_entry is None:
        raise JsonableError(_("Unable to update the plan. The plan has ended."))

    if status is not None:
        if status == CustomerPlan.ACTIVE:
            assert plan.status < CustomerPlan.LIVE_STATUS_THRESHOLD
            do_change_plan_status(plan, status)
        elif status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE:
            assert plan.status < CustomerPlan.LIVE_STATUS_THRESHOLD
            downgrade_at_the_end_of_billing_cycle(user.realm)
        elif status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE:
            assert plan.billing_schedule == CustomerPlan.MONTHLY
            assert plan.status < CustomerPlan.LIVE_STATUS_THRESHOLD
            # Customer needs to switch to an active plan first to avoid unexpected behavior.
            assert plan.status != CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
            assert plan.fixed_price is None
            do_change_plan_status(plan, status)
        elif status == CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE:
            assert plan.billing_schedule == CustomerPlan.ANNUAL
            assert plan.status < CustomerPlan.LIVE_STATUS_THRESHOLD
            # Customer needs to switch to an active plan first to avoid unexpected behavior.
            assert plan.status != CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
            assert plan.fixed_price is None
            do_change_plan_status(plan, status)
        elif status == CustomerPlan.ENDED:
            assert plan.is_free_trial()
            downgrade_now_without_creating_additional_invoices(user.realm)
        return json_success(request)

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
                _("You cannot decrease the licenses in the current billing period.")
            )
        validate_licenses(
            plan.charge_automatically,
            licenses,
            get_latest_seat_count(user.realm),
            plan.customer.exempt_from_license_number_check,
        )
        update_license_ledger_for_manual_plan(plan, timezone_now(), licenses=licenses)
        return json_success(request)

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
            plan.customer.exempt_from_license_number_check,
        )
        update_license_ledger_for_manual_plan(
            plan, timezone_now(), licenses_at_next_renewal=licenses_at_next_renewal
        )
        return json_success(request)

    raise JsonableError(_("Nothing to change."))
