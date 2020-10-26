import logging
import smtplib
import urllib
from typing import Dict, List, Optional

import pytz
from django.conf import settings
from django.contrib.auth import authenticate, get_backends
from django.core import validators
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import ugettext as _
from django_auth_ldap.backend import LDAPBackend, _LDAPUser

from confirmation import settings as confirmation_settings
from confirmation.models import (
    Confirmation,
    ConfirmationKeyException,
    RealmCreationKey,
    create_confirmation_link,
    get_object_from_key,
    render_confirmation_key_error,
    validate_key,
)
from zerver.context_processors import get_realm_from_request, login_context
from zerver.decorator import do_login, require_post
from zerver.forms import (
    FindMyTeamForm,
    HomepageForm,
    RealmCreationForm,
    RealmRedirectForm,
    RegistrationForm,
)
from zerver.lib.actions import (
    bulk_add_subscriptions,
    do_activate_user,
    do_change_full_name,
    do_change_password,
    do_create_realm,
    do_create_user,
    do_set_user_display_setting,
    lookup_default_stream_groups,
)
from zerver.lib.create_user import get_role_for_new_user
from zerver.lib.email_validation import email_allowed_for_realm, validate_email_not_already_in_realm
from zerver.lib.onboarding import send_initial_realm_messages, setup_realm_internal_bots
from zerver.lib.pysa import mark_sanitized
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.sessions import get_expirable_session_var
from zerver.lib.subdomains import get_subdomain, is_root_domain_available
from zerver.lib.url_encoding import add_query_to_redirect_url
from zerver.lib.users import get_accounts_for_email
from zerver.lib.zephyr import compute_mit_user_fullname
from zerver.models import (
    DisposableEmailError,
    DomainNotAllowedForRealmError,
    EmailContainsPlusError,
    MultiuseInvite,
    Realm,
    Stream,
    UserProfile,
    get_default_stream_groups,
    get_realm,
    get_source_profile,
    get_user_by_delivery_email,
    name_changes_disabled,
)
from zerver.views.auth import (
    create_preregistration_user,
    finish_desktop_flow,
    finish_mobile_flow,
    get_safe_redirect_to,
    redirect_and_log_into_subdomain,
    redirect_to_deactivation_notice,
)
from zproject.backends import (
    ExternalAuthResult,
    ZulipLDAPAuthBackend,
    ZulipLDAPExceptionNoMatchingLDAPUser,
    any_social_backend_enabled,
    email_auth_enabled,
    email_belongs_to_ldap,
    ldap_auth_enabled,
    password_auth_enabled,
)


def check_prereg_key_and_redirect(request: HttpRequest, confirmation_key: str) -> HttpResponse:
    confirmation = Confirmation.objects.filter(confirmation_key=confirmation_key).first()
    if confirmation is None or confirmation.type not in [
            Confirmation.USER_REGISTRATION, Confirmation.INVITATION, Confirmation.REALM_CREATION]:
        return render_confirmation_key_error(
            request, ConfirmationKeyException(ConfirmationKeyException.DOES_NOT_EXIST))

    prereg_user = confirmation.content_object
    if prereg_user.status == confirmation_settings.STATUS_REVOKED:
        return render(request, "zerver/confirmation_link_expired_error.html")

    try:
        get_object_from_key(confirmation_key, confirmation.type, activate_object=False)
    except ConfirmationKeyException as exception:
        return render_confirmation_key_error(request, exception)

    # confirm_preregistrationuser.html just extracts the confirmation_key
    # (and GET parameters) and redirects to /accounts/register, so that the
    # user can enter their information on a cleaner URL.
    return render(request, 'confirmation/confirm_preregistrationuser.html',
                  context={
                      'key': confirmation_key,
                      'full_name': request.GET.get("full_name", None)})

