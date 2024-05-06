import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from operator import attrgetter
from typing import Any, Dict, Iterable, List, Optional, Union
from urllib.parse import urlencode, urlsplit

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.timesince import timesince
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from confirmation.models import Confirmation, confirmation_url
from confirmation.settings import STATUS_USED
from corporate.lib.activity import format_optional_datetime, remote_installation_stats_link
from corporate.lib.stripe import (
    BILLING_SUPPORT_EMAIL,
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    ServerDeactivateWithExistingPlanError,
    SupportRequestError,
    SupportType,
    SupportViewRequest,
    cents_to_dollar_string,
    do_deactivate_remote_server,
    do_reactivate_remote_server,
    format_discount_percentage,
)
from corporate.lib.support import (
    CloudSupportData,
    RemoteSupportData,
    get_data_for_cloud_support_view,
    get_data_for_remote_support_view,
    get_realm_support_url,
)
from corporate.models import CustomerPlan
from zerver.actions.create_realm import do_change_realm_subdomain
from zerver.actions.realm_settings import (
    do_change_realm_org_type,
    do_change_realm_plan_type,
    do_deactivate_realm,
    do_scrub_realm,
    do_send_realm_reactivation_email,
)
from zerver.actions.users import do_delete_user_preserving_messages
from zerver.decorator import require_server_admin, zulip_login_required
from zerver.forms import check_subdomain_available
from zerver.lib.exceptions import JsonableError
from zerver.lib.rate_limiter import rate_limit_request_by_ip
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.subdomains import get_subdomain_from_hostname
from zerver.lib.validator import (
    check_bool,
    check_date,
    check_string,
    check_string_in,
    to_decimal,
    to_non_negative_int,
)
from zerver.models import (
    MultiuseInvite,
    PreregistrationRealm,
    PreregistrationUser,
    Realm,
    RealmReactivationStatus,
    UserProfile,
)
from zerver.models.realms import get_org_type_display_name, get_realm
from zerver.models.users import get_user_profile_by_id
from zerver.views.invite import get_invitee_emails_set
from zilencer.lib.remote_counts import MissingDataError, compute_max_monthly_messages
from zilencer.models import (
    RemoteRealm,
    RemoteRealmBillingUser,
    RemoteServerBillingUser,
    RemoteZulipServer,
)


class SupportRequestForm(forms.Form):
    # We use the same subject length requirement as GitHub's
    # contact support form.
    MAX_SUBJECT_LENGTH = 50
    request_subject = forms.CharField(max_length=MAX_SUBJECT_LENGTH)
    request_message = forms.CharField(widget=forms.Textarea)


class DemoRequestForm(forms.Form):
    MAX_INPUT_LENGTH = 50
    SORTED_ORG_TYPE_NAMES = sorted(
        ([org_type["name"] for org_type in Realm.ORG_TYPES.values() if not org_type["hidden"]]),
    )
    full_name = forms.CharField(max_length=MAX_INPUT_LENGTH)
    email = forms.EmailField()
    role = forms.CharField(max_length=MAX_INPUT_LENGTH)
    organization_name = forms.CharField(max_length=MAX_INPUT_LENGTH)
    organization_type = forms.CharField()
    organization_website = forms.URLField(required=True)
    expected_user_count = forms.CharField(max_length=MAX_INPUT_LENGTH)
    message = forms.CharField(widget=forms.Textarea)


@zulip_login_required
@has_request_variables
def support_request(request: HttpRequest) -> HttpResponse:
    user = request.user
    assert user.is_authenticated

    context = {
        "email": user.delivery_email,
        "realm_name": user.realm.name,
        "MAX_SUBJECT_LENGTH": SupportRequestForm.MAX_SUBJECT_LENGTH,
    }

    if request.POST:
        post_data = request.POST.copy()
        form = SupportRequestForm(post_data)

        if form.is_valid():
            email_context = {
                "requested_by": user.full_name,
                "realm_string_id": user.realm.string_id,
                "request_subject": form.cleaned_data["request_subject"],
                "request_message": form.cleaned_data["request_message"],
                "support_url": get_realm_support_url(user.realm),
                "user_role": user.get_role_name(),
            }
            # Sent to the server's support team, so this email is not user-facing.
            send_email(
                "zerver/emails/support_request",
                to_emails=[FromAddress.SUPPORT],
                from_name="Zulip support request",
                from_address=FromAddress.tokenized_no_reply_address(),
                reply_to_email=user.delivery_email,
                context=email_context,
            )

            response = render(
                request, "corporate/support/support_request_thanks.html", context=context
            )
            return response

    response = render(request, "corporate/support/support_request.html", context=context)
    return response


