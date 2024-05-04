import logging
from contextlib import suppress
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
from urllib.parse import urlencode, urljoin

import orjson
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME, authenticate, get_backends
from django.contrib.sessions.backends.base import SessionBase
from django.core import validators
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.utils import IntegrityError
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import get_language
from django.views.defaults import server_error
from django_auth_ldap.backend import LDAPBackend, _LDAPUser

from confirmation.models import (
    Confirmation,
    ConfirmationKeyError,
    RealmCreationKey,
    create_confirmation_link,
    get_object_from_key,
    render_confirmation_key_error,
    validate_key,
)
from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import do_activate_mirror_dummy_user, do_create_user
from zerver.actions.default_streams import lookup_default_stream_groups
from zerver.actions.user_settings import (
    do_change_full_name,
    do_change_password,
    do_change_user_setting,
)
from zerver.context_processors import (
    get_realm_create_form_context,
    get_realm_from_request,
    login_context,
)
from zerver.decorator import add_google_analytics, do_login, require_post
from zerver.forms import (
    FindMyTeamForm,
    HomepageForm,
    RealmCreationForm,
    RealmRedirectForm,
    RegistrationForm,
)
from zerver.lib.email_validation import email_allowed_for_realm, validate_email_not_already_in_realm
from zerver.lib.exceptions import RateLimitedError
from zerver.lib.i18n import (
    get_browser_language_code,
    get_default_language_for_new_user,
    get_language_name,
)
from zerver.lib.pysa import mark_sanitized
from zerver.lib.rate_limiter import rate_limit_request_by_ip
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.send_email import EmailNotDeliveredError, FromAddress, send_email
from zerver.lib.sessions import get_expirable_session_var
from zerver.lib.subdomains import get_subdomain
from zerver.lib.url_encoding import append_url_query_string
from zerver.lib.users import get_accounts_for_email
from zerver.lib.validator import (
    check_capped_string,
    check_int_in,
    to_converted_or_fallback,
    to_non_negative_int,
    to_timezone_or_empty,
)
from zerver.lib.zephyr import compute_mit_user_fullname
from zerver.models import (
    MultiuseInvite,
    PreregistrationRealm,
    PreregistrationUser,
    Realm,
    RealmUserDefault,
    Stream,
    UserProfile,
)
from zerver.models.constants import MAX_LANGUAGE_ID_LENGTH
from zerver.models.realm_audit_logs import RealmAuditLog
from zerver.models.realms import (
    DisposableEmailError,
    DomainNotAllowedForRealmError,
    EmailContainsPlusError,
    get_org_type_display_name,
    get_realm,
    name_changes_disabled,
)
from zerver.models.streams import get_default_stream_groups
from zerver.models.users import get_source_profile, get_user_by_delivery_email
from zerver.views.auth import (
    create_preregistration_realm,
    create_preregistration_user,
    finish_desktop_flow,
    finish_mobile_flow,
    redirect_and_log_into_subdomain,
    redirect_to_deactivation_notice,
)
from zerver.views.errors import config_error
from zproject.backends import (
    ExternalAuthResult,
    NoMatchingLDAPUserError,
    ZulipLDAPAuthBackend,
    email_auth_enabled,
    email_belongs_to_ldap,
    get_external_method_dicts,
    ldap_auth_enabled,
    password_auth_enabled,
)

if settings.BILLING_ENABLED:
    from corporate.lib.registration import check_spare_licenses_available_for_registering_new_user
    from corporate.lib.stripe import LicenseLimitError


@has_request_variables
def get_prereg_key_and_redirect(
    request: HttpRequest, confirmation_key: str, full_name: Optional[str] = REQ(default=None)
) -> HttpResponse:
    """
    The purpose of this little endpoint is primarily to take a GET
    request to a long URL containing a confirmation key, and render
    a page that will via JavaScript immediately do a POST request to
    /accounts/register, so that the user can create their account on
    a page with a cleaner URL (and with the browser security and UX
    benefits of an HTTP POST having generated the page).

    The only thing it does before rendering that page is to check
    the validity of the confirmation link. This is redundant with a
    similar check in accounts_register, but it provides a slightly nicer
    user-facing error handling experience if the URL you visited is
    displayed in the browser. (E.g. you can debug that you
    accidentally adding an extra character after pasting).
    """
    try:
        prereg_object, realm_creation = check_prereg_key(request, confirmation_key)
    except ConfirmationKeyError as e:
        return render_confirmation_key_error(request, e)

    registration_url = reverse("accounts_register")
    if realm_creation:
        registration_url = reverse("realm_register")

    return render(
        request,
        "confirmation/confirm_preregistrationuser.html",
        context={
            "key": confirmation_key,
            "full_name": full_name,
            "registration_url": registration_url,
        },
    )


