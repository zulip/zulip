import uuid
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from operator import attrgetter
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

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
from pydantic import AfterValidator, Json, NonNegativeInt

from confirmation.models import Confirmation, confirmation_url
from confirmation.settings import STATUS_USED
from corporate.lib.activity import (
    format_optional_datetime,
    realm_support_link,
    remote_installation_stats_link,
)
from corporate.lib.billing_types import BillingModality
from corporate.models.plans import CustomerPlan
from zerver.actions.create_realm import do_change_realm_subdomain
from zerver.actions.realm_settings import (
    do_change_realm_max_invites,
    do_change_realm_org_type,
    do_change_realm_plan_type,
    do_deactivate_realm,
    do_scrub_realm,
    do_send_realm_reactivation_email,
)
from zerver.actions.users import do_delete_user_preserving_messages
from zerver.decorator import require_server_admin, zulip_login_required
from zerver.forms import check_subdomain_available
from zerver.lib.rate_limiter import rate_limit_request_by_ip
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.subdomains import get_subdomain_from_hostname
from zerver.lib.typed_endpoint import (
    ApiParamConfig,
    typed_endpoint,
    typed_endpoint_without_parameters,
)
from zerver.lib.validator import check_date
from zerver.models import (
    MultiuseInvite,
    PreregistrationRealm,
    PreregistrationUser,
    Realm,
    RealmReactivationStatus,
    UserProfile,
)
from zerver.models.realms import (
    get_default_max_invites_for_realm_plan_type,
    get_org_type_display_name,
    get_realm,
)
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
    TYPE_OF_HOSTING_OPTIONS = [
        "Zulip Cloud",
        "Self-hosting",
        "Both / not sure",
    ]
    full_name = forms.CharField(max_length=MAX_INPUT_LENGTH)
    email = forms.EmailField()
    role = forms.CharField(max_length=MAX_INPUT_LENGTH)
    organization_name = forms.CharField(max_length=MAX_INPUT_LENGTH)
    organization_type = forms.CharField()
    organization_website = forms.URLField(required=True, assume_scheme="https")
    expected_user_count = forms.CharField(max_length=MAX_INPUT_LENGTH)
    type_of_hosting = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)


class SalesRequestForm(forms.Form):
    MAX_INPUT_LENGTH = 50
    organization_website = forms.URLField(required=True, assume_scheme="https")
    expected_user_count = forms.CharField(max_length=MAX_INPUT_LENGTH)
    message = forms.CharField(widget=forms.Textarea)


@zulip_login_required
@typed_endpoint_without_parameters
def support_request(request: HttpRequest) -> HttpResponse:
    from corporate.lib.stripe import build_support_url

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
                "support_url": build_support_url("support", user.realm.string_id),
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


@typed_endpoint_without_parameters
def demo_request(request: HttpRequest) -> HttpResponse:
    from corporate.lib.stripe import BILLING_SUPPORT_EMAIL

    context = {
        "MAX_INPUT_LENGTH": DemoRequestForm.MAX_INPUT_LENGTH,
        "SORTED_ORG_TYPE_NAMES": DemoRequestForm.SORTED_ORG_TYPE_NAMES,
        "TYPE_OF_HOSTING_OPTIONS": DemoRequestForm.TYPE_OF_HOSTING_OPTIONS,
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
                "type_of_hosting": form.cleaned_data["type_of_hosting"],
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


@zulip_login_required
@typed_endpoint_without_parameters
def sales_support_request(request: HttpRequest) -> HttpResponse:
    from corporate.lib.stripe import BILLING_SUPPORT_EMAIL

    assert request.user.is_authenticated

    if not request.user.is_realm_admin:
        return render(request, "404.html", status=404)

    context = {
        "MAX_INPUT_LENGTH": SalesRequestForm.MAX_INPUT_LENGTH,
        "user_email": request.user.delivery_email,
        "user_full_name": request.user.full_name,
    }

    if request.POST:
        post_data = request.POST.copy()
        form = SalesRequestForm(post_data)

        if form.is_valid():
            rate_limit_request_by_ip(request, domain="sends_email_by_ip")

            email_context = {
                "full_name": request.user.full_name,
                "email": request.user.delivery_email,
                "role": UserProfile.ROLE_ID_TO_API_NAME[request.user.role],
                "organization_name": request.user.realm.name,
                "organization_type": get_org_type_display_name(request.user.realm.org_type),
                "organization_website": form.cleaned_data["organization_website"],
                "expected_user_count": form.cleaned_data["expected_user_count"],
                "message": form.cleaned_data["message"],
                "support_link": realm_support_link(request.user.realm.string_id),
            }

            send_email(
                "zerver/emails/sales_support_request",
                to_emails=[BILLING_SUPPORT_EMAIL],
                from_name="Sales support request",
                from_address=FromAddress.tokenized_no_reply_address(),
                reply_to_email=email_context["email"],
                context=email_context,
            )

            response = render(
                request, "corporate/support/support_request_thanks.html", context=context
            )
            return response

    response = render(request, "corporate/support/sales_support_request.html", context=context)
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
    types: list[int], object_ids: Iterable[int], hostname: str | None = None
) -> list[dict[str, Any]]:
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