@require_post
def accounts_register(request: HttpRequest) -> HttpResponse:
    try:
        key = request.POST.get('key', default='')
        confirmation = Confirmation.objects.get(confirmation_key=key)
    except Confirmation.DoesNotExist:
        return render(request, "zerver/confirmation_link_expired_error.html")

    prereg_user = confirmation.content_object
    if prereg_user.status == confirmation_settings.STATUS_REVOKED:
        return render(request, "zerver/confirmation_link_expired_error.html")
    email = prereg_user.email
    realm_creation = prereg_user.realm_creation
    password_required = prereg_user.password_required

    role = get_role_for_new_user(prereg_user.invited_as, realm_creation)

    try:
        validators.validate_email(email)
    except ValidationError:
        return render(request, "zerver/invalid_email.html", context={"invalid_email": True})

    if realm_creation:
        # For creating a new realm, there is no existing realm or domain
        realm = None
    else:
        if get_subdomain(request) != prereg_user.realm.string_id:
            return render_confirmation_key_error(
                request, ConfirmationKeyException(ConfirmationKeyException.DOES_NOT_EXIST))
        realm = prereg_user.realm
        try:
            email_allowed_for_realm(email, realm)
        except DomainNotAllowedForRealmError:
            return render(request, "zerver/invalid_email.html",
                          context={"realm_name": realm.name, "closed_domain": True})
        except DisposableEmailError:
            return render(request, "zerver/invalid_email.html",
                          context={"realm_name": realm.name, "disposable_emails_not_allowed": True})
        except EmailContainsPlusError:
            return render(request, "zerver/invalid_email.html",
                          context={"realm_name": realm.name, "email_contains_plus": True})

        if realm.deactivated:
            # The user is trying to register for a deactivated realm. Advise them to
            # contact support.
            return redirect_to_deactivation_notice()

        try:
            validate_email_not_already_in_realm(realm, email)
        except ValidationError:
            view_url = reverse('login')
            redirect_url = add_query_to_redirect_url(view_url, 'email=' + urllib.parse.quote_plus(email))
            return HttpResponseRedirect(redirect_url)

    name_validated = False
    full_name = None
    require_ldap_password = False

    if request.POST.get('from_confirmation'):
        try:
            del request.session['authenticated_full_name']
        except KeyError:
            pass

        ldap_full_name = None
        if settings.POPULATE_PROFILE_VIA_LDAP:
            # If the user can be found in LDAP, we'll take the full name from the directory,
            # and further down create a form pre-filled with it.
            for backend in get_backends():
                if isinstance(backend, LDAPBackend):
                    try:
                        ldap_username = backend.django_to_ldap_username(email)
                    except ZulipLDAPExceptionNoMatchingLDAPUser:
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

        if ldap_full_name:
            # We don't use initial= here, because if the form is
            # complete (that is, no additional fields need to be
            # filled out by the user) we want the form to validate,
            # so they can be directly registered without having to
            # go through this interstitial.
            form = RegistrationForm({'full_name': ldap_full_name},
                                    realm_creation=realm_creation)
            request.session['authenticated_full_name'] = ldap_full_name
            name_validated = True
        elif realm is not None and realm.is_zephyr_mirror_realm:
            # For MIT users, we can get an authoritative name from Hesiod.
            # Technically we should check that this is actually an MIT
            # realm, but we can cross that bridge if we ever get a non-MIT
            # zephyr mirroring realm.
            hesiod_name = compute_mit_user_fullname(email)
            form = RegistrationForm(
                initial={'full_name': hesiod_name if "@" not in hesiod_name else ""},
                realm_creation=realm_creation)
            name_validated = True
        elif prereg_user.full_name:
            if prereg_user.full_name_validated:
                request.session['authenticated_full_name'] = prereg_user.full_name
                name_validated = True
                form = RegistrationForm({'full_name': prereg_user.full_name},
                                        realm_creation=realm_creation)
            else:
                form = RegistrationForm(initial={'full_name': prereg_user.full_name},
                                        realm_creation=realm_creation)
        elif 'full_name' in request.POST:
            form = RegistrationForm(
                initial={'full_name': request.POST.get('full_name')},
                realm_creation=realm_creation,
            )
        else:
            form = RegistrationForm(realm_creation=realm_creation)
    else:
        postdata = request.POST.copy()
        if name_changes_disabled(realm):
            # If we populate profile information via LDAP and we have a
            # verified name from you on file, use that. Otherwise, fall
            # back to the full name in the request.
            try:
                postdata.update(full_name=request.session['authenticated_full_name'])
                name_validated = True
            except KeyError:
                pass
        form = RegistrationForm(postdata, realm_creation=realm_creation)

    if not (password_auth_enabled(realm) and password_required):
        form['password'].field.required = False

    if form.is_valid():
        if password_auth_enabled(realm) and form['password'].field.required:
            password = form.cleaned_data['password']
        else:
            # If the user wasn't prompted for a password when
            # completing the authentication form (because they're
            # signing up with SSO and no password is required), set
            # the password field to `None` (Which causes Django to
            # create an unusable password).
            password = None

        if realm_creation:
            string_id = form.cleaned_data['realm_subdomain']
            realm_name = form.cleaned_data['realm_name']
            realm = do_create_realm(string_id, realm_name)
            setup_realm_internal_bots(realm)
        assert(realm is not None)

        full_name = form.cleaned_data['full_name']
        default_stream_group_names = request.POST.getlist('default_stream_group')
        default_stream_groups = lookup_default_stream_groups(default_stream_group_names, realm)

        timezone = ""
        if 'timezone' in request.POST and request.POST['timezone'] in pytz.all_timezones_set:
            timezone = request.POST['timezone']

        if 'source_realm' in request.POST and request.POST["source_realm"] != "on":
            source_profile = get_source_profile(email, request.POST["source_realm"])
        else:
            source_profile = None

        if not realm_creation:
            try:
                existing_user_profile: Optional[UserProfile] = get_user_by_delivery_email(email, realm)
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
            # pregeg_user.realm_creation carries the information about whether
            # we're in realm creation mode, and the ldap flow will handle
            # that and create the user with the appropriate parameters.
            user_profile = authenticate(request=request,
                                        username=email,
                                        password=password,
                                        realm=realm,
                                        prereg_user=prereg_user,
                                        return_data=return_data)
            if user_profile is None:
                can_use_different_backend = email_auth_enabled(realm) or any_social_backend_enabled(realm)
                if settings.LDAP_APPEND_DOMAIN:
                    # In LDAP_APPEND_DOMAIN configurations, we don't allow making a non-LDAP account
                    # if the email matches the ldap domain.
                    can_use_different_backend = can_use_different_backend and (
                        not email_belongs_to_ldap(realm, email))
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
                    view_url = reverse('login')
                    query = 'email=' + urllib.parse.quote_plus(email)
                    redirect_url = add_query_to_redirect_url(view_url, query)
                    return HttpResponseRedirect(redirect_url)
            elif not realm_creation:
                # Since we'll have created a user, we now just log them in.
                return login_and_go_to_home(request, user_profile)
            else:
                # With realm_creation=True, we're going to return further down,
                # after finishing up the creation process.
                pass

        if existing_user_profile is not None and existing_user_profile.is_mirror_dummy:
            user_profile = existing_user_profile
            do_activate_user(user_profile, acting_user=user_profile)
            do_change_password(user_profile, password)
            do_change_full_name(user_profile, full_name, user_profile)
            do_set_user_display_setting(user_profile, 'timezone', timezone)
            # TODO: When we clean up the `do_activate_user` code path,
            # make it respect invited_as_admin / is_realm_admin.

        if user_profile is None:
            user_profile = do_create_user(email, password, realm, full_name,
                                          prereg_user=prereg_user,
                                          role=role,
                                          tos_version=settings.TOS_VERSION,
                                          timezone=timezone,
                                          newsletter_data={"IP": request.META['REMOTE_ADDR']},
                                          default_stream_groups=default_stream_groups,
                                          source_profile=source_profile,
                                          realm_creation=realm_creation,
                                          acting_user=None)

        if realm_creation:
            bulk_add_subscriptions(realm, [realm.signup_notifications_stream], [user_profile])
            send_initial_realm_messages(realm)

            # Because for realm creation, registration happens on the
            # root domain, we need to log them into the subdomain for
            # their new realm.
            return redirect_and_log_into_subdomain(ExternalAuthResult(user_profile=user_profile,
                                                                      data_dict={'is_realm_creation': True}))

        # This dummy_backend check below confirms the user is
        # authenticating to the correct subdomain.
        auth_result = authenticate(username=user_profile.delivery_email,
                                   realm=realm,
                                   return_data=return_data,
                                   use_dummy_backend=True)
        if return_data.get('invalid_subdomain'):
            # By construction, this should never happen.
            logging.error(
                "Subdomain mismatch in registration %s: %s",
                realm.subdomain, user_profile.delivery_email,
            )
            return redirect('/')

        return login_and_go_to_home(request, auth_result)

    return render(
        request,
        'zerver/register.html',
        context={'form': form,
                 'email': email,
                 'key': key,
                 'full_name': request.session.get('authenticated_full_name', None),
                 'lock_name': name_validated and name_changes_disabled(realm),
                 # password_auth_enabled is normally set via our context processor,
                 # but for the registration form, there is no logged in user yet, so
                 # we have to set it here.
                 'creating_new_team': realm_creation,
                 'password_required': password_auth_enabled(realm) and password_required,
                 'require_ldap_password': require_ldap_password,
                 'password_auth_enabled': password_auth_enabled(realm),
                 'root_domain_available': is_root_domain_available(),
                 'default_stream_groups': [] if realm is None else get_default_stream_groups(realm),
                 'accounts': get_accounts_for_email(email),
                 'MAX_REALM_NAME_LENGTH': str(Realm.MAX_REALM_NAME_LENGTH),
                 'MAX_NAME_LENGTH': str(UserProfile.MAX_NAME_LENGTH),
                 'MAX_PASSWORD_LENGTH': str(form.MAX_PASSWORD_LENGTH),
                 'MAX_REALM_SUBDOMAIN_LENGTH': str(Realm.MAX_REALM_SUBDOMAIN_LENGTH),
                 },
    )

