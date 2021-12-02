import urllib
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.timesince import timesince
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from confirmation.models import Confirmation, confirmation_url
from confirmation.settings import STATUS_ACTIVE
from zerver.decorator import require_server_admin
from zerver.forms import check_subdomain_available
from zerver.lib.actions import (
    do_change_plan_type,
    do_change_realm_org_type,
    do_change_realm_subdomain,
    do_deactivate_realm,
    do_scrub_realm,
    do_send_realm_reactivation_email,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.subdomains import get_subdomain_from_hostname
from zerver.lib.validator import check_bool, check_string_in, to_decimal, to_non_negative_int
from zerver.models import (
    MultiuseInvite,
    PreregistrationUser,
    Realm,
    UserProfile,
    get_org_type_display_name,
    get_realm,
)
from zerver.views.invite import get_invitee_emails_set

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import approve_sponsorship as do_approve_sponsorship
    from corporate.lib.stripe import (
        attach_discount_to_realm,
        downgrade_at_the_end_of_billing_cycle,
        downgrade_now_without_creating_additional_invoices,
        get_discount_for_realm,
        get_latest_seat_count,
        make_end_of_cycle_updates_if_needed,
        update_billing_method_of_current_plan,
        update_sponsorship_status,
        void_all_open_invoices,
    )
    from corporate.models import get_current_plan_by_realm, get_customer_by_realm


def get_plan_name(plan_type: int) -> str:
    return {
        Realm.PLAN_TYPE_SELF_HOSTED: "self hosted",
        Realm.PLAN_TYPE_LIMITED: "limited",
        Realm.PLAN_TYPE_STANDARD: "standard",
        Realm.PLAN_TYPE_STANDARD_FREE: "open source",
        Realm.PLAN_TYPE_PLUS: "plus",
    }[plan_type]


def get_confirmations(
    types: List[int], object_ids: List[int], hostname: Optional[str] = None
) -> List[Dict[str, Any]]:
    lowest_datetime = timezone_now() - timedelta(days=30)
    confirmations = Confirmation.objects.filter(
        type__in=types, object_id__in=object_ids, date_sent__gte=lowest_datetime
    )
    confirmation_dicts = []
    for confirmation in confirmations:
        realm = confirmation.realm
        content_object = confirmation.content_object

        type = confirmation.type
        expiry_date = confirmation.expiry_date

        assert content_object is not None
        if hasattr(content_object, "status"):
            if content_object.status == STATUS_ACTIVE:
                link_status = "Link has been clicked"
            else:
                link_status = "Link has never been clicked"
        else:
            link_status = ""

        now = timezone_now()
        if now < expiry_date:
            expires_in = timesince(now, expiry_date)
        else:
            expires_in = "Expired"

        url = confirmation_url(confirmation.confirmation_key, realm, type)
        confirmation_dicts.append(
            {
                "object": confirmation.content_object,
                "url": url,
                "type": type,
                "link_status": link_status,
                "expires_in": expires_in,
            }
        )
    return confirmation_dicts


VALID_DOWNGRADE_METHODS = [
    "downgrade_at_billing_cycle_end",
    "downgrade_now_without_additional_licenses",
    "downgrade_now_void_open_invoices",
]

VALID_STATUS_VALUES = [
    "active",
    "deactivated",
]

VALID_BILLING_METHODS = [
    "send_invoice",
    "charge_automatically",
]


@require_server_admin
@has_request_variables
def support(
    request: HttpRequest,
    realm_id: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    plan_type: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    discount: Optional[Decimal] = REQ(default=None, converter=to_decimal),
    new_subdomain: Optional[str] = REQ(default=None),
    status: Optional[str] = REQ(default=None, str_validator=check_string_in(VALID_STATUS_VALUES)),
    billing_method: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_BILLING_METHODS)
    ),
    sponsorship_pending: Optional[bool] = REQ(default=None, json_validator=check_bool),
    approve_sponsorship: Optional[bool] = REQ(default=None, json_validator=check_bool),
    downgrade_method: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_DOWNGRADE_METHODS)
    ),
    scrub_realm: Optional[bool] = REQ(default=None, json_validator=check_bool),
    query: Optional[str] = REQ("q", default=None),
    org_type: Optional[int] = REQ(default=None, converter=to_non_negative_int),
) -> HttpResponse:
    context: Dict[str, Any] = {}

    if "success_message" in request.session:
        context["success_message"] = request.session["success_message"]
        del request.session["success_message"]

    if settings.BILLING_ENABLED and request.method == "POST":
        # We check that request.POST only has two keys in it: The
        # realm_id and a field to change.
        keys = set(request.POST.keys())
        if "csrfmiddlewaretoken" in keys:
            keys.remove("csrfmiddlewaretoken")
        if len(keys) != 2:
            raise JsonableError(_("Invalid parameters"))

        realm = Realm.objects.get(id=realm_id)

        acting_user = request.user
        assert isinstance(acting_user, UserProfile)
        if plan_type is not None:
            current_plan_type = realm.plan_type
            do_change_plan_type(realm, plan_type, acting_user=acting_user)
            msg = f"Plan type of {realm.string_id} changed from {get_plan_name(current_plan_type)} to {get_plan_name(plan_type)} "
            context["success_message"] = msg
        elif org_type is not None:
            current_realm_type = realm.org_type
            do_change_realm_org_type(realm, org_type, acting_user=acting_user)
            msg = f"Org type of {realm.string_id} changed from {get_org_type_display_name(current_realm_type)} to {get_org_type_display_name(org_type)} "
            context["success_message"] = msg
        elif discount is not None:
            current_discount = get_discount_for_realm(realm) or 0
            attach_discount_to_realm(realm, discount, acting_user=acting_user)
            context[
                "success_message"
            ] = f"Discount of {realm.string_id} changed to {discount}% from {current_discount}%."
        elif new_subdomain is not None:
            old_subdomain = realm.string_id
            try:
                check_subdomain_available(new_subdomain)
            except ValidationError as error:
                context["error_message"] = error.message
            else:
                do_change_realm_subdomain(realm, new_subdomain, acting_user=acting_user)
                request.session[
                    "success_message"
                ] = f"Subdomain changed from {old_subdomain} to {new_subdomain}"
                return HttpResponseRedirect(
                    reverse("support") + "?" + urlencode({"q": new_subdomain})
                )
        elif status is not None:
            if status == "active":
                do_send_realm_reactivation_email(realm, acting_user=acting_user)
                context[
                    "success_message"
                ] = f"Realm reactivation email sent to admins of {realm.string_id}."
            elif status == "deactivated":
                do_deactivate_realm(realm, acting_user=acting_user)
                context["success_message"] = f"{realm.string_id} deactivated."
        elif billing_method is not None:
            if billing_method == "send_invoice":
                update_billing_method_of_current_plan(
                    realm, charge_automatically=False, acting_user=acting_user
                )
                context[
                    "success_message"
                ] = f"Billing method of {realm.string_id} updated to pay by invoice."
            elif billing_method == "charge_automatically":
                update_billing_method_of_current_plan(
                    realm, charge_automatically=True, acting_user=acting_user
                )
                context[
                    "success_message"
                ] = f"Billing method of {realm.string_id} updated to charge automatically."
        elif sponsorship_pending is not None:
            if sponsorship_pending:
                update_sponsorship_status(realm, True, acting_user=acting_user)
                context["success_message"] = f"{realm.string_id} marked as pending sponsorship."
            else:
                update_sponsorship_status(realm, False, acting_user=acting_user)
                context["success_message"] = f"{realm.string_id} is no longer pending sponsorship."
        elif approve_sponsorship:
            do_approve_sponsorship(realm, acting_user=acting_user)
            context["success_message"] = f"Sponsorship approved for {realm.string_id}"
        elif downgrade_method is not None:
            if downgrade_method == "downgrade_at_billing_cycle_end":
                downgrade_at_the_end_of_billing_cycle(realm)
                context[
                    "success_message"
                ] = f"{realm.string_id} marked for downgrade at the end of billing cycle"
            elif downgrade_method == "downgrade_now_without_additional_licenses":
                downgrade_now_without_creating_additional_invoices(realm)
                context[
                    "success_message"
                ] = f"{realm.string_id} downgraded without creating additional invoices"
            elif downgrade_method == "downgrade_now_void_open_invoices":
                downgrade_now_without_creating_additional_invoices(realm)
                voided_invoices_count = void_all_open_invoices(realm)
                context[
                    "success_message"
                ] = f"{realm.string_id} downgraded and voided {voided_invoices_count} open invoices"
        elif scrub_realm:
            do_scrub_realm(realm, acting_user=acting_user)
            context["success_message"] = f"{realm.string_id} scrubbed."

    if query:
        key_words = get_invitee_emails_set(query)

        users = set(UserProfile.objects.filter(delivery_email__in=key_words))
        realms = set(Realm.objects.filter(string_id__in=key_words))

        for key_word in key_words:
            try:
                URLValidator()(key_word)
                parse_result = urllib.parse.urlparse(key_word)
                hostname = parse_result.hostname
                assert hostname is not None
                if parse_result.port:
                    hostname = f"{hostname}:{parse_result.port}"
                subdomain = get_subdomain_from_hostname(hostname)
                try:
                    realms.add(get_realm(subdomain))
                except Realm.DoesNotExist:
                    pass
            except ValidationError:
                users.update(UserProfile.objects.filter(full_name__iexact=key_word))

        for realm in realms:
            realm.customer = get_customer_by_realm(realm)

            current_plan = get_current_plan_by_realm(realm)
            if current_plan is not None:
                new_plan, last_ledger_entry = make_end_of_cycle_updates_if_needed(
                    current_plan, timezone_now()
                )
                if last_ledger_entry is not None:
                    if new_plan is not None:
                        realm.current_plan = new_plan
                    else:
                        realm.current_plan = current_plan
                    realm.current_plan.licenses = last_ledger_entry.licenses
                    realm.current_plan.licenses_used = get_latest_seat_count(realm)

        # full_names can have , in them
        users.update(UserProfile.objects.filter(full_name__iexact=query))

        context["users"] = users
        context["realms"] = realms

        confirmations: List[Dict[str, Any]] = []

        preregistration_users = PreregistrationUser.objects.filter(email__in=key_words)
        confirmations += get_confirmations(
            [Confirmation.USER_REGISTRATION, Confirmation.INVITATION, Confirmation.REALM_CREATION],
            preregistration_users,
            hostname=request.get_host(),
        )

        multiuse_invites = MultiuseInvite.objects.filter(realm__in=realms)
        confirmations += get_confirmations([Confirmation.MULTIUSE_INVITE], multiuse_invites)

        confirmations += get_confirmations(
            [Confirmation.REALM_REACTIVATION], [realm.id for realm in realms]
        )

        context["confirmations"] = confirmations

    def get_realm_owner_emails_as_string(realm: Realm) -> str:
        return ", ".join(
            realm.get_human_owner_users()
            .order_by("delivery_email")
            .values_list("delivery_email", flat=True)
        )

    def get_realm_admin_emails_as_string(realm: Realm) -> str:
        return ", ".join(
            realm.get_human_admin_users(include_realm_owners=False)
            .order_by("delivery_email")
            .values_list("delivery_email", flat=True)
        )

    context["get_realm_owner_emails_as_string"] = get_realm_owner_emails_as_string
    context["get_realm_admin_emails_as_string"] = get_realm_admin_emails_as_string
    context["get_discount_for_realm"] = get_discount_for_realm
    context["get_org_type_display_name"] = get_org_type_display_name
    context["realm_icon_url"] = realm_icon_url
    context["Confirmation"] = Confirmation
    context["sorted_realm_types"] = sorted(
        Realm.ORG_TYPES.values(), key=lambda d: d["display_order"]
    )

    return render(request, "analytics/support.html", context=context)
