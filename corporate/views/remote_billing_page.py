import logging
from typing import Any, Literal, TypeAlias, cast
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Exists, OuterRef
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.utils.timezone import now as timezone_now
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from pydantic import Json

from confirmation.models import (
    Confirmation,
    ConfirmationKeyError,
    create_confirmation_link,
    get_object_from_key,
    render_confirmation_key_error,
)
from corporate.lib.decorator import self_hosting_management_endpoint
from corporate.lib.remote_billing_util import (
    REMOTE_BILLING_SESSION_VALIDITY_SECONDS,
    LegacyServerIdentityDict,
    RemoteBillingIdentityDict,
    RemoteBillingIdentityExpiredError,
    RemoteBillingUserDict,
    get_remote_server_and_user_from_session,
)
from corporate.models.customers import get_customer_by_remote_server
from corporate.models.plans import CustomerPlan, get_current_plan_by_customer
from zerver.lib.exceptions import (
    JsonableError,
    MissingRemoteRealmError,
    RateLimitedError,
    RemoteBillingAuthenticationError,
    RemoteRealmServerMismatchError,
)
from zerver.lib.rate_limiter import rate_limit_request_by_ip
from zerver.lib.remote_server import RealmDataForAnalytics, UserDataForRemoteBilling
from zerver.lib.response import json_success
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zilencer.auth import rate_limit_remote_server
from zilencer.models import (
    PreregistrationRemoteRealmBillingUser,
    PreregistrationRemoteServerBillingUser,
    RemoteRealm,
    RemoteRealmBillingUser,
    RemoteServerBillingUser,
    RemoteZulipServer,
    get_remote_server_by_uuid,
)
from zilencer.views import handle_customer_migration_from_server_to_realm

billing_logger = logging.getLogger("corporate.stripe")


VALID_NEXT_PAGES = [None, "sponsorship", "upgrade", "billing", "plans", "deactivate"]
VALID_NEXT_PAGES_TYPE: TypeAlias = Literal[
    None, "sponsorship", "upgrade", "billing", "plans", "deactivate"
]

REMOTE_BILLING_SIGNED_ACCESS_TOKEN_VALIDITY_IN_SECONDS = 2 * 60 * 60
# We use units of hours here so that we can pass this through to the
# email template that tells the recipient how long these will last.
LOGIN_CONFIRMATION_EMAIL_DURATION_HOURS = 24


@csrf_exempt
@typed_endpoint
def remote_realm_billing_entry(
    request: HttpRequest,
    remote_server: RemoteZulipServer,
    *,
    user: Json[UserDataForRemoteBilling],
    realm: Json[RealmDataForAnalytics],
    uri_scheme: Literal["http://", "https://"] = "https://",
    next_page: VALID_NEXT_PAGES_TYPE = None,
) -> HttpResponse:
    try:
        remote_realm = RemoteRealm.objects.get(uuid=realm.uuid, server=remote_server)
    except RemoteRealm.DoesNotExist:
        if RemoteRealm.objects.filter(uuid=realm.uuid).exists():  # nocoverage
            billing_logger.warning(
                "%s: Realm %s exists, but not registered to server %s",
                request.path,
                realm.uuid,
                remote_server.id,
            )
            raise RemoteRealmServerMismatchError
        else:
            # This error will prod the remote server to submit its realm info, which
            # should lead to the creation of this missing RemoteRealm registration.
            raise MissingRemoteRealmError

    identity_dict = RemoteBillingIdentityDict(
        user=RemoteBillingUserDict(
            user_email=user.email, user_uuid=str(user.uuid), user_full_name=user.full_name
        ),
        remote_server_uuid=str(remote_server.uuid),
        remote_realm_uuid=str(remote_realm.uuid),
        remote_billing_user_id=None,
        authenticated_at=datetime_to_timestamp(timezone_now()),
        uri_scheme=uri_scheme,
        next_page=next_page,
    )

    signed_identity_dict = signing.dumps(identity_dict)

    billing_access_url = (
        f"{settings.EXTERNAL_URI_SCHEME}{settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN}.{settings.EXTERNAL_HOST}"
        + reverse(remote_realm_billing_finalize_login, args=[signed_identity_dict])
    )
    return json_success(request, data={"billing_access_url": billing_access_url})


