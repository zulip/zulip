# -*- coding: utf-8 -*-
from __future__ import absolute_import
from typing import Any, List, Dict, Optional, Callable, Tuple, Iterable, Sequence

from django.utils import translation
from django.utils.translation import ugettext as _
from django.conf import settings
from django.contrib.auth import authenticate, login, get_backends
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse, HttpRequest
from django.shortcuts import redirect
from django.template import RequestContext, loader
from django.utils.timezone import now
from django.utils.cache import patch_cache_control
from django.core.exceptions import ValidationError
from django.core import validators
from django.contrib.auth.views import login as django_login_page, \
    logout_then_login as django_logout_then_login
from django.core.mail import send_mail
from django.middleware.csrf import get_token
from zerver.models import Message, UserProfile, Stream, Subscription, Huddle, \
    Recipient, Realm, UserMessage, DefaultStream, RealmEmoji, RealmAlias, \
    RealmFilter, \
    PreregistrationUser, get_client, UserActivity, \
    get_stream, UserPresence, get_recipient, \
    split_email_to_domain, resolve_email_to_domain, email_to_username, get_realm, \
    completely_open, get_unique_open_realm, remote_user_to_email, email_allowed_for_realm, \
    get_cross_realm_users
from zerver.lib.actions import do_change_password, do_change_full_name, do_change_is_admin, \
    do_activate_user, do_create_user, do_create_realm, set_default_streams, \
    internal_send_message, update_user_presence, do_events_register, \
    do_change_enable_offline_email_notifications, \
    do_change_enable_digest_emails, do_change_tos_version, \
    get_default_subs, user_email_is_unique, do_invite_users, do_refer_friend, \
    compute_mit_user_fullname, do_set_muted_topics, clear_followup_emails_queue, \
    do_update_pointer, realm_user_count
from zerver.lib.push_notifications import num_push_devices_for_user
from zerver.forms import RegistrationForm, HomepageForm, RealmCreationForm, ToSForm, \
    CreateUserForm, OurAuthenticationForm
from zerver.lib.actions import is_inactive
from django.views.decorators.csrf import csrf_exempt
from django_auth_ldap.backend import LDAPBackend, _LDAPUser
from zerver.lib import bugdown
from zerver.lib.validator import check_string, check_list, check_bool
from zerver.decorator import require_post, authenticated_json_post_view, \
    has_request_variables, to_non_negative_int, \
    JsonableError, get_user_profile_by_email, REQ, \
    zulip_login_required
from zerver.lib.avatar import avatar_url
from zerver.lib.i18n import get_language_list, get_language_name, \
    get_language_list_for_templates
from zerver.lib.response import json_success, json_error
from zerver.lib.utils import statsd, generate_random_token
from zproject.backends import password_auth_enabled, dev_auth_enabled, google_auth_enabled

from confirmation.models import Confirmation, RealmCreationKey, check_key_is_valid

import requests

import calendar
import datetime
import ujson
import simplejson
import re
from six import text_type
from six.moves import urllib, zip_longest, zip, range
import time
import logging
import jwt
import hashlib
import hmac
import os

from zproject.jinja2 import render_to_response

def name_changes_disabled(realm):
    # type: (Optional[Realm]) -> bool
    if realm is None:
        return settings.NAME_CHANGES_DISABLED
    return settings.NAME_CHANGES_DISABLED or realm.name_changes_disabled

@require_post
def accounts_register(request):
    # type: (HttpRequest) -> HttpResponse
    key = request.POST['key']
    confirmation = Confirmation.objects.get(confirmation_key=key)
    prereg_user = confirmation.content_object
    email = prereg_user.email
    realm_creation = prereg_user.realm_creation
    try:
        existing_user_profile = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        existing_user_profile = None

    validators.validate_email(email)
    # If OPEN_REALM_CREATION is enabled all user sign ups should go through the
    # special URL with domain name so that REALM can be identified if multiple realms exist
    unique_open_realm = get_unique_open_realm()
    if unique_open_realm is not None:
        realm = unique_open_realm
        domain = realm.domain
    elif prereg_user.referred_by:
        # If someone invited you, you are joining their realm regardless
        # of your e-mail address.
        realm = prereg_user.referred_by.realm
        domain = realm.domain
        if not email_allowed_for_realm(email, realm):
            return render_to_response("zerver/closed_realm.html", {"closed_domain_name": realm.name})
    elif prereg_user.realm:
        # You have a realm set, even though nobody referred you. This
        # happens if you sign up through a special URL for an open
        # realm.
        domain = prereg_user.realm.domain
        realm = get_realm(domain)
    else:
        domain = resolve_email_to_domain(email)
        realm = get_realm(domain)

    if realm and realm.deactivated:
        # The user is trying to register for a deactivated realm. Advise them to
        # contact support.
        return render_to_response("zerver/deactivated.html",
                                  {"deactivated_domain_name": realm.name,
                                   "zulip_administrator": settings.ZULIP_ADMINISTRATOR})

    try:
        if existing_user_profile is not None and existing_user_profile.is_mirror_dummy:
            # Mirror dummy users to be activated must be inactive
            is_inactive(email)
        else:
            # Other users should not already exist at all.
            user_email_is_unique(email)
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
        if realm is not None and realm.is_zephyr_mirror_realm and domain == "mit.edu":
            # for MIT users, we can get an authoritative name from Hesiod
            hesiod_name = compute_mit_user_fullname(email)
            form = RegistrationForm(
                    initial={'full_name': hesiod_name if "@" not in hesiod_name else ""})
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
                        form = RegistrationForm({'full_name': ldap_full_name})
                        # FIXME: This will result in the user getting
                        # validation errors if they have to enter a password.
                        # Not relevant for ONLY_SSO, though.
                        break
                    except TypeError:
                        # Let the user fill out a name and/or try another backend
                        form = RegistrationForm()
        elif 'full_name' in request.POST:
            form = RegistrationForm(
                initial={'full_name': request.POST.get('full_name')}
            )
        else:
            form = RegistrationForm()
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
        form = RegistrationForm(postdata)
        if not password_auth_enabled(realm):
            form['password'].field.required = False

    if form.is_valid():
        if password_auth_enabled(realm):
            password = form.cleaned_data['password']
        else:
            # SSO users don't need no passwords
            password = None

        if realm_creation:
            domain = split_email_to_domain(email)
            realm = do_create_realm(domain, form.cleaned_data['realm_name'])[0]
            set_default_streams(realm, settings.DEFAULT_NEW_REALM_STREAMS)

        full_name = form.cleaned_data['full_name']
        short_name = email_to_username(email)
        first_in_realm = len(UserProfile.objects.filter(realm=realm, is_bot=False)) == 0

        # FIXME: sanitize email addresses and fullname
        if existing_user_profile is not None and existing_user_profile.is_mirror_dummy:
            try:
                user_profile = existing_user_profile
                do_activate_user(user_profile)
                do_change_password(user_profile, password)
                do_change_full_name(user_profile, full_name)
            except UserProfile.DoesNotExist:
                user_profile = do_create_user(email, password, realm, full_name, short_name,
                                              prereg_user=prereg_user,
                                              tos_version=settings.TOS_VERSION,
                                              newsletter_data={"IP": request.META['REMOTE_ADDR']})
        else:
            user_profile = do_create_user(email, password, realm, full_name, short_name,
                                          prereg_user=prereg_user,
                                          tos_version=settings.TOS_VERSION,
                                          newsletter_data={"IP": request.META['REMOTE_ADDR']})

        # This logs you in using the ZulipDummyBackend, since honestly nothing
        # more fancy than this is required.
        login(request, authenticate(username=user_profile.email, use_dummy_backend=True))

        if first_in_realm:
            do_change_is_admin(user_profile, True)
            return HttpResponseRedirect(reverse('zerver.views.initial_invite_page'))
        else:
            return HttpResponseRedirect(reverse('zerver.views.home'))

    return render_to_response('zerver/register.html',
            {'form': form,
             'company_name': domain,
             'email': email,
             'key': key,
             'full_name': request.session.get('authenticated_full_name', None),
             'lock_name': name_validated and name_changes_disabled(realm),
             # password_auth_enabled is normally set via our context processor,
             # but for the registration form, there is no logged in user yet, so
             # we have to set it here.
             'creating_new_team': realm_creation,
             'password_auth_enabled': password_auth_enabled(realm),
            },
        request=request)

