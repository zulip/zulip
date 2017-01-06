# -*- coding: utf-8 -*-
from __future__ import absolute_import
from typing import Any, List, Dict, Optional, Text

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
from django.core.mail import send_mail
from zerver.models import Message, UserProfile, Stream, Subscription, Huddle, \
    Recipient, Realm, UserMessage, DefaultStream, RealmEmoji, RealmAlias, \
    RealmFilter, \
    PreregistrationUser, get_client, UserActivity, \
    get_stream, UserPresence, get_recipient, name_changes_disabled, email_to_username, \
    completely_open, get_unique_open_realm, email_allowed_for_realm, \
    get_realm, get_realm_by_email_domain, list_of_domains_for_realm
from zerver.lib.actions import do_change_password, do_change_full_name, do_change_is_admin, \
    do_activate_user, do_create_user, do_create_realm, set_default_streams, \
    update_user_presence, do_events_register, \
    do_change_tos_version, \
    user_email_is_unique, \
    compute_mit_user_fullname, do_set_muted_topics, \
    get_cross_realm_dicts, \
    do_update_pointer, realm_user_count
from zerver.lib.push_notifications import num_push_devices_for_user
from zerver.forms import RegistrationForm, HomepageForm, RealmCreationForm, ToSForm, \
    CreateUserForm, FindMyTeamForm
from zerver.lib.actions import is_inactive
from django_auth_ldap.backend import LDAPBackend, _LDAPUser
from zerver.lib.validator import check_string, check_list
from zerver.decorator import require_post, authenticated_json_post_view, \
    has_request_variables, \
    JsonableError, get_user_profile_by_email, REQ, \
    zulip_login_required
from zerver.lib.avatar import avatar_url
from zerver.lib.i18n import get_language_list, get_language_name, \
    get_language_list_for_templates
from zerver.lib.response import json_success, json_error
from zerver.lib.utils import statsd, get_subdomain
from version import ZULIP_VERSION
from zproject.backends import password_auth_enabled

from confirmation.models import Confirmation, RealmCreationKey, check_key_is_valid

import requests
import ujson

import calendar
import datetime
import simplejson
import re
from six.moves import urllib, zip_longest, zip, range
import time
import logging

from zproject.jinja2 import render_to_response

def redirect_and_log_into_subdomain(realm, full_name, email_address):
    # type: (Realm, Text, Text) -> HttpResponse
    subdomain_login_uri = ''.join([
        realm.uri,
        reverse('zerver.views.auth.log_into_subdomain')
    ])

    domain = '.' + settings.EXTERNAL_HOST.split(':')[0]
    response = redirect(subdomain_login_uri)

    data = {'name': full_name, 'email': email_address, 'subdomain': realm.subdomain}
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
    elif prereg_user.referred_by:
        # If someone invited you, you are joining their realm regardless
        # of your e-mail address.
        realm = prereg_user.referred_by.realm
    elif prereg_user.realm:
        # You have a realm set, even though nobody referred you. This
        # happens if you sign up through a special URL for an open realm.
        realm = prereg_user.realm
    elif realm_creation:
        # For creating a new realm, there is no existing realm or domain
        realm = None
    elif settings.REALMS_HAVE_SUBDOMAINS:
        realm = get_realm(get_subdomain(request))
    else:
        realm = get_realm_by_email_domain(email)

    if realm and not email_allowed_for_realm(email, realm):
        return render_to_response("zerver/closed_realm.html", {"closed_domain_name": realm.name})

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
        if realm is not None and realm.is_zephyr_mirror_realm:
            # For MIT users, we can get an authoritative name from Hesiod.
            # Technically we should check that this is actually an MIT
            # realm, but we can cross that bridge if we ever get a non-MIT
            # zephyr mirroring realm.
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
            string_id = form.cleaned_data['realm_subdomain']
            realm_name = form.cleaned_data['realm_name']
            org_type = int(form.cleaned_data['realm_org_type'])
            realm = do_create_realm(string_id, realm_name, org_type=org_type)[0]

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

        if first_in_realm:
            do_change_is_admin(user_profile, True)

        if realm_creation and settings.REALMS_HAVE_SUBDOMAINS:
            # Because for realm creation, registration happens on the
            # root domain, we need to log them into the subdomain for
            # their new realm.
            return redirect_and_log_into_subdomain(realm, full_name, email)

        # This dummy_backend check below confirms the user is
        # authenticating to the correct subdomain.
        return_data = {} # type: Dict[str, bool]
        auth_result = authenticate(username=user_profile.email,
                                   realm_subdomain=realm.subdomain,
                                   return_data=return_data,
                                   use_dummy_backend=True)
        if return_data.get('invalid_subdomain'):
            # By construction, this should never happen.
            logging.error("Subdomain mismatch in registration %s: %s" % (
                realm.subdomain, user_profile.email,))
            return redirect('/')
        login(request, auth_result)
        return HttpResponseRedirect(realm.uri + reverse('zerver.views.home'))

    return render_to_response(
        'zerver/register.html',
        {'form': form,
         'email': email,
         'key': key,
         'full_name': request.session.get('authenticated_full_name', None),
         'lock_name': name_validated and name_changes_disabled(realm),
         # password_auth_enabled is normally set via our context processor,
         # but for the registration form, there is no logged in user yet, so
         # we have to set it here.
         'creating_new_team': realm_creation,
         'realms_have_subdomains': settings.REALMS_HAVE_SUBDOMAINS,
         'password_auth_enabled': password_auth_enabled(realm), }, request=request)

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
    special_message_template = None
    if request.user.tos_version is None and settings.FIRST_TIME_TOS_TEMPLATE is not None:
        special_message_template = 'zerver/' + settings.FIRST_TIME_TOS_TEMPLATE
    return render_to_response(
        'zerver/accounts_accept_terms.html',
        {'form': form,
         'email': email,
         'special_message_template': special_message_template},
        request=request)

