# -*- coding: utf-8 -*-
from typing import List, Dict, Optional

from django.utils.translation import ugettext as _
from django.conf import settings
from django.contrib.auth import authenticate, get_backends
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse, HttpRequest
from django.shortcuts import redirect, render
from django.core.exceptions import ValidationError
from django.core import validators
from zerver.context_processors import get_realm_from_request
from zerver.models import UserProfile, Realm, Stream, MultiuseInvite, \
    name_changes_disabled, email_to_username, email_allowed_for_realm, \
    get_realm, get_user_by_delivery_email, get_default_stream_groups, DisposableEmailError, \
    DomainNotAllowedForRealmError, get_source_profile, EmailContainsPlusError, \
    PreregistrationUser
from zerver.lib.send_email import send_email, FromAddress
from zerver.lib.actions import do_change_password, do_change_full_name, \
    do_activate_user, do_create_user, do_create_realm, \
    validate_email_for_realm, \
    do_set_user_display_setting, lookup_default_stream_groups, bulk_add_subscriptions
from zerver.forms import RegistrationForm, HomepageForm, RealmCreationForm, \
    FindMyTeamForm, RealmRedirectForm
from django_auth_ldap.backend import LDAPBackend, _LDAPUser
from zerver.decorator import require_post, \
    do_login
from zerver.lib.onboarding import setup_initial_streams, \
    send_initial_realm_messages, setup_realm_internal_bots
from zerver.lib.subdomains import get_subdomain, is_root_domain_available
from zerver.lib.timezone import get_all_timezones
from zerver.lib.users import get_accounts_for_email
from zerver.lib.zephyr import compute_mit_user_fullname
from zerver.views.auth import create_preregistration_user, redirect_and_log_into_subdomain, \
    redirect_to_deactivation_notice, get_safe_redirect_to

from zproject.backends import ldap_auth_enabled, password_auth_enabled, \
    ZulipLDAPExceptionOutsideDomain, email_auth_enabled

from confirmation.models import Confirmation, RealmCreationKey, ConfirmationKeyException, \
    validate_key, create_confirmation_link, get_object_from_key, \
    render_confirmation_key_error

import logging
import smtplib

import urllib

