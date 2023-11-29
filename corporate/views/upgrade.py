import logging
from typing import Optional

from django import forms
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from pydantic import Json

from corporate.lib.decorator import authenticated_remote_realm_management_endpoint
from corporate.lib.stripe import (
    VALID_BILLING_MODALITY_VALUES,
    VALID_BILLING_SCHEDULE_VALUES,
    VALID_LICENSE_MANAGEMENT_VALUES,
    BillingError,
    InitialUpgradeRequest,
    RealmBillingSession,
    RemoteRealmBillingSession,
    UpgradeRequest,
)
from corporate.lib.support import get_support_url
from corporate.models import CustomerPlan, ZulipSponsorshipRequest
from zerver.actions.users import do_change_is_billing_admin
from zerver.decorator import require_organization_member, zulip_login_required
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.lib.validator import check_bool, check_int, check_string_in
from zerver.models import UserProfile, get_org_type_display_name
from zilencer.models import RemoteRealm

billing_logger = logging.getLogger("corporate.stripe")


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
) -> HttpResponse:
    try:
        upgrade_request = UpgradeRequest(
            billing_modality=billing_modality,
            schedule=schedule,
            signed_seat_count=signed_seat_count,
            salt=salt,
            license_management=license_management,
            licenses=licenses,
        )
        billing_session = RealmBillingSession(user)
        data = billing_session.do_upgrade(upgrade_request)
        return json_success(request, data)
    except BillingError as e:
        billing_logger.warning(
            "BillingError during upgrade: %s. user=%s, realm=%s (%s), billing_modality=%s, "
            "schedule=%s, license_management=%s, licenses=%s",
            e.error_description,
            user.id,
            user.realm.id,
            user.realm.string_id,
            billing_modality,
            schedule,
            license_management,
            licenses,
        )
        raise e
    except Exception:
        billing_logger.exception("Uncaught exception in billing:", stack_info=True)
        error_message = BillingError.CONTACT_SUPPORT.format(email=settings.ZULIP_ADMINISTRATOR)
        error_description = "uncaught exception during upgrade"
        raise BillingError(error_description, error_message)


@zulip_login_required
@has_request_variables
def upgrade_page(
    request: HttpRequest,
    manual_license_management: bool = REQ(default=False, json_validator=check_bool),
) -> HttpResponse:
    user = request.user
    assert user.is_authenticated

    if not settings.BILLING_ENABLED or user.is_guest:
        return render(request, "404.html", status=404)

    initial_upgrade_request = InitialUpgradeRequest(
        manual_license_management=manual_license_management,
        tier=CustomerPlan.STANDARD,
    )
    billing_session = RealmBillingSession(user)
    redirect_url, context = billing_session.get_initial_upgrade_context(initial_upgrade_request)

    if redirect_url:
        return HttpResponseRedirect(redirect_url)

    response = render(request, "corporate/upgrade.html", context=context)
    return response


@authenticated_remote_realm_management_endpoint
@typed_endpoint
def remote_realm_upgrade_page(
    request: HttpRequest,
    remote_realm: RemoteRealm,
    *,
    realm_uuid: PathOnly[str],
    manual_license_management: Json[bool] = False,
) -> HttpResponse:  # nocoverage
    initial_upgrade_request = InitialUpgradeRequest(
        manual_license_management=manual_license_management,
        tier=CustomerPlan.STANDARD,
    )
    billing_session = RemoteRealmBillingSession(remote_realm)
    redirect_url, context = billing_session.get_initial_upgrade_context(initial_upgrade_request)

    if redirect_url:
        return HttpResponseRedirect(redirect_url)

    response = render(request, "corporate/upgrade.html", context=context)
    return response


class SponsorshipRequestForm(forms.Form):
    website = forms.URLField(max_length=ZulipSponsorshipRequest.MAX_ORG_URL_LENGTH, required=False)
    organization_type = forms.IntegerField()
    description = forms.CharField(widget=forms.Textarea)
    expected_total_users = forms.CharField(widget=forms.Textarea)
    paid_users_count = forms.CharField(widget=forms.Textarea)
    paid_users_description = forms.CharField(widget=forms.Textarea, required=False)


@require_organization_member
@has_request_variables
def sponsorship(
    request: HttpRequest,
    user: UserProfile,
    organization_type: str = REQ(),
    website: str = REQ(),
    description: str = REQ(),
    expected_total_users: str = REQ(),
    paid_users_count: str = REQ(),
    paid_users_description: str = REQ(),
) -> HttpResponse:
    realm = user.realm
    billing_session = RealmBillingSession(user)

    requested_by = user.full_name
    user_role = user.get_role_name()
    support_url = get_support_url(realm)

    post_data = request.POST.copy()
    form = SponsorshipRequestForm(post_data)

    if form.is_valid():
        with transaction.atomic():
            # Ensures customer is created first before updating sponsorship status.
            billing_session.update_customer_sponsorship_status(True)
            sponsorship_request = ZulipSponsorshipRequest(
                customer=billing_session.get_customer(),
                requested_by=user,
                org_website=form.cleaned_data["website"],
                org_description=form.cleaned_data["description"],
                org_type=form.cleaned_data["organization_type"],
                expected_total_users=form.cleaned_data["expected_total_users"],
                paid_users_count=form.cleaned_data["paid_users_count"],
                paid_users_description=form.cleaned_data["paid_users_description"],
            )
            sponsorship_request.save()

            org_type = form.cleaned_data["organization_type"]
            if realm.org_type != org_type:
                realm.org_type = org_type
                realm.save(update_fields=["org_type"])

            do_change_is_billing_admin(user, True)

            org_type_display_name = get_org_type_display_name(org_type)

        context = {
            "requested_by": requested_by,
            "user_role": user_role,
            "string_id": realm.string_id,
            "support_url": support_url,
            "organization_type": org_type_display_name,
            "website": sponsorship_request.org_website,
            "description": sponsorship_request.org_description,
            "expected_total_users": sponsorship_request.expected_total_users,
            "paid_users_count": sponsorship_request.paid_users_count,
            "paid_users_description": sponsorship_request.paid_users_description,
        }
        # Sent to the server's support team, so this email is not user-facing.
        send_email(
            "zerver/emails/sponsorship_request",
            to_emails=[FromAddress.SUPPORT],
            from_name="Zulip sponsorship request",
            from_address=FromAddress.tokenized_no_reply_address(),
            reply_to_email=user.delivery_email,
            context=context,
        )

        return json_success(request)
    else:
        message = " ".join(
            error["message"]
            for error_list in form.errors.get_json_data().values()
            for error in error_list
        )
        raise BillingError("Form validation error", message=message)