def check_prereg_key(
    request: HttpRequest, confirmation_key: str
) -> Tuple[Union[PreregistrationUser, PreregistrationRealm], bool]:
    """
    Checks if the Confirmation key is valid, returning the PreregistrationUser or
    PreregistrationRealm object in case of success and raising an appropriate
    ConfirmationKeyError otherwise.
    """
    confirmation_types = [
        Confirmation.USER_REGISTRATION,
        Confirmation.INVITATION,
        Confirmation.REALM_CREATION,
    ]

    prereg_object = get_object_from_key(
        confirmation_key, confirmation_types, mark_object_used=False
    )
    assert isinstance(prereg_object, (PreregistrationRealm, PreregistrationUser))

    confirmation_obj = prereg_object.confirmation.get()
    realm_creation = confirmation_obj.type == Confirmation.REALM_CREATION

    if realm_creation:
        assert isinstance(prereg_object, PreregistrationRealm)
        # Defensive assert to make sure no mix-up in how .status is set leading to reuse
        # of a PreregistrationRealm object.
        assert prereg_object.created_realm is None
    else:
        assert isinstance(prereg_object, PreregistrationUser)
        # Defensive assert to make sure no mix-up in how .status is set leading to reuse
        # of a PreregistrationUser object.
        assert prereg_object.created_user is None

    return prereg_object, realm_creation


def get_selected_realm_type_name(prereg_realm: Optional[PreregistrationRealm]) -> Optional[str]:
    if prereg_realm is None:
        # We show the selected realm type only when creating new realm.
        return None

    return get_org_type_display_name(prereg_realm.org_type)


def get_selected_realm_default_language_name(
    prereg_realm: Optional[PreregistrationRealm],
) -> Optional[str]:
    if prereg_realm is None:
        # We show the selected realm language only when creating new realm.
        return None

    return get_language_name(prereg_realm.default_language)


@add_google_analytics
@require_post
def realm_register(*args: Any, **kwargs: Any) -> HttpResponse:
    return registration_helper(*args, **kwargs)


@require_post
def accounts_register(*args: Any, **kwargs: Any) -> HttpResponse:
    return registration_helper(*args, **kwargs)