def check_prereg_key_and_redirect(request: HttpRequest, confirmation_key: str) -> HttpResponse:
    # If the key isn't valid, show the error message on the original URL
    confirmation = Confirmation.objects.filter(confirmation_key=confirmation_key).first()
    if confirmation is None or confirmation.type not in [
            Confirmation.USER_REGISTRATION, Confirmation.INVITATION, Confirmation.REALM_CREATION]:
        return render_confirmation_key_error(
            request, ConfirmationKeyException(ConfirmationKeyException.DOES_NOT_EXIST))
    try:
        get_object_from_key(confirmation_key, confirmation.type)
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
    key = request.POST['key']
    confirmation = Confirmation.objects.get(confirmation_key=key)
    prereg_user = confirmation.content_object
    email = prereg_user.email
    realm_creation = prereg_user.realm_creation
    password_required = prereg_user.password_required
    is_realm_admin = prereg_user.invited_as == PreregistrationUser.INVITE_AS['REALM_ADMIN'] or realm_creation
    is_guest = prereg_user.invited_as == PreregistrationUser.INVITE_AS['GUEST_USER']

    try:
        validators.validate_email(email)
    except ValidationError:
        return render(request, "zerver/invalid_email.html", context={"invalid_email": True})

    if realm_creation:
        # For creating a new realm, there is no existing realm or domain
        realm = None
    else:
        realm = get_realm(get_subdomain(request))
        if realm is None or realm != prereg_user.realm:
            return render_confirmation_key_error(
                request, ConfirmationKeyException(ConfirmationKeyException.DOES_NOT_EXIST))

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
            validate_email_for_realm(realm, email)
        except ValidationError:  # nocoverage # We need to add a test for this.
            return HttpResponseRedirect(reverse('django.contrib.auth.views.login') + '?email=' +
                                        urllib.parse.quote_plus(email))

    name_validated = False
    full_name = None
    require_ldap_password = False

    if request.POST.get('from_confirmation'):
        try:
            del request.session['authenticated_full_name']
        except KeyError:
            pass
        if realm is not None and realm.is_zephyr_mirror_realm:
            # For MIT users, we can get an authoritative name from Hesiod.
            # Technically we should check that this is actually an MIT
            # realm, but we can cross that bridge if we ever get a non-MIT
            # zephyr mirroring realm.
            hesiod_name = compute_mit_user_fullname(email)
            form = RegistrationForm(
                initial={'full_name': hesiod_name if "@" not in hesiod_name else ""},
                realm_creation=realm_creation)
            name_validated = True
        elif settings.POPULATE_PROFILE_VIA_LDAP:
            for backend in get_backends():
                if isinstance(backend, LDAPBackend):
                    try:
                        ldap_username = backend.django_to_ldap_username(email)
                    except ZulipLDAPExceptionOutsideDomain:
                        logging.warning("New account email %s could not be found in LDAP" % (email,))
                        form = RegistrationForm(realm_creation=realm_creation)
                        break

                    ldap_user = _LDAPUser(backend, ldap_username)

                    try:
                        ldap_full_name, _ = backend.get_mapped_name(ldap_user)
                        request.session['authenticated_full_name'] = ldap_full_name
                        name_validated = True
                        # We don't use initial= here, because if the form is
                        # complete (that is, no additional fields need to be
                        # filled out by the user) we want the form to validate,
                        # so they can be directly registered without having to
                        # go through this interstitial.
                        form = RegistrationForm({'full_name': ldap_full_name},
                                                realm_creation=realm_creation)
                        require_ldap_password = True
                        break
                    except TypeError:
                        # Let the user fill out a name and/or try another backend
                        form = RegistrationForm(realm_creation=realm_creation)
        elif 'full_name' in request.POST:
            form = RegistrationForm(
                initial={'full_name': request.POST.get('full_name')},
                realm_creation=realm_creation
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
                postdata.update({'full_name': request.session['authenticated_full_name']})
                name_validated = True
            except KeyError:
                pass
        form = RegistrationForm(postdata, realm_creation=realm_creation)
        if not (password_auth_enabled(realm) and password_required):
            form['password'].field.required = False

    if form.is_valid():
        if password_auth_enabled(realm):
            password = form.cleaned_data['password']
        else:
            # SSO users don't need no passwords
            password = None

        if realm_creation:
            string_id = form.cleaned_data['realm_subdomain']
            realm_name = form.cleaned_data['realm_name']
            realm = do_create_realm(string_id, realm_name)
            setup_initial_streams(realm)
            setup_realm_internal_bots(realm)
        assert(realm is not None)

        full_name = form.cleaned_data['full_name']
        short_name = email_to_username(email)
        default_stream_group_names = request.POST.getlist('default_stream_group')
        default_stream_groups = lookup_default_stream_groups(default_stream_group_names, realm)

        timezone = ""
        if 'timezone' in request.POST and request.POST['timezone'] in get_all_timezones():
            timezone = request.POST['timezone']

        if 'source_realm' in request.POST and request.POST["source_realm"] != "on":
            source_profile = get_source_profile(email, request.POST["source_realm"])
        else:
            source_profile = None

        if not realm_creation:
            try:
                existing_user_profile = get_user_by_delivery_email(email, realm)  # type: Optional[UserProfile]
            except UserProfile.DoesNotExist:
                existing_user_profile = None
        else:
            existing_user_profile = None

        return_data = {}  # type: Dict[str, bool]
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
            auth_result = authenticate(request,
                                       username=email,
                                       password=password,
                                       realm=realm,
                                       prereg_user=prereg_user,
                                       return_data=return_data)
            if auth_result is not None:
                # Since we'll have created a user, we now just log them in.
                return login_and_go_to_home(request, auth_result)

            if return_data.get("outside_ldap_domain") and email_auth_enabled(realm):
                # If both the LDAP and Email auth backends are
                # enabled, and the user's email is outside the LDAP
                # domain, then the intent is to create a user in the
                # realm with their email outside the LDAP organization
                # (with e.g. a password stored in the Zulip database,
                # not LDAP).  So we fall through and create the new
                # account.
                #
                # It's likely that we can extend this block to the
                # Google and GitHub auth backends with no code changes
                # other than here.
                pass
            else:
                # TODO: This probably isn't going to give a
                # user-friendly error message, but it doesn't
                # particularly matter, because the registration form
                # is hidden for most users.
                return HttpResponseRedirect(reverse('django.contrib.auth.views.login') + '?email=' +
                                            urllib.parse.quote_plus(email))

        if existing_user_profile is not None and existing_user_profile.is_mirror_dummy:
            user_profile = existing_user_profile
            do_activate_user(user_profile)
            do_change_password(user_profile, password)
            do_change_full_name(user_profile, full_name, user_profile)
            do_set_user_display_setting(user_profile, 'timezone', timezone)
            # TODO: When we clean up the `do_activate_user` code path,
            # make it respect invited_as_admin / is_realm_admin.
        else:
            user_profile = do_create_user(email, password, realm, full_name, short_name,
                                          prereg_user=prereg_user,
                                          is_realm_admin=is_realm_admin,
                                          is_guest=is_guest,
                                          tos_version=settings.TOS_VERSION,
                                          timezone=timezone,
                                          newsletter_data={"IP": request.META['REMOTE_ADDR']},
                                          default_stream_groups=default_stream_groups,
                                          source_profile=source_profile,
                                          realm_creation=realm_creation)

        if realm_creation:
            bulk_add_subscriptions([realm.signup_notifications_stream], [user_profile])
            send_initial_realm_messages(realm)

            # Because for realm creation, registration happens on the
            # root domain, we need to log them into the subdomain for
            # their new realm.
            return redirect_and_log_into_subdomain(realm, full_name, email)

        # This dummy_backend check below confirms the user is
        # authenticating to the correct subdomain.
        auth_result = authenticate(username=user_profile.delivery_email,
                                   realm=realm,
                                   return_data=return_data,
                                   use_dummy_backend=True)
        if return_data.get('invalid_subdomain'):
            # By construction, this should never happen.
            logging.error("Subdomain mismatch in registration %s: %s" % (
                realm.subdomain, user_profile.email,))
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
                 'default_stream_groups': get_default_stream_groups(realm),
                 'accounts': get_accounts_for_email(email),
                 'MAX_REALM_NAME_LENGTH': str(Realm.MAX_REALM_NAME_LENGTH),
                 'MAX_NAME_LENGTH': str(UserProfile.MAX_NAME_LENGTH),
                 'MAX_PASSWORD_LENGTH': str(form.MAX_PASSWORD_LENGTH),
                 'MAX_REALM_SUBDOMAIN_LENGTH': str(Realm.MAX_REALM_SUBDOMAIN_LENGTH)
                 }
    )

