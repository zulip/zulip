from django.forms import Form
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.views import login as django_login_page, \
    logout_then_login as django_logout_then_login
from django.contrib.auth.views import password_reset as django_password_reset
from django.urls import reverse
from zerver.decorator import require_post, \
    process_client, do_login, log_view_func
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import SimpleTemplateResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.utils.translation import ugettext as _
from django.utils.http import is_safe_url
from django.core import signing
import urllib
from typing import Any, Dict, List, Optional, Tuple

from confirmation.models import Confirmation, create_confirmation_link
from zerver.context_processors import zulip_default_context, get_realm_from_request
from zerver.forms import HomepageForm, OurAuthenticationForm, \
    WRONG_SUBDOMAIN_ERROR, ZulipPasswordResetForm, AuthenticationTokenForm
from zerver.lib.mobile_auth_otp import is_valid_otp, otp_encrypt_api_key
from zerver.lib.push_notifications import push_notifications_enabled
from zerver.lib.request import REQ, has_request_variables, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.subdomains import get_subdomain, is_subdomain_root_or_alias
from zerver.lib.user_agent import parse_user_agent
from zerver.lib.users import get_api_key
from zerver.lib.validator import validate_login_email
from zerver.models import PreregistrationUser, UserProfile, remote_user_to_email, Realm, \
    get_realm
from zerver.signals import email_on_new_login
from zproject.backends import password_auth_enabled, dev_auth_enabled, \
    ldap_auth_enabled, ZulipLDAPConfigurationError, ZulipLDAPAuthBackend, \
    AUTH_BACKEND_NAME_MAP, auth_enabled_helper
from version import ZULIP_VERSION

import hashlib
import hmac
import jwt
import logging
import requests
import time

from two_factor.forms import BackupTokenForm
from two_factor.views import LoginView as BaseTwoFactorLoginView

ExtraContext = Optional[Dict[str, Any]]

def get_safe_redirect_to(url: str, redirect_host: str) -> str:
    is_url_safe = is_safe_url(url=url, host=redirect_host)
    if is_url_safe:
        return urllib.parse.urljoin(redirect_host, url)
    else:
        return redirect_host

def create_preregistration_user(email: str, request: HttpRequest, realm_creation: bool=False,
                                password_required: bool=True) -> HttpResponse:
    realm = None
    if not realm_creation:
        realm = get_realm(get_subdomain(request))
    return PreregistrationUser.objects.create(email=email,
                                              realm_creation=realm_creation,
                                              password_required=password_required,
                                              realm=realm)

def maybe_send_to_registration(request: HttpRequest, email: str, full_name: str='',
                               is_signup: bool=False, password_required: bool=True,
                               multiuse_object_key: str='') -> HttpResponse:
    realm = get_realm(get_subdomain(request))
    from_multiuse_invite = False
    multiuse_obj = None
    streams_to_subscribe = None
    invited_as = PreregistrationUser.INVITE_AS['MEMBER']
    if multiuse_object_key:
        from_multiuse_invite = True
        multiuse_obj = Confirmation.objects.get(confirmation_key=multiuse_object_key).content_object
        realm = multiuse_obj.realm
        streams_to_subscribe = multiuse_obj.streams.all()
        invited_as = multiuse_obj.invited_as

    form = HomepageForm({'email': email}, realm=realm, from_multiuse_invite=from_multiuse_invite)
    if form.is_valid():
        # Construct a PreregistrationUser object and send the user over to
        # the confirmation view.
        prereg_user = None
        if settings.ONLY_SSO:
            try:
                prereg_user = PreregistrationUser.objects.filter(
                    email__iexact=email, realm=realm).latest("invited_at")
            except PreregistrationUser.DoesNotExist:
                prereg_user = create_preregistration_user(email, request,
                                                          password_required=password_required)
        else:
            prereg_user = create_preregistration_user(email, request,
                                                      password_required=password_required)

        if multiuse_object_key:
            request.session.modified = True
            if streams_to_subscribe is not None:
                prereg_user.streams.set(streams_to_subscribe)
            prereg_user.invited_as = invited_as
            prereg_user.save()

        confirmation_link = create_confirmation_link(prereg_user, request.get_host(),
                                                     Confirmation.USER_REGISTRATION)
        if is_signup:
            return redirect(confirmation_link)

        context = {'email': email,
                   'continue_link': confirmation_link,
                   'full_name': full_name}
        return render(request,
                      'zerver/confirm_continue_registration.html',
                      context=context)
    else:
        url = reverse('register')
        return render(request,
                      'zerver/accounts_home.html',
                      context={'form': form, 'current_url': lambda: url,
                               'from_multiuse_invite': from_multiuse_invite,
                               'multiuse_object_key': multiuse_object_key},
                      )

