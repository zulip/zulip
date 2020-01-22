from django.forms import Form
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.views import login as django_login_page, \
    logout_then_login as django_logout_then_login
from django.contrib.auth.views import password_reset as django_password_reset
from django.urls import reverse
from zerver.decorator import require_post, \
    process_client, do_login, log_view_func
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, \
    HttpResponseServerError
from django.template.response import SimpleTemplateResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe
from django.utils.translation import ugettext as _
from django.utils.http import is_safe_url
from django.core import signing
import urllib
from typing import Any, Dict, List, Optional, Mapping

from confirmation.models import Confirmation, create_confirmation_link
from zerver.context_processors import zulip_default_context, get_realm_from_request, \
    login_context
from zerver.forms import HomepageForm, OurAuthenticationForm, \
    WRONG_SUBDOMAIN_ERROR, DEACTIVATED_ACCOUNT_ERROR, ZulipPasswordResetForm, \
    AuthenticationTokenForm
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
    AUTH_BACKEND_NAME_MAP, auth_enabled_helper, saml_auth_enabled, SAMLAuthBackend, \
    redirect_to_config_error, ZulipRemoteUserBackend
from version import ZULIP_VERSION

import jwt
import logging

from social_django.utils import load_backend, load_strategy

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
                                password_required: bool=True, full_name: Optional[str]=None,
                                full_name_validated: bool=False) -> HttpResponse:
    realm = None
    if not realm_creation:
        try:
            realm = get_realm(get_subdomain(request))
        except Realm.DoesNotExist:
            pass
    return PreregistrationUser.objects.create(
        email=email,
        realm_creation=realm_creation,
        password_required=password_required,
        realm=realm,
        full_name=full_name,
        full_name_validated=full_name_validated
    )

def maybe_send_to_registration(request: HttpRequest, email: str, full_name: str='',
                               is_signup: bool=False, password_required: bool=True,
                               multiuse_object_key: str='',
                               full_name_validated: bool=False) -> HttpResponse:
    """Given a successful authentication for an email address (i.e. we've
    confirmed the user controls the email address) that does not
    currently have a Zulip account in the target realm, send them to
    the registration flow or the "continue to registration" flow,
    depending on is_signup, whether the email address can join the
    organization (checked in HomepageForm), and similar details.
    """
    if multiuse_object_key:
        from_multiuse_invite = True
        multiuse_obj = Confirmation.objects.get(confirmation_key=multiuse_object_key).content_object
        realm = multiuse_obj.realm
        streams_to_subscribe = multiuse_obj.streams.all()
        invited_as = multiuse_obj.invited_as
    else:
        from_multiuse_invite = False
        multiuse_obj = None
        try:
            realm = get_realm(get_subdomain(request))
        except Realm.DoesNotExist:
            realm = None
        streams_to_subscribe = None
        invited_as = PreregistrationUser.INVITE_AS['MEMBER']

    form = HomepageForm({'email': email}, realm=realm, from_multiuse_invite=from_multiuse_invite)
    if form.is_valid():
        # If the email address is allowed to sign up for an account in
        # this organization, construct a PreregistrationUser and
        # Confirmation objects, and then send the user to account
        # creation or confirm-continue-registration depending on
        # is_signup.
        try:
            prereg_user = PreregistrationUser.objects.filter(
                email__iexact=email, realm=realm).latest("invited_at")

            # password_required and full_name data passed here as argument should take precedence
            # over the defaults with which the existing PreregistrationUser that we've just fetched
            # was created.
            prereg_user.password_required = password_required
            update_fields = ["password_required"]
            if full_name:
                prereg_user.full_name = full_name
                prereg_user.full_name_validated = full_name_validated
                update_fields.extend(["full_name", "full_name_validated"])
            prereg_user.save(update_fields=update_fields)
        except PreregistrationUser.DoesNotExist:
            prereg_user = create_preregistration_user(
                email, request,
                password_required=password_required,
                full_name=full_name,
                full_name_validated=full_name_validated
            )

        if multiuse_object_key:
            request.session.modified = True
            if streams_to_subscribe is not None:
                prereg_user.streams.set(streams_to_subscribe)
            prereg_user.invited_as = invited_as
            prereg_user.save()

        # We want to create a confirmation link to create an account
        # in the current realm, i.e. one with a hostname of
        # realm.host.  For the Apache REMOTE_USER_SSO auth code path,
        # this is preferable over realm.get_host() because the latter
        # contains the port number of the Apache instance and we want
        # to send the user back to nginx.  But if we're in the realm
        # creation code path, there might not be a realm yet, so we
        # have to use request.get_host().
        if realm is not None:
            host = realm.host
        else:
            host = request.get_host()
        confirmation_link = create_confirmation_link(prereg_user, host,
                                                     Confirmation.USER_REGISTRATION)
        if is_signup:
            return redirect(confirmation_link)

        context = {'email': email,
                   'continue_link': confirmation_link,
                   'full_name': full_name}
        return render(request,
                      'zerver/confirm_continue_registration.html',
                      context=context)

    # This email address it not allowed to join this organization, so
    # just send the user back to the registration page.
    url = reverse('register')
    context = login_context(request)
    extra_context = {'form': form, 'current_url': lambda: url,
                     'from_multiuse_invite': from_multiuse_invite,
                     'multiuse_object_key': multiuse_object_key}  # type: Mapping[str, Any]
    context.update(extra_context)
    return render(request, 'zerver/accounts_home.html', context=context)