@zulip_login_required
def accounts_accept_terms(request):
    # type: (HttpRequest) -> HttpResponse
    if request.method == "POST":
        form = ToSForm(request.POST)
        if form.is_valid():
            do_change_tos_version(request.user, settings.TOS_VERSION)
            return redirect(home)
    else:
        form = ToSForm()

    email = request.user.email
    domain = resolve_email_to_domain(email)
    special_message_template = None
    if request.user.tos_version is None and settings.FIRST_TIME_TOS_TEMPLATE is not None:
        special_message_template = 'zerver/' + settings.FIRST_TIME_TOS_TEMPLATE
    return render_to_response('zerver/accounts_accept_terms.html',
        { 'form': form, 'company_name': domain, 'email': email, \
          'special_message_template' : special_message_template },
        request=request)


def api_endpoint_docs(request):
    # type: (HttpRequest) -> HttpResponse
    raw_calls = open('templates/zerver/api_content.json', 'r').read()
    calls = ujson.loads(raw_calls)
    langs = set()
    for call in calls:
        call["endpoint"] = "%s/v1/%s" % (settings.EXTERNAL_API_URI, call["endpoint"])
        call["example_request"]["curl"] = call["example_request"]["curl"].replace("https://api.zulip.com",
                                                                                  settings.EXTERNAL_API_URI)
        response = call['example_response']
        if '\n' not in response:
            # For 1-line responses, pretty-print them
            extended_response = response.replace(", ", ",\n ")
        else:
            extended_response = response
        call['rendered_response'] = bugdown.convert("~~~ .py\n" + extended_response + "\n~~~\n", "default")
        for example_type in ('request', 'response'):
            for lang in call.get('example_' + example_type, []):
                langs.add(lang)
    return render_to_response(
            'zerver/api_endpoints.html', {
                'content': calls,
                'langs': langs,
                },
        request=request)

@authenticated_json_post_view
@has_request_variables
def json_invite_users(request, user_profile, invitee_emails_raw=REQ("invitee_emails")):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    if not invitee_emails_raw:
        return json_error(_("You must specify at least one email address."))

    invitee_emails = get_invitee_emails_set(invitee_emails_raw)

    stream_names = request.POST.getlist('stream')
    if not stream_names:
        return json_error(_("You must specify at least one stream for invitees to join."))

    # We unconditionally sub you to the notifications stream if it
    # exists and is public.
    notifications_stream = user_profile.realm.notifications_stream
    if notifications_stream and not notifications_stream.invite_only:
        stream_names.append(notifications_stream.name)

    streams = [] # type: List[Stream]
    for stream_name in stream_names:
        stream = get_stream(stream_name, user_profile.realm)
        if stream is None:
            return json_error(_("Stream does not exist: %s. No invites were sent.") % (stream_name,))
        streams.append(stream)

    ret_error, error_data = do_invite_users(user_profile, invitee_emails, streams)

    if ret_error is not None:
        return json_error(data=error_data, msg=ret_error)
    else:
        return json_success()

def get_invitee_emails_set(invitee_emails_raw):
    # type: (str) -> Set[str]
    invitee_emails_list = set(re.split(r'[,\n]', invitee_emails_raw))
    invitee_emails = set()
    for email in invitee_emails_list:
        is_email_with_name = re.search(r'<(?P<email>.*)>', email)
        if is_email_with_name:
            email = is_email_with_name.group('email')
        invitee_emails.add(email.strip())
    return invitee_emails

def create_homepage_form(request, user_info=None):
    # type: (HttpRequest, Optional[Dict[str, Any]]) -> HomepageForm
    if user_info:
        return HomepageForm(user_info, domain=request.session.get("domain"))
    # An empty fields dict is not treated the same way as not
    # providing it.
    return HomepageForm(domain=request.session.get("domain"))

