from __future__ import absolute_import

from django.conf import settings
from django.contrib.auth import authenticate, login, get_backends
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext, loader
from django.utils.timezone import now
from django.utils.cache import patch_cache_control
from django.core.exceptions import ValidationError
from django.core import validators
from django.contrib.auth.views import login as django_login_page, \
    logout_then_login as django_logout_then_login
from django.db.models import Q, F
from django.forms.models import model_to_dict
from django.core.mail import send_mail
from django.middleware.csrf import get_token
from django.db import transaction
from zerver.models import Message, UserProfile, Stream, Subscription, Huddle, \
    Recipient, Realm, UserMessage, DefaultStream, RealmEmoji, RealmAlias, \
    RealmFilter, bulk_get_recipients, \
    PreregistrationUser, get_client, MitUser, UserActivity, PushDeviceToken, \
    get_stream, bulk_get_streams, UserPresence, \
    get_recipient, valid_stream_name, \
    split_email_to_domain, resolve_email_to_domain, email_to_username, get_realm, \
    completely_open, get_unique_open_realm, get_active_user_dicts_in_realm, remote_user_to_email
from zerver.lib.actions import bulk_remove_subscriptions, do_change_password, \
    do_change_full_name, do_change_enable_desktop_notifications, do_change_is_admin, \
    do_change_enter_sends, do_change_enable_sounds, do_activate_user, do_create_user, \
    do_change_subscription_property, internal_send_message, \
    create_stream_if_needed, gather_subscriptions, subscribed_to_stream, \
    update_user_presence, bulk_add_subscriptions, do_events_register, \
    get_status_dict, do_change_enable_offline_email_notifications, \
    do_change_enable_digest_emails, do_set_realm_name, do_set_realm_restricted_to_domain, \
    do_set_realm_invite_required, do_set_realm_invite_by_admins_only, internal_prep_message, \
    do_send_messages, get_default_subs, do_deactivate_user, do_reactivate_user, \
    user_email_is_unique, do_invite_users, do_refer_friend, compute_mit_user_fullname, \
    do_add_alert_words, do_remove_alert_words, do_set_alert_words, get_subscriber_emails, \
    do_set_muted_topics, do_rename_stream, clear_followup_emails_queue, \
    do_change_enable_offline_push_notifications, \
    do_deactivate_stream, do_change_autoscroll_forever, do_make_stream_public, \
    do_add_default_stream, do_change_default_all_public_streams, \
    do_change_default_desktop_notifications, \
    do_change_default_events_register_stream, do_change_default_sending_stream, \
    do_change_enable_stream_desktop_notifications, do_change_enable_stream_sounds, \
    do_change_stream_description, do_get_streams, do_make_stream_private, \
    do_regenerate_api_key, do_remove_default_stream, do_update_pointer, \
    do_change_avatar_source, do_change_twenty_four_hour_time, do_change_left_side_userlist, \
    realm_user_count

from zerver.lib.create_user import random_api_key
from zerver.lib.push_notifications import num_push_devices_for_user
from zerver.forms import RegistrationForm, HomepageForm, ToSForm, \
    CreateUserForm, is_inactive, OurAuthenticationForm
from django.views.decorators.csrf import csrf_exempt
from django_auth_ldap.backend import LDAPBackend, _LDAPUser
from zerver.lib import bugdown
from zerver.lib.alert_words import user_alert_words
from zerver.lib.validator import check_string, check_list, check_dict, \
    check_int, check_bool, check_variable_type
from zerver.decorator import require_post, \
    authenticated_api_view, authenticated_json_post_view, \
    has_request_variables, authenticated_json_view, to_non_negative_int, \
    JsonableError, get_user_profile_by_email, REQ, require_realm_admin, \
    RequestVariableConversionError
from zerver.lib.avatar import avatar_url, get_avatar_url
from zerver.lib.upload import upload_message_image_through_web_client, upload_avatar_image, \
    get_signed_upload_url, get_realm_for_filename
from zerver.lib.response import json_success, json_error, json_response
from zerver.lib.unminify import SourceMap
from zerver.lib.queue import queue_json_publish
from zerver.lib.utils import statsd, generate_random_token, statsd_key
from zproject.backends import password_auth_enabled, dev_auth_enabled

from confirmation.models import Confirmation

import requests

import subprocess
import calendar
import datetime
import ujson
import simplejson
import re
import urllib
import base64
import time
import logging
import os
import jwt
import hashlib
import hmac
from collections import defaultdict

from zerver.lib.rest import rest_dispatch as _rest_dispatch
from six.moves import map
rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))

def list_to_streams(streams_raw, user_profile, autocreate=False, invite_only=False):
    """Converts plaintext stream names to a list of Streams, validating input in the process

    For each stream name, we validate it to ensure it meets our
    requirements for a proper stream name: that is, that it is shorter
    than Stream.MAX_NAME_LENGTH characters and passes
    valid_stream_name.

    This function in autocreate mode should be atomic: either an exception will be raised
    during a precheck, or all the streams specified will have been created if applicable.

    @param streams_raw The list of stream names to process
    @param user_profile The user for whom we are retreiving the streams
    @param autocreate Whether we should create streams if they don't already exist
    @param invite_only Whether newly created streams should have the invite_only bit set
    """
    existing_streams = []
    created_streams = []
    # Validate all streams, getting extant ones, then get-or-creating the rest.
    stream_set = set(stream_name.strip() for stream_name in streams_raw)
    rejects = []
    for stream_name in stream_set:
        if len(stream_name) > Stream.MAX_NAME_LENGTH:
            raise JsonableError("Stream name (%s) too long." % (stream_name,))
        if not valid_stream_name(stream_name):
            raise JsonableError("Invalid stream name (%s)." % (stream_name,))

    existing_stream_map = bulk_get_streams(user_profile.realm, stream_set)

    for stream_name in stream_set:
        stream = existing_stream_map.get(stream_name.lower())
        if stream is None:
            rejects.append(stream_name)
        else:
            existing_streams.append(stream)
    if autocreate:
        for stream_name in rejects:
            stream, created = create_stream_if_needed(user_profile.realm,
                                                      stream_name,
                                                      invite_only=invite_only)
            if created:
                created_streams.append(stream)
            else:
                existing_streams.append(stream)
    elif rejects:
        raise JsonableError("Stream(s) (%s) do not exist" % ", ".join(rejects))

    return existing_streams, created_streams

class PrincipalError(JsonableError):
    def __init__(self, principal):
        self.principal = principal

    def to_json_error_msg(self):
        return ("User not authorized to execute queries on behalf of '%s'"
                % (self.principal,))

def principal_to_user_profile(agent, principal):
    principal_doesnt_exist = False
    try:
        principal_user_profile = get_user_profile_by_email(principal)
    except UserProfile.DoesNotExist:
        principal_doesnt_exist = True

    if (principal_doesnt_exist
        or agent.realm != principal_user_profile.realm):
        # We have to make sure we don't leak information about which users
        # are registered for Zulip in a different realm.  We could do
        # something a little more clever and check the domain part of the
        # principal to maybe give a better error message
        raise PrincipalError(principal)

    return principal_user_profile

def name_changes_disabled(realm):
    return settings.NAME_CHANGES_DISABLED or realm.name_changes_disabled

@require_post
def accounts_register(request):
    key = request.POST['key']
    confirmation = Confirmation.objects.get(confirmation_key=key)
    prereg_user = confirmation.content_object
    email = prereg_user.email
    mit_beta_user = isinstance(confirmation.content_object, MitUser)
    try:
        existing_user_profile = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        existing_user_profile = None

    validators.validate_email(email)
    # If someone invited you, you are joining their realm regardless
    # of your e-mail address.
    #
    # MitUsers can't be referred and don't have a referred_by field.
    if not mit_beta_user and prereg_user.referred_by:
        realm = prereg_user.referred_by.realm
        domain = realm.domain
        if realm.restricted_to_domain and domain != resolve_email_to_domain(email):
            return render_to_response("zerver/closed_realm.html", {"closed_domain_name": realm.name})
    elif not mit_beta_user and prereg_user.realm:
        # You have a realm set, even though nobody referred you. This
        # happens if you sign up through a special URL for an open
        # realm.
        domain = prereg_user.realm.domain
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
        return HttpResponseRedirect(reverse('django.contrib.auth.views.login') + '?email=' + urllib.quote_plus(email))

    name_validated = False
    full_name = None

    if request.POST.get('from_confirmation'):
        try:
            del request.session['authenticated_full_name']
        except KeyError:
            pass
        if domain == "mit.edu":
            hesiod_name = compute_mit_user_fullname(email)
            form = RegistrationForm(
                    initial={'full_name': hesiod_name if "@" not in hesiod_name else ""})
            name_validated = True
        elif settings.POPULATE_PROFILE_VIA_LDAP:
            for backend in get_backends():
                if isinstance(backend, LDAPBackend):
                    ldap_attrs = _LDAPUser(backend, backend.django_to_ldap_username(email)).attrs
                    try:
                        request.session['authenticated_full_name'] = ldap_attrs[settings.AUTH_LDAP_USER_ATTR_MAP['full_name']][0]
                        name_validated = True
                        # We don't use initial= here, because if the form is
                        # complete (that is, no additional fields need to be
                        # filled out by the user) we want the form to validate,
                        # so they can be directly registered without having to
                        # go through this interstitial.
                        form = RegistrationForm(
                            {'full_name': request.session['authenticated_full_name']})
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
                                              newsletter_data={"IP": request.META['REMOTE_ADDR']})
        else:
            user_profile = do_create_user(email, password, realm, full_name, short_name,
                                          prereg_user=prereg_user,
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
             'password_auth_enabled': password_auth_enabled(realm),
            },
        context_instance=RequestContext(request))

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
def accounts_accept_terms(request):
    email = request.user.email
    domain = resolve_email_to_domain(email)
    if request.method == "POST":
        form = ToSForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data['full_name']
            send_mail('Terms acceptance for ' + full_name,
                    loader.render_to_string('zerver/tos_accept_body.txt',
                        {'name': full_name,
                         'email': email,
                         'ip': request.META['REMOTE_ADDR'],
                         'browser': request.META['HTTP_USER_AGENT']}),
                        settings.EMAIL_HOST_USER,
                        ["all@zulip.com"])
            do_change_full_name(request.user, full_name)
            return redirect(home)

    else:
        form = ToSForm()
    return render_to_response('zerver/accounts_accept_terms.html',
        { 'form': form, 'company_name': domain, 'email': email },
        context_instance=RequestContext(request))

