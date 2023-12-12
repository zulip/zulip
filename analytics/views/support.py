from contextlib import suppress
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Union
from urllib.parse import urlencode, urlsplit

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
from zerver.actions.create_realm import do_change_realm_subdomain
from zerver.actions.realm_settings import (
    do_change_realm_org_type,
    do_change_realm_plan_type,
    do_deactivate_realm,
    do_scrub_realm,
    do_send_realm_reactivation_email,
)
from zerver.actions.users import do_delete_user_preserving_messages
from zerver.decorator import require_server_admin
from zerver.forms import check_subdomain_available
from zerver.lib.exceptions import JsonableError
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.subdomains import get_subdomain_from_hostname
from zerver.lib.validator import check_bool, check_string_in, to_decimal, to_non_negative_int
from zerver.models import (
    MultiuseInvite,
    PreregistrationRealm,
    PreregistrationUser,
    Realm,
    RealmReactivationStatus,
    UserProfile,
    get_org_type_display_name,
    get_realm,
    get_user_profile_by_id,
)
from zerver.views.invite import get_invitee_emails_set

if settings.ZILENCER_ENABLED:
    from zilencer.lib.remote_counts import MissingDataError, compute_max_monthly_messages
    from zilencer.models import RemoteRealm, RemoteZulipServer

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import (
        RealmBillingSession,
        RemoteRealmBillingSession,
        RemoteServerBillingSession,
        SupportType,
        SupportViewRequest,
    )
    from corporate.lib.support import (
        PlanData,
        get_current_plan_data_for_support_view,
        get_customer_discount_for_support_view,
    )
    from corporate.models import CustomerPlan


