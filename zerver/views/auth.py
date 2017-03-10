from __future__ import absolute_import

from django.conf import settings
from django.contrib.auth import authenticate, login, get_backends
from django.contrib.auth.views import login as django_login_page, \
    logout_then_login as django_logout_then_login
from django.core.urlresolvers import reverse
from zerver.decorator import authenticated_json_post_view, require_post
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, \
    HttpResponseNotFound
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext as _
from django.core import signing
from six.moves import urllib
from typing import Any, Dict, List, Optional, Tuple, Text

from confirmation.models import Confirmation
from zerver.forms import HomepageForm, OurAuthenticationForm, \
    WRONG_SUBDOMAIN_ERROR

from zerver.lib.request import REQ, has_request_variables, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.utils import get_subdomain, is_subdomain_root_or_alias
from zerver.models import PreregistrationUser, UserProfile, remote_user_to_email, Realm
from zerver.views.registration import create_preregistration_user, get_realm_from_request, \
    redirect_and_log_into_subdomain
from zproject.backends import password_auth_enabled, dev_auth_enabled, google_auth_enabled
from zproject.jinja2 import render_to_response
from version import ZULIP_VERSION

import hashlib
import hmac
import jwt
import logging
import requests
import time
import ujson

def maybe_send_to_registration(request, email, full_name=''):
    # type: (HttpRequest, Text, Text) -> HttpResponse
    form = HomepageForm({'email': email}, realm=get_realm_from_request(request))
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

def redirect_to_subdomain_login_url():
    # type: () -> HttpResponseRedirect
    login_url = reverse('django.contrib.auth.views.login')
    redirect_url = login_url + '?subdomain=1'
    return HttpResponseRedirect(redirect_url)

def login_or_register_remote_user(request, remote_username, user_profile, full_name='',
                                  invalid_subdomain=False):
    # type: (HttpRequest, Text, UserProfile, Text, Optional[bool]) -> HttpResponse
    if invalid_subdomain:
        # Show login page with an error message
        return redirect_to_subdomain_login_url()

    elif user_profile is None or user_profile.is_mirror_dummy:
        # Since execution has reached here, the client specified a remote user
        # but no associated user account exists. Send them over to the
        # PreregistrationUser flow.
        return maybe_send_to_registration(request, remote_user_to_email(remote_username), full_name)
    else:
        login(request, user_profile)
        if settings.REALMS_HAVE_SUBDOMAINS and user_profile.realm.subdomain is not None:
            return HttpResponseRedirect(user_profile.realm.uri)
        return HttpResponseRedirect("%s%s" % (settings.EXTERNAL_URI_SCHEME,
                                              request.get_host()))

def remote_user_sso(request):
    # type: (HttpRequest) -> HttpResponse
    try:
        remote_user = request.META["REMOTE_USER"]
    except KeyError:
        raise JsonableError(_("No REMOTE_USER set."))

    user_profile = authenticate(remote_user=remote_user, realm_subdomain=get_subdomain(request))
    return login_or_register_remote_user(request, remote_user, user_profile)

@csrf_exempt
def remote_user_jwt(request):
    # type: (HttpRequest) -> HttpResponse
    subdomain = get_subdomain(request)
    try:
        auth_key = settings.JWT_AUTH_KEYS[subdomain]
    except KeyError:
        raise JsonableError(_("Auth key for this subdomain not found."))

    try:
        json_web_token = request.POST["json_web_token"]
        options = {'verify_signature': True}
        payload = jwt.decode(json_web_token, auth_key, options=options)
    except KeyError:
        raise JsonableError(_("No JSON web token passed in request"))
    except jwt.InvalidTokenError:
        raise JsonableError(_("Bad JSON web token"))

    remote_user = payload.get("user", None)
    if remote_user is None:
        raise JsonableError(_("No user specified in JSON web token claims"))
    realm = payload.get('realm', None)
    if realm is None:
        raise JsonableError(_("No realm specified in JSON web token claims"))

    email = "%s@%s" % (remote_user, realm)

    try:
        # We do all the authentication we need here (otherwise we'd have to
        # duplicate work), but we need to call authenticate with some backend so
        # that the request.backend attribute gets set.
        return_data = {} # type: Dict[str, bool]
        user_profile = authenticate(username=email,
                                    realm_subdomain=subdomain,
                                    return_data=return_data,
                                    use_dummy_backend=True)
        if return_data.get('invalid_subdomain'):
            logging.warning("User attempted to JWT login to wrong subdomain %s: %s" % (subdomain, email,))
            raise JsonableError(_("Wrong subdomain"))
    except UserProfile.DoesNotExist:
        user_profile = None

    return login_or_register_remote_user(request, email, user_profile, remote_user)

