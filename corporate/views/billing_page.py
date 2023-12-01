import logging
from typing import Any, Dict, Optional

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from corporate.lib.stripe import RealmBillingSession, UpdatePlanRequest
from corporate.models import CustomerPlan, get_customer_by_realm
from zerver.decorator import require_billing_access, zulip_login_required
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_int, check_int_in, check_string
from zerver.models import UserProfile

billing_logger = logging.getLogger("corporate.stripe")


@zulip_login_required
@has_request_variables
def billing_page(
    request: HttpRequest,
    success_message: str = REQ(default="", str_validator=check_string),
) -> HttpResponse:
    user = request.user
    assert user.is_authenticated

    # BUG: This should pass the acting_user; this is just working
    # around that make_end_of_cycle_updates_if_needed doesn't do audit
    # logging not using the session user properly.
    billing_session = RealmBillingSession(user=None, realm=user.realm)

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
        if not billing_session.on_paid_plan():
            return HttpResponseRedirect(reverse("sponsorship_request"))
        # If the realm is on a paid plan, show the sponsorship pending message
        context["sponsorship_pending"] = True

    if user.realm.plan_type == user.realm.PLAN_TYPE_LIMITED:
        return HttpResponseRedirect(reverse("plans"))

    if customer is None:
        return HttpResponseRedirect(reverse("upgrade_page"))

    if not CustomerPlan.objects.filter(customer=customer).exists():
        return HttpResponseRedirect(reverse("upgrade_page"))

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
                CustomerPlan.FREE_TRIAL,
                CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
                CustomerPlan.ENDED,
            ]
        ),
        default=None,
    ),
    licenses: Optional[int] = REQ("licenses", json_validator=check_int, default=None),
    licenses_at_next_renewal: Optional[int] = REQ(
        "licenses_at_next_renewal", json_validator=check_int, default=None
    ),
    schedule: Optional[int] = REQ("schedule", json_validator=check_int, default=None),
) -> HttpResponse:
    update_plan_request = UpdatePlanRequest(
        status=status,
        licenses=licenses,
        licenses_at_next_renewal=licenses_at_next_renewal,
        schedule=schedule,
    )
    billing_session = RealmBillingSession(user=user)
    billing_session.do_update_plan(update_plan_request)
    return json_success(request)