@has_request_variables
def demo_request(request: HttpRequest) -> HttpResponse:
    context = {
        "MAX_INPUT_LENGTH": DemoRequestForm.MAX_INPUT_LENGTH,
        "SORTED_ORG_TYPE_NAMES": DemoRequestForm.SORTED_ORG_TYPE_NAMES,
    }

    if request.POST:
        post_data = request.POST.copy()
        form = DemoRequestForm(post_data)

        if form.is_valid():
            rate_limit_request_by_ip(request, domain="sends_email_by_ip")

            email_context = {
                "full_name": form.cleaned_data["full_name"],
                "email": form.cleaned_data["email"],
                "role": form.cleaned_data["role"],
                "organization_name": form.cleaned_data["organization_name"],
                "organization_type": form.cleaned_data["organization_type"],
                "organization_website": form.cleaned_data["organization_website"],
                "expected_user_count": form.cleaned_data["expected_user_count"],
                "message": form.cleaned_data["message"],
            }
            # Sent to the server's sales team, so this email is not user-facing.
            send_email(
                "zerver/emails/demo_request",
                to_emails=[BILLING_SUPPORT_EMAIL],
                from_name="Zulip demo request",
                from_address=FromAddress.tokenized_no_reply_address(),
                reply_to_email=email_context["email"],
                context=email_context,
            )

            response = render(
                request, "corporate/support/support_request_thanks.html", context=context
            )
            return response

    response = render(request, "corporate/support/demo_request.html", context=context)
    return response


def get_plan_type_string(plan_type: int) -> str:
    return {
        Realm.PLAN_TYPE_SELF_HOSTED: "Self-hosted",
        Realm.PLAN_TYPE_LIMITED: "Limited",
        Realm.PLAN_TYPE_STANDARD: "Standard",
        Realm.PLAN_TYPE_STANDARD_FREE: "Standard free",
        Realm.PLAN_TYPE_PLUS: "Plus",
        RemoteZulipServer.PLAN_TYPE_SELF_MANAGED: "Free",
        RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY: CustomerPlan.name_from_tier(
            CustomerPlan.TIER_SELF_HOSTED_LEGACY
        ),
        RemoteZulipServer.PLAN_TYPE_COMMUNITY: "Community",
        RemoteZulipServer.PLAN_TYPE_BASIC: "Basic",
        RemoteZulipServer.PLAN_TYPE_BUSINESS: "Business",
        RemoteZulipServer.PLAN_TYPE_ENTERPRISE: "Enterprise",
    }[plan_type]


