from __future__ import absolute_import

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth import authenticate, get_backends
from django.contrib.auth.views import login as django_login_page, \
    logout_then_login as django_logout_then_login
from django.core.urlresolvers import reverse
from zerver.decorator import authenticated_json_post_view, require_post, \
    process_client, do_login
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, \
    HttpResponseNotFound
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.utils.translation import ugettext as _
from django.core import signing
from six.moves import urllib
from typing import Any, Dict, List, Optional, Tuple, Text

from confirmation.models import Confirmation, create_confirmation_link
from zerver.context_processors import zulip_default_context
from zerver.forms import HomepageForm, OurAuthenticationForm, \
    WRONG_SUBDOMAIN_ERROR
from zerver.lib.mobile_auth_otp import is_valid_otp, otp_encrypt_api_key
from zerver.lib.request import REQ, has_request_variables, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.utils import get_subdomain, is_subdomain_root_or_alias
from zerver.lib.validator import validate_login_email
from zerver.models import PreregistrationUser, UserProfile, remote_user_to_email, Realm, \
    get_realm
from zerver.views.registration import create_preregistration_user, get_realm_from_request, \
    redirect_and_log_into_subdomain, redirect_to_deactivation_notice
from zerver.signals import email_on_new_login
from zproject.backends import password_auth_enabled, dev_auth_enabled, \
    github_auth_enabled, google_auth_enabled, ldap_auth_enabled
from version import ZULIP_VERSION

import hashlib
import hmac
import jwt
import logging
import requests
import time
import ujson

def maybe_send_to_registration(request, email, full_name='', password_required=True):
    # type: (HttpRequest, Text, Text, bool) -> HttpResponse
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
                prereg_user = create_preregistration_user(email, request,
                                                          password_required=password_required)
        else:
            prereg_user = create_preregistration_user(email, request,
                                                      password_required=password_required)

        return redirect("".join((
            create_confirmation_link(prereg_user, request.get_host(), Confirmation.USER_REGISTRATION),
            '?full_name=',
            # urllib does not handle Unicode, so coerece to encoded byte string
            # Explanation: http://stackoverflow.com/a/5605354/90777
            urllib.parse.quote_plus(full_name.encode('utf8')))))
    else:
        url = reverse('register')
        return render(request,
                      'zerver/accounts_home.html',
                      context={'form': form, 'current_url': lambda: url},
                      )

def redirect_to_subdomain_login_url():
    # type: () -> HttpResponseRedirect
    login_url = reverse('django.contrib.auth.views.login')
    redirect_url = login_url + '?subdomain=1'
    return HttpResponseRedirect(redirect_url)

def redirect_to_config_error(error_type):
    # type: (str) -> HttpResponseRedirect
    return HttpResponseRedirect("/config-error/%s" % (error_type,))

def login_or_register_remote_user(request, remote_username, user_profile, full_name='',
                                  invalid_subdomain=False, mobile_flow_otp=None,
                                  is_signup=False):
    # type: (HttpRequest, Optional[Text], Optional[UserProfile], Text, bool, Optional[str], bool) -> HttpResponse
    if invalid_subdomain:
        # Show login page with an error message
        return redirect_to_subdomain_login_url()

    if user_profile is None or user_profile.is_mirror_dummy:
        # Since execution has reached here, we have verified the user
        # controls an email address (remote_username) but there's no
        # associated Zulip user account.
        if is_signup:
            # If they're trying to sign up, send them over to the PreregistrationUser flow.
            return maybe_send_to_registration(request, remote_user_to_email(remote_username),
                                              full_name, password_required=False)

        # Otherwise, we send them to a special page that asks if they
        # want to register or provided the wrong email and want to go back.
        try:
            validate_email(remote_username)
            invalid_email = False
        except ValidationError:
            # If email address is invalid, we can't send the user
            # PreregistrationUser flow.
            invalid_email = True
        context = {'full_name': full_name,
                   'email': remote_username,
                   'invalid_email': invalid_email}
        return render(request,
                      'zerver/confirm_continue_registration.html',
                      context=context)

    if mobile_flow_otp is not None:
        # For the mobile Oauth flow, we send the API key and other
        # necessary details in a redirect to a zulip:// URI scheme.
        params = {
            'otp_encrypted_api_key': otp_encrypt_api_key(user_profile, mobile_flow_otp),
            'email': remote_username,
            'realm': user_profile.realm.uri,
        }
        # We can't use HttpResponseRedirect, since it only allows HTTP(S) URLs
        response = HttpResponse(status=302)
        response['Location'] = 'zulip://login?' + urllib.parse.urlencode(params)
        # Maybe sending 'user_logged_in' signal is the better approach:
        #   user_logged_in.send(sender=user_profile.__class__, request=request, user=user_profile)
        # Not doing this only because over here we don't add the user information
        # in the session. If the signal receiver assumes that we do then that
        # would cause problems.
        email_on_new_login(sender=user_profile.__class__, request=request, user=user_profile)

        # Mark this request as having a logged-in user for our server logs.
        process_client(request, user_profile)
        request._email = user_profile.email

        return response

    do_login(request, user_profile)
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

    # Django invokes authenticate methods by matching arguments, and this
    # authentication flow will not invoke LDAP authentication because of
    # this condition of Django so no need to check if LDAP backend is
    # enabled.
    validate_login_email(remote_user_to_email(remote_user))

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
        return_data = {}  # type: Dict[str, bool]
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
    # type: (HttpRequest, str) -> str
    # In Django 1.10, get_token returns a salted token which changes
    # everytime get_token is called.
    from django.middleware.csrf import _unsalt_cipher_token
    token = _unsalt_cipher_token(get_token(request))
    return hmac.new(token.encode('utf-8'), value.encode("utf-8"), hashlib.sha256).hexdigest()

