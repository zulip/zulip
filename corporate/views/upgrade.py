import logging
from decimal import Decimal
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urljoin, urlunsplit

from django import forms
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from corporate.lib.stripe import (
    DEFAULT_INVOICE_DAYS_UNTIL_DUE,
    MIN_INVOICED_LICENSES,
    STRIPE_PUBLISHABLE_KEY,
    BillingError,
    get_latest_seat_count,
    is_sponsored_realm,
    process_initial_upgrade,
    sign_string,
    unsign_string,
    update_sponsorship_status,
    validate_licenses,
)
from corporate.models import (
    CustomerPlan,
    ZulipSponsorshipRequest,
    get_current_plan_by_customer,
    get_customer_by_realm,
)
from corporate.views.billing_page import billing_home
from zerver.decorator import require_organization_member, zulip_login_required
from zerver.lib.actions import do_make_user_billing_admin
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.validator import check_bool, check_int, check_string_in
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
@has_request_variables
def initial_upgrade(
    request: HttpRequest, onboarding: bool = REQ(default=False, json_validator=check_bool)
) -> HttpResponse:
    user = request.user
    assert user.is_authenticated

    if not settings.BILLING_ENABLED or user.is_guest:
        return render(request, "404.html", status=404)

    billing_page_url = reverse(billing_home)

    customer = get_customer_by_realm(user.realm)
    if customer is not None and (
        get_current_plan_by_customer(customer) is not None or customer.sponsorship_pending
    ):
        if onboarding:
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
        "onboarding": onboarding,
        "page_params": {
            "seat_count": seat_count,
            "annual_price": 8000,
            "monthly_price": 800,
            "percent_off": float(percent_off),
        },
        "realm_org_type": user.realm.org_type,
        "sorted_org_types": sorted(
            (
                [org_type_name, org_type]
                for (org_type_name, org_type) in Realm.ORG_TYPES.items()
                if not org_type.get("hidden")
            ),
            key=lambda d: d[1]["display_order"],
        ),
    }
    response = render(request, "corporate/upgrade.html", context=context)
    return response


class SponsorshipRequestForm(forms.Form):
    website = forms.URLField(max_length=ZulipSponsorshipRequest.MAX_ORG_URL_LENGTH, required=False)
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

    if form.is_valid():
        with transaction.atomic():
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
    else:
        messages = []
        for error_list in form.errors.get_json_data().values():
            for error in error_list:
                messages.append(error["message"])
        message = " ".join(messages)
        raise BillingError("Form validation error", message=message)