def get_remote_plan_tier_options() -> list[SupportSelectOption]:
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


def get_realm_plan_type_options() -> list[SupportSelectOption]:
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


def get_realm_plan_type_options_for_discount() -> list[SupportSelectOption]:
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


def get_default_max_invites_for_plan_type(realm: Realm) -> int:
    default_max = get_default_max_invites_for_realm_plan_type(realm.plan_type)
    if default_max is None:
        return settings.INVITES_DEFAULT_REALM_DAILY_MAX
    return default_max


def check_update_max_invites(realm: Realm, new_max: int, default_max: int) -> bool:
    if new_max in [0, default_max]:
        return realm.max_invites != default_max
    return new_max > default_max


ModifyPlan = Literal[
    "downgrade_at_billing_cycle_end",
    "downgrade_now_without_additional_licenses",
    "downgrade_now_void_open_invoices",
    "upgrade_plan_tier",
]

RemoteServerStatus = Literal["active", "deactivated"]


def shared_support_context() -> dict[str, object]:
    from corporate.lib.stripe import cents_to_dollar_string

    return {
        "get_org_type_display_name": get_org_type_display_name,
        "get_plan_type_name": get_plan_type_string,
        "dollar_amount": cents_to_dollar_string,
    }


@require_server_admin
@typed_endpoint
def support(
    request: HttpRequest,
    *,
    realm_id: Json[NonNegativeInt] | None = None,
    plan_type: Json[NonNegativeInt] | None = None,
    monthly_discounted_price: Json[NonNegativeInt] | None = None,
    annual_discounted_price: Json[NonNegativeInt] | None = None,
    minimum_licenses: Json[NonNegativeInt] | None = None,
    required_plan_tier: Json[NonNegativeInt] | None = None,
    new_subdomain: str | None = None,
    status: RemoteServerStatus | None = None,
    billing_modality: BillingModality | None = None,
    sponsorship_pending: Json[bool] | None = None,
    approve_sponsorship: Json[bool] = False,
    modify_plan: ModifyPlan | None = None,
    scrub_realm: Json[bool] = False,
    delete_user_by_id: Json[NonNegativeInt] | None = None,
    query: Annotated[str | None, ApiParamConfig("q")] = None,
    org_type: Json[NonNegativeInt] | None = None,
    max_invites: Json[NonNegativeInt] | None = None,
    plan_end_date: Annotated[str, AfterValidator(lambda x: check_date("plan_end_date", x))]
    | None = None,
    fixed_price: Json[NonNegativeInt] | None = None,
    sent_invoice_id: str | None = None,
    delete_fixed_price_next_plan: Json[bool] = False,
) -> HttpResponse:
    from corporate.lib.stripe import (
        RealmBillingSession,
        SupportRequestError,
        SupportType,
        SupportViewRequest,
    )
    from corporate.lib.support import CloudSupportData, get_data_for_cloud_support_view

    context = shared_support_context()

    if "success_message" in request.session:
        context["success_message"] = request.session["success_message"]
        del request.session["success_message"]

    acting_user = request.user
    assert isinstance(acting_user, UserProfile)
    if settings.BILLING_ENABLED and request.method == "POST":
        # We check that request.POST only has two keys in it: The
        # realm_id and a field to change.
        keys = set(request.POST.keys())
        keys.discard("csrfmiddlewaretoken")

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
        elif monthly_discounted_price is not None or annual_discounted_price is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.attach_discount,
                monthly_discounted_price=monthly_discounted_price,
                annual_discounted_price=annual_discounted_price,
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
        elif plan_end_date is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.update_plan_end_date,
                plan_end_date=plan_end_date,
            )
        elif fixed_price is not None:
            # Treat empty string for send_invoice_id as None.
            if sent_invoice_id is not None and sent_invoice_id.strip() == "":
                sent_invoice_id = None
            support_view_request = SupportViewRequest(
                support_type=SupportType.configure_fixed_price_plan,
                fixed_price=fixed_price,
                sent_invoice_id=sent_invoice_id,
            )
        elif delete_fixed_price_next_plan:
            support_view_request = SupportViewRequest(
                support_type=SupportType.delete_fixed_price_next_plan,
            )
        elif plan_type is not None:
            current_plan_type = realm.plan_type
            do_change_realm_plan_type(realm, plan_type, acting_user=acting_user)
            msg = f"Plan type of {realm.string_id} changed from {get_plan_type_string(current_plan_type)} to {get_plan_type_string(plan_type)} "
            context["success_message"] = msg
        elif org_type is not None:
            current_realm_type = realm.org_type
            do_change_realm_org_type(realm, org_type, acting_user=acting_user)
            msg = f"Organization type of {realm.string_id} changed from {get_org_type_display_name(current_realm_type)} to {get_org_type_display_name(org_type)} "
            context["success_message"] = msg
        elif max_invites is not None:
            default_max = get_default_max_invites_for_plan_type(realm)
            if check_update_max_invites(realm, max_invites, default_max):
                do_change_realm_max_invites(realm, max_invites, acting_user=acting_user)
                update_text = str(max_invites)
                if max_invites == 0:
                    update_text = "the default for the current plan type"
                msg = f"Maximum number of daily invitations for {realm.string_id} updated to {update_text}."
                context["success_message"] = msg
            else:
                update_text = f"{max_invites} is less than the default for the current plan type"
                if max_invites in [0, default_max]:
                    update_text = "the default for the current plan type is already set"
                context["error_message"] = (
                    f"Cannot update maximum number of daily invitations for {realm.string_id}, because {update_text}."
                )
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
                return HttpResponseRedirect(reverse("support", query={"q": new_subdomain}))
        elif status is not None:
            if status == "active":
                do_send_realm_reactivation_email(realm, acting_user=acting_user)
                context["success_message"] = (
                    f"Realm reactivation email sent to admins of {realm.string_id}."
                )
            elif status == "deactivated":
                # TODO: Add support for deactivation reason in the support UI that'll be passed
                # here.
                do_deactivate_realm(
                    realm,
                    acting_user=acting_user,
                    deactivation_reason="owner_request",
                    email_owners=True,
                )
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
                assert subdomain is not None
                with suppress(Realm.DoesNotExist):
                    realms.add(get_realm(subdomain))
            except ValidationError:
                users.update(UserProfile.objects.filter(full_name__iexact=key_word))

        # full_names can have , in them
        users.update(UserProfile.objects.filter(full_name__iexact=query))

        context["users"] = users
        context["realms"] = realms

        confirmations: list[dict[str, Any]] = []

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
        realm_support_data: dict[int, CloudSupportData] = {}
        for realm in all_realms:
            billing_session = RealmBillingSession(user=None, realm=realm)
            realm_data = get_data_for_cloud_support_view(billing_session)
            realm_support_data[realm.id] = realm_data
        context["realm_support_data"] = realm_support_data
        context["SPONSORED_PLAN_TYPE"] = Realm.PLAN_TYPE_STANDARD_FREE

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
    context["realm_icon_url"] = realm_icon_url
    context["Confirmation"] = Confirmation
    context["REALM_PLAN_TYPES"] = get_realm_plan_type_options()
    context["REALM_PLAN_TYPES_FOR_DISCOUNT"] = get_realm_plan_type_options_for_discount()
    context["ORGANIZATION_TYPES"] = sorted(
        Realm.ORG_TYPES.values(), key=lambda d: d["display_order"]
    )
    context["remote_support_view"] = False

    return render(request, "corporate/support/support.html", context=context)