def get_identity_dict_from_signed_access_token(
    signed_billing_access_token: str,
) -> RemoteBillingIdentityDict:
    try:
        identity_dict: RemoteBillingIdentityDict = signing.loads(
            signed_billing_access_token,
            max_age=REMOTE_BILLING_SIGNED_ACCESS_TOKEN_VALIDITY_IN_SECONDS,
        )
    except signing.SignatureExpired:
        raise JsonableError(_("Billing access token expired."))
    except signing.BadSignature:
        raise JsonableError(_("Invalid billing access token."))
    return identity_dict


def is_tos_consent_needed_for_user(
    remote_user: RemoteRealmBillingUser | RemoteServerBillingUser,
) -> bool:
    assert settings.TERMS_OF_SERVICE_VERSION is not None
    return int(settings.TERMS_OF_SERVICE_VERSION.split(".")[0]) > int(
        remote_user.tos_version.split(".")[0]
    )


@self_hosting_management_endpoint
@typed_endpoint
def remote_realm_billing_finalize_login(
    request: HttpRequest,
    *,
    signed_billing_access_token: PathOnly[str],
    full_name: str | None = None,
    tos_consent: Literal[None, "true"] = None,
    enable_major_release_emails: Literal[None, "true", "false"] = None,
    enable_maintenance_release_emails: Literal[None, "true", "false"] = None,
) -> HttpResponse:
    """
    This is the endpoint accessed via the billing_access_url, generated by
    remote_realm_billing_entry entry.
    """
    from corporate.lib.stripe import BILLING_SUPPORT_EMAIL, RemoteRealmBillingSession

    if request.method not in ["GET", "POST"]:
        return HttpResponseNotAllowed(["GET", "POST"])
    tos_consent_given = tos_consent == "true"

    # Sanity assert, because otherwise these make no sense.
    assert (
        REMOTE_BILLING_SIGNED_ACCESS_TOKEN_VALIDITY_IN_SECONDS
        <= REMOTE_BILLING_SESSION_VALIDITY_SECONDS
    )

    identity_dict = get_identity_dict_from_signed_access_token(signed_billing_access_token)

    # Now we want to fetch the RemoteRealmBillingUser object implied
    # by the IdentityDict. We'll use this:
    # (1) If the user came here via just GET, we want to show them a confirmation
    #     page with the relevant info details before finalizing login. If they wish
    #     to proceed, they'll approve the form, causing a POST, bring us to case (2).
    # (2) If the user came here via POST, we finalize login, using the info from the
    #     IdentityDict to update the RemoteRealmBillingUser object if needed.
    # Finally, if the user is logging in for the first time, we'll need to create
    # their account first. This will happen by making them fill out a form to confirm
    # their email first. Only after clicking the confirmation link in the email,
    # they will have their account created and finally be redirected back here.
    remote_realm_uuid = identity_dict["remote_realm_uuid"]
    remote_server_uuid = identity_dict["remote_server_uuid"]
    try:
        remote_server = get_remote_server_by_uuid(remote_server_uuid)
        remote_realm = RemoteRealm.objects.get(uuid=remote_realm_uuid, server=remote_server)
    except ObjectDoesNotExist:
        # These should definitely still exist, since the access token was signed
        # pretty recently. (And we generally don't delete these at all.)
        raise AssertionError

    try:
        handle_customer_migration_from_server_to_realm(server=remote_server)
    except JsonableError:
        # JsonableError should be propagated up, as they are meant to convey
        # a json error response to be returned.
        raise
    except Exception:  # nocoverage
        billing_logger.exception(
            "%s: Failed to migrate customer from server (id: %s) to realm",
            request.path,
            remote_server.id,
            stack_info=True,
        )
        raise JsonableError(
            _(
                "Couldn't reconcile billing data between server and realm. Please contact {support_email}"
            ).format(support_email=BILLING_SUPPORT_EMAIL)
        )

    # Redirect to error page if server is on an active plan
    server_customer = get_customer_by_remote_server(remote_server)
    if server_customer is not None:
        server_plan = get_current_plan_by_customer(server_customer)
        if server_plan is not None:
            return render(
                request,
                "corporate/billing/remote_realm_login_error_for_server_on_active_plan.html",
                context={
                    "server_plan_name": server_plan.name,
                },
            )

    user_dict = identity_dict["user"]

    user_email = user_dict["user_email"]
    user_uuid = user_dict["user_uuid"]

    assert settings.TERMS_OF_SERVICE_VERSION is not None, (
        "This is only run on the bouncer, which has ToS"
    )

    try:
        remote_user = RemoteRealmBillingUser.objects.get(
            remote_realm=remote_realm,
            user_uuid=user_uuid,
        )
        tos_consent_needed = is_tos_consent_needed_for_user(remote_user)
    except RemoteRealmBillingUser.DoesNotExist:
        # This is the first time this user is logging in.
        remote_user = None
        tos_consent_needed = True

    if request.method == "GET":
        if remote_user is not None:
            # Render a template where the user will just confirm their info,
            # possibly accept ToS if needed, POST back here and will get fully
            # authenticated.
            context = {
                "remote_server_uuid": remote_server_uuid,
                "remote_realm_uuid": remote_realm_uuid,
                "host": remote_realm.host,
                "user_email": remote_user.email,
                "user_full_name": remote_user.full_name,
                "tos_consent_needed": tos_consent_needed,
                "action_url": reverse(
                    remote_realm_billing_finalize_login, args=(signed_billing_access_token,)
                ),
            }
            return render(
                request,
                "corporate/billing/remote_billing_finalize_login_confirmation.html",
                context=context,
            )
        else:
            # This user is logging in for the first time, so we need to create their
            # RemoteRealmBillingUser object. Render a template where they'll
            # enter their email address - we'll send a verification email to it.
            context = {
                "email": user_email,
                "action_url": reverse(
                    remote_realm_billing_confirm_email, args=(signed_billing_access_token,)
                ),
            }
            return render(
                request,
                "corporate/billing/remote_billing_confirm_email_form.html",
                context=context,
            )

    assert request.method == "POST"
    if remote_user is None:
        # Users logging in for the first time need to be created and follow
        # a different path - they should not be POSTing here. It should be impossible
        # to get here with a remote_user that is None without tampering with the form
        # or manually crafting a POST request.
        raise JsonableError(_("User account doesn't exist yet."))

    if tos_consent_needed and not tos_consent_given:
        # This shouldn't be possible without tampering with the form, so we
        # don't need a pretty error.
        raise JsonableError(_("You must accept the Terms of Service to proceed."))

    # The current approach is to update the full_name and email preferences
    # only when the user first logs in.
    if full_name is not None:
        remote_user.full_name = full_name
        remote_user.enable_major_release_emails = enable_major_release_emails == "true"
        remote_user.enable_maintenance_release_emails = enable_maintenance_release_emails == "true"

    remote_user.tos_version = settings.TERMS_OF_SERVICE_VERSION
    remote_user.last_login = timezone_now()

    remote_user.save(
        update_fields=[
            "full_name",
            "tos_version",
            "last_login",
            "enable_maintenance_release_emails",
            "enable_major_release_emails",
        ]
    )

    identity_dict["remote_billing_user_id"] = remote_user.id
    request.session["remote_billing_identities"] = {}
    request.session["remote_billing_identities"][f"remote_realm:{remote_realm_uuid}"] = (
        identity_dict
    )

    next_page = identity_dict["next_page"]
    assert next_page in VALID_NEXT_PAGES
    if next_page is not None:
        return HttpResponseRedirect(
            reverse(f"remote_realm_{next_page}_page", args=(remote_realm_uuid,))
        )
    elif remote_realm.plan_type in [
        RemoteRealm.PLAN_TYPE_SELF_MANAGED,
        RemoteRealm.PLAN_TYPE_SELF_MANAGED_LEGACY,
    ]:
        # If they have a scheduled upgrade while on a complimentary access plan,
        # redirect to billing page.
        billing_session = RemoteRealmBillingSession(remote_realm)
        customer = billing_session.get_customer()
        if (
            customer is not None
            and billing_session.get_complimentary_access_next_plan_name(customer) is not None
        ):
            return HttpResponseRedirect(
                reverse("remote_realm_billing_page", args=(remote_realm_uuid,))
            )
        return HttpResponseRedirect(reverse("remote_realm_plans_page", args=(remote_realm_uuid,)))
    elif remote_realm.plan_type == RemoteRealm.PLAN_TYPE_COMMUNITY:
        return HttpResponseRedirect(
            reverse("remote_realm_sponsorship_page", args=(remote_realm_uuid,))
        )
    else:
        return HttpResponseRedirect(reverse("remote_realm_billing_page", args=(remote_realm_uuid,)))