def redirect_to_subdomain_login_url() -> HttpResponseRedirect:
    login_url = reverse('django.contrib.auth.views.login')
    redirect_url = login_url + '?subdomain=1'
    return HttpResponseRedirect(redirect_url)

def login_or_register_remote_user(request: HttpRequest, remote_username: str,
                                  user_profile: Optional[UserProfile], full_name: str='',
                                  mobile_flow_otp: Optional[str]=None,
                                  is_signup: bool=False, redirect_to: str='',
                                  multiuse_object_key: str='',
                                  full_name_validated: bool=False) -> HttpResponse:
    """Given a successful authentication showing the user controls given
    email address (remote_username) and potentially a UserProfile
    object (if the user already has a Zulip account), redirect the
    browser to the appropriate place:

    * The logged-in app if the user already has a Zulip account and is
      trying to login, potentially to an initial narrow or page that had been
      saved in the `redirect_to` parameter.
    * The registration form if is_signup was set (i.e. the user is
      trying to create a Zulip account)
    * A special `confirm_continue_registration.html` "do you want to
      register or try another account" if the user doesn't have a
      Zulip account but is_signup is False (i.e. the user tried to login
      and then did social authentication selecting an email address that does
      not have a Zulip account in this organization).
    * A zulip:// URL to send control back to the mobile apps if they
      are doing authentication using the mobile_flow_otp flow.
    """
    email = remote_user_to_email(remote_username)
    if user_profile is None or user_profile.is_mirror_dummy:
        # We have verified the user controls an email address, but
        # there's no associated Zulip user account.  Consider sending
        # the request to registration.
        return maybe_send_to_registration(request, email, full_name, password_required=False,
                                          is_signup=is_signup, multiuse_object_key=multiuse_object_key,
                                          full_name_validated=full_name_validated)

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

        # Since we are returning an API key instead of going through
        # the Django login() function (which creates a browser
        # session, etc.), the "new login" signal handler (which
        # triggers an email notification new logins) will not run
        # automatically.  So we call it manually here.
        #
        # Arguably, sending a fake 'user_logged_in' signal would be a better approach:
        #   user_logged_in.send(sender=user_profile.__class__, request=request, user=user_profile)
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
    subdomain = get_subdomain(request)
    try:
        realm = get_realm(subdomain)  # type: Optional[Realm]
    except Realm.DoesNotExist:
        realm = None

    if not auth_enabled_helper([ZulipRemoteUserBackend.auth_backend_name], realm):
        return redirect_to_config_error("remoteuser/backend_disabled")

    try:
        remote_user = request.META["REMOTE_USER"]
    except KeyError:
        return redirect_to_config_error("remoteuser/remote_user_header_missing")

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
    if realm is None:
        user_profile = None
    else:
        user_profile = authenticate(remote_user=remote_user, realm=realm)

    redirect_to = request.GET.get('next', '')

    return login_or_register_remote_user(request, remote_user, user_profile,
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

    try:
        realm = get_realm(subdomain)
    except Realm.DoesNotExist:
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

def oauth_redirect_to_root(request: HttpRequest, url: str,
                           sso_type: str, is_signup: bool=False,
                           extra_url_params: Dict[str, str]={}) -> HttpResponse:
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

    params = {**params, **extra_url_params}

    return redirect(main_site_uri + '?' + urllib.parse.urlencode(params))

def start_social_login(request: HttpRequest, backend: str, extra_arg: Optional[str]=None
                       ) -> HttpResponse:
    backend_url = reverse('social:begin', args=[backend])
    extra_url_params = {}  # type: Dict[str, str]
    if backend == "saml":
        result = SAMLAuthBackend.check_config()
        if result is not None:
            return result

        # This backend requires the name of the IdP (from the list of configured ones)
        # to be passed as the parameter.
        if not extra_arg or extra_arg not in settings.SOCIAL_AUTH_SAML_ENABLED_IDPS:
            logging.info("Attempted to initiate SAML authentication with wrong idp argument: {}"
                         .format(extra_arg))
            return redirect_to_config_error("saml")
        extra_url_params = {'idp': extra_arg}
    if (backend == "github") and not (settings.SOCIAL_AUTH_GITHUB_KEY and
                                      settings.SOCIAL_AUTH_GITHUB_SECRET):
        return redirect_to_config_error("github")
    if (backend == "google") and not (settings.SOCIAL_AUTH_GOOGLE_KEY and
                                      settings.SOCIAL_AUTH_GOOGLE_SECRET):
        return redirect_to_config_error("google")
    # TODO: Add a similar block for AzureAD.

    return oauth_redirect_to_root(request, backend_url, 'social', extra_url_params=extra_url_params)

def start_social_signup(request: HttpRequest, backend: str, extra_arg: Optional[str]=None
                        ) -> HttpResponse:
    backend_url = reverse('social:begin', args=[backend])
    extra_url_params = {}  # type: Dict[str, str]
    if backend == "saml":
        result = SAMLAuthBackend.check_config()
        if result is not None:
            return result

        if not extra_arg or extra_arg not in settings.SOCIAL_AUTH_SAML_ENABLED_IDPS:
            logging.info("Attempted to initiate SAML authentication with wrong idp argument: {}"
                         .format(extra_arg))
            return redirect_to_config_error("saml")
        extra_url_params = {'idp': extra_arg}
    return oauth_redirect_to_root(request, backend_url, 'social', is_signup=True,
                                  extra_url_params=extra_url_params)

def authenticate_remote_user(realm: Realm,
                             email_address: Optional[str]) -> Optional[UserProfile]:
    if email_address is None:
        # No need to authenticate if email address is None. We already
        # know that user_profile would be None as well. In fact, if we
        # call authenticate in this case, we might get an exception from
        # ZulipDummyBackend which doesn't accept a None as a username.
        logging.warning("Email address was None while trying to authenticate "
                        "remote user.")
        return None

    user_profile = authenticate(username=email_address,
                                realm=realm,
                                use_dummy_backend=True)
    return user_profile

_subdomain_token_salt = 'zerver.views.auth.log_into_subdomain'

@log_view_func
def log_into_subdomain(request: HttpRequest, token: str) -> HttpResponse:
    """Given a valid signed authentication token (generated by
    redirect_and_log_into_subdomain called on auth.zulip.example.com),
    call login_or_register_remote_user, passing all the authentication
    result data that had been encoded in the signed token.
    """

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
    full_name_validated = data.get('full_name_validated', False)

    if 'multiuse_object_key' in data:
        multiuse_object_key = data['multiuse_object_key']
    else:
        multiuse_object_key = ''

    # We cannot pass the actual authenticated user_profile object that
    # was fetched by the original authentication backend and passed
    # into redirect_and_log_into_subdomain through a signed URL token,
    # so we need to re-fetch it from the database.
    if is_signup:
        # If we are creating a new user account, user_profile will
        # always have been None, so we set that here.  In the event
        # that a user account with this email was somehow created in a
        # race, the eventual registration code will catch that and
        # throw an error, so we don't need to check for that here.
        user_profile = None
    else:
        # We're just trying to login.  We can be reasonably confident
        # that this subdomain actually has a corresponding active
        # realm, since the signed cookie proves there was one very
        # recently.  But as part of fetching the UserProfile object
        # for the target user, we use DummyAuthBackend, which
        # conveniently re-validates that the realm and user account
        # were not deactivated in the meantime.

        # Note: Ideally, we'd have a nice user-facing error message
        # for the case where this auth fails (because e.g. the realm
        # or user was deactivated since the signed cookie was
        # generated < 15 seconds ago), but the authentication result
        # is correct in those cases and such a race would be very
        # rare, so a nice error message is low priority.
        realm = get_realm(subdomain)
        user_profile = authenticate_remote_user(realm, email_address)

    return login_or_register_remote_user(request, email_address, user_profile,
                                         full_name,
                                         is_signup=is_signup, redirect_to=redirect_to,
                                         multiuse_object_key=multiuse_object_key,
                                         full_name_validated=full_name_validated)

def redirect_and_log_into_subdomain(realm: Realm, full_name: str, email_address: str,
                                    is_signup: bool=False, redirect_to: str='',
                                    multiuse_object_key: str='',
                                    full_name_validated: bool=False) -> HttpResponse:
    data = {'name': full_name, 'email': email_address, 'subdomain': realm.subdomain,
            'is_signup': is_signup, 'next': redirect_to,
            'multiuse_object_key': multiuse_object_key,
            'full_name_validated': full_name_validated}
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

def add_dev_login_context(realm: Optional[Realm], context: Dict[str, Any]) -> None:
    users = get_dev_users(realm)
    context['current_realm'] = realm
    context['all_realms'] = Realm.objects.all()

    context['direct_admins'] = [u for u in users if u.is_realm_admin]
    context['guest_users'] = [u for u in users if u.is_guest]
    context['direct_users'] = [u for u in users if not (u.is_realm_admin or u.is_guest)]

def update_login_page_context(request: HttpRequest, context: Dict[str, Any]) -> None:
    for key in ('email', 'subdomain', 'already_registered', 'is_deactivated'):
        try:
            context[key] = request.GET[key]
        except KeyError:
            pass

    context['deactivated_account_error'] = DEACTIVATED_ACCOUNT_ERROR
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
    # To support previewing the Zulip login pages, we have a special option
    # that disables the default behavior of redirecting logged-in users to the
    # logged-in app.
    is_preview = 'preview' in request.GET
    if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:
        if request.user and request.user.is_verified():
            return HttpResponseRedirect(request.user.realm.uri)
    elif request.user.is_authenticated and not is_preview:
        return HttpResponseRedirect(request.user.realm.uri)
    if is_subdomain_root_or_alias(request) and settings.ROOT_DOMAIN_LANDING_PAGE:
        redirect_url = reverse('zerver.views.registration.realm_redirect')
        if request.GET:
            redirect_url = "{}?{}".format(redirect_url, request.GET.urlencode())
        return HttpResponseRedirect(redirect_url)

    realm = get_realm_from_request(request)
    if realm and realm.deactivated:
        return redirect_to_deactivation_notice()

    extra_context = kwargs.pop('extra_context', {})
    if dev_auth_enabled() and kwargs.get("template_name") == "zerver/dev_login.html":
        if 'new_realm' in request.POST:
            try:
                realm = get_realm(request.POST['new_realm'])
            except Realm.DoesNotExist:
                realm = None

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
        extra_context.update(login_context(request))
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
    return json_success({"api_key": api_key, "email": user_profile.delivery_email})

@csrf_exempt
def api_dev_list_users(request: HttpRequest) -> HttpResponse:
    if not dev_auth_enabled() or settings.PRODUCTION:
        return json_error(_("Dev environment not enabled."))
    users = get_dev_users()
    return json_success(dict(direct_admins=[dict(email=u.delivery_email, realm_uri=u.realm.uri)
                                            for u in users if u.is_realm_admin],
                             direct_users=[dict(email=u.delivery_email, realm_uri=u.realm.uri)
                                           for u in users if not u.is_realm_admin]))

@csrf_exempt
@require_post
@has_request_variables
def api_fetch_api_key(request: HttpRequest, username: str=REQ(), password: str=REQ()) -> HttpResponse:
    return_data = {}  # type: Dict[str, bool]
    subdomain = get_subdomain(request)
    realm = get_realm(subdomain)
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
    return json_success({"api_key": api_key, "email": user_profile.delivery_email})

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

def check_server_incompatibility(request: HttpRequest) -> bool:
    user_agent = parse_user_agent(request.META.get("HTTP_USER_AGENT", "Missing User-Agent"))
    return user_agent['name'] == "ZulipInvalid"

@require_safe
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
    context.update(login_context(request))
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
            "realm_description",
            "external_authentication_methods"]:
        if context[settings_item] is not None:
            result[settings_item] = context[settings_item]
    return json_success(result)