def get_confirmations(
    types: List[int], object_ids: Iterable[int], hostname: Optional[str] = None
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
            if content_object.status == STATUS_USED:
                link_status = "Link has been used"
            else:
                link_status = "Link has not been used"
        else:
            link_status = ""

        now = timezone_now()
        if expiry_date is None:
            expires_in = "Never"
        elif now < expiry_date:
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


@dataclass
class SupportSelectOption:
    name: str
    value: int


def get_remote_plan_tier_options() -> List[SupportSelectOption]:
    remote_plan_tiers = [
        SupportSelectOption("None", 0),
        SupportSelectOption(
            CustomerPlan.name_from_tier(CustomerPlan.TIER_SELF_HOSTED_BASIC),
            CustomerPlan.TIER_SELF_HOSTED_BASIC,
        ),
        SupportSelectOption(
            CustomerPlan.name_from_tier(CustomerPlan.TIER_SELF_HOSTED_BUSINESS),
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        ),
    ]
    return remote_plan_tiers


def get_realm_plan_type_options() -> List[SupportSelectOption]:
    plan_types = [
        SupportSelectOption(
            get_plan_type_string(Realm.PLAN_TYPE_SELF_HOSTED), Realm.PLAN_TYPE_SELF_HOSTED
        ),
        SupportSelectOption(get_plan_type_string(Realm.PLAN_TYPE_LIMITED), Realm.PLAN_TYPE_LIMITED),
        SupportSelectOption(
            get_plan_type_string(Realm.PLAN_TYPE_STANDARD), Realm.PLAN_TYPE_STANDARD
        ),
        SupportSelectOption(
            get_plan_type_string(Realm.PLAN_TYPE_STANDARD_FREE), Realm.PLAN_TYPE_STANDARD_FREE
        ),
        SupportSelectOption(get_plan_type_string(Realm.PLAN_TYPE_PLUS), Realm.PLAN_TYPE_PLUS),
    ]
    return plan_types


def get_realm_plan_type_options_for_discount() -> List[SupportSelectOption]:
    plan_types = [
        SupportSelectOption("None", 0),
        SupportSelectOption(
            CustomerPlan.name_from_tier(CustomerPlan.TIER_CLOUD_STANDARD),
            CustomerPlan.TIER_CLOUD_STANDARD,
        ),
        SupportSelectOption(
            CustomerPlan.name_from_tier(CustomerPlan.TIER_CLOUD_PLUS),
            CustomerPlan.TIER_CLOUD_PLUS,
        ),
    ]
    return plan_types


VALID_MODIFY_PLAN_METHODS = [
    "downgrade_at_billing_cycle_end",
    "downgrade_now_without_additional_licenses",
    "downgrade_now_void_open_invoices",
    "upgrade_plan_tier",
]

VALID_STATUS_VALUES = [
    "active",
    "deactivated",
]

VALID_BILLING_MODALITY_VALUES = [
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
    minimum_licenses: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    required_plan_tier: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    new_subdomain: Optional[str] = REQ(default=None),
    status: Optional[str] = REQ(default=None, str_validator=check_string_in(VALID_STATUS_VALUES)),
    billing_modality: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_BILLING_MODALITY_VALUES)
    ),
    sponsorship_pending: Optional[bool] = REQ(default=None, json_validator=check_bool),
    approve_sponsorship: bool = REQ(default=False, json_validator=check_bool),
    modify_plan: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_MODIFY_PLAN_METHODS)
    ),
    scrub_realm: bool = REQ(default=False, json_validator=check_bool),
    delete_user_by_id: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    query: Optional[str] = REQ("q", default=None),
    org_type: Optional[int] = REQ(default=None, converter=to_non_negative_int),
) -> HttpResponse:
    context: Dict[str, Any] = {}

    if "success_message" in request.session:
        context["success_message"] = request.session["success_message"]
        del request.session["success_message"]

    acting_user = request.user
    assert isinstance(acting_user, UserProfile)
    if settings.BILLING_ENABLED and request.method == "POST":
        # We check that request.POST only has two keys in it: The
        # realm_id and a field to change.
        keys = set(request.POST.keys())
        if "csrfmiddlewaretoken" in keys:
            keys.remove("csrfmiddlewaretoken")
        if len(keys) != 2:
            raise JsonableError(_("Invalid parameters"))

        assert realm_id is not None
        realm = Realm.objects.get(id=realm_id)

        support_view_request = None

        if approve_sponsorship:
            support_view_request = SupportViewRequest(support_type=SupportType.approve_sponsorship)
        elif sponsorship_pending is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.update_sponsorship_status,
                sponsorship_status=sponsorship_pending,
            )
        elif discount is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.attach_discount,
                discount=discount,
            )
        elif minimum_licenses is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.update_minimum_licenses,
                minimum_licenses=minimum_licenses,
            )
        elif required_plan_tier is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.update_required_plan_tier,
                required_plan_tier=required_plan_tier,
            )
        elif billing_modality is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.update_billing_modality,
                billing_modality=billing_modality,
            )
        elif modify_plan is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.modify_plan,
                plan_modification=modify_plan,
            )
            if modify_plan == "upgrade_plan_tier":
                support_view_request["new_plan_tier"] = CustomerPlan.TIER_CLOUD_PLUS
        elif plan_type is not None:
            current_plan_type = realm.plan_type
            do_change_realm_plan_type(realm, plan_type, acting_user=acting_user)
            msg = f"Plan type of {realm.string_id} changed from {get_plan_type_string(current_plan_type)} to {get_plan_type_string(plan_type)} "
            context["success_message"] = msg
        elif org_type is not None:
            current_realm_type = realm.org_type
            do_change_realm_org_type(realm, org_type, acting_user=acting_user)
            msg = f"Org type of {realm.string_id} changed from {get_org_type_display_name(current_realm_type)} to {get_org_type_display_name(org_type)} "
            context["success_message"] = msg
        elif new_subdomain is not None:
            old_subdomain = realm.string_id
            try:
                check_subdomain_available(new_subdomain)
            except ValidationError as error:
                context["error_message"] = error.message
            else:
                do_change_realm_subdomain(realm, new_subdomain, acting_user=acting_user)
                request.session["success_message"] = (
                    f"Subdomain changed from {old_subdomain} to {new_subdomain}"
                )
                return HttpResponseRedirect(
                    reverse("support") + "?" + urlencode({"q": new_subdomain})
                )
        elif status is not None:
            if status == "active":
                do_send_realm_reactivation_email(realm, acting_user=acting_user)
                context["success_message"] = (
                    f"Realm reactivation email sent to admins of {realm.string_id}."
                )
            elif status == "deactivated":
                do_deactivate_realm(realm, acting_user=acting_user)
                context["success_message"] = f"{realm.string_id} deactivated."
        elif scrub_realm:
            do_scrub_realm(realm, acting_user=acting_user)
            context["success_message"] = f"{realm.string_id} scrubbed."
        elif delete_user_by_id:
            user_profile_for_deletion = get_user_profile_by_id(delete_user_by_id)
            user_email = user_profile_for_deletion.delivery_email
            assert user_profile_for_deletion.realm == realm
            do_delete_user_preserving_messages(user_profile_for_deletion)
            context["success_message"] = f"{user_email} in {realm.subdomain} deleted."

        if support_view_request is not None:
            billing_session = RealmBillingSession(
                user=acting_user, realm=realm, support_session=True
            )
            try:
                success_message = billing_session.process_support_view_request(support_view_request)
                context["success_message"] = success_message
            except SupportRequestError as error:
                context["error_message"] = error.msg

    if query:
        key_words = get_invitee_emails_set(query)

        case_insensitive_users_q = Q()
        for key_word in key_words:
            case_insensitive_users_q |= Q(delivery_email__iexact=key_word)
        users = set(UserProfile.objects.filter(case_insensitive_users_q))
        realms = set(Realm.objects.filter(string_id__in=key_words))

        for key_word in key_words:
            try:
                URLValidator()(key_word)
                parse_result = urlsplit(key_word)
                hostname = parse_result.hostname
                assert hostname is not None
                if parse_result.port:
                    hostname = f"{hostname}:{parse_result.port}"
                subdomain = get_subdomain_from_hostname(hostname)
                with suppress(Realm.DoesNotExist):
                    realms.add(get_realm(subdomain))
            except ValidationError:
                users.update(UserProfile.objects.filter(full_name__iexact=key_word))

        # full_names can have , in them
        users.update(UserProfile.objects.filter(full_name__iexact=query))

        context["users"] = users
        context["realms"] = realms

        confirmations: List[Dict[str, Any]] = []

        preregistration_user_ids = [
            user.id for user in PreregistrationUser.objects.filter(email__in=key_words)
        ]
        confirmations += get_confirmations(
            [Confirmation.USER_REGISTRATION, Confirmation.INVITATION],
            preregistration_user_ids,
            hostname=request.get_host(),
        )

        preregistration_realm_ids = [
            user.id for user in PreregistrationRealm.objects.filter(email__in=key_words)
        ]
        confirmations += get_confirmations(
            [Confirmation.REALM_CREATION],
            preregistration_realm_ids,
            hostname=request.get_host(),
        )

        multiuse_invite_ids = [
            invite.id for invite in MultiuseInvite.objects.filter(realm__in=realms)
        ]
        confirmations += get_confirmations([Confirmation.MULTIUSE_INVITE], multiuse_invite_ids)

        realm_reactivation_status_objects = RealmReactivationStatus.objects.filter(realm__in=realms)
        confirmations += get_confirmations(
            [Confirmation.REALM_REACTIVATION], [obj.id for obj in realm_reactivation_status_objects]
        )

        context["confirmations"] = confirmations

        # We want a union of all realms that might appear in the search result,
        # but not necessary as a separate result item.
        # Therefore, we do not modify the realms object in the context.
        all_realms = realms.union(
            [
                confirmation["object"].realm
                for confirmation in confirmations
                # For confirmations, we only display realm details when the type is USER_REGISTRATION
                # or INVITATION.
                if confirmation["type"] in (Confirmation.USER_REGISTRATION, Confirmation.INVITATION)
            ]
            + [user.realm for user in users]
        )
        realm_support_data: Dict[int, CloudSupportData] = {}
        for realm in all_realms:
            billing_session = RealmBillingSession(user=None, realm=realm)
            realm_data = get_data_for_cloud_support_view(billing_session)
            realm_support_data[realm.id] = realm_data
        context["realm_support_data"] = realm_support_data

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
    context["format_discount"] = format_discount_percentage
    context["dollar_amount"] = cents_to_dollar_string
    context["realm_icon_url"] = realm_icon_url
    context["Confirmation"] = Confirmation
    context["REALM_PLAN_TYPES"] = get_realm_plan_type_options()
    context["REALM_PLAN_TYPES_FOR_DISCOUNT"] = get_realm_plan_type_options_for_discount()
    context["ORGANIZATION_TYPES"] = sorted(
        Realm.ORG_TYPES.values(), key=lambda d: d["display_order"]
    )

    return render(request, "corporate/support/support.html", context=context)