def start_google_oauth2(request):
    # type: (HttpRequest) -> HttpResponse
    url = reverse('zerver.views.auth.send_oauth_request_to_google')

    if not (settings.GOOGLE_OAUTH2_CLIENT_ID and settings.GOOGLE_OAUTH2_CLIENT_SECRET):
        return redirect_to_config_error("google")

    is_signup = bool(request.GET.get('is_signup'))
    return redirect_to_main_site(request, url, is_signup=is_signup)

def redirect_to_main_site(request, url, is_signup=False):
    # type: (HttpRequest, Text, bool) -> HttpResponse
    main_site_uri = ''.join((
        settings.EXTERNAL_URI_SCHEME,
        settings.EXTERNAL_HOST,
        url,
    ))
    params = {
        'subdomain': get_subdomain(request),
        'is_signup': '1' if is_signup else '0',
    }

    # mobile_flow_otp is a one-time pad provided by the app that we
    # can use to encrypt the API key when passing back to the app.
    mobile_flow_otp = request.GET.get('mobile_flow_otp')
    if mobile_flow_otp is not None:
        if not is_valid_otp(mobile_flow_otp):
            raise JsonableError(_("Invalid OTP"))
        params['mobile_flow_otp'] = mobile_flow_otp

    return redirect(main_site_uri + '?' + urllib.parse.urlencode(params))

def start_social_login(request, backend):
    # type: (HttpRequest, Text) -> HttpResponse
    backend_url = reverse('social:begin', args=[backend])
    if (backend == "github") and not (settings.SOCIAL_AUTH_GITHUB_KEY and settings.SOCIAL_AUTH_GITHUB_SECRET):
        return redirect_to_config_error("github")

    return redirect_to_main_site(request, backend_url)

def start_social_signup(request, backend):
    # type: (HttpRequest, Text) -> HttpResponse
    backend_url = reverse('social:begin', args=[backend])
    return redirect_to_main_site(request, backend_url, is_signup=True)