@has_request_variables
def registration_helper(
    request: HttpRequest,
    key: str = REQ(default=""),
    timezone: str = REQ(default="", converter=to_timezone_or_empty),
    from_confirmation: Optional[str] = REQ(default=None),
    form_full_name: Optional[str] = REQ("full_name", default=None),
    source_realm_id: Optional[int] = REQ(
        default=None, converter=to_converted_or_fallback(to_non_negative_int, None)
    ),
    form_is_demo_organization: Optional[str] = REQ("is_demo_organization", default=None),
) -> HttpResponse:
    try:
        prereg_object, realm_creation = check_prereg_key(request, key)
    except ConfirmationKeyError as e:
        return render_confirmation_key_error(request, e)

    email = prereg_object.email
    prereg_realm = None
    prereg_user = None
    if realm_creation:
        assert isinstance(prereg_object, PreregistrationRealm)
        prereg_realm = prereg_object
        password_required = True
        role = UserProfile.ROLE_REALM_OWNER
    else:
        assert isinstance(prereg_object, PreregistrationUser)
        prereg_user = prereg_object
        password_required = prereg_object.password_required
        role = prereg_object.invited_as

    if form_is_demo_organization is None:
        demo_organization_creation = False
    else:
        # Check the explicit strings that return false
        # in django.forms.BooleanField.to_python.
        false_strings = ("false", "0")
        demo_organization_creation = form_is_demo_organization.strip().lower() not in false_strings

    if email == "":
        # Do not attempt to validate email for users without an email address.
        # The assertions here are to help document the only circumstance under which
        # this condition should be possible.
        assert realm_creation and demo_organization_creation
        # TODO: Remove settings.DEVELOPMENT when demo organization feature ready
        # to be fully implemented.
        assert settings.DEVELOPMENT
    else:
        try:
            validators.validate_email(email)
        except ValidationError:
            return TemplateResponse(
                request,
                "zerver/invalid_email.html",
                context={"invalid_email": True},
                status=400,
            )

    if realm_creation:
        # For creating a new realm, there is no existing realm or domain
        realm = None
    else:
        assert prereg_user is not None
        assert prereg_user.realm is not None
        if get_subdomain(request) != prereg_user.realm.string_id:
            return render_confirmation_key_error(
                request, ConfirmationKeyError(ConfirmationKeyError.DOES_NOT_EXIST)
            )
        realm = prereg_user.realm
        try:
            email_allowed_for_realm(email, realm)
        except DomainNotAllowedForRealmError:
            return TemplateResponse(
                request,
                "zerver/invalid_email.html",
                context={"realm_name": realm.name, "closed_domain": True},
                status=400,
            )
        except DisposableEmailError:
            return TemplateResponse(
                request,
                "zerver/invalid_email.html",
                context={"realm_name": realm.name, "disposable_emails_not_allowed": True},
                status=400,
            )
        except EmailContainsPlusError:
            return TemplateResponse(
                request,
                "zerver/invalid_email.html",
                context={"realm_name": realm.name, "email_contains_plus": True},
                status=400,
            )

        if realm.deactivated:
            # The user is trying to register for a deactivated realm. Advise them to
            # contact support.
            return redirect_to_deactivation_notice()

        try:
            validate_email_not_already_in_realm(realm, email)
        except ValidationError:
            return redirect_to_email_login_url(email)

        if settings.BILLING_ENABLED:
            try:
                check_spare_licenses_available_for_registering_new_user(realm, email, role=role)
            except LicenseLimitError:
                return TemplateResponse(request, "zerver/no_spare_licenses.html")

    name_validated = False
    require_ldap_password = False

    if from_confirmation:
        with suppress(KeyError):
            del request.session["authenticated_full_name"]

        ldap_full_name = None
        if settings.POPULATE_PROFILE_VIA_LDAP:
            # If the user can be found in LDAP, we'll take the full name from the directory,
            # and further down create a form pre-filled with it.
            for backend in get_backends():
                if isinstance(backend, LDAPBackend):
                    try:
                        ldap_username = backend.django_to_ldap_username(email)
                    except NoMatchingLDAPUserError:
                        logging.warning("New account email %s could not be found in LDAP", email)
                        break

                    # Note that this `ldap_user` object is not a
                    # `ZulipLDAPUser` with a `Realm` attached, so
                    # calling `.populate_user()` on it will crash.
                    # This is OK, since we're just accessing this user
                    # to extract its name.
                    #
                    # TODO: We should potentially be accessing this
                    # user to sync its initial avatar and custom
                    # profile fields as well, if we indeed end up
                    # creating a user account through this flow,
                    # rather than waiting until `manage.py
                    # sync_ldap_user_data` runs to populate it.
                    ldap_user = _LDAPUser(backend, ldap_username)

                    try:
                        ldap_full_name = backend.get_mapped_name(ldap_user)
                    except TypeError:
                        break

                    # Check whether this is ZulipLDAPAuthBackend,
                    # which is responsible for authentication and
                    # requires that LDAP accounts enter their LDAP
                    # password to register, or ZulipLDAPUserPopulator,
                    # which just populates UserProfile fields (no auth).
                    require_ldap_password = isinstance(backend, ZulipLDAPAuthBackend)
                    break

        initial_data = {}
        if realm_creation:
            assert prereg_realm is not None
            initial_data = {
                "realm_name": prereg_realm.name,
                "realm_type": prereg_realm.org_type,
                "realm_default_language": prereg_realm.default_language,
                "realm_subdomain": prereg_realm.string_id,
            }

        if ldap_full_name:
            # We don't add "full_name" to initial here, because if the realm
            # already exists and form is complete (that is, no additional fields
            # need to be filled out by the user) we want the form to validate,
            # so they can be directly registered without having to go through
            # this interstitial.
            form = RegistrationForm(
                {"full_name": ldap_full_name},
                initial=initial_data,
                realm_creation=realm_creation,
                realm=realm,
            )
            request.session["authenticated_full_name"] = ldap_full_name
            name_validated = True
        elif realm is not None and realm.is_zephyr_mirror_realm:
            # For MIT users, we can get an authoritative name from Hesiod.
            # Technically we should check that this is actually an MIT
            # realm, but we can cross that bridge if we ever get a non-MIT
            # zephyr mirroring realm.
            hesiod_name = compute_mit_user_fullname(email)
            form = RegistrationForm(
                initial={"full_name": hesiod_name if "@" not in hesiod_name else ""},
                realm_creation=realm_creation,
                realm=realm,
            )
            name_validated = True
        elif prereg_user is not None and prereg_user.full_name:
            if prereg_user.full_name_validated:
                request.session["authenticated_full_name"] = prereg_user.full_name
                name_validated = True
                form = RegistrationForm(
                    {"full_name": prereg_user.full_name},
                    initial=initial_data,
                    realm_creation=realm_creation,
                    realm=realm,
                )
            else:
                initial_data["full_name"] = prereg_user.full_name
                form = RegistrationForm(
                    initial=initial_data,
                    realm_creation=realm_creation,
                    realm=realm,
                )
        elif form_full_name is not None:
            initial_data["full_name"] = form_full_name
            form = RegistrationForm(
                initial=initial_data,
                realm_creation=realm_creation,
                realm=realm,
            )
        else:
            form = RegistrationForm(
                initial=initial_data, realm_creation=realm_creation, realm=realm
            )
    else:
        postdata = request.POST.copy()
        if name_changes_disabled(realm):
            # If we populate profile information via LDAP and we have a
            # verified name from you on file, use that. Otherwise, fall
            # back to the full name in the request.
            try:
                postdata.update(full_name=request.session["authenticated_full_name"])
                name_validated = True
            except KeyError:
                pass
        form = RegistrationForm(postdata, realm_creation=realm_creation, realm=realm)

    if not (password_auth_enabled(realm) and password_required):
        form["password"].field.required = False

    if form.is_valid():
        if password_auth_enabled(realm) and form["password"].field.required:
            password = form.cleaned_data["password"]
        else:
            # If the user wasn't prompted for a password when
            # completing the authentication form (because they're
            # signing up with SSO and no password is required), set
            # the password field to `None` (Which causes Django to
            # create an unusable password).
            password = None

        if realm_creation:
            string_id = form.cleaned_data["realm_subdomain"]
            realm_name = form.cleaned_data["realm_name"]
            realm_type = form.cleaned_data["realm_type"]
            realm_default_language = form.cleaned_data["realm_default_language"]
            is_demo_organization = form.cleaned_data["is_demo_organization"]
            how_realm_creator_found_zulip = RealmAuditLog.HOW_REALM_CREATOR_FOUND_ZULIP_OPTIONS[
                form.cleaned_data["how_realm_creator_found_zulip"]
            ]
            how_realm_creator_found_zulip_extra_context = ""
            if (
                how_realm_creator_found_zulip
                == RealmAuditLog.HOW_REALM_CREATOR_FOUND_ZULIP_OPTIONS["other"]
            ):
                how_realm_creator_found_zulip_extra_context = form.cleaned_data[
                    "how_realm_creator_found_zulip_other_text"
                ]
            elif (
                how_realm_creator_found_zulip
                == RealmAuditLog.HOW_REALM_CREATOR_FOUND_ZULIP_OPTIONS["ad"]
            ):
                how_realm_creator_found_zulip_extra_context = form.cleaned_data[
                    "how_realm_creator_found_zulip_where_ad"
                ]
            elif (
                how_realm_creator_found_zulip
                == RealmAuditLog.HOW_REALM_CREATOR_FOUND_ZULIP_OPTIONS["existing_user"]
            ):
                how_realm_creator_found_zulip_extra_context = form.cleaned_data[
                    "how_realm_creator_found_zulip_which_organization"
                ]

            realm = do_create_realm(
                string_id,
                realm_name,
                org_type=realm_type,
                default_language=realm_default_language,
                is_demo_organization=is_demo_organization,
                prereg_realm=prereg_realm,
                how_realm_creator_found_zulip=how_realm_creator_found_zulip,
                how_realm_creator_found_zulip_extra_context=how_realm_creator_found_zulip_extra_context,
            )
        assert realm is not None

        full_name = form.cleaned_data["full_name"]
        enable_marketing_emails = form.cleaned_data["enable_marketing_emails"]
        email_address_visibility = form.cleaned_data["email_address_visibility"]
        default_stream_group_names = request.POST.getlist("default_stream_group")
        default_stream_groups = lookup_default_stream_groups(default_stream_group_names, realm)

        if source_realm_id is not None:
            # Non-integer realm_id values like "string" are treated
            # like the "Do not import" value of "".
            source_profile: Optional[UserProfile] = get_source_profile(email, source_realm_id)
        else:
            source_profile = None

        if not realm_creation:
            try:
                existing_user_profile: Optional[UserProfile] = get_user_by_delivery_email(
                    email, realm
                )
            except UserProfile.DoesNotExist:
                existing_user_profile = None
        else:
            existing_user_profile = None

        user_profile: Optional[UserProfile] = None
        return_data: Dict[str, bool] = {}
        if ldap_auth_enabled(realm):
            # If the user was authenticated using an external SSO
            # mechanism like Google or GitHub auth, then authentication
            # will have already been done before creating the
            # PreregistrationUser object with password_required=False, and
            # so we don't need to worry about passwords.
            #
            # If instead the realm is using EmailAuthBackend, we will
            # set their password above.
            #
            # But if the realm is using LDAPAuthBackend, we need to verify
            # their LDAP password (which will, as a side effect, create
            # the user account) here using authenticate.
            # prereg_user.realm_creation carries the information about whether
            # we're in realm creation mode, and the ldap flow will handle
            # that and create the user with the appropriate parameters.
            user = authenticate(
                request=request,
                username=email,
                password=password,
                realm=realm,
                prereg_user=prereg_user,
                prereg_realm=prereg_realm,
                return_data=return_data,
            )
            if user is None:
                # This logic is security-sensitive. The user has NOT been successfully authenticated
                # with LDAP and we need to carefully decide whether they should be permitted to proceed
                # with account creation anyway or be stopped. There are three scenarios to consider:
                #
                # 1. EmailAuthBackend is enabled for the realm. That explicitly means that a user
                #    with a valid confirmation link should be able to create an account, because
                #    they were invited or organization permissions allowed sign up.
                # 2. EmailAuthBackend is disabled - that means the organization wants to be authenticating
                #    users with an external source (LDAP or one of the ExternalAuthMethods). If the user
                #    came here through one of the ExternalAuthMethods, their identity can be considered
                #    verified and account creation can proceed.
                # 3. EmailAuthBackend is disabled and the user did not come here through an ExternalAuthMethod.
                #    That means they came here by entering their email address on the registration page
                #    and clicking the confirmation link received. That means their identity needs to be
                #    verified with LDAP - and that has just failed above. Thus the account should NOT be
                #    created.
                #
                if email_auth_enabled(realm):
                    can_use_different_backend = True
                # We can identify the user came here through an ExternalAuthMethod by password_required
                # being set to False on the PreregistrationUser object.
                elif len(get_external_method_dicts(realm)) > 0 and not password_required:
                    can_use_different_backend = True
                else:
                    can_use_different_backend = False

                if settings.LDAP_APPEND_DOMAIN:
                    # In LDAP_APPEND_DOMAIN configurations, we don't allow making a non-LDAP account
                    # if the email matches the ldap domain.
                    can_use_different_backend = can_use_different_backend and (
                        not email_belongs_to_ldap(realm, email)
                    )
                if return_data.get("no_matching_ldap_user") and can_use_different_backend:
                    # If both the LDAP and Email or Social auth backends are
                    # enabled, and there's no matching user in the LDAP
                    # directory then the intent is to create a user in the
                    # realm with their email outside the LDAP organization
                    # (with e.g. a password stored in the Zulip database,
                    # not LDAP).  So we fall through and create the new
                    # account.
                    pass
                else:
                    # TODO: This probably isn't going to give a
                    # user-friendly error message, but it doesn't
                    # particularly matter, because the registration form
                    # is hidden for most users.
                    view_url = reverse("login")
                    query = urlencode({"email": email})
                    redirect_url = append_url_query_string(view_url, query)
                    return HttpResponseRedirect(redirect_url)
            else:
                assert isinstance(user, UserProfile)
                user_profile = user
                if not realm_creation:
                    # Since we'll have created a user, we now just log them in.
                    return login_and_go_to_home(request, user_profile)
                # With realm_creation=True, we're going to return further down,
                # after finishing up the creation process.

        if existing_user_profile is not None and existing_user_profile.is_mirror_dummy:
            user_profile = existing_user_profile
            do_activate_mirror_dummy_user(user_profile, acting_user=user_profile)
            do_change_password(user_profile, password)
            do_change_full_name(user_profile, full_name, user_profile)
            do_change_user_setting(user_profile, "timezone", timezone, acting_user=user_profile)
            do_change_user_setting(
                user_profile,
                "default_language",
                get_default_language_for_new_user(realm, request=request),
                acting_user=None,
            )
            # TODO: When we clean up the `do_activate_mirror_dummy_user` code path,
            # make it respect invited_as_admin / is_realm_admin.

        if user_profile is None:
            try:
                user_profile = do_create_user(
                    email,
                    password,
                    realm,
                    full_name,
                    prereg_user=prereg_user,
                    prereg_realm=prereg_realm,
                    role=role,
                    tos_version=settings.TERMS_OF_SERVICE_VERSION,
                    timezone=timezone,
                    default_language=get_default_language_for_new_user(realm, request=request),
                    default_stream_groups=default_stream_groups,
                    source_profile=source_profile,
                    realm_creation=realm_creation,
                    acting_user=None,
                    enable_marketing_emails=enable_marketing_emails,
                    email_address_visibility=email_address_visibility,
                )
            except IntegrityError:
                # Race condition making the user, leading to a
                # duplicate email address.  Redirect them to the login
                # form.
                return redirect_to_email_login_url(email)

        if realm_creation:
            # Because for realm creation, registration happens on the
            # root domain, we need to log them into the subdomain for
            # their new realm.
            return redirect_and_log_into_subdomain(
                ExternalAuthResult(user_profile=user_profile, data_dict={"is_realm_creation": True})
            )

        # This dummy_backend check below confirms the user is
        # authenticating to the correct subdomain.
        auth_result = authenticate(
            request=request,
            username=user_profile.delivery_email,
            realm=realm,
            return_data=return_data,
            use_dummy_backend=True,
        )
        if return_data.get("invalid_subdomain"):
            # By construction, this should never happen.
            logging.error(
                "Subdomain mismatch in registration %s: %s",
                realm.subdomain,
                user_profile.delivery_email,
            )
            return redirect("/")

        assert isinstance(auth_result, UserProfile)
        return login_and_go_to_home(request, auth_result)

    default_email_address_visibility = None
    if realm is not None:
        realm_user_default = RealmUserDefault.objects.get(realm=realm)
        default_email_address_visibility = realm_user_default.email_address_visibility

    context = {
        "form": form,
        "email": email,
        "key": key,
        "full_name": request.session.get("authenticated_full_name", None),
        "lock_name": name_validated and name_changes_disabled(realm),
        # password_auth_enabled is normally set via our context processor,
        # but for the registration form, there is no logged in user yet, so
        # we have to set it here.
        "creating_new_realm": realm_creation,
        "password_required": password_auth_enabled(realm) and password_required,
        "require_ldap_password": require_ldap_password,
        "password_auth_enabled": password_auth_enabled(realm),
        "default_stream_groups": [] if realm is None else get_default_stream_groups(realm),
        "accounts": get_accounts_for_email(email),
        "MAX_NAME_LENGTH": str(UserProfile.MAX_NAME_LENGTH),
        "MAX_PASSWORD_LENGTH": str(form.MAX_PASSWORD_LENGTH),
        "corporate_enabled": settings.CORPORATE_ENABLED,
        "default_email_address_visibility": default_email_address_visibility,
        "selected_realm_type_name": get_selected_realm_type_name(prereg_realm),
        "selected_realm_default_language_name": get_selected_realm_default_language_name(
            prereg_realm
        ),
        "email_address_visibility_admins_only": RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_ADMINS,
        "email_address_visibility_moderators": RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_MODERATORS,
        "email_address_visibility_nobody": RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_NOBODY,
        "email_address_visibility_options_dict": UserProfile.EMAIL_ADDRESS_VISIBILITY_ID_TO_NAME_MAP,
        "how_realm_creator_found_zulip_options": RealmAuditLog.HOW_REALM_CREATOR_FOUND_ZULIP_OPTIONS.items(),
    }
    # Add context for realm creation part of the form.
    context.update(get_realm_create_form_context())

    return TemplateResponse(request, "zerver/register.html", context=context)