def create_preregistration_user(email, request, realm_creation=False):
    # type: (Text, HttpRequest, bool) -> HttpResponse
    realm_str = request.session.pop('realm_str', None)
    if realm_str is not None:
        # realm_str was set in accounts_home_with_realm_str.
        # The user is trying to sign up for a completely open realm,
        # so create them a PreregistrationUser for that realm
        return PreregistrationUser.objects.create(email=email,
                                                  realm=get_realm(realm_str),
                                                  realm_creation=realm_creation)

    return PreregistrationUser.objects.create(email=email, realm_creation=realm_creation)

def accounts_home_with_realm_str(request, realm_str):
    # type: (HttpRequest, str) -> HttpResponse
    if not settings.REALMS_HAVE_SUBDOMAINS and completely_open(get_realm(realm_str)):
        # You can sign up for a completely open realm through a
        # special registration path that contains the domain in the
        # URL. We store this information in the session rather than
        # elsewhere because we don't have control over URL or form
        # data for folks registering through OpenID.
        request.session["realm_str"] = realm_str
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
                                                  additional_context=context,
                                                  host=request.get_host())

def redirect_to_email_login_url(email):
    # type: (str) -> HttpResponseRedirect
    login_url = reverse('django.contrib.auth.views.login')
    redirect_url = login_url + '?email=' + urllib.parse.quote_plus(email)
    return HttpResponseRedirect(redirect_url)

def create_realm(request, creation_key=None):
    # type: (HttpRequest, Optional[Text]) -> HttpResponse
    if not settings.OPEN_REALM_CREATION:
        if creation_key is None:
            return render_to_response("zerver/realm_creation_failed.html",
                                      {'message': _('New organization creation disabled.')})
        elif not check_key_is_valid(creation_key):
            return render_to_response("zerver/realm_creation_failed.html",
                                      {'message': _('The organization creation link has been expired'
                                                    ' or is not valid.')})

    # When settings.OPEN_REALM_CREATION is enabled, anyone can create a new realm,
    # subject to a few restrictions on their email address.
    if request.method == 'POST':
        form = RealmCreationForm(request.POST)
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
            # Maybe the user is trying to log in
            return redirect_to_email_login_url(email)
    else:
        form = RealmCreationForm()
    return render_to_response('zerver/create_realm.html',
                              {'form': form, 'current_url': request.get_full_path},
                              request=request)

def confirmation_key(request):
    # type: (HttpRequest) -> HttpResponse
    return json_success(request.session.get('confirmation_key'))

def get_realm_from_request(request):
    # type: (HttpRequest) -> Realm
    if settings.REALMS_HAVE_SUBDOMAINS:
        realm_str = get_subdomain(request)
    else:
        realm_str = request.session.get("realm_str")
    return get_realm(realm_str)

def accounts_home(request):
    # type: (HttpRequest) -> HttpResponse
    realm = get_realm_from_request(request)
    if request.method == 'POST':
        form = HomepageForm(request.POST, realm=realm)
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
        form = HomepageForm(realm=realm)
    return render_to_response('zerver/accounts_home.html',
                              {'form': form, 'current_url': request.get_full_path},
                              request=request)