def get_remote_servers_for_support(
    email_to_search: str | None, uuid_to_search: str | None, hostname_to_search: str | None
) -> list["RemoteZulipServer"]:
    remote_servers_query = RemoteZulipServer.objects.order_by("id")

    if email_to_search:
        remote_servers_set = {
            *remote_servers_query.filter(contact_email__iexact=email_to_search),
            *(
                server_billing_user.remote_server
                for server_billing_user in RemoteServerBillingUser.objects.filter(
                    email__iexact=email_to_search
                ).select_related("remote_server")
            ),
            *(
                realm_billing_user.remote_realm.server
                for realm_billing_user in RemoteRealmBillingUser.objects.filter(
                    email__iexact=email_to_search
                ).select_related("remote_realm__server")
            ),
        }
        return sorted(remote_servers_set, key=attrgetter("deactivated"))

    if uuid_to_search:
        remote_servers_set = {
            *remote_servers_query.filter(uuid__iexact=uuid_to_search),
            *(
                remote_realm.server
                for remote_realm in RemoteRealm.objects.filter(
                    uuid__iexact=uuid_to_search
                ).select_related("server")
            ),
        }
        return sorted(remote_servers_set, key=attrgetter("deactivated"))

    if hostname_to_search:
        remote_servers_set = {
            *remote_servers_query.filter(hostname__icontains=hostname_to_search),
            *(
                remote_realm.server
                for remote_realm in (
                    RemoteRealm.objects.filter(host__icontains=hostname_to_search)
                ).select_related("server")
            ),
        }
        return sorted(remote_servers_set, key=attrgetter("deactivated"))

    return []