@self_hosting_management_endpoint
@typed_endpoint
def remote_realm_billing_confirm_email(
    request: HttpRequest,
    *,
    signed_billing_access_token: PathOnly[str],
    email: str,
) -> HttpResponse:
    """
    Endpoint for users in the RemoteRealm flow that are logging in for the first time
    and still have to have their RemoteRealmBillingUser object created.
    Takes the POST from the above form asking for their email address
    and sends confirmation email to the provided
    email address in order to verify. Only the confirmation link will grant
    a fully authenticated session.
    """

    from corporate.lib.stripe import BILLING_SUPPORT_EMAIL

    identity_dict = get_identity_dict_from_signed_access_token(signed_billing_access_token)
    try:
        remote_server = get_remote_server_by_uuid(identity_dict["remote_server_uuid"])
        remote_realm = RemoteRealm.objects.get(
            uuid=identity_dict["remote_realm_uuid"], server=remote_server
        )
    except ObjectDoesNotExist:
        raise AssertionError

    rate_limit_error_response = check_rate_limits(request, remote_server)
    if rate_limit_error_response is not None:
        return rate_limit_error_response

    obj = PreregistrationRemoteRealmBillingUser.objects.create(
        email=email,
        remote_realm=remote_realm,
        user_uuid=identity_dict["user"]["user_uuid"],
        next_page=identity_dict["next_page"],
        uri_scheme=identity_dict["uri_scheme"],
    )
    url = create_remote_billing_confirmation_link(
        obj,
        Confirmation.REMOTE_REALM_BILLING_LEGACY_LOGIN,
        validity_in_minutes=LOGIN_CONFIRMATION_EMAIL_DURATION_HOURS * 60,
    )

    context = {
        "remote_realm_host": remote_realm.host,
        "confirmation_url": url,
        "billing_help_link": "https://zulip.com/help/self-hosted-billing",
        "billing_contact_email": BILLING_SUPPORT_EMAIL,
        "validity_in_hours": LOGIN_CONFIRMATION_EMAIL_DURATION_HOURS,
    }
    send_email(
        "zerver/emails/remote_realm_billing_confirm_login",
        to_emails=[email],
        from_address=FromAddress.tokenized_no_reply_address(),
        language=get_language(),
        context=context,
    )

    return render(
        request,
        "corporate/billing/remote_billing_email_confirmation_sent.html",
        context={"email": email},
    )