def get_remote_servers_for_support(
    email_to_search: Optional[str], uuid_to_search: Optional[str], hostname_to_search: Optional[str]
) -> List["RemoteZulipServer"]:
    remote_servers_query = RemoteZulipServer.objects.order_by("id")

    if email_to_search:
        remote_servers_set = set(remote_servers_query.filter(contact_email__iexact=email_to_search))
        remote_server_billing_users = RemoteServerBillingUser.objects.filter(
            email__iexact=email_to_search
        ).select_related("remote_server")
        for server_billing_user in remote_server_billing_users:
            remote_servers_set.add(server_billing_user.remote_server)
        remote_realm_billing_users = RemoteRealmBillingUser.objects.filter(
            email__iexact=email_to_search
        ).select_related("remote_realm__server")
        for realm_billing_user in remote_realm_billing_users:
            remote_servers_set.add(realm_billing_user.remote_realm.server)
        return sorted(remote_servers_set, key=attrgetter("deactivated"))

    if uuid_to_search:
        remote_servers_set = set(remote_servers_query.filter(uuid__iexact=uuid_to_search))
        remote_realm_matches = RemoteRealm.objects.filter(
            uuid__iexact=uuid_to_search
        ).select_related("server")
        for remote_realm in remote_realm_matches:
            remote_servers_set.add(remote_realm.server)
        return sorted(remote_servers_set, key=attrgetter("deactivated"))

    if hostname_to_search:
        remote_servers_set = set(
            remote_servers_query.filter(hostname__icontains=hostname_to_search)
        )
        remote_realm_matches = (
            RemoteRealm.objects.filter(host__icontains=hostname_to_search)
        ).select_related("server")
        for remote_realm in remote_realm_matches:
            remote_servers_set.add(remote_realm.server)
        return sorted(remote_servers_set, key=attrgetter("deactivated"))

    return []