def redirect_to_subdomain_login_url() -> HttpResponseRedirect:
    login_url = reverse('django.contrib.auth.views.login')
    redirect_url = login_url + '?subdomain=1'
    return HttpResponseRedirect(redirect_url)

def redirect_to_config_error(error_type: str) -> HttpResponseRedirect:
    return HttpResponseRedirect("/config-error/%s" % (error_type,))

def login_or_register_remote_user(request: HttpRequest, remote_username: Optional[str],
                                  user_profile: Optional[UserProfile], full_name: str='',
                                  invalid_subdomain: bool=False, mobile_flow_otp: Optional[str]=None,
                                  is_signup: bool=False, redirect_to: str='',
                                  multiuse_object_key: str='') -> HttpResponse:
    email = remote_user_to_email(remote_username)
    if user_profile is None or user_profile.is_mirror_dummy:
        # We have verified the user controls an email address, but
        # there's no associated Zulip user account.  Consider sending
        # the request to registration.
        return maybe_send_to_registration(request, email, full_name, password_required=False,
                                          is_signup=is_signup, multiuse_object_key=multiuse_object_key)

    # Otherwise, the user has successfully authenticated to an
    # account, and we need to do the right thing depending whether
    # or not they're using the mobile OTP flow or want a browser session.
    if mobile_flow_otp is not None:
        # For the mobile Oauth flow, we send the API key and other
        # necessary details in a redirect to a zulip:// URI scheme.
        api_key = get_api_key(user_profile)
        params = {
            'otp_encrypted_api_key': otp_encrypt_api_key(api_key, mobile_flow_otp),
            'email': email,
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

    redirect_to = get_safe_redirect_to(redirect_to, user_profile.realm.uri)
    return HttpResponseRedirect(redirect_to)

@log_view_func
@has_request_variables
def remote_user_sso(request: HttpRequest,
                    mobile_flow_otp: Optional[str]=REQ(default=None)) -> HttpResponse:
    try:
        remote_user = request.META["REMOTE_USER"]
    except KeyError:
        # TODO: Arguably the JsonableError values here should be
        # full-page HTML configuration errors instead.
        raise JsonableError(_("No REMOTE_USER set."))

    # Django invokes authenticate methods by matching arguments, and this
    # authentication flow will not invoke LDAP authentication because of
    # this condition of Django so no need to check if LDAP backend is
    # enabled.
    validate_login_email(remote_user_to_email(remote_user))

    # Here we support the mobile flow for REMOTE_USER_BACKEND; we
    # validate the data format and then pass it through to
    # login_or_register_remote_user if appropriate.
    if mobile_flow_otp is not None:
        if not is_valid_otp(mobile_flow_otp):
            raise JsonableError(_("Invalid OTP"))

    subdomain = get_subdomain(request)
    realm = get_realm(subdomain)
    # Since RemoteUserBackend will return None if Realm is None, we
    # don't need to check whether `get_realm` returned None.
    return_data = {}  # type: Dict[str, Any]
    user_profile = authenticate(remote_user=remote_user, realm=realm,
                                return_data=return_data)

    redirect_to = request.GET.get('next', '')

    return login_or_register_remote_user(request, remote_user, user_profile,
                                         invalid_subdomain = bool(return_data.get("invalid_subdomain")),
                                         mobile_flow_otp=mobile_flow_otp,
                                         redirect_to=redirect_to)

@csrf_exempt
@log_view_func
def remote_user_jwt(request: HttpRequest) -> HttpResponse:
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
    email_domain = payload.get('realm', None)
    if email_domain is None:
        raise JsonableError(_("No organization specified in JSON web token claims"))

    email = "%s@%s" % (remote_user, email_domain)

    realm = get_realm(subdomain)
    if realm is None:
        raise JsonableError(_("Wrong subdomain"))

    try:
        # We do all the authentication we need here (otherwise we'd have to
        # duplicate work), but we need to call authenticate with some backend so
        # that the request.backend attribute gets set.
        return_data = {}  # type: Dict[str, bool]
        user_profile = authenticate(username=email,
                                    realm=realm,
                                    return_data=return_data,
                                    use_dummy_backend=True)
    except UserProfile.DoesNotExist:
        user_profile = None

    return login_or_register_remote_user(request, email, user_profile, remote_user)

def google_oauth2_csrf(request: HttpRequest, value: str) -> str:
    # In Django 1.10, get_token returns a salted token which changes
    # every time get_token is called.
    from django.middleware.csrf import _unsalt_cipher_token
    token = _unsalt_cipher_token(get_token(request))
    return hmac.new(token.encode('utf-8'), value.encode("utf-8"), hashlib.sha256).hexdigest()

def reverse_on_root(viewname: str, args: List[str]=None, kwargs: Dict[str, str]=None) -> str:
    return settings.ROOT_DOMAIN_URI + reverse(viewname, args=args, kwargs=kwargs)

def oauth_redirect_to_root(request: HttpRequest, url: str,
                           sso_type: str, is_signup: bool=False) -> HttpResponse:
    main_site_uri = settings.ROOT_DOMAIN_URI + url
    if settings.SOCIAL_AUTH_SUBDOMAIN is not None and sso_type == 'social':
        main_site_uri = (settings.EXTERNAL_URI_SCHEME +
                         settings.SOCIAL_AUTH_SUBDOMAIN +
                         "." +
                         settings.EXTERNAL_HOST) + url

    params = {
        'subdomain': get_subdomain(request),
        'is_signup': '1' if is_signup else '0',
    }

    params['multiuse_object_key'] = request.GET.get('multiuse_object_key', '')

    # mobile_flow_otp is a one-time pad provided by the app that we
    # can use to encrypt the API key when passing back to the app.
    mobile_flow_otp = request.GET.get('mobile_flow_otp')
    if mobile_flow_otp is not None:
        if not is_valid_otp(mobile_flow_otp):
            raise JsonableError(_("Invalid OTP"))
        params['mobile_flow_otp'] = mobile_flow_otp

    next = request.GET.get('next')
    if next:
        params['next'] = next

    return redirect(main_site_uri + '?' + urllib.parse.urlencode(params))

def start_google_oauth2(request: HttpRequest) -> HttpResponse:
    url = reverse('zerver.views.auth.send_oauth_request_to_google')

    if not (settings.GOOGLE_OAUTH2_CLIENT_ID and settings.GOOGLE_OAUTH2_CLIENT_SECRET):
        return redirect_to_config_error("google")

    is_signup = bool(request.GET.get('is_signup'))
    return oauth_redirect_to_root(request, url, 'google', is_signup=is_signup)

def start_social_login(request: HttpRequest, backend: str) -> HttpResponse:
    backend_url = reverse('social:begin', args=[backend])
    if (backend == "github") and not (settings.SOCIAL_AUTH_GITHUB_KEY and
                                      settings.SOCIAL_AUTH_GITHUB_SECRET):
        return redirect_to_config_error("github")
    # TODO: Add a similar block of AzureAD.

    return oauth_redirect_to_root(request, backend_url, 'social')

def start_social_signup(request: HttpRequest, backend: str) -> HttpResponse:
    backend_url = reverse('social:begin', args=[backend])
    return oauth_redirect_to_root(request, backend_url, 'social', is_signup=True)

def send_oauth_request_to_google(request: HttpRequest) -> HttpResponse:
    subdomain = request.GET.get('subdomain', '')
    is_signup = request.GET.get('is_signup', '')
    next = request.GET.get('next', '')
    mobile_flow_otp = request.GET.get('mobile_flow_otp', '0')
    multiuse_object_key = request.GET.get('multiuse_object_key', '')

    if ((settings.ROOT_DOMAIN_LANDING_PAGE and subdomain == '') or
            not Realm.objects.filter(string_id=subdomain).exists()):
        return redirect_to_subdomain_login_url()

    google_uri = 'https://accounts.google.com/o/oauth2/auth?'
    cur_time = str(int(time.time()))
    csrf_state = '%s:%s:%s:%s:%s:%s' % (cur_time, subdomain, mobile_flow_otp, is_signup,
                                        next, multiuse_object_key)
    # Now compute the CSRF hash with the other parameters as an input
    csrf_state += ":%s" % (google_oauth2_csrf(request, csrf_state),)

    params = {
        'response_type': 'code',
        'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
        'redirect_uri': reverse_on_root('zerver.views.auth.finish_google_oauth2'),
        'scope': 'profile email',
        'state': csrf_state,
        'prompt': 'select_account',
    }
    return redirect(google_uri + urllib.parse.urlencode(params))

@log_view_func
def finish_google_oauth2(request: HttpRequest) -> HttpResponse:
    error = request.GET.get('error')
    if error == 'access_denied':
        return redirect('/')
    elif error is not None:
        logging.warning('Error from google oauth2 login: %s' % (request.GET.get("error"),))
        return HttpResponse(status=400)

    csrf_state = request.GET.get('state')
    if csrf_state is None or len(csrf_state.split(':')) != 7:
        logging.warning('Missing Google oauth2 CSRF state')
        return HttpResponse(status=400)

    (csrf_data, hmac_value) = csrf_state.rsplit(':', 1)
    if hmac_value != google_oauth2_csrf(request, csrf_data):
        logging.warning('Google oauth2 CSRF error')
        return HttpResponse(status=400)
    cur_time, subdomain, mobile_flow_otp, is_signup, next, multiuse_object_key = csrf_data.split(':')
    if mobile_flow_otp == '0':
        mobile_flow_otp = None

    is_signup = bool(is_signup == '1')

    resp = requests.post(
        'https://www.googleapis.com/oauth2/v3/token',
        data={
            'code': request.GET.get('code'),
            'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            'redirect_uri': reverse_on_root('zerver.views.auth.finish_google_oauth2'),
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
        'https://www.googleapis.com/oauth2/v3/userinfo',
        params={'access_token': access_token}
    )
    if resp.status_code == 400:
        logging.warning('Google login failed making info API call: %s' % (resp.text,))
        return HttpResponse(status=400)
    elif resp.status_code != 200:
        logging.error('Google login failed making API call: %s' % (resp.text,))
        return HttpResponse(status=400)
    body = resp.json()

    if not body['email_verified']:
        logging.error('Google oauth2 account email not verified.')
        return HttpResponse(status=400)

    # Extract the user info from the Google response
    full_name = body['name']
    email_address = body['email']

    try:
        realm = Realm.objects.get(string_id=subdomain)
    except Realm.DoesNotExist:  # nocoverage
        return redirect_to_subdomain_login_url()

    if mobile_flow_otp is not None:
        # When request was not initiated from subdomain.
        user_profile, return_data = authenticate_remote_user(realm, email_address)
        invalid_subdomain = bool(return_data.get('invalid_subdomain'))
        return login_or_register_remote_user(request, email_address, user_profile,
                                             full_name, invalid_subdomain,
                                             mobile_flow_otp=mobile_flow_otp,
                                             is_signup=is_signup,
                                             redirect_to=next)

    return redirect_and_log_into_subdomain(
        realm, full_name, email_address, is_signup=is_signup,
        redirect_to=next, multiuse_object_key=multiuse_object_key)

def authenticate_remote_user(realm: Realm, email_address: str) -> Tuple[UserProfile, Dict[str, Any]]:
    return_data = {}  # type: Dict[str, bool]
    if email_address is None:
        # No need to authenticate if email address is None. We already
        # know that user_profile would be None as well. In fact, if we
        # call authenticate in this case, we might get an exception from
        # ZulipDummyBackend which doesn't accept a None as a username.
        logging.warning("Email address was None while trying to authenticate "
                        "remote user.")
        return None, return_data

    user_profile = authenticate(username=email_address,
                                realm=realm,
                                use_dummy_backend=True,
                                return_data=return_data)
    return user_profile, return_data

_subdomain_token_salt = 'zerver.views.auth.log_into_subdomain'

@log_view_func
def log_into_subdomain(request: HttpRequest, token: str) -> HttpResponse:
    try:
        data = signing.loads(token, salt=_subdomain_token_salt, max_age=15)
    except signing.SignatureExpired as e:
        logging.warning('Subdomain cookie: {}'.format(e))
        return HttpResponse(status=400)
    except signing.BadSignature:
        logging.warning('Subdomain cookie: Bad signature.')
        return HttpResponse(status=400)

    subdomain = get_subdomain(request)
    if data['subdomain'] != subdomain:
        logging.warning('Login attempt on invalid subdomain')
        return HttpResponse(status=400)

    email_address = data['email']
    full_name = data['name']
    is_signup = data['is_signup']
    redirect_to = data['next']

    if 'multiuse_object_key' in data:
        multiuse_object_key = data['multiuse_object_key']
    else:
        multiuse_object_key = ''

    if is_signup:
        # If we are signing up, user_profile should be None. In case
        # email_address already exists, user will get an error message.
        user_profile = None
        return_data = {}  # type: Dict[str, Any]
    else:
        # We can be reasonably confident that this subdomain actually
        # has a corresponding realm, since it was referenced in a
        # signed cookie.  But we probably should add some error
        # handling for the case where the realm disappeared in the
        # meantime.
        realm = get_realm(subdomain)
        user_profile, return_data = authenticate_remote_user(realm, email_address)
    invalid_subdomain = bool(return_data.get('invalid_subdomain'))
    return login_or_register_remote_user(request, email_address, user_profile,
                                         full_name, invalid_subdomain=invalid_subdomain,
                                         is_signup=is_signup, redirect_to=redirect_to,
                                         multiuse_object_key=multiuse_object_key)

def redirect_and_log_into_subdomain(realm: Realm, full_name: str, email_address: str,
                                    is_signup: bool=False, redirect_to: str='',
                                    multiuse_object_key: str='') -> HttpResponse:
    data = {'name': full_name, 'email': email_address, 'subdomain': realm.subdomain,
            'is_signup': is_signup, 'next': redirect_to,
            'multiuse_object_key': multiuse_object_key}
    token = signing.dumps(data, salt=_subdomain_token_salt)
    subdomain_login_uri = (realm.uri
                           + reverse('zerver.views.auth.log_into_subdomain', args=[token]))
    return redirect(subdomain_login_uri)

def get_dev_users(realm: Optional[Realm]=None, extra_users_count: int=10) -> List[UserProfile]:
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

def redirect_to_misconfigured_ldap_notice(error_type: int) -> HttpResponse:
    if error_type == ZulipLDAPAuthBackend.REALM_IS_NONE_ERROR:
        url = reverse('ldap_error_realm_is_none')
    else:
        raise AssertionError("Invalid error type")

    return HttpResponseRedirect(url)

def show_deactivation_notice(request: HttpRequest) -> HttpResponse:
    realm = get_realm_from_request(request)
    if realm and realm.deactivated:
        return render(request, "zerver/deactivated.html",
                      context={"deactivated_domain_name": realm.name})

    return HttpResponseRedirect(reverse('zerver.views.auth.login_page'))

def redirect_to_deactivation_notice() -> HttpResponse:
    return HttpResponseRedirect(reverse('zerver.views.auth.show_deactivation_notice'))

def add_dev_login_context(realm: Realm, context: Dict[str, Any]) -> None:
    users = get_dev_users(realm)
    context['current_realm'] = realm
    context['all_realms'] = Realm.objects.all()

    context['direct_admins'] = [u for u in users if u.is_realm_admin]
    context['guest_users'] = [u for u in users if u.is_guest]
    context['direct_users'] = [u for u in users if not (u.is_realm_admin or u.is_guest)]

def update_login_page_context(request: HttpRequest, context: Dict[str, Any]) -> None:
    for key in ('email', 'subdomain', 'already_registered'):
        try:
            context[key] = request.GET[key]
        except KeyError:
            pass

    context['wrong_subdomain_error'] = WRONG_SUBDOMAIN_ERROR

class TwoFactorLoginView(BaseTwoFactorLoginView):
    extra_context = None  # type: ExtraContext
    form_list = (
        ('auth', OurAuthenticationForm),
        ('token', AuthenticationTokenForm),
        ('backup', BackupTokenForm),
    )

    def __init__(self, extra_context: ExtraContext=None,
                 *args: Any, **kwargs: Any) -> None:
        self.extra_context = extra_context
        super().__init__(*args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        if self.extra_context is not None:
            context.update(self.extra_context)
        update_login_page_context(self.request, context)

        realm = get_realm_from_request(self.request)
        redirect_to = realm.uri if realm else '/'
        context['next'] = self.request.GET.get('next', redirect_to)
        return context

    def done(self, form_list: List[Form], **kwargs: Any) -> HttpResponse:
        """
        Login the user and redirect to the desired page.

        We need to override this function so that we can redirect to
        realm.uri instead of '/'.
        """
        realm_uri = self.get_user().realm.uri
        # This mock.patch business is an unpleasant hack that we'd
        # ideally like to remove by instead patching the upstream
        # module to support better configurability of the
        # LOGIN_REDIRECT_URL setting.  But until then, it works.  We
        # import mock.patch here because mock has an expensive import
        # process involving pbr -> pkgresources (which is really slow).
        from mock import patch
        with patch.object(settings, 'LOGIN_REDIRECT_URL', realm_uri):
            return super().done(form_list, **kwargs)

def login_page(request: HttpRequest, **kwargs: Any) -> HttpResponse:
    if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:
        if request.user and request.user.is_verified():
            return HttpResponseRedirect(request.user.realm.uri)
    elif request.user.is_authenticated:
        return HttpResponseRedirect(request.user.realm.uri)
    if is_subdomain_root_or_alias(request) and settings.ROOT_DOMAIN_LANDING_PAGE:
        redirect_url = reverse('zerver.views.registration.realm_redirect')
        if request.method == "GET" and request.GET:
            redirect_url = "{}?{}".format(redirect_url, request.GET.urlencode())
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

        add_dev_login_context(realm, extra_context)
        if realm and 'new_realm' in request.POST:
            # If we're switching realms, redirect to that realm, but
            # only if it actually exists.
            return HttpResponseRedirect(realm.uri)

    if 'username' in request.POST:
        extra_context['email'] = request.POST['username']

    if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:
        return start_two_factor_auth(request, extra_context=extra_context,
                                     **kwargs)

    try:
        template_response = django_login_page(
            request, authentication_form=OurAuthenticationForm,
            extra_context=extra_context, **kwargs)
    except ZulipLDAPConfigurationError as e:
        assert len(e.args) > 1
        return redirect_to_misconfigured_ldap_notice(e.args[1])

    if isinstance(template_response, SimpleTemplateResponse):
        # Only those responses that are rendered using a template have
        # context_data attribute. This attribute doesn't exist otherwise. It is
        # added in SimpleTemplateResponse class, which is a derived class of
        # HttpResponse. See django.template.response.SimpleTemplateResponse,
        # https://github.com/django/django/blob/master/django/template/response.py#L19.
        update_login_page_context(request, template_response.context_data)

    return template_response

def start_two_factor_auth(request: HttpRequest,
                          extra_context: ExtraContext=None,
                          **kwargs: Any) -> HttpResponse:
    two_fa_form_field = 'two_factor_login_view-current_step'
    if two_fa_form_field not in request.POST:
        # Here we inject the 2FA step in the request context if it's missing to
        # force the user to go to the first step of 2FA authentication process.
        # This seems a bit hackish but simplifies things from testing point of
        # view. I don't think this can result in anything bad because all the
        # authentication logic runs after the auth step.
        #
        # If we don't do this, we will have to modify a lot of auth tests to
        # insert this variable in the request.
        request.POST = request.POST.copy()
        request.POST.update({two_fa_form_field: 'auth'})

    """
    This is how Django implements as_view(), so extra_context will be passed
    to the __init__ method of TwoFactorLoginView.

    def as_view(cls, **initkwargs):
        def view(request, *args, **kwargs):
            self = cls(**initkwargs)
            ...

        return view
    """
    two_fa_view = TwoFactorLoginView.as_view(extra_context=extra_context,
                                             **kwargs)
    return two_fa_view(request, **kwargs)

@csrf_exempt
def dev_direct_login(request: HttpRequest, **kwargs: Any) -> HttpResponse:
    # This function allows logging in without a password and should only be called
    # in development environments.  It may be called if the DevAuthBackend is included
    # in settings.AUTHENTICATION_BACKENDS
    if (not dev_auth_enabled()) or settings.PRODUCTION:
        # This check is probably not required, since authenticate would fail without
        # an enabled DevAuthBackend.
        return HttpResponseRedirect(reverse('dev_not_supported'))
    email = request.POST['direct_email']
    subdomain = get_subdomain(request)
    realm = get_realm(subdomain)
    user_profile = authenticate(dev_auth_username=email, realm=realm)
    if user_profile is None:
        return HttpResponseRedirect(reverse('dev_not_supported'))
    do_login(request, user_profile)

    next = request.GET.get('next', '')
    redirect_to = get_safe_redirect_to(next, user_profile.realm.uri)
    return HttpResponseRedirect(redirect_to)

@csrf_exempt
@require_post
@has_request_variables
def api_dev_fetch_api_key(request: HttpRequest, username: str=REQ()) -> HttpResponse:
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

    subdomain = get_subdomain(request)
    realm = get_realm(subdomain)

    return_data = {}  # type: Dict[str, bool]
    user_profile = authenticate(dev_auth_username=username,
                                realm=realm,
                                return_data=return_data)
    if return_data.get("inactive_realm"):
        return json_error(_("This organization has been deactivated."),
                          data={"reason": "realm deactivated"}, status=403)
    if return_data.get("inactive_user"):
        return json_error(_("Your account has been disabled."),
                          data={"reason": "user disable"}, status=403)
    if user_profile is None:
        return json_error(_("This user is not registered."),
                          data={"reason": "unregistered"}, status=403)
    do_login(request, user_profile)
    api_key = get_api_key(user_profile)
    return json_success({"api_key": api_key, "email": user_profile.email})

@csrf_exempt
def api_dev_list_users(request: HttpRequest) -> HttpResponse:
    if not dev_auth_enabled() or settings.PRODUCTION:
        return json_error(_("Dev environment not enabled."))
    users = get_dev_users()
    return json_success(dict(direct_admins=[dict(email=u.email, realm_uri=u.realm.uri)
                                            for u in users if u.is_realm_admin],
                             direct_users=[dict(email=u.email, realm_uri=u.realm.uri)
                                           for u in users if not u.is_realm_admin]))

@csrf_exempt
@require_post
@has_request_variables
def api_fetch_api_key(request: HttpRequest, username: str=REQ(), password: str=REQ()) -> HttpResponse:
    return_data = {}  # type: Dict[str, bool]
    subdomain = get_subdomain(request)
    realm = get_realm(subdomain)
    if username == "google-oauth2-token":
        # This code path is auth for the legacy Android app
        user_profile = authenticate(google_oauth2_token=password,
                                    realm=realm,
                                    return_data=return_data)
    else:
        if not ldap_auth_enabled(realm=get_realm_from_request(request)):
            # In case we don't authenticate against LDAP, check for a valid
            # email. LDAP backend can authenticate against a non-email.
            validate_login_email(username)

        user_profile = authenticate(username=username,
                                    password=password,
                                    realm=realm,
                                    return_data=return_data)
    if return_data.get("inactive_user"):
        return json_error(_("Your account has been disabled."),
                          data={"reason": "user disable"}, status=403)
    if return_data.get("inactive_realm"):
        return json_error(_("This organization has been deactivated."),
                          data={"reason": "realm deactivated"}, status=403)
    if return_data.get("password_auth_disabled"):
        return json_error(_("Password auth is disabled in your team."),
                          data={"reason": "password auth disabled"}, status=403)
    if user_profile is None:
        if return_data.get("valid_attestation"):
            # We can leak that the user is unregistered iff
            # they present a valid authentication string for the user.
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

    api_key = get_api_key(user_profile)
    return json_success({"api_key": api_key, "email": user_profile.email})

def get_auth_backends_data(request: HttpRequest) -> Dict[str, Any]:
    """Returns which authentication methods are enabled on the server"""
    subdomain = get_subdomain(request)
    try:
        realm = Realm.objects.get(string_id=subdomain)
    except Realm.DoesNotExist:
        # If not the root subdomain, this is an error
        if subdomain != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
            raise JsonableError(_("Invalid subdomain"))
        # With the root subdomain, it's an error or not depending
        # whether ROOT_DOMAIN_LANDING_PAGE (which indicates whether
        # there are some realms without subdomains on this server)
        # is set.
        if settings.ROOT_DOMAIN_LANDING_PAGE:
            raise JsonableError(_("Subdomain required"))
        else:
            realm = None
    result = {
        "password": password_auth_enabled(realm),
    }
    for auth_backend_name in AUTH_BACKEND_NAME_MAP:
        key = auth_backend_name.lower()
        result[key] = auth_enabled_helper([auth_backend_name], realm)
    return result

@csrf_exempt
def api_get_auth_backends(request: HttpRequest) -> HttpResponse:
    """Deprecated route; this is to be replaced by api_get_server_settings"""
    auth_backends = get_auth_backends_data(request)
    auth_backends['zulip_version'] = ZULIP_VERSION
    return json_success(auth_backends)

def check_server_incompatibility(request: HttpRequest) -> bool:
    user_agent = parse_user_agent(request.META.get("HTTP_USER_AGENT", "Missing User-Agent"))
    return user_agent['name'] == "ZulipInvalid"

@require_GET
@csrf_exempt
def api_get_server_settings(request: HttpRequest) -> HttpResponse:
    # Log which client is making this request.
    process_client(request, request.user, skip_update_user_activity=True)
    result = dict(
        authentication_methods=get_auth_backends_data(request),
        zulip_version=ZULIP_VERSION,
        push_notifications_enabled=push_notifications_enabled(),
        is_incompatible=check_server_incompatibility(request),
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

@has_request_variables
def json_fetch_api_key(request: HttpRequest, user_profile: UserProfile,
                       password: str=REQ(default='')) -> HttpResponse:
    subdomain = get_subdomain(request)
    realm = get_realm(subdomain)
    if password_auth_enabled(user_profile.realm):
        if not authenticate(username=user_profile.email, password=password,
                            realm=realm):
            return json_error(_("Your username or password is incorrect."))

    api_key = get_api_key(user_profile)
    return json_success({"api_key": api_key})

@csrf_exempt
def api_fetch_google_client_id(request: HttpRequest) -> HttpResponse:
    if not settings.GOOGLE_CLIENT_ID:
        return json_error(_("GOOGLE_CLIENT_ID is not configured"), status=400)
    return json_success({"google_client_id": settings.GOOGLE_CLIENT_ID})

@require_post
def logout_then_login(request: HttpRequest, **kwargs: Any) -> HttpResponse:
    return django_logout_then_login(request, kwargs)

def password_reset(request: HttpRequest, **kwargs: Any) -> HttpResponse:
    realm = get_realm(get_subdomain(request))

    if realm is None:
        # If trying to get to password reset on a subdomain that
        # doesn't exist, just go to find_account.
        redirect_url = reverse('zerver.views.registration.find_account')
        return HttpResponseRedirect(redirect_url)

    return django_password_reset(request,
                                 template_name='zerver/reset.html',
                                 password_reset_form=ZulipPasswordResetForm,
                                 post_reset_redirect='/accounts/password/reset/done/')