def get_plan_type_string(plan_type: int) -> str:
    return {
        Realm.PLAN_TYPE_SELF_HOSTED: "Self-hosted",
        Realm.PLAN_TYPE_LIMITED: "Limited",
        Realm.PLAN_TYPE_STANDARD: "Standard",
        Realm.PLAN_TYPE_STANDARD_FREE: "Standard free",
        Realm.PLAN_TYPE_PLUS: "Plus",
        RemoteZulipServer.PLAN_TYPE_SELF_HOSTED: "Self-hosted",
        RemoteZulipServer.PLAN_TYPE_COMMUNITY: "Community",
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
            success_message = billing_session.process_support_view_request(support_view_request)
            context["success_message"] = success_message

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
        plan_data: Dict[int, PlanData] = {}
        for realm in all_realms:
            billing_session = RealmBillingSession(user=None, realm=realm)
            realm_plan_data = get_current_plan_data_for_support_view(billing_session)
            plan_data[realm.id] = realm_plan_data
        context["plan_data"] = plan_data

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
    context["get_discount"] = get_customer_discount_for_support_view
    context["get_org_type_display_name"] = get_org_type_display_name
    context["realm_icon_url"] = realm_icon_url
    context["Confirmation"] = Confirmation
    context["sorted_realm_types"] = sorted(
        Realm.ORG_TYPES.values(), key=lambda d: d["display_order"]
    )

    return render(request, "analytics/support.html", context=context)


def get_remote_servers_for_support(
    email_to_search: Optional[str], hostname_to_search: Optional[str]
) -> List["RemoteZulipServer"]:
    if not email_to_search and not hostname_to_search:
        return []

    remote_servers_query = RemoteZulipServer.objects.order_by("id").prefetch_related(
        "remoterealm_set"
    )
    if email_to_search:
        remote_servers_query = remote_servers_query.filter(contact_email__iexact=email_to_search)
    elif hostname_to_search:
        remote_servers_query = remote_servers_query.filter(hostname__icontains=hostname_to_search)

    return list(remote_servers_query)


@require_server_admin
@has_request_variables
def remote_servers_support(
    request: HttpRequest,
    query: Optional[str] = REQ("q", default=None),
    remote_server_id: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    remote_realm_id: Optional[int] = REQ(default=None, converter=to_non_negative_int),
    discount: Optional[Decimal] = REQ(default=None, converter=to_decimal),
    sponsorship_pending: Optional[bool] = REQ(default=None, json_validator=check_bool),
    approve_sponsorship: bool = REQ(default=False, json_validator=check_bool),
    billing_modality: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_BILLING_MODALITY_VALUES)
    ),
    modify_plan: Optional[str] = REQ(
        default=None, str_validator=check_string_in(VALID_MODIFY_PLAN_METHODS)
    ),
) -> HttpResponse:
    context: Dict[str, Any] = {}

    if "success_message" in request.session:
        context["success_message"] = request.session["success_message"]
        del request.session["success_message"]

    acting_user = request.user
    assert isinstance(acting_user, UserProfile)
    if settings.BILLING_ENABLED and request.method == "POST":
        # We check that request.POST only has two keys in it:
        # either the remote_server_id or a remote_realm_id,
        # and a field to change.
        keys = set(request.POST.keys())
        if "csrfmiddlewaretoken" in keys:
            keys.remove("csrfmiddlewaretoken")
        if len(keys) != 2:
            raise JsonableError(_("Invalid parameters"))

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
        if support_view_request is not None:
            if remote_realm_support_request:
                success_message = RemoteRealmBillingSession(
                    support_staff=acting_user, remote_realm=remote_realm
                ).process_support_view_request(support_view_request)
            else:
                success_message = RemoteServerBillingSession(
                    support_staff=acting_user, remote_server=remote_server
                ).process_support_view_request(support_view_request)
            context["success_message"] = success_message

    email_to_search = None
    hostname_to_search = None
    if query:
        if "@" in query:
            email_to_search = query
        else:
            hostname_to_search = query

    remote_servers = get_remote_servers_for_support(
        email_to_search=email_to_search, hostname_to_search=hostname_to_search
    )
    remote_server_to_max_monthly_messages: Dict[int, Union[int, str]] = dict()
    server_plan_data: Dict[int, PlanData] = {}
    realm_plan_data: Dict[int, PlanData] = {}
    remote_realms: Dict[int, List[RemoteRealm]] = {}
    for remote_server in remote_servers:
        # Get remote realms attached to remote server
        remote_realms_for_server = list(
            remote_server.remoterealm_set.exclude(is_system_bot_realm=True)
        )
        remote_realms[remote_server.id] = remote_realms_for_server
        # Get plan data for remote realms
        for remote_realm in remote_realms[remote_server.id]:
            realm_billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)
            remote_realm_plan_data = get_current_plan_data_for_support_view(realm_billing_session)
            realm_plan_data[remote_realm.id] = remote_realm_plan_data
        # Get plan data for remote server
        server_billing_session = RemoteServerBillingSession(remote_server=remote_server)
        remote_server_plan_data = get_current_plan_data_for_support_view(server_billing_session)
        server_plan_data[remote_server.id] = remote_server_plan_data
        # Get max monthly messages
        try:
            remote_server_to_max_monthly_messages[remote_server.id] = compute_max_monthly_messages(
                remote_server
            )
        except MissingDataError:
            remote_server_to_max_monthly_messages[remote_server.id] = "Recent data missing"

    context["remote_servers"] = remote_servers
    context["remote_servers_plan_data"] = server_plan_data
    context["remote_server_to_max_monthly_messages"] = remote_server_to_max_monthly_messages
    context["remote_realms"] = remote_realms
    context["remote_realms_plan_data"] = realm_plan_data
    context["get_discount"] = get_customer_discount_for_support_view
    context["get_plan_type_name"] = get_plan_type_string
    context["get_org_type_display_name"] = get_org_type_display_name
    context["SPONSORED_PLAN_TYPE"] = RemoteZulipServer.PLAN_TYPE_COMMUNITY

    return render(
        request,
        "analytics/remote_server_support.html",
        context=context,
    )