def maybe_send_to_registration(request, email, full_name=''):
    # type: (HttpRequest, text_type, text_type) -> HttpResponse
    form = create_homepage_form(request, user_info={'email': email})
    request.verified_email = None
    if form.is_valid():
        # Construct a PreregistrationUser object and send the user over to
        # the confirmation view.
        prereg_user = None
        if settings.ONLY_SSO:
            try:
                prereg_user = PreregistrationUser.objects.filter(email__iexact=email).latest("invited_at")
            except PreregistrationUser.DoesNotExist:
                prereg_user = create_preregistration_user(email, request)
        else:
            prereg_user = create_preregistration_user(email, request)

        return redirect("".join((
            settings.EXTERNAL_URI_SCHEME,
            request.get_host(),
            "/",
            # Split this so we only get the part after the /
            Confirmation.objects.get_link_for_object(prereg_user).split("/", 3)[3],
            '?full_name=',
            # urllib does not handle Unicode, so coerece to encoded byte string
            # Explanation: http://stackoverflow.com/a/5605354/90777
            urllib.parse.quote_plus(full_name.encode('utf8')))))
    else:
        url = reverse('register')
        return render_to_response('zerver/accounts_home.html',
                                  {'form': form, 'current_url': lambda: url},
                                  request=request)

def login_or_register_remote_user(request, remote_username, user_profile, full_name=''):
    # type: (HttpRequest, text_type, UserProfile, text_type) -> HttpResponse
    if user_profile is None or user_profile.is_mirror_dummy:
        # Since execution has reached here, the client specified a remote user
        # but no associated user account exists. Send them over to the
        # PreregistrationUser flow.
        return maybe_send_to_registration(request, remote_user_to_email(remote_username), full_name)
    else:
        login(request, user_profile)
        return HttpResponseRedirect("%s%s" % (settings.EXTERNAL_URI_SCHEME,
                                              request.get_host()))

def remote_user_sso(request):
    # type: (HttpRequest) -> HttpResponse
    try:
        remote_user = request.META["REMOTE_USER"]
    except KeyError:
        raise JsonableError(_("No REMOTE_USER set."))

    user_profile = authenticate(remote_user=remote_user)
    return login_or_register_remote_user(request, remote_user, user_profile)

@csrf_exempt
def remote_user_jwt(request):
    # type: (HttpRequest) -> HttpResponse
    try:
        json_web_token = request.POST["json_web_token"]
        payload, signing_input, header, signature = jwt.load(json_web_token)
    except KeyError:
        raise JsonableError(_("No JSON web token passed in request"))
    except jwt.DecodeError:
        raise JsonableError(_("Bad JSON web token"))

    remote_user = payload.get("user", None)
    if remote_user is None:
        raise JsonableError(_("No user specified in JSON web token claims"))
    domain = payload.get('realm', None)
    if domain is None:
        raise JsonableError(_("No domain specified in JSON web token claims"))

    email = "%s@%s" % (remote_user, domain)

    try:
        jwt.verify_signature(payload, signing_input, header, signature,
                             settings.JWT_AUTH_KEYS[domain])
        # We do all the authentication we need here (otherwise we'd have to
        # duplicate work), but we need to call authenticate with some backend so
        # that the request.backend attribute gets set.
        user_profile = authenticate(username=email, use_dummy_backend=True)
    except (jwt.DecodeError, jwt.ExpiredSignature):
        raise JsonableError(_("Bad JSON web token signature"))
    except KeyError:
        raise JsonableError(_("Realm not authorized for JWT login"))
    except UserProfile.DoesNotExist:
        user_profile = None

    return login_or_register_remote_user(request, email, user_profile, remote_user)

def google_oauth2_csrf(request, value):
    # type: (HttpRequest, str) -> HttpResponse
    return hmac.new(get_token(request).encode('utf-8'), value, hashlib.sha256).hexdigest()

def start_google_oauth2(request):
    # type: (HttpRequest) -> HttpResponse
    uri = 'https://accounts.google.com/o/oauth2/auth?'
    cur_time = str(int(time.time()))
    csrf_state = '{}:{}'.format(
        cur_time,
        google_oauth2_csrf(request, cur_time),
    )
    prams = {
        'response_type': 'code',
        'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
        'redirect_uri': ''.join((
            settings.EXTERNAL_URI_SCHEME,
            request.get_host(),
            reverse('zerver.views.finish_google_oauth2'),
        )),
        'scope': 'profile email',
        'state': csrf_state,
    }
    return redirect(uri + urllib.parse.urlencode(prams))

# Workaround to support the Python-requests 1.0 transition of .json
# from a property to a function
requests_json_is_function = callable(requests.Response.json)
def extract_json_response(resp):
    # type: (HttpResponse) -> Dict[str, Any]
    if requests_json_is_function:
        return resp.json()
    else:
        return resp.json

def finish_google_oauth2(request):
    # type: (HttpRequest) -> HttpResponse
    error = request.GET.get('error')
    if error == 'access_denied':
        return redirect('/')
    elif error is not None:
        logging.warning('Error from google oauth2 login %r', request.GET)
        return HttpResponse(status=400)

    value, hmac_value = request.GET.get('state').split(':')
    if hmac_value != google_oauth2_csrf(request, value):
        logging.warning('Google oauth2 CSRF error')
        return HttpResponse(status=400)

    resp = requests.post(
        'https://www.googleapis.com/oauth2/v3/token',
        data={
            'code': request.GET.get('code'),
            'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            'redirect_uri': ''.join((
                settings.EXTERNAL_URI_SCHEME,
                request.get_host(),
                reverse('zerver.views.finish_google_oauth2'),
            )),
            'grant_type': 'authorization_code',
        },
    )
    if resp.status_code == 400:
        logging.warning('User error converting Google oauth2 login to token: %r' % (resp.text,))
        return HttpResponse(status=400)
    elif resp.status_code != 200:
        raise Exception('Could not convert google oauth2 code to access_token\r%r' % (resp.text,))
    access_token = extract_json_response(resp)['access_token']

    resp = requests.get(
        'https://www.googleapis.com/plus/v1/people/me',
        params={'access_token': access_token}
    )
    if resp.status_code == 400:
        logging.warning('Google login failed making info API call: %r' % (resp.text,))
        return HttpResponse(status=400)
    elif resp.status_code != 200:
        raise Exception('Google login failed making API call\r%r' % (resp.text,))
    body = extract_json_response(resp)

    try:
        full_name = body['name']['formatted']
    except KeyError:
        # Only google+ users have a formated name. I am ignoring i18n here.
        full_name = u'{} {}'.format(
            body['name']['givenName'], body['name']['familyName']
        )
    for email in body['emails']:
        if email['type'] == 'account':
            break
    else:
        raise Exception('Google oauth2 account email not found %r' % (body,))
    email_address = email['value']
    user_profile = authenticate(username=email_address, use_dummy_backend=True)
    return login_or_register_remote_user(request, email_address, user_profile, full_name)