def login_and_go_to_home(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    do_login(request, user_profile)
    return HttpResponseRedirect(user_profile.realm.uri + reverse('zerver.views.home.home'))

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

    activation_url = create_confirmation_link(prereg_user, request.get_host(), confirmation_type)
    if settings.DEVELOPMENT and realm_creation:
        request.session['confirmation_key'] = {'confirmation_key': activation_url.split('/')[-1]}
    return activation_url

def send_confirm_registration_email(email: str, activation_url: str, language: str) -> None:
    send_email('zerver/emails/confirm_registration', to_emails=[email],
               from_address=FromAddress.tokenized_no_reply_address(),
               language=language, context={'activate_url': activation_url})

def redirect_to_email_login_url(email: str) -> HttpResponseRedirect:
    login_url = reverse('django.contrib.auth.views.login')
    email = urllib.parse.quote_plus(email)
    redirect_url = login_url + '?already_registered=' + email
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
                logging.error('Error in create_realm: %s' % (str(e),))
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

def accounts_home(request: HttpRequest, multiuse_object_key: Optional[str]="",
                  multiuse_object: Optional[MultiuseInvite]=None) -> HttpResponse:
    realm = get_realm(get_subdomain(request))

    if realm is None:
        return HttpResponseRedirect(reverse('zerver.views.registration.find_account'))
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
                send_confirm_registration_email(email, activation_url, request.LANGUAGE_CODE)
            except smtplib.SMTPException as e:
                logging.error('Error in accounts_home: %s' % (str(e),))
                return HttpResponseRedirect("/config-error/smtp")

            return HttpResponseRedirect(reverse('signup_send_confirm', kwargs={'email': email}))

        email = request.POST['email']
        try:
            validate_email_for_realm(realm, email)
        except ValidationError:
            return redirect_to_email_login_url(email)
    else:
        form = HomepageForm(realm=realm)
    return render(request,
                  'zerver/accounts_home.html',
                  context={'form': form, 'current_url': request.get_full_path,
                           'multiuse_object_key': multiuse_object_key,
                           'from_multiuse_invite': from_multiuse_invite},
                  )

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
    url = reverse('zerver.views.registration.find_account')

    emails = []  # type: List[str]
    if request.method == 'POST':
        form = FindMyTeamForm(request.POST)
        if form.is_valid():
            emails = form.cleaned_data['emails']
            for user in UserProfile.objects.filter(
                    email__in=emails, is_active=True, is_bot=False, realm__deactivated=False):
                context = common_context(user)
                context.update({
                    'email': user.email,
                })
                send_email('zerver/emails/find_team', to_user_ids=[user.id], context=context)

            # Note: Show all the emails in the result otherwise this
            # feature can be used to ascertain which email addresses
            # are associated with Zulip.
            data = urllib.parse.urlencode({'emails': ','.join(emails)})
            return redirect(url + "?" + data)
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
                           'emails': emails},)

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