@self_hosting_management_endpoint
@typed_endpoint
def remote_realm_billing_from_login_confirmation_link(
    request: HttpRequest,
    *,
    confirmation_key: PathOnly[str],
) -> HttpResponse:
    """
    The user comes here via the confirmation link they received via email.
    Creates the RemoteRealmBillingUser object and redirects to
    remote_realm_billing_finalize_login with a new signed access token,
    where they will finally be logged in now that they have an account.
    """
    try:
        prereg_object = get_object_from_key(
            confirmation_key,
            [Confirmation.REMOTE_REALM_BILLING_LEGACY_LOGIN],
            # These links aren't reusable. The user just clicks it
            # to get their account created. Afterwards, they're not
            # subject to the confirmation link part of the flow anymore.
            mark_object_used=True,
        )
    except ConfirmationKeyError as exception:
        return render_confirmation_key_error(request, exception)
    assert isinstance(prereg_object, PreregistrationRemoteRealmBillingUser)
    remote_realm = prereg_object.remote_realm

    uri_scheme = prereg_object.uri_scheme
    next_page = prereg_object.next_page
    assert next_page in VALID_NEXT_PAGES
    assert uri_scheme in ["http://", "https://"]
    # Mypy is not satisfied by the above assert, so we need to cast.
    uri_scheme = cast(Literal["http://", "https://"], uri_scheme)

    remote_billing_user, created = RemoteRealmBillingUser.objects.get_or_create(
        remote_realm=remote_realm,
        user_uuid=prereg_object.user_uuid,
        defaults={"email": prereg_object.email},
    )
    if not created:
        billing_logger.info(
            "Matching RemoteRealmBillingUser already exists for "
            "PreregistrationRemoteRealmBillingUser %s",
            prereg_object.id,
        )

    prereg_object.created_user = remote_billing_user
    prereg_object.save(update_fields=["created_user"])

    identity_dict = RemoteBillingIdentityDict(
        user=RemoteBillingUserDict(
            user_email=remote_billing_user.email,
            user_uuid=str(remote_billing_user.user_uuid),
            user_full_name=remote_billing_user.full_name,
        ),
        remote_server_uuid=str(remote_realm.server.uuid),
        remote_realm_uuid=str(remote_realm.uuid),
        # This will be figured out by the next endpoint in the flow anyway.
        remote_billing_user_id=None,
        authenticated_at=datetime_to_timestamp(timezone_now()),
        uri_scheme=uri_scheme,
        next_page=next_page,
    )

    signed_identity_dict = signing.dumps(identity_dict)

    return HttpResponseRedirect(
        reverse(remote_realm_billing_finalize_login, args=[signed_identity_dict])
    )


