# -*- coding: utf-8 -*-
from __future__ import absolute_import
from typing import Any, List, Dict, Mapping, Optional, Text

from django.utils.translation import ugettext as _
from django.conf import settings
from django.contrib.auth import authenticate, get_backends
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse, HttpRequest
from django.shortcuts import redirect, render
from django.template import RequestContext, loader
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.core import validators
from zerver.models import UserProfile, Realm, Stream, PreregistrationUser, MultiuseInvite, \
    name_changes_disabled, email_to_username, \
    completely_open, get_unique_open_realm, email_allowed_for_realm, \
    get_realm, get_realm_by_email_domain, get_user_profile_by_email
from zerver.lib.send_email import send_email, FromAddress
from zerver.lib.events import do_events_register
from zerver.lib.actions import do_change_password, do_change_full_name, do_change_is_admin, \
    do_activate_user, do_create_user, do_create_realm, \
    user_email_is_unique, compute_mit_user_fullname, validate_email_for_realm, \
    do_set_user_display_setting
from zerver.forms import RegistrationForm, HomepageForm, RealmCreationForm, \
    CreateUserForm, FindMyTeamForm
from django_auth_ldap.backend import LDAPBackend, _LDAPUser
from zerver.decorator import require_post, has_request_variables, \
    JsonableError, REQ, do_login
from zerver.lib.onboarding import send_initial_pms, setup_initial_streams, \
    setup_initial_private_stream, send_initial_realm_messages
from zerver.lib.response import json_success
from zerver.lib.utils import get_subdomain
from zerver.lib.timezone import get_all_timezones
from zproject.backends import password_auth_enabled

from confirmation.models import Confirmation, RealmCreationKey, ConfirmationKeyException, \
    check_key_is_valid, create_confirmation_link, get_object_from_key, \
    render_confirmation_key_error

import logging
import requests
import smtplib
import ujson

from six.moves import urllib

def redirect_and_log_into_subdomain(realm, full_name, email_address,
                                    is_signup=False):
    # type: (Realm, Text, Text, bool) -> HttpResponse
    subdomain_login_uri = ''.join([
        realm.uri,
        reverse('zerver.views.auth.log_into_subdomain')
    ])

    domain = '.' + settings.EXTERNAL_HOST.split(':')[0]
    response = redirect(subdomain_login_uri)

    data = {'name': full_name, 'email': email_address, 'subdomain': realm.subdomain,
            'is_signup': is_signup}
    # Creating a singed cookie so that it cannot be tampered with.
    # Cookie and the signature expire in 15 seconds.
    response.set_signed_cookie('subdomain.signature',
                               ujson.dumps(data),
                               expires=15,
                               domain=domain,
                               salt='zerver.views.auth')
    return response