def approximate_unread_count(user_profile):
    # type: (UserProfile) -> int
    not_in_home_view_recipients = [sub.recipient.id for sub in
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

def home(request):
    # type: (HttpRequest) -> HttpResponse
    if not settings.SUBDOMAINS_HOMEPAGE:
        return home_real(request)

    # If settings.SUBDOMAINS_HOMEPAGE, sends the user the landing
    # page, not the login form, on the root domain

    subdomain = get_subdomain(request)
    if subdomain != "":
        return home_real(request)

    return render_to_response('zerver/hello.html',
                              request=request)

@zulip_login_required
def home_real(request):
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

    narrow = [] # type: List[List[Text]]
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
        zulip_version         = ZULIP_VERSION,
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
        people_list           = register_ret['realm_users'],
        bot_list              = register_ret['realm_bots'],
        initial_pointer       = register_ret['pointer'],
        initial_presences     = register_ret['presences'],
        initial_servertime    = time.time(), # Used for calculating relative presence age
        fullname              = user_profile.full_name,
        email                 = user_profile.email,
        domain                = user_profile.realm.domain,
        domains               = list_of_domains_for_realm(user_profile.realm),
        realm_name            = register_ret['realm_name'],
        realm_invite_required = register_ret['realm_invite_required'],
        realm_invite_by_admins_only = register_ret['realm_invite_by_admins_only'],
        realm_authentication_methods = register_ret['realm_authentication_methods'],
        realm_create_stream_by_admins_only = register_ret['realm_create_stream_by_admins_only'],
        realm_add_emoji_by_admins_only = register_ret['realm_add_emoji_by_admins_only'],
        realm_allow_message_editing = register_ret['realm_allow_message_editing'],
        realm_message_content_edit_limit_seconds = register_ret['realm_message_content_edit_limit_seconds'],
        realm_restricted_to_domain = register_ret['realm_restricted_to_domain'],
        realm_default_language = register_ret['realm_default_language'],
        realm_waiting_period_threshold = register_ret['realm_waiting_period_threshold'],
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
        cross_realm_bots      = list(get_cross_realm_dicts()),
        use_websockets        = settings.USE_WEBSOCKETS,

        # Stream message notification settings:
        stream_desktop_notifications_enabled = user_profile.enable_stream_desktop_notifications,
        stream_sounds_enabled = user_profile.enable_stream_sounds,

        # Private message and @-mention notification settings:
        desktop_notifications_enabled = desktop_notifications_enabled,
        sounds_enabled = user_profile.enable_sounds,
        enable_offline_email_notifications = user_profile.enable_offline_email_notifications,
        pm_content_in_desktop_notifications = user_profile.pm_content_in_desktop_notifications,
        enable_offline_push_notifications = user_profile.enable_offline_push_notifications,
        enable_online_push_notifications = user_profile.enable_online_push_notifications,
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
        avatar_url_medium     = avatar_url(user_profile, medium=True),
        avatar_source         = user_profile.avatar_source,
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
                                   'page_params': simplejson.encoder.JSONEncoderForHTML().encode(page_params),
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

@authenticated_json_post_view
@has_request_variables
def json_set_muted_topics(request, user_profile,
                          muted_topics=REQ(validator=check_list(check_list(check_string, length=2)), default=[])):
    # type: (HttpRequest, UserProfile, List[List[Text]]) -> HttpResponse
    do_set_muted_topics(user_profile, muted_topics)
    return json_success()

def generate_204(request):
    # type: (HttpRequest) -> HttpResponse
    return HttpResponse(content=None, status=204)

try:
    import mailer
    send_mail = mailer.send_mail
except ImportError:
    # no mailer app present, stick with default
    pass

def send_find_my_team_emails(user_profile):
    # type: (UserProfile) -> None
    text_template = 'zerver/emails/find_team/find_team_email.txt'
    html_template = 'zerver/emails/find_team/find_team_email.html'
    context = {'user_profile': user_profile}
    text_content = loader.render_to_string(text_template, context)
    html_content = loader.render_to_string(html_template, context)
    sender = settings.NOREPLY_EMAIL_ADDRESS
    recipients = [user_profile.email]
    subject = loader.render_to_string('zerver/emails/find_team/find_team_email.subject').strip()

    send_mail(subject, text_content, sender, recipients, html_message=html_content)

def find_my_team(request):
    # type: (HttpRequest) -> HttpResponse
    url = reverse('zerver.views.find_my_team')

    emails = []  # type: List[Text]
    if request.method == 'POST':
        form = FindMyTeamForm(request.POST)
        if form.is_valid():
            emails = form.cleaned_data['emails']
            for user_profile in UserProfile.objects.filter(email__in=emails):
                send_find_my_team_emails(user_profile)

            # Note: Show all the emails in the result otherwise this
            # feature can be used to ascertain which email addresses
            # are associated with Zulip.
            data = urllib.parse.urlencode({'emails': ','.join(emails)})
            return redirect(url + "?" + data)
    else:
        form = FindMyTeamForm()
        result = request.GET.get('emails')
        if result:
            for email in result.split(','):
                try:
                    validators.validate_email(email)
                    emails.append(email)
                except ValidationError:
                    pass

    return render_to_response('zerver/find_my_team.html',
                              {'form': form, 'current_url': lambda: url,
                               'emails': emails},
                              request=request)