def create_remote_billing_confirmation_link(
    obj: PreregistrationRemoteRealmBillingUser | PreregistrationRemoteServerBillingUser,
    confirmation_type: int,
    validity_in_minutes: int,
) -> str:
    url = create_confirmation_link(
        obj,
        confirmation_type,
        validity_in_minutes=validity_in_minutes,
        no_associated_realm_object=True,
    )

    # create_confirmation_link will create the url on the root subdomain, so we need to
    # do a hacky approach to change it into the self hosting management subdomain.
    new_hostname = f"{settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN}.{settings.EXTERNAL_HOST}"
    split_url = urlsplit(url)
    modified_url = split_url._replace(netloc=new_hostname)
    final_url = urlunsplit(modified_url)

    return final_url


@self_hosting_management_endpoint
@typed_endpoint
def remote_billing_legacy_server_login(
    request: HttpRequest,
    *,
    zulip_org_id: str | None = None,
    zulip_org_key: str | None = None,
    next_page: VALID_NEXT_PAGES_TYPE = None,
) -> HttpResponse:
    context: dict[str, Any] = {"next_page": next_page}
    if zulip_org_id is None or zulip_org_key is None:
        context.update({"error_message": False})
        return render(request, "corporate/billing/legacy_server_login.html", context)

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        remote_server = get_remote_server_by_uuid(zulip_org_id)
    except RemoteZulipServer.DoesNotExist:
        context.update(
            {
                "error_message": _(
                    "This zulip_org_id is not registered with Zulip's billing management system."
                )
            }
        )
        return render(request, "corporate/billing/legacy_server_login.html", context)

    if not constant_time_compare(zulip_org_key, remote_server.api_key):
        context.update({"error_message": _("Invalid zulip_org_key for this zulip_org_id.")})
        return render(request, "corporate/billing/legacy_server_login.html", context)

    if remote_server.deactivated:
        context.update({"error_message": _("Your server registration has been deactivated.")})
        return render(request, "corporate/billing/legacy_server_login.html", context)

    remote_server_uuid = str(remote_server.uuid)

    # We will want to render a page with a form that POSTs user-filled data to
    # the next endpoint in the flow. That endpoint needs to know the user is already
    # authenticated as a billing admin for this remote server, so we need to store
    # our usual IdentityDict structure in the session.
    request.session["remote_billing_identities"] = {}
    request.session["remote_billing_identities"][f"remote_server:{remote_server_uuid}"] = (
        LegacyServerIdentityDict(
            remote_server_uuid=remote_server_uuid,
            authenticated_at=datetime_to_timestamp(timezone_now()),
            # The lack of remote_billing_user_id indicates the auth hasn't been completed.
            # This means access to authenticated endpoints will be denied. Only proceeding
            # to the next step in the flow is permitted with this.
            remote_billing_user_id=None,
        )
    )

    context = {
        "remote_server_hostname": remote_server.hostname,
        "next_page": next_page,
        "action_url": reverse(
            remote_billing_legacy_server_confirm_login, args=(str(remote_server.uuid),)
        ),
    }
    return render(
        request,
        "corporate/billing/remote_billing_confirm_email_form.html",
        context=context,
    )