def login_and_go_to_home(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    mobile_flow_otp = get_expirable_session_var(request.session, 'registration_mobile_flow_otp',
                                                delete=True)
    desktop_flow_otp = get_expirable_session_var(request.session, 'registration_desktop_flow_otp',
                                                 delete=True)
    if mobile_flow_otp is not None:
        return finish_mobile_flow(request, user_profile, mobile_flow_otp)
    elif desktop_flow_otp is not None:
        return finish_desktop_flow(request, user_profile, desktop_flow_otp)

    do_login(request, user_profile)
    # Using 'mark_sanitized' to work around false positive where Pysa thinks
    # that 'user_profile' is user-controlled
    return HttpResponseRedirect(mark_sanitized(user_profile.realm.uri) + reverse('home'))

def prepare_activation_url(email: str, request: HttpRequest,
                           realm_creation: bool=False,
                           streams: Optional[List[Stream]]=None,
                           invited_as: Optional[int]=None) -> str:
    """
    Send an email with a confirmation link to the provided e-mail so the user
    can complete their registration.
    """
    prereg_user = create_preregistration_user(email, request, realm_creation)

    if streams is not None:
        prereg_user.streams.set(streams)

    if invited_as is not None:
        prereg_user.invited_as = invited_as
        prereg_user.save()

    confirmation_type = Confirmation.USER_REGISTRATION
    if realm_creation:
        confirmation_type = Confirmation.REALM_CREATION

    activation_url = create_confirmation_link(prereg_user, confirmation_type)
    if settings.DEVELOPMENT and realm_creation:
        request.session['confirmation_key'] = {'confirmation_key': activation_url.split('/')[-1]}
    return activation_url

def send_confirm_registration_email(email: str, activation_url: str, language: str,
                                    realm: Optional[Realm]=None) -> None:
    send_email('zerver/emails/confirm_registration', to_emails=[email],
               from_address=FromAddress.tokenized_no_reply_address(),
               language=language, context={'activate_url': activation_url},
               realm=realm)

def redirect_to_email_login_url(email: str) -> HttpResponseRedirect:
    login_url = reverse('login')
    email = urllib.parse.quote_plus(email)
    redirect_url = add_query_to_redirect_url(login_url, 'already_registered=' + email)
    return HttpResponseRedirect(redirect_url)

def create_realm(request: HttpRequest, creation_key: Optional[str]=None) -> HttpResponse:
    try:
        key_record = validate_key(creation_key)
    except RealmCreationKey.Invalid:
        return render(request, "zerver/realm_creation_failed.html",
                      context={'message': _('The organization creation link has expired'
                                            ' or is not valid.')})
    if not settings.OPEN_REALM_CREATION:
        if key_record is None:
            return render(request, "zerver/realm_creation_failed.html",
                          context={'message': _('New organization creation disabled')})

    # When settings.OPEN_REALM_CREATION is enabled, anyone can create a new realm,
    # with a few restrictions on their email address.
    if request.method == 'POST':
        form = RealmCreationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            activation_url = prepare_activation_url(email, request, realm_creation=True)
            if key_record is not None and key_record.presume_email_valid:
                # The user has a token created from the server command line;
                # skip confirming the email is theirs, taking their word for it.
                # This is essential on first install if the admin hasn't stopped
                # to configure outbound email up front, or it isn't working yet.
                key_record.delete()
                return HttpResponseRedirect(activation_url)

            try:
                send_confirm_registration_email(email, activation_url, request.LANGUAGE_CODE)
            except smtplib.SMTPException as e:
                logging.error('Error in create_realm: %s', str(e))
                return HttpResponseRedirect("/config-error/smtp")

            if key_record is not None:
                key_record.delete()
            return HttpResponseRedirect(reverse('new_realm_send_confirm', kwargs={'email': email}))
    else:
        form = RealmCreationForm()
    return render(request,
                  'zerver/create_realm.html',
                  context={'form': form, 'current_url': request.get_full_path},
                  )

def accounts_home(request: HttpRequest, multiuse_object_key: str="",
                  multiuse_object: Optional[MultiuseInvite]=None) -> HttpResponse:
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
        realm = multiuse_object.realm
        streams_to_subscribe = multiuse_object.streams.all()
        from_multiuse_invite = True
        invited_as = multiuse_object.invited_as

    if request.method == 'POST':
        form = HomepageForm(request.POST, realm=realm, from_multiuse_invite=from_multiuse_invite)
        if form.is_valid():
            email = form.cleaned_data['email']
            activation_url = prepare_activation_url(email, request, streams=streams_to_subscribe,
                                                    invited_as=invited_as)
            try:
                send_confirm_registration_email(email, activation_url, request.LANGUAGE_CODE, realm=realm)
            except smtplib.SMTPException as e:
                logging.error('Error in accounts_home: %s', str(e))
                return HttpResponseRedirect("/config-error/smtp")

            return HttpResponseRedirect(reverse('signup_send_confirm', kwargs={'email': email}))

        email = request.POST['email']
        try:
            validate_email_not_already_in_realm(realm, email)
        except ValidationError:
            return redirect_to_email_login_url(email)
    else:
        form = HomepageForm(realm=realm)
    context = login_context(request)
    context.update(form=form, current_url=request.get_full_path,
                   multiuse_object_key=multiuse_object_key,
                   from_multiuse_invite=from_multiuse_invite)
    return render(request, 'zerver/accounts_home.html', context=context)

def accounts_home_from_multiuse_invite(request: HttpRequest, confirmation_key: str) -> HttpResponse:
    multiuse_object = None
    try:
        multiuse_object = get_object_from_key(confirmation_key, Confirmation.MULTIUSE_INVITE)
        # Required for oAuth2
    except ConfirmationKeyException as exception:
        realm = get_realm_from_request(request)
        if realm is None or realm.invite_required:
            return render_confirmation_key_error(request, exception)
    return accounts_home(request, multiuse_object_key=confirmation_key,
                         multiuse_object=multiuse_object)

def generate_204(request: HttpRequest) -> HttpResponse:
    return HttpResponse(content=None, status=204)

def find_account(request: HttpRequest) -> HttpResponse:
    from zerver.context_processors import common_context
    url = reverse('find_account')

    emails: List[str] = []
    if request.method == 'POST':
        form = FindMyTeamForm(request.POST)
        if form.is_valid():
            emails = form.cleaned_data['emails']

            # Django doesn't support __iexact__in lookup with EmailField, so we have
            # to use Qs to get around that without needing to do multiple queries.
            emails_q = Q()
            for email in emails:
                emails_q |= Q(delivery_email__iexact=email)

            for user in UserProfile.objects.filter(
                    emails_q, is_active=True, is_bot=False,
                    realm__deactivated=False):
                context = common_context(user)
                context.update(
                    email=user.delivery_email,
                )
                send_email('zerver/emails/find_team', to_user_ids=[user.id], context=context,
                           from_address=FromAddress.SUPPORT)

            # Note: Show all the emails in the result otherwise this
            # feature can be used to ascertain which email addresses
            # are associated with Zulip.
            data = urllib.parse.urlencode({'emails': ','.join(emails)})
            return redirect(add_query_to_redirect_url(url, data))
    else:
        form = FindMyTeamForm()
        result = request.GET.get('emails')
        # The below validation is perhaps unnecessary, in that we
        # shouldn't get able to get here with an invalid email unless
        # the user hand-edits the URLs.
        if result:
            for email in result.split(','):
                try:
                    validators.validate_email(email)
                    emails.append(email)
                except ValidationError:
                    pass

    return render(request,
                  'zerver/find_account.html',
                  context={'form': form, 'current_url': lambda: url,
                           'emails': emails})

def realm_redirect(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = RealmRedirectForm(request.POST)
        if form.is_valid():
            subdomain = form.cleaned_data['subdomain']
            realm = get_realm(subdomain)
            redirect_to = get_safe_redirect_to(request.GET.get("next", ""), realm.uri)
            return HttpResponseRedirect(redirect_to)
    else:
        form = RealmRedirectForm()

    return render(request, 'zerver/realm_redirect.html', context={'form': form})