def login_and_go_to_home(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    mobile_flow_otp = get_expirable_session_var(
        request.session, "registration_mobile_flow_otp", delete=True
    )
    desktop_flow_otp = get_expirable_session_var(
        request.session, "registration_desktop_flow_otp", delete=True
    )
    if mobile_flow_otp is not None:
        return finish_mobile_flow(request, user_profile, mobile_flow_otp)
    elif desktop_flow_otp is not None:
        params_to_store_in_authenticated_session = orjson.loads(
            get_expirable_session_var(
                request.session,
                "registration_desktop_flow_params_to_store_in_authenticated_session",
                default_value="{}",
                delete=True,
            )
        )
        return finish_desktop_flow(
            request, user_profile, desktop_flow_otp, params_to_store_in_authenticated_session
        )

    do_login(request, user_profile)
    # Using 'mark_sanitized' to work around false positive where Pysa thinks
    # that 'user_profile' is user-controlled
    return HttpResponseRedirect(mark_sanitized(user_profile.realm.uri) + reverse("home"))


def prepare_activation_url(
    email: str,
    session: SessionBase,
    *,
    realm: Optional[Realm],
    streams: Optional[Iterable[Stream]] = None,
    invited_as: Optional[int] = None,
    multiuse_invite: Optional[MultiuseInvite] = None,
) -> str:
    """
    Send an email with a confirmation link to the provided e-mail so the user
    can complete their registration.
    """
    prereg_user = create_preregistration_user(email, realm, multiuse_invite=multiuse_invite)

    if streams is not None:
        prereg_user.streams.set(streams)

    if invited_as is not None:
        prereg_user.invited_as = invited_as
        prereg_user.save()

    confirmation_type = Confirmation.USER_REGISTRATION

    activation_url = create_confirmation_link(prereg_user, confirmation_type)
    return activation_url


def prepare_realm_activation_url(
    email: str,
    session: SessionBase,
    realm_name: str,
    string_id: str,
    org_type: int,
    default_language: str,
) -> str:
    prereg_realm = create_preregistration_realm(
        email, realm_name, string_id, org_type, default_language
    )
    activation_url = create_confirmation_link(
        prereg_realm, Confirmation.REALM_CREATION, no_associated_realm_object=True
    )

    if settings.DEVELOPMENT:
        session["confirmation_key"] = {"confirmation_key": activation_url.split("/")[-1]}
    return activation_url


def send_confirm_registration_email(
    email: str,
    activation_url: str,
    *,
    realm: Optional[Realm] = None,
    realm_subdomain: Optional[str] = None,
    realm_type: Optional[int] = None,
    request: Optional[HttpRequest] = None,
) -> None:
    org_url = ""
    org_type = ""
    if realm is None:
        assert realm_subdomain is not None
        org_url = f"{realm_subdomain}.{settings.EXTERNAL_HOST}"
        assert realm_type is not None
        org_type = get_org_type_display_name(realm_type)
    send_email(
        "zerver/emails/confirm_registration",
        to_emails=[email],
        from_address=FromAddress.tokenized_no_reply_address(),
        language=get_language() if request is not None else None,
        context={
            "create_realm": realm is None,
            "activate_url": activation_url,
            "corporate_enabled": settings.CORPORATE_ENABLED,
            "organization_url": org_url,
            "organization_type": org_type,
        },
        realm=realm,
        request=request,
    )


def redirect_to_email_login_url(email: str) -> HttpResponseRedirect:
    login_url = reverse("login")
    redirect_url = append_url_query_string(
        login_url, urlencode({"email": email, "already_registered": 1})
    )
    return HttpResponseRedirect(redirect_url)


@add_google_analytics
def create_realm(request: HttpRequest, creation_key: Optional[str] = None) -> HttpResponse:
    try:
        key_record = validate_key(creation_key)
    except RealmCreationKey.InvalidError:
        return TemplateResponse(
            request,
            "zerver/realm_creation_link_invalid.html",
        )
    if not settings.OPEN_REALM_CREATION and key_record is None:
        return TemplateResponse(
            request,
            "zerver/realm_creation_disabled.html",
        )

    # When settings.OPEN_REALM_CREATION is enabled, anyone can create a new realm,
    # with a few restrictions on their email address.
    if request.method == "POST":
        form = RealmCreationForm(request.POST)
        if form.is_valid():
            try:
                rate_limit_request_by_ip(request, domain="sends_email_by_ip")
            except RateLimitedError as e:
                assert e.secs_to_freedom is not None
                return TemplateResponse(
                    request,
                    "zerver/rate_limit_exceeded.html",
                    context={"retry_after": int(e.secs_to_freedom)},
                    status=429,
                )

            email = form.cleaned_data["email"]
            realm_name = form.cleaned_data["realm_name"]
            realm_type = form.cleaned_data["realm_type"]
            realm_default_language = form.cleaned_data["realm_default_language"]
            realm_subdomain = form.cleaned_data["realm_subdomain"]
            activation_url = prepare_realm_activation_url(
                email,
                request.session,
                realm_name,
                realm_subdomain,
                realm_type,
                realm_default_language,
            )
            if key_record is not None and key_record.presume_email_valid:
                # The user has a token created from the server command line;
                # skip confirming the email is theirs, taking their word for it.
                # This is essential on first install if the admin hasn't stopped
                # to configure outbound email up front, or it isn't working yet.
                key_record.delete()
                return HttpResponseRedirect(activation_url)

            try:
                send_confirm_registration_email(
                    email,
                    activation_url,
                    realm_subdomain=realm_subdomain,
                    realm_type=realm_type,
                    request=request,
                )
            except EmailNotDeliveredError:
                logging.exception("Failed to deliver email during realm creation")
                if settings.CORPORATE_ENABLED:
                    return server_error(request)
                return config_error(request, "smtp")

            if key_record is not None:
                key_record.delete()
            new_realm_send_confirm_url = reverse("new_realm_send_confirm")
            query = urlencode(
                {
                    "email": email,
                    "realm_name": realm_name,
                    "realm_type": realm_type,
                    "realm_default_language": realm_default_language,
                    "realm_subdomain": realm_subdomain,
                }
            )
            url = append_url_query_string(new_realm_send_confirm_url, query)
            return HttpResponseRedirect(url)
    else:
        default_language_code = get_browser_language_code(request)
        if default_language_code is None:
            default_language_code = "en"

        initial_data = {
            "realm_default_language": default_language_code,
        }
        form = RealmCreationForm(initial=initial_data)

    context = get_realm_create_form_context()
    context.update(
        {
            "form": form,
            "current_url": request.get_full_path,
        }
    )
    return TemplateResponse(
        request,
        "zerver/create_realm.html",
        context=context,
    )


@has_request_variables
def signup_send_confirm(request: HttpRequest, email: str = REQ("email")) -> HttpResponse:
    try:
        # Because we interpolate the email directly into the template
        # from the query parameter, do a simple validation that it
        # looks a at least a bit like an email address.
        validators.validate_email(email)
    except ValidationError:
        return TemplateResponse(
            request,
            "zerver/invalid_email.html",
            context={"invalid_email": True},
            status=400,
        )
    return TemplateResponse(
        request,
        "zerver/accounts_send_confirm.html",
        context={"email": email},
    )


@add_google_analytics
@has_request_variables
def new_realm_send_confirm(
    request: HttpRequest,
    email: str = REQ("email"),
    realm_name: str = REQ(str_validator=check_capped_string(Realm.MAX_REALM_NAME_LENGTH)),
    realm_type: int = REQ(json_validator=check_int_in(Realm.ORG_TYPE_IDS)),
    realm_default_language: str = REQ(str_validator=check_capped_string(MAX_LANGUAGE_ID_LENGTH)),
    realm_subdomain: str = REQ(str_validator=check_capped_string(Realm.MAX_REALM_SUBDOMAIN_LENGTH)),
) -> HttpResponse:
    return TemplateResponse(
        request,
        "zerver/accounts_send_confirm.html",
        context={
            "email": email,
            # Using "new_realm_name" key here since "realm_name" key is already present in
            # the context provided by zulip_default_context and it is "None" during realm
            # creation.
            "new_realm_name": realm_name,
            "realm_type": realm_type,
            "realm_default_language": realm_default_language,
            "realm_subdomain": realm_subdomain,
            "realm_creation": True,
        },
    )


def accounts_home(
    request: HttpRequest,
    multiuse_object_key: str = "",
    multiuse_object: Optional[MultiuseInvite] = None,
) -> HttpResponse:
    try:
        realm = get_realm(get_subdomain(request))
    except Realm.DoesNotExist:
        return HttpResponseRedirect(reverse(find_account))
    if realm.deactivated:
        return redirect_to_deactivation_notice()

    from_multiuse_invite = False
    streams_to_subscribe = None
    invited_as = None

    if multiuse_object:
        # multiuse_object's realm should have been validated by the caller,
        # so this code shouldn't be reachable with a multiuse_object which
        # has its realm mismatching the realm of the request.
        assert realm == multiuse_object.realm

        streams_to_subscribe = multiuse_object.streams.all()
        from_multiuse_invite = True
        invited_as = multiuse_object.invited_as

    if request.method == "POST":
        form = HomepageForm(
            request.POST,
            realm=realm,
            from_multiuse_invite=from_multiuse_invite,
            invited_as=invited_as,
        )
        if form.is_valid():
            try:
                rate_limit_request_by_ip(request, domain="sends_email_by_ip")
            except RateLimitedError as e:
                assert e.secs_to_freedom is not None
                return render(
                    request,
                    "zerver/rate_limit_exceeded.html",
                    context={"retry_after": int(e.secs_to_freedom)},
                    status=429,
                )

            email = form.cleaned_data["email"]

            try:
                validate_email_not_already_in_realm(realm, email)
            except ValidationError:
                return redirect_to_email_login_url(email)

            activation_url = prepare_activation_url(
                email,
                request.session,
                realm=realm,
                streams=streams_to_subscribe,
                invited_as=invited_as,
                multiuse_invite=multiuse_object,
            )
            try:
                send_confirm_registration_email(email, activation_url, request=request, realm=realm)
            except EmailNotDeliveredError:
                logging.exception("Failed to deliver email during user registration")
                if settings.CORPORATE_ENABLED:
                    return server_error(request)
                return config_error(request, "smtp")
            signup_send_confirm_url = reverse("signup_send_confirm")
            query = urlencode({"email": email})
            url = append_url_query_string(signup_send_confirm_url, query)
            return HttpResponseRedirect(url)

    else:
        form = HomepageForm(realm=realm)
    context = login_context(request)
    context.update(
        form=form,
        current_url=request.get_full_path,
        multiuse_object_key=multiuse_object_key,
        from_multiuse_invite=from_multiuse_invite,
    )
    return render(request, "zerver/accounts_home.html", context=context)


def accounts_home_from_multiuse_invite(request: HttpRequest, confirmation_key: str) -> HttpResponse:
    realm = get_realm_from_request(request)
    multiuse_object: Optional[MultiuseInvite] = None
    try:
        confirmation_obj = get_object_from_key(
            confirmation_key, [Confirmation.MULTIUSE_INVITE], mark_object_used=False
        )
        assert isinstance(confirmation_obj, MultiuseInvite)
        multiuse_object = confirmation_obj
        if realm != multiuse_object.realm:
            return render(request, "confirmation/link_does_not_exist.html", status=404)
        # Required for OAuth 2
    except ConfirmationKeyError as exception:
        if realm is None or realm.invite_required:
            return render_confirmation_key_error(request, exception)
    return accounts_home(
        request, multiuse_object_key=confirmation_key, multiuse_object=multiuse_object
    )


@has_request_variables
def find_account(request: HttpRequest) -> HttpResponse:
    url = reverse("find_account")
    form = FindMyTeamForm()
    emails: List[str] = []
    if request.method == "POST":
        form = FindMyTeamForm(request.POST)
        if form.is_valid():
            # Note: Show all the emails in the POST request response
            # otherwise this feature can be used to ascertain which
            # email addresses are associated with Zulip.
            emails = form.cleaned_data["emails"]
            for i in range(len(emails)):
                try:
                    rate_limit_request_by_ip(request, domain="sends_email_by_ip")
                except RateLimitedError as e:
                    assert e.secs_to_freedom is not None
                    return render(
                        request,
                        "zerver/rate_limit_exceeded.html",
                        context={"retry_after": int(e.secs_to_freedom)},
                        status=429,
                    )

            # Django doesn't support __iexact__in lookup with EmailField, so we have
            # to use Qs to get around that without needing to do multiple queries.
            emails_q = Q()
            for email in emails:
                emails_q |= Q(delivery_email__iexact=email)

            user_profiles = UserProfile.objects.filter(
                emails_q, is_active=True, is_bot=False, realm__deactivated=False
            )

            # We organize the data in preparation for sending exactly
            # one outgoing email per provided email address, with each
            # email listing all of the accounts that email address has
            # with the current Zulip server.
            emails_account_found: Set[str] = set()
            context: Dict[str, Dict[str, Any]] = {}
            for user in user_profiles:
                key = user.delivery_email.lower()
                context.setdefault(key, {})
                context[key].setdefault("realms", [])
                context[key]["realms"].append(user.realm)
                # This value will end up being the last user ID among
                # matching accounts; since it's only used for minor
                # details like language, that arbitrary choice is OK.
                context[key]["to_user_id"] = user.id
                emails_account_found.add(user.delivery_email)

            # Links in find_team emails use the server's information
            # and not any particular realm's information.
            external_host_base_url = f"{settings.EXTERNAL_URI_SCHEME}{settings.EXTERNAL_HOST}"
            help_base_url = f"{external_host_base_url}/help"
            help_reset_password_link = (
                f"{help_base_url}/change-your-password#if-youve-forgotten-or-never-had-a-password"
            )
            help_logging_in_link = f"{help_base_url}/logging-in#find-the-zulip-log-in-url"
            find_accounts_link = f"{external_host_base_url}/accounts/find/"

            for delivery_email, realm_context in context.items():
                send_email(
                    "zerver/emails/find_team",
                    to_user_ids=[realm_context["to_user_id"]],
                    context={
                        "account_found": True,
                        "external_host": settings.EXTERNAL_HOST,
                        "corporate_enabled": settings.CORPORATE_ENABLED,
                        "help_reset_password_link": help_reset_password_link,
                        "realms": realm_context["realms"],
                        "email": delivery_email,
                    },
                    from_address=FromAddress.SUPPORT,
                    request=request,
                )

            emails_lower_with_account = {email.lower() for email in emails_account_found}
            emails_without_account: Set[str] = {
                email for email in emails if email.lower() not in emails_lower_with_account
            }
            if emails_without_account:
                send_email(
                    "zerver/emails/find_team",
                    to_emails=list(emails_without_account),
                    context=(
                        {
                            "account_found": False,
                            "external_host": settings.EXTERNAL_HOST,
                            "corporate_enabled": settings.CORPORATE_ENABLED,
                            "find_accounts_link": find_accounts_link,
                            "help_logging_in_link": help_logging_in_link,
                        }
                    ),
                    from_address=FromAddress.SUPPORT,
                    request=request,
                )
    return render(
        request,
        "zerver/find_account.html",
        context={"form": form, "current_url": url, "emails": emails},
    )


@has_request_variables
def realm_redirect(request: HttpRequest, next: str = REQ(default="")) -> HttpResponse:
    if request.method == "POST":
        form = RealmRedirectForm(request.POST)
        if form.is_valid():
            subdomain = form.cleaned_data["subdomain"]
            realm = get_realm(subdomain)
            redirect_to = urljoin(realm.uri, settings.HOME_NOT_LOGGED_IN)

            if next:
                redirect_to = append_url_query_string(
                    redirect_to, urlencode({REDIRECT_FIELD_NAME: next})
                )

            return HttpResponseRedirect(redirect_to)
    else:
        form = RealmRedirectForm()

    return render(request, "zerver/realm_redirect.html", context={"form": form})