def login_page(request, **kwargs):
    # type: (HttpRequest, **Any) -> HttpResponse
    extra_context = kwargs.pop('extra_context', {})
    if dev_auth_enabled():
        # Development environments usually have only a few users, but
        # it still makes sense to limit how many users we render to
        # support performance testing with DevAuthBackend.
        MAX_DEV_BACKEND_USERS = 100
        users_query = UserProfile.objects.select_related().filter(is_bot=False, is_active=True)
        users = users_query.order_by('email')[0:MAX_DEV_BACKEND_USERS]
        extra_context['direct_admins'] = [u.email for u in users if u.is_realm_admin]
        extra_context['direct_users'] = [u.email for u in users if not u.is_realm_admin]
    template_response = django_login_page(
        request, authentication_form=OurAuthenticationForm,
        extra_context=extra_context, **kwargs)
    try:
        template_response.context_data['email'] = request.GET['email']
    except KeyError:
        pass

    return template_response

def dev_direct_login(request, **kwargs):
    # type: (HttpRequest, **Any) -> HttpResponse
    # This function allows logging in without a password and should only be called in development environments.
    # It may be called if the DevAuthBackend is included in settings.AUTHENTICATION_BACKENDS
    if (not dev_auth_enabled()) or settings.PRODUCTION:
        # This check is probably not required, since authenticate would fail without an enabled DevAuthBackend.
        raise Exception('Direct login not supported.')
    email = request.POST['direct_email']
    user_profile = authenticate(username=email)
    if user_profile is None:
        raise Exception("User cannot login")
    login(request, user_profile)
    return HttpResponseRedirect("%s%s" % (settings.EXTERNAL_URI_SCHEME,
                                          request.get_host()))

@csrf_exempt
@require_post
@has_request_variables
def api_dev_fetch_api_key(request, username=REQ()):
    # type: (HttpRequest, str) -> HttpResponse
    """This function allows logging in without a password on the Zulip
    mobile apps when connecting to a Zulip development environment.  It
    requires DevAuthBackend to be included in settings.AUTHENTICATION_BACKENDS.
    """
    if not dev_auth_enabled() or settings.PRODUCTION:
        return json_error(_("Dev environment not enabled."))
    return_data = {} # type: Dict[str, bool]
    user_profile = authenticate(username=username, return_data=return_data)
    if return_data.get("inactive_realm") == True:
        return json_error(_("Your realm has been deactivated."),
                          data={"reason": "realm deactivated"}, status=403)
    if return_data.get("inactive_user") == True:
        return json_error(_("Your account has been disabled."),
                          data={"reason": "user disable"}, status=403)
    login(request, user_profile)
    return json_success({"api_key": user_profile.api_key, "email": user_profile.email})

@csrf_exempt
def api_dev_get_emails(request):
    # type: (HttpRequest) -> HttpResponse
    if not dev_auth_enabled() or settings.PRODUCTION:
        return json_error(_("Dev environment not enabled."))
    MAX_DEV_BACKEND_USERS = 100 # type: int
    users_query = UserProfile.objects.select_related().filter(is_bot=False, is_active=True)
    users = users_query.order_by('email')[0:MAX_DEV_BACKEND_USERS]
    return json_success(dict(direct_admins=[u.email for u in users if u.is_realm_admin],
                             direct_users=[u.email for u in users if not u.is_realm_admin]))

@authenticated_json_post_view
@has_request_variables
def json_bulk_invite_users(request, user_profile,
                           invitee_emails_list=REQ('invitee_emails',
                                                   validator=check_list(check_string))):
    # type: (HttpRequest, UserProfile, List[str]) -> HttpResponse
    invitee_emails = set(invitee_emails_list)
    streams = get_default_subs(user_profile)

    ret_error, error_data = do_invite_users(user_profile, invitee_emails, streams)

    if ret_error is not None:
        return json_error(data=error_data, msg=ret_error)
    else:
        # Report bulk invites to internal Zulip.
        invited = PreregistrationUser.objects.filter(referred_by=user_profile)
        internal_message = "%s <`%s`> invited %d people to Zulip." % (
            user_profile.full_name, user_profile.email, invited.count())
        internal_send_message(settings.NEW_USER_BOT, "stream", "signups",
                              user_profile.realm.domain, internal_message)
        return json_success()

@zulip_login_required
def initial_invite_page(request):
    # type: (HttpRequest) -> HttpResponse
    user = request.user
    # Only show the bulk-invite page for the first user in a realm
    domain_count = len(UserProfile.objects.filter(realm=user.realm))
    if domain_count > 1:
        return redirect('zerver.views.home')

    params = {'company_name': user.realm.domain}

    if (user.realm.restricted_to_domain):
        params['invite_suffix'] = user.realm.domain

    return render_to_response('zerver/initial_invite_page.html', params,
                              request=request)

@require_post
def logout_then_login(request, **kwargs):
    # type: (HttpRequest, **Any) -> HttpResponse
    return django_logout_then_login(request, kwargs)