@require_post
def accounts_register(request):
    # type: (HttpRequest) -> HttpResponse
    key = request.POST['key']
    confirmation = Confirmation.objects.get(confirmation_key=key)
    prereg_user = confirmation.content_object
    email = prereg_user.email
    realm_creation = prereg_user.realm_creation
    password_required = prereg_user.password_required

    validators.validate_email(email)
    # If OPEN_REALM_CREATION is enabled all user sign ups should go through the
    # special URL with domain name so that REALM can be identified if multiple realms exist
    unique_open_realm = get_unique_open_realm()
    if unique_open_realm is not None:
        realm = unique_open_realm  # type: Optional[Realm]
    elif prereg_user.referred_by:
        # If someone invited you, you are joining their realm regardless
        # of your e-mail address.
        realm = prereg_user.referred_by.realm
    elif realm_creation:
        # For creating a new realm, there is no existing realm or domain
        realm = None
    elif settings.REALMS_HAVE_SUBDOMAINS:
        realm = get_realm(get_subdomain(request))
    else:
        realm = get_realm_by_email_domain(email)

    if realm and not email_allowed_for_realm(email, realm):
        return render(request, "zerver/closed_realm.html",
                      context={"closed_domain_name": realm.name})

    if realm and realm.deactivated:
        # The user is trying to register for a deactivated realm. Advise them to
        # contact support.
        return redirect_to_deactivation_notice()

    try:
        validate_email_for_realm(realm, email)
    except ValidationError:
        return HttpResponseRedirect(reverse('django.contrib.auth.views.login') + '?email=' +
                                    urllib.parse.quote_plus(email))

    name_validated = False
    full_name = None

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
                    ldap_attrs = _LDAPUser(backend, backend.django_to_ldap_username(email)).attrs
                    try:
                        ldap_full_name = ldap_attrs[settings.AUTH_LDAP_USER_ATTR_MAP['full_name']][0]
                        request.session['authenticated_full_name'] = ldap_full_name
                        name_validated = True
                        # We don't use initial= here, because if the form is
                        # complete (that is, no additional fields need to be
                        # filled out by the user) we want the form to validate,
                        # so they can be directly registered without having to
                        # go through this interstitial.
                        form = RegistrationForm({'full_name': ldap_full_name},
                                                realm_creation=realm_creation)
                        # FIXME: This will result in the user getting
                        # validation errors if they have to enter a password.
                        # Not relevant for ONLY_SSO, though.
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
        assert(realm is not None)

        full_name = form.cleaned_data['full_name']
        short_name = email_to_username(email)

        timezone = u""
        if 'timezone' in request.POST and request.POST['timezone'] in get_all_timezones():
            timezone = request.POST['timezone']

        try:
            existing_user_profile = get_user_profile_by_email(email)
        except UserProfile.DoesNotExist:
            existing_user_profile = None

        if existing_user_profile is not None and existing_user_profile.is_mirror_dummy:
            user_profile = existing_user_profile
            do_activate_user(user_profile)
            do_change_password(user_profile, password)
            do_change_full_name(user_profile, full_name, user_profile)
            do_set_user_display_setting(user_profile, 'timezone', timezone)
        else:
            user_profile = do_create_user(email, password, realm, full_name, short_name,
                                          prereg_user=prereg_user, is_realm_admin=realm_creation,
                                          tos_version=settings.TOS_VERSION,
                                          timezone=timezone,
                                          newsletter_data={"IP": request.META['REMOTE_ADDR']})

        send_initial_pms(user_profile)

        if realm_creation:
            setup_initial_private_stream(user_profile)
            send_initial_realm_messages(realm)

        if realm_creation and settings.REALMS_HAVE_SUBDOMAINS:
            # Because for realm creation, registration happens on the
            # root domain, we need to log them into the subdomain for
            # their new realm.
            return redirect_and_log_into_subdomain(realm, full_name, email)

        # This dummy_backend check below confirms the user is
        # authenticating to the correct subdomain.
        return_data = {}  # type: Dict[str, bool]
        auth_result = authenticate(username=user_profile.email,
                                   realm_subdomain=realm.subdomain,
                                   return_data=return_data,
                                   use_dummy_backend=True)
        if return_data.get('invalid_subdomain'):
            # By construction, this should never happen.
            logging.error("Subdomain mismatch in registration %s: %s" % (
                realm.subdomain, user_profile.email,))
            return redirect('/')

        # Mark the user as having been just created, so no login email is sent
        auth_result.just_registered = True
        do_login(request, auth_result)
        return HttpResponseRedirect(realm.uri + reverse('zerver.views.home.home'))

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
                 'realms_have_subdomains': settings.REALMS_HAVE_SUBDOMAINS,
                 'password_required': password_auth_enabled(realm) and password_required,
                 'password_auth_enabled': password_auth_enabled(realm),
                 'MAX_REALM_NAME_LENGTH': str(Realm.MAX_REALM_NAME_LENGTH),
                 'MAX_NAME_LENGTH': str(UserProfile.MAX_NAME_LENGTH),
                 'MAX_PASSWORD_LENGTH': str(form.MAX_PASSWORD_LENGTH),
                 'MAX_REALM_SUBDOMAIN_LENGTH': str(Realm.MAX_REALM_SUBDOMAIN_LENGTH)
                 }
    )

def create_preregistration_user(email, request, realm_creation=False,
                                password_required=True):
    # type: (Text, HttpRequest, bool, bool) -> HttpResponse
    return PreregistrationUser.objects.create(email=email,
                                              realm_creation=realm_creation,
                                              password_required=password_required)

def send_registration_completion_email(email, request, realm_creation=False, streams=None):
    # type: (str, HttpRequest, bool, Optional[List[Stream]]) -> None
    """
    Send an email with a confirmation link to the provided e-mail so the user
    can complete their registration.
    """
    prereg_user = create_preregistration_user(email, request, realm_creation)

    if streams is not None:
        prereg_user.streams = streams
        prereg_user.save()

    activation_url = create_confirmation_link(prereg_user, request.get_host(), Confirmation.USER_REGISTRATION)
    send_email('zerver/emails/confirm_registration', to_email=email, from_address=FromAddress.NOREPLY,
               context={'activate_url': activation_url})
    if settings.DEVELOPMENT and realm_creation:
        request.session['confirmation_key'] = {'confirmation_key': activation_url.split('/')[-1]}

def redirect_to_email_login_url(email):
    # type: (str) -> HttpResponseRedirect
    login_url = reverse('django.contrib.auth.views.login')
    email = urllib.parse.quote_plus(email)
    redirect_url = login_url + '?already_registered=' + email
    return HttpResponseRedirect(redirect_url)