def google_oauth2_csrf(request, value):
    # type: (HttpRequest, str) -> HttpResponse
    # In Django 1.10, get_token returns a salted token which changes
    # everytime get_token is called.
    try:
        from django.middleware.csrf import _unsalt_cipher_token
        token = _unsalt_cipher_token(get_token(request))
    except ImportError:
        token = get_token(request)

    return hmac.new(token.encode('utf-8'), value.encode("utf-8"), hashlib.sha256).hexdigest()

def start_google_oauth2(request):
    # type: (HttpRequest) -> HttpResponse
    url = reverse('zerver.views.auth.send_oauth_request_to_google')
    return redirect_to_main_site(request, url)

def redirect_to_main_site(request, url):
    # type: (HttpRequest, Text) -> HttpResponse
    main_site_uri = ''.join((
        settings.EXTERNAL_URI_SCHEME,
        settings.EXTERNAL_HOST,
        url,
    ))
    params = {'subdomain': get_subdomain(request)}
    return redirect(main_site_uri + '?' + urllib.parse.urlencode(params))

def start_social_login(request, backend):
    # type: (HttpRequest, Text) -> HttpResponse
    backend_url = reverse('social:begin', args=[backend])
    return redirect_to_main_site(request, backend_url)

def send_oauth_request_to_google(request):
    # type: (HttpRequest) -> HttpResponse
    subdomain = request.GET.get('subdomain', '')
    if settings.REALMS_HAVE_SUBDOMAINS:
        if not subdomain or not Realm.objects.filter(string_id=subdomain).exists():
            return redirect_to_subdomain_login_url()

    google_uri = 'https://accounts.google.com/o/oauth2/auth?'
    cur_time = str(int(time.time()))
    csrf_state = '{}:{}:{}'.format(
        cur_time,
        google_oauth2_csrf(request, cur_time + subdomain),
        subdomain
    )

    prams = {
        'response_type': 'code',
        'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
        'redirect_uri': ''.join((
            settings.EXTERNAL_URI_SCHEME,
            settings.EXTERNAL_HOST,
            reverse('zerver.views.auth.finish_google_oauth2'),
        )),
        'scope': 'profile email',
        'state': csrf_state,
    }
    return redirect(google_uri + urllib.parse.urlencode(prams))

def finish_google_oauth2(request):
    # type: (HttpRequest) -> HttpResponse
    error = request.GET.get('error')
    if error == 'access_denied':
        return redirect('/')
    elif error is not None:
        logging.warning('Error from google oauth2 login: %s' % (request.GET.get("error"),))
        return HttpResponse(status=400)

    csrf_state = request.GET.get('state')
    if csrf_state is None or len(csrf_state.split(':')) != 3:
        logging.warning('Missing Google oauth2 CSRF state')
        return HttpResponse(status=400)

    value, hmac_value, subdomain = csrf_state.split(':')
    if hmac_value != google_oauth2_csrf(request, value + subdomain):
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
                settings.EXTERNAL_HOST,
                reverse('zerver.views.auth.finish_google_oauth2'),
            )),
            'grant_type': 'authorization_code',
        },
    )
    if resp.status_code == 400:
        logging.warning('User error converting Google oauth2 login to token: %s' % (resp.text,))
        return HttpResponse(status=400)
    elif resp.status_code != 200:
        logging.error('Could not convert google oauth2 code to access_token: %s' % (resp.text,))
        return HttpResponse(status=400)
    access_token = resp.json()['access_token']

    resp = requests.get(
        'https://www.googleapis.com/plus/v1/people/me',
        params={'access_token': access_token}
    )
    if resp.status_code == 400:
        logging.warning('Google login failed making info API call: %s' % (resp.text,))
        return HttpResponse(status=400)
    elif resp.status_code != 200:
        logging.error('Google login failed making API call: %s' % (resp.text,))
        return HttpResponse(status=400)
    body = resp.json()

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
        logging.error('Google oauth2 account email not found: %s' % (body,))
        return HttpResponse(status=400)

    email_address = email['value']
    if not subdomain:
        # When request was not initiated from subdomain.
        user_profile, return_data = authenticate_remote_user(request, email_address)
        invalid_subdomain = bool(return_data.get('invalid_subdomain'))
        return login_or_register_remote_user(request, email_address, user_profile,
                                             full_name, invalid_subdomain)

    try:
        realm = Realm.objects.get(string_id=subdomain)
    except Realm.DoesNotExist:
        return redirect_to_subdomain_login_url()

    return redirect_and_log_into_subdomain(realm, full_name, email_address)

