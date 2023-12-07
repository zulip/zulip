import logging
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from pydantic import Json

from corporate.lib.decorator import (
    authenticated_remote_realm_management_endpoint,
    authenticated_remote_server_management_endpoint,
)
from corporate.lib.stripe import (
    VALID_BILLING_MODALITY_VALUES,
    VALID_BILLING_SCHEDULE_VALUES,
    VALID_LICENSE_MANAGEMENT_VALUES,
    BillingError,
    InitialUpgradeRequest,
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    UpgradeRequest,
)
from corporate.models import CustomerPlan
from zerver.decorator import require_organization_member, zulip_login_required
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.validator import check_bool, check_int, check_string_in
from zerver.models import UserProfile
from zilencer.lib.remote_counts import MissingDataError

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
            # TODO: tier should be a passed parameter.
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            remote_server_plan_start_date=None,
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


@authenticated_remote_realm_management_endpoint
@has_request_variables
def remote_realm_upgrade(
    request: HttpRequest,
    billing_session: RemoteRealmBillingSession,
    billing_modality: str = REQ(str_validator=check_string_in(VALID_BILLING_MODALITY_VALUES)),
    schedule: str = REQ(str_validator=check_string_in(VALID_BILLING_SCHEDULE_VALUES)),
    signed_seat_count: str = REQ(),
    salt: str = REQ(),
    license_management: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_LICENSE_MANAGEMENT_VALUES)
    ),
    licenses: Optional[int] = REQ(json_validator=check_int, default=None),
    remote_server_plan_start_date: Optional[str] = REQ(default=None),
) -> HttpResponse:  # nocoverage
    try:
        upgrade_request = UpgradeRequest(
            billing_modality=billing_modality,
            schedule=schedule,
            signed_seat_count=signed_seat_count,
            salt=salt,
            license_management=license_management,
            licenses=licenses,
            # TODO: tier should be a passed parameter.
            tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            remote_server_plan_start_date=remote_server_plan_start_date,
        )
        data = billing_session.do_upgrade(upgrade_request)
        return json_success(request, data)
    except BillingError as e:
        billing_logger.warning(
            "BillingError during upgrade: %s. remote_realm=%s (%s), billing_modality=%s, "
            "schedule=%s, license_management=%s, licenses=%s",
            e.error_description,
            billing_session.remote_realm.id,
            billing_session.remote_realm.host,
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


@authenticated_remote_server_management_endpoint
@has_request_variables
def remote_server_upgrade(
    request: HttpRequest,
    billing_session: RemoteServerBillingSession,
    billing_modality: str = REQ(str_validator=check_string_in(VALID_BILLING_MODALITY_VALUES)),
    schedule: str = REQ(str_validator=check_string_in(VALID_BILLING_SCHEDULE_VALUES)),
    signed_seat_count: str = REQ(),
    salt: str = REQ(),
    license_management: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_LICENSE_MANAGEMENT_VALUES)
    ),
    licenses: Optional[int] = REQ(json_validator=check_int, default=None),
    remote_server_plan_start_date: Optional[str] = REQ(default=None),
) -> HttpResponse:  # nocoverage
    try:
        upgrade_request = UpgradeRequest(
            billing_modality=billing_modality,
            schedule=schedule,
            signed_seat_count=signed_seat_count,
            salt=salt,
            license_management=license_management,
            licenses=licenses,
            # TODO: tier should be a passed parameter.
            tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            remote_server_plan_start_date=remote_server_plan_start_date,
        )
        data = billing_session.do_upgrade(upgrade_request)
        return json_success(request, data)
    except BillingError as e:
        billing_logger.warning(
            "BillingError during upgrade: %s. remote_server=%s (%s), billing_modality=%s, "
            "schedule=%s, license_management=%s, licenses=%s",
            e.error_description,
            billing_session.remote_server.id,
            billing_session.remote_server.hostname,
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
        tier=CustomerPlan.TIER_CLOUD_STANDARD,
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
    billing_session: RemoteRealmBillingSession,
    *,
    manual_license_management: Json[bool] = False,
    success_message: str = "",
) -> HttpResponse:  # nocoverage
    initial_upgrade_request = InitialUpgradeRequest(
        manual_license_management=manual_license_management,
        tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        success_message=success_message,
    )
    try:
        redirect_url, context = billing_session.get_initial_upgrade_context(initial_upgrade_request)
    except MissingDataError:
        return billing_session.missing_data_error_page(request)

    if redirect_url:
        return HttpResponseRedirect(redirect_url)

    response = render(request, "corporate/upgrade.html", context=context)
    return response


@authenticated_remote_server_management_endpoint
@typed_endpoint
def remote_server_upgrade_page(
    request: HttpRequest,
    billing_session: RemoteServerBillingSession,
    *,
    manual_license_management: Json[bool] = False,
    success_message: str = "",
) -> HttpResponse:  # nocoverage
    initial_upgrade_request = InitialUpgradeRequest(
        manual_license_management=manual_license_management,
        tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        success_message=success_message,
    )
    try:
        redirect_url, context = billing_session.get_initial_upgrade_context(initial_upgrade_request)
    except MissingDataError:
        return billing_session.missing_data_error_page(request)

    if redirect_url:
        return HttpResponseRedirect(redirect_url)

    response = render(request, "corporate/upgrade.html", context=context)
    return response