@require_server_admin
@typed_endpoint
def remote_servers_support(
    request: HttpRequest,
    *,
    query: Annotated[str | None, ApiParamConfig("q")] = None,
    remote_server_id: Json[NonNegativeInt] | None = None,
    remote_realm_id: Json[NonNegativeInt] | None = None,
    monthly_discounted_price: Json[NonNegativeInt] | None = None,
    annual_discounted_price: Json[NonNegativeInt] | None = None,
    minimum_licenses: Json[NonNegativeInt] | None = None,
    required_plan_tier: Json[NonNegativeInt] | None = None,
    fixed_price: Json[NonNegativeInt] | None = None,
    sent_invoice_id: str | None = None,
    sponsorship_pending: Json[bool] | None = None,
    approve_sponsorship: Json[bool] = False,
    billing_modality: BillingModality | None = None,
    plan_end_date: Annotated[str, AfterValidator(lambda x: check_date("plan_end_date", x))]
    | None = None,
    modify_plan: ModifyPlan | None = None,
    delete_fixed_price_next_plan: Json[bool] = False,
    remote_server_status: RemoteServerStatus | None = None,
    complimentary_access_plan: Annotated[
        str, AfterValidator(lambda x: check_date("complimentary_access_plan", x))
    ]
    | None = None,
) -> HttpResponse:
    from corporate.lib.stripe import (
        RemoteRealmBillingSession,
        RemoteServerBillingSession,
        ServerDeactivateWithExistingPlanError,
        SupportRequestError,
        SupportType,
        SupportViewRequest,
        do_deactivate_remote_server,
        do_reactivate_remote_server,
    )
    from corporate.lib.support import RemoteSupportData, get_data_for_remote_support_view

    context = shared_support_context()

    if "success_message" in request.session:
        context["success_message"] = request.session["success_message"]
        del request.session["success_message"]

    acting_user = request.user
    assert isinstance(acting_user, UserProfile)
    if settings.BILLING_ENABLED and request.method == "POST":
        keys = set(request.POST.keys())
        keys.discard("csrfmiddlewaretoken")

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
        elif monthly_discounted_price is not None or annual_discounted_price is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.attach_discount,
                monthly_discounted_price=monthly_discounted_price,
                annual_discounted_price=annual_discounted_price,
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
        elif complimentary_access_plan is not None:
            support_view_request = SupportViewRequest(
                support_type=SupportType.configure_complimentary_access_plan,
                plan_end_date=complimentary_access_plan,
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
    remote_server_to_max_monthly_messages: dict[int, int | str] = dict()
    server_support_data: dict[int, RemoteSupportData] = {}
    realm_support_data: dict[int, RemoteSupportData] = {}
    remote_realms: dict[int, list[RemoteRealm]] = {}
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
    context["format_optional_datetime"] = format_optional_datetime
    context["server_analytics_link"] = remote_installation_stats_link
    context["REMOTE_PLAN_TIERS"] = get_remote_plan_tier_options()
    context["get_remote_server_billing_user_emails"] = (
        get_remote_server_billing_user_emails_as_string
    )
    context["get_remote_realm_billing_user_emails"] = get_remote_realm_billing_user_emails_as_string
    context["SPONSORED_PLAN_TYPE"] = RemoteZulipServer.PLAN_TYPE_COMMUNITY
    context["remote_support_view"] = True

    return render(
        request,
        "corporate/support/remote_server_support.html",
        context=context,
    )