@self_hosting_management_endpoint
@typed_endpoint
def remote_billing_legacy_server_confirm_login(
    request: HttpRequest,
    *,
    server_uuid: PathOnly[str],
    email: str,
    next_page: VALID_NEXT_PAGES_TYPE = None,
) -> HttpResponse:
    """
    Takes the POST from the above form and sends confirmation email to the provided
    email address in order to verify. Only the confirmation link will grant
    a fully authenticated session.
    """

    from corporate.lib.stripe import BILLING_SUPPORT_EMAIL

    try:
        remote_server, remote_billing_user = get_remote_server_and_user_from_session(
            request, server_uuid=server_uuid
        )
        if remote_billing_user is not None:
            # This session is already fully authenticated, it doesn't make sense for
            # the user to be here. Just raise an exception so it's immediately caught
            # and the user is redirected to the beginning of the login flow where
            # they can re-auth.
            raise RemoteBillingAuthenticationError
    except (RemoteBillingIdentityExpiredError, RemoteBillingAuthenticationError):
        return HttpResponseRedirect(
            reverse("remote_billing_legacy_server_login", query={"next_page": next_page})
        )

    rate_limit_error_response = check_rate_limits(request, remote_server)
    if rate_limit_error_response is not None:
        return rate_limit_error_response

    obj = PreregistrationRemoteServerBillingUser.objects.create(
        email=email,
        remote_server=remote_server,
        next_page=next_page,
    )
    url = create_remote_billing_confirmation_link(
        obj,
        Confirmation.REMOTE_SERVER_BILLING_LEGACY_LOGIN,
        validity_in_minutes=LOGIN_CONFIRMATION_EMAIL_DURATION_HOURS * 60,
    )

    context = {
        "remote_server_hostname": remote_server.hostname,
        "confirmation_url": url,
        "billing_help_link": "https://zulip.com/help/self-hosted-billing",
        "billing_contact_email": BILLING_SUPPORT_EMAIL,
        "validity_in_hours": LOGIN_CONFIRMATION_EMAIL_DURATION_HOURS,
    }
    send_email(
        "zerver/emails/remote_billing_legacy_server_confirm_login",
        to_emails=[email],
        from_address=FromAddress.tokenized_no_reply_address(),
        language=get_language(),
        context=context,
    )

    return render(
        request,
        "corporate/billing/remote_billing_email_confirmation_sent.html",
        context={"email": email, "remote_server_hostname": remote_server.hostname},
    )


