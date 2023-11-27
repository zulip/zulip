import logging
from typing import Any, Dict, Optional

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from corporate.lib.stripe import RealmBillingSession, UpdatePlanRequest
from corporate.models import CustomerPlan, get_current_plan_by_customer, get_customer_by_realm
from zerver.decorator import require_billing_access, zulip_login_required
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_int, check_int_in, check_string
from zerver.models import Realm, UserProfile

billing_logger = logging.getLogger("corporate.stripe")

PAID_PLANS = [
    Realm.PLAN_TYPE_STANDARD,
    Realm.PLAN_TYPE_PLUS,
]


def is_realm_on_paid_plan(realm: Realm) -> bool:
    return realm.plan_type in PAID_PLANS


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
        if is_realm_on_paid_plan(user.realm):
            return HttpResponseRedirect(reverse("billing_home"))

        context["is_sponsorship_pending"] = True

    if user.realm.plan_type == user.realm.PLAN_TYPE_STANDARD_FREE:
        context["is_sponsored"] = True

    if customer is not None:
        plan = get_current_plan_by_customer(customer)
        if plan is not None:
            context["plan_name"] = plan.name
            context["free_trial"] = plan.is_free_trial()
        # We don't create CustomerPlan objects for fully sponsored realms via support page.
        elif user.realm.plan_type == Realm.PLAN_TYPE_STANDARD_FREE:
            context["plan_name"] = "Zulip Cloud Standard"
        else:
            context["plan_name"] = "Zulip Cloud Free"

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

    customer = get_customer_by_realm(user.realm)
    if customer is not None and customer.sponsorship_pending:
        # Don't redirect to sponsorship page if the realm is on a paid plan
        if not is_realm_on_paid_plan(user.realm):
            return HttpResponseRedirect(reverse("sponsorship_request"))
        # If the realm is on a paid plan, show the sponsorship pending message
        # TODO: Add a sponsorship pending message to the billing page
        context["sponsorship_pending"] = True

    if user.realm.plan_type == user.realm.PLAN_TYPE_LIMITED:
        return HttpResponseRedirect(reverse("plans"))

    if customer is None:
        from corporate.views.upgrade import upgrade_page

        return HttpResponseRedirect(reverse(upgrade_page))

    if not CustomerPlan.objects.filter(customer=customer).exists():
        from corporate.views.upgrade import upgrade_page

        return HttpResponseRedirect(reverse(upgrade_page))

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
    update_plan_request = UpdatePlanRequest(
        status=status,
        licenses=licenses,
        licenses_at_next_renewal=licenses_at_next_renewal,
    )
    billing_session = RealmBillingSession(user=user)
    billing_session.do_update_plan(update_plan_request)
    return json_success(request)