from zerver.lib.ccache import make_ccache

@authenticated_json_view
@has_request_variables
def webathena_kerberos_login(request, user_profile,
                             cred=REQ(default=None)):
    if cred is None:
        return json_error("Could not find Kerberos credential")
    if not user_profile.realm.domain == "mit.edu":
        return json_error("Webathena login only for mit.edu realm")

    try:
        parsed_cred = ujson.loads(cred)
        user = parsed_cred["cname"]["nameString"][0]
        if user == "golem":
            # Hack for an mit.edu user whose Kerberos username doesn't
            # match what he zephyrs as
            user = "ctl"
        assert(user == user_profile.email.split("@")[0])
        ccache = make_ccache(parsed_cred)
    except Exception:
        return json_error("Invalid Kerberos cache")

    # TODO: Send these data via (say) rabbitmq
    try:
        subprocess.check_call(["ssh", "zulip@zmirror2.zulip.net", "--",
                               "/home/zulip/zulip/bots/process_ccache",
                               user,
                               user_profile.api_key,
                               base64.b64encode(ccache)])
    except Exception:
        logging.exception("Error updating the user's ccache")
        return json_error("We were unable to setup mirroring for you")

    return json_success()

def api_endpoint_docs(request):
    raw_calls = open('templates/zerver/api_content.json', 'r').read()
    calls = ujson.loads(raw_calls)
    langs = set()
    for call in calls:
        call["endpoint"] = "%s/v1/%s" % (settings.EXTERNAL_API_URI, call["endpoint"])
        call["example_request"]["curl"] = call["example_request"]["curl"].replace("https://api.zulip.com", settings.EXTERNAL_API_URI)
        response = call['example_response']
        if not '\n' in response:
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
        context_instance=RequestContext(request))

@authenticated_json_post_view
@has_request_variables
def json_invite_users(request, user_profile, invitee_emails=REQ):
    if not invitee_emails:
        return json_error("You must specify at least one email address.")

    invitee_emails = set(re.split(r'[, \n]', invitee_emails))

    stream_names = request.POST.getlist('stream')
    if not stream_names:
        return json_error("You must specify at least one stream for invitees to join.")

    # We unconditionally sub you to the notifications stream if it
    # exists and is public.
    notifications_stream = user_profile.realm.notifications_stream
    if notifications_stream and not notifications_stream.invite_only:
        stream_names.append(notifications_stream.name)

    streams = []
    for stream_name in stream_names:
        stream = get_stream(stream_name, user_profile.realm)
        if stream is None:
            return json_error("Stream does not exist: %s. No invites were sent." % stream_name)
        streams.append(stream)

    ret_error, error_data = do_invite_users(user_profile, invitee_emails, streams)

    if ret_error is not None:
        return json_error(data=error_data, msg=ret_error)
    else:
        return json_success()

def create_homepage_form(request, user_info=None):
    if user_info:
        return HomepageForm(user_info, domain=request.session.get("domain"))
    # An empty fields dict is not treated the same way as not
    # providing it.
    return HomepageForm(domain=request.session.get("domain"))

def maybe_send_to_registration(request, email, full_name=''):
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
            urllib.quote_plus(full_name.encode('utf8')))))
    else:
        return render_to_response('zerver/accounts_home.html', {'form': form},
                                  context_instance=RequestContext(request))

def login_or_register_remote_user(request, remote_username, user_profile, full_name=''):
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
    try:
        remote_user = request.META["REMOTE_USER"]
    except KeyError:
        raise JsonableError("No REMOTE_USER set.")

    user_profile = authenticate(remote_user=remote_user)
    return login_or_register_remote_user(request, remote_user, user_profile)

@csrf_exempt
def remote_user_jwt(request):
    try:
        json_web_token = request.POST["json_web_token"]
        payload, signing_input, header, signature = jwt.load(json_web_token)
    except KeyError:
        raise JsonableError("No JSON web token passed in request")
    except jwt.DecodeError:
        raise JsonableError("Bad JSON web token")

    remote_user = payload.get("user", None)
    if remote_user is None:
        raise JsonableError("No user specified in JSON web token claims")
    domain = payload.get('realm', None)
    if domain is None:
        raise JsonableError("No domain specified in JSON web token claims")

    email = "%s@%s" % (remote_user, domain)

    try:
        jwt.verify_signature(payload, signing_input, header, signature,
                             settings.JWT_AUTH_KEYS[domain])
        # We do all the authentication we need here (otherwise we'd have to
        # duplicate work), but we need to call authenticate with some backend so
        # that the request.backend attribute gets set.
        user_profile = authenticate(username=email, use_dummy_backend=True)
    except (jwt.DecodeError, jwt.ExpiredSignature):
        raise JsonableError("Bad JSON web token signature")
    except KeyError:
        raise JsonableError("Realm not authorized for JWT login")
    except UserProfile.DoesNotExist:
        user_profile = None

    return login_or_register_remote_user(request, email, user_profile, remote_user)

def google_oauth2_csrf(request, value):
    return hmac.new(get_token(request).encode('utf-8'), value, hashlib.sha256).hexdigest()

def start_google_oauth2(request):
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
    return redirect(uri + urllib.urlencode(prams))

# Workaround to support the Python-requests 1.0 transition of .json
# from a property to a function
requests_json_is_function = callable(requests.Response.json)
def extract_json_response(resp):
    if requests_json_is_function:
        return resp.json()
    else:
        return resp.json

def finish_google_oauth2(request):
    error = request.GET.get('error')
    if error == 'access_denied':
        return redirect('/')
    elif error is not None:
        logging.error('Error from google oauth2 login %r', request.GET)
        return HttpResponse(status=400)

    value, hmac_value = request.GET.get('state').split(':')
    if hmac_value != google_oauth2_csrf(request, value):
        raise Exception('Google oauth2 CSRF error')

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
    if resp.status_code != 200:
        raise Exception('Could not convert google pauth2 code to access_token\r%r' % resp.text)
    access_token = extract_json_response(resp)['access_token']

    resp = requests.get(
        'https://www.googleapis.com/plus/v1/people/me',
        params={'access_token': access_token}
    )
    if resp.status_code != 200:
        raise Exception('Google login failed making API call\r%r' % resp.text)
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
        raise Exception('Google oauth2 account email not found %r' % body)
    email_address = email['value']
    user_profile = authenticate(username=email_address, use_dummy_backend=True)
    return login_or_register_remote_user(request, email_address, user_profile, full_name)

def login_page(request, **kwargs):
    extra_context = kwargs.pop('extra_context', {})
    if dev_auth_enabled():
        users = UserProfile.objects.filter(is_bot=False, is_active=True)
        extra_context['direct_admins'] = sorted([u.email for u in users if u.is_admin()])
        extra_context['direct_users'] = sorted([u.email for u in users if not u.is_admin()])
    template_response = django_login_page(
        request, authentication_form=OurAuthenticationForm,
        extra_context=extra_context, **kwargs)
    try:
        template_response.context_data['email'] = request.GET['email']
    except KeyError:
        pass

    return template_response

def dev_direct_login(request, **kwargs):
    # This function allows logging in without a password and should only be called in development environments.
    # It may be called if the DevAuthBackend is included in settings.AUTHENTICATION_BACKENDS
    if (not dev_auth_enabled()) or settings.PRODUCTION:
        # This check is probably not required, since authenticate would fail without an enabled DevAuthBackend.
        raise Exception('Direct login not supported.')
    email = request.POST['direct_email']
    user_profile = authenticate(username=email)
    login(request, user_profile)
    return HttpResponseRedirect("%s%s" % (settings.EXTERNAL_URI_SCHEME,
                                          request.get_host()))