def create_preregistration_user(email, request, realm_creation=False):
    # type: (text_type, HttpRequest, bool) -> HttpResponse
    domain = request.session.get("domain")
    if completely_open(domain):
        # Clear the "domain" from the session object; it's no longer needed
        request.session["domain"] = None

        # The user is trying to sign up for a completely open realm,
        # so create them a PreregistrationUser for that realm
        return PreregistrationUser.objects.create(email=email,
                                                  realm=get_realm(domain),
                                                  realm_creation=realm_creation)

    return PreregistrationUser.objects.create(email=email, realm_creation=realm_creation)

def accounts_home_with_domain(request, domain):
    # type: (HttpRequest, str) -> HttpResponse
    if completely_open(domain):
        # You can sign up for a completely open realm through a
        # special registration path that contains the domain in the
        # URL. We store this information in the session rather than
        # elsewhere because we don't have control over URL or form
        # data for folks registering through OpenID.
        request.session["domain"] = domain
        return accounts_home(request)
    else:
        return HttpResponseRedirect(reverse('zerver.views.accounts_home'))

def send_registration_completion_email(email, request, realm_creation=False):
    # type: (str, HttpRequest, bool) -> Confirmation
    """
    Send an email with a confirmation link to the provided e-mail so the user
    can complete their registration.
    """
    prereg_user = create_preregistration_user(email, request, realm_creation)
    context = {'support_email': settings.ZULIP_ADMINISTRATOR,
               'verbose_support_offers': settings.VERBOSE_SUPPORT_OFFERS}
    return Confirmation.objects.send_confirmation(prereg_user, email,
                                                  additional_context=context)

def redirect_to_email_login_url(email):
    # type: (str) -> HttpResponseRedirect
    login_url = reverse('django.contrib.auth.views.login')
    redirect_url = login_url + '?email=' + urllib.parse.quote_plus(email)
    return HttpResponseRedirect(redirect_url)

"""
When settings.OPEN_REALM_CREATION is enabled public users can create new realm. For creating the realm the user should
not be the member of any current realm. The realm is created with domain same as the that of the user's email.
When there is no unique_open_realm user registrations are made by visiting /register/domain_of_the_realm.
"""
def create_realm(request, creation_key=None):
    # type: (HttpRequest, Optional[text_type]) -> HttpResponse
    if not settings.OPEN_REALM_CREATION:
        if creation_key is None:
            return render_to_response("zerver/realm_creation_failed.html",
                                      {'message': _('New organization creation disabled.')})
        elif not check_key_is_valid(creation_key):
            return render_to_response("zerver/realm_creation_failed.html",
                                      {'message': _('The organization creation link has been expired'
                                                    ' or is not valid.')})

    if request.method == 'POST':
        form = RealmCreationForm(request.POST, domain=request.session.get("domain"))
        if form.is_valid():
            email = form.cleaned_data['email']
            confirmation_key = send_registration_completion_email(email, request, realm_creation=True).confirmation_key
            if settings.DEVELOPMENT:
                 request.session['confirmation_key'] = {'confirmation_key': confirmation_key}
            if (creation_key is not None and check_key_is_valid(creation_key)):
                RealmCreationKey.objects.get(creation_key=creation_key).delete()
            return HttpResponseRedirect(reverse('send_confirm', kwargs={'email': email}))
        try:
            email = request.POST['email']
            user_email_is_unique(email)
        except ValidationError:
            # if the user user is already registered he can't create a new realm as a realm
            # with the same domain as user's email already exists
            return redirect_to_email_login_url(email)
    else:
        form = RealmCreationForm(domain=request.session.get("domain"))
    return render_to_response('zerver/create_realm.html',
                              {'form': form, 'current_url': request.get_full_path},
                              request=request)

def confirmation_key(request):
    # type: (HttpRequest) -> HttpResponse
    return json_success(request.session.get('confirmation_key'))