def has_live_plan_for_any_remote_realm_on_server(server: RemoteZulipServer) -> bool:
    has_plan_with_status_lt_live_threshold = CustomerPlan.objects.filter(
        customer__remote_realm__server=server,
        status__lt=CustomerPlan.LIVE_STATUS_THRESHOLD,
        customer__remote_realm=OuterRef("pk"),
    )

    return (
        RemoteRealm.objects.filter(server=server)
        .alias(has_plan=Exists(has_plan_with_status_lt_live_threshold))
        .filter(has_plan=True)
        .exists()
    )


@self_hosting_management_endpoint
@typed_endpoint
def remote_billing_legacy_server_from_login_confirmation_link(
    request: HttpRequest,
    *,
    confirmation_key: PathOnly[str],
    full_name: str | None = None,
    tos_consent: Literal[None, "true"] = None,
    enable_major_release_emails: Literal[None, "true", "false"] = None,
    enable_maintenance_release_emails: Literal[None, "true", "false"] = None,
) -> HttpResponse:
    """
    The user comes here via the confirmation link they received via email.
    """
    from corporate.lib.stripe import RemoteServerBillingSession

    if request.method not in ["GET", "POST"]:
        return HttpResponseNotAllowed(["GET", "POST"])

    try:
        prereg_object = get_object_from_key(
            confirmation_key,
            [Confirmation.REMOTE_SERVER_BILLING_LEGACY_LOGIN],
            # These links are reusable.
            mark_object_used=False,
        )
    except ConfirmationKeyError as exception:
        return render_confirmation_key_error(request, exception)
    assert isinstance(prereg_object, PreregistrationRemoteServerBillingUser)
    remote_server = prereg_object.remote_server
    remote_server_uuid = str(remote_server.uuid)

    remote_billing_user = RemoteServerBillingUser.objects.filter(
        remote_server=remote_server, email=prereg_object.email
    ).first()
    tos_consent_needed = remote_billing_user is None or is_tos_consent_needed_for_user(
        remote_billing_user
    )

    if request.method == "GET":
        context = {
            "remote_server_uuid": remote_server_uuid,
            "host": remote_server.hostname,
            "user_full_name": getattr(remote_billing_user, "full_name", None),
            "user_email": prereg_object.email,
            "tos_consent_needed": tos_consent_needed,
            "action_url": reverse(
                remote_billing_legacy_server_from_login_confirmation_link,
                args=(confirmation_key,),
            ),
            "legacy_server_confirmation_flow": True,
            "next_page": prereg_object.next_page,
        }
        return render(
            request,
            "corporate/billing/remote_billing_finalize_login_confirmation.html",
            context=context,
        )

    assert request.method == "POST"

    if tos_consent_needed and not tos_consent:
        # This shouldn't be possible without tampering with the form, so we
        # don't need a pretty error.
        raise JsonableError(_("You must accept the Terms of Service to proceed."))

    if (
        has_live_plan_for_any_remote_realm_on_server(remote_server)
        and prereg_object.next_page != "deactivate"
    ):
        return render(
            request,
            "corporate/billing/remote_server_login_error_for_any_realm_on_active_plan.html",
        )

    if remote_billing_user is None:
        assert full_name is not None
        assert settings.TERMS_OF_SERVICE_VERSION is not None
        remote_billing_user = RemoteServerBillingUser.objects.create(
            full_name=full_name,
            email=prereg_object.email,
            remote_server=remote_server,
            tos_version=settings.TERMS_OF_SERVICE_VERSION,
            enable_major_release_emails=enable_major_release_emails == "true",
            enable_maintenance_release_emails=enable_maintenance_release_emails == "true",
        )
        prereg_object.created_user = remote_billing_user
        prereg_object.save(update_fields=["created_user"])

    remote_billing_user.last_login = timezone_now()
    remote_billing_user.save(update_fields=["last_login"])

    # Refresh IdentityDict in the session. (Or create it
    # if the user came here e.g. in a different browser than they
    # started the login flow in.)
    request.session["remote_billing_identities"] = {}
    request.session["remote_billing_identities"][f"remote_server:{remote_server_uuid}"] = (
        LegacyServerIdentityDict(
            remote_server_uuid=remote_server_uuid,
            authenticated_at=datetime_to_timestamp(timezone_now()),
            # Having a remote_billing_user_id indicates the auth has been completed.
            # The user will now be granted access to authenticated endpoints.
            remote_billing_user_id=remote_billing_user.id,
        )
    )

    next_page = prereg_object.next_page
    assert next_page in VALID_NEXT_PAGES
    if next_page is not None:
        return HttpResponseRedirect(
            reverse(f"remote_server_{next_page}_page", args=(remote_server_uuid,))
        )
    elif remote_server.plan_type in [
        RemoteZulipServer.PLAN_TYPE_SELF_MANAGED,
        RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY,
    ]:
        # If they have a scheduled upgrade while on a complimentary access plan,
        # redirect to billing page.
        billing_session = RemoteServerBillingSession(remote_server)
        customer = billing_session.get_customer()
        if (
            customer is not None
            and billing_session.get_complimentary_access_next_plan_name(customer) is not None
        ):
            return HttpResponseRedirect(
                reverse("remote_server_billing_page", args=(remote_server_uuid,))
            )
        return HttpResponseRedirect(reverse("remote_server_plans_page", args=(remote_server_uuid,)))
    elif remote_server.plan_type == RemoteZulipServer.PLAN_TYPE_COMMUNITY:
        return HttpResponseRedirect(
            reverse("remote_server_sponsorship_page", args=(remote_server_uuid,))
        )
    else:
        return HttpResponseRedirect(
            reverse("remote_server_billing_page", args=(remote_server_uuid,))
        )