def authenticate_remote_user(request, email_address):
    # type: (HttpRequest, str) -> Tuple[UserProfile, Dict[str, Any]]
    return_data = {} # type: Dict[str, bool]
    user_profile = authenticate(username=email_address,
                                realm_subdomain=get_subdomain(request),
                                use_dummy_backend=True,
                                return_data=return_data)
    return user_profile, return_data

def log_into_subdomain(request):
    # type: (HttpRequest) -> HttpResponse
    try:
        # Discard state if older than 15 seconds
        state = request.get_signed_cookie('subdomain.signature',
                                          salt='zerver.views.auth',
                                          max_age=15)
    except KeyError:
        logging.warning('Missing subdomain signature cookie.')
        return HttpResponse(status=400)
    except signing.BadSignature:
        logging.warning('Subdomain cookie has bad signature.')
        return HttpResponse(status=400)

    data = ujson.loads(state)
    if data['subdomain'] != get_subdomain(request):
        logging.warning('Login attemp on invalid subdomain')
        return HttpResponse(status=400)

    email_address = data['email']
    full_name = data['name']
    user_profile, return_data = authenticate_remote_user(request, email_address)
    invalid_subdomain = bool(return_data.get('invalid_subdomain'))
    return login_or_register_remote_user(request, email_address, user_profile,
                                         full_name, invalid_subdomain)

def get_dev_users(extra_users_count=10):
    # type: (int) -> List[UserProfile]
    # Development environments usually have only a few users, but
    # it still makes sense to limit how many extra users we render to
    # support performance testing with DevAuthBackend.
    users_query = UserProfile.objects.select_related().filter(is_bot=False, is_active=True)
    shakespearian_users = users_query.exclude(email__startswith='extrauser').order_by('email')
    extra_users = users_query.filter(email__startswith='extrauser').order_by('email')
    # Limit the number of extra users we offer by default
    extra_users = extra_users[0:extra_users_count]
    users = list(shakespearian_users) + list(extra_users)
    return users

def login_page(request, **kwargs):
    # type: (HttpRequest, **Any) -> HttpResponse
    if request.user.is_authenticated():
        return HttpResponseRedirect("/")
    if is_subdomain_root_or_alias(request) and settings.REALMS_HAVE_SUBDOMAINS:
        redirect_url = reverse('zerver.views.registration.find_my_team')
        return HttpResponseRedirect(redirect_url)

    extra_context = kwargs.pop('extra_context', {})
    if dev_auth_enabled():
        users = get_dev_users()
        extra_context['direct_admins'] = [u.email for u in users if u.is_realm_admin]
        extra_context['direct_users'] = [
            u.email for u in users
            if not u.is_realm_admin and u.realm.string_id == 'zulip']
        extra_context['community_users'] = [
            u.email for u in users
            if u.realm.string_id != 'zulip']
    template_response = django_login_page(
        request, authentication_form=OurAuthenticationForm,
        extra_context=extra_context, **kwargs)
    try:
        template_response.context_data['email'] = request.GET['email']
    except KeyError:
        pass

    try:
        template_response.context_data['subdomain'] = request.GET['subdomain']
        template_response.context_data['wrong_subdomain_error'] = WRONG_SUBDOMAIN_ERROR
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
    user_profile = authenticate(username=email, realm_subdomain=get_subdomain(request))
    if user_profile is None:
        raise Exception("User cannot login")
    login(request, user_profile)
    if settings.REALMS_HAVE_SUBDOMAINS and user_profile.realm.subdomain is not None:
        return HttpResponseRedirect(user_profile.realm.uri)
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
    user_profile = authenticate(username=username,
                                realm_subdomain=get_subdomain(request),
                                return_data=return_data)
    if return_data.get("inactive_realm"):
        return json_error(_("Your realm has been deactivated."),
                          data={"reason": "realm deactivated"}, status=403)
    if return_data.get("inactive_user"):
        return json_error(_("Your account has been disabled."),
                          data={"reason": "user disable"}, status=403)
    login(request, user_profile)
    return json_success({"api_key": user_profile.api_key, "email": user_profile.email})