@require_server_admin
@has_request_variables
def remote_servers_support(
    request: HttpRequest,
    query: Optional[str] = REQ("q", default=None),
    remote_server_id: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    remote_realm_id: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    discount: Optional[Decimal] = REQ(default=None, converter=to_decimal),
    minimum_licenses: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    required_plan_tier: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    fixed_price: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    sent_invoice_id: Optional[str] = REQ(default=None, str_validator=check_string),
    sponsorship_pending: Optional[bool] = REQ(default=None, json_validator=check_bool),
    approve_sponsorship: bool = REQ(default=False, json_validator=check_bool),
    billing_modality: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_BILLING_MODALITY_VALUES)
    ),
    plan_end_date: Optional[str] = REQ(default=None, str_validator=check_date),
    modify_plan: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_MODIFY_PLAN_METHODS)
    ),
    delete_fixed_price_next_plan: bool = REQ(default=False, json_validator=check_bool),
    remote_server_status: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_STATUS_VALUES)
    ),
) -> HttpResponse:
    context: Dict[str, Any] = {}

    if "success_message" in request.session:
        context["success_message"] = request.session["success_message"]
        del request.session["success_message"]

    acting_user = request.user
    assert isinstance(acting_user, UserProfile)
    if settings.BILLING_ENABLED and request.method == "POST":
        keys = set(request.POST.keys())
        if "csrfmiddlewaretoken" in keys:
            keys.remove("csrfmiddlewaretoken")

        if remote_realm_id is not None:
            remote_realm_support_request = True
            remote_realm = RemoteRealm.objects.get(id=remote_realm_id)
        else:
            assert remote_server_id is not None
            remote_realm_support_request = False
            remote_server = RemoteZulipServer.objects.get(id=remote_server_id)

        support_view_request = None

        if approve_sponsorship:
            support_view_request = SupportViewRequest(support_type=SupportType.approve_sponsorship)
        elif sponsorship_pending is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.update_sponsorship_status,
                sponsorship_status=sponsorship_pending,
            )
        elif discount is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.attach_discount,
                discount=discount,
            )
        elif minimum_licenses is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.update_minimum_licenses,
                minimum_licenses=minimum_licenses,
            )
        elif required_plan_tier is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.update_required_plan_tier,
                required_plan_tier=required_plan_tier,
            )
        elif fixed_price is not None:
            # Treat empty field submitted as None.
            if sent_invoice_id is not None and sent_invoice_id.strip() == "":
                sent_invoice_id = None
            support_view_request = SupportViewRequest(
                support_type=SupportType.configure_fixed_price_plan,
                fixed_price=fixed_price,
                sent_invoice_id=sent_invoice_id,
            )
        elif billing_modality is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.update_billing_modality,
                billing_modality=billing_modality,
            )
        elif plan_end_date is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.update_plan_end_date,
                plan_end_date=plan_end_date,
            )
        elif modify_plan is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.modify_plan,
                plan_modification=modify_plan,
            )
        elif delete_fixed_price_next_plan:
            support_view_request = SupportViewRequest(
                support_type=SupportType.delete_fixed_price_next_plan,
            )
        elif remote_server_status:
            assert remote_server is not None
            remote_server_status_billing_session = RemoteServerBillingSession(
                support_staff=acting_user, remote_server=remote_server
            )
            if remote_server_status == "active":
                do_reactivate_remote_server(remote_server)
                context["success_message"] = (
                    f"Remote server ({remote_server.hostname}) reactivated."
                )
            else:
                assert remote_server_status == "deactivated"
                try:
                    do_deactivate_remote_server(remote_server, remote_server_status_billing_session)
                    context["success_message"] = (
                        f"Remote server ({remote_server.hostname}) deactivated."
                    )
                except ServerDeactivateWithExistingPlanError:
                    context["error_message"] = (
                        f"Cannot deactivate remote server ({remote_server.hostname}) that has active or scheduled plans."
                    )

        if support_view_request is not None:
            if remote_realm_support_request:
                try:
                    success_message = RemoteRealmBillingSession(
                        support_staff=acting_user, remote_realm=remote_realm
                    ).process_support_view_request(support_view_request)
                    context["success_message"] = success_message
                except SupportRequestError as error:
                    context["error_message"] = error.msg
            else:
                try:
                    success_message = RemoteServerBillingSession(
                        support_staff=acting_user, remote_server=remote_server
                    ).process_support_view_request(support_view_request)
                    context["success_message"] = success_message
                except SupportRequestError as error:
                    context["error_message"] = error.msg

    email_to_search = None
    uuid_to_search = None
    hostname_to_search = None
    if query:
        search_text = query.strip()
        if "@" in search_text:
            email_to_search = search_text
        else:
            try:
                uuid.UUID(search_text, version=4)
                uuid_to_search = search_text
            except ValueError:
                hostname_to_search = search_text

    remote_servers = get_remote_servers_for_support(
        email_to_search=email_to_search,
        uuid_to_search=uuid_to_search,
        hostname_to_search=hostname_to_search,
    )
    remote_server_to_max_monthly_messages: Dict[int, Union[int, str]] = dict()
    server_support_data: Dict[int, RemoteSupportData] = {}
    realm_support_data: Dict[int, RemoteSupportData] = {}
    remote_realms: Dict[int, List[RemoteRealm]] = {}
    for remote_server in remote_servers:
        # Get remote realms attached to remote server
        remote_realms_for_server = list(
            remote_server.remoterealm_set.exclude(is_system_bot_realm=True)
        )
        remote_realms[remote_server.id] = remote_realms_for_server
        # Get plan data for remote realms
        for remote_realm in remote_realms_for_server:
            realm_billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)
            remote_realm_data = get_data_for_remote_support_view(realm_billing_session)
            realm_support_data[remote_realm.id] = remote_realm_data
        # Get plan data for remote server
        server_billing_session = RemoteServerBillingSession(remote_server=remote_server)
        remote_server_data = get_data_for_remote_support_view(server_billing_session)
        server_support_data[remote_server.id] = remote_server_data
        # Get max monthly messages
        try:
            remote_server_to_max_monthly_messages[remote_server.id] = compute_max_monthly_messages(
                remote_server
            )
        except MissingDataError:
            remote_server_to_max_monthly_messages[remote_server.id] = (
                "Recent analytics data missing"
            )

    def get_remote_server_billing_user_emails_as_string(remote_server: RemoteZulipServer) -> str:
        return ", ".join(
            remote_server.get_remote_server_billing_users()
            .order_by("email")
            .values_list("email", flat=True)
        )

    def get_remote_realm_billing_user_emails_as_string(remote_realm: RemoteRealm) -> str:
        return ", ".join(
            remote_realm.get_remote_realm_billing_users()
            .order_by("email")
            .values_list("email", flat=True)
        )

    context["remote_servers"] = remote_servers
    context["remote_servers_support_data"] = server_support_data
    context["remote_server_to_max_monthly_messages"] = remote_server_to_max_monthly_messages
    context["remote_realms"] = remote_realms
    context["remote_realms_support_data"] = realm_support_data
    context["get_plan_type_name"] = get_plan_type_string
    context["get_org_type_display_name"] = get_org_type_display_name
    context["format_discount"] = format_discount_percentage
    context["format_optional_datetime"] = format_optional_datetime
    context["dollar_amount"] = cents_to_dollar_string
    context["server_analytics_link"] = remote_installation_stats_link
    context["REMOTE_PLAN_TIERS"] = get_remote_plan_tier_options()
    context["get_remote_server_billing_user_emails"] = (
        get_remote_server_billing_user_emails_as_string
    )
    context["get_remote_realm_billing_user_emails"] = get_remote_realm_billing_user_emails_as_string
    context["SPONSORED_PLAN_TYPE"] = RemoteZulipServer.PLAN_TYPE_COMMUNITY

    return render(
        request,
        "corporate/support/remote_server_support.html",
        context=context,
    )