@authenticated_json_post_view
@has_request_variables
def json_bulk_invite_users(request, user_profile,
                           invitee_emails=REQ(validator=check_list(check_string))):
    invitee_emails = set(invitee_emails)
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

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
def initial_invite_page(request):
    user = request.user
    # Only show the bulk-invite page for the first user in a realm
    domain_count = len(UserProfile.objects.filter(realm=user.realm))
    if domain_count > 1:
        return redirect('zerver.views.home')

    params = {'company_name': user.realm.domain}

    if (user.realm.restricted_to_domain):
        params['invite_suffix'] = user.realm.domain

    return render_to_response('zerver/initial_invite_page.html', params,
                              context_instance=RequestContext(request))

@require_post
def logout_then_login(request, **kwargs):
    return django_logout_then_login(request, kwargs)

def create_preregistration_user(email, request):
    domain = request.session.get("domain")
    if completely_open(domain):
        # Clear the "domain" from the session object; it's no longer needed
        request.session["domain"] = None

        # The user is trying to sign up for a completely open realm,
        # so create them a PreregistrationUser for that realm
        return PreregistrationUser.objects.create(email=email,
                                                  realm=get_realm(domain))

    # MIT users who are not explicitly signing up for an open realm
    # require special handling (They may already have an (inactive)
    # account, for example)
    if split_email_to_domain(email) == "mit.edu":
        return MitUser.objects.get_or_create(email=email)[0]
    return PreregistrationUser.objects.create(email=email)

def accounts_home_with_domain(request, domain):
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

def send_registration_completion_email(email, request):
    """
    Send an email with a confirmation link to the provided e-mail so the user
    can complete their registration.
    """
    prereg_user = create_preregistration_user(email, request)
    context = {'support_email': settings.ZULIP_ADMINISTRATOR,
               'voyager': settings.VOYAGER}
    Confirmation.objects.send_confirmation(prereg_user, email,
                                           additional_context=context)

def accounts_home(request):
    # First we populate request.session with a domain if
    # there is a single realm, which is open.
    # This is then used in HomepageForm and in creating a PreregistrationUser
    unique_realm = get_unique_open_realm()
    if unique_realm:
        request.session['domain'] = unique_realm.domain

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
            return HttpResponseRedirect(reverse('django.contrib.auth.views.login') + '?email=' + urllib.quote_plus(email))
    else:
        form = create_homepage_form(request)
    return render_to_response('zerver/accounts_home.html',
                              {'form': form, 'current_url': request.get_full_path},
                              context_instance=RequestContext(request))

def approximate_unread_count(user_profile):
    not_in_home_view_recipients = [sub.recipient.id for sub in \
                                       Subscription.objects.filter(
            user_profile=user_profile, in_home_view=False)]

    muted_topics = ujson.loads(user_profile.muted_topics)
    # If muted_topics is empty, it looks like []. If it is non-empty, it look
    # like [[u'devel', u'test']]. We should switch to a consistent envelope, but
    # until we do we still have both in the database.
    if muted_topics:
        muted_topics = muted_topics[0]

    return UserMessage.objects.filter(
        user_profile=user_profile, message_id__gt=user_profile.pointer).exclude(
        message__recipient__type=Recipient.STREAM,
        message__recipient__id__in=not_in_home_view_recipients).exclude(
        message__subject__in=muted_topics).exclude(
        flags=UserMessage.flags.read).count()