@csrf_exempt
def api_dev_get_emails(request):
    # type: (HttpRequest) -> HttpResponse
    if not dev_auth_enabled() or settings.PRODUCTION:
        return json_error(_("Dev environment not enabled."))
    users = get_dev_users()
    return json_success(dict(direct_admins=[u.email for u in users if u.is_realm_admin],
                             direct_users=[u.email for u in users if not u.is_realm_admin]))

@csrf_exempt
@require_post
@has_request_variables
def api_fetch_api_key(request, username=REQ(), password=REQ()):
    # type: (HttpRequest, str, str) -> HttpResponse
    return_data = {} # type: Dict[str, bool]
    if username == "google-oauth2-token":
        user_profile = authenticate(google_oauth2_token=password,
                                    realm_subdomain=get_subdomain(request),
                                    return_data=return_data)
    else:
        user_profile = authenticate(username=username,
                                    password=password,
                                    realm_subdomain=get_subdomain(request),
                                    return_data=return_data)
    if return_data.get("inactive_user"):
        return json_error(_("Your account has been disabled."),
                          data={"reason": "user disable"}, status=403)
    if return_data.get("inactive_realm"):
        return json_error(_("Your realm has been deactivated."),
                          data={"reason": "realm deactivated"}, status=403)
    if return_data.get("password_auth_disabled"):
        return json_error(_("Password auth is disabled in your team."),
                          data={"reason": "password auth disabled"}, status=403)
    if user_profile is None:
        if return_data.get("valid_attestation"):
            # We can leak that the user is unregistered iff they present a valid authentication string for the user.
            return json_error(_("This user is not registered; do so from a browser."),
                              data={"reason": "unregistered"}, status=403)
        return json_error(_("Your username or password is incorrect."),
                          data={"reason": "incorrect_creds"}, status=403)
    return json_success({"api_key": user_profile.api_key, "email": user_profile.email})

@csrf_exempt
def api_get_auth_backends(request):
    # type: (HttpRequest) -> HttpResponse
    """Returns which authentication methods are enabled on the server"""
    if settings.REALMS_HAVE_SUBDOMAINS:
        subdomain = get_subdomain(request)
        try:
            realm = Realm.objects.get(string_id=subdomain)
        except Realm.DoesNotExist:
            # If not the root subdomain, this is an error
            if subdomain != "":
                return json_error(_("Invalid subdomain"))
            # With the root subdomain, it's an error or not depending
            # whether SUBDOMAINS_HOMEPAGE (which indicates whether
            # there are some realms without subdomains on this server)
            # is set.
            if settings.SUBDOMAINS_HOMEPAGE:
                return json_error(_("Subdomain required"))
            else:
                realm = None
    else:
        # Without subdomains, we just have to report what the server
        # supports, since we don't know the realm.
        realm = None
    return json_success({"password": password_auth_enabled(realm),
                         "dev": dev_auth_enabled(realm),
                         "google": google_auth_enabled(realm),
                         "zulip_version": ZULIP_VERSION,
                         })

@authenticated_json_post_view
@has_request_variables
def json_fetch_api_key(request, user_profile, password=REQ(default='')):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    if password_auth_enabled(user_profile.realm):
        if not authenticate(username=user_profile.email, password=password,
                            realm_subdomain=get_subdomain(request)):
            return json_error(_("Your username or password is incorrect."))
    return json_success({"api_key": user_profile.api_key})

@csrf_exempt
def api_fetch_google_client_id(request):
    # type: (HttpRequest) -> HttpResponse
    if not settings.GOOGLE_CLIENT_ID:
        return json_error(_("GOOGLE_CLIENT_ID is not configured"), status=400)
    return json_success({"google_client_id": settings.GOOGLE_CLIENT_ID})

@require_post
def logout_then_login(request, **kwargs):
    # type: (HttpRequest, **Any) -> HttpResponse
    return django_logout_then_login(request, kwargs)