def generate_confirmation_link_for_server_deactivation(
    remote_server: RemoteZulipServer, validity_in_minutes: int
) -> str:
    obj = PreregistrationRemoteServerBillingUser.objects.create(
        email=remote_server.contact_email,
        remote_server=remote_server,
        next_page="deactivate",
    )
    url = create_remote_billing_confirmation_link(
        obj,
        Confirmation.REMOTE_SERVER_BILLING_LEGACY_LOGIN,
        validity_in_minutes=validity_in_minutes,
    )
    return url


def check_rate_limits(
    request: HttpRequest, remote_server: RemoteZulipServer
) -> HttpResponse | None:
    try:
        rate_limit_request_by_ip(request, domain="sends_email_by_ip")
    except RateLimitedError as e:
        # Our generic error response is good enough here, since this is
        # about the user's IP address, not their entire server.
        assert e.secs_to_freedom is not None
        return render(
            request,
            "zerver/portico_error_pages/rate_limit_exceeded.html",
            context={"retry_after": int(e.secs_to_freedom)},
            status=429,
        )

    try:
        rate_limit_remote_server(request, remote_server, "sends_email_by_remote_server")
    except RateLimitedError as e:
        # In this case it's the limit for the entire server the user belongs to
        # that was exceeded, so we need to show an error page explaining
        # that specific situation.
        assert e.secs_to_freedom is not None
        return render(
            request,
            "corporate/billing/remote_server_rate_limit_exceeded.html",
            context={"retry_after": int(e.secs_to_freedom)},
            status=429,
        )

    return None