def create_realm(request, creation_key=None):
    # type: (HttpRequest, Optional[Text]) -> HttpResponse
    if not settings.OPEN_REALM_CREATION:
        if creation_key is None:
            return render(request, "zerver/realm_creation_failed.html",
                          context={'message': _('New organization creation disabled.')})
        elif not check_key_is_valid(creation_key):
            return render(request, "zerver/realm_creation_failed.html",
                          context={'message': _('The organization creation link has expired'
                                                ' or is not valid.')})

    # When settings.OPEN_REALM_CREATION is enabled, anyone can create a new realm,
    # subject to a few restrictions on their email address.
    if request.method == 'POST':
        form = RealmCreationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                send_registration_completion_email(email, request, realm_creation=True)
            except smtplib.SMTPException as e:
                logging.error('Error in create_realm: %s' % (str(e),))
                return HttpResponseRedirect("/config-error/smtp")

            if (creation_key is not None and check_key_is_valid(creation_key)):
                RealmCreationKey.objects.get(creation_key=creation_key).delete()
            return HttpResponseRedirect(reverse('send_confirm', kwargs={'email': email}))
        try:
            email = request.POST['email']
            user_email_is_unique(email)
        except ValidationError:
            # Maybe the user is trying to log in
            return redirect_to_email_login_url(email)
    else:
        form = RealmCreationForm()
    return render(request,
                  'zerver/create_realm.html',
                  context={'form': form, 'current_url': request.get_full_path},
                  )

def confirmation_key(request):
    # type: (HttpRequest) -> HttpResponse
    return json_success(request.session.get('confirmation_key'))

def get_realm_from_request(request):
    # type: (HttpRequest) -> Realm
    if settings.REALMS_HAVE_SUBDOMAINS:
        realm_str = get_subdomain(request)
    else:
        realm_str = None
    return get_realm(realm_str)

def show_deactivation_notice(request):
    # type: (HttpRequest) -> HttpResponse
    realm = get_realm_from_request(request)
    if realm and realm.deactivated:
        return render(request, "zerver/deactivated.html",
                      context={"deactivated_domain_name": realm.name})

    return HttpResponseRedirect(reverse('zerver.views.auth.login_page'))

def redirect_to_deactivation_notice():
    # type: () -> HttpResponse
    return HttpResponseRedirect(reverse('zerver.views.registration.show_deactivation_notice'))

def accounts_home(request, multiuse_object=None):
    # type: (HttpRequest, Optional[MultiuseInvite]) -> HttpResponse
    realm = get_realm_from_request(request)
    if realm and realm.deactivated:
        return redirect_to_deactivation_notice()

    from_multiuse_invite = False
    streams_to_subscribe = None

    if multiuse_object:
        realm = multiuse_object.realm
        streams_to_subscribe = multiuse_object.streams.all()
        from_multiuse_invite = True

    if request.method == 'POST':
        form = HomepageForm(request.POST, realm=realm, from_multiuse_invite=from_multiuse_invite)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                send_registration_completion_email(email, request, streams=streams_to_subscribe)
            except smtplib.SMTPException as e:
                logging.error('Error in accounts_home: %s' % (str(e),))
                return HttpResponseRedirect("/config-error/smtp")

            return HttpResponseRedirect(reverse('send_confirm', kwargs={'email': email}))

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
                           'from_multiuse_invite': from_multiuse_invite},
                  )

def accounts_home_from_multiuse_invite(request, confirmation_key):
    # type: (HttpRequest, str) -> HttpResponse
    multiuse_object = None
    try:
        multiuse_object = get_object_from_key(confirmation_key)
    except ConfirmationKeyException as exception:
        realm = get_realm_from_request(request)
        if realm is None or realm.invite_required:
            return render_confirmation_key_error(request, exception)
    return accounts_home(request, multiuse_object=multiuse_object)

def generate_204(request):
    # type: (HttpRequest) -> HttpResponse
    return HttpResponse(content=None, status=204)

def find_account(request):
    # type: (HttpRequest) -> HttpResponse
    url = reverse('zerver.views.registration.find_account')

    emails = []  # type: List[Text]
    if request.method == 'POST':
        form = FindMyTeamForm(request.POST)
        if form.is_valid():
            emails = form.cleaned_data['emails']
            for user_profile in UserProfile.objects.filter(
                    email__in=emails, is_active=True, is_bot=False, realm__deactivated=False):
                send_email('zerver/emails/find_team', to_user_id=user_profile.id,
                           context={'user_profile': user_profile})

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