def send_oauth_request_to_google(request):
    # type: (HttpRequest) -> HttpResponse
    subdomain = request.GET.get('subdomain', '')
    is_signup = request.GET.get('is_signup', '')
    mobile_flow_otp = request.GET.get('mobile_flow_otp', '0')

    if settings.REALMS_HAVE_SUBDOMAINS:
        if ((settings.ROOT_DOMAIN_LANDING_PAGE and subdomain == '') or
                not Realm.objects.filter(string_id=subdomain).exists()):
            return redirect_to_subdomain_login_url()

    google_uri = 'https://accounts.google.com/o/oauth2/auth?'
    cur_time = str(int(time.time()))
    csrf_state = '%s:%s:%s:%s' % (cur_time, subdomain, mobile_flow_otp, is_signup)

    # Now compute the CSRF hash with the other parameters as an input
    csrf_state += ":%s" % (google_oauth2_csrf(request, csrf_state),)

    params = {
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
    return redirect(google_uri + urllib.parse.urlencode(params))

def finish_google_oauth2(request):
    # type: (HttpRequest) -> HttpResponse
    error = request.GET.get('error')
    if error == 'access_denied':
        return redirect('/')
    elif error is not None:
        logging.warning('Error from google oauth2 login: %s' % (request.GET.get("error"),))
        return HttpResponse(status=400)

    csrf_state = request.GET.get('state')
    if csrf_state is None or len(csrf_state.split(':')) != 5:
        logging.warning('Missing Google oauth2 CSRF state')
        return HttpResponse(status=400)

    (csrf_data, hmac_value) = csrf_state.rsplit(':', 1)
    if hmac_value != google_oauth2_csrf(request, csrf_data):
        logging.warning('Google oauth2 CSRF error')
        return HttpResponse(status=400)
    cur_time, subdomain, mobile_flow_otp, is_signup = csrf_data.split(':')
    if mobile_flow_otp == '0':
        mobile_flow_otp = None

    is_signup = bool(is_signup == '1')

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

    if not subdomain or mobile_flow_otp is not None:
        # When request was not initiated from subdomain.
        user_profile, return_data = authenticate_remote_user(request, email_address,
                                                             subdomain=subdomain)
        invalid_subdomain = bool(return_data.get('invalid_subdomain'))
        return login_or_register_remote_user(request, email_address, user_profile,
                                             full_name, invalid_subdomain,
                                             mobile_flow_otp=mobile_flow_otp,
                                             is_signup=is_signup)

    try:
        realm = Realm.objects.get(string_id=subdomain)
    except Realm.DoesNotExist:  # nocoverage
        return redirect_to_subdomain_login_url()

    return redirect_and_log_into_subdomain(
        realm, full_name, email_address, is_signup=is_signup)

def authenticate_remote_user(request, email_address, subdomain=None):
    # type: (HttpRequest, str, Optional[Text]) -> Tuple[UserProfile, Dict[str, Any]]
    return_data = {}  # type: Dict[str, bool]
    if email_address is None:
        # No need to authenticate if email address is None. We already
        # know that user_profile would be None as well. In fact, if we
        # call authenticate in this case, we might get an exception from
        # ZulipDummyBackend which doesn't accept a None as a username.
        logging.warning("Email address was None while trying to authenticate "
                        "remote user.")
        return None, return_data
    if subdomain is None:
        subdomain = get_subdomain(request)

    user_profile = authenticate(username=email_address,
                                realm_subdomain=subdomain,
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
    is_signup = data['is_signup']
    if is_signup:
        # If we are signing up, user_profile should be None. In case
        # email_address already exists, user will get an error message.
        user_profile = None
        return_data = {}  # type: Dict[str, Any]
    else:
        user_profile, return_data = authenticate_remote_user(request, email_address)
    invalid_subdomain = bool(return_data.get('invalid_subdomain'))
    return login_or_register_remote_user(request, email_address, user_profile,
                                         full_name, invalid_subdomain=invalid_subdomain,
                                         is_signup=is_signup)

def get_dev_users(realm=None, extra_users_count=10):
    # type: (Optional[Realm], int) -> List[UserProfile]
    # Development environments usually have only a few users, but
    # it still makes sense to limit how many extra users we render to
    # support performance testing with DevAuthBackend.
    if realm is not None:
        users_query = UserProfile.objects.select_related().filter(is_bot=False, is_active=True, realm=realm)
    else:
        users_query = UserProfile.objects.select_related().filter(is_bot=False, is_active=True)

    shakespearian_users = users_query.exclude(email__startswith='extrauser').order_by('email')
    extra_users = users_query.filter(email__startswith='extrauser').order_by('email')
    # Limit the number of extra users we offer by default
    extra_users = extra_users[0:extra_users_count]
    users = list(shakespearian_users) + list(extra_users)
    return users

def login_page(request, **kwargs):
    # type: (HttpRequest, **Any) -> HttpResponse
    if request.user.is_authenticated:
        return HttpResponseRedirect("/")
    if is_subdomain_root_or_alias(request) and settings.ROOT_DOMAIN_LANDING_PAGE:
        redirect_url = reverse('zerver.views.registration.find_account')
        return HttpResponseRedirect(redirect_url)

    realm = get_realm_from_request(request)
    if realm and realm.deactivated:
        return redirect_to_deactivation_notice()

    extra_context = kwargs.pop('extra_context', {})
    if dev_auth_enabled():
        if 'new_realm' in request.POST:
            realm = get_realm(request.POST['new_realm'])
        else:
            realm = get_realm_from_request(request)

        users = get_dev_users(realm)
        extra_context['current_realm'] = realm
        extra_context['all_realms'] = Realm.objects.all()

        extra_context['direct_admins'] = [u.email for u in users if u.is_realm_admin]
        extra_context['direct_users'] = [u.email for u in users if not u.is_realm_admin]

        if settings.REALMS_HAVE_SUBDOMAINS and 'new_realm' in request.POST:
            # If we're switching realms, redirect to that realm
            return HttpResponseRedirect(realm.uri)

    template_response = django_login_page(
        request, authentication_form=OurAuthenticationForm,
        extra_context=extra_context, **kwargs)
    try:
        template_response.context_data['email'] = request.GET['email']
    except KeyError:
        pass

    try:
        already_registered = request.GET['already_registered']
        template_response.context_data['already_registered'] = already_registered
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
    do_login(request, user_profile)
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

    # Django invokes authenticate methods by matching arguments, and this
    # authentication flow will not invoke LDAP authentication because of
    # this condition of Django so no need to check if LDAP backend is
    # enabled.
    validate_login_email(username)

    return_data = {}  # type: Dict[str, bool]
    user_profile = authenticate(username=username,
                                realm_subdomain=get_subdomain(request),
                                return_data=return_data)
    if return_data.get("inactive_realm"):
        return json_error(_("Your realm has been deactivated."),
                          data={"reason": "realm deactivated"}, status=403)
    if return_data.get("inactive_user"):
        return json_error(_("Your account has been disabled."),
                          data={"reason": "user disable"}, status=403)
    if user_profile is None:
        return json_error(_("This user is not registered."),
                          data={"reason": "unregistered"}, status=403)
    do_login(request, user_profile)
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
    return_data = {}  # type: Dict[str, bool]
    if username == "google-oauth2-token":
        user_profile = authenticate(google_oauth2_token=password,
                                    realm_subdomain=get_subdomain(request),
                                    return_data=return_data)
    else:
        if not ldap_auth_enabled(realm=get_realm_from_request(request)):
            # In case we don't authenticate against LDAP, check for a valid
            # email. LDAP backend can authenticate against a non-email.
            validate_login_email(username)

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

    # Maybe sending 'user_logged_in' signal is the better approach:
    #   user_logged_in.send(sender=user_profile.__class__, request=request, user=user_profile)
    # Not doing this only because over here we don't add the user information
    # in the session. If the signal receiver assumes that we do then that
    # would cause problems.
    email_on_new_login(sender=user_profile.__class__, request=request, user=user_profile)

    # Mark this request as having a logged-in user for our server logs.
    process_client(request, user_profile)
    request._email = user_profile.email

    return json_success({"api_key": user_profile.api_key, "email": user_profile.email})

def get_auth_backends_data(request):
    # type: (HttpRequest) -> Dict[str, Any]
    """Returns which authentication methods are enabled on the server"""
    if settings.REALMS_HAVE_SUBDOMAINS:
        subdomain = get_subdomain(request)
        try:
            realm = Realm.objects.get(string_id=subdomain)
        except Realm.DoesNotExist:
            # If not the root subdomain, this is an error
            if subdomain != "":
                raise JsonableError(_("Invalid subdomain"))
            # With the root subdomain, it's an error or not depending
            # whether ROOT_DOMAIN_LANDING_PAGE (which indicates whether
            # there are some realms without subdomains on this server)
            # is set.
            if settings.ROOT_DOMAIN_LANDING_PAGE:
                raise JsonableError(_("Subdomain required"))
            else:
                realm = None
    else:
        # Without subdomains, we just have to report what the server
        # supports, since we don't know the realm.
        realm = None
    return {"password": password_auth_enabled(realm),
            "dev": dev_auth_enabled(realm),
            "github": github_auth_enabled(realm),
            "google": google_auth_enabled(realm)}

@csrf_exempt
def api_get_auth_backends(request):
    # type: (HttpRequest) -> HttpResponse
    """Deprecated route; this is to be replaced by api_get_server_settings"""
    auth_backends = get_auth_backends_data(request)
    auth_backends['zulip_version'] = ZULIP_VERSION
    return json_success(auth_backends)

@require_GET
@csrf_exempt
def api_get_server_settings(request):
    # type: (HttpRequest) -> HttpResponse
    result = dict(
        authentication_methods=get_auth_backends_data(request),
        zulip_version=ZULIP_VERSION,
    )
    context = zulip_default_context(request)
    # IMPORTANT NOTE:
    # realm_name, realm_icon, etc. are not guaranteed to appear in the response.
    # * If they do, that means the server URL has only one realm on it
    # * If they don't, the server has multiple realms, and it's not clear which is
    #   the requested realm, so we can't send back these data.
    for settings_item in [
            "email_auth_enabled",
            "require_email_format_usernames",
            "realm_uri",
            "realm_name",
            "realm_icon",
            "realm_description"]:
        if context[settings_item] is not None:
            result[settings_item] = context[settings_item]
    return json_success(result)

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