def sent_time_in_epoch_seconds(user_message):
    # user_message is a UserMessage object.
    if not user_message:
        return None
    # We have USE_TZ = True, so our datetime objects are timezone-aware.
    # Return the epoch seconds in UTC.
    return calendar.timegm(user_message.message.pub_date.utctimetuple())

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
def home(request):
    # We need to modify the session object every two weeks or it will expire.
    # This line makes reloading the page a sufficient action to keep the
    # session alive.
    request.session.modified = True

    user_profile = request.user
    request._email = request.user.email
    request.client = get_client("website")

    narrow = []
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

    # Pass parameters to the client-side JavaScript code.
    # These end up in a global JavaScript Object named 'page_params'.
    page_params = dict(
        voyager               = settings.VOYAGER,
        debug_mode            = settings.DEBUG,
        test_suite            = settings.TEST_SUITE,
        poll_timeout          = settings.POLL_TIMEOUT,
        login_page            = settings.HOME_NOT_LOGGED_IN,
        password_auth_enabled = password_auth_enabled(user_profile.realm),
        have_initial_messages = user_has_messages,
        subbed_info           = register_ret['subscriptions'],
        unsubbed_info         = register_ret['unsubscribed'],
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
        realm_restricted_to_domain = register_ret['realm_restricted_to_domain'],
        enter_sends           = user_profile.enter_sends,
        left_side_userlist    = register_ret['left_side_userlist'],
        referrals             = register_ret['referrals'],
        realm_emoji           = register_ret['realm_emoji'],
        needs_tutorial        = needs_tutorial,
        first_in_realm        = first_in_realm,
        prompt_for_invites    = prompt_for_invites,
        notifications_stream  = notifications_stream,

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
        staging               = settings.ZULIP_COM_STAGING or settings.DEVELOPMENT,
        alert_words           = register_ret['alert_words'],
        muted_topics          = register_ret['muted_topics'],
        realm_filters         = register_ret['realm_filters'],
        is_admin              = user_profile.is_admin(),
        can_create_streams    = user_profile.can_create_streams(),
        name_changes_disabled = name_changes_disabled(user_profile.realm),
        has_mobile_devices    = num_push_devices_for_user(user_profile) > 0,
        autoscroll_forever = user_profile.autoscroll_forever,
        default_desktop_notifications = user_profile.default_desktop_notifications,
        avatar_url            = avatar_url(user_profile),
        mandatory_topics      = user_profile.realm.mandatory_topics,
        show_digest_email     = user_profile.realm.show_digest_email,
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
    if user_profile.realm.invite_by_admins_only and not user_profile.is_admin():
        show_invites = False

    product_name = "Zulip"
    page_params['product_name'] = product_name
    request._log_data['extra'] = "[%s]" % (register_ret["queue_id"],)
    response = render_to_response('zerver/index.html',
                                  {'user_profile': user_profile,
                                   'page_params' : simplejson.encoder.JSONEncoderForHTML().encode(page_params),
                                   'nofontface': is_buggy_ua(request.META["HTTP_USER_AGENT"]),
                                   'avatar_url': avatar_url(user_profile),
                                   'show_debug':
                                       settings.DEBUG and ('show_debug' in request.GET),
                                   'show_invites': show_invites,
                                   'is_admin': user_profile.is_admin(),
                                   'show_webathena': user_profile.realm.domain == "mit.edu",
                                   'enable_feedback': settings.ENABLE_FEEDBACK,
                                   'embedded': narrow_stream is not None,
                                   'product_name': product_name
                                   },
                                  context_instance=RequestContext(request))
    patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
    return response

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
def desktop_home(request):
    return HttpResponseRedirect(reverse('zerver.views.home'))

def is_buggy_ua(agent):
    """Discrimiate CSS served to clients based on User Agent

    Due to QTBUG-3467, @font-face is not supported in QtWebKit.
    This may get fixed in the future, but for right now we can
    just serve the more conservative CSS to all our desktop apps.
    """
    return ("Humbug Desktop/" in agent or "Zulip Desktop/" in agent or "ZulipDesktop/" in agent) and \
        not "Mac" in agent

def get_pointer_backend(request, user_profile):
    return json_success({'pointer': user_profile.pointer})

@authenticated_json_post_view
def json_update_pointer(request, user_profile):
    return update_pointer_backend(request, user_profile)

@has_request_variables
def update_pointer_backend(request, user_profile,
                           pointer=REQ(converter=to_non_negative_int)):
    if pointer <= user_profile.pointer:
        return json_success()

    try:
        UserMessage.objects.get(
            user_profile=user_profile,
            message__id=pointer
        )
    except UserMessage.DoesNotExist:
        raise JsonableError("Invalid message ID")

    request._log_data["extra"] = "[%s]" % (pointer,)
    update_flags = (request.client.name.lower() in ['android', "zulipandroid"])
    do_update_pointer(user_profile, pointer, update_flags=update_flags)

    return json_success()

def generate_client_id():
    return generate_random_token(32)

@authenticated_json_post_view
def json_get_profile(request, user_profile):
    return get_profile_backend(request, user_profile)

# The order of creation of the various dictionaries are important.
# We filter on {userprofile,stream,subscription_recipient}_ids.
@require_realm_admin
def export(request, user_profile):
    if (Message.objects.filter(sender__realm=user_profile.realm).count() > 1000000 or
        UserMessage.objects.filter(user_profile__realm=user_profile.realm).count() > 3000000):
        return json_error("Realm has too much data for non-batched export.")

    response = {}

    response['zerver_realm'] = [model_to_dict(x)
        for x in Realm.objects.select_related().filter(id=user_profile.realm.id)]

    response['zerver_userprofile'] = [model_to_dict(x, exclude=["password", "api_key"])
                                      for x in UserProfile.objects.select_related().filter(realm=user_profile.realm)]

    userprofile_ids = set(userprofile["id"] for userprofile in response['zerver_userprofile'])

    response['zerver_stream'] = [model_to_dict(x, exclude=["email_token"])
                                 for x in Stream.objects.select_related().filter(realm=user_profile.realm, invite_only=False)]

    stream_ids = set(x["id"] for x in response['zerver_stream'])

    response['zerver_usermessage'] = [model_to_dict(x) for x in UserMessage.objects.select_related()
                                 if x.user_profile_id in userprofile_ids]

    user_recipients = [model_to_dict(x)
                       for x in Recipient.objects.select_related().filter(type=1)
                       if x.type_id in userprofile_ids]

    stream_recipients = [model_to_dict(x)
                         for x in Recipient.objects.select_related().filter(type=2)
                         if x.type_id in stream_ids]

    stream_recipient_ids = set(x["id"] for x in stream_recipients)

    # only check for subscriptions to streams
    response['zerver_subscription'] = [model_to_dict(x) for x in Subscription.objects.select_related()
                                 if x.user_profile_id in userprofile_ids
                                 and x.recipient_id in stream_recipient_ids]

    subscription_recipient_ids = set(x["recipient"] for x in response['zerver_subscription'])

    huddle_recipients = [model_to_dict(r)
                         for r in Recipient.objects.select_related().filter(type=3)
                         if r.type_id in subscription_recipient_ids]

    huddle_ids = set(x["type_id"] for x in huddle_recipients)

    response["zerver_recipient"] = user_recipients + stream_recipients + huddle_recipients

    response['zerver_huddle'] = [model_to_dict(h)
                                 for h in Huddle.objects.select_related()
                                 if h.id in huddle_ids]

    recipient_ids = set(x["id"] for x in response['zerver_recipient'])
    response["zerver_message"] = [model_to_dict(m) for m in Message.objects.select_related()
                                  if m.recipient_id in recipient_ids
                                  and m.sender_id in userprofile_ids]

    for (table, model) in [("defaultstream", DefaultStream),
                           ("realmemoji", RealmEmoji),
                           ("realmalias", RealmAlias),
                           ("realmfilter", RealmFilter)]:
        response["zerver_"+table] = [model_to_dict(x) for x in
                                     model.objects.select_related().filter(realm_id=user_profile.realm.id)]

    return json_success(response)

def get_profile_backend(request, user_profile):
    result = dict(pointer        = user_profile.pointer,
                  client_id      = generate_client_id(),
                  max_message_id = -1)

    messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
    if messages:
        result['max_message_id'] = messages[0].id

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_change_enter_sends(request, user_profile,
                            enter_sends=REQ('enter_sends', validator=check_bool)):
    do_change_enter_sends(user_profile, enter_sends)
    return json_success()


@authenticated_json_post_view
@has_request_variables
def json_tutorial_send_message(request, user_profile, type=REQ,
                               recipient=REQ, topic=REQ, content=REQ):
    """
    This function, used by the onboarding tutorial, causes the Tutorial Bot to
    send you the message you pass in here. (That way, the Tutorial Bot's
    messages to you get rendered by the server and therefore look like any other
    message.)
    """
    sender_name = "welcome-bot@zulip.com"
    if type == 'stream':
        internal_send_message(sender_name, "stream", recipient, topic, content,
                              realm=user_profile.realm)
        return json_success()
    # For now, there are no PM cases.
    return json_error('Bad data passed in to tutorial_send_message')

@authenticated_json_post_view
@has_request_variables
def json_tutorial_status(request, user_profile, status=REQ('status')):
    if status == 'started':
        user_profile.tutorial_status = UserProfile.TUTORIAL_STARTED
    elif status == 'finished':
        user_profile.tutorial_status = UserProfile.TUTORIAL_FINISHED
    user_profile.save(update_fields=["tutorial_status"])

    return json_success()

@authenticated_json_post_view
def json_get_public_streams(request, user_profile):
    return get_public_streams_backend(request, user_profile)

# By default, lists all streams that the user has access to --
# i.e. public streams plus invite-only streams that the user is on
@has_request_variables
def get_streams_backend(request, user_profile,
                        include_public=REQ(validator=check_bool, default=True),
                        include_subscribed=REQ(validator=check_bool, default=True),
                        include_all_active=REQ(validator=check_bool, default=False)):

    streams = do_get_streams(user_profile, include_public, include_subscribed,
                             include_all_active)
    return json_success({"streams": streams})

def get_public_streams_backend(request, user_profile):
    return get_streams_backend(request, user_profile, include_public=True,
                               include_subscribed=False, include_all_active=False)

@require_realm_admin
@has_request_variables
def update_realm(request, user_profile, name=REQ(validator=check_string, default=None),
                 restricted_to_domain=REQ(validator=check_bool, default=None),
                 invite_required=REQ(validator=check_bool, default=None),
                 invite_by_admins_only=REQ(validator=check_bool, default=None)):
    realm = user_profile.realm
    data = {}
    if name is not None and realm.name != name:
        do_set_realm_name(realm, name)
        data['name'] = 'updated'
    if restricted_to_domain is not None and realm.restricted_to_domain != restricted_to_domain:
        do_set_realm_restricted_to_domain(realm, restricted_to_domain)
        data['restricted_to_domain'] = restricted_to_domain
    if invite_required is not None and realm.invite_required != invite_required:
        do_set_realm_invite_required(realm, invite_required)
        data['invite_required'] = invite_required
    if invite_by_admins_only is not None and realm.invite_by_admins_only != invite_by_admins_only:
        do_set_realm_invite_by_admins_only(realm, invite_by_admins_only)
        data['invite_by_admins_only'] = invite_by_admins_only
    return json_success(data)

@require_realm_admin
@has_request_variables
def add_default_stream(request, user_profile, stream_name=REQ):
    return json_success(do_add_default_stream(user_profile.realm, stream_name))

@require_realm_admin
@has_request_variables
def remove_default_stream(request, user_profile, stream_name=REQ):
    return json_success(do_remove_default_stream(user_profile.realm, stream_name))

@authenticated_json_post_view
@require_realm_admin
@has_request_variables
def json_rename_stream(request, user_profile, old_name=REQ, new_name=REQ):
    return json_success(do_rename_stream(user_profile.realm, old_name, new_name))

@authenticated_json_post_view
@require_realm_admin
@has_request_variables
def json_make_stream_public(request, user_profile, stream_name=REQ):
    return json_success(do_make_stream_public(user_profile, user_profile.realm, stream_name))

@authenticated_json_post_view
@require_realm_admin
@has_request_variables
def json_make_stream_private(request, user_profile, stream_name=REQ):
    return json_success(do_make_stream_private(user_profile.realm, stream_name))

@require_realm_admin
@has_request_variables
def update_stream_backend(request, user_profile, stream_name,
                          description=REQ(validator=check_string, default=None)):
    if description is not None:
       do_change_stream_description(user_profile.realm, stream_name, description)
    return json_success({})

def list_subscriptions_backend(request, user_profile):
    return json_success({"subscriptions": gather_subscriptions(user_profile)[0]})

@transaction.atomic
@has_request_variables
def update_subscriptions_backend(request, user_profile,
                                 delete=REQ(validator=check_list(check_string), default=[]),
                                 add=REQ(validator=check_list(check_dict([['name', check_string]])), default=[])):
    if not add and not delete:
        return json_error('Nothing to do. Specify at least one of "add" or "delete".')

    json_dict = {}
    for method, items in ((add_subscriptions_backend, add), (remove_subscriptions_backend, delete)):
        response = method(request, user_profile, streams_raw=items)
        if response.status_code != 200:
            transaction.rollback()
            return response
        json_dict.update(ujson.loads(response.content))
    return json_success(json_dict)

@authenticated_json_post_view
def json_remove_subscriptions(request, user_profile):
    return remove_subscriptions_backend(request, user_profile)

@has_request_variables
def remove_subscriptions_backend(request, user_profile,
                                 streams_raw = REQ("subscriptions", validator=check_list(check_string)),
                                 principals = REQ(validator=check_list(check_string), default=None)):

    removing_someone_else = principals and \
        set(principals) != set((user_profile.email,))
    if removing_someone_else and not user_profile.is_admin():
        # You can only unsubscribe other people from a stream if you are a realm
        # admin.
        return json_error("This action requires administrative rights")

    streams, _ = list_to_streams(streams_raw, user_profile)

    for stream in streams:
        if removing_someone_else and stream.invite_only and \
                not subscribed_to_stream(user_profile, stream):
            # Even as an admin, you can't remove other people from an
            # invite-only stream you're not on.
            return json_error("Cannot administer invite-only streams this way")

    if principals:
        people_to_unsub = set(principal_to_user_profile(
                user_profile, principal) for principal in principals)
    else:
        people_to_unsub = [user_profile]

    result = dict(removed=[], not_subscribed=[])
    (removed, not_subscribed) = bulk_remove_subscriptions(people_to_unsub, streams)

    for (subscriber, stream) in removed:
        result["removed"].append(stream.name)
    for (subscriber, stream) in not_subscribed:
        result["not_subscribed"].append(stream.name)

    return json_success(result)

@authenticated_json_post_view
def json_add_subscriptions(request, user_profile):
    return add_subscriptions_backend(request, user_profile)

def filter_stream_authorization(user_profile, streams):
    streams_subscribed = set()
    recipients_map = bulk_get_recipients(Recipient.STREAM, [stream.id for stream in streams])
    subs = Subscription.objects.filter(user_profile=user_profile,
                                       recipient__in=recipients_map.values(),
                                       active=True)

    for sub in subs:
        streams_subscribed.add(sub.recipient.type_id)

    unauthorized_streams = []
    for stream in streams:
        # The user is authorized for his own streams
        if stream.id in streams_subscribed:
            continue

        # The user is not authorized for invite_only streams
        if stream.invite_only:
            unauthorized_streams.append(stream)

    streams = [stream for stream in streams if
               stream.id not in set(stream.id for stream in unauthorized_streams)]
    return streams, unauthorized_streams

def stream_link(stream_name):
    "Escapes a stream name to make a #narrow/stream/stream_name link"
    return "#narrow/stream/%s" % (urllib.quote(stream_name.encode('utf-8')),)

def stream_button(stream_name):
    stream_name = stream_name.replace('\\', '\\\\')
    stream_name = stream_name.replace(')', '\\)')
    return '!_stream_subscribe_button(%s)' % (stream_name,)

@has_request_variables
def add_subscriptions_backend(request, user_profile,
                              streams_raw = REQ("subscriptions",
                              validator=check_list(check_dict([['name', check_string]]))),
                              invite_only = REQ(validator=check_bool, default=False),
                              announce = REQ(validator=check_bool, default=False),
                              principals = REQ(validator=check_list(check_string), default=None),
                              authorization_errors_fatal = REQ(validator=check_bool, default=True)):

    if not user_profile.can_create_streams():
        return json_error('User cannot create streams.')

    stream_names = []
    for stream in streams_raw:
        stream_name = stream["name"].strip()
        if len(stream_name) > Stream.MAX_NAME_LENGTH:
            return json_error("Stream name (%s) too long." % (stream_name,))
        if not valid_stream_name(stream_name):
            return json_error("Invalid stream name (%s)." % (stream_name,))
        stream_names.append(stream_name)

    existing_streams, created_streams = \
        list_to_streams(stream_names, user_profile, autocreate=True, invite_only=invite_only)
    authorized_streams, unauthorized_streams = \
        filter_stream_authorization(user_profile, existing_streams)
    if len(unauthorized_streams) > 0 and authorization_errors_fatal:
        return json_error("Unable to access stream (%s)." % unauthorized_streams[0].name)
    # Newly created streams are also authorized for the creator
    streams = authorized_streams + created_streams

    if principals is not None:
        if user_profile.realm.domain == 'mit.edu' and not all(stream.invite_only for stream in streams):
            return json_error("You can only invite other mit.edu users to invite-only streams.")
        subscribers = set(principal_to_user_profile(user_profile, principal) for principal in principals)
    else:
        subscribers = [user_profile]

    (subscribed, already_subscribed) = bulk_add_subscriptions(streams, subscribers)

    result = dict(subscribed=defaultdict(list), already_subscribed=defaultdict(list))
    for (subscriber, stream) in subscribed:
        result["subscribed"][subscriber.email].append(stream.name)
    for (subscriber, stream) in already_subscribed:
        result["already_subscribed"][subscriber.email].append(stream.name)

    private_streams = dict((stream.name, stream.invite_only) for stream in streams)
    bots = dict((subscriber.email, subscriber.is_bot) for subscriber in subscribers)

    # Inform the user if someone else subscribed them to stuff,
    # or if a new stream was created with the "announce" option.
    notifications = []
    if principals and result["subscribed"]:
        for email, subscriptions in result["subscribed"].iteritems():
            if email == user_profile.email:
                # Don't send a Zulip if you invited yourself.
                continue
            if bots[email]:
                # Don't send invitation Zulips to bots
                continue

            if len(subscriptions) == 1:
                msg = ("Hi there!  We thought you'd like to know that %s just "
                       "subscribed you to the%s stream [%s](%s)."
                       % (user_profile.full_name,
                          " **invite-only**" if private_streams[subscriptions[0]] else "",
                          subscriptions[0],
                          stream_link(subscriptions[0]),
                        ))
            else:
                msg = ("Hi there!  We thought you'd like to know that %s just "
                       "subscribed you to the following streams: \n\n"
                       % (user_profile.full_name,))
                for stream in subscriptions:
                    msg += "* [%s](%s)%s\n" % (
                        stream,
                        stream_link(stream),
                        " (**invite-only**)" if private_streams[stream] else "")

            if len([s for s in subscriptions if not private_streams[s]]) > 0:
                msg += "\nYou can see historical content on a non-invite-only stream by narrowing to it."
            notifications.append(internal_prep_message(settings.NOTIFICATION_BOT,
                                                       "private", email, "", msg))

    if announce and len(created_streams) > 0:
        notifications_stream = user_profile.realm.notifications_stream
        if notifications_stream is not None:
            if len(created_streams) > 1:
                stream_msg = "the following streams: %s" % \
                              (", ".join('`%s`' % (s.name,) for s in created_streams),)
            else:
                stream_msg = "a new stream `%s`" % (created_streams[0].name)

            stream_buttons = ' '.join(stream_button(s.name) for s in created_streams)
            msg = ("%s just created %s. %s" % (user_profile.full_name,
                                                stream_msg, stream_buttons))
            notifications.append(internal_prep_message(settings.NOTIFICATION_BOT,
                                   "stream",
                                   notifications_stream.name, "Streams", msg,
                                   realm=notifications_stream.realm))
        else:
            msg = ("Hi there!  %s just created a new stream '%s'. %s"
                       % (user_profile.full_name, created_streams[0].name, stream_button(created_streams[0].name)))
            for realm_user_dict in get_active_user_dicts_in_realm(user_profile.realm):
                # Don't announce to yourself or to people you explicitly added
                # (who will get the notification above instead).
                if realm_user_dict['email'] in principals or realm_user_dict['email'] == user_profile.email:
                    continue
                notifications.append(internal_prep_message(settings.NOTIFICATION_BOT,
                                                           "private",
                                                           realm_user_dict['email'], "", msg))

    if len(notifications) > 0:
        do_send_messages(notifications)

    result["subscribed"] = dict(result["subscribed"])
    result["already_subscribed"] = dict(result["already_subscribed"])
    if not authorization_errors_fatal:
        result["unauthorized"] = [stream.name for stream in unauthorized_streams]
    return json_success(result)

def get_members_backend(request, user_profile):
    realm = user_profile.realm
    admins = set(user_profile.realm.get_admin_users())
    members = []
    for profile in UserProfile.objects.select_related().filter(realm=realm):
        avatar_url = get_avatar_url(
            profile.avatar_source,
            profile.email
        )
        member = {"full_name": profile.full_name,
                  "is_bot": profile.is_bot,
                  "is_active": profile.is_active,
                  "is_admin": (profile in admins),
                  "email": profile.email,
                  "avatar_url": avatar_url,}
        if profile.is_bot and profile.bot_owner is not None:
            member["bot_owner"] = profile.bot_owner.email
        members.append(member)
    return json_success({'members': members})

@authenticated_json_post_view
def json_get_subscribers(request, user_profile):
    return get_subscribers_backend(request, user_profile)

@authenticated_json_post_view
@has_request_variables
def json_upload_file(request, user_profile):
    if len(request.FILES) == 0:
        return json_error("You must specify a file to upload")
    if len(request.FILES) != 1:
        return json_error("You may only upload one file at a time")

    user_file = request.FILES.values()[0]
    uri = upload_message_image_through_web_client(request, user_file, user_profile)
    return json_success({'uri': uri})

@login_required(login_url = settings.HOME_NOT_LOGGED_IN)
@has_request_variables
def get_uploaded_file(request, realm_id, filename,
                      redir=REQ(validator=check_bool, default=True)):
    if settings.LOCAL_UPLOADS_DIR is not None:
        return HttpResponseForbidden() # Should have been served by nginx

    user_profile = request.user
    url_path = "%s/%s" % (realm_id, filename)

    if realm_id == "unk":
        realm_id = get_realm_for_filename(url_path)
        if realm_id is None:
            # File does not exist
            return json_error("That file does not exist.", status=404)

    # Internal users can access all uploads so we can receive attachments in cross-realm messages
    if user_profile.realm.id == int(realm_id) or user_profile.realm.domain == 'zulip.com':
        uri = get_signed_upload_url(url_path)
        if redir:
            return redirect(uri)
        else:
            return json_success({'uri': uri})
    else:
        return HttpResponseForbidden()

@has_request_variables
def get_subscribers_backend(request, user_profile, stream_name=REQ('stream')):
    stream = get_stream(stream_name, user_profile.realm)
    if stream is None:
        raise JsonableError("Stream does not exist: %s" % (stream_name,))

    subscribers = get_subscriber_emails(stream, user_profile)

    return json_success({'subscribers': subscribers})

@authenticated_json_post_view
@has_request_variables
def json_change_settings(request, user_profile,
                         full_name=REQ,
                         old_password=REQ(default=""),
                         new_password=REQ(default=""),
                         confirm_password=REQ(default="")):
    if new_password != "" or confirm_password != "":
        if new_password != confirm_password:
            return json_error("New password must match confirmation password!")
        if not authenticate(username=user_profile.email, password=old_password):
            return json_error("Wrong password!")
        do_change_password(user_profile, new_password)

    result = {}
    if user_profile.full_name != full_name and full_name.strip() != "":
        if name_changes_disabled(user_profile.realm):
            # Failingly silently is fine -- they can't do it through the UI, so
            # they'd have to be trying to break the rules.
            pass
        else:
            new_full_name = full_name.strip()
            if len(new_full_name) > UserProfile.MAX_NAME_LENGTH:
                return json_error("Name too long!")
            do_change_full_name(user_profile, new_full_name)
            result['full_name'] = new_full_name

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_time_setting(request, user_profile, twenty_four_hour_time=REQ(validator=check_bool, default=None)):
    result = {}
    if twenty_four_hour_time is not None and \
        user_profile.twenty_four_hour_time != twenty_four_hour_time:
        do_change_twenty_four_hour_time(user_profile, twenty_four_hour_time)

    result['twenty_four_hour_time'] = twenty_four_hour_time

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_left_side_userlist(request, user_profile, left_side_userlist=REQ(validator=check_bool, default=None)):
    result = {}
    if left_side_userlist is not None and \
        user_profile.left_side_userlist != left_side_userlist:
        do_change_left_side_userlist(user_profile, left_side_userlist)

    result['left_side_userlist'] = left_side_userlist

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_change_notify_settings(request, user_profile,
                                enable_stream_desktop_notifications=REQ(validator=check_bool,
                                                                        default=None),
                                enable_stream_sounds=REQ(validator=check_bool,
                                                         default=None),
                                enable_desktop_notifications=REQ(validator=check_bool,
                                                                 default=None),
                                enable_sounds=REQ(validator=check_bool,
                                                  default=None),
                                enable_offline_email_notifications=REQ(validator=check_bool,
                                                                       default=None),
                                enable_offline_push_notifications=REQ(validator=check_bool,
                                                                      default=None),
                                enable_digest_emails=REQ(validator=check_bool,
                                                         default=None)):

    result = {}

    # Stream notification settings.

    if enable_stream_desktop_notifications is not None and \
            user_profile.enable_stream_desktop_notifications != enable_stream_desktop_notifications:
        do_change_enable_stream_desktop_notifications(
            user_profile, enable_stream_desktop_notifications)
        result['enable_stream_desktop_notifications'] = enable_stream_desktop_notifications

    if enable_stream_sounds is not None and \
            user_profile.enable_stream_sounds != enable_stream_sounds:
        do_change_enable_stream_sounds(user_profile, enable_stream_sounds)
        result['enable_stream_sounds'] = enable_stream_sounds

    # PM and @-mention settings.

    if enable_desktop_notifications is not None and \
            user_profile.enable_desktop_notifications != enable_desktop_notifications:
        do_change_enable_desktop_notifications(user_profile, enable_desktop_notifications)
        result['enable_desktop_notifications'] = enable_desktop_notifications

    if enable_sounds is not None and \
            user_profile.enable_sounds != enable_sounds:
        do_change_enable_sounds(user_profile, enable_sounds)
        result['enable_sounds'] = enable_sounds

    if enable_offline_email_notifications is not None and \
            user_profile.enable_offline_email_notifications != enable_offline_email_notifications:
        do_change_enable_offline_email_notifications(user_profile, enable_offline_email_notifications)
        result['enable_offline_email_notifications'] = enable_offline_email_notifications

    if enable_offline_push_notifications is not None and \
            user_profile.enable_offline_push_notifications != enable_offline_push_notifications:
        do_change_enable_offline_push_notifications(user_profile, enable_offline_push_notifications)
        result['enable_offline_push_notifications'] = enable_offline_push_notifications

    if enable_digest_emails is not None and \
            user_profile.enable_digest_emails != enable_digest_emails:
        do_change_enable_digest_emails(user_profile, enable_digest_emails)
        result['enable_digest_emails'] = enable_digest_emails

    return json_success(result)

@require_realm_admin
@has_request_variables
def create_user_backend(request, user_profile, email=REQ, password=REQ,
                        full_name=REQ, short_name=REQ):
    form = CreateUserForm({'full_name': full_name, 'email': email})
    if not form.is_valid():
        return json_error('Bad name or username')

    # Check that the new user's email address belongs to the admin's realm
    realm = user_profile.realm
    domain = resolve_email_to_domain(email)
    if realm.domain != domain:
        return json_error("Email '%s' does not belong to domain '%s'" % (email, realm.domain))

    try:
        get_user_profile_by_email(email)
        return json_error("Email '%s' already in use" % (email,))
    except UserProfile.DoesNotExist:
        pass

    do_create_user(email, password, realm, full_name, short_name)
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_change_ui_settings(request, user_profile,
                            autoscroll_forever=REQ(validator=check_bool,
                                                   default=None),
                            default_desktop_notifications=REQ(validator=check_bool,
                                                              default=None)):

    result = {}

    if autoscroll_forever is not None and \
            user_profile.autoscroll_forever != autoscroll_forever:
        do_change_autoscroll_forever(user_profile, autoscroll_forever)
        result['autoscroll_forever'] = autoscroll_forever

    if default_desktop_notifications is not None and \
            user_profile.default_desktop_notifications != default_desktop_notifications:
        do_change_default_desktop_notifications(user_profile, default_desktop_notifications)
        result['default_desktop_notifications'] = default_desktop_notifications

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_stream_exists(request, user_profile, stream=REQ,
                       autosubscribe=REQ(default=False)):
    return stream_exists_backend(request, user_profile, stream, autosubscribe)

def stream_exists_backend(request, user_profile, stream_name, autosubscribe):
    if not valid_stream_name(stream_name):
        return json_error("Invalid characters in stream name")
    stream = get_stream(stream_name, user_profile.realm)
    result = {"exists": bool(stream)}
    if stream is not None:
        recipient = get_recipient(Recipient.STREAM, stream.id)
        if autosubscribe:
            bulk_add_subscriptions([stream], [user_profile])
        result["subscribed"] = Subscription.objects.filter(user_profile=user_profile,
                                                           recipient=recipient,
                                                           active=True).exists()
        return json_success(result) # results are ignored for HEAD requests
    return json_response(data=result, status=404)

def get_subscription_or_die(stream_name, user_profile):
    stream = get_stream(stream_name, user_profile.realm)
    if not stream:
        raise JsonableError("Invalid stream %s" % (stream.name,))
    recipient = get_recipient(Recipient.STREAM, stream.id)
    subscription = Subscription.objects.filter(user_profile=user_profile,
                                               recipient=recipient, active=True)

    if not subscription.exists():
        raise JsonableError("Not subscribed to stream %s" % (stream_name,))

    return subscription

@authenticated_json_view
@has_request_variables
def json_subscription_property(request, user_profile, subscription_data=REQ(
        validator=check_list(
            check_dict([["stream", check_string],
                        ["property", check_string],
                        ["value", check_variable_type(
                            [check_string, check_bool])]])))):
    """
    This is the entry point to changing subscription properties. This
    is a bulk endpoint: requestors always provide a subscription_data
    list containing dictionaries for each stream of interest.

    Requests are of the form:

    [{"stream": "devel", "property": "in_home_view", "value": False},
     {"stream": "devel", "property": "color", "value": "#c2c2c2"}]
    """
    if request.method != "POST":
        return json_error("Invalid verb")

    property_converters = {"color": check_string, "in_home_view": check_bool,
                           "desktop_notifications": check_bool,
                           "audible_notifications": check_bool}
    response_data = []

    for change in subscription_data:
        stream_name = change["stream"]
        property = change["property"]
        value = change["value"]

        if property not in property_converters:
            return json_error("Unknown subscription property: %s" % (property,))

        sub = get_subscription_or_die(stream_name, user_profile)[0]

        property_conversion = property_converters[property](property, value)
        if property_conversion:
            return json_error(property_conversion)

        do_change_subscription_property(user_profile, sub, stream_name,
                                        property, value)

        response_data.append({'stream': stream_name,
                              'property': property,
                              'value': value})

    return json_success({"subscription_data": response_data})

@csrf_exempt
@require_post
@has_request_variables
def api_fetch_api_key(request, username=REQ, password=REQ):
    return_data = {}
    if username == "google-oauth2-token":
        user_profile = authenticate(google_oauth2_token=password, return_data=return_data)
    else:
        user_profile = authenticate(username=username, password=password)
    if user_profile is None:
        if return_data.get("valid_attestation") == True:
            # We can leak that the user is unregistered iff they present a valid authentication string for the user.
            return json_error("This user is not registered; do so from a browser.", data={"reason": "unregistered"}, status=403)
        return json_error("Your username or password is incorrect.", data={"reason": "incorrect_creds"}, status=403)
    if not user_profile.is_active:
        return json_error("Your account has been disabled.", data={"reason": "disabled"}, status=403)
    return json_success({"api_key": user_profile.api_key, "email": user_profile.email})

@authenticated_json_post_view
@has_request_variables
def json_fetch_api_key(request, user_profile, password=REQ(default='')):
    if password_auth_enabled(user_profile.realm) and not user_profile.check_password(password):
        return json_error("Your username or password is incorrect.")
    return json_success({"api_key": user_profile.api_key})

@csrf_exempt
def api_fetch_google_client_id(request):
    if not settings.GOOGLE_CLIENT_ID:
        return json_error("GOOGLE_CLIENT_ID is not configured", status=400)
    return json_success({"google_client_id": settings.GOOGLE_CLIENT_ID})

def get_status_list(requesting_user_profile):
    return {'presences': get_status_dict(requesting_user_profile),
            'server_timestamp': time.time()}

@has_request_variables
def update_active_status_backend(request, user_profile, status=REQ,
                                 new_user_input=REQ(validator=check_bool, default=False)):
    status_val = UserPresence.status_from_string(status)
    if status_val is None:
        raise JsonableError("Invalid presence status: %s" % (status,))
    else:
        update_user_presence(user_profile, request.client, now(), status_val,
                             new_user_input)

    ret = get_status_list(user_profile)
    if user_profile.realm.domain == "mit.edu":
        try:
            activity = UserActivity.objects.get(user_profile = user_profile,
                                                query="get_events_backend",
                                                client__name="zephyr_mirror")

            ret['zephyr_mirror_active'] = \
                (activity.last_visit.replace(tzinfo=None) >
                 datetime.datetime.utcnow() - datetime.timedelta(minutes=5))
        except UserActivity.DoesNotExist:
            ret['zephyr_mirror_active'] = False

    return json_success(ret)

@authenticated_json_post_view
def json_update_active_status(request, user_profile):
    return update_active_status_backend(request, user_profile)

@authenticated_json_post_view
def json_get_active_statuses(request, user_profile):
    return json_success(get_status_list(user_profile))

# Read the source map information for decoding JavaScript backtraces
js_source_map = None
if not (settings.DEBUG or settings.TEST_SUITE):
    js_source_map = SourceMap(os.path.join(
        settings.DEPLOY_ROOT, 'prod-static/source-map'))

@authenticated_json_post_view
@has_request_variables
def json_report_send_time(request, user_profile,
                          time=REQ(converter=to_non_negative_int),
                          received=REQ(converter=to_non_negative_int, default="(unknown)"),
                          displayed=REQ(converter=to_non_negative_int, default="(unknown)"),
                          locally_echoed=REQ(validator=check_bool, default=False),
                          rendered_content_disparity=REQ(validator=check_bool, default=False)):
    request._log_data["extra"] = "[%sms/%sms/%sms/echo:%s/diff:%s]" \
        % (time, received, displayed, locally_echoed, rendered_content_disparity)
    statsd.timing("endtoend.send_time.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), time)
    if received != "(unknown)":
        statsd.timing("endtoend.receive_time.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), received)
    if displayed != "(unknown)":
        statsd.timing("endtoend.displayed_time.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), displayed)
    if locally_echoed:
        statsd.incr('locally_echoed')
    if rendered_content_disparity:
        statsd.incr('render_disparity')
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_report_narrow_time(request, user_profile,
                            initial_core=REQ(converter=to_non_negative_int),
                            initial_free=REQ(converter=to_non_negative_int),
                            network=REQ(converter=to_non_negative_int)):
    request._log_data["extra"] = "[%sms/%sms/%sms]" % (initial_core, initial_free, network)
    statsd.timing("narrow.initial_core.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), initial_core)
    statsd.timing("narrow.initial_free.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), initial_free)
    statsd.timing("narrow.network.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), network)
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_report_unnarrow_time(request, user_profile,
                            initial_core=REQ(converter=to_non_negative_int),
                            initial_free=REQ(converter=to_non_negative_int)):
    request._log_data["extra"] = "[%sms/%sms]" % (initial_core, initial_free)
    statsd.timing("unnarrow.initial_core.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), initial_core)
    statsd.timing("unnarrow.initial_free.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), initial_free)
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_report_error(request, user_profile, message=REQ, stacktrace=REQ,
                      ui_message=REQ(validator=check_bool), user_agent=REQ,
                      href=REQ, log=REQ,
                      more_info=REQ(validator=check_dict([]), default=None)):

    if not settings.ERROR_REPORTING:
        return json_success()

    if js_source_map:
        stacktrace = js_source_map.annotate_stacktrace(stacktrace)

    try:
        version = subprocess.check_output(["git", "log", "HEAD^..HEAD", "--oneline"])
    except Exception:
        version = None

    queue_json_publish('error_reports', dict(
        type = "browser",
        report = dict(
            user_email = user_profile.email,
            user_full_name = user_profile.full_name,
            user_visible = ui_message,
            server_path = settings.DEPLOY_ROOT,
            version = version,
            user_agent = user_agent,
            href = href,
            message = message,
            stacktrace = stacktrace,
            log = log,
            more_info = more_info,
        )
    ), lambda x: None)

    return json_success()

@authenticated_json_post_view
def json_events_register(request, user_profile):
    return events_register_backend(request, user_profile)

# Does not need to be authenticated because it's called from rest_dispatch
@has_request_variables
def api_events_register(request, user_profile,
                        apply_markdown=REQ(default=False, validator=check_bool),
                        all_public_streams=REQ(default=None, validator=check_bool)):
    return events_register_backend(request, user_profile,
                                   apply_markdown=apply_markdown,
                                   all_public_streams=all_public_streams)

def _default_all_public_streams(user_profile, all_public_streams):
    if all_public_streams is not None:
        return all_public_streams
    else:
        return user_profile.default_all_public_streams

def _default_narrow(user_profile, narrow):
    default_stream = user_profile.default_events_register_stream
    if not narrow and user_profile.default_events_register_stream is not None:
        narrow = [('stream', default_stream.name)]
    return narrow

@has_request_variables
def events_register_backend(request, user_profile, apply_markdown=True,
                            all_public_streams=None,
                            event_types=REQ(validator=check_list(check_string), default=None),
                            narrow=REQ(validator=check_list(check_list(check_string, length=2)), default=[]),
                            queue_lifespan_secs=REQ(converter=int, default=0)):

    all_public_streams = _default_all_public_streams(user_profile, all_public_streams)
    narrow = _default_narrow(user_profile, narrow)

    ret = do_events_register(user_profile, request.client, apply_markdown,
                             event_types, queue_lifespan_secs, all_public_streams,
                             narrow=narrow)
    return json_success(ret)


def deactivate_user_backend(request, user_profile, email):
    try:
        target = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        return json_error('No such user')
    if target.is_bot:
        return json_error('No such user')
    return _deactivate_user_profile_backend(request, user_profile, target)

def deactivate_bot_backend(request, user_profile, email):
    try:
        target = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        return json_error('No such bot')
    if not target.is_bot:
        return json_error('No such bot')
    return _deactivate_user_profile_backend(request, user_profile, target)

def _deactivate_user_profile_backend(request, user_profile, target):
    if not user_profile.can_admin_user(target):
        return json_error('Insufficient permission')

    do_deactivate_user(target)
    return json_success({})

def reactivate_user_backend(request, user_profile, email):
    try:
        target = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        return json_error('No such user')

    if not user_profile.can_admin_user(target):
        return json_error('Insufficient permission')

    do_reactivate_user(target)
    return json_success({})

@has_request_variables
def update_user_backend(request, user_profile, email,
                        is_admin=REQ(default=None, validator=check_bool)):
    try:
        target = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        return json_error('No such user')

    if not user_profile.can_admin_user(target):
        return json_error('Insufficient permission')

    if is_admin is not None:
        do_change_is_admin(target, is_admin)
    return json_success({})

@require_realm_admin
def deactivate_stream_backend(request, user_profile, stream_name):
    target = get_stream(stream_name, user_profile.realm)
    if not target:
        return json_error('No such stream name')

    if target.invite_only and not subscribed_to_stream(user_profile, target):
        return json_error('Cannot administer invite-only streams this way')

    do_deactivate_stream(target)
    return json_success({})

def avatar(request, email):
    try:
        user_profile = get_user_profile_by_email(email)
        avatar_source = user_profile.avatar_source
    except UserProfile.DoesNotExist:
        avatar_source = 'G'
    url = get_avatar_url(avatar_source, email)
    if '?' in url:
        sep = '&'
    else:
        sep = '?'
    url += sep + request.META['QUERY_STRING']
    return redirect(url)

def get_stream_name(stream):
    if stream:
        name = stream.name
    else :
        name = None
    return name

def stream_or_none(stream_name, realm):
    if stream_name == '':
        return None
    else:
        stream = get_stream(stream_name, realm)
        if not stream:
            raise JsonableError('No such stream \'%s\'' %  (stream_name, ))
        return stream

@has_request_variables
def patch_bot_backend(request, user_profile, email,
                      full_name=REQ(default=None),
                      default_sending_stream=REQ(default=None),
                      default_events_register_stream=REQ(default=None),
                      default_all_public_streams=REQ(default=None, validator=check_bool)):
    try:
        bot = get_user_profile_by_email(email)
    except:
        return json_error('No such user')

    if not user_profile.can_admin_user(bot):
        return json_error('Insufficient permission')

    if full_name is not None:
        do_change_full_name(bot, full_name)
    if default_sending_stream is not None:
        stream = stream_or_none(default_sending_stream, bot.realm)
        do_change_default_sending_stream(bot, stream)
    if default_events_register_stream is not None:
        stream = stream_or_none(default_events_register_stream, bot.realm)
        do_change_default_events_register_stream(bot, stream)
    if default_all_public_streams is not None:
        do_change_default_all_public_streams(bot, default_all_public_streams)

    if len(request.FILES) == 0:
        pass
    elif len(request.FILES) == 1:
        user_file = request.FILES.values()[0]
        upload_avatar_image(user_file, user_profile, bot.email)
        avatar_source = UserProfile.AVATAR_FROM_USER
        do_change_avatar_source(bot, avatar_source)
    else:
        return json_error("You may only upload one file at a time")

    json_result = dict(
        full_name=bot.full_name,
        avatar_url=avatar_url(bot),
        default_sending_stream=get_stream_name(bot.default_sending_stream),
        default_events_register_stream=get_stream_name(bot.default_events_register_stream),
        default_all_public_streams=bot.default_all_public_streams,
    )
    return json_success(json_result)

@authenticated_json_post_view
def json_set_avatar(request, user_profile):
    if len(request.FILES) != 1:
        return json_error("You must upload exactly one avatar.")

    user_file = request.FILES.values()[0]
    upload_avatar_image(user_file, user_profile, user_profile.email)
    do_change_avatar_source(user_profile, UserProfile.AVATAR_FROM_USER)
    user_avatar_url = avatar_url(user_profile)

    json_result = dict(
        avatar_url = user_avatar_url
    )
    return json_success(json_result)

@has_request_variables
def regenerate_api_key(request, user_profile):
    do_regenerate_api_key(user_profile)
    json_result = dict(
        api_key = user_profile.api_key
    )
    return json_success(json_result)

@has_request_variables
def regenerate_bot_api_key(request, user_profile, email):
    try:
        bot = get_user_profile_by_email(email)
    except:
        return json_error('No such user')

    if not user_profile.can_admin_user(bot):
        return json_error('Insufficient permission')

    do_regenerate_api_key(bot)
    json_result = dict(
        api_key = bot.api_key
    )
    return json_success(json_result)

@has_request_variables
def add_bot_backend(request, user_profile, full_name=REQ, short_name=REQ,
                    default_sending_stream=REQ(default=None),
                    default_events_register_stream=REQ(default=None),
                    default_all_public_streams=REQ(validator=check_bool, default=None)):
    short_name += "-bot"
    email = short_name + "@" + user_profile.realm.domain
    form = CreateUserForm({'full_name': full_name, 'email': email})
    if not form.is_valid():
        # We validate client-side as well
        return json_error('Bad name or username')

    try:
        get_user_profile_by_email(email)
        return json_error("Username already in use")
    except UserProfile.DoesNotExist:
        pass

    if len(request.FILES) == 0:
        avatar_source = UserProfile.AVATAR_FROM_GRAVATAR
    elif len(request.FILES) != 1:
        return json_error("You may only upload one file at a time")
    else:
        user_file = request.FILES.values()[0]
        upload_avatar_image(user_file, user_profile, email)
        avatar_source = UserProfile.AVATAR_FROM_USER

    if default_sending_stream is not None:
        default_sending_stream = stream_or_none(default_sending_stream, user_profile.realm)
    if default_sending_stream and not default_sending_stream.is_public() and not \
        subscribed_to_stream(user_profile, default_sending_stream):
        return json_error('Insufficient permission')

    if default_events_register_stream is not None:
        default_events_register_stream = stream_or_none(default_events_register_stream,
                                                         user_profile.realm)
    if default_events_register_stream and not default_events_register_stream.is_public() and not \
        subscribed_to_stream(user_profile, default_events_register_stream):
        return json_error('Insufficient permission')


    bot_profile = do_create_user(email=email, password='',
                                 realm=user_profile.realm, full_name=full_name,
                                 short_name=short_name, active=True, bot=True,
                                 bot_owner=user_profile,
                                 avatar_source=avatar_source,
                                 default_sending_stream=default_sending_stream,
                                 default_events_register_stream=default_events_register_stream,
                                 default_all_public_streams=default_all_public_streams)
    json_result = dict(
            api_key=bot_profile.api_key,
            avatar_url=avatar_url(bot_profile),
            default_sending_stream=get_stream_name(bot_profile.default_sending_stream),
            default_events_register_stream=get_stream_name(bot_profile.default_events_register_stream),
            default_all_public_streams=bot_profile.default_all_public_streams,
    )
    return json_success(json_result)

def get_bots_backend(request, user_profile):
    bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True,
                                              bot_owner=user_profile)
    bot_profiles = bot_profiles.select_related('default_sending_stream', 'default_events_register_stream')
    bot_profiles = bot_profiles.order_by('date_joined')

    def bot_info(bot_profile):
        default_sending_stream = get_stream_name(bot_profile.default_sending_stream)
        default_events_register_stream = get_stream_name(bot_profile.default_events_register_stream)

        return dict(
            username=bot_profile.email,
            full_name=bot_profile.full_name,
            api_key=bot_profile.api_key,
            avatar_url=avatar_url(bot_profile),
            default_sending_stream=default_sending_stream,
            default_events_register_stream=default_events_register_stream,
            default_all_public_streams=bot_profile.default_all_public_streams,
        )

    return json_success({'bots': list(map(bot_info, bot_profiles))})

@authenticated_json_post_view
@has_request_variables
def json_refer_friend(request, user_profile, email=REQ):
    if not email:
        return json_error("No email address specified")
    if user_profile.invites_granted - user_profile.invites_used <= 0:
        return json_error("Insufficient invites")

    do_refer_friend(user_profile, email);

    return json_success()

def list_alert_words(request, user_profile):
    return json_success({'alert_words': user_alert_words(user_profile)})

@authenticated_json_post_view
@has_request_variables
def json_set_alert_words(request, user_profile,
                         alert_words=REQ(validator=check_list(check_string), default=[])):
    do_set_alert_words(user_profile, alert_words)
    return json_success()

@has_request_variables
def set_alert_words(request, user_profile,
                    alert_words=REQ(validator=check_list(check_string), default=[])):
    do_set_alert_words(user_profile, alert_words)
    return json_success()

@has_request_variables
def add_alert_words(request, user_profile,
                    alert_words=REQ(validator=check_list(check_string), default=[])):
    do_add_alert_words(user_profile, alert_words)
    return json_success()

@has_request_variables
def remove_alert_words(request, user_profile,
                       alert_words=REQ(validator=check_list(check_string), default=[])):
    do_remove_alert_words(user_profile, alert_words)
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_set_muted_topics(request, user_profile,
                         muted_topics=REQ(validator=check_list(check_list(check_string, length=2)), default=[])):
    do_set_muted_topics(user_profile, muted_topics)
    return json_success()

def add_push_device_token(request, user_profile, token, kind, ios_app_id=None):
    if token == '' or len(token) > 4096:
        return json_error('Empty or invalid length token')

    # If another user was previously logged in on the same device and didn't
    # properly log out, the token will still be registered to the wrong account
    PushDeviceToken.objects.filter(token=token).delete()

    # Overwrite with the latest value
    token, created = PushDeviceToken.objects.get_or_create(user=user_profile,
                                                           token=token,
                                                           kind=kind,
                                                           ios_app_id=ios_app_id)
    if not created:
        token.last_updated = now()
        token.save(update_fields=['last_updated'])

    return json_success()

@has_request_variables
def add_apns_device_token(request, user_profile, token=REQ, appid=REQ(default=settings.ZULIP_IOS_APP_ID)):
    return add_push_device_token(request, user_profile, token, PushDeviceToken.APNS, ios_app_id=appid)

@has_request_variables
def add_android_reg_id(request, user_profile, token=REQ):
    return add_push_device_token(request, user_profile, token, PushDeviceToken.GCM)

def remove_push_device_token(request, user_profile, token, kind):
    if token == '' or len(token) > 4096:
        return json_error('Empty or invalid length token')

    try:
        token = PushDeviceToken.objects.get(token=token, kind=kind)
        token.delete()
    except PushDeviceToken.DoesNotExist:
        return json_error("Token does not exist")

    return json_success()

@has_request_variables
def remove_apns_device_token(request, user_profile, token=REQ):
    return remove_push_device_token(request, user_profile, token, PushDeviceToken.APNS)

@has_request_variables
def remove_android_reg_id(request, user_profile, token=REQ):
    return remove_push_device_token(request, user_profile, token, PushDeviceToken.GCM)


def generate_204(request):
    return HttpResponse(content=None, status=204)

def process_unsubscribe(token, type, unsubscribe_function):
    try:
        confirmation = Confirmation.objects.get(confirmation_key=token)
    except Confirmation.DoesNotExist:
        return render_to_response('zerver/unsubscribe_link_error.html')

    user_profile = confirmation.content_object
    unsubscribe_function(user_profile)
    return render_to_response('zerver/unsubscribe_success.html',
                              {"subscription_type": type,
                               "external_host": settings.EXTERNAL_HOST})

# Email unsubscribe functions. All have the function signature
# processor(user_profile).

def do_missedmessage_unsubscribe(user_profile):
    do_change_enable_offline_email_notifications(user_profile, False)

def do_welcome_unsubscribe(user_profile):
    clear_followup_emails_queue(user_profile.email)

def do_digest_unsubscribe(user_profile):
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
    if type in email_unsubscribers:
        display_name, unsubscribe_function = email_unsubscribers[type]
        return process_unsubscribe(token, display_name, unsubscribe_function)

    return render_to_response('zerver/unsubscribe_link_error.html', {},
                              context_instance=RequestContext(request))