@has_request_variables
def json_fetch_api_key(request: HttpRequest, user_profile: UserProfile,
                       password: str=REQ(default='')) -> HttpResponse:
    subdomain = get_subdomain(request)
    realm = get_realm(subdomain)
    if password_auth_enabled(user_profile.realm):
        if not authenticate(username=user_profile.delivery_email, password=password,
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
    if not Realm.objects.filter(string_id=get_subdomain(request)).exists():
        # If trying to get to password reset on a subdomain that
        # doesn't exist, just go to find_account.
        redirect_url = reverse('zerver.views.registration.find_account')
        return HttpResponseRedirect(redirect_url)

    return django_password_reset(request,
                                 template_name='zerver/reset.html',
                                 password_reset_form=ZulipPasswordResetForm,
                                 post_reset_redirect='/accounts/password/reset/done/')

@csrf_exempt
def saml_sp_metadata(request: HttpRequest, **kwargs: Any) -> HttpResponse:  # nocoverage
    """
    This is the view function for generating our SP metadata
    for SAML authentication. It's meant for helping check the correctness
    of the configuration when setting up SAML, or for obtaining the XML metadata
    if the IdP requires it.
    Taken from https://python-social-auth.readthedocs.io/en/latest/backends/saml.html
    """
    if not saml_auth_enabled():
        return redirect_to_config_error("saml")

    complete_url = reverse('social:complete', args=("saml",))
    saml_backend = load_backend(load_strategy(request), "saml",
                                complete_url)
    metadata, errors = saml_backend.generate_metadata_xml()
    if not errors:
        return HttpResponse(content=metadata,
                            content_type='text/xml')

    return HttpResponseServerError(content=', '.join(errors))