def accounts_home(request):
    # type: (HttpRequest) -> HttpResponse
    if request.method == 'POST':
        form = create_homepage_form(request, user_info=request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            send_registration_completion_email(email, request)
            return HttpResponseRedirect(reverse('send_confirm', kwargs={'email': email}))
        try:
            email = request.POST['email']
            # Note: We don't check for uniqueness
            is_inactive(email)
        except ValidationError:
            return redirect_to_email_login_url(email)
    else:
        form = create_homepage_form(request)
    return render_to_response('zerver/accounts_home.html',
                              {'form': form, 'current_url': request.get_full_path},
                              request=request)

def approximate_unread_count(user_profile):
    # type: (UserProfile) -> int
    not_in_home_view_recipients = [sub.recipient.id for sub in \
                                       Subscription.objects.filter(
            user_profile=user_profile, in_home_view=False)]

    # TODO: We may want to exclude muted messages from this count.
    #       It was attempted in the past, but the original attempt
    #       was broken.  When we re-architect muting, we may
    #       want to to revisit this (see git issue #1019).
    return UserMessage.objects.filter(
        user_profile=user_profile, message_id__gt=user_profile.pointer).exclude(
        message__recipient__type=Recipient.STREAM,
        message__recipient__id__in=not_in_home_view_recipients).exclude(
        flags=UserMessage.flags.read).count()

def sent_time_in_epoch_seconds(user_message):
    # type: (UserMessage) -> float
    # user_message is a UserMessage object.
    if not user_message:
        return None
    # We have USE_TZ = True, so our datetime objects are timezone-aware.
    # Return the epoch seconds in UTC.
    return calendar.timegm(user_message.message.pub_date.utctimetuple())

@zulip_login_required
def home(request):
    # type: (HttpRequest) -> HttpResponse
    # We need to modify the session object every two weeks or it will expire.
    # This line makes reloading the page a sufficient action to keep the
    # session alive.
    request.session.modified = True

    user_profile = request.user
    request._email = request.user.email
    request.client = get_client("website")

    # If a user hasn't signed the current Terms of Service, send them there
    if settings.TERMS_OF_SERVICE is not None and settings.TOS_VERSION is not None and \
       int(settings.TOS_VERSION.split('.')[0]) > user_profile.major_tos_version():
        return accounts_accept_terms(request)

    narrow = [] # type: List[List[text_type]]
    narrow_stream = None
    narrow_topic = request.GET.get("topic")
    if request.GET.get("stream"):
        try:
            narrow_stream = get_stream(request.GET.get("stream"), user_profile.realm)
            assert(narrow_stream is not None)
            assert(narrow_stream.is_public())
            narrow = [["stream", narrow_stream.name]]
        except Exception:
            logging.exception("Narrow parsing")
        if narrow_topic is not None:
            narrow.append(["topic", narrow_topic])

    register_ret = do_events_register(user_profile, request.client,
                                      apply_markdown=True, narrow=narrow)
    user_has_messages = (register_ret['max_message_id'] != -1)

    # Reset our don't-spam-users-with-email counter since the
    # user has since logged in
    if not user_profile.last_reminder is None:
        user_profile.last_reminder = None
        user_profile.save(update_fields=["last_reminder"])

    # Brand new users get the tutorial
    needs_tutorial = settings.TUTORIAL_ENABLED and \
        user_profile.tutorial_status != UserProfile.TUTORIAL_FINISHED

    first_in_realm = realm_user_count(user_profile.realm) == 1
    # If you are the only person in the realm and you didn't invite
    # anyone, we'll continue to encourage you to do so on the frontend.
    prompt_for_invites = first_in_realm and \
        not PreregistrationUser.objects.filter(referred_by=user_profile).count()

    if user_profile.pointer == -1 and user_has_messages:
        # Put the new user's pointer at the bottom
        #
        # This improves performance, because we limit backfilling of messages
        # before the pointer.  It's also likely that someone joining an
        # organization is interested in recent messages more than the very
        # first messages on the system.

        register_ret['pointer'] = register_ret['max_message_id']
        user_profile.last_pointer_updater = request.session.session_key

    if user_profile.pointer == -1:
        latest_read = None
    else:
        try:
            latest_read = UserMessage.objects.get(user_profile=user_profile,
                                                  message__id=user_profile.pointer)
        except UserMessage.DoesNotExist:
            # Don't completely fail if your saved pointer ID is invalid
            logging.warning("%s has invalid pointer %s" % (user_profile.email, user_profile.pointer))
            latest_read = None

    desktop_notifications_enabled = user_profile.enable_desktop_notifications
    if narrow_stream is not None:
        desktop_notifications_enabled = False

    if user_profile.realm.notifications_stream:
        notifications_stream = user_profile.realm.notifications_stream.name
    else:
        notifications_stream = ""

    # Set default language and make it persist
    default_language = register_ret['default_language']
    url_lang = '/{}'.format(request.LANGUAGE_CODE)
    if not request.path.startswith(url_lang):
        translation.activate(default_language)

    request.session[translation.LANGUAGE_SESSION_KEY] = default_language

    # Pass parameters to the client-side JavaScript code.
    # These end up in a global JavaScript Object named 'page_params'.
    page_params = dict(
        share_the_love        = settings.SHARE_THE_LOVE,
        development_environment = settings.DEVELOPMENT,
        debug_mode            = settings.DEBUG,
        test_suite            = settings.TEST_SUITE,
        poll_timeout          = settings.POLL_TIMEOUT,
        login_page            = settings.HOME_NOT_LOGGED_IN,
        server_uri            = settings.SERVER_URI,
        realm_uri             = user_profile.realm.uri,
        maxfilesize           = settings.MAX_FILE_UPLOAD_SIZE,
        server_generation     = settings.SERVER_GENERATION,
        password_auth_enabled = password_auth_enabled(user_profile.realm),
        have_initial_messages = user_has_messages,
        subbed_info           = register_ret['subscriptions'],
        unsubbed_info         = register_ret['unsubscribed'],
        neversubbed_info      = register_ret['never_subscribed'],
        email_dict            = register_ret['email_dict'],
        people_list           = register_ret['realm_users'],
        bot_list              = register_ret['realm_bots'],
        initial_pointer       = register_ret['pointer'],
        initial_presences     = register_ret['presences'],
        initial_servertime    = time.time(), # Used for calculating relative presence age
        fullname              = user_profile.full_name,
        email                 = user_profile.email,
        domain                = user_profile.realm.domain,
        realm_name            = register_ret['realm_name'],
        realm_invite_required = register_ret['realm_invite_required'],
        realm_invite_by_admins_only = register_ret['realm_invite_by_admins_only'],
        realm_create_stream_by_admins_only = register_ret['realm_create_stream_by_admins_only'],
        realm_allow_message_editing = register_ret['realm_allow_message_editing'],
        realm_message_content_edit_limit_seconds = register_ret['realm_message_content_edit_limit_seconds'],
        realm_restricted_to_domain = register_ret['realm_restricted_to_domain'],
        realm_default_language = register_ret['realm_default_language'],
        enter_sends           = user_profile.enter_sends,
        user_id               = user_profile.id,
        left_side_userlist    = register_ret['left_side_userlist'],
        default_language      = register_ret['default_language'],
        default_language_name = get_language_name(register_ret['default_language']),
        language_list_dbl_col = get_language_list_for_templates(register_ret['default_language']),
        language_list         = get_language_list(),
        referrals             = register_ret['referrals'],
        realm_emoji           = register_ret['realm_emoji'],
        needs_tutorial        = needs_tutorial,
        first_in_realm        = first_in_realm,
        prompt_for_invites    = prompt_for_invites,
        notifications_stream  = notifications_stream,
        cross_realm_user_emails = list(get_cross_realm_users()),

        # Stream message notification settings:
        stream_desktop_notifications_enabled =
            user_profile.enable_stream_desktop_notifications,
        stream_sounds_enabled = user_profile.enable_stream_sounds,

        # Private message and @-mention notification settings:
        desktop_notifications_enabled = desktop_notifications_enabled,
        sounds_enabled =
            user_profile.enable_sounds,
        enable_offline_email_notifications =
            user_profile.enable_offline_email_notifications,
        enable_offline_push_notifications =
            user_profile.enable_offline_push_notifications,
        twenty_four_hour_time = register_ret['twenty_four_hour_time'],

        enable_digest_emails  = user_profile.enable_digest_emails,
        event_queue_id        = register_ret['queue_id'],
        last_event_id         = register_ret['last_event_id'],
        max_message_id        = register_ret['max_message_id'],
        unread_count          = approximate_unread_count(user_profile),
        furthest_read_time    = sent_time_in_epoch_seconds(latest_read),
        save_stacktraces      = settings.SAVE_FRONTEND_STACKTRACES,
        alert_words           = register_ret['alert_words'],
        muted_topics          = register_ret['muted_topics'],
        realm_filters         = register_ret['realm_filters'],
        realm_default_streams = register_ret['realm_default_streams'],
        is_admin              = user_profile.is_realm_admin,
        can_create_streams    = user_profile.can_create_streams(),
        name_changes_disabled = name_changes_disabled(user_profile.realm),
        has_mobile_devices    = num_push_devices_for_user(user_profile) > 0,
        autoscroll_forever = user_profile.autoscroll_forever,
        default_desktop_notifications = user_profile.default_desktop_notifications,
        avatar_url            = avatar_url(user_profile),
        mandatory_topics      = user_profile.realm.mandatory_topics,
        show_digest_email     = user_profile.realm.show_digest_email,
        presence_disabled     = user_profile.realm.presence_disabled,
        is_zephyr_mirror_realm = user_profile.realm.is_zephyr_mirror_realm,
    )

    if narrow_stream is not None:
        # In narrow_stream context, initial pointer is just latest message
        recipient = get_recipient(Recipient.STREAM, narrow_stream.id)
        try:
            initial_pointer = Message.objects.filter(recipient=recipient).order_by('id').reverse()[0].id
        except IndexError:
            initial_pointer = -1
        page_params["narrow_stream"] = narrow_stream.name
        if narrow_topic is not None:
            page_params["narrow_topic"] = narrow_topic
        page_params["narrow"] = [dict(operator=term[0], operand=term[1]) for term in narrow]
        page_params["max_message_id"] = initial_pointer
        page_params["initial_pointer"] = initial_pointer
        page_params["have_initial_messages"] = (initial_pointer != -1)

    statsd.incr('views.home')
    show_invites = True

    # Some realms only allow admins to invite users
    if user_profile.realm.invite_by_admins_only and not user_profile.is_realm_admin:
        show_invites = False

    product_name = "Zulip"
    page_params['product_name'] = product_name
    request._log_data['extra'] = "[%s]" % (register_ret["queue_id"],)
    response = render_to_response('zerver/index.html',
                                  {'user_profile': user_profile,
                                   'page_params' : simplejson.encoder.JSONEncoderForHTML().encode(page_params),
                                   'nofontface': is_buggy_ua(request.META.get("HTTP_USER_AGENT", "Unspecified")),
                                   'avatar_url': avatar_url(user_profile),
                                   'show_debug':
                                       settings.DEBUG and ('show_debug' in request.GET),
                                   'pipeline': settings.PIPELINE_ENABLED,
                                   'show_invites': show_invites,
                                   'is_admin': user_profile.is_realm_admin,
                                   'show_webathena': user_profile.realm.webathena_enabled,
                                   'enable_feedback': settings.ENABLE_FEEDBACK,
                                   'embedded': narrow_stream is not None,
                                   'product_name': product_name
                                   },
                                  request=request)
    patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
    return response

@zulip_login_required
def desktop_home(request):
    # type: (HttpRequest) -> HttpResponse
    return HttpResponseRedirect(reverse('zerver.views.home'))

def is_buggy_ua(agent):
    # type: (str) -> bool
    """Discrimiate CSS served to clients based on User Agent

    Due to QTBUG-3467, @font-face is not supported in QtWebKit.
    This may get fixed in the future, but for right now we can
    just serve the more conservative CSS to all our desktop apps.
    """
    return ("Humbug Desktop/" in agent or "Zulip Desktop/" in agent or "ZulipDesktop/" in agent) and \
        "Mac" not in agent

def get_pointer_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return json_success({'pointer': user_profile.pointer})

@has_request_variables
def update_pointer_backend(request, user_profile,
                           pointer=REQ(converter=to_non_negative_int)):
    # type: (HttpRequest, UserProfile, int) -> HttpResponse
    if pointer <= user_profile.pointer:
        return json_success()

    try:
        UserMessage.objects.get(
            user_profile=user_profile,
            message__id=pointer
        )
    except UserMessage.DoesNotExist:
        raise JsonableError(_("Invalid message ID"))

    request._log_data["extra"] = "[%s]" % (pointer,)
    update_flags = (request.client.name.lower() in ['android', "zulipandroid"])
    do_update_pointer(user_profile, pointer, update_flags=update_flags)

    return json_success()

def generate_client_id():
    # type: () -> text_type
    return generate_random_token(32)

def get_profile_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    result = dict(pointer        = user_profile.pointer,
                  client_id      = generate_client_id(),
                  max_message_id = -1)

    messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
    if messages:
        result['max_message_id'] = messages[0].id

    return json_success(result)

@csrf_exempt
@require_post
@has_request_variables
def api_fetch_api_key(request, username=REQ(), password=REQ()):
    # type: (HttpRequest, str, str) -> HttpResponse
    return_data = {} # type: Dict[str, bool]
    if username == "google-oauth2-token":
        user_profile = authenticate(google_oauth2_token=password, return_data=return_data)
    else:
        user_profile = authenticate(username=username, password=password, return_data=return_data)
    if return_data.get("inactive_user") == True:
        return json_error(_("Your account has been disabled."),
                          data={"reason": "user disable"}, status=403)
    if return_data.get("inactive_realm") == True:
        return json_error(_("Your realm has been deactivated."),
                          data={"reason": "realm deactivated"}, status=403)
    if return_data.get("password_auth_disabled") == True:
        return json_error(_("Password auth is disabled in your team."),
                          data={"reason": "password auth disabled"}, status=403)
    if user_profile is None:
        if return_data.get("valid_attestation") == True:
            # We can leak that the user is unregistered iff they present a valid authentication string for the user.
            return json_error(_("This user is not registered; do so from a browser."),
                              data={"reason": "unregistered"}, status=403)
        return json_error(_("Your username or password is incorrect."),
                          data={"reason": "incorrect_creds"}, status=403)
    return json_success({"api_key": user_profile.api_key, "email": user_profile.email})

@csrf_exempt
def api_get_auth_backends(request):
    # type: (HttpRequest) -> HttpResponse
    # May return a false positive for password auth if it's been disabled
    # for a specific realm. Currently only happens for zulip.com on prod
    return json_success({"password": password_auth_enabled(None),
                         "dev": dev_auth_enabled(),
                         "google": google_auth_enabled(),
                        })

@authenticated_json_post_view
@has_request_variables
def json_fetch_api_key(request, user_profile, password=REQ(default='')):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    if password_auth_enabled(user_profile.realm):
        if not authenticate(username=user_profile.email, password=password):
            return json_error(_("Your username or password is incorrect."))
    return json_success({"api_key": user_profile.api_key})

@csrf_exempt
def api_fetch_google_client_id(request):
    # type: (HttpRequest) -> HttpResponse
    if not settings.GOOGLE_CLIENT_ID:
        return json_error(_("GOOGLE_CLIENT_ID is not configured"), status=400)
    return json_success({"google_client_id": settings.GOOGLE_CLIENT_ID})

# Does not need to be authenticated because it's called from rest_dispatch
@has_request_variables
def api_events_register(request, user_profile,
                        apply_markdown=REQ(default=False, validator=check_bool),
                        all_public_streams=REQ(default=None, validator=check_bool)):
    # type: (HttpRequest, UserProfile, bool, Optional[bool]) -> HttpResponse
    return events_register_backend(request, user_profile,
                                   apply_markdown=apply_markdown,
                                   all_public_streams=all_public_streams)

def _default_all_public_streams(user_profile, all_public_streams):
    # type: (UserProfile, Optional[bool]) -> bool
    if all_public_streams is not None:
        return all_public_streams
    else:
        return user_profile.default_all_public_streams

def _default_narrow(user_profile, narrow):
    # type: (UserProfile, Iterable[Sequence[text_type]]) -> Iterable[Sequence[text_type]]
    default_stream = user_profile.default_events_register_stream
    if not narrow and user_profile.default_events_register_stream is not None:
        narrow = [['stream', default_stream.name]]
    return narrow

@has_request_variables
def events_register_backend(request, user_profile, apply_markdown=True,
                            all_public_streams=None,
                            event_types=REQ(validator=check_list(check_string), default=None),
                            narrow=REQ(validator=check_list(check_list(check_string, length=2)), default=[]),
                            queue_lifespan_secs=REQ(converter=int, default=0)):
    # type: (HttpRequest, UserProfile, bool, Optional[bool], Optional[Iterable[str]], Iterable[Sequence[text_type]], int) -> HttpResponse
    all_public_streams = _default_all_public_streams(user_profile, all_public_streams)
    narrow = _default_narrow(user_profile, narrow)

    ret = do_events_register(user_profile, request.client, apply_markdown,
                             event_types, queue_lifespan_secs, all_public_streams,
                             narrow=narrow)
    return json_success(ret)


@authenticated_json_post_view
@has_request_variables
def json_refer_friend(request, user_profile, email=REQ()):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    if not email:
        return json_error(_("No email address specified"))
    if user_profile.invites_granted - user_profile.invites_used <= 0:
        return json_error(_("Insufficient invites"))

    do_refer_friend(user_profile, email);

    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_set_muted_topics(request, user_profile,
                         muted_topics=REQ(validator=check_list(check_list(check_string, length=2)), default=[])):
    # type: (HttpRequest, UserProfile, List[List[text_type]]) -> HttpResponse
    do_set_muted_topics(user_profile, muted_topics)
    return json_success()

def generate_204(request):
    # type: (HttpRequest) -> HttpResponse
    return HttpResponse(content=None, status=204)

def process_unsubscribe(token, subscription_type, unsubscribe_function):
    # type: (HttpRequest, str, Callable[[UserProfile], None]) -> HttpResponse
    try:
        confirmation = Confirmation.objects.get(confirmation_key=token)
    except Confirmation.DoesNotExist:
        return render_to_response('zerver/unsubscribe_link_error.html')

    user_profile = confirmation.content_object
    unsubscribe_function(user_profile)
    return render_to_response('zerver/unsubscribe_success.html',
                              {"subscription_type": subscription_type,
                               "external_host": settings.EXTERNAL_HOST,
                               'external_uri_scheme': settings.EXTERNAL_URI_SCHEME,
                               'server_uri': settings.SERVER_URI,
                               'realm_uri': user_profile.realm.uri,
                              })

# Email unsubscribe functions. All have the function signature
# processor(user_profile).

def do_missedmessage_unsubscribe(user_profile):
    # type: (UserProfile) -> None
    do_change_enable_offline_email_notifications(user_profile, False)

def do_welcome_unsubscribe(user_profile):
    # type: (UserProfile) -> None
    clear_followup_emails_queue(user_profile.email)

def do_digest_unsubscribe(user_profile):
    # type: (UserProfile) -> None
    do_change_enable_digest_emails(user_profile, False)

# The keys are part of the URL for the unsubscribe link and must be valid
# without encoding.
# The values are a tuple of (display name, unsubscribe function), where the
# display name is what we call this class of email in user-visible text.
email_unsubscribers = {
    "missed_messages": ("missed messages", do_missedmessage_unsubscribe),
    "welcome": ("welcome", do_welcome_unsubscribe),
    "digest": ("digest", do_digest_unsubscribe)
    }

# Login NOT required. These are for one-click unsubscribes.
def email_unsubscribe(request, type, token):
    # type: (HttpRequest, str, str) -> HttpResponse
    if type in email_unsubscribers:
        display_name, unsubscribe_function = email_unsubscribers[type]
        return process_unsubscribe(token, display_name, unsubscribe_function)

    return render_to_response('zerver/unsubscribe_link_error.html', {},
                              request=request)
